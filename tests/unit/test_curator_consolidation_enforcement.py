import subprocess
from pathlib import Path
from typing import Any

import pytest

from wikiskill.curator import (
    CuratorSandboxTools,
    WikiSkillCuratorAgent,
)
from wikiskill.sync import GitHubSyncManager


@pytest.fixture
def sandbox_env(tmp_path: Path) -> tuple[Path, Path]:
    project_dir = tmp_path / "workspace"
    project_dir.mkdir()
    (project_dir / "CLAUDE.md").write_text(
        "# Project Guide\nFollow TDD.", encoding="utf-8"
    )
    (project_dir / "AGENTS.md").write_text("@CLAUDE.md\n", encoding="utf-8")
    (project_dir / "src").mkdir()
    (project_dir / "src" / "app.py").write_text(
        "print('prod code')\n", encoding="utf-8"
    )

    hub_dir = tmp_path / "hub"
    sync_mgr = GitHubSyncManager(
        hub_dir=hub_dir, remote_url="https://github.com/test/skills-hub.git"
    )
    sync_mgr.init_hub()

    # Seed merged skills on hub main
    for skill_name, grp, initial_pat in [
        ("file-editing", "global", "edit-string-mismatch-loop"),
        ("cli-tool-execution", "python", "unprefixed-python-runner-loop"),
        ("dependency-management", "python", "missing-dependency-import-loop"),
    ]:
        merged_skill = hub_dir / "global" / "skills" / skill_name
        merged_skill.mkdir(parents=True, exist_ok=True)
        (merged_skill / "SKILL.md").write_text(
            f"---\nname: {skill_name}\ngroup: {grp}\ndescription: {skill_name} rules\nstatus: active\npatterns_addressed:\n  - {initial_pat}\n---\n\n# Operational Rules\n\n## Rules\n- Initial rule for {skill_name}.\n",
            encoding="utf-8",
        )
        (merged_skill / "PURPOSE.md").write_text(
            f"# Purpose {skill_name}\n", encoding="utf-8"
        )

    sync_mgr._run_git(["add", "."])
    sync_mgr._run_git(["commit", "-m", "Seed merged skills on main"])

    # Sync hub to project so .agents/skills is initialized
    sync_mgr.sync_hub_to_project(project_dir)

    return project_dir, hub_dir


def test_curator_discards_pattern_echoes_and_reconciles_skills_on_disk(
    sandbox_env: tuple[Path, Path],
):
    project_dir, hub_dir = sandbox_env

    # Simulate failure mode where ReAct LLM echoes raw pattern names as proposals and never writes files
    def bad_react_runner(tools: CuratorSandboxTools, **kwargs: Any) -> dict[str, Any]:
        return {
            "proposals": [
                {"name": "file-not-found-access-error", "group": None},
                {"name": "cli-external-command-not-found", "group": None},
                {"name": "python-linting-type-checking-errors", "group": None},
            ],
            "deleted_skills": [],
        }

    agent = WikiSkillCuratorAgent(
        project_dir=project_dir,
        hub_dir=hub_dir,
        react_runner=bad_react_runner,
    )

    extracted_patterns = [
        {
            "name": "file-not-found-access-error",
            "content": "# File Not Found\n\n## Problem\nview_file failed with file not found.\n\n## Fix\nVerify path existence with list_dir before viewing.\n",
        },
        {
            "name": "cli-external-command-not-found",
            "content": "# CLI Command Not Found\n\n## Problem\nCommand not found error in run_command.\n\n## Fix\nCheck tool installation and PATH.\n",
        },
        {
            "name": "python-linting-type-checking-errors",
            "content": "# Python Linting Errors\n\n## Problem\nRuff reported undefined name dspy.\n\n## Fix\nAdd missing imports and sync __all__.\n",
        },
    ]

    res = agent.curate_local_session(
        session_id="test-session-123",
        extracted_patterns=extracted_patterns,
        dry_run=False,
    )

    assert res["status"] == "success"
    proposals = res["proposals"]
    assert len(proposals) > 0

    # Ensure none of the proposals are raw pattern names
    proposal_names = [p["name"] for p in proposals]
    assert "file-not-found-access-error" not in proposal_names
    assert "cli-external-command-not-found" not in proposal_names
    assert "python-linting-type-checking-errors" not in proposal_names

    # Ensure mapped skills are present
    assert "file-editing" in proposal_names
    assert "cli-tool-execution" in proposal_names
    assert "dependency-management" in proposal_names

    # Verify that skill files were ACTUALLY written to disk on .agents/skills
    file_editing_md = (
        project_dir / ".agents" / "skills" / "file-editing" / "SKILL.md"
    ).read_text(encoding="utf-8")
    assert "file-not-found-access-error" in file_editing_md
    assert "Verify path existence" in file_editing_md

    cli_md = (
        project_dir / ".agents" / "skills" / "cli-tool-execution" / "SKILL.md"
    ).read_text(encoding="utf-8")
    assert "cli-external-command-not-found" in cli_md

    dep_md = (
        project_dir / ".agents" / "skills" / "dependency-management" / "SKILL.md"
    ).read_text(encoding="utf-8")
    assert "python-linting-type-checking-errors" in dep_md


