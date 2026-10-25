from pathlib import Path
from unittest.mock import patch

from wikiskill.harness import WikiSkillHarness
from wikiskill.models import SessionTrajectory, TrajectoryStep


@patch("wikiskill.adapters.claude.ClaudeCodeLogAdapter.get_latest_session_trajectory")
@patch("wikiskill.wiki_manager.WikiManager.call_llm_for_wiki_update")
@patch("wikiskill.wiki_manager.WikiManager.process_llm_wiki_response")
@patch("wikiskill.curator.WikiSkillCuratorAgent.curate_local_session")
def test_harness_post_session_flow(
    mock_curate_local,
    mock_process_wiki,
    mock_llm_wiki_update,
    mock_get_trajectory,
    tmp_path,
):
    mock_get_trajectory.return_value = SessionTrajectory(
        session_id="main-test-session",
        timestamp="2026-08-31T10:00:00Z",
        model_routed="claude-3-opus",
        steps=[
            TrajectoryStep(
                step_number=1,
                tool_name="Bash",
                tool_input={"command": "pytest"},
                observation="FAILED test",
                is_error=True,
            )
        ],
        final_status="success",
    )
    mock_llm_wiki_update.return_value = {
        "create_patterns": [{"name": "test-pattern", "content": "# Test Pattern"}],
        "update_patterns": [],
        "update_index": {"additions": ["- Main test update"]},
        "append_log": "Main test log.",
    }
    mock_curate_local.return_value = {
        "status": "success",
        "proposals": [
            {
                "action": "create",
                "name": "main-test-skill",
                "description": "Test description",
                "rules": ["rule 1", "rule 2"],
                "patterns_addressed": ["test-pattern"],
            }
        ],
        "deleted_skills": [],
    }

    wiki_path = tmp_path / ".claude" / "wiki"
    skills_path = tmp_path / ".claude" / "skills"

    harness = WikiSkillHarness(
        project_dir=str(tmp_path),
        wiki_dir=str(wiki_path),
        skills_dir=str(skills_path),
    )

    result = harness.run_post_session()

    assert result["status"] == "success"
    assert result["session_id"] == "main-test-session"
    assert len(result["proposals"]) == 1

    mock_get_trajectory.assert_called_once()
    mock_llm_wiki_update.assert_called_once()
    mock_process_wiki.assert_called_once()
    mock_curate_local.assert_called_once()


def test_harness_clean_session_does_not_create_skills_or_patterns(tmp_path: Path):
    wiki_path = tmp_path / ".claude" / "wiki"
    skills_path = tmp_path / ".claude" / "skills"

    harness = WikiSkillHarness(
        project_dir=str(tmp_path),
        wiki_dir=str(wiki_path),
        skills_dir=str(skills_path),
        mock=False,
    )
    harness.init_project()

    clean_trajectory = SessionTrajectory(
        session_id="clean-test-session-123",
        timestamp="2026-10-03T12:00:00Z",
        model_routed="claude-3-7-sonnet",
        steps=[
            TrajectoryStep(
                step_number=1,
                tool_name="Read",
                tool_input={"file_path": "main.py"},
                observation="print('clean')",
                is_error=False,
            )
        ],
    )

    with patch.object(
        harness.adapter, "get_latest_session_trajectory", return_value=clean_trajectory
    ):
        result = harness.run_post_session()

    assert result["status"] == "clean_session"
    assert result["patterns_created"] == []
    assert result["proposals"] == []

    # Verify no pattern markdown files were created
    pattern_files = list((wiki_path / "patterns").glob("*.md"))
    assert len(pattern_files) == 0

    # Verify no skill directories were created
    skill_dirs = [d for d in skills_path.iterdir() if d.is_dir()]
    assert len(skill_dirs) == 0


def test_harness_defaults_to_agents_dir_and_links_claude(tmp_path: Path):
    harness = WikiSkillHarness(project_dir=tmp_path, mock=True)
    assert harness.wiki_dir == (tmp_path / ".agents" / "wiki").resolve()
    assert harness.skills_dir == (tmp_path / ".agents" / "skills").resolve()

    harness.init_project()
    assert (tmp_path / ".agents" / "wiki" / "index.md").exists()
    assert (tmp_path / ".agents" / "skills").is_dir()
    # Provider-specific .claude/wiki and .claude/skills must resolve to .agents/
    assert (tmp_path / ".claude" / "wiki" / "index.md").exists()
    assert (tmp_path / ".claude" / "skills").exists()


def test_harness_syncs_hub_before_consolidation_and_forwards_update_patterns(
    tmp_path: Path,
):
    hub_dir = tmp_path / "hub"
    (hub_dir / ".git").mkdir(parents=True)

    harness = WikiSkillHarness(
        project_dir=tmp_path,
        hub_dir=hub_dir,
        mock=False,
        sync_before_run=True,
    )

    trajectory = SessionTrajectory(
        session_id="sess-sync-first",
        timestamp="2026-10-24T15:00:00Z",
        model_routed="claude-3-7-sonnet",
        steps=[
            TrajectoryStep(
                step_number=1,
                tool_name="Bash",
                tool_input={"command": "uv add --dry-run pkg"},
                observation="error: unexpected argument '--dry-run'",
                is_error=True,
            )
        ],
    )

    call_order: list[str] = []

    with (
        patch.object(
            harness.adapter, "get_latest_session_trajectory", return_value=trajectory
        ),
        patch("wikiskill.harness.GitHubSyncManager") as mock_sync_cls,
        patch.object(
            harness.wiki_manager,
            "call_llm_for_wiki_update",
            side_effect=lambda *a, **kw: (
                call_order.append("wiki_update")
                or {
                    "create_patterns": [],
                    "update_patterns": [
                        {
                            "name": "uv-dependency-resolution",
                            "content": "# UV Dependency Resolution",
                        }
                    ],
                    "update_index": {"additions": []},
                    "append_log": "Updated uv-dependency-resolution.",
                }
            ),
        ),
        patch.object(
            harness.curator,
            "curate_local_session",
            side_effect=lambda *a, **kw: (
                call_order.append("curate_local_session")
                or {
                    "status": "success",
                    "proposals": [
                        {
                            "action": "update",
                            "name": "dependency-management",
                            "description": "Updated",
                            "rules": ["Rule 1"],
                            "patterns_addressed": ["uv-dependency-resolution"],
                        }
                    ],
                    "deleted_skills": [],
                }
            ),
        ) as mock_curate,
    ):
        sync_instance = mock_sync_cls.return_value
        sync_instance.pull.side_effect = lambda *a, **kw: (
            call_order.append("hub_pull") or True
        )
        sync_instance.sync_hub_to_project.side_effect = lambda *a, **kw: (
            call_order.append("hub_sync_to_project")
            or {"status": "success", "applied_skills": ["dependency-management"]}
        )

        res = harness.run_post_session()

    assert res["status"] == "success"
    assert call_order == [
        "hub_pull",
        "hub_sync_to_project",
        "wiki_update",
        "curate_local_session",
    ]
    # Verify update_patterns were forwarded to curate_local_session
    curate_kwargs = mock_curate.call_args.kwargs
    assert curate_kwargs["extracted_patterns"] == [
        {
            "name": "uv-dependency-resolution",
            "content": "# UV Dependency Resolution",
        }
    ]
