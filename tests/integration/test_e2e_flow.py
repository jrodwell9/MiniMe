import json
from pathlib import Path

from wikiskill import (
    GitHubSyncManager,
    WikiSkillHarness,
    WikiSkillLLMAdapter,
    sanitize_project_path,
)


def test_e2e_full_lifecycle(tmp_path: Path):
    """End-to-end integration test validating the entire WikiSkill lifecycle.

    1. Scaffolds a project workspace with .claude/wiki and .claude/skills.
    2. Simulates a Claude Code session with tool errors.
    3. Runs the post-session evolution loop to extract patterns and propose skills.
    4. Syncs the workspace knowledge into a central Hub.
    5. Verifies skill files, purpose definitions, and patterns on disk.
    """
    # 1. Workspace Scaffolding
    sandbox_repo = tmp_path / "my_demo_app"
    sandbox_repo.mkdir()
    (sandbox_repo / "app.py").write_text("def hello():\n    print('Hello World')\n")

    harness = WikiSkillHarness(
        project_dir=sandbox_repo,
        claude_dir=tmp_path / ".claude",
        llm_adapter=WikiSkillLLMAdapter(mock=True),
    )
    harness.init_project()

    assert (sandbox_repo / ".claude" / "wiki" / "index.md").exists()
    assert (sandbox_repo / ".claude" / "wiki" / "patterns").is_dir()
    assert (sandbox_repo / ".claude" / "skills").is_dir()

    # 2. Simulate Claude Code session with failure patterns
    claude_projects_dir = tmp_path / ".claude" / "projects"
    slug = sanitize_project_path(sandbox_repo)
    project_claude_dir = claude_projects_dir / slug
    project_claude_dir.mkdir(parents=True)

    session_id = "e2e-session-9876"
    session_file = project_claude_dir / f"{session_id}.jsonl"

    lines = [
        {"type": "mode", "sessionId": session_id},
        # Turn 1: Edit failed due to string mismatch
        {
            "type": "assistant",
            "message": {
                "content": [
                    {
                        "type": "tool_use",
                        "id": "call_1",
                        "name": "Edit",
                        "input": {
                            "file_path": "app.py",
                            "old_string": "def wrong_func():",
                            "new_string": "def hello():",
                        },
                    }
                ]
            },
        },
        {
            "type": "user",
            "message": {
                "content": [
                    {
                        "type": "tool_result",
                        "tool_use_id": "call_1",
                        "content": "Error: old_string not found in file content",
                        "is_error": True,
                    }
                ]
            },
        },
        # Turn 2: Bash execution failed due to python prefix missing
        {
            "type": "assistant",
            "message": {
                "content": [
                    {
                        "type": "tool_use",
                        "id": "call_2",
                        "name": "Bash",
                        "input": {"command": "pytest tests/"},
                    }
                ]
            },
        },
        {
            "type": "user",
            "message": {
                "content": [
                    {
                        "type": "tool_result",
                        "tool_use_id": "call_2",
                        "content": "bash: pytest: command not found (did you mean 'uv run pytest'?)",
                        "is_error": True,
                    }
                ]
            },
        },
    ]

    with open(session_file, "w", encoding="utf-8") as f:
        f.writelines(json.dumps(entry) + "\n" for entry in lines)

    assert session_file.exists()

    # 3. Execute Post-Session Evolution
    res = harness.run_post_session(
        dry_run=False,
    )

    assert res["status"] == "success"
    assert len(res["patterns_created"]) >= 2
    assert "edit-string-mismatch-loop" in res["patterns_created"]
    assert "unprefixed-python-runner-loop" in res["patterns_created"]
    proposed_skill_names = [p["name"] for p in res["proposals"]]
    assert len(proposed_skill_names) >= 2
    assert "file-editing" in proposed_skill_names
    assert "cli-tool-execution" in proposed_skill_names

    # Verify pattern files on disk
    p_file = (
        sandbox_repo / ".claude" / "wiki" / "patterns" / "edit-string-mismatch-loop.md"
    )
    assert p_file.exists()
    p_content = p_file.read_text(encoding="utf-8")
    assert "Edit String Mismatch Loop" in p_content

    # Verify skill file with frontmatter linking
    s_file = sandbox_repo / ".claude" / "skills" / "file-editing" / "SKILL.md"
    assert s_file.exists()
    s_content = s_file.read_text(encoding="utf-8")
    assert "patterns_addressed" in s_content
    assert "edit-string-mismatch-loop" in s_content

    # 4. Central Hub Synchronization
    hub_dir = tmp_path / "central_hub"
    sync_manager = GitHubSyncManager(hub_dir=hub_dir)
    sync_manager.init_hub()
    sync_res = sync_manager.sync_project_to_hub(sandbox_repo)

    assert sync_res["status"] == "success"
    assert "edit-string-mismatch-loop" in sync_res["synced_patterns"]
    assert "file-editing" in sync_res["synced_skills"]

    # Verify global promotion in hub
    hub_patterns = list((hub_dir / "global" / "wiki" / "patterns").glob("*.md"))
    assert len(hub_patterns) >= 2

    # 5. Status inspection
    status_res = harness.get_status()
    assert len(status_res["patterns"]) >= 2
    assert "edit-string-mismatch-loop" in status_res["patterns"]
    assert "file-editing" in status_res["skills"]
    assert "cli-tool-execution" in status_res["skills"]

    # 6. Verify skill purpose and rules files
    fe_purpose = sandbox_repo / ".claude" / "skills" / "file-editing" / "PURPOSE.md"
    assert fe_purpose.exists()
    assert "edit-string-mismatch-loop" in fe_purpose.read_text(encoding="utf-8")
