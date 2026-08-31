from unittest.mock import patch

from ..scripts.wikiskill_dataclasses import SessionTrajectory
from ..scripts.wikiskill_harness import (
    SkillProposer,
    WikiManager,
)


# Test cases for main harness logic (mocking external calls)
@patch(
    "MiniMe.scripts.wikiskill_harness.ClaudeCodeLogAdapter.get_latest_session_trajectory"
)
@patch("MiniMe.scripts.wikiskill_harness.WikiManager.call_llm_for_wiki_update")
@patch("MiniMe.scripts.wikiskill_harness.WikiManager.process_llm_wiki_response")
@patch("MiniMe.scripts.wikiskill_harness.SkillProposer.call_llm_for_skill_proposal")
@patch("MiniMe.scripts.wikiskill_harness.SkillProposer.apply_skill_proposal")
@patch("MiniMe.scripts.wikiskill_harness.WikiManager._write_file")
def test_main_post_session_flow(
    mock_write_file,
    mock_apply_skill,
    mock_skill_proposal,
    mock_process_wiki,
    mock_llm_wiki_update,
    mock_get_trajectory,
    tmp_path,
):
    # Setup mocks
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

    # Create a temporary directory structure for wiki and skills
    wiki_path = tmp_path / ".claude" / "wiki"
    patterns_path = wiki_path / "patterns"
    patterns_path.mkdir(parents=True)
    (wiki_path / "index.md").write_text("Initial Index\n")
    (wiki_path / "logs.md").write_text("Initial Log\n")
    (wiki_path / "skill-impact.md").write_text("Initial Impact\n")

    skills_path = tmp_path / ".claude" / "skills"
    skills_path.mkdir(parents=True)

    wiki_manager_instance = WikiManager(base_path=str(wiki_path))
    skill_proposer_instance = SkillProposer(base_path=str(skills_path))

    trajectory = mock_get_trajectory()
    current_wiki_index = wiki_manager_instance.get_wiki_index()
    llm_wiki_response_data = mock_llm_wiki_update(trajectory, current_wiki_index or "")
    wiki_manager_instance.process_llm_wiki_response(llm_wiki_response_data)

    updated_wiki_context = (
        f"Index: {wiki_manager_instance.get_wiki_index() or 'N/A'}\n"
        f"Skill Impact: {wiki_manager_instance.get_skill_impact_log() or 'N/A'}"
    )
    proposals = mock_skill_proposal(
        updated_wiki_context, patterns=llm_wiki_response_data.get("create_patterns")
    )

    for proposal in proposals:
        skill_proposer_instance.apply_skill_proposal(proposal)
        impact_entry = f"## Session {trajectory.session_id}\n- Target Skill: `{proposal['name']}`\n"
        wiki_manager_instance._write_file(
            wiki_manager_instance.skill_impact_path, impact_entry, mode="a"
        )

    # Assertions for the main flow
    mock_get_trajectory.assert_called_once()
    mock_llm_wiki_update.assert_called_once_with(trajectory, current_wiki_index or "")
    mock_process_wiki.assert_called_once_with(llm_wiki_response_data)
    mock_skill_proposal.assert_called_once_with(
        updated_wiki_context, patterns=llm_wiki_response_data.get("create_patterns")
    )
    assert any(
        call.args[0] == str(wiki_path / "skill-impact.md")
        for call in mock_write_file.call_args_list
    )
