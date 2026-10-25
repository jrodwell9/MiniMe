import json
from pathlib import Path
from typing import Any

import pytest

from wikiskill.cli import main
from wikiskill.curator import (
    CuratorSandboxError,
    CuratorSandboxTools,
    WikiSkillCuratorAgent,
    bump_plugin_version,
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

    # Seed a merged skill on hub main
    merged_skill = hub_dir / "global" / "skills" / "cli-tool-execution"
    merged_skill.mkdir(parents=True, exist_ok=True)
    (merged_skill / "SKILL.md").write_text(
        "---\nname: cli-tool-execution\ndescription: CLI rules\nstatus: active\npatterns_addressed:\n  - unprefixed-python-runner-loop\n---\n\n# Operational Rules\n\n## Rules\n- Always use uv run.\n",
        encoding="utf-8",
    )
    (merged_skill / "PURPOSE.md").write_text("# Purpose\n", encoding="utf-8")
    sync_mgr._run_git(["add", "."])
    sync_mgr._run_git(["commit", "-m", "Seed merged skill on main"])

    # Sync hub to project so .agents/ is initialized
    sync_mgr.sync_hub_to_project(project_dir)

    return project_dir, hub_dir


def test_sandbox_blocks_writes_outside_agents_dir(sandbox_env: tuple[Path, Path]):
    project_dir, hub_dir = sandbox_env
    tools = CuratorSandboxTools(
        project_dir=project_dir, hub_dir=hub_dir, allow_hub_mutations=False
    )

    # Blocked writes outside .agents/
    with pytest.raises(CuratorSandboxError):
        tools.write_local_file("src/app.py", "hacked")

    with pytest.raises(CuratorSandboxError):
        tools.write_local_file("../escape.md", "hacked")

    with pytest.raises(CuratorSandboxError):
        tools.write_local_file("CLAUDE.md", "overwrite rules")

    assert (project_dir / "src" / "app.py").read_text(
        encoding="utf-8"
    ) == "print('prod code')\n"

    # Allowed writes inside .agents/skills and .agents/wiki
    res_skill = tools.write_local_file(
        "skills/cli-tool-execution/SKILL.md",
        "---\nname: cli-tool-execution\n---\nUpdated\n",
    )
    assert "cli-tool-execution" in res_skill
    assert (
        (project_dir / ".agents" / "skills" / "cli-tool-execution" / "SKILL.md")
        .read_text(encoding="utf-8")
        .endswith("Updated\n")
    )

    res_pat = tools.write_local_file(
        "wiki/patterns/new-pat.md",
        "# New Pat\n",
    )
    assert "new-pat.md" in res_pat
    assert (project_dir / ".agents" / "wiki" / "patterns" / "new-pat.md").exists()


def test_sandbox_blocks_reads_outside_agents_and_project_docs(
    sandbox_env: tuple[Path, Path],
):
    project_dir, hub_dir = sandbox_env
    tools = CuratorSandboxTools(
        project_dir=project_dir, hub_dir=hub_dir, allow_hub_mutations=False
    )

    with pytest.raises(CuratorSandboxError):
        tools.read_local_file("src/app.py")

    with pytest.raises(CuratorSandboxError):
        tools.read_local_file("../secret.txt")

    # Project context (CLAUDE.md / AGENTS.md) is readable
    ctx = tools.read_project_context()
    assert "# Project Guide" in ctx

    # Files inside .agents/ are readable
    skill_text = tools.read_local_file("skills/cli-tool-execution/SKILL.md")
    assert "name: cli-tool-execution" in skill_text


def test_sandbox_protects_merged_hub_skills_from_deletion(
    sandbox_env: tuple[Path, Path],
):
    project_dir, hub_dir = sandbox_env
    tools = CuratorSandboxTools(
        project_dir=project_dir, hub_dir=hub_dir, allow_hub_mutations=False
    )

    # cli-tool-execution is merged on hub main -> cannot be deleted locally
    with pytest.raises(CuratorSandboxError):
        tools.delete_unmerged_local_skill("cli-tool-execution")
    assert (project_dir / ".agents" / "skills" / "cli-tool-execution").exists()

    # Create an unmerged micro-skill locally
    micro_dir = project_dir / ".agents" / "skills" / "uv-arg-micro-skill"
    micro_dir.mkdir(parents=True)
    (micro_dir / "SKILL.md").write_text(
        "---\nname: uv-arg-micro-skill\n---\n", encoding="utf-8"
    )

    msg = tools.delete_unmerged_local_skill("uv-arg-micro-skill")
    assert "uv-arg-micro-skill" in msg
    assert not micro_dir.exists()


def test_sandbox_blocks_hub_mutations_when_disabled(sandbox_env: tuple[Path, Path]):
    project_dir, hub_dir = sandbox_env
    tools = CuratorSandboxTools(
        project_dir=project_dir, hub_dir=hub_dir, allow_hub_mutations=False
    )

    with pytest.raises(CuratorSandboxError):
        tools.upsert_skill_proposal_pr(
            skill_name="cli-tool-execution",
            skill_md_content="---\nname: cli-tool-execution\n---\n",
            purpose_md_content="# Purpose\n",
            patterns={},
            pr_title="Title",
            pr_body="Body",
        )

    with pytest.raises(CuratorSandboxError):
        tools.close_superseded_pr("proposal/skill-old", "Consolidated")


def test_upsert_skill_proposal_pr_creates_and_updates_canonical_branch_in_place(
    sandbox_env: tuple[Path, Path], monkeypatch: pytest.MonkeyPatch
):
    project_dir, hub_dir = sandbox_env
    tools = CuratorSandboxTools(
        project_dir=project_dir, hub_dir=hub_dir, allow_hub_mutations=True
    )

    open_prs: list[dict[str, Any]] = []
    gh_calls: list[list[str]] = []

    monkeypatch.setattr(
        "shutil.which", lambda cmd: "/usr/bin/gh" if cmd == "gh" else None
    )

    class FakeProc:
        def __init__(self, returncode: int = 0, stdout: str = "", stderr: str = ""):
            self.returncode = returncode
            self.stdout = stdout
            self.stderr = stderr

    real_run = __import__("subprocess").run

    def fake_subprocess_run(cmd: list[str], *args: Any, **kwargs: Any) -> Any:
        if cmd and cmd[0] == "gh":
            gh_calls.append(cmd)
            if cmd[1:3] == ["auth", "status"]:
                return FakeProc(0, "Logged in")
            if cmd[1:3] == ["pr", "list"]:
                return FakeProc(0, json.dumps(open_prs))
            if cmd[1:3] == ["pr", "create"]:
                pr_url = "https://github.com/test/skills-hub/pull/101"
                open_prs.append(
                    {
                        "number": 101,
                        "headRefName": "proposal/skill-cli-tool-execution",
                        "title": "WikiSkill Proposal: cli-tool-execution",
                        "url": pr_url,
                    }
                )
                return FakeProc(0, pr_url)
            if cmd[1:3] == ["pr", "edit"]:
                return FakeProc(0, "https://github.com/test/skills-hub/pull/101")
            if cmd[1:3] == ["pr", "close"]:
                return FakeProc(0, "Closed")
        return real_run(cmd, *args, **kwargs)

    monkeypatch.setattr("subprocess.run", fake_subprocess_run)

    # 1. First upsert: no open PR -> creates canonical branch proposal/skill-cli-tool-execution and calls gh pr create
    res1 = tools.upsert_skill_proposal_pr(
        skill_name="cli-tool-execution",
        skill_md_content="---\nname: cli-tool-execution\ndescription: v2\npatterns_addressed:\n  - unprefixed-python-runner-loop\n  - cli-syntax-error-loop\n---\n\n# Operational Rules\n\n## Rules\n- Always use uv run.\n- Check --help.\n",
        purpose_md_content="# Purpose v2\n",
        patterns={"cli-syntax-error-loop": "# CLI Syntax Error Loop\n"},
        pr_title="WikiSkill Proposal: cli-tool-execution",
        pr_body="Initial consolidated proposal",
    )
    assert res1["branch"] == "proposal/skill-cli-tool-execution"
    assert res1["action"] == "created"
    assert res1["pr_url"] == "https://github.com/test/skills-hub/pull/101"
    assert any(c[1:3] == ["pr", "create"] for c in gh_calls)

    # 2. Second upsert for same skill: open PR exists -> updates canonical branch and calls gh pr edit in-place
    gh_calls.clear()
    res2 = tools.upsert_skill_proposal_pr(
        skill_name="cli-tool-execution",
        skill_md_content="---\nname: cli-tool-execution\ndescription: v3\npatterns_addressed:\n  - unprefixed-python-runner-loop\n  - cli-syntax-error-loop\n---\n\n# Operational Rules\n\n## Rules\n- Always use uv run.\n- Check --help.\n- Inspect subcommands.\n",
        purpose_md_content="# Purpose v3\n",
        patterns={"cli-syntax-error-loop": "# CLI Syntax Error Loop v3\n"},
        pr_title="WikiSkill Proposal: cli-tool-execution",
        pr_body="Updated consolidated proposal v3",
    )
    assert res2["branch"] == "proposal/skill-cli-tool-execution"
    assert res2["action"] == "updated"
    assert res2["pr_url"] == "https://github.com/test/skills-hub/pull/101"
    assert any(c[1:3] == ["pr", "edit"] for c in gh_calls)
    assert not any(c[1:3] == ["pr", "create"] for c in gh_calls)


def test_curator_agent_local_session_consolidates_and_cleans_unmerged_micro_skill(
    sandbox_env: tuple[Path, Path],
):
    project_dir, hub_dir = sandbox_env

    # Seed an unmerged redundant local micro-skill
    micro_skill = project_dir / ".agents" / "skills" / "cli-arg-helper"
    micro_skill.mkdir(parents=True)
    (micro_skill / "SKILL.md").write_text(
        "---\nname: cli-arg-helper\ndescription: Micro skill for CLI args\nstatus: active\npatterns_addressed:\n  - cli-syntax-error-loop\n---\n\n# Operational Rules\n\n## Rules\n- Check --help before running CLI subcommands.\n",
        encoding="utf-8",
    )

    def fake_react_runner(tools: CuratorSandboxTools, **kwargs: Any) -> dict[str, Any]:
        # Agent inspects local & hub skills, consolidates cli-arg-helper into cli-tool-execution, and deletes cli-arg-helper
        existing = tools.read_local_file("skills/cli-tool-execution/SKILL.md")
        assert "Always use uv run." in existing
        tools.write_local_file(
            "skills/cli-tool-execution/SKILL.md",
            "---\nname: cli-tool-execution\ndescription: Consolidated CLI rules\nstatus: active\norigin_session: sess-1\npatterns_addressed:\n  - unprefixed-python-runner-loop\n  - cli-syntax-error-loop\n---\n\n# Operational Rules\n\n## Rules\n- Always use uv run.\n- Check --help before running CLI subcommands.\n",
        )
        tools.delete_unmerged_local_skill("cli-arg-helper")
        return {
            "proposals": [
                {
                    "action": "update",
                    "name": "cli-tool-execution",
                    "description": "Consolidated CLI rules",
                    "status": "active",
                    "rules": [
                        "Always use uv run.",
                        "Check --help before running CLI subcommands.",
                    ],
                    "patterns_addressed": [
                        "unprefixed-python-runner-loop",
                        "cli-syntax-error-loop",
                    ],
                }
            ],
            "deleted_skills": ["cli-arg-helper"],
        }

    agent = WikiSkillCuratorAgent(
        project_dir=project_dir,
        hub_dir=hub_dir,
        react_runner=fake_react_runner,
    )
    res = agent.curate_local_session(
        session_id="sess-1",
        extracted_patterns=[
            {"name": "cli-syntax-error-loop", "content": "# CLI Syntax Error Loop\n"}
        ],
    )

    assert res["status"] == "success"
    assert not micro_skill.exists()
    updated_md = (
        project_dir / ".agents" / "skills" / "cli-tool-execution" / "SKILL.md"
    ).read_text(encoding="utf-8")
    assert "cli-syntax-error-loop" in updated_md
    assert "Check --help before running CLI subcommands." in updated_md


def test_cli_sync_push_preserves_local_skill_updates_without_clobbering_from_main(
    sandbox_env: tuple[Path, Path],
):
    project_dir, hub_dir = sandbox_env

    # Update existing skill locally in .agents/skills/cli-tool-execution/SKILL.md
    local_skill_md = (
        project_dir / ".agents" / "skills" / "cli-tool-execution" / "SKILL.md"
    )
    updated_content = "---\nname: cli-tool-execution\ndescription: Updated locally\nstatus: active\npatterns_addressed:\n  - unprefixed-python-runner-loop\n  - cli-syntax-error-loop\n---\n\n# Operational Rules\n\n## Rules\n- Always use uv run.\n- Check --help first.\n"
    local_skill_md.write_text(updated_content, encoding="utf-8")

    local_pat = (
        project_dir / ".agents" / "wiki" / "patterns" / "cli-syntax-error-loop.md"
    )
    local_pat.parent.mkdir(parents=True, exist_ok=True)
    local_pat.write_text(
        "# CLI Syntax Error Loop\n\n## Fix\nUse --help.\n", encoding="utf-8"
    )

    exit_code = main(
        [
            "sync",
            "--push",
            "--project-dir",
            str(project_dir),
            "--hub-dir",
            str(hub_dir),
        ]
    )
    assert exit_code == 0

    # Local skill must NOT be overwritten back to hub main's v1 content
    assert "Updated locally" in local_skill_md.read_text(encoding="utf-8")
    assert "Check --help first." in local_skill_md.read_text(encoding="utf-8")


def test_commitizen_bump_plugin_version():
    assert bump_plugin_version(None, "feat(skill): initial skill") == "1.0.0"
    assert bump_plugin_version("1.0.0", "fix(skill): refine rule") == "1.0.1"
    assert bump_plugin_version("1.0.1", "refactor(skill): clean up") == "1.0.2"
    assert bump_plugin_version("1.0.2", "feat(skill): add new capability") == "1.1.0"
    assert bump_plugin_version("1.1.0", "feat(skill)!: breaking change") == "2.0.0"
    assert (
        bump_plugin_version(
            "2.0.0", "feat(skill): change\n\nBREAKING CHANGE: drop old flag"
        )
        == "3.0.0"
    )


def test_group_marketplace_scaffolding_and_semver_bumping(
    sandbox_env: tuple[Path, Path], monkeypatch: pytest.MonkeyPatch
):
    project_dir, hub_dir = sandbox_env
    tools = CuratorSandboxTools(
        project_dir=project_dir, hub_dir=hub_dir, allow_hub_mutations=True
    )
    monkeypatch.setattr("shutil.which", lambda cmd: None)

    # 1. Create initial skill in 'ai-engineer' group -> version 1.0.0
    res1 = tools.upsert_skill_proposal_pr(
        skill_name="llm-configuration",
        skill_md_content="---\nname: llm-configuration\ndescription: LLM config rules\npatterns_addressed:\n  - llm-model-config-resolution-error\n---\n\n# Operational Rules\n\n## Rules\n- Set API key.\n",
        purpose_md_content="# Purpose\n",
        patterns={"llm-model-config-resolution-error": "# LLM Error\n"},
        pr_title="WikiSkill Proposal: llm-configuration",
        pr_body="Initial proposal",
        group="ai-engineer",
        commit_message="feat(skill): initial llm-configuration",
    )
    assert res1["version"] == "1.0.0"
    assert res1["group"] == "ai-engineer"

    # Merge proposal branch into main to simulate PR merge
    tools.sync_manager._run_git(["checkout", "main"])
    tools.sync_manager._run_git(["merge", res1["branch"]])

    assert (hub_dir / ".cz.toml").exists()
    plugin_json_path = (
        hub_dir
        / "groups"
        / "ai-engineer"
        / "plugins"
        / "llm-configuration"
        / "plugin.json"
    )
    claude_plugin_json_path = (
        hub_dir
        / "groups"
        / "ai-engineer"
        / "plugins"
        / "llm-configuration"
        / ".claude-plugin"
        / "plugin.json"
    )
    marketplace_path = hub_dir / ".claude-plugin" / "marketplace.json"
    group_skills_path = hub_dir / "groups" / "ai-engineer" / "skills.json"

    assert plugin_json_path.exists()
    assert claude_plugin_json_path.exists()
    assert marketplace_path.exists()
    assert group_skills_path.exists()

    p_data = json.loads(plugin_json_path.read_text(encoding="utf-8"))
    assert p_data["version"] == "1.0.0"
    assert p_data["group"] == "ai-engineer"

    m_data = json.loads(marketplace_path.read_text(encoding="utf-8"))
    entry = next(p for p in m_data["plugins"] if p["name"] == "llm-configuration")
    assert entry["version"] == "1.0.0"
    assert entry["category"] == "ai-engineer"
    assert entry["source"] == "./groups/ai-engineer/plugins/llm-configuration"

    # 2. Second upsert with 'fix(skill): ...' -> bumps PATCH to 1.0.1
    res2 = tools.upsert_skill_proposal_pr(
        skill_name="llm-configuration",
        skill_md_content="---\nname: llm-configuration\ndescription: LLM config rules v2\npatterns_addressed:\n  - llm-model-config-resolution-error\n---\n\n# Operational Rules\n\n## Rules\n- Set API key.\n- Check env var.\n",
        purpose_md_content="# Purpose v2\n",
        patterns={"llm-model-config-resolution-error": "# LLM Error\n"},
        pr_title="WikiSkill Proposal: llm-configuration",
        pr_body="Patch proposal",
        group="ai-engineer",
        commit_message="fix(skill): refine env var priority",
    )
    assert res2["version"] == "1.0.1"
    tools.sync_manager._run_git(["checkout", "main"])
    tools.sync_manager._run_git(["merge", res2["branch"]])

    # 3. Third upsert with 'feat(skill): ...' -> bumps MINOR to 1.1.0
    res3 = tools.upsert_skill_proposal_pr(
        skill_name="llm-configuration",
        skill_md_content="---\nname: llm-configuration\ndescription: LLM config rules v3\npatterns_addressed:\n  - llm-model-config-resolution-error\n---\n\n# Operational Rules\n\n## Rules\n- Set API key.\n- Check env var.\n- Support OpenRouter.\n",
        purpose_md_content="# Purpose v3\n",
        patterns={"llm-model-config-resolution-error": "# LLM Error\n"},
        pr_title="WikiSkill Proposal: llm-configuration",
        pr_body="Minor proposal",
        group="ai-engineer",
        commit_message="feat(skill): add openrouter fallback",
    )
    assert res3["version"] == "1.1.0"
    tools.sync_manager._run_git(["checkout", "main"])
    tools.sync_manager._run_git(["merge", res3["branch"]])

    m_data_v3 = json.loads(marketplace_path.read_text(encoding="utf-8"))
    entry_v3 = next(p for p in m_data_v3["plugins"] if p["name"] == "llm-configuration")
    assert entry_v3["version"] == "1.1.0"


def test_new_group_creation_and_zero_copy_workspace_group_subscription(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    hub_dir = tmp_path / "hub"
    sync_mgr = GitHubSyncManager(
        hub_dir=hub_dir, remote_url="https://github.com/test/skills-hub.git"
    )
    sync_mgr.init_hub()
    monkeypatch.setattr("shutil.which", lambda cmd: None)

    frontend_repo = tmp_path / "frontend_app"
    frontend_repo.mkdir()

    tools = CuratorSandboxTools(
        project_dir=frontend_repo, hub_dir=hub_dir, allow_hub_mutations=True
    )

    # Seed a skill in 'global' and a skill in 'frontend' and a skill in 'ai-engineer'
    for group_name, s_name in (
        ("global", "git-workflow"),
        ("frontend", "react-rendering"),
        ("ai-engineer", "llm-configuration"),
    ):
        res = tools.upsert_skill_proposal_pr(
            skill_name=s_name,
            skill_md_content=f"---\nname: {s_name}\ndescription: {s_name}\n---\n# Rules\n",
            purpose_md_content="# Purpose\n",
            patterns={},
            pr_title=f"Proposal: {s_name}",
            pr_body="Body",
            group=group_name,
            commit_message=f"feat(skill): add {s_name}",
        )
        tools.sync_manager._run_git(["checkout", "main"])
        tools.sync_manager._run_git(["merge", res["branch"]])

    groups_map = tools.list_hub_groups_and_plugins()
    assert "global" in groups_map
    assert "frontend" in groups_map
    assert "ai-engineer" in groups_map

    # Subscribe frontend_repo ONLY to 'frontend' (which automatically includes 'global')
    sub_res = tools.configure_workspace_groups(groups=["frontend"])
    assert sub_res["groups"] == ["global", "frontend"]

    ws_skills_json = frontend_repo / ".agents" / "skills.json"
    assert ws_skills_json.exists()
    ws_cfg = json.loads(ws_skills_json.read_text(encoding="utf-8"))
    inherited_paths = [item["path"] for item in ws_cfg["inherits"]]
    assert any(
        "groups/global/skills.json" in p.replace("\\", "/") for p in inherited_paths
    )
    assert any(
        "groups/frontend/skills.json" in p.replace("\\", "/") for p in inherited_paths
    )
    assert not any(
        "groups/ai-engineer/skills.json" in p.replace("\\", "/")
        for p in inherited_paths
    )
    # Zero SKILL.md files copied into frontend_repo
    assert list(frontend_repo.rglob("SKILL.md")) == []
