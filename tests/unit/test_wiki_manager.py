import os
from pathlib import Path

import pytest

from wikiskill.dataclasses import SessionTrajectory, TrajectoryStep
from wikiskill.wiki_manager import WikiManager


@pytest.fixture
def wiki_manager(tmp_path):
    wiki_path = tmp_path / ".claude" / "wiki"
    patterns_path = wiki_path / "patterns"
    patterns_path.mkdir(parents=True)
    (wiki_path / "index.md").write_text("Initial Index\n")
    (wiki_path / "logs.md").write_text("Initial Log\n")
    (wiki_path / "skill-impact.md").write_text("Initial Impact\n")
    return WikiManager(base_path=str(wiki_path))


def test_wiki_manager_init(wiki_manager, tmp_path):
    assert wiki_manager.base_path == str(tmp_path / ".claude" / "wiki")
    assert os.path.exists(wiki_manager.index_path)
    assert os.path.exists(wiki_manager.patterns_path)


def test_wiki_manager_read_file_success(wiki_manager):
    content = wiki_manager._read_file(wiki_manager.index_path)
    assert content == "Initial Index\n"


def test_wiki_manager_read_file_not_found(wiki_manager):
    content = wiki_manager._read_file("non_existent_file.md")
    assert content is None


def test_wiki_manager_write_file(wiki_manager, tmp_path):
    test_file = tmp_path / ".claude" / "wiki" / "test_write.md"
    wiki_manager._write_file(str(test_file), "Test content.")
    assert test_file.read_text() == "Test content."


def test_wiki_manager_get_wiki_index(wiki_manager):
    assert wiki_manager.get_wiki_index() == "Initial Index\n"


def test_wiki_manager_get_skill_impact_log(wiki_manager):
    assert wiki_manager.get_skill_impact_log() == "Initial Impact\n"


def test_wiki_manager_create_pattern(wiki_manager, tmp_path):
    wiki_manager.create_pattern("new-pattern", "Content for new pattern.")
    pattern_file = tmp_path / ".claude" / "wiki" / "patterns" / "new-pattern.md"
    assert pattern_file.read_text() == "Content for new pattern."


def test_wiki_manager_update_pattern(wiki_manager, tmp_path, capsys):
    wiki_manager.create_pattern("existing-pattern", "Original content.")
    wiki_manager.update_pattern("existing-pattern", "Updated content.")
    pattern_file = tmp_path / ".claude" / "wiki" / "patterns" / "existing-pattern.md"
    assert pattern_file.read_text() == "Updated content."


def test_wiki_manager_update_pattern_non_existent(wiki_manager, capsys):
    wiki_manager.update_pattern("non-existent-pattern", "Should not be written.")
    captured = capsys.readouterr()
    assert "Warning: Pattern file" in captured.out


def test_wiki_manager_update_index(wiki_manager, tmp_path):
    wiki_manager.update_index(["- New item 1", "- New item 2"])
    index_file = tmp_path / ".claude" / "wiki" / "index.md"
    assert index_file.read_text() == "Initial Index\n- New item 1\n- New item 2\n"


def test_wiki_manager_update_index_no_duplicates(wiki_manager, tmp_path):
    wiki_manager.update_index(["- New item 1"])
    wiki_manager.update_index(["- New item 1", "- Another item"])
    index_file = tmp_path / ".claude" / "wiki" / "index.md"
    assert index_file.read_text() == "Initial Index\n- New item 1\n- Another item\n"


def test_wiki_manager_append_log(wiki_manager, tmp_path):
    wiki_manager.append_log("Log entry 1.")
    wiki_manager.append_log("Log entry 2.")
    log_file = tmp_path / ".claude" / "wiki" / "logs.md"
    assert log_file.read_text() == "Initial Log\nLog entry 1.\nLog entry 2.\n"


def test_wiki_manager_call_llm_for_wiki_update_extracts_real_patterns(wiki_manager):
    trajectory = SessionTrajectory(
        session_id="test-session-patterns",
        timestamp="2026-08-31T12:00:00Z",
        model_routed="claude-3-7-sonnet",
        steps=[
            TrajectoryStep(
                step_number=1,
                tool_name="Edit",
                tool_input={"file_path": "foo.py", "old_string": "def bar():"},
                observation="<tool_use_error>String to replace not found in file.",
                is_error=True,
                latency_ms=10.0,
            ),
            TrajectoryStep(
                step_number=2,
                tool_name="Bash",
                tool_input={"command": "pytest"},
                observation="Exit code 127\n/usr/bin/bash: line 1: pytest: command not found",
                is_error=True,
                latency_ms=15.0,
            ),
        ],
        final_status="success",
    )

    response = wiki_manager.call_llm_for_wiki_update(trajectory, "Initial Index\n")
    assert len(response["create_patterns"]) >= 2
    pattern_names = [p["name"] for p in response["create_patterns"]]
    assert "edit-string-mismatch-loop" in pattern_names
    assert "unprefixed-python-runner-loop" in pattern_names
    assert len(response["update_index"]["additions"]) >= 2
    assert "test-session-patterns" in response["append_log"]


def test_wiki_manager_clean_session_produces_no_patterns(wiki_manager):
    trajectory = SessionTrajectory(
        session_id="clean-test-session",
        timestamp="2026-10-03T12:00:00Z",
        model_routed="claude-3-7-sonnet",
        steps=[
            TrajectoryStep(
                step_number=1,
                tool_name="Read",
                tool_input={"file_path": "app.py"},
                observation="def foo(): pass",
                is_error=False,
                latency_ms=10.0,
            ),
            TrajectoryStep(
                step_number=2,
                tool_name="Bash",
                tool_input={"command": "uv run pytest"},
                observation="1 passed in 0.02s",
                is_error=False,
                latency_ms=25.0,
            ),
        ],
        final_status="success",
    )

    response = wiki_manager.call_llm_for_wiki_update(trajectory, "Initial Index\n")
    assert len(response["create_patterns"]) == 0
    assert len(response["update_index"]["additions"]) == 0
    assert "clean execution" in response["append_log"]


def test_wiki_manager_process_llm_wiki_response_full(wiki_manager, tmp_path):
    llm_response = {
        "create_patterns": [
            {
                "name": "edit-string-mismatch-loop",
                "content": "# Edit String Mismatch Loop\n\n## Problem\nEdit failed.\n\n## Root Cause\nMismatched string.\n\n## Fix\nInspect lines first.",
            }
        ],
        "update_patterns": [],
        "update_index": {
            "additions": [
                "- [edit-string-mismatch-loop](wiki/patterns/edit-string-mismatch-loop.md): Edit failed. Cause: Mismatched string. Fix: Inspect lines first."
            ]
        },
        "append_log": "Session 123: Documented edit-string-mismatch-loop.",
    }

    wiki_manager.process_llm_wiki_response(llm_response)

    pattern_file = Path(wiki_manager.patterns_path) / "edit-string-mismatch-loop.md"
    assert pattern_file.exists()
    assert "# Edit String Mismatch Loop" in pattern_file.read_text(encoding="utf-8")
    assert "- [edit-string-mismatch-loop]" in Path(wiki_manager.index_path).read_text(
        encoding="utf-8"
    )
    assert "Session 123: Documented edit-string-mismatch-loop." in Path(
        wiki_manager.logs_path
    ).read_text(encoding="utf-8")
