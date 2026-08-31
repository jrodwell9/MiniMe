import argparse
import json
import os

from .ccr_log_adapter import CCRLogAdapter
from .skill_proposer import SkillProposer
from .sqlite_mock_db import create_mock_sqlite_db
from .wiki_manager import WikiManager

if __name__ == "__main__":
    # Main harness logic
    parser = argparse.ArgumentParser(description="WikiSkill Harness.")
    parser.add_argument(
        "--post-session", action="store_true", help="Run after a session ends."
    )
    parser.add_argument(
        "--since",
        type=str,
        help="Process sessions since a specific timestamp (YYYY-MM-DDTHH:MM:SSZ).",
    )
    args = parser.parse_args()

    if args.post_session:
        print("Running in --post-session mode.")
        # In a real scenario, this would get the latest session from CCR
        # For now, we set up a mock SQLite DB and use it
        sqlite_db_path = os.path.expanduser("~/.claude-code-router/logs.db")
        if not os.path.exists(sqlite_db_path):
            os.makedirs(os.path.dirname(sqlite_db_path), exist_ok=True)
            create_mock_sqlite_db(sqlite_db_path)

        adapter = CCRLogAdapter(ccr_log_source="sqlite", db_path=sqlite_db_path)

        trajectory = adapter.get_latest_session_trajectory()

        wiki_manager = WikiManager()
        skill_proposer = SkillProposer()

        if trajectory:
            print(f"Processing session ID: {trajectory.session_id} from SQLite")
            # Step 1: Wiki Maintainer processes session trajectory
            current_wiki_index = wiki_manager.get_wiki_index()
            llm_wiki_response = wiki_manager.call_llm_for_wiki_update(
                trajectory, current_wiki_index or ""
            )
            wiki_manager.process_llm_wiki_response(llm_wiki_response)

            # Step 2: Skill Proposer proposes skill edits based on updated wiki state
            updated_wiki_context = f"Index: {wiki_manager.get_wiki_index() or 'N/A'}\nSkill Impact: {wiki_manager.get_skill_impact_log() or 'N/A'}"
            skill_proposal_response = skill_proposer.call_llm_for_skill_proposal(
                updated_wiki_context
            )

            # Step 3: Implement GitHub PR creation (mocked for now)
            print("\nSimulating GitHub PR creation for skill proposal:")
            print(json.dumps(skill_proposal_response, indent=2))
            # In a real scenario, this would involve:
            # - Creating a new branch
            # - Applying the edits from skill_proposal_response["edits"]
            # - Committing the changes
            # - Creating a pull request

            # Step 4: Audit logging (mocked acceptance for now)
            # This would typically happen after PR acceptance/rejection
            impact_entry = (
                f"## Session {trajectory.session_id}\n"
                f"- Target Skill: {skill_proposal_response['name']}\n"
                f"- Proposal Action: {skill_proposal_response['action']}\n"
                f"- Acceptance Outcome: Accepted (Mock)\n"
                f"- Diff: ```diff\n"
                f"  # Mock diff based on proposed edits\n"
                f"  {skill_proposal_response['edits'][0]['old_string']}\n"
                f"  {skill_proposal_response['edits'][0]['new_string']}\n"
                f"```\n"
            )
            wiki_manager._write_file(
                wiki_manager.skill_impact_path, impact_entry, mode="a"
            )
            print(f"Appended to skill impact log: {wiki_manager.skill_impact_path}")

        else:
            print("No session trajectory found to process.")
    else:
        print("No --post-session argument found. Exiting.")
