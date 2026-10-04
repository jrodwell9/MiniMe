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


def test_push_patterns_pr_mode(mock_hub_and_project):
    hub_dir, _ = mock_hub_and_project
    manager = GitHubSyncManager(hub_dir=hub_dir)
    manager.init_hub()

    # Create a new pattern and skill in hub global
    new_pat = hub_dir / "global" / "wiki" / "patterns" / "new-pattern.md"
    new_pat.parent.mkdir(parents=True, exist_ok=True)
    new_pat.write_text(
        "# New Pattern\n\n## Description\nFailure description\n\n## Recommended Fix\nFix description\n",
        encoding="utf-8",
    )

    new_skill = hub_dir / "global" / "skills" / "new-skill"
    new_skill.mkdir(parents=True, exist_ok=True)
    (new_skill / "SKILL.md").write_text(
        "---\nname: new-skill\ndescription: A new skill\nstatus: active\npatterns_addressed: [new-pattern]\n---\nRules\n",
        encoding="utf-8",
    )

    res = manager.push_patterns(
        commit_message="Test PR push",
        direct=False,
        branch_name="proposal/test-branch",
    )
    assert res["status"] == "success"
    assert res["mode"] == "pr"
    assert res["branch"] == "proposal/test-branch"
    assert "description" in res
    assert "new-skill" in res["description"]
    assert "new-pattern.md" in res["description"]
    assert len(res["proposals"]) >= 1


def test_push_patterns_multi_skill_pr_mode(mock_hub_and_project):
    hub_dir, _ = mock_hub_and_project
    manager = GitHubSyncManager(hub_dir=hub_dir)
    manager.init_hub()

    # Create two skills
    skill_a = hub_dir / "global" / "skills" / "skill-a"
    skill_a.mkdir(parents=True, exist_ok=True)
    (skill_a / "SKILL.md").write_text(
        "---\nname: skill-a\ndescription: Skill A\nstatus: active\n---\nRules A\n",
        encoding="utf-8",
    )

    skill_b = hub_dir / "global" / "skills" / "skill-b"
    skill_b.mkdir(parents=True, exist_ok=True)
    (skill_b / "SKILL.md").write_text(
        "---\nname: skill-b\ndescription: Skill B\nstatus: active\n---\nRules B\n",
        encoding="utf-8",
    )

    res = manager.push_patterns(direct=False)
    assert res["status"] == "success"
    assert res["mode"] == "pr"
    assert len(res["proposals"]) == 2
    prop_names = [p["name"] for p in res["proposals"]]
    assert "skill-a" in prop_names
    assert "skill-b" in prop_names
    for prop in res["proposals"]:
        assert f"proposal/skill-{prop['name']}-" in prop["branch"]

    # Verify PR descriptions are self-contained
    prop_a = next(p for p in res["proposals"] if p["name"] == "skill-a")
    prop_b = next(p for p in res["proposals"] if p["name"] == "skill-b")

    assert "skill-a" in prop_a["description"]
    assert "skill-b" not in prop_a["description"]

    assert "skill-b" in prop_b["description"]
    assert "skill-a" not in prop_b["description"]


