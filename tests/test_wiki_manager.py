import os
from unittest.mock import patch

import pytest

from ..scripts.wiki_manager import WikiManager


@pytest.fixture
def wiki_manager(tmp_path):
    # Create a temporary directory structure for wiki files
    wiki_path = tmp_path / ".claude" / "wiki"
    patterns_path = wiki_path / "patterns"
    patterns_path.mkdir(parents=True)
    (wiki_path / "index.md").write_text("Initial Index\n")
    (wiki_path / "logs.md").write_text("Initial Log\n")
    (wiki_path / "skill-impact.md").write_text("Initial Impact\n")
    return WikiManager(base_path=str(wiki_path))


# Test cases for WikiManager
def test_wiki_manager_init(wiki_manager, tmp_path):
    assert wiki_manager.base_path == str(tmp_path / ".claude" / "wiki")
    assert os.path.exists(wiki_manager.index_path)
    assert os.path.exists(wiki_manager.logs_path)
    assert os.path.exists(wiki_manager.skill_impact_path)


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
    # First create a pattern to update
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


@patch("MiniMe.scripts.wiki_manager.WikiManager.call_llm_for_wiki_update")
def test_wiki_manager_process_llm_wiki_response(
    mock_call_llm_for_wiki_update, wiki_manager, tmp_path
):
    mock_call_llm_for_wiki_update.return_value = {
        "create_patterns": [
            {"name": "mock-pattern-create", "content": "Mock created content."}
        ],
        "update_patterns": [
            {"name": "mock-pattern-update", "content": "Mock updated content."}
        ],
        "update_index": {"additions": ["- Index addition."]},
        "append_log": "Mock log entry.",
    }

    # Pre-create a pattern for update
    (tmp_path / ".claude" / "wiki" / "patterns" / "mock-pattern-update.md").write_text(
        "Original update content."
    )

    # Call the LLM simulation function first to populate the mock return value
    llm_response_data = mock_call_llm_for_wiki_update.return_value
    wiki_manager.process_llm_wiki_response(llm_response_data)

    assert (
        tmp_path / ".claude" / "wiki" / "patterns" / "mock-pattern-create.md"
    ).read_text() == "Mock created content."
    assert (
        tmp_path / ".claude" / "wiki" / "patterns" / "mock-pattern-update.md"
    ).read_text() == "Mock updated content."
    assert (
        tmp_path / ".claude" / "wiki" / "index.md"
    ).read_text() == "Initial Index\n- Index addition.\n"
    assert (
        tmp_path / ".claude" / "wiki" / "logs.md"
    ).read_text() == "Initial Log\nMock log entry.\n"