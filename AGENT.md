# Agent Architecture

## Overview

This agent is a CLI tool that uses an LLM (Large Language Model) with tool-calling capabilities to answer questions about the Learning Management Service project. It can read documentation files, explore the project structure, and query the live backend API for data-dependent questions.

## LLM Provider

**Provider:** Qwen Code API  
**Model:** `qwen3-coder-plus`  
**API Base:** `http://10.93.24.132:42005/v1`

Qwen Code provides 1000 free requests per day and works from Russia without requiring a credit card. The agent uses the OpenAI-compatible chat completions API with function calling support.

## Architecture

```
┌─────────────────┐     ┌──────────────┐     ┌─────────────┐
│ User Question   │ ──→ │ LLM (Qwen)   │ ──→ │ Tool Decision│
│ (CLI argument)  │     │ with tools   │     │              │
└─────────────────┘     └──────────────┘     └─────────────┘
                                                 │
                       ┌─────────────────────────┼─────────────────────────┐
                       │                         │                         │
                       ▼                         ▼                         ▼
               ┌──────────────┐         ┌──────────────┐         ┌──────────────┐
               │ read_file    │         │ query_api    │         │ list_files   │
               │ (wiki/code)  │         │ (live data)  │         │ (exploration)│
               └──────────────┘         └──────────────┘         └──────────────┘
                       │                         │                         │
                       └─────────────────────────┼─────────────────────────┘
                                                 │
                                                 ▼
                                         ┌──────────────┐
                                         │ LLM combines │
                                         │ results      │
                                         └──────────────┘
                                                 │
                                                 ▼
                                         ┌──────────────┐
                                         │ JSON Output  │
                                         │ (stdout)     │
                                         └──────────────┘
```

## Components

### `agent.py`

The main CLI entry point with the following components:

1. **Environment Loading** - Loads `.env.agent.secret` and `.env.docker.secret` using `python-dotenv`
2. **Tool Implementations** - Three tools: `read_file`, `list_files`, `query_api`
3. **Tool Schemas** - OpenAI-compatible function calling schemas
4. **Agentic Loop** - Iteratively calls LLM, executes tools, and collects results
5. **JSON Output** - Returns structured JSON with `answer`, `tool_calls`, and `source` fields

### Tools

#### `read_file`

Reads a file from the project repository.

- **Parameters:** `path` (string) - Relative path to the file
- **Returns:** File content as string (truncated to 10000 chars)
- **Use cases:** Reading source code, configuration files, wiki documentation
- **Security:** Prevents access to files outside project root

#### `list_files`

Lists files in a directory.

- **Parameters:** `dir_path` (string) - Relative path to the directory
- **Returns:** List of files and directories, one per line
- **Use cases:** Exploring project structure when exact file path is unknown

#### `query_api`

Queries the backend Learning Management Service API.

- **Parameters:** 
  - `method` (string) - HTTP method (GET, POST, PUT, DELETE)
  - `path` (string) - API endpoint path
  - `body` (string, optional) - JSON request body for POST/PUT
- **Returns:** JSON string with `status_code` and `body` fields
- **Authentication:** Uses `LMS_API_KEY` from `.env.docker.secret`
- **Use cases:** Getting item counts, scores, analytics, completion rates

### Environment Variables

| Variable | Source File | Purpose | Default |
|----------|-------------|---------|---------|
| `LLM_API_KEY` | `.env.agent.secret` | LLM provider authentication | - |
| `LLM_API_BASE` | `.env.agent.secret` | LLM API endpoint URL | - |
| `LLM_MODEL` | `.env.agent.secret` | Model name | - |
| `LMS_API_KEY` | `.env.docker.secret` | Backend API authentication | - |
| `AGENT_API_BASE_URL` | Environment | Base URL for backend API | `http://localhost:42002` |

**Important:** The autochecker injects its own values for these variables. The agent must read all configuration from environment variables, not hardcoded values.

### System Prompt

The system prompt guides the LLM on tool usage:

- **For project structure, code, or documentation** → use `read_file`
- **For live data (items, scores, analytics)** → use `query_api`
- **For system setup questions (framework, ports)** → use `read_file` on config files
- **When file path is unknown** → use `list_files` to explore

### Agentic Loop

1. Send user question + tool schemas to LLM
2. Parse response for tool calls
3. Execute each tool, collect results
4. Add tool responses to message history
5. Send results back to LLM
6. Repeat until LLM returns final answer (no tool calls)
7. Output JSON with `answer`, `tool_calls`, and `source`

### Output Format

```json
{
  "answer": "The LLM's answer to the question",
  "tool_calls": [
    {
      "tool": "query_api",
      "args": {"method": "GET", "path": "/items/"},
      "result": "{\"status_code\": 200, \"body\": {...}}"
    }
  ],
  "source": "backend/app/main.py"  // if read_file was used
}
```

## Usage

```bash
# Static system question
uv run agent.py "What Python web framework does this project use?"

# Data-dependent question
uv run agent.py "How many items are in the database?"

# Analytics question
uv run agent.py "What is the completion rate for lab-01?"
```

## Dependencies

- `requests` - For making HTTP requests to the LLM API and backend API
- `python-dotenv` - For loading environment variables from `.env` files

## Error Handling

- **Missing environment variables** → Exit with error message to stderr
- **Network timeout (60s for LLM, 30s for API)** → Return error in tool result
- **File not found** → Return error message in tool result
- **API authentication failure** → Return 401 status in tool result
- **Unknown tool** → Return error in tool result
- **LLM API error** → Log details to stderr, retry or return error

## Testing

Two regression tests verify correct tool usage:

1. **`test_framework_question_uses_read_file`** - Verifies that static system questions use `read_file`
2. **`test_item_count_question_uses_query_api`** - Verifies that data questions use `query_api`

Run tests:
```bash
uv run pytest tests/test_agent.py -v
```

## Lessons Learned

Building this agent taught me several important lessons about LLM-based tool calling systems:

**1. Tool descriptions matter immensely.** Initially, my tool descriptions were vague, and the LLM would often call the wrong tool. For example, it would try to use `read_file` for questions about database contents. After I made the `query_api` description more explicit with examples like "How many items are in the database? → GET /items/", the LLM started using the correct tool consistently.

**2. Message format is critical for multi-turn conversations.** The OpenAI-compatible API has strict requirements for tool message formatting. The tool response must include a `tool_call_id` that matches the ID from the assistant's tool call, and the assistant message with tool_calls must be added to the history before the tool responses. Getting this wrong resulted in cryptic API errors.

**3. Environment variable separation is essential.** The agent uses two different API keys: `LLM_API_KEY` for the LLM provider and `LMS_API_KEY` for the backend API. Mixing these up caused authentication failures. Clear documentation and separate `.env` files help prevent this confusion.

**4. Truncation prevents context overflow.** Large files can exceed the LLM's context window. I implemented a 10000-character limit for file content to prevent this, though this means very large files may be truncated.

**5. Debug output separation is crucial.** All debug logging goes to stderr while only the final JSON answer goes to stdout. This allows the output to be piped to other tools without parsing issues.

**6. Iteration limits prevent infinite loops.** Without a maximum iteration count, the agent could potentially loop forever if the LLM keeps calling tools without producing a final answer. A limit of 10 iterations is sufficient for most questions.

## Final Evaluation Score

The agent passes all 10 local questions in `run_eval.py`:
- Wiki lookup questions (using `read_file`)
- System facts questions (using `read_file` on config files)
- Data queries (using `query_api`)
- Bug diagnosis (using combination of tools)
- Reasoning questions (using multiple tool calls)
