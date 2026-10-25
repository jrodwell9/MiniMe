import json
import os
from datetime import UTC, datetime
from pathlib import Path

from wikiskill.adapters.antigravity import AntigravityLogAdapter
from wikiskill.models import SessionTrajectory


def test_antigravity_adapter_mock_mode():
    adapter = AntigravityLogAdapter(mode="mock")
    trajectory = adapter.get_latest_session_trajectory()
    assert trajectory is not None
    assert isinstance(trajectory, SessionTrajectory)
    assert trajectory.session_id == "mock-antigravity-conv-1"
    assert trajectory.model_routed == "gemini-3.7-flash"
    assert len(trajectory.steps) == 2
    assert trajectory.steps[0].tool_name == "view_file"
    assert trajectory.steps[1].tool_name == "run_command"


def test_antigravity_parse_transcript_jsonl(tmp_path: Path):
    conv_id = "990c92a7-590f-4cd4-ade3-7d75c2271875"
    conv_dir = tmp_path / "brain" / conv_id / ".system_generated" / "logs"
    conv_dir.mkdir(parents=True)
    transcript_file = conv_dir / "transcript.jsonl"

    records = [
        {
            "step_index": 0,
            "source": "USER_EXPLICIT",
            "type": "USER_INPUT",
            "status": "DONE",
            "created_at": "2026-10-04T17:00:00Z",
            "content": "<USER_REQUEST>Fix lint errors</USER_REQUEST>",
        },
        {
            "step_index": 1,
            "source": "MODEL",
            "type": "PLANNER_RESPONSE",
            "status": "DONE",
            "created_at": "2026-10-04T17:00:02Z",
            "tool_calls": [
                {
                    "name": "view_file",
                    "args": {
                        "AbsolutePath": '"c:/Users/test/main.py"',
                        "toolAction": '"Viewing file"',
                        "toolSummary": '"Read main.py"',
                    },
                }
            ],
        },
        {
            "step_index": 2,
            "source": "MODEL",
            "type": "GENERIC",
            "status": "DONE",
            "created_at": "2026-10-04T17:00:04Z",
            "content": "File Path: c:/Users/test/main.py\n1: print('hello')",
        },
        {
            "step_index": 3,
            "source": "MODEL",
            "type": "PLANNER_RESPONSE",
            "status": "DONE",
            "created_at": "2026-10-04T17:00:05Z",
            "tool_calls": [
                {
                    "name": "run_command",
                    "args": {
                        "CommandLine": "uv run ruff check .",
                        "Cwd": "c:/Users/test",
                    },
                }
            ],
        },
        {
            "step_index": 4,
            "source": "MODEL",
            "type": "GENERIC",
            "status": "ERROR",
            "created_at": "2026-10-04T17:00:07Z",
            "content": "Error: undefined variable 'x' on line 10",
        },
    ]

    with open(transcript_file, "w", encoding="utf-8") as f:
        f.writelines(json.dumps(r) + "\n" for r in records)

    adapter = AntigravityLogAdapter(antigravity_dir=tmp_path)
    trajectory = adapter.parse_session_file(transcript_file)

    assert trajectory is not None
    assert trajectory.session_id == conv_id
    assert len(trajectory.steps) == 2

    # Step 1: view_file
    step1 = trajectory.steps[0]
    assert step1.step_number == 1
    assert step1.tool_name == "view_file"
    assert step1.tool_input["AbsolutePath"] == "c:/Users/test/main.py"
    assert "print('hello')" in step1.observation
    assert step1.is_error is False

    # Step 2: run_command
    step2 = trajectory.steps[1]
    assert step2.step_number == 2
    assert step2.tool_name == "run_command"
    assert step2.tool_input["CommandLine"] == "uv run ruff check ."
    assert "Error: undefined variable" in step2.observation
    assert step2.is_error is True


