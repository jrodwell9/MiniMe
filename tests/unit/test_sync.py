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

