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
    assert results[0]["project_slug"] == proj_slug

    # Verify session is marked as processed
    assert "sess-1234" in daemon.processed_sessions

    # Running scan again should skip already processed session
    second_results = daemon.scan_and_process_sessions()
    assert len(second_results) == 0
