import json
import os
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from MiniMe.scripts.wikiskill_dataclasses import SessionTrajectory, TrajectoryStep


def sanitize_project_path(project_path: str | Path) -> str:
    """
    Sanitize a filesystem path into Claude Code's project directory slug format.
    E.g. 'C:\\Users\\jrodw\\Documents\\MiniMe' -> 'C--Users-jrodw-Documents-MiniMe'
    """
    path_str = str(project_path)
    sanitized = path_str.replace(":", "-").replace("\\", "-").replace("/", "-")
    return sanitized


class ClaudeCodeLogAdapter:
    def __init__(
        self,
        projects_dir: str | Path | None = None,
        project_path: str | Path | None = None,
        mode: str = "auto",
    ):
        self.mode = mode
        self.projects_dir = Path(
            os.path.expanduser(projects_dir or "~/.claude/projects")
        )
        self.project_path = Path(project_path or os.getcwd()).resolve()

    def get_latest_session_trajectory(
        self, since: str | None = None
    ) -> SessionTrajectory | None:
        if self.mode == "mock":
            return self._get_mock_session_trajectory()

        session_file = self._find_latest_session_file(since=since)
        if not session_file:
            return None

        return self._parse_session_jsonl(session_file)

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

        # Sort files by modification time descending
        jsonl_files.sort(key=lambda p: p.stat().st_mtime, reverse=True)

        for file_path in jsonl_files:
            mtime = file_path.stat().st_mtime
            if since_ts is not None and mtime < since_ts:
                continue
            return file_path

        return None

    def _parse_session_jsonl(self, file_path: Path) -> SessionTrajectory | None:
        session_id: str = file_path.stem
        timestamp: str = datetime.fromtimestamp(
            file_path.stat().st_mtime, tz=UTC
        ).isoformat()
        model_routed: str = "unknown"
        steps: list[TrajectoryStep] = []

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

                    # Assistant turn: captures tool_use invocations
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

                    # User turn: captures tool_result observations
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

                                    steps.append(
                                        TrajectoryStep(
                                            step_number=len(steps) + 1,
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

        return SessionTrajectory(
            session_id=session_id,
            timestamp=timestamp,
            model_routed=model_routed,
            steps=steps,
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
