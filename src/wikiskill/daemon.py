import json
import os
import time
from pathlib import Path
from typing import Any

from .adapters import AgentLogAdapter, AgentLogAdapterFactory, ClaudeCodeLogAdapter
from .harness import WikiSkillHarness
from .sync import GitHubSyncManager


class WikiSkillDaemon:
    def __init__(
        self,
        claude_dir: Path | str | None = None,
        antigravity_dir: Path | str | None = None,
        hub_dir: Path | str | None = None,
        interval: int = 300,
        adapters: list[AgentLogAdapter] | None = None,
    ):
        self.claude_dir = Path(os.path.expanduser(claude_dir or "~/.claude")).resolve()
        self.antigravity_dir = Path(
            os.path.expanduser(antigravity_dir or "~/.gemini/antigravity")
        ).resolve()
        self.hub_dir = Path(
            os.path.expanduser(hub_dir or "~/.claude/wikiskill-hub")
        ).resolve()
        self.interval = interval
        self.state_file = self.hub_dir / ".processed_sessions.json"

        self.sync_manager = GitHubSyncManager(hub_dir=self.hub_dir)
        self.sync_manager.init_hub()

        self.processed_sessions: dict[str, Any] = self._load_state()

        if adapters is not None:
            self.adapters = adapters
        elif claude_dir and not antigravity_dir:
            self.adapters = [
                ClaudeCodeLogAdapter(
                    claude_dir=self.claude_dir,
                    projects_dir=self.claude_dir / "projects",
                )
            ]
        else:
            detected = AgentLogAdapterFactory.detect_available_adapters(
                claude_dir=self.claude_dir,
                antigravity_dir=self.antigravity_dir,
            )
            if detected:
                self.adapters = detected
            else:
                self.adapters = [
                    ClaudeCodeLogAdapter(
                        claude_dir=self.claude_dir,
                        projects_dir=self.claude_dir / "projects",
                    )
                ]

    def _load_state(self) -> dict[str, Any]:
        if self.state_file.exists():
            try:
                data = json.loads(self.state_file.read_text(encoding="utf-8"))
                if isinstance(data, dict):
                    return data
                if isinstance(data, list):
                    return {k: {"mtime": 0.0, "step_count": 0} for k in data}
            except (json.JSONDecodeError, OSError):
                pass
        return {}

    def _save_state(self) -> None:
        try:
            self.state_file.parent.mkdir(parents=True, exist_ok=True)
            self.state_file.write_text(
                json.dumps(self.processed_sessions, indent=2),
                encoding="utf-8",
            )
        except OSError as e:
            print(f"Warning: Failed to save processed sessions state: {e}")

    def scan_and_process_sessions(self) -> list[dict[str, Any]]:
        """Scan all detected agent environments and process unhandled or updated sessions."""
        processed_results: list[dict[str, Any]] = []

        for adapter in self.adapters:
            unprocessed = adapter.discover_unprocessed_sessions(self.processed_sessions)
            for record_key, session_file, checkpoint in unprocessed:
                try:
                    file_mtime = session_file.stat().st_mtime
                    checkpoint_dict = checkpoint if isinstance(checkpoint, dict) else {}
                    start_step = int(checkpoint_dict.get("step_count", 0))
                    raw_ts = checkpoint_dict.get("last_timestamp")
                    last_timestamp: str | None = (
                        str(raw_ts) if raw_ts is not None else None
                    )

                    harness = WikiSkillHarness(
                        project_dir=self.hub_dir,
                        wiki_dir=self.hub_dir / "global" / "wiki",
                        skills_dir=self.hub_dir / "global" / "skills",
                        adapter=adapter,
                    )

                    res = harness.run_post_session(
                        session_file=session_file,
                        since=last_timestamp,
                        start_step=start_step,
                    )
                    steps_count = res.get("steps_count", 0)

                    if res.get("status") in ("success", "clean_session") and (
                        steps_count > 0 or res.get("patterns_created")
                    ):
                        processed_results.append(
                            {
                                "agent": adapter.agent_name,
                                "session_id": res.get("session_id", session_file.stem),
                                "record_key": record_key,
                                "steps_count": steps_count,
                                "patterns": res.get("patterns_created", []),
                                "proposals": res.get("proposals", []),
                            }
                        )

                    # Update checkpoint with latest mtime, accumulated step count, and timestamp
                    self.processed_sessions[record_key] = {
                        "mtime": file_mtime,
                        "step_count": start_step + steps_count,
                        "last_timestamp": res.get("timestamp") or last_timestamp,
                    }
                except (OSError, ValueError, KeyError, json.JSONDecodeError) as e:
                    print(
                        f"Error processing session '{record_key}' from {session_file}: {e}"
                    )
                    if record_key not in self.processed_sessions:
                        self.processed_sessions[record_key] = {
                            "mtime": session_file.stat().st_mtime,
                            "step_count": 0,
                        }

        if processed_results:
            self._save_state()

        return processed_results

    def run_loop(self, once: bool = False) -> None:
        """Run continuous monitoring loop across active agent harnesses."""
        agent_names = ", ".join(a.agent_name for a in self.adapters)
        print(f"Starting WikiSkill Daemon (monitoring agents: {agent_names})...")
        while True:
            results = self.scan_and_process_sessions()
            if results:
                print(f"Processed {len(results)} new session(s).")
            if once:
                break
            time.sleep(self.interval)
