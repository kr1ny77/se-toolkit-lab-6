#!/usr/bin/env python3
"""
Documentation Agent CLI - Calls an LLM with tools to read documentation.

Tools:
- read_file: Read a file from the project
- list_files: List files in a directory

Usage:
    uv run agent.py "Your question here"

Output:
    JSON to stdout: {"answer": "...", "source": "...", "tool_calls": [...]}
    All debug output goes to stderr.
"""

import json
import os
import sys
from pathlib import Path
from typing import Optional

import requests
from dotenv import load_dotenv

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

PROJECT_ROOT = Path(__file__).parent


def load_env():
    """Load environment variables from .env.agent.secret."""
    env_path = PROJECT_ROOT / ".env.agent.secret"
    if not env_path.exists():
        print(f"Error: {env_path} not found", file=sys.stderr)
        sys.exit(1)

    load_dotenv(env_path)

    api_key = os.getenv("LLM_API_KEY")
    api_base = os.getenv("LLM_API_BASE")
    model = os.getenv("LLM_MODEL")

    if not api_key:
        print("Error: LLM_API_KEY not set", file=sys.stderr)
        sys.exit(1)
    if not api_base:
        print("Error: LLM_API_BASE not set", file=sys.stderr)
        sys.exit(1)
    if not model:
        print("Error: LLM_MODEL not set", file=sys.stderr)
        sys.exit(1)

    return api_key, api_base, model


# ---------------------------------------------------------------------------
# Tools
# ---------------------------------------------------------------------------

def validate_path(path: str) -> Path:
    """
    Validate and resolve a relative path within project root.
    
    Security: prevents directory traversal attacks (../).
    """
    full_path = (PROJECT_ROOT / path).resolve()
    
    # Security check: ensure path is within project root
    if not str(full_path).startswith(str(PROJECT_ROOT.resolve())):
        raise ValueError(f"Access denied: path outside project root")
    
    return full_path


def read_file(path: str) -> str:
    """
    Read a file from the project.
    
    Args:
        path: Relative path to the file (e.g., "wiki/git-workflow.md")
    
    Returns:
        File content as string (truncated to 10000 chars if longer),
        or error message if file doesn't exist or access denied.
    """
    try:
        full_path = validate_path(path)
    except ValueError as e:
        return f"Error: {e}"
    
    if not full_path.exists():
        return f"Error: File not found: {path}"
    
    if not full_path.is_file():
        return f"Error: Not a file: {path}"
    
    try:
        content = full_path.read_text()
        # Truncate if too long
        if len(content) > 10000:
            content = content[:10000] + "\n... (truncated)"
        return content
    except Exception as e:
        return f"Error reading file: {e}"


def list_files(dir_path: str) -> str:
    """
    List files in a directory.
    
    Args:
        dir_path: Relative path to the directory (e.g., "wiki")
    
    Returns:
        List of files and directories, one per line,
        or error message if directory doesn't exist or access denied.
    """
    try:
        full_path = validate_path(dir_path)
    except ValueError as e:
        return f"Error: {e}"
    
    if not full_path.exists():
        return f"Error: Directory not found: {dir_path}"
    
    if not full_path.is_dir():
        return f"Error: Not a directory: {dir_path}"
    
    try:
        items = []
        for item in sorted(full_path.iterdir()):
            prefix = "[DIR] " if item.is_dir() else ""
            items.append(f"{prefix}{item.name}")
        return "\n".join(items)
    except Exception as e:
        return f"Error listing directory: {e}"


# ---------------------------------------------------------------------------
# Tool schemas for LLM
# ---------------------------------------------------------------------------

TOOL_SCHEMAS = [
    {
        "type": "function",
        "function": {
            "name": "read_file",
            "description": "Read a file from the project. Use this to read documentation in the wiki folder, source code, or configuration files. After using list_files to discover files, use read_file to get the content.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "Relative path to the file from project root, e.g., 'wiki/git-workflow.md', 'pyproject.toml', 'backend/app/main.py'",
                    }
                },
                "required": ["path"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "list_files",
            "description": "List files in a directory. Use this to explore the project structure when you don't know the exact file path. For example, use list_files('wiki') to see what documentation files are available.",
            "parameters": {
                "type": "object",
                "properties": {
                    "dir_path": {
                        "type": "string",
                        "description": "Relative directory path from project root, e.g., 'wiki', 'backend/app', 'backend/app/routers'",
                    }
                },
                "required": ["dir_path"],
            },
        },
    },
]

TOOLS = {
    "read_file": read_file,
    "list_files": list_files,
}


# ---------------------------------------------------------------------------
# System prompt
# ---------------------------------------------------------------------------

