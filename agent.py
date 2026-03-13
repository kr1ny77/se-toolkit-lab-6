#!/usr/bin/env python3
"""
Agent CLI - Calls an LLM and returns a structured JSON answer.

Usage:
    uv run agent.py "Your question here"

Output:
    JSON to stdout: {"answer": "...", "tool_calls": []}
    All debug output goes to stderr.
"""

import json
import os
import sys
from pathlib import Path

import requests
from dotenv import load_dotenv


def load_env():
    """Load environment variables from .env.agent.secret."""
    env_path = Path(__file__).parent / ".env.agent.secret"
    if not env_path.exists():
        print(f"Error: {env_path} not found", file=sys.stderr)
        sys.exit(1)
    
    load_dotenv(env_path)
    
    api_key = os.getenv("LLM_API_KEY")
    api_base = os.getenv("LLM_API_BASE")
    model = os.getenv("LLM_MODEL")
    
    if not api_key:
        print("Error: LLM_API_KEY not set in .env.agent.secret", file=sys.stderr)
        sys.exit(1)
    if not api_base:
        print("Error: LLM_API_BASE not set in .env.agent.secret", file=sys.stderr)
        sys.exit(1)
    if not model:
        print("Error: LLM_MODEL not set in .env.agent.secret", file=sys.stderr)
        sys.exit(1)
    
    return api_key, api_base, model


def call_lllm(question: str, api_key: str, api_base: str, model: str) -> str:
    """
    Call the LLM API and return the answer.
    
    Args:
        question: The user's question
        api_key: API key for authentication
        api_base: Base URL of the API (e.g., http://localhost:42005/v1)
        model: Model name to use
    
    Returns:
        The LLM's answer as a string
    """
    url = f"{api_base}/chat/completions"
    
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {api_key}",
    }
    
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": "You are a helpful assistant. Answer questions concisely and accurately."},
            {"role": "user", "content": question},
        ],
    }
    
    print(f"Calling LLM at {url} with model {model}...", file=sys.stderr)
    
    response = requests.post(url, headers=headers, json=payload, timeout=60)
    response.raise_for_status()
    
    result = response.json()
    answer = result["choices"][0]["message"]["content"]
    
    print(f"Got response from LLM", file=sys.stderr)
    
    return answer


def main():
    """Main entry point."""
    if len(sys.argv) < 2:
        print("Usage: uv run agent.py \"Your question here\"", file=sys.stderr)
        sys.exit(1)
    
    question = sys.argv[1]
    
    # Load environment
    api_key, api_base, model = load_env()
    
    # Call LLM
    answer = call_lllm(question, api_key, api_base, model)
    
    # Output JSON
    output = {
        "answer": answer,
        "tool_calls": [],
    }
    
    print(json.dumps(output))


if __name__ == "__main__":
    main()
