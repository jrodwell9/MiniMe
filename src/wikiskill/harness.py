import os
from pathlib import Path
from typing import Any

from .adapters import AgentLogAdapter, AgentLogAdapterFactory, ClaudeCodeLogAdapter
from .curator import WikiSkillCuratorAgent
from .llm import WikiSkillLLMAdapter
from .sync import GitHubSyncManager, ensure_agent_links
from .wiki_manager import WikiManager


class WikiSkillHarness:
    def __init__(
        self,
        project_dir: str | Path | None = None,
        wiki_dir: str | Path | None = None,
        skills_dir: str | Path | None = None,
        claude_dir: str | Path | None = None,
        antigravity_dir: str | Path | None = None,
        hub_dir: str | Path | None = None,
        adapter: AgentLogAdapter | None = None,
        agent: str | None = None,
        llm_adapter: WikiSkillLLMAdapter | None = None,
        model: str | None = None,
        lm: Any | None = None,
        mock: bool = False,
        sync_before_run: bool = True,
        verbose: bool = False,
    ):
        self.project_dir = Path(project_dir or os.getcwd()).resolve()
        self._custom_dirs = bool(wiki_dir or skills_dir)
        self.wiki_dir = Path(
            wiki_dir or (self.project_dir / ".agents" / "wiki")
        ).resolve()
        self.skills_dir = Path(
            skills_dir or (self.project_dir / ".agents" / "skills")
        ).resolve()
        self.claude_dir = Path(os.path.expanduser(claude_dir or "~/.claude")).resolve()
        self.antigravity_dir = Path(
            os.path.expanduser(antigravity_dir or "~/.gemini/antigravity")
        ).resolve()
        self._explicit_hub_dir = bool(hub_dir)
        self.hub_dir = (
            Path(os.path.expanduser(hub_dir)).resolve()
            if hub_dir
            else (self.claude_dir / "wikiskill-hub").resolve()
        )
        self.mock = mock
        self.sync_before_run = sync_before_run
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

        self.llm_adapter = llm_adapter or WikiSkillLLMAdapter(
            model=model,
            lm=lm,
            mock=mock,
        )
        self.wiki_manager = WikiManager(
            base_path=str(self.wiki_dir),
            llm_adapter=self.llm_adapter,
            mock=self.llm_adapter.mock,
        )
        self.curator = WikiSkillCuratorAgent(
            project_dir=self.project_dir,
            hub_dir=self.hub_dir,
            skills_dir=self.skills_dir,
            wiki_dir=self.wiki_dir,
            llm_adapter=self.llm_adapter,
        )

    def init_project(self) -> dict[str, Any]:
        """Scaffold canonical .agents/wiki and .agents/skills directories and link .claude/ in target project."""
        if not self._custom_dirs:
            ensure_agent_links(self.project_dir)
        self.wiki_manager.initialize_wiki()
        self.skills_dir.mkdir(parents=True, exist_ok=True)
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
        if self.skills_dir.exists():
            skills = [
                s.name
                for s in self.skills_dir.iterdir()
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
        start_step: int = 0,
        dry_run: bool = False,
        sync_before_run: bool | None = None,
    ) -> dict[str, Any]:
        """Execute self-evolution loop on the session transcript."""
        if session_file is not None:
            trajectory = self.adapter.parse_session_file(
                Path(session_file), since=since, start_step=start_step
            )
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

        if not trajectory.steps:
            return {
                "status": "clean_session",
                "session_id": trajectory.session_id,
                "timestamp": trajectory.timestamp,
                "model": trajectory.model_routed,
                "steps_count": 0,
                "patterns_created": [],
                "patterns_updated": [],
                "proposals": [],
            }

        has_errors = any(s.is_error for s in trajectory.steps)
        effective_sync = (
            self.sync_before_run if sync_before_run is None else sync_before_run
        )

        if has_errors and not dry_run and not self._custom_dirs:
            ensure_agent_links(self.project_dir)

        if (
            has_errors
            and not dry_run
            and effective_sync
            and (not self._custom_dirs or self._explicit_hub_dir)
            and not self.llm_adapter.mock
            and (self.hub_dir / ".git").exists()
        ):
            try:
                sync_mgr = GitHubSyncManager(hub_dir=self.hub_dir)
                sync_mgr.pull()
                sync_mgr.sync_hub_to_project(self.project_dir)
            except (OSError, RuntimeError) as exc:
                if self.verbose:
                    print(f"Warning: Pre-consolidation hub sync failed: {exc}")

        # Stage 1: Wiki Maintainer processes session trajectory
        current_wiki_index = self.wiki_manager.get_wiki_index()
        llm_wiki_response = self.wiki_manager.call_llm_for_wiki_update(
            trajectory, current_wiki_index or ""
        )

        patterns_to_create = llm_wiki_response.get("create_patterns", [])
        patterns_to_update = llm_wiki_response.get("update_patterns", [])
        active_patterns = patterns_to_create + patterns_to_update

        if not dry_run and active_patterns:
            if not self._custom_dirs:
                ensure_agent_links(self.project_dir)
            self.wiki_manager.process_llm_wiki_response(llm_wiki_response)

        # Stage 2: Curator Sub-Agent consolidates patterns and skills inside .agents/
        curation_res = self.curator.curate_local_session(
            session_id=trajectory.session_id,
            extracted_patterns=active_patterns,
            dry_run=dry_run,
        )
        proposals = curation_res.get("proposals", [])

        if dry_run:
            return {
                "status": "dry_run",
                "session_id": trajectory.session_id,
                "timestamp": trajectory.timestamp,
                "model": trajectory.model_routed,
                "steps_count": len(trajectory.steps),
                "wiki_updates": llm_wiki_response,
                "proposals": proposals,
            }

        if not active_patterns and not proposals:
            return {
                "status": "clean_session",
                "session_id": trajectory.session_id,
                "timestamp": trajectory.timestamp,
                "model": trajectory.model_routed,
                "steps_count": len(trajectory.steps),
                "patterns_created": [],
                "patterns_updated": [],
                "proposals": [],
            }

        if not self._custom_dirs:
            ensure_agent_links(self.project_dir)

        if not active_patterns:
            self.wiki_manager.process_llm_wiki_response(llm_wiki_response)

        return {
            "status": "success",
            "session_id": trajectory.session_id,
            "timestamp": trajectory.timestamp,
            "model": trajectory.model_routed,
            "steps_count": len(trajectory.steps),
            "patterns_created": [p["name"] for p in patterns_to_create],
            "patterns_updated": [p["name"] for p in patterns_to_update],
            "proposals": proposals,
        }
