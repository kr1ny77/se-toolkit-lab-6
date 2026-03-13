# Agent Architecture

## Overview

This agent is a CLI tool that uses an LLM (Large Language Model) with tool-calling capabilities to answer questions about the Learning Management Service project. It can read documentation files and explore the project structure using two tools: `read_file` and `list_files`.

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
                       ▼                         ▼                         │
               ┌──────────────┐         ┌──────────────┐                    │
               │ read_file    │         │ list_files   │                    │
               │ (wiki/code)  │         │ (exploration)│                    │
               └──────────────┘         └──────────────┘                    │
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

1. **Environment Loading** - Loads `.env.agent.secret` using `python-dotenv`
2. **Tool Implementations** - Two tools: `read_file`, `list_files`
3. **Tool Schemas** - OpenAI-compatible function calling schemas
4. **Agentic Loop** - Iteratively calls LLM, executes tools, and collects results
5. **JSON Output** - Returns structured JSON with `answer`, `source`, and `tool_calls` fields

### Tools

#### `read_file`

Reads a file from the project repository.

- **Parameters:** `path` (string) - Relative path to the file
- **Returns:** File content as string (truncated to 10000 chars)
- **Use cases:** Reading wiki documentation, source code, configuration files
- **Security:** Prevents access to files outside project root (no `../` traversal)

#### `list_files`

Lists files in a directory.

- **Parameters:** `dir_path` (string) - Relative path to the directory
- **Returns:** List of files and directories, one per line with `[DIR]` prefix for directories
- **Use cases:** Exploring project structure when exact file path is unknown
- **Security:** Prevents access to directories outside project root

### Path Security

Both tools validate paths to prevent directory traversal attacks:

```python
def validate_path(path: str) -> Path:
    """Validate and resolve a relative path within project root."""
    full_path = (PROJECT_ROOT / path).resolve()
    
    # Security check: ensure path is within project root
    if not str(full_path).startswith(str(PROJECT_ROOT.resolve())):
        raise ValueError(f"Access denied: path outside project root")
    
    return full_path
```

### Environment Variables (`.env.agent.secret`)

| Variable | Description |
|----------|-------------|
| `LLM_API_KEY` | API key for authentication |
| `LLM_API_BASE` | Base URL of the LLM API endpoint |
| `LLM_MODEL` | Model name to use (e.g., `qwen3-coder-plus`) |

## Agentic Loop

The agentic loop is the core of the agent's reasoning process:

1. **Send question to LLM** - Include user question + tool schemas
2. **Parse response** - Check for `tool_calls` in response
3. **If tool calls exist:**
   - Execute each tool with provided arguments
   - Append tool results as "tool" role messages
   - Add assistant message with tool_calls to history
   - Go back to step 1
4. **If no tool calls (final answer):**
   - Extract answer text
   - Extract source (file path from `read_file` calls)
   - Output JSON and exit
5. **If max iterations (10) reached:**
   - Stop looping
   - Use whatever answer we have

### Message Format

```python
messages = [
    {"role": "system", "content": SYSTEM_PROMPT},
    {"role": "user", "content": question},
    # After LLM responds with tool_calls:
    {"role": "assistant", "content": None, "tool_calls": [...]},
    # After executing each tool:
    {"role": "tool", "tool_call_id": "<id>", "content": "<result>"},
    # Then send back to LLM for next iteration
]
```

## System Prompt Strategy

The system prompt guides the LLM on tool usage:

```
You are a helpful assistant for the Learning Management Service project.

You have access to these tools:
1. read_file - Read a file from the project (use for documentation, source code, config files)
2. list_files - List files in a directory (use to explore project structure)

Guidelines:
- For questions about documentation → use list_files to find the relevant wiki file, then read_file
- Always cite your sources: mention the file path in your answer
- Think step by step: first explore with list_files if needed, then read specific files with read_file
```

The prompt encourages:
- **Exploration first** - Use `list_files` to discover relevant files
- **Then read** - Use `read_file` to get specific content
- **Cite sources** - Include file paths in answers

## Usage

```bash
# Documentation question
uv run agent.py "How do you resolve a merge conflict?"

# Exploration question
uv run agent.py "What files are in the wiki?"
```

## Output Format

```json
{
  "answer": "The LLM's answer to the question",
  "source": "wiki/git.md",
  "tool_calls": [
    {
      "tool": "list_files",
      "args": {"dir_path": "wiki"},
      "result": "api.md\narchitectural-views.md\n..."
    },
    {
      "tool": "read_file",
      "args": {"path": "wiki/git.md"},
      "result": "# Git\n\nGit is a distributed..."
    }
  ]
}
```

- `answer` (string, required) - The final answer
- `source` (string, required) - Wiki file path that was read
- `tool_calls` (array, required) - All tool calls made during execution

## Dependencies

- `requests` - For making HTTP requests to the LLM API
- `python-dotenv` - For loading environment variables from `.env.agent.secret`

## Error Handling

- **Missing environment variables** → Exit with error message to stderr
- **Network timeout (60s)** → Exception raised
- **File not found** → Return error message in tool result
- **Path traversal attempt** → Return "Access denied" error
- **Unknown tool** → Return error in tool result
- **LLM API error** → Log details to stderr, retry or return error

## Testing

Two regression tests verify correct tool usage:

1. **`test_merge_conflict_question`** - Verifies that documentation questions use `read_file` and cite the correct source
2. **`test_wiki_listing_question`** - Verifies that exploration questions use `list_files`

Run tests:
```bash
uv run pytest tests/test_agent.py -v
```

## Lessons Learned

Building this documentation agent taught me several important lessons:

**1. Tool parameter names must match exactly.** The LLM learns the tool schema from the JSON definition. If the schema says `dir_path` but the function expects `path`, the tool call will fail. Consistency between schema and implementation is critical.

**2. The agentic loop needs iteration limits.** Without a maximum iteration count, the LLM could potentially loop forever calling tools without producing a final answer. A limit of 10 iterations is sufficient for most documentation questions.

**3. Message format is strict for tool calls.** The OpenAI-compatible API requires:
- Assistant message with `tool_calls` array before tool responses
- Tool response with `tool_call_id` matching the original tool call ID
- Correct role names (`assistant`, `tool`)

**4. Truncation prevents context overflow.** Large files can exceed the LLM's context window. I implemented a 10000-character limit for file content to prevent this.

**5. Debug output separation is crucial.** All debug logging goes to stderr while only the final JSON answer goes to stdout. This allows the output to be piped to other tools without parsing issues.

**6. Source tracking requires careful implementation.** The `source` field should capture which file was read to answer the question. I track this by recording the path from the first `read_file` call.
