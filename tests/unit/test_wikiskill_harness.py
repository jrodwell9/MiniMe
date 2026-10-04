from pathlib import Path
from unittest.mock import patch

from wikiskill.harness import WikiSkillHarness
from wikiskill.models import SessionTrajectory, TrajectoryStep


@patch("wikiskill.adapters.claude.ClaudeCodeLogAdapter.get_latest_session_trajectory")
@patch("wikiskill.wiki_manager.WikiManager.call_llm_for_wiki_update")
@patch("wikiskill.wiki_manager.WikiManager.process_llm_wiki_response")
@patch("wikiskill.skill_proposer.SkillProposer.call_llm_for_skill_proposal")
@patch("wikiskill.skill_proposer.SkillProposer.apply_skill_proposal")
def test_harness_post_session_flow(
    mock_apply_skill,
    mock_skill_proposal,
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
        "create_patterns": [],
        "update_patterns": [],
        "update_index": {"additions": ["- Main test update"]},
        "append_log": "Main test log.",
    }
    mock_skill_proposal.return_value = [
        {
            "action": "create",
            "name": "main-test-skill",
            "description": "Test description",
            "rules": ["rule 1", "rule 2"],
            "patterns_addressed": ["test-pattern"],
        }
    ]

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
    mock_skill_proposal.assert_called_once()
    mock_apply_skill.assert_called_once()


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
