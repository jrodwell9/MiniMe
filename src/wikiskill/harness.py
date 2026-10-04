import os
from pathlib import Path
from typing import Any

from .adapters import AgentLogAdapter, AgentLogAdapterFactory, ClaudeCodeLogAdapter
from .skill_proposer import SkillProposer
from .wiki_manager import WikiManager


class WikiSkillHarness:
    def __init__(
        self,
        project_dir: str | Path | None = None,
        wiki_dir: str | Path | None = None,
        skills_dir: str | Path | None = None,
        claude_dir: str | Path | None = None,
        antigravity_dir: str | Path | None = None,
        adapter: AgentLogAdapter | None = None,
        agent: str | None = None,
        mock: bool = False,
        verbose: bool = False,
    ):
        self.project_dir = Path(project_dir or os.getcwd()).resolve()
        self.wiki_dir = Path(
            wiki_dir or (self.project_dir / ".claude" / "wiki")
        ).resolve()
        self.skills_dir = Path(
            skills_dir or (self.project_dir / ".claude" / "skills")
        ).resolve()
        self.claude_dir = Path(os.path.expanduser(claude_dir or "~/.claude")).resolve()
        self.antigravity_dir = Path(
            os.path.expanduser(antigravity_dir or "~/.gemini/antigravity")
        ).resolve()
        self.mock = mock
        self.verbose = verbose

        projects_dir = self.claude_dir / "projects"
        mode = "mock" if mock else "auto"

        if adapter is not None:
            self.adapter = adapter
        elif claude_dir and not agent:
            # Preserve explicit claude directory targeting
            self.adapter = ClaudeCodeLogAdapter(
                projects_dir=projects_dir,
                project_path=self.project_dir,
                mode=mode,
            )
        else:
            self.adapter = AgentLogAdapterFactory.get_primary_adapter(
                agent_name=agent,
                project_path=self.project_dir,
                claude_dir=self.claude_dir,
                antigravity_dir=self.antigravity_dir,
                mode=mode,
            )

        self.wiki_manager = WikiManager(base_path=str(self.wiki_dir))
        self.skill_proposer = SkillProposer(base_path=str(self.skills_dir))

    def init_project(self) -> dict[str, Any]:
        """Scaffold .claude/wiki and .claude/skills directories in target project."""
        self.wiki_manager.initialize_wiki()
        self.skill_proposer.initialize_skills()
        return {
            "status": "success",
            "wiki_dir": str(self.wiki_dir),
            "skills_dir": str(self.skills_dir),
        }

    def get_status(self) -> dict[str, Any]:
        """Return active patterns, evolution logs, and skills."""
        index_content = self.wiki_manager.get_wiki_index() or ""
        patterns: list[str] = []
        pattern_dir = Path(self.wiki_manager.patterns_path)
        if pattern_dir.exists():
            patterns = [p.stem for p in pattern_dir.glob("*.md")]

        skills: list[str] = []
        skills_path = Path(self.skill_proposer.base_path)
        if skills_path.exists():
            skills = [
                s.name
                for s in skills_path.iterdir()
                if s.is_dir() and (s / "SKILL.md").exists()
            ]

        return {
            "project_dir": str(self.project_dir),
            "wiki_dir": str(self.wiki_dir),
            "skills_dir": str(self.skills_dir),
            "patterns": patterns,
            "skills": skills,
            "index_summary": index_content.strip(),
        }

    def run_post_session(
        self,
        since: str | None = None,
        session_file: Path | str | None = None,
        dry_run: bool = False,
    ) -> dict[str, Any]:
        """Execute self-evolution loop on the session transcript."""
        if session_file is not None:
            trajectory = self.adapter.parse_session_file(Path(session_file))
        else:
            trajectory = self.adapter.get_latest_session_trajectory(since=since)

        if not trajectory:
            return {
                "status": "no_session",
                "message": "No session trajectory found to process.",
            }

        if self.verbose:
            print(
                f"Processing session ID: {trajectory.session_id} "
                f"(model: {trajectory.model_routed}, steps: {len(trajectory.steps)})"
            )

        # Step 1: Wiki Maintainer processes session trajectory
        current_wiki_index = self.wiki_manager.get_wiki_index()
        llm_wiki_response = self.wiki_manager.call_llm_for_wiki_update(
            trajectory, current_wiki_index or ""
        )

        patterns_to_create = llm_wiki_response.get("create_patterns", [])

        # Step 2: Skill Proposer proposes skill edits based on updated wiki state
        updated_wiki_context = (
            f"Index: {self.wiki_manager.get_wiki_index() or 'N/A'}\n"
            f"Skill Impact: {self.wiki_manager.get_skill_impact_log() or 'N/A'}"
        )
        proposals = self.skill_proposer.call_llm_for_skill_proposal(
            updated_wiki_context,
            patterns=patterns_to_create,
        )

        if dry_run:
            return {
                "status": "dry_run",
                "session_id": trajectory.session_id,
                "model": trajectory.model_routed,
                "steps_count": len(trajectory.steps),
                "wiki_updates": llm_wiki_response,
                "proposals": proposals,
            }

        # If clean session with 0 new patterns and 0 proposals, exit cleanly without writing dummy files
        if not patterns_to_create and not proposals:
            return {
                "status": "clean_session",
                "session_id": trajectory.session_id,
                "model": trajectory.model_routed,
                "steps_count": len(trajectory.steps),
                "patterns_created": [],
                "proposals": [],
            }

        # Apply Wiki updates
        self.wiki_manager.process_llm_wiki_response(llm_wiki_response)

        # Step 3: Apply skills with frontmatter metadata
        for proposal in proposals:
            self.skill_proposer.apply_skill_proposal(
                proposal, session_id=trajectory.session_id
            )

        return {
            "status": "success",
            "session_id": trajectory.session_id,
            "model": trajectory.model_routed,
            "steps_count": len(trajectory.steps),
            "patterns_created": [p["name"] for p in patterns_to_create],
            "proposals": proposals,
        }