def test_push_patterns_multi_skill_and_unclaimed_patterns_self_contained(
    mock_hub_and_project,
):
    hub_dir, _ = mock_hub_and_project
    manager = GitHubSyncManager(hub_dir=hub_dir)
    manager.init_hub()

    # Pattern A addressed by Skill A
    pat_a = hub_dir / "global" / "wiki" / "patterns" / "pattern-a.md"
    pat_a.parent.mkdir(parents=True, exist_ok=True)
    pat_a.write_text(
        "# Pattern A\n\n## Description\nDesc A\n## Recommended Fix\nFix A\n",
        encoding="utf-8",
    )

    # Pattern B addressed by Skill B
    pat_b = hub_dir / "global" / "wiki" / "patterns" / "pattern-b.md"
    pat_b.write_text(
        "# Pattern B\n\n## Description\nDesc B\n## Recommended Fix\nFix B\n",
        encoding="utf-8",
    )

    # Pattern C unclaimed
    pat_c = hub_dir / "global" / "wiki" / "patterns" / "pattern-c.md"
    pat_c.write_text(
        "# Pattern C\n\n## Description\nDesc C\n## Recommended Fix\nFix C\n",
        encoding="utf-8",
    )

    # Skill A
    skill_a = hub_dir / "global" / "skills" / "skill-a"
    skill_a.mkdir(parents=True, exist_ok=True)
    (skill_a / "SKILL.md").write_text(
        "---\nname: skill-a\ndescription: Skill A\nstatus: active\npatterns_addressed: [pattern-a]\n---\nRules A\n",
        encoding="utf-8",
    )

    # Skill B
    skill_b = hub_dir / "global" / "skills" / "skill-b"
    skill_b.mkdir(parents=True, exist_ok=True)
    (skill_b / "SKILL.md").write_text(
        "---\nname: skill-b\ndescription: Skill B\nstatus: active\npatterns_addressed: [pattern-b]\n---\nRules B\n",
        encoding="utf-8",
    )

    res = manager.push_patterns(direct=False)
    assert res["status"] == "success"
    assert res["mode"] == "pr"
    # Should produce 3 PRs: skill-a (with pat_a), skill-b (with pat_b), and patterns (with pat_c)
    assert len(res["proposals"]) == 3

    prop_a = next(p for p in res["proposals"] if p["name"] == "skill-a")
    prop_b = next(p for p in res["proposals"] if p["name"] == "skill-b")
    prop_c = next(p for p in res["proposals"] if p["name"] == "patterns")

    # PR A: only skill-a and pattern-a
    assert "skill-a" in prop_a["description"]
    assert "pattern-a.md" in prop_a["description"]
    assert "skill-b" not in prop_a["description"]
    assert "pattern-b.md" not in prop_a["description"]
    assert "pattern-c.md" not in prop_a["description"]

    # PR B: only skill-b and pattern-b
    assert "skill-b" in prop_b["description"]
    assert "pattern-b.md" in prop_b["description"]
    assert "skill-a" not in prop_b["description"]
    assert "pattern-a.md" not in prop_b["description"]
    assert "pattern-c.md" not in prop_b["description"]

    # PR C: only pattern-c
    assert "pattern-c.md" in prop_c["description"]
    assert "skill-a" not in prop_c["description"]
    assert "skill-b" not in prop_c["description"]
    assert "pattern-a.md" not in prop_c["description"]
    assert "pattern-b.md" not in prop_c["description"]


def test_get_remote_owner_repo():
    manager = GitHubSyncManager(remote_url="https://github.com/user123/repo456.git")
    assert manager._get_remote_owner_repo() == ("user123", "repo456")

    manager_ssh = GitHubSyncManager(remote_url="git@github.com:user123/repo456.git")
    assert manager_ssh._get_remote_owner_repo() == ("user123", "repo456")


def test_create_pull_request_gh_cli(monkeypatch):
    manager = GitHubSyncManager(remote_url="https://github.com/user123/repo456.git")
    monkeypatch.setattr(
        "shutil.which", lambda cmd: "/usr/bin/gh" if cmd == "gh" else None
    )

    class MockProcess:
        returncode = 0
        stdout = "https://github.com/user123/repo456/pull/99\n"

    monkeypatch.setattr(
        "subprocess.run",
        lambda *args, **kwargs: MockProcess(),
    )

    pr_url = manager._create_pull_request(
        target_branch="proposal/skills-1",
        title="Evolution Proposal",
        body="Description",
    )
    assert pr_url == "https://github.com/user123/repo456/pull/99"


def test_create_pull_request_web_fallback_accept(monkeypatch):
    manager = GitHubSyncManager(remote_url="https://github.com/user123/repo456.git")
    monkeypatch.setattr("shutil.which", lambda cmd: None)
    monkeypatch.setattr("builtins.input", lambda prompt="": "y")

    import sys

    monkeypatch.setattr(sys.stdin, "isatty", lambda: True)

    pr_url = manager._create_pull_request(
        target_branch="proposal/skills-1",
        title="Evolution Proposal",
        body="Description",
        interactive=True,
    )
    assert pr_url is not None
    assert (
        "https://github.com/user123/repo456/compare/main...proposal/skills-1" in pr_url
    )
    assert "expand=1" in pr_url


