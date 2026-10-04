import json
import os
import time
from pathlib import Path
from typing import Any

from .harness import WikiSkillHarness
from .sync import GitHubSyncManager


class WikiSkillDaemon:
    def __init__(
        self,
        claude_dir: Path | str | None = None,
        hub_dir: Path | str | None = None,
        interval: int = 300,
    ):
        self.claude_dir = Path(os.path.expanduser(claude_dir or "~/.claude")).resolve()
        self.hub_dir = Path(
            os.path.expanduser(hub_dir or "~/.claude/wikiskill-hub")
        ).resolve()
        self.interval = interval
        self.state_file = self.hub_dir / ".processed_sessions.json"

        self.sync_manager = GitHubSyncManager(hub_dir=self.hub_dir)
        self.sync_manager.init_hub()

        self.processed_sessions: set[str] = self._load_state()

    def _load_state(self) -> set[str]:
        if self.state_file.exists():
            try:
                data = json.loads(self.state_file.read_text(encoding="utf-8"))
                if isinstance(data, list):
                    return set(data)
            except (json.JSONDecodeError, OSError):
                pass
        return set()

    def _save_state(self) -> None:
        try:
            self.state_file.parent.mkdir(parents=True, exist_ok=True)
            self.state_file.write_text(
                json.dumps(sorted(self.processed_sessions), indent=2),
                encoding="utf-8",
            )
        except OSError as e:
            print(f"Warning: Failed to save processed sessions state: {e}")

    def scan_and_process_sessions(self) -> list[dict[str, Any]]:
        """Scan all projects under ~/.claude/projects/ and process unhandled sessions."""
        projects_dir = self.claude_dir / "projects"
        if not projects_dir.exists() or not projects_dir.is_dir():
            return []

        processed_results: list[dict[str, Any]] = []

        for proj_folder in projects_dir.iterdir():
            if not proj_folder.is_dir():
                continue

            jsonl_files = list(proj_folder.glob("*.jsonl"))
            for jsonl_file in jsonl_files:
                session_id = jsonl_file.stem
                record_key = f"{proj_folder.name}/{session_id}"
                if (
                    record_key in self.processed_sessions
                    or session_id in self.processed_sessions
                ):
                    continue

                # Process this session
                try:
                    harness = WikiSkillHarness(
                        project_dir=self.hub_dir,
                        wiki_dir=self.hub_dir / "global" / "wiki",
                        skills_dir=self.hub_dir / "global" / "skills",
                        claude_dir=self.claude_dir,
                    )
                    harness.adapter.project_path = proj_folder

                    res = harness.run_post_session()
                    if res.get("status") in ("success", "clean_session"):
                        processed_results.append(
                            {
                                "session_id": session_id,
                                "project_slug": proj_folder.name,
                                "patterns": res.get("patterns_created", []),
                            }
                        )
                    self.processed_sessions.add(record_key)
                except (OSError, ValueError, KeyError, json.JSONDecodeError) as e:
                    print(
                        f"Error processing session {session_id} in {proj_folder.name}: {e}"
                    )
                    self.processed_sessions.add(record_key)

        if processed_results:
            self._save_state()

        return processed_results

    def run_loop(self, once: bool = False) -> None:
        """Run continuous monitoring loop."""
        print(
            f"Starting WikiSkill Daemon (monitoring: {self.claude_dir / 'projects'})..."
        )
        while True:
            results = self.scan_and_process_sessions()
            if results:
                print(f"Processed {len(results)} new session(s).")
            if once:
                break
            time.sleep(self.interval)
