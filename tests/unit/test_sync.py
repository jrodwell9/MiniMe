from pathlib import Path

import pytest

from wikiskill.sync import GitHubSyncManager, _parse_frontmatter


@pytest.fixture
def mock_hub_and_project(tmp_path: Path):
    hub_dir = tmp_path / "hub"
    hub_dir.mkdir()

    project_dir = tmp_path / "project_alpha"
    project_dir.mkdir()

    wiki_dir = project_dir / ".claude" / "wiki"
    patterns_dir = wiki_dir / "patterns"
    patterns_dir.mkdir(parents=True)
    (patterns_dir / "alpha-pattern.md").write_text(
        "# Alpha Pattern\n\nFix: Alpha fix.", encoding="utf-8"
    )
    (wiki_dir / "index.md").write_text(
        "# Index\n- [alpha-pattern](wiki/patterns/alpha-pattern.md)\n",
        encoding="utf-8",
    )

    return hub_dir, project_dir


def test_sync_manager_init_hub(mock_hub_and_project):
    hub_dir, _ = mock_hub_and_project
    manager = GitHubSyncManager(hub_dir=hub_dir)
    success = manager.init_hub()
    assert success is True
    assert (hub_dir / "global" / "wiki" / "patterns").is_dir()
    assert (hub_dir / "global" / "skills").is_dir()


def test_sync_project_to_hub(mock_hub_and_project):
    hub_dir, project_dir = mock_hub_and_project
    manager = GitHubSyncManager(hub_dir=hub_dir)
    manager.init_hub()

    # Add universal pattern and skill to project
    universal_pat = (
        project_dir / ".claude" / "wiki" / "patterns" / "edit-string-mismatch-loop.md"
    )
    universal_pat.write_text("# Universal Edit Fix", encoding="utf-8")

    proj_skill = project_dir / ".claude" / "skills" / "file-editing"
    proj_skill.mkdir(parents=True, exist_ok=True)
    (proj_skill / "SKILL.md").write_text(
        "---\nname: file-editing\n---\n", encoding="utf-8"
    )

    result = manager.sync_project_to_hub(project_dir)
    assert result["status"] == "success"
    assert "edit-string-mismatch-loop" in result["synced_patterns"]
    assert "file-editing" in result["synced_skills"]

    # Verify promoted global files exist in hub
    assert (
        hub_dir / "global" / "wiki" / "patterns" / "edit-string-mismatch-loop.md"
    ).exists()
    assert (hub_dir / "global" / "skills" / "file-editing" / "SKILL.md").exists()


def test_sync_hub_to_project(mock_hub_and_project):
    hub_dir, project_dir = mock_hub_and_project
    manager = GitHubSyncManager(hub_dir=hub_dir)
    manager.init_hub()

    # Create a global skill in hub
    global_skill_dir = hub_dir / "global" / "skills" / "global-git-hygiene"
    global_skill_dir.mkdir(parents=True)
    (global_skill_dir / "SKILL.md").write_text(
        "---\nname: global-git-hygiene\n---\nRules: git status.",
        encoding="utf-8",
    )

    result = manager.sync_hub_to_project(project_dir)
    assert result["status"] == "success"

    # Verify global skill was copied to project
    assert (
        project_dir / ".claude" / "skills" / "global-git-hygiene" / "SKILL.md"
    ).exists()


def test_sync_hub_to_project_with_prune(mock_hub_and_project):
    hub_dir, project_dir = mock_hub_and_project
    manager = GitHubSyncManager(hub_dir=hub_dir)
    manager.init_hub()

    # Create an orphaned/rejected local skill and pattern in project
    local_skills_dir = project_dir / ".claude" / "skills" / "rejected-skill"
    local_skills_dir.mkdir(parents=True)
    (local_skills_dir / "SKILL.md").write_text("Rejected", encoding="utf-8")

    local_patterns_dir = project_dir / ".claude" / "wiki" / "patterns"
    local_patterns_dir.mkdir(parents=True, exist_ok=True)
    (local_patterns_dir / "rejected-pattern.md").write_text(
        "Rejected", encoding="utf-8"
    )

    # Valid global skill
    global_skill_dir = hub_dir / "global" / "skills" / "valid-skill"
    global_skill_dir.mkdir(parents=True)
    (global_skill_dir / "SKILL.md").write_text("Valid", encoding="utf-8")

    result = manager.sync_hub_to_project(project_dir, prune=True)
    assert result["status"] == "success"
    assert "rejected-skill" in result["pruned_skills"]
    assert "rejected-pattern" in result["pruned_patterns"]

    # Verify pruned files were removed
    assert not (project_dir / ".claude" / "skills" / "rejected-skill").exists()
    assert not (local_patterns_dir / "rejected-pattern.md").exists()
    # Verify valid skill was applied
    assert (project_dir / ".claude" / "skills" / "valid-skill" / "SKILL.md").exists()

