"""
Regression tests for agent.py

Tests verify that the agent outputs valid JSON with required fields.
"""

import json
import subprocess
import sys
from pathlib import Path


def test_agent_outputs_valid_json():
    """Test that agent.py outputs valid JSON with answer and tool_calls fields."""
    # Get project root directory
    project_root = Path(__file__).parent.parent
    
    # Run the agent with a simple question
    result = subprocess.run(
        ["uv", "run", "agent.py", "What is 2+2?"],
        capture_output=True,
        text=True,
        cwd=project_root,
    )
    
    # Check exit code
    assert result.returncode == 0, f"Agent failed with: {result.stderr}"
    
    # Parse stdout as JSON
    output = json.loads(result.stdout)
    
    # Check required fields exist
    assert "answer" in output, "Missing 'answer' field in output"
    assert "tool_calls" in output, "Missing 'tool_calls' field in output"
    
    # Check field types
    assert isinstance(output["answer"], str), "'answer' should be a string"
    assert isinstance(output["tool_calls"], list), "'tool_calls' should be an array"
    
    # Check answer is non-empty
    assert len(output["answer"]) > 0, "'answer' should not be empty"
    
    # Check tool_calls is empty (Task 1 doesn't have tools)
    assert len(output["tool_calls"]) == 0, "'tool_calls' should be empty for Task 1"
    
    print(f"✓ Agent output: {output}")


if __name__ == "__main__":
    test_agent_outputs_valid_json()
    print("All tests passed!")
