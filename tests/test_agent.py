"""
Regression tests for agent.py

Tests verify that the agent uses the correct tools for documentation questions.
"""

import json
import subprocess
import sys
from pathlib import Path


def run_agent(question: str) -> dict:
    """Helper to run the agent and parse output."""
    project_root = Path(__file__).parent.parent
    result = subprocess.run(
        ["uv", "run", "agent.py", question],
        capture_output=True,
        text=True,
        cwd=project_root,
        timeout=180,  # Increased timeout for network latency
    )
    assert result.returncode == 0, f"Agent failed: {result.stderr}"
    return json.loads(result.stdout)


def test_merge_conflict_question():
    """
    Test that agent uses read_file and cites wiki/git.md as source.
    
    Question: "How do you resolve a merge conflict?"
    Expected: Agent should call list_files then read_file on wiki/git.md
    """
    output = run_agent("How do you resolve a merge conflict?")
    
    # Check required fields
    assert "answer" in output, "Missing 'answer' field"
    assert "source" in output, "Missing 'source' field"
    assert "tool_calls" in output, "Missing 'tool_calls' field"
    
    # Check that read_file was used
    tools_used = [tc.get("tool") for tc in output["tool_calls"]]
    assert "read_file" in tools_used, f"Expected read_file tool, got: {tools_used}"
    
    # Check source contains wiki/git.md or wiki/git-workflow.md
    source = output.get("source", "")
    assert source and ("wiki/git.md" in source or "wiki/git-workflow.md" in source or "wiki/git-vscode.md" in source), \
        f"Source should reference wiki git file, got: {source}"
    
    # Check answer mentions conflict resolution
    answer_lower = output["answer"].lower()
    assert "conflict" in answer_lower or "merge" in answer_lower, \
        f"Answer should mention conflict resolution: {output['answer'][:200]}"
    
    print(f"✓ Merge conflict question: source={source}, answer={output['answer'][:100]}...")


def test_wiki_listing_question():
    """
    Test that agent uses list_files to explore wiki directory.
    
    Question: "What files are in the wiki?"
    Expected: Agent should call list_files with dir_path='wiki'
    """
    output = run_agent("What files are in the wiki?")
    
    # Check required fields
    assert "answer" in output, "Missing 'answer' field"
    assert "tool_calls" in output, "Missing 'tool_calls' field"
    
    # Check that list_files was used
    tools_used = [tc.get("tool") for tc in output["tool_calls"]]
    assert "list_files" in tools_used, f"Expected list_files tool, got: {tools_used}"
    
    # Check answer mentions wiki files
    answer_lower = output["answer"].lower()
    assert "wiki" in answer_lower or ".md" in answer_lower, \
        f"Answer should mention wiki files: {output['answer'][:200]}"
    
    print(f"✓ Wiki listing question: answer={output['answer'][:100]}...")


if __name__ == "__main__":
    print("Running agent regression tests...")
    test_merge_conflict_question()
    test_wiki_listing_question()
    print("\nAll tests passed!")
