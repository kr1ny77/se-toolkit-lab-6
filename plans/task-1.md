# Task 1 Plan: Call an LLM from Code

## LLM Provider and Model

**Provider:** Qwen Code API  
**Model:** `qwen3-coder-plus`

**Reasoning:**
- Qwen Code provides 1000 free requests per day (vs 50 for OpenRouter)
- More reliable for testing the autochecker (20 questions)
- No credit card required
- Works from Russia

## Agent Structure

### Input/Output Flow

```
Command line argument → Parse question → Call LLM API → Parse response → Output JSON
```

### Components

1. **Environment Loading**
   - Use `python-dotenv` to load `.env.agent.secret`
   - Read `LLM_API_KEY`, `LLM_API_BASE`, `LLM_MODEL`

2. **Command-Line Parsing**
   - Use `sys.argv[1]` to get the question argument
   - Validate that a question was provided

3. **LLM API Call**
   - Use `requests` library for HTTP POST
   - OpenAI-compatible chat completions endpoint: `{LLM_API_BASE}/chat/completions`
   - Request body: `{"model": model, "messages": [{"role": "user", "content": question}]}`

4. **Response Formatting**
   - Extract answer from LLM response: `response["choices"][0]["message"]["content"]`
   - Output JSON: `{"answer": "...", "tool_calls": []}`
   - Use `json.dumps()` for valid JSON output

5. **Error Handling**
   - Missing API key → exit with error message to stderr
   - Network timeout (60s) → catch exception, output error JSON
   - Invalid response → catch exception, output error JSON

### Data Flow

```
┌─────────────┐     ┌──────────────┐     ┌─────────────┐     ┌──────────────┐
│ sys.argv[1] │ ──→ │ Load .env    │ ──→ │ POST to LLM │ ──→ │ Parse JSON   │
│  (question) │     │ credentials  │     │ API         │     │ response     │
└─────────────┘     └──────────────┘     └─────────────┘     └──────────────┘
                                                                   │
                                                                   ▼
                                                          ┌──────────────┐
                                                          │ stdout: JSON │
                                                          │ stderr: logs │
                                                          └──────────────┘
```

## Implementation Steps

1. Create `.env.agent.secret` from `.env.agent.example` and fill in credentials
2. Create `agent.py` with:
   - Environment loading
   - Argument parsing
   - LLM API call function
   - JSON output formatting
3. Test manually with a simple question
4. Create 1 regression test in `tests/`
5. Create `AGENT.md` documentation

## Testing Strategy

- Run `uv run agent.py "What is 2+2?"` and verify JSON output
- Check that `answer` field exists and is non-empty
- Check that `tool_calls` is an empty array
- Verify all debug output goes to stderr (not stdout)