def test_curator_dry_run_reconciles_proposals_without_writing_to_disk(
    sandbox_env: tuple[Path, Path],
):
    project_dir, hub_dir = sandbox_env

    def empty_react_runner(tools: CuratorSandboxTools, **kwargs: Any) -> dict[str, Any]:
        return {"proposals": [], "deleted_skills": []}

    agent = WikiSkillCuratorAgent(
        project_dir=project_dir,
        hub_dir=hub_dir,
        react_runner=empty_react_runner,
    )

    extracted_patterns = [
        {
            "name": "file-not-found-access-error",
            "content": "# File Not Found\n\n## Problem\nview_file failed.\n\n## Fix\nUse list_dir first.\n",
        }
    ]

    before_content = (
        project_dir / ".agents" / "skills" / "file-editing" / "SKILL.md"
    ).read_text(encoding="utf-8")

    res = agent.curate_local_session(
        session_id="test-session-dry",
        extracted_patterns=extracted_patterns,
        dry_run=True,
    )

    assert res["status"] == "dry_run"
    assert any(p["name"] == "file-editing" for p in res["proposals"])

    # Disk file must NOT be modified in dry_run
    after_content = (
        project_dir / ".agents" / "skills" / "file-editing" / "SKILL.md"
    ).read_text(encoding="utf-8")
    assert before_content == after_content


def test_sync_push_creates_skill_proposals_after_curator_consolidation(
    sandbox_env: tuple[Path, Path],
    monkeypatch: pytest.MonkeyPatch,
):
    project_dir, hub_dir = sandbox_env

    # Mock gh CLI
    class FakeProc:
        def __init__(self, returncode: int, stdout: str = "", stderr: str = ""):
            self.returncode = returncode
            self.stdout = stdout
            self.stderr = stderr

    gh_pr_created = []
    real_run = subprocess.run

    def fake_subprocess_run(cmd: list[str], *args: Any, **kwargs: Any) -> Any:
        if cmd[0] == "gh":
            if cmd[1:3] == ["auth", "status"]:
                return FakeProc(0, "Logged in")
            if cmd[1:3] == ["pr", "create"]:
                pr_url = (
                    f"https://github.com/test/skills-hub/pull/{len(gh_pr_created) + 1}"
                )
                gh_pr_created.append({"cmd": cmd, "url": pr_url})
                return FakeProc(0, pr_url)
        return real_run(cmd, *args, **kwargs)

    monkeypatch.setattr("subprocess.run", fake_subprocess_run)
    monkeypatch.setattr(
        "shutil.which", lambda prog: "C:/fake/gh.exe" if prog == "gh" else None
    )

    # 1. Curator consolidates patterns into skills on disk
    agent = WikiSkillCuratorAgent(
        project_dir=project_dir,
        hub_dir=hub_dir,
        react_runner=lambda *_, **__: {"proposals": [], "deleted_skills": []},
    )

    extracted_patterns = [
        {
            "name": "file-not-found-access-error",
            "content": "# File Not Found\n\n## Problem\nview_file failed.\n\n## Fix\nVerify path existence.\n",
        }
    ]

    res = agent.curate_local_session(
        session_id="session-e2e",
        extracted_patterns=extracted_patterns,
        dry_run=False,
    )
    assert res["status"] == "success"

    # Also seed the pattern file in .agents/wiki/patterns/
    pat_file = (
        project_dir / ".agents" / "wiki" / "patterns" / "file-not-found-access-error.md"
    )
    pat_file.parent.mkdir(parents=True, exist_ok=True)
    pat_file.write_text(extracted_patterns[0]["content"], encoding="utf-8")

    # 2. Sync project to hub and push
    sync_mgr = GitHubSyncManager(hub_dir=hub_dir)
    sync_res = sync_mgr.sync_project_to_hub(project_dir)
    assert "file-editing" in sync_res["synced_skills"]
    assert "file-not-found-access-error" in sync_res["synced_patterns"]

    push_res = sync_mgr.push_patterns()
    assert push_res.get("mode") == "pr" or len(push_res.get("proposals", [])) > 0
    proposals = push_res.get("proposals", [push_res])

    # The proposal must be a SKILL proposal, NOT a fallback pattern proposal
    skill_proposals = [p for p in proposals if p.get("name") == "file-editing"]
    assert len(skill_proposals) == 1
    assert "proposal/skill-file-editing" in skill_proposals[0]["branch"]
