import json
from pathlib import Path
from wikiskill.adapters.claude import ClaudeCodeLogAdapter

def test_adapter_mock_mode():
    adapter = ClaudeCodeLogAdapter(project_path=".", mode="mock")
    traj = adapter.get_latest_session_trajectory()
    assert traj is not None
    assert traj.session_id == "mock-session-123"
    assert len(traj.steps) == 2
    assert traj.steps[0].tool_name == "Bash"
    assert traj.steps[1].tool_name == "Read"

def test_parse_session_jsonl(tmp_path: Path):
    session_file = tmp_path / "test_session.jsonl"
    lines = [
        {"sessionId": "test-123", "timestamp": "2026-08-31T12:00:00Z", "type": "assistant", "message": {"model": "claude-3-7-sonnet", "content": [{"type": "tool_use", "id": "t1", "name": "Bash", "input": {"command": "pytest"}}]}},
        {"sessionId": "test-123", "timestamp": "2026-08-31T12:00:01Z", "type": "user", "message": {"content": [{"type": "tool_result", "tool_use_id": "t1", "content": "1 passed"}]}},
    ]
    with open(session_file, "w", encoding="utf-8") as f:
        for line in lines:
            f.write(json.dumps(line) + "\n")

    adapter = ClaudeCodeLogAdapter(project_path=tmp_path)
    traj = adapter.parse_session_file(session_file)
    assert traj is not None
    assert traj.session_id == "test-123"
    assert len(traj.steps) == 1
    assert traj.steps[0].tool_name == "Bash"
    assert traj.steps[0].observation == "1 passed"
