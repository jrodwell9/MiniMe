from pathlib import Path

import pytest

from wikiskill.sync import GitHubSyncManager


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
    assert (hub_dir / "projects").is_dir()


def test_sync_project_to_hub(mock_hub_and_project):
    hub_dir, project_dir = mock_hub_and_project
    manager = GitHubSyncManager(hub_dir=hub_dir)
    manager.init_hub()

    result = manager.sync_project_to_hub(project_dir)
    assert result["status"] == "success"

    # Verify project patterns were synced to hub
    project_slug = result["project_slug"]
    hub_project_patterns = hub_dir / "projects" / project_slug / "wiki" / "patterns"
    assert (hub_project_patterns / "alpha-pattern.md").exists()


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
