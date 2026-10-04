import json
import os
from datetime import UTC, datetime
from pathlib import Path

from wikiskill.adapters.claude import (
    ClaudeCodeLogAdapter,
    sanitize_project_path,
)
from wikiskill.models import SessionTrajectory


def test_sanitize_project_path_windows():
    win_path = r"C:\Users\jrodw\Documents\MiniMe"
    slug = sanitize_project_path(win_path)
    assert slug == "C--Users-jrodw-Documents-MiniMe"


def test_sanitize_project_path_posix():
    posix_path = "/home/user/workspace/project"
    slug = sanitize_project_path(posix_path)
    assert slug in ("-home-user-workspace-project", "home-user-workspace-project")


def test_adapter_mock_mode():
    adapter = ClaudeCodeLogAdapter(mode="mock")
    trajectory = adapter.get_latest_session_trajectory()
    assert trajectory is not None
    assert isinstance(trajectory, SessionTrajectory)
    assert trajectory.session_id == "mock-session-123"
    assert len(trajectory.steps) >= 2
    assert trajectory.steps[0].tool_name == "Bash"


def test_find_latest_session_file(tmp_path: Path):
    project_dir = tmp_path / "C--test-project"
    project_dir.mkdir(parents=True)

    file1 = project_dir / "11111111-1111-1111-1111-111111111111.jsonl"
    file2 = project_dir / "22222222-2222-2222-2222-222222222222.jsonl"

    file1.write_text('{"type": "mode", "sessionId": "111"}\n', encoding="utf-8")
    file2.write_text('{"type": "mode", "sessionId": "222"}\n', encoding="utf-8")

    os.utime(file1, (1000, 1000))
    os.utime(file2, (2000, 2000))

    adapter = ClaudeCodeLogAdapter(
        projects_dir=tmp_path,
        project_path=Path(r"C:\test\project"),
        mode="file",
    )
    latest = adapter._find_latest_session_file()
    assert latest == file2


def test_find_latest_session_file_with_since(tmp_path: Path):
    project_dir = tmp_path / "C--test-project"
    project_dir.mkdir(parents=True)

    file1 = project_dir / "11111111-1111-1111-1111-111111111111.jsonl"
    file1.write_text('{"type": "mode", "sessionId": "111"}\n', encoding="utf-8")

    os.utime(file1, (1000, 1000))

    adapter = ClaudeCodeLogAdapter(
        projects_dir=tmp_path,
        project_path=Path(r"C:\test\project"),
        mode="file",
    )
    since_dt = datetime.fromtimestamp(1500, tz=UTC).isoformat()
    latest = adapter._find_latest_session_file(since=since_dt)
    assert latest is None


def test_parse_session_jsonl(tmp_path: Path):
    session_file = tmp_path / "test-session.jsonl"
    lines = [
        {"type": "mode", "mode": "normal", "sessionId": "test-sess-uuid"},
        {
            "type": "assistant",
            "timestamp": "2026-08-31T12:00:00.000Z",
            "message": {
                "role": "assistant",
                "model": "claude-3-7-sonnet",
                "content": [
                    {
                        "type": "tool_use",
                        "id": "call_1",
                        "name": "Bash",
                        "input": {"command": "pytest"},
                    }
                ],
            },
        },
        {
            "type": "user",
            "timestamp": "2026-08-31T12:00:01.000Z",
            "message": {
                "role": "user",
                "content": [
                    {
                        "type": "tool_result",
                        "tool_use_id": "call_1",
                        "content": "1 passed in 0.05s",
                        "is_error": False,
                    }
                ],
            },
        },
        {
            "type": "assistant",
            "timestamp": "2026-08-31T12:00:02.000Z",
            "message": {
                "role": "assistant",
                "model": "claude-3-7-sonnet",
                "content": [
                    {
                        "type": "tool_use",
                        "id": "call_2",
                        "name": "Read",
                        "input": {"file_path": "nonexistent.py"},
                    }
                ],
            },
        },
        {
            "type": "user",
            "timestamp": "2026-08-31T12:00:03.000Z",
            "message": {
                "role": "user",
                "content": [
                    {
                        "type": "tool_result",
                        "tool_use_id": "call_2",
                        "content": [{"type": "text", "text": "FileNotFoundError"}],
                        "is_error": True,
                    }
                ],
            },
        },
        # Corrupted line to test resilience
        "NOT_A_JSON_LINE",
    ]

    with open(session_file, "w", encoding="utf-8") as f:
        f.writelines(
            (json.dumps(item) + "\n") if isinstance(item, dict) else (item + "\n")
            for item in lines
        )

    adapter = ClaudeCodeLogAdapter(mode="file")
    trajectory = adapter.parse_session_file(session_file)

    assert trajectory is not None
    assert trajectory.session_id == "test-sess-uuid"
    assert trajectory.model_routed == "claude-3-7-sonnet"
    assert trajectory.timestamp == "2026-08-31T12:00:00.000Z"
    assert len(trajectory.steps) == 2

    # Step 1
    step1 = trajectory.steps[0]
    assert step1.step_number == 1
    assert step1.tool_name == "Bash"
    assert step1.tool_input == {"command": "pytest"}
    assert step1.observation == "1 passed in 0.05s"
    assert step1.is_error is False

    # Step 2
    step2 = trajectory.steps[1]
    assert step2.step_number == 2
    assert step2.tool_name == "Read"
    assert step2.tool_input == {"file_path": "nonexistent.py"}
    assert "FileNotFoundError" in step2.observation
    assert step2.is_error is True