SYSTEM_PROMPT = """You are a helpful assistant for the Learning Management Service project.

You have access to these tools:
1. read_file - Read a file from the project (use for documentation, source code, config files)
2. list_files - List files in a directory (use to explore project structure)

Guidelines:
- For questions about documentation → use list_files to find the relevant wiki file, then read_file to read it
- Always cite your sources: mention the file path in your answer
- Think step by step: first explore with list_files if needed, then read specific files with read_file
- If you don't find the answer after exploring, say so honestly

When answering:
- Provide a clear, concise answer based on what you read
- Include the source file path (e.g., "wiki/git-workflow.md")
- If referencing a specific section, mention the section heading"""


# ---------------------------------------------------------------------------
# Agent loop
# ---------------------------------------------------------------------------

def call_llm(messages: list, api_key: str, api_base: str, model: str) -> dict:
    """
    Call the LLM API with tool support.
    
    Returns:
        dict with 'content' and/or 'tool_calls' keys
    """
    url = f"{api_base}/chat/completions"
    
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {api_key}",
    }
    
    payload = {
        "model": model,
        "messages": messages,
        "tools": TOOL_SCHEMAS,
        "tool_choice": "auto",
    }
    
    print(f"Calling LLM at {url}...", file=sys.stderr)
    
    response = requests.post(url, headers=headers, json=payload, timeout=60)
    
    if response.status_code != 200:
        print(f"LLM API error: {response.status_code} - {response.text[:500]}", file=sys.stderr)
        response.raise_for_status()
    
    result = response.json()
    
    if not result.get("choices"):
        print(f"LLM returned no choices: {result}", file=sys.stderr)
        return {"content": "No response from LLM"}
    
    return result["choices"][0]["message"]


def run_agent(question: str, max_iterations: int = 10) -> dict:
    """
    Run the agentic loop.
    
    Args:
        question: User's question
        max_iterations: Maximum tool call iterations
    
    Returns:
        dict with 'answer', 'source', and 'tool_calls' fields
    """
    api_key, api_base, model = load_env()
    
    # Initialize messages
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": question},
    ]
    
    tool_calls_log = []
    source = None
    
    for iteration in range(max_iterations):
        print(f"Iteration {iteration + 1}/{max_iterations}...", file=sys.stderr)
        
        # Call LLM
        response = call_llm(messages, api_key, api_base, model)
        
        # Check for content (final answer)
        content = response.get("content") or ""
        
        # Check for tool calls
        tool_calls = response.get("tool_calls") or []
        
        if not tool_calls:
            # No more tool calls - we have the final answer
            print(f"Final answer received", file=sys.stderr)
            break
        
        # Add assistant message with tool_calls to history
        messages.append({
            "role": "assistant",
            "content": None,
            "tool_calls": tool_calls,
        })
        
        # Execute tool calls and collect results
        for tool_call in tool_calls:
            function = tool_call.get("function", {})
            name = function.get("name", "")
            arguments_str = function.get("arguments", "{}")
            
            try:
                arguments = json.loads(arguments_str)
            except json.JSONDecodeError:
                arguments = {}
            
            print(f"Calling tool: {name} with args: {arguments}", file=sys.stderr)
            
            # Log tool call for output
            tool_call_log = {
                "tool": name,
                "args": arguments,
                "result": None,
            }
            
            # Execute tool
            if name in TOOLS:
                try:
                    result = TOOLS[name](**arguments)
                    tool_call_log["result"] = result
                    
                    # Track source if it's a read_file call
                    if name == "read_file" and not source:
                        source = arguments.get("path", "")
                    
                except Exception as e:
                    tool_call_log["result"] = f"Error: {e}"
            else:
                tool_call_log["result"] = f"Error: Unknown tool '{name}'"
            
            tool_calls_log.append(tool_call_log)
            
            # Add tool response to messages
            messages.append({
                "role": "tool",
                "tool_call_id": tool_call.get("id", "unknown"),
                "content": str(tool_call_log["result"]),
            })
    
    # Extract final answer
    if not content:
        # If no content in last response, synthesize from tool results
        if tool_calls_log:
            last_result = tool_calls_log[-1].get("result", "")
            content = f"Based on the tool results: {last_result}"
        else:
            content = "I couldn't find an answer to your question."
    
    return {
        "answer": content,
        "source": source,
        "tool_calls": tool_calls_log,
    }


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    """Main entry point."""
    if len(sys.argv) < 2:
        print("Usage: uv run agent.py \"Your question here\"", file=sys.stderr)
        sys.exit(1)
    
    question = sys.argv[1]
    
    # Run agent
    result = run_agent(question)
    
    # Output JSON
    print(json.dumps(result))


if __name__ == "__main__":
    main()
