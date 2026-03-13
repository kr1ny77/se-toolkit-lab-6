# Task 3 Plan: The System Agent

## Overview

Task 3 extends the documentation agent from Task 2 with a new `query_api` tool that allows the agent to query the deployed backend API. This enables the agent to answer:
1. **Static system facts** - framework, ports, status codes (from wiki or source code)
2. **Data-dependent queries** - item count, scores, analytics (from live API)

## LLM Provider and Model

**Provider:** Qwen Code API  
**Model:** `qwen3-coder-plus`  
**API Base:** `http://10.93.24.132:42005/v1`

## Environment Variables

The agent will read configuration from environment variables:

| Variable | Source File | Purpose | Default |
|----------|-------------|---------|---------|
| `LLM_API_KEY` | `.env.agent.secret` | LLM provider authentication | - |
| `LLM_API_BASE` | `.env.agent.secret` | LLM API endpoint URL | - |
| `LLM_MODEL` | `.env.agent.secret` | Model name | - |
| `LMS_API_KEY` | `.env.docker.secret` | Backend API authentication for `query_api` | - |
| `AGENT_API_BASE_URL` | Environment (optional) | Base URL for backend API | `http://localhost:42002` |

**Important:** The autochecker injects its own values, so all config must come from environment variables, not hardcoded values.

## Tool Schema: `query_api`

```json
{
  "name": "query_api",
  "description": "Query the backend LMS API to get live data from the database. Use this for questions about item counts, scores, analytics, completion rates, or any data that requires querying the running system. Examples: 'How many items are in the database?' -> GET /items/, 'What is the completion rate?' -> GET /analytics/completion-rate?lab=lab-01",
  "parameters": {
    "type": "object",
    "properties": {
      "method": {
        "type": "string",
        "description": "HTTP method (GET, POST, PUT, DELETE)",
        "enum": ["GET", "POST", "PUT", "DELETE"]
      },
      "path": {
        "type": "string",
        "description": "API endpoint path, e.g., '/items/', '/analytics/completion-rate?lab=lab-01', '/analytics/scores?lab=lab-01'"
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

```
You are a helpful assistant for the Learning Management Service project.

You have access to these tools:
1. read_file - Read a file from the project (use for source code, config files, documentation)
2. list_files - List files in a directory (use to explore project structure)
3. query_api - Query the live backend API (use for data questions like item counts, scores, analytics)

Guidelines:
- For questions about project structure, code, or documentation → use read_file
- For questions about live data (items in database, scores, analytics, completion rates) → use query_api
- For questions about the system setup (framework, ports, configuration) → use read_file on pyproject.toml, docker-compose.yml, or backend/app files
```

## Implementation Steps

1. Ensure `.env.docker.secret` exists with `LMS_API_KEY`
2. Add `query_api` tool to agent.py
3. Add tool schema to TOOL_SCHEMAS
4. Update system prompt
5. Test manually with data questions
6. Run `run_eval.py` and iterate
7. Create 2 regression tests
8. Update AGENT.md

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
    assert any(char.isdigit() for char in result["answer"])
```

## Success Criteria

- [ ] `plans/task-3.md` exists with implementation plan
- [ ] `agent.py` defines `query_api` as function-calling schema
- [ ] `query_api` authenticates with `LMS_API_KEY` from environment
- [ ] Agent reads all LLM config from environment variables
- [ ] Agent reads `AGENT_API_BASE_URL` from environment (default: `http://localhost:42002`)
- [ ] Agent answers static system questions correctly
- [ ] Agent answers data-dependent questions with plausible values
- [ ] `run_eval.py` passes all 10 local questions
- [ ] `AGENT.md` documents final architecture and lessons learned (200+ words)
- [ ] 2 tool-calling regression tests exist and pass
