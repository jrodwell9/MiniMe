from unittest.mock import patch

from wikiskill.dataclasses import SessionTrajectory
from wikiskill.harness import WikiSkillHarness


@patch(
    "wikiskill.claude_log_adapter.ClaudeCodeLogAdapter.get_latest_session_trajectory"
)
@patch("wikiskill.wiki_manager.WikiManager.call_llm_for_wiki_update")
@patch("wikiskill.wiki_manager.WikiManager.process_llm_wiki_response")
@patch("wikiskill.skill_proposer.SkillProposer.call_llm_for_skill_proposal")
@patch("wikiskill.skill_proposer.SkillProposer.apply_skill_proposal")
@patch("wikiskill.wiki_manager.WikiManager._write_file")
def test_harness_post_session_flow(
    mock_write_file,
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
        steps=[],
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
