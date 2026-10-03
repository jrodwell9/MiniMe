from pathlib import Path

import pytest

from wikiskill.mcp import (
    get_active_skills,
    handle_mcp_call,
    lookup_pattern,
    record_reflection,
)


@pytest.fixture
def mock_wiki_structure(tmp_path: Path):
    wiki_dir = tmp_path / ".claude" / "wiki"
    patterns_dir = wiki_dir / "patterns"
    patterns_dir.mkdir(parents=True)

    (patterns_dir / "edit-string-mismatch-loop.md").write_text(
        "# Edit String Mismatch Loop\n\n## Problem\nString not found.\n\n## Fix\nInspect lines before edit.",
        encoding="utf-8",
    )
    (wiki_dir / "index.md").write_text(
        "# Index\n\n- [edit-string-mismatch-loop](wiki/patterns/edit-string-mismatch-loop.md): Edit mismatch.",
        encoding="utf-8",
    )

    skills_dir = tmp_path / ".claude" / "skills" / "file-editing"
    skills_dir.mkdir(parents=True)
    (skills_dir / "SKILL.md").write_text(
        "---\nname: file-editing\ndescription: Rules for editing\n---\n\n## Rules\n- View lines first.",
        encoding="utf-8",
    )

    return tmp_path


def test_mcp_lookup_pattern_found(mock_wiki_structure: Path):
    result = lookup_pattern("edit mismatch", project_dir=str(mock_wiki_structure))
    assert result["status"] == "found"
    assert "Edit String Mismatch Loop" in result["content"]
    assert "Inspect lines before edit" in result["content"]


def test_mcp_lookup_pattern_not_found(mock_wiki_structure: Path):
    result = lookup_pattern(
        "nonexistent pattern query", project_dir=str(mock_wiki_structure)
    )
    assert result["status"] == "not_found"


def test_mcp_get_active_skills(mock_wiki_structure: Path):
    result = get_active_skills(project_dir=str(mock_wiki_structure))
    assert result["status"] == "success"
    assert len(result["skills"]) >= 1
    assert result["skills"][0]["name"] == "file-editing"
    assert "View lines first" in result["skills"][0]["content"]


def test_mcp_record_reflection(mock_wiki_structure: Path):
    result = record_reflection(
        summary="Custom CLI syntax error",
        error_encountered="Exit code 127: invalid flag --xyz",
        fix_applied="Pass --help first to check flags",
        project_dir=str(mock_wiki_structure),
    )
    assert result["status"] == "success"
    pattern_name = result["pattern_name"]
    pattern_file = (
        mock_wiki_structure / ".claude" / "wiki" / "patterns" / f"{pattern_name}.md"
    )
    assert pattern_file.exists()
    assert "invalid flag --xyz" in pattern_file.read_text(encoding="utf-8")


def test_mcp_json_rpc_dispatcher(mock_wiki_structure: Path):
    # Test JSON-RPC tools/call request
    request = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "tools/call",
        "params": {
            "name": "lookup_pattern",
            "arguments": {
                "query": "edit mismatch",
                "project_dir": str(mock_wiki_structure),
            },
        },
    }
    response = handle_mcp_call(request)
    assert response["jsonrpc"] == "2.0"
    assert response["id"] == 1
    assert "Edit String Mismatch Loop" in response["result"]["content"][0]["text"]
