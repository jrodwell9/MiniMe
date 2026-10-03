"""
End-to-End Demonstration Script for WikiSkill.
Demonstrates:
1. Workspace Scaffolding
2. Simulating a Claude Code session with real execution errors
3. Automatic post-session pattern consolidation & skill generation
4. Synchronization with the Central Hub (~/.claude/wikiskill-hub)
5. MCP sidecar query & in-flight reflection capture
"""

import json
import shutil
import tempfile
from pathlib import Path

from wikiskill import (
    GitHubSyncManager,
    WikiSkillHarness,
    get_active_skills,
    lookup_pattern,
    record_reflection,
    sanitize_project_path,
)


def print_step(title: str):
    print("\n" + "=" * 70)
    print(f"  {title}")
    print("=" * 70)


def main():
    temp_dir = Path(tempfile.mkdtemp(prefix="wikiskill_e2e_")).resolve()
    print_step(f"1. Setting up Sandbox Workspace: {temp_dir}")

    sandbox_repo = temp_dir / "my_demo_app"
    sandbox_repo.mkdir()
    (sandbox_repo / "app.py").write_text("def hello():\n    print('Hello World')\n")
    print(f"[+] Created sample repo at: {sandbox_repo}")

    # Initialize WikiSkill directories in sandbox repo
    harness = WikiSkillHarness(project_dir=sandbox_repo)
    harness.init_project()
    print("[+] Initialized .claude/wiki and .claude/skills in sandbox")

    # Step 2: Simulate Claude Code session transcript
    print_step("2. Simulating Claude Code Session with Failure Patterns")
    claude_projects_dir = temp_dir / ".claude" / "projects"
    slug = sanitize_project_path(sandbox_repo)
    project_claude_dir = claude_projects_dir / slug
    project_claude_dir.mkdir(parents=True)

    session_id = "demo-session-9876"
    session_file = project_claude_dir / f"{session_id}.jsonl"

    lines = [
        {"type": "mode", "sessionId": session_id},
        # Turn 1: Edit failed due to string mismatch
        {
            "type": "assistant",
            "message": {
                "role": "assistant",
                "model": "claude-3-7-sonnet",
                "content": [
                    {
                        "type": "tool_use",
                        "id": "call_1",
                        "name": "Edit",
                        "input": {"file_path": "app.py", "old_string": "def hello():\r\n    wrong whitespace"},
                    }
                ],
            },
        },
        {
            "type": "user",
            "message": {
                "role": "user",
                "content": [
                    {
                        "type": "tool_result",
                        "tool_use_id": "call_1",
                        "content": "<tool_use_error>String to replace not found in file.",
                        "is_error": True,
                    }
                ],
            },
        },
        # Turn 2: Bash failed because command ran bare instead of with uv run
        {
            "type": "assistant",
            "message": {
                "role": "assistant",
                "model": "claude-3-7-sonnet",
                "content": [
                    {
                        "type": "tool_use",
                        "id": "call_2",
                        "name": "Bash",
                        "input": {"command": "pytest"},
                    }
                ],
            },
        },
        {
            "type": "user",
            "message": {
                "role": "user",
                "content": [
                    {
                        "type": "tool_result",
                        "tool_use_id": "call_2",
                        "content": "Exit code 127\n/usr/bin/bash: line 1: pytest: command not found",
                        "is_error": True,
                    }
                ],
            },
        },
    ]

    with open(session_file, "w", encoding="utf-8") as f:
        f.writelines(json.dumps(line) + "\n" for line in lines)
    print(f"[+] Written simulated session log with 2 errors to: {session_file.name}")

    # Step 3: Run WikiSkill Evolution Harness
    print_step("3. Running Post-Session Evolution Harness")
    sandbox_harness = WikiSkillHarness(
        project_dir=sandbox_repo,
        claude_dir=temp_dir / ".claude",
        verbose=True,
    )
    result = sandbox_harness.run_post_session()
    print(f"[+] Result Status: {result['status']}")
    print(f"[+] Patterns Extracted: {result['patterns_created']}")
    print(f"[+] Skills Applied: {[p['name'] for p in result['proposals']]}")

    # Inspect generated files
    print("\n--- Generated Pattern (.claude/wiki/patterns/edit-string-mismatch-loop.md) ---")
    p_file = sandbox_repo / ".claude" / "wiki" / "patterns" / "edit-string-mismatch-loop.md"
    if p_file.exists():
        print(p_file.read_text(encoding="utf-8"))

    print("--- Generated Skill (.claude/skills/file-editing/SKILL.md) ---")
    s_file = sandbox_repo / ".claude" / "skills" / "file-editing" / "SKILL.md"
    if s_file.exists():
        print(s_file.read_text(encoding="utf-8"))

    # Step 4: Central Hub Synchronization
    print_step("4. Synchronizing Sandbox Knowledge into Central Hub")
    hub_dir = temp_dir / "central_hub"
    sync_manager = GitHubSyncManager(hub_dir=hub_dir)
    sync_manager.init_hub()
    sync_res = sync_manager.sync_project_to_hub(sandbox_repo)
    print(f"[+] Synced Project Slug: {sync_res['project_slug']}")
    print(f"[+] Synced Patterns to Hub: {sync_res['synced_patterns']}")
    print(f"[+] Promoted Global Patterns: {[f.stem for f in (hub_dir / 'global' / 'wiki' / 'patterns').glob('*.md')]}")

    # Step 5: Test MCP Sidecar Queries
    print_step("5. Querying Knowledge via MCP Sidecar Tools")
    # 5a: Lookup pattern
    lookup_res = lookup_pattern("edit string mismatch", project_dir=str(sandbox_repo))
    print("[+] MCP lookup_pattern('edit string mismatch'):")
    print(json.dumps(lookup_res, indent=2))

    # 5b: Get active skills
    skills_res = get_active_skills(project_dir=str(sandbox_repo))
    print(f"\n[+] MCP get_active_skills() found {len(skills_res['skills'])} active skills:")
    for sk in skills_res['skills']:
        print(f"    - Skill '{sk['name']}': {sk['path']}")

    # 5c: Record in-flight reflection
    print("\n[+] MCP record_reflection(...) recording real-time insight:")
    refl_res = record_reflection(
        summary="Missing requirements lockfile on fresh clone",
        error_encountered="uv.lock missing on new machine clone",
        fix_applied="Always run 'uv sync' before executing tests on clean checkout",
        project_dir=str(sandbox_repo),
    )
    print(json.dumps(refl_res, indent=2))

    # Clean up temp sandbox
    shutil.rmtree(temp_dir, ignore_errors=True)
    print_step("End-to-End Demonstration Complete: Cleaned up temporary sandbox")


if __name__ == "__main__":
    main()

