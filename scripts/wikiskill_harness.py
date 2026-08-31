import argparse
import sys
from pathlib import Path

# Ensure workspace and parent directories are in sys.path when invoked directly
_workspace_root = Path(__file__).resolve().parent.parent
_parent_root = _workspace_root.parent
for _p in (_workspace_root, _parent_root):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

from MiniMe.scripts.claude_log_adapter import ClaudeCodeLogAdapter
from MiniMe.scripts.skill_proposer import SkillProposer
from MiniMe.scripts.wiki_manager import WikiManager

if __name__ == "__main__":
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
        adapter = ClaudeCodeLogAdapter()
        trajectory = adapter.get_latest_session_trajectory(since=args.since)

        wiki_manager = WikiManager()
        skill_proposer = SkillProposer()

        if trajectory:
            print(
                f"Processing session ID: {trajectory.session_id} (model: {trajectory.model_routed}, steps: {len(trajectory.steps)})"
            )
            # Step 1: Wiki Maintainer processes session trajectory
            current_wiki_index = wiki_manager.get_wiki_index()
            llm_wiki_response = wiki_manager.call_llm_for_wiki_update(
                trajectory, current_wiki_index or ""
            )
            wiki_manager.process_llm_wiki_response(llm_wiki_response)

            # Step 2: Skill Proposer proposes skill edits based on updated wiki state
            updated_wiki_context = (
                f"Index: {wiki_manager.get_wiki_index() or 'N/A'}\n"
                f"Skill Impact: {wiki_manager.get_skill_impact_log() or 'N/A'}"
            )
            proposals = skill_proposer.call_llm_for_skill_proposal(
                updated_wiki_context,
                patterns=llm_wiki_response.get("create_patterns"),
            )

            # Step 3: Apply skills and audit log
            for proposal in proposals:
                skill_proposer.apply_skill_proposal(proposal)

                # Format audit log entry
                rules_list = "\n".join(f"  + {r}" for r in proposal.get("rules", []))
                impact_entry = f"""
## Session {trajectory.session_id}
- Target Skill: `{proposal["name"]}`
- Proposal Action: `{proposal["action"]}`
- Patterns Addressed: {", ".join(proposal.get("patterns_addressed", []))}
- Acceptance Outcome: Accepted
- Rules Applied:
```markdown
{rules_list}
```
"""
                wiki_manager._write_file(
                    wiki_manager.skill_impact_path, impact_entry, mode="a"
                )
                print(
                    f"Appended proposal for '{proposal['name']}' to {wiki_manager.skill_impact_path}"
                )

        else:
            print("No session trajectory found to process.")
    else:
        print("No --post-session argument found. Exiting.")
