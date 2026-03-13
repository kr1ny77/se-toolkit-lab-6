#!/usr/bin/env python3
"""
System Agent CLI - Calls an LLM with tools to answer questions.

Tools:
- read_file: Read a file from the project
- list_files: List files in a directory
- query_api: Query the backend LMS API

Usage:
    uv run agent.py "Your question here"

Output:
    JSON to stdout: {"answer": "...", "tool_calls": [...], "source": "..."}
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

WIKI_DIR = Path(__file__).parent / "wiki"
PROJECT_ROOT = Path(__file__).parent


def load_env():
    """Load environment variables from .env files."""
    # Load LLM config from .env.agent.secret
    agent_env = PROJECT_ROOT / ".env.agent.secret"
    if agent_env.exists():
        load_dotenv(agent_env)
    
    # Load LMS API key from .env.docker.secret
    docker_env = PROJECT_ROOT / ".env.docker.secret"
    if docker_env.exists():
        load_dotenv(docker_env, override=False)
    
    # Validate required variables
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

def read_file(path: str) -> str:
    """
    Read a file from the project.
    
    Args:
        path: Relative path to the file (e.g., "wiki/backend.md", "pyproject.toml")
    
    Returns:
        File content as string (truncated to 10000 chars if longer)
    """
    # Resolve path relative to project root
    if not os.path.isabs(path):
        full_path = PROJECT_ROOT / path
    else:
        full_path = Path(path)
    
    # Security: ensure path is within project root
    try:
        full_path = full_path.resolve()
        if not str(full_path).startswith(str(PROJECT_ROOT.resolve())):
            return "Error: Access denied - path outside project root"
    except Exception as e:
        return f"Error resolving path: {e}"
    
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
        dir_path: Relative path to the directory (e.g., "wiki", "backend/app")
    
    Returns:
        List of files and directories, one per line
    """
    if not os.path.isabs(dir_path):
        full_path = PROJECT_ROOT / dir_path
    else:
        full_path = Path(dir_path)
    
    try:
        full_path = full_path.resolve()
        if not str(full_path).startswith(str(PROJECT_ROOT.resolve())):
            return "Error: Access denied - path outside project root"
    except Exception as e:
        return f"Error resolving path: {e}"
    
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


def query_api(method: str, path: str, body: Optional[str] = None) -> str:
    """
    Query the backend Learning Management Service API.
    
    Args:
        method: HTTP method (GET, POST, PUT, DELETE, etc.)
        path: API endpoint path (e.g., "/items/", "/analytics/completion-rate?lab=lab-1")
        body: Optional JSON request body for POST/PUT requests
    
    Returns:
        JSON string with "status_code" and "body" fields
    """
    lms_api_key = os.getenv("LMS_API_KEY")
    api_base_url = os.getenv("AGENT_API_BASE_URL", "http://localhost:42002")
    
    if not lms_api_key:
        return json.dumps({
            "status_code": 0,
            "body": {"error": "LMS_API_KEY not set in environment"},
        })
    
    url = f"{api_base_url}{path}"
    headers = {
        "Authorization": f"Bearer {lms_api_key}",
        "Content-Type": "application/json",
    }
    
    try:
        response = requests.request(
            method=method.upper(),
            url=url,
            headers=headers,
            json=json.loads(body) if body else None,
            timeout=30,
        )
        
        result = {
            "status_code": response.status_code,
            "body": response.json() if response.text else None,
        }
        return json.dumps(result)
    
    except requests.exceptions.Timeout:
        return json.dumps({
            "status_code": 0,
            "body": {"error": "Request timed out"},
        })
    except requests.exceptions.RequestException as e:
        return json.dumps({
            "status_code": 0,
            "body": {"error": str(e)},
        })
    except json.JSONDecodeError as e:
        return json.dumps({
            "status_code": response.status_code,
            "body": {"error": f"Invalid JSON response: {e}"},
        })


# ---------------------------------------------------------------------------
# Tool schemas for LLM
# ---------------------------------------------------------------------------

TOOL_SCHEMAS = [
    {
        "type": "function",
        "function": {
            "name": "read_file",
            "description": "Read a file from the project. Use this to read source code, configuration files, documentation in the wiki folder, or any other file in the project repository.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "Relative path to the file, e.g., 'wiki/backend.md', 'pyproject.toml', 'backend/app/main.py'",
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
            "description": "List files in a directory. Use this to explore the project structure when you don't know the exact file path.",
            "parameters": {
                "type": "object",
                "properties": {
                    "dir_path": {
                        "type": "string",
                        "description": "Relative path to the directory, e.g., 'wiki', 'backend/app', 'backend/app/routers'",
                    }
                },
                "required": ["dir_path"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "query_api",
            "description": "Query the backend LMS API to get live data from the database. Use this for questions about item counts, scores, analytics, completion rates, or any data that requires querying the running system. Examples: 'How many items are in the database?' -> GET /items/, 'What is the completion rate?' -> GET /analytics/completion-rate?lab=lab-01",
            "parameters": {
                "type": "object",
                "properties": {
                    "method": {
                        "type": "string",
                        "description": "HTTP method (GET, POST, PUT, DELETE)",
                        "enum": ["GET", "POST", "PUT", "DELETE"],
                    },
                    "path": {
                        "type": "string",
                        "description": "API endpoint path, e.g., '/items/', '/analytics/completion-rate?lab=lab-01', '/analytics/scores?lab=lab-01'",
                    },
                    "body": {
                        "type": "string",
                        "description": "Optional JSON request body for POST/PUT requests",
                    },
                },
                "required": ["method", "path"],
            },
        },
    },
]

TOOLS = {
    "read_file": read_file,
    "list_files": list_files,
    "query_api": query_api,
}


# ---------------------------------------------------------------------------
# System prompt
# ---------------------------------------------------------------------------

SYSTEM_PROMPT = """You are a helpful assistant for the Learning Management Service project.

You have access to these tools:
1. read_file - Read a file from the project (use for source code, config files, documentation)
2. list_files - List files in a directory (use to explore project structure)
3. query_api - Query the live backend API (use for data questions like item counts, scores, analytics)

Guidelines:
- For questions about project structure, code, or documentation → use read_file
- For questions about live data (items in database, scores, analytics, completion rates) → use query_api
- For questions about the system setup (framework, ports, configuration) → use read_file on pyproject.toml, docker-compose.yml, or backend/app files
- When you need to find a file but don't know the path → use list_files to explore
- Always use tools to gather information before answering
- Cite your sources when referencing files or API responses

Think step by step:
1. Understand what the user is asking
2. Decide which tool(s) to use
3. Call the tool and examine the results
4. If needed, call more tools based on the results
5. Formulate a clear answer based on the tool results"""


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
        dict with 'answer', 'tool_calls', and 'source' fields
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
            # OpenAI API expects tool role with tool_call_id matching the tool call id
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
        "tool_calls": tool_calls_log,
        "source": source,
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
