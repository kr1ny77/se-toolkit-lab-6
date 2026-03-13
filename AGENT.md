# Agent Architecture

## Overview

This agent is a CLI tool that calls an LLM (Large Language Model) and returns structured JSON answers. It serves as the foundation for the more advanced agent with tools that will be built in subsequent tasks.

## LLM Provider

**Provider:** Qwen Code API  
**Model:** `qwen3-coder-plus`  
**API Base:** `http://10.93.24.132:42005/v1`

Qwen Code provides 1000 free requests per day and works from Russia without requiring a credit card.

## Architecture

```
┌─────────────────┐     ┌──────────────┐     ┌─────────────┐     ┌──────────────┐
│ Command Line    │ ──→ │ Environment  │ ──→ │ LLM API     │ ──→ │ JSON Output  │
│ Argument        │     │ Variables    │     │ (Qwen)      │     │ (stdout)     │
│ (question)      │     │ (.env file)  │     │             │     │              │
└─────────────────┘     └──────────────┘     └─────────────┘     └──────────────┘
```

## Components

### `agent.py`

The main CLI entry point with the following responsibilities:

1. **Argument Parsing** - Reads the question from `sys.argv[1]`
2. **Environment Loading** - Loads `.env.agent.secret` using `python-dotenv`
3. **LLM API Call** - Makes HTTP POST request to the OpenAI-compatible chat completions endpoint
4. **Response Formatting** - Outputs JSON with `answer` and `tool_calls` fields

### Environment Variables (`.env.agent.secret`)

| Variable | Description |
|----------|-------------|
| `LLM_API_KEY` | API key for authentication |
| `LLM_API_BASE` | Base URL of the LLM API endpoint |
| `LLM_MODEL` | Model name to use (e.g., `qwen3-coder-plus`) |

## Usage

```bash
# Run with a question
uv run agent.py "What does REST stand for?"

# Output (JSON to stdout)
{"answer": "Representational State Transfer.", "tool_calls": []}
```

## Output Format

The agent outputs a single JSON line to stdout:

```json
{
  "answer": "The LLM's response",
  "tool_calls": []
}
```

- `answer`: The LLM's answer to the question
- `tool_calls`: Empty array (will be populated in Task 2 when tools are added)

All debug and error output goes to **stderr**, ensuring clean JSON output on stdout.

## Dependencies

- `requests` - For making HTTP requests to the LLM API
- `python-dotenv` - For loading environment variables from `.env.agent.secret`

## Error Handling

- Missing `.env.agent.secret` file → Exit with error message to stderr
- Missing environment variables → Exit with error message to stderr
- Network timeout (60s) → Exception raised
- Invalid API response → Exception raised