def test_create_pull_request_web_fallback_deny(monkeypatch):
    manager = GitHubSyncManager(remote_url="https://github.com/user123/repo456.git")
    monkeypatch.setattr("shutil.which", lambda cmd: None)
    monkeypatch.setattr("builtins.input", lambda prompt="": "n")

    import sys

    monkeypatch.setattr(sys.stdin, "isatty", lambda: True)

    pr_url = manager._create_pull_request(
        target_branch="proposal/skills-1",
        title="Evolution Proposal",
        body="Description",
        interactive=True,
    )
    assert pr_url is None


def test_push_patterns_aborted_when_user_denies_web_fallback(
    mock_hub_and_project, monkeypatch
):
    hub_dir, _ = mock_hub_and_project
    manager = GitHubSyncManager(hub_dir=hub_dir)
    manager.init_hub()

    # Create a new skill in hub
    skill_dir = hub_dir / "global" / "skills" / "test-abort-skill"
    skill_dir.mkdir(parents=True, exist_ok=True)
    (skill_dir / "SKILL.md").write_text(
        "---\nname: test-abort-skill\n---\nRules", encoding="utf-8"
    )

    monkeypatch.setattr("shutil.which", lambda cmd: None)
    monkeypatch.setattr("builtins.input", lambda prompt="": "n")

    import sys

    monkeypatch.setattr(sys.stdin, "isatty", lambda: True)

    res = manager.push_patterns(direct=False, interactive=True)
    assert res["status"] == "aborted"
    assert res["success"] is False

    # Verify no candidate branches were created
    _, branches = manager._run_git(["branch"])
    assert "proposal/" not in branches


def test_parse_frontmatter():
    # Empty / non-frontmatter
    assert _parse_frontmatter("No frontmatter") == {}
    assert _parse_frontmatter("---\n---") == {}

    # Multiline list
    content_multiline = """---
name: cross-agent-skill-linking
description: Standards for sharing and linking skills across different agent harnesses
status: active
origin_session: in-flight
patterns_addressed:
  - cross-agent-skill-discovery
  - second-pattern
---
# Rules
"""
    parsed = _parse_frontmatter(content_multiline)
    assert parsed["name"] == "cross-agent-skill-linking"
    assert "Standards for sharing" in parsed["description"]
    assert parsed["status"] == "active"
    assert parsed["origin_session"] == "in-flight"
    assert parsed["patterns_addressed"] == [
        "cross-agent-skill-discovery",
        "second-pattern",
    ]

    # Inline list and quotes
    content_inline = """---
name: 'test-skill'
patterns: ["pat1", "pat2"]
---
Body
"""
    parsed_inline = _parse_frontmatter(content_inline)
    assert parsed_inline["name"] == "test-skill"
    assert parsed_inline["patterns"] == ["pat1", "pat2"]


def test_push_patterns_multiline_yaml_patterns_addressed(mock_hub_and_project):
    hub_dir, _ = mock_hub_and_project
    manager = GitHubSyncManager(hub_dir=hub_dir)
    manager.init_hub()

    # Create pattern
    pat_file = hub_dir / "global" / "wiki" / "patterns" / "linked-pattern.md"
    pat_file.parent.mkdir(parents=True, exist_ok=True)
    pat_file.write_text(
        "# Linked Pattern\n\n## Description\nPattern description\n",
        encoding="utf-8",
    )

    # Create skill referencing pattern via multiline YAML list
    skill_dir = hub_dir / "global" / "skills" / "linked-skill"
    skill_dir.mkdir(parents=True, exist_ok=True)
    (skill_dir / "SKILL.md").write_text(
        "---\nname: linked-skill\ndescription: Linked skill\npatterns_addressed:\n  - linked-pattern\n---\nRules\n",
        encoding="utf-8",
    )

    res = manager.push_patterns(
        commit_message="Test multiline PR push",
        direct=False,
    )
    assert res["status"] == "success"
    assert res["mode"] == "pr"
    # Exactly one proposal for the skill, bundled with the pattern (no standalone patterns PR)
    assert len(res["proposals"]) == 1
    assert res["proposals"][0]["name"] == "linked-skill"
    assert "linked-pattern.md" in res["description"]
