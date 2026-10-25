import json
from pathlib import Path

import pytest

from wikiskill.daemon import WikiSkillDaemon


@pytest.fixture
def mock_claude_environment(tmp_path: Path):
    claude_dir = tmp_path / ".claude"
    projects_dir = claude_dir / "projects"
    projects_dir.mkdir(parents=True)

    hub_dir = tmp_path / "hub"
    hub_dir.mkdir(parents=True)

    # Create dummy project directory with a session file
    proj_slug = "C--test-workspace-app"
    proj_dir = projects_dir / proj_slug
    proj_dir.mkdir()

    session_file = proj_dir / "sess-1234.jsonl"
    lines = [
        {"type": "mode", "sessionId": "sess-1234"},
        {
            "type": "assistant",
            "message": {
                "role": "assistant",
                "content": [
                    {
                        "type": "tool_use",
                        "id": "t1",
                        "name": "Bash",
                        "input": {"command": "pytest"},
                    }
                ],
            },
        },
        {
            "type": "user",
            "message": {
                "content": [
                    {
                        "type": "tool_result",
                        "tool_use_id": "t1",
                        "content": "1 passed",
                        "is_error": False,
                    }
                ],
            },
        },
    ]
    with open(session_file, "w", encoding="utf-8") as f:
        f.writelines(json.dumps(line) + "\n" for line in lines)

    return claude_dir, hub_dir, proj_slug, session_file


def test_daemon_scan_and_process_sessions(mock_claude_environment):
    claude_dir, hub_dir, proj_slug, _session_file = mock_claude_environment
    daemon = WikiSkillDaemon(claude_dir=claude_dir, hub_dir=hub_dir)

    results = daemon.scan_and_process_sessions()
    assert len(results) == 1
    assert results[0]["session_id"] == "sess-1234"
    assert results[0]["agent"] == "claude"

    # Verify session is marked as processed
    assert (
        f"claude:{proj_slug}/sess-1234" in daemon.processed_sessions
        or f"{proj_slug}/sess-1234" in daemon.processed_sessions
    )

    # Running scan again should skip already processed session
    second_results = daemon.scan_and_process_sessions()
    assert len(second_results) == 0


def test_daemon_multi_agent_scan(tmp_path: Path):
    claude_dir = tmp_path / ".claude"
    projects_dir = claude_dir / "projects" / "test-proj"
    projects_dir.mkdir(parents=True)
    claude_sess = projects_dir / "claude-sess-1.jsonl"
    claude_sess.write_text(
        '{"type": "mode", "sessionId": "claude-sess-1"}\n{"type": "assistant", "message": {"content": [{"type": "tool_use", "id": "t1", "name": "Bash", "input": {"command": "echo"}}]}}\n{"type": "user", "message": {"content": [{"type": "tool_result", "tool_use_id": "t1", "content": "hello"}]}}\n',
        encoding="utf-8",
    )

    antigravity_dir = tmp_path / "antigravity"
    conv_dir = antigravity_dir / "brain" / "conv-ag-999" / ".system_generated" / "logs"
    conv_dir.mkdir(parents=True)
    ag_sess = conv_dir / "transcript.jsonl"
    ag_sess.write_text(
        '{"step_index": 0, "type": "USER_INPUT", "content": "hi"}\n{"step_index": 1, "type": "PLANNER_RESPONSE", "tool_calls": [{"name": "view_file", "args": {"AbsolutePath": "test.py"}}]}\n{"step_index": 2, "type": "GENERIC", "content": "1: test"}\n',
        encoding="utf-8",
    )

    hub_dir = tmp_path / "hub"
    daemon = WikiSkillDaemon(
        claude_dir=claude_dir,
        antigravity_dir=antigravity_dir,
        hub_dir=hub_dir,
    )

    results = daemon.scan_and_process_sessions()
    assert len(results) == 2
    agents = {r["agent"] for r in results}
    assert agents == {"claude", "antigravity"}

    # Re-scan should find 0
    second_run = daemon.scan_and_process_sessions()
    assert len(second_run) == 0


def test_daemon_incremental_delta_processing(tmp_path: Path):
    antigravity_dir = tmp_path / "antigravity"
    conv_dir = antigravity_dir / "brain" / "conv-incr-1" / ".system_generated" / "logs"
    conv_dir.mkdir(parents=True)
    ag_sess = conv_dir / "transcript.jsonl"

    initial_lines = [
        {"step_index": 0, "type": "USER_INPUT", "content": "turn 1"},
        {
            "step_index": 1,
            "type": "PLANNER_RESPONSE",
            "tool_calls": [{"name": "view_file", "args": {"AbsolutePath": "foo.py"}}],
        },
        {"step_index": 2, "type": "GENERIC", "content": "def foo(): pass"},
    ]
    with open(ag_sess, "w", encoding="utf-8") as f:
        f.writelines(json.dumps(r) + "\n" for r in initial_lines)

    import os

    os.utime(ag_sess, (1000, 1000))

    claude_dir = tmp_path / ".claude"
    hub_dir = tmp_path / "hub"
    daemon = WikiSkillDaemon(
        claude_dir=claude_dir,
        antigravity_dir=antigravity_dir,
        hub_dir=hub_dir,
    )

    # First pass: processes turn 1 (1 step)
    res1 = daemon.scan_and_process_sessions()
    assert len(res1) == 1
    assert res1[0]["steps_count"] == 1
    assert res1[0]["record_key"] == "antigravity:conv-incr-1"
    assert daemon.processed_sessions["antigravity:conv-incr-1"]["step_count"] == 1

    # Append turn 2 (1 new step)
    delta_lines = [
        {"step_index": 3, "type": "USER_INPUT", "content": "turn 2"},
        {
            "step_index": 4,
            "type": "PLANNER_RESPONSE",
            "tool_calls": [{"name": "run_command", "args": {"CommandLine": "pytest"}}],
        },
        {"step_index": 5, "type": "GENERIC", "content": "1 passed"},
    ]
    with open(ag_sess, "a", encoding="utf-8") as f:
        f.writelines(json.dumps(r) + "\n" for r in delta_lines)

    # Update file mtime
    os.utime(ag_sess, (2000, 2000))

    # Second pass: only harvests the delta step (1 step, start_step=1)
    res2 = daemon.scan_and_process_sessions()
    assert len(res2) == 1
    assert res2[0]["steps_count"] == 1
    assert daemon.processed_sessions["antigravity:conv-incr-1"]["step_count"] == 2

    # Third pass without changes: 0 sessions processed
    res3 = daemon.scan_and_process_sessions()
    assert len(res3) == 0
