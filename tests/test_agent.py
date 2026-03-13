"""
Regression tests for agent.py

Tests verify that the agent uses the correct tools for different question types.
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


def test_framework_question_uses_read_file():
    """
    Test that agent uses read_file tool for static system questions.
    
    Question: "What Python web framework does this project use?"
    Expected: Agent should call read_file on backend/app/main.py or pyproject.toml
    """
    output = run_agent("What Python web framework does this project use?")
    
    # Check required fields
    assert "answer" in output, "Missing 'answer' field"
    assert "tool_calls" in output, "Missing 'tool_calls' field"
    
    # Check that read_file was used
    tools_used = [tc.get("tool") for tc in output["tool_calls"]]
    assert "read_file" in tools_used, f"Expected read_file tool, got: {tools_used}"
    
    # Check answer contains FastAPI
    answer_lower = output["answer"].lower()
    assert "fastapi" in answer_lower, f"Answer should mention FastAPI: {output['answer']}"
    
    print(f"✓ Framework question: answer={output['answer'][:100]}...")


def test_item_count_question_uses_query_api():
    """
    Test that agent uses query_api tool for data-dependent questions.
    
    Question: "How many items are in the database?"
    Expected: Agent should call query_api GET /items/
    """
    output = run_agent("How many items are in the database?")
    
    # Check required fields
    assert "answer" in output, "Missing 'answer' field"
    assert "tool_calls" in output, "Missing 'tool_calls' field"
    
    # Check that query_api was used
    tools_used = [tc.get("tool") for tc in output["tool_calls"]]
    assert "query_api" in tools_used, f"Expected query_api tool, got: {tools_used}"
    
    # Check answer contains a number
    import re
    numbers = re.findall(r'\d+', output["answer"])
    assert len(numbers) > 0, f"Answer should contain a number: {output['answer']}"
    
    print(f"✓ Item count question: answer={output['answer'][:100]}...")


if __name__ == "__main__":
    print("Running agent regression tests...")
    test_framework_question_uses_read_file()
    test_item_count_question_uses_query_api()
    print("\nAll tests passed!")
