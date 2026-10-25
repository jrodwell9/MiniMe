import json
from pathlib import Path
from wikiskill.adapters.antigravity import AntigravityLogAdapter

def test_antigravity_adapter_mock_mode():
    adapter = AntigravityLogAdapter(project_path=".", mode="mock")
    traj = adapter.get_latest_session_trajectory()
    assert traj is not None
    assert traj.session_id == "mock-antigravity-conv-1"
    assert len(traj.steps) == 2
    assert traj.steps[0].tool_name == "view_file"
    assert traj.steps[1].tool_name == "run_command"

def test_antigravity_parse_transcript_jsonl(tmp_path: Path):
    t_file = tmp_path / "transcript.jsonl"
    lines = [
        {"type": "PLANNER_RESPONSE", "content": "I will inspect", "tool_calls": [{"name": "run_command", "args": {"CommandLine": "pytest"}}]},
        {"type": "TOOL_RESULT", "content": "1 passed in 0.1s", "status": "DONE"},
    ]
    with open(t_file, "w", encoding="utf-8") as f:
        for line in lines:
            f.write(json.dumps(line) + "\n")

    adapter = AntigravityLogAdapter(project_path=tmp_path)
    traj = adapter.parse_session_file(t_file)
    assert traj is not None
    assert len(traj.steps) == 1
    assert traj.steps[0].tool_name == "run_command"
    assert not traj.steps[0].is_error