def test_claude_parse_session_start_step(tmp_path: Path):
    session_file = tmp_path / "test-session-steps.jsonl"
    lines = [
        {"type": "mode", "sessionId": "sess-step"},
        {
            "type": "assistant",
            "message": {
                "content": [
                    {
                        "type": "tool_use",
                        "id": "call_1",
                        "name": "Bash",
                        "input": {"command": "ls"},
                    }
                ]
            },
        },
        {
            "type": "user",
            "message": {
                "content": [
                    {
                        "type": "tool_result",
                        "tool_use_id": "call_1",
                        "content": "file.txt",
                        "is_error": False,
                    }
                ]
            },
        },
        {
            "type": "assistant",
            "message": {
                "content": [
                    {
                        "type": "tool_use",
                        "id": "call_2",
                        "name": "Read",
                        "input": {"file_path": "file.txt"},
                    }
                ]
            },
        },
        {
            "type": "user",
            "message": {
                "content": [
                    {
                        "type": "tool_result",
                        "tool_use_id": "call_2",
                        "content": "hello",
                        "is_error": False,
                    }
                ]
            },
        },
    ]
    with open(session_file, "w", encoding="utf-8") as f:
        f.writelines(json.dumps(item) + "\n" for item in lines)

    adapter = ClaudeCodeLogAdapter(mode="file")

    # start_step = 0 -> 2 steps
    traj_all = adapter.parse_session_file(session_file, start_step=0)
    assert traj_all is not None
    assert len(traj_all.steps) == 2

    # start_step = 1 -> 1 step (second step)
    traj_delta = adapter.parse_session_file(session_file, start_step=1)
    assert traj_delta is not None
    assert len(traj_delta.steps) == 1
    assert traj_delta.steps[0].tool_name == "Read"

    # start_step >= 2 -> 0 steps
    traj_empty = adapter.parse_session_file(session_file, start_step=2)
    assert traj_empty is not None
    assert len(traj_empty.steps) == 0


def test_claude_discover_unprocessed_sessions(tmp_path: Path):
    proj_dir1 = tmp_path / "proj1"
    proj_dir2 = tmp_path / "proj2"
    proj_dir1.mkdir(parents=True)
    proj_dir2.mkdir(parents=True)

    f1 = proj_dir1 / "sess1.jsonl"
    f2 = proj_dir2 / "sess2.jsonl"
    f1.write_text('{"type": "mode"}\n', encoding="utf-8")
    f2.write_text('{"type": "mode"}\n', encoding="utf-8")

    adapter = ClaudeCodeLogAdapter(projects_dir=tmp_path)
    assert adapter.is_available() is True

    # Initial discovery with empty set
    discovered = adapter.discover_unprocessed_sessions(set())
    assert len(discovered) == 2
    keys = [item[0] for item in discovered]
    assert "claude:proj1/sess1" in keys
    assert "claude:proj2/sess2" in keys

    # With proj1/sess1 marked processed in set
    subset = adapter.discover_unprocessed_sessions({"claude:proj1/sess1"})
    assert len(subset) == 1
    assert subset[0][0] == "claude:proj2/sess2"

    # With dict checkpoint containing mtime
    f1_mtime = f1.stat().st_mtime
    checkpoint_state = {
        "claude:proj1/sess1": {"mtime": f1_mtime, "step_count": 2},
        "claude:proj2/sess2": {"mtime": 0.0, "step_count": 0},
    }
    discovered_dict = adapter.discover_unprocessed_sessions(checkpoint_state)
    assert len(discovered_dict) == 1
    assert discovered_dict[0][0] == "claude:proj2/sess2"
    assert discovered_dict[0][2] == {"mtime": 0.0, "step_count": 0}
