# Task 3 Plan: The System Agent

## Overview

Task 3 extends the documentation agent from Task 2 with a new `query_api` tool that allows the agent to query the deployed backend API. This enables the agent to answer:
1. **Static system facts** - framework, ports, status codes (from wiki or source code)
2. **Data-dependent queries** - item count, scores, analytics (from live API)

## LLM Provider and Model

**Provider:** Qwen Code API  
**Model:** `qwen3-coder-plus`  
**API Base:** `http://10.93.24.132:42005/v1`

Same setup as Task 1/2 for consistency.

## Environment Variables

The agent will read configuration from environment variables:

| Variable | Source File | Purpose |
|----------|-------------|---------|
| `LLM_API_KEY` | `.env.agent.secret` | LLM provider authentication |
| `LLM_API_BASE` | `.env.agent.secret` | LLM API endpoint URL |
| `LLM_MODEL` | `.env.agent.secret` | Model name |
| `LMS_API_KEY` | `.env.docker.secret` | Backend API authentication for `query_api` |
| `AGENT_API_BASE_URL` | Environment (optional) | Base URL for backend API (default: `http://localhost:42002`) |

**Important:** The autochecker injects its own values, so all config must come from environment variables, not hardcoded values.

## Tool Schema: `query_api`

### Function Definition

```python
def query_api(method: str, path: str, body: Optional[str] = None) -> str:
    """
    Query the backend Learning Management Service API.
    
    Args:
        method: HTTP method (GET, POST, PUT, DELETE, etc.)
        path: API endpoint path (e.g., "/items/", "/analytics/completion-rate")
        body: Optional JSON request body for POST/PUT requests
    
    Returns:
        JSON string with "status_code" and "body" fields
    """
```

### Tool Registration (OpenAI Function Calling)

```json
{
  "name": "query_api",
  "description": "Query the backend LMS API to get live data from the database. Use this for questions about item counts, scores, analytics, or any data that requires querying the running system.",
  "parameters": {
    "type": "object",
    "properties": {
      "method": {
        "type": "string",
        "description": "HTTP method (GET, POST, PUT, DELETE)"
      },
      "path": {
        "type": "string",
        "description": "API endpoint path, e.g., '/items/', '/analytics/completion-rate?lab=lab-1'"
      },
      "body": {
        "type": "string",
        "description": "Optional JSON request body for POST/PUT requests"
      }
    },
    "required": ["method", "path"]
  }
}
```

## Implementation Details

### 1. Authentication

- Read `LMS_API_KEY` from `.env.docker.secret`
- Include in request headers: `Authorization: Bearer {LMS_API_KEY}`
- Read `AGENT_API_BASE_URL` from environment (default: `http://localhost:42002`)

### 2. Tool Implementation

```python
def query_api(method: str, path: str, body: Optional[str] = None) -> str:
    import os
    import requests
    
    lms_api_key = os.getenv("LMS_API_KEY")
    api_base_url = os.getenv("AGENT_API_BASE_URL", "http://localhost:42002")
    
    url = f"{api_base_url}{path}"
    headers = {
        "Authorization": f"Bearer {lms_api_key}",
        "Content-Type": "application/json",
    }
    
    response = requests.request(
        method=method,
        url=url,
        headers=headers,
        json=json.loads(body) if body else None,
        timeout=30,
    )
    
    return json.dumps({
        "status_code": response.status_code,
        "body": response.json() if response.text else None,
    })
```

### 3. System Prompt Update

The system prompt needs to guide the LLM on when to use each tool:

```
You are a helpful assistant for the Learning Management Service project.

You have access to these tools:
1. read_file - Read a file from the project (use for source code, config files)
2. query_api - Query the live backend API (use for data questions like item counts, scores)
3. list_files - List files in a directory (use to explore project structure)

Guidelines:
- For questions about project structure, code, or documentation → use read_file
- For questions about live data (items in database, scores, analytics) → use query_api
- For questions about the system setup (framework, ports) → use read_file on pyproject.toml or docker-compose.yml
```

### 4. Agentic Loop

Same as Task 2:
1. Send user question + tool schemas to LLM
2. Parse response for tool calls
3. Execute tools, collect results
4. Send results back to LLM
5. Get final answer
6. Output JSON with `answer` and `tool_calls`

## Agent Architecture

```
┌──────────────┐     ┌──────────────┐     ┌─────────────┐
│ User Question│ ──→ │ LLM (Qwen)   │ ──→ │ Tool Decision│
└──────────────┘     └──────────────┘     └─────────────┘
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
                                      └──────────────┘
```

## Implementation Steps

1. **Set up environment:**
   - Ensure `.env.docker.secret` exists with `LMS_API_KEY`
   - Copy from `.env.docker.example` and keep `LMS_API_KEY=my-secret-api-key`

2. **Create agent.py with:**
   - Environment loading for all config variables
   - `query_api` tool implementation
   - Tool schema registration
   - Updated system prompt
   - Agentic loop with tool execution

3. **Test manually:**
   - `uv run agent.py "What framework does this project use?"` → should use `read_file`
   - `uv run agent.py "How many items are in the database?"` → should use `query_api`

4. **Run the benchmark:**
   - `uv run run_eval.py`
   - Iterate on failures

5. **Create 2 regression tests:**
   - Test for `read_file` usage (static question)
   - Test for `query_api` usage (data question)

6. **Update AGENT.md:**
   - Document `query_api` tool
   - Explain authentication
   - Document lessons learned (200+ words)

## Benchmark Iteration Strategy

After first run of `run_eval.py`:

1. Record initial score (X/10 passed)
2. For each failure:
   - Identify the issue (wrong tool, wrong arguments, parsing error)
   - Fix: improve tool description, fix implementation, or adjust system prompt
   - Re-run and verify
3. Repeat until 10/10

Common issues and fixes:
| Symptom | Fix |
|---------|-----|
| Agent doesn't call `query_api` for data questions | Make tool description more explicit about "database", "count", "items" |
| Wrong API path | Add examples in tool description |
| Authentication fails | Verify `LMS_API_KEY` is loaded correctly |
| Agent loops reading same file | Add iteration limit, improve file content truncation |

## Testing Strategy

**Test 1: Static system question**
```python
def test_framework_question():
    """Agent should use read_file to find the web framework."""
    result = run_agent("What Python web framework does this project use?")
    assert "answer" in result
    assert any(tc["tool"] == "read_file" for tc in result["tool_calls"])
    assert "fastapi" in result["answer"].lower()
```

**Test 2: Data-dependent question**
```python
def test_item_count_question():
    """Agent should use query_api to get item count."""
    result = run_agent("How many items are in the database?")
    assert "answer" in result
    assert any(tc["tool"] == "query_api" for tc in result["tool_calls"])
    # Answer should contain a number
    assert any(char.isdigit() for char in result["answer"])
```

## Success Criteria

- [ ] `query_api` tool implemented and registered
- [ ] Authentication via `LMS_API_KEY` from environment
- [ ] Agent reads all config from environment variables
- [ ] `run_eval.py` passes 10/10 questions
- [ ] 2 regression tests pass
- [ ] `AGENT.md` updated (200+ words)
