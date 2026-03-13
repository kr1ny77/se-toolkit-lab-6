# Task 2 Plan: The Documentation Agent

## Overview

Task 2 extends the basic LLM CLI from Task 1 with an **agentic loop** and two documentation tools: `read_file` and `list_files`. The agent can now navigate the project wiki, read documentation files, and cite sources when answering questions.

## LLM Provider and Model

**Provider:** Qwen Code API  
**Model:** `qwen3-coder-plus`  
**API Base:** `http://10.93.24.132:42005/v1`

Same setup as Task 1 for consistency.

## Tool Schemas

### `read_file`

**Purpose:** Read a file from the project repository.

**Schema:**
```json
{
  "name": "read_file",
  "description": "Read a file from the project. Use this to read documentation in the wiki folder, source code, or configuration files.",
  "parameters": {
    "type": "object",
    "properties": {
      "path": {
        "type": "string",
        "description": "Relative path to the file from project root, e.g., 'wiki/git-workflow.md', 'pyproject.toml'"
      }
    },
    "required": ["path"]
  }
}
```

**Implementation:**
- Resolve path relative to project root
- Security check: ensure resolved path is within project root (no `../` traversal)
- Return file content as string, or error message if file doesn't exist
- Truncate content if > 10000 characters to prevent context overflow

### `list_files`

**Purpose:** List files and directories at a given path.

**Schema:**
```json
{
  "name": "list_files",
  "description": "List files in a directory. Use this to explore the project structure when you don't know the exact file path.",
  "parameters": {
    "type": "object",
    "properties": {
      "path": {
        "type": "string",
        "description": "Relative directory path from project root, e.g., 'wiki', 'backend/app'"
      }
    },
    "required": ["path"]
  }
}
```

**Implementation:**
- Resolve path relative to project root
- Security check: ensure resolved path is within project root
- Return newline-separated list of entries with `[DIR]` prefix for directories
- Return error message if directory doesn't exist

## Path Security

Both tools must prevent access to files outside the project root:

```python
def validate_path(path: str) -> Path:
    """Validate and resolve a relative path within project root."""
    project_root = Path(__file__).parent
    full_path = (project_root / path).resolve()
    
    # Security check: ensure path is within project root
    if not str(full_path).startswith(str(project_root.resolve())):
        raise ValueError(f"Access denied: path outside project root")
    
    return full_path
```

## Agentic Loop

The agentic loop iteratively calls the LLM, executes tool calls, and feeds results back:

```
1. Send user question + tool schemas to LLM
2. Parse response for tool_calls
3. If tool_calls exist:
   a. Execute each tool
   b. Append tool results as "tool" role messages
   c. Go to step 1
4. If no tool_calls (final answer):
   a. Extract answer text
   b. Extract source (file path from read_file calls)
   c. Output JSON and exit
5. If max iterations (10) reached:
   a. Stop looping
   b. Use whatever answer we have
```

**Message format for OpenAI-compatible API:**
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

## System Prompt

The system prompt guides the LLM on tool usage:

```
You are a helpful assistant for the Learning Management Service project.

You have access to these tools:
1. read_file - Read a file from the project (use for documentation, source code, config files)
2. list_files - List files in a directory (use to explore project structure)

Guidelines:
- For questions about documentation → use list_files to find the relevant wiki file, then read_file
- Always cite your sources: include the file path and section anchor in the source field
- Think step by step: first explore, then read specific files
- If you don't find the answer after exploring, say so honestly

When answering:
- Provide a clear, concise answer
- Include the source file path (e.g., "wiki/git-workflow.md")
- If referencing a specific section, include the anchor (e.g., "wiki/git-workflow.md#resolving-merge-conflicts")
```

## Output Format

```json
{
  "answer": "The LLM's answer to the question",
  "source": "wiki/git-workflow.md#resolving-merge-conflicts",
  "tool_calls": [
    {
      "tool": "list_files",
      "args": {"path": "wiki"},
      "result": "git-workflow.md\n..."
    },
    {
      "tool": "read_file",
      "args": {"path": "wiki/git-workflow.md"},
      "result": "..."
    }
  ]
}
```

- `answer` (string, required) - The final answer
- `source` (string, required) - Wiki section reference
- `tool_calls` (array, required) - All tool calls made during execution

## Implementation Steps

1. **Create plans/task-2.md** - This plan document
2. **Update agent.py:**
   - Implement `read_file` tool with path security
   - Implement `list_files` tool with path security
   - Define tool schemas for LLM
   - Implement agentic loop with max 10 iterations
   - Update output JSON to include `source` and `tool_calls`
3. **Test manually:**
   - `uv run agent.py "How do you resolve a merge conflict?"` → should use `read_file` on wiki/git-workflow.md
   - `uv run agent.py "What files are in the wiki?"` → should use `list_files`
4. **Create 2 regression tests:**
   - Test for merge conflict question (expects `read_file`, source contains `wiki/git-workflow.md`)
   - Test for wiki listing question (expects `list_files`)
5. **Update AGENT.md:**
   - Document the tools and their schemas
   - Explain the agentic loop
   - Document the system prompt strategy

## Testing Strategy

**Test 1: Merge conflict question**
```python
def test_merge_conflict_question():
    """Agent should use read_file and cite wiki/git-workflow.md as source."""
    result = run_agent("How do you resolve a merge conflict?")
    assert "answer" in result
    assert "source" in result
    assert "wiki/git-workflow.md" in result["source"]
    assert any(tc["tool"] == "read_file" for tc in result["tool_calls"])
```

**Test 2: Wiki listing question**
```python
def test_wiki_listing_question():
    """Agent should use list_files to explore wiki directory."""
    result = run_agent("What files are in the wiki?")
    assert "answer" in result
    assert any(tc["tool"] == "list_files" for tc in result["tool_calls"])
```

## Success Criteria

- [ ] `plans/task-2.md` exists with implementation plan
- [ ] `agent.py` defines `read_file` and `list_files` tool schemas
- [ ] Agentic loop executes tool calls and feeds results back to LLM
- [ ] `tool_calls` in output is populated when tools are used
- [ ] `source` field correctly identifies wiki section
- [ ] Tools have path security (no `../` traversal)
- [ ] `AGENT.md` documents tools and agentic loop
- [ ] 2 regression tests pass