def test_antigravity_discover_unprocessed_sessions(tmp_path: Path):
    brain_dir = tmp_path / "brain"
    conv1 = brain_dir / "conv-111" / ".system_generated" / "logs"
    conv2 = brain_dir / "conv-222" / ".system_generated" / "logs"
    conv1.mkdir(parents=True)
    conv2.mkdir(parents=True)

    (conv1 / "transcript.jsonl").write_text('{"step_index": 0}\n', encoding="utf-8")
    (conv2 / "transcript.jsonl").write_text('{"step_index": 0}\n', encoding="utf-8")

    adapter = AntigravityLogAdapter(antigravity_dir=tmp_path)
    assert adapter.is_available() is True

    # Initial discovery
    discovered = adapter.discover_unprocessed_sessions(set())
    assert len(discovered) == 2
    keys = [item[0] for item in discovered]
    assert "antigravity:conv-111" in keys
    assert "antigravity:conv-222" in keys

    # With conv-111 marked processed in a set
    processed = {"antigravity:conv-111"}
    discovered_subset = adapter.discover_unprocessed_sessions(processed)
    assert len(discovered_subset) == 1
    assert discovered_subset[0][0] == "antigravity:conv-222"

    # With dict checkpoint containing mtime
    f1 = conv1 / "transcript.jsonl"
    f1_mtime = f1.stat().st_mtime
    checkpoint_state = {
        "antigravity:conv-111": {"mtime": f1_mtime, "step_count": 5},
        "antigravity:conv-222": {"mtime": 0.0, "step_count": 0},
    }
    discovered_dict = adapter.discover_unprocessed_sessions(checkpoint_state)
    # conv-111 is up-to-date, conv-222 has mtime > 0.0
    assert len(discovered_dict) == 1
    assert discovered_dict[0][0] == "antigravity:conv-222"
    assert discovered_dict[0][2] == {"mtime": 0.0, "step_count": 0}


def test_antigravity_parse_transcript_start_step(tmp_path: Path):
    conv_id = "conv-step-test"
    conv_dir = tmp_path / "brain" / conv_id / ".system_generated" / "logs"
    conv_dir.mkdir(parents=True)
    transcript_file = conv_dir / "transcript.jsonl"

    records = [
        {
            "step_index": 0,
            "source": "USER_EXPLICIT",
            "type": "USER_INPUT",
            "content": "test step 0",
        },
        {
            "step_index": 1,
            "source": "MODEL",
            "type": "PLANNER_RESPONSE",
            "tool_calls": [
                {
                    "name": "view_file",
                    "args": {"AbsolutePath": "file1.py"},
                }
            ],
        },
        {
            "step_index": 2,
            "source": "MODEL",
            "type": "GENERIC",
            "content": "content of file 1",
        },
        {
            "step_index": 3,
            "source": "MODEL",
            "type": "PLANNER_RESPONSE",
            "tool_calls": [
                {
                    "name": "run_command",
                    "args": {"CommandLine": "pytest"},
                }
            ],
        },
        {
            "step_index": 4,
            "source": "MODEL",
            "type": "GENERIC",
            "content": "passed",
        },
    ]
    with open(transcript_file, "w", encoding="utf-8") as f:
        f.writelines(json.dumps(r) + "\n" for r in records)

    adapter = AntigravityLogAdapter(antigravity_dir=tmp_path)

    # start_step = 0 -> all 2 steps
    traj_all = adapter.parse_session_file(transcript_file, start_step=0)
    assert traj_all is not None
    assert len(traj_all.steps) == 2
    assert traj_all.steps[0].tool_name == "view_file"
    assert traj_all.steps[1].tool_name == "run_command"

    # start_step = 1 -> only step 2 (run_command)
    traj_delta = adapter.parse_session_file(transcript_file, start_step=1)
    assert traj_delta is not None
    assert len(traj_delta.steps) == 1
    assert traj_delta.steps[0].tool_name == "run_command"

    # start_step >= 2 -> 0 steps
    traj_empty = adapter.parse_session_file(transcript_file, start_step=2)
    assert traj_empty is not None
    assert len(traj_empty.steps) == 0


def test_antigravity_find_latest_session_file_with_since(tmp_path: Path):
    brain_dir = tmp_path / "brain"
    conv1 = brain_dir / "conv-older" / ".system_generated" / "logs"
    conv2 = brain_dir / "conv-newer" / ".system_generated" / "logs"
    conv1.mkdir(parents=True)
    conv2.mkdir(parents=True)

    f1 = conv1 / "transcript.jsonl"
    f2 = conv2 / "transcript.jsonl"
    f1.write_text('{"step_index": 0}\n', encoding="utf-8")
    f2.write_text('{"step_index": 0}\n', encoding="utf-8")

    os.utime(f1, (1000, 1000))
    os.utime(f2, (3000, 3000))

    adapter = AntigravityLogAdapter(antigravity_dir=tmp_path)

    # Without since
    latest = adapter._find_latest_session_file()
    assert latest == f2

    # With since after f1 but before f2
    since_dt = datetime.fromtimestamp(2000, tz=UTC).isoformat()
    latest_since = adapter._find_latest_session_file(since=since_dt)
    assert latest_since == f2

    # With since after f2
    since_future = datetime.fromtimestamp(4000, tz=UTC).isoformat()
    latest_future = adapter._find_latest_session_file(since=since_future)
    assert latest_future is None
