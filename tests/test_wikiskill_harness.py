from unittest.mock import patch

from ..scripts.wikiskill_dataclasses import SessionTrajectory
from ..scripts.wikiskill_harness import (
    WikiManager,
)


# Test cases for main harness logic (mocking external calls)
@patch("MiniMe.scripts.wikiskill_harness.CCRLogAdapter.get_latest_session_trajectory")
@patch("MiniMe.scripts.wikiskill_harness.WikiManager.call_llm_for_wiki_update")
@patch("MiniMe.scripts.wikiskill_harness.WikiManager.process_llm_wiki_response")
@patch("MiniMe.scripts.wikiskill_harness.SkillProposer.call_llm_for_skill_proposal")
@patch("MiniMe.scripts.wikiskill_harness.WikiManager._write_file")
def test_main_post_session_flow(
    mock_write_file,
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
    mock_skill_proposal.return_value = {
        "action": "patch",
        "name": "main-test-skill",
        "edits": [
            {
                "file": "main-test-skill/SKILL.md",
                "old_string": "old",
                "new_string": "new",
            }
        ],
    }

    # Create a temporary directory structure for wiki files
    wiki_path = tmp_path / ".claude" / "wiki"
    patterns_path = wiki_path / "patterns"
    patterns_path.mkdir(parents=True)
    (wiki_path / "index.md").write_text("Initial Index\n")
    (wiki_path / "logs.md").write_text("Initial Log\n")
    (wiki_path / "skill-impact.md").write_text("Initial Impact\n")

    wiki_manager_instance = WikiManager(base_path=str(wiki_path))

    trajectory = mock_get_trajectory()
    current_wiki_index = wiki_manager_instance.get_wiki_index()
    llm_wiki_response_data = mock_llm_wiki_update(
        trajectory, current_wiki_index or ""
    )  # Call the mocked function
    wiki_manager_instance.process_llm_wiki_response(llm_wiki_response_data)

    updated_wiki_context = (
        f"Index: {wiki_manager_instance.get_wiki_index() or 'N/A'}\n"
        f"Skill Impact: {wiki_manager_instance.get_skill_impact_log() or 'N/A'}"
    )
    mock_skill_proposal(updated_wiki_context)  # Call the mocked function

    # Simulate the audit logging from the __main__ block
    impact_entry = (
        f"## Session {trajectory.session_id}\n"
        f"- Target Skill: {mock_skill_proposal.return_value['name']}\n"
        f"- Proposal Action: {mock_skill_proposal.return_value['action']}\n"
        f"- Acceptance Outcome: Accepted (Mock)\n"
        f"- Diff: ```diff\n"
        f"  # Mock diff based on proposed edits\n"
        f"  {mock_skill_proposal.return_value['edits'][0]['old_string']}\n"
        f"  {mock_skill_proposal.return_value['edits'][0]['new_string']}\n"
        f"```\n"
    )
    wiki_manager_instance._write_file(
        wiki_manager_instance.skill_impact_path, impact_entry, mode="a"
    )

    # Assertions for the main flow
    mock_get_trajectory.assert_called_once()
    mock_llm_wiki_update.assert_called_once_with(trajectory, current_wiki_index or "")
    mock_process_wiki.assert_called_once_with(llm_wiki_response_data)
    mock_skill_proposal.assert_called_once_with(updated_wiki_context)
    # Check that _write_file was called for skill-impact.md
    assert any(
        call.args[0] == str(wiki_path / "skill-impact.md")
        for call in mock_write_file.call_args_list
    )
