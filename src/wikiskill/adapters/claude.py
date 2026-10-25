import json
import os
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from ..models import SessionTrajectory, TrajectoryStep
from .base import AgentLogAdapter


def sanitize_project_path(project_path: str | Path) -> str:
    """
    Sanitize a filesystem path into Claude Code's project directory slug format.
    E.g. 'C:\\Users\\jrodw\\Documents\\MiniMe' -> 'C--Users-jrodw-Documents-MiniMe'
    """
    path_str = str(project_path)
    sanitized = path_str.replace(":", "-").replace("\\", "-").replace("/", "-")
    return sanitized


class ClaudeCodeLogAdapter(AgentLogAdapter):
    """Log adapter for Claude Code session transcripts stored in ~/.claude/projects/."""

    agent_name: str = "claude"

    def __init__(
        self,
        projects_dir: str | Path | None = None,
        project_path: str | Path | None = None,
        claude_dir: str | Path | None = None,
        mode: str = "auto",
        **kwargs: Any,
    ):
        super().__init__(mode=mode, **kwargs)
        base_claude = Path(os.path.expanduser(claude_dir or "~/.claude"))
        self.projects_dir = Path(
            os.path.expanduser(projects_dir or (base_claude / "projects"))
        ).resolve()
        self.project_path = Path(project_path or os.getcwd()).resolve()

    def is_available(self) -> bool:
        """Check if Claude Code projects directory exists."""
        return self.projects_dir.exists() and self.projects_dir.is_dir()

    def get_latest_session_trajectory(
        self, since: str | None = None
    ) -> SessionTrajectory | None:
        if self.mode == "mock":
            return self._get_mock_session_trajectory()

        session_file = self._find_latest_session_file(since=since)
        if not session_file:
            return None

        return self.parse_session_file(session_file, since=since)

    def discover_unprocessed_sessions(
        self, processed_state: dict[str, Any] | set[str]
    ) -> list[tuple[str, Path, dict[str, Any] | None]]:
        """Scan all project folders under projects_dir for unhandled or updated .jsonl transcripts."""
        if not self.is_available():
            return []

        results: list[tuple[str, Path, dict[str, Any] | None]] = []
        for proj_folder in self.projects_dir.iterdir():
            if not proj_folder.is_dir():
                continue

            for jsonl_file in proj_folder.glob("*.jsonl"):
                session_id = jsonl_file.stem
                record_key = f"{proj_folder.name}/{session_id}"
                namespaced_key = f"claude:{record_key}"
                file_mtime = jsonl_file.stat().st_mtime

                if isinstance(processed_state, dict):
                    checkpoint = (
                        processed_state.get(namespaced_key)
                        or processed_state.get(record_key)
                        or processed_state.get(session_id)
                    )
                    if checkpoint is None:
                        results.append((namespaced_key, jsonl_file, None))
                    elif isinstance(checkpoint, dict):
                        last_mtime = checkpoint.get("mtime", 0.0)
                        if file_mtime > last_mtime + 0.001:
                            results.append((namespaced_key, jsonl_file, checkpoint))
                    elif (
                        isinstance(checkpoint, (int, float))
                        and file_mtime > checkpoint + 0.001
                    ):
                        results.append(
                            (namespaced_key, jsonl_file, {"mtime": checkpoint})
                        )
                else:
                    if (
                        record_key not in processed_state
                        and namespaced_key not in processed_state
                        and session_id not in processed_state
                    ):
                        results.append((namespaced_key, jsonl_file, None))

        return results

    def _find_latest_session_file(self, since: str | None = None) -> Path | None:
        slug = sanitize_project_path(self.project_path)
        target_dir = self.projects_dir / slug

        if not target_dir.exists() or not target_dir.is_dir():
            if not self.projects_dir.exists():
                return None
            candidates = [
                d
                for d in self.projects_dir.iterdir()
                if d.is_dir() and slug.endswith(d.name)
            ]
            if candidates:
                target_dir = candidates[0]
            else:
                return None

        jsonl_files = list(target_dir.glob("*.jsonl"))
        if not jsonl_files:
            return None

        since_ts: float | None = None
        if since:
            try:
                dt = datetime.fromisoformat(since)
                since_ts = dt.timestamp()
            except ValueError as e:
                print(f"Warning: Failed to parse 'since' timestamp '{since}': {e}")

        jsonl_files.sort(key=lambda p: p.stat().st_mtime, reverse=True)

        for file_path in jsonl_files:
            mtime = file_path.stat().st_mtime
            if since_ts is not None and mtime < since_ts:
                continue
            return file_path

        return None

    def parse_session_file(
        self,
        file_path: Path,
        since: str | None = None,
        start_step: int = 0,
    ) -> SessionTrajectory | None:
        session_id: str = file_path.stem
        timestamp: str = datetime.fromtimestamp(
            file_path.stat().st_mtime, tz=UTC
        ).isoformat()
        model_routed: str = "unknown"
        all_steps: list[TrajectoryStep] = []

        tool_calls: dict[str, dict[str, Any]] = {}

        try:
            with open(file_path, "r", encoding="utf-8", errors="replace") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        record = json.loads(line)
                    except json.JSONDecodeError:
                        continue

                    if not isinstance(record, dict):
                        continue

                    if record.get("sessionId"):
                        session_id = record["sessionId"]

                    if (
                        record.get("timestamp")
                        and timestamp
                        == datetime.fromtimestamp(
                            file_path.stat().st_mtime, tz=UTC
                        ).isoformat()
                    ):
                        timestamp = record["timestamp"]

                    msg = record.get("message", {})
                    if not isinstance(msg, dict):
                        continue

                    rec_type = record.get("type")

                    if rec_type == "assistant":
                        if msg.get("model"):
                            model_routed = msg["model"]
                        content = msg.get("content", [])
                        if isinstance(content, list):
                            for block in content:
                                if (
                                    isinstance(block, dict)
                                    and block.get("type") == "tool_use"
                                ):
                                    tool_id = str(block.get("id", ""))
                                    if tool_id:
                                        tool_calls[tool_id] = {
                                            "name": block.get("name", "unknown"),
                                            "input": block.get("input", {}),
                                        }

                    elif rec_type == "user":
                        content = msg.get("content", [])
                        if isinstance(content, list):
                            for block in content:
                                if (
                                    isinstance(block, dict)
                                    and block.get("type") == "tool_result"
                                ):
                                    tool_use_id = str(block.get("tool_use_id", ""))
                                    call_info = tool_calls.get(tool_use_id, {})
                                    tool_name = str(call_info.get("name", "unknown"))
                                    tool_input: dict[str, Any] = call_info.get(
                                        "input", {}
                                    )
                                    is_error = bool(block.get("is_error", False))

                                    raw_content = block.get("content", "")
                                    if isinstance(raw_content, list):
                                        observation = "\n".join(
                                            c.get("text", str(c))
                                            if isinstance(c, dict)
                                            else str(c)
                                            for c in raw_content
                                        )
                                    else:
                                        observation = str(raw_content)

                                    all_steps.append(
                                        TrajectoryStep(
                                            step_number=len(all_steps) + 1,
                                            tool_name=tool_name,
                                            tool_input=tool_input,
                                            observation=observation,
                                            is_error=is_error,
                                            latency_ms=0.0,
                                        )
                                    )
        except OSError as e:
            print(f"Error reading session file {file_path}: {e}")
            return None

        # Filter steps based on start_step
        filtered_steps = all_steps
        if start_step > 0 and start_step < len(all_steps):
            filtered_steps = all_steps[start_step:]
        elif start_step >= len(all_steps):
            filtered_steps = []

        return SessionTrajectory(
            session_id=session_id,
            timestamp=timestamp,
            model_routed=model_routed,
            steps=filtered_steps,
            final_status="success",
        )

    def _get_mock_session_trajectory(self) -> SessionTrajectory:
        mock_steps = [
            TrajectoryStep(
                step_number=1,
                tool_name="Bash",
                tool_input={"command": "ls -la"},
                observation="""total 0
-rw-r--r--  1 user  group  0 Aug 31 10:00 file.txt""",
                is_error=False,
                latency_ms=150.5,
            ),
            TrajectoryStep(
                step_number=2,
                tool_name="Read",
                tool_input={"file_path": "file.txt"},
                observation="1\tHello World!",
                is_error=False,
                latency_ms=80.2,
            ),
        ]
        return SessionTrajectory(
            session_id="mock-session-123",
            timestamp="2026-08-31T10:00:00Z",
            model_routed="claude-3-7-sonnet",
            steps=mock_steps,
            final_status="success",
        )
