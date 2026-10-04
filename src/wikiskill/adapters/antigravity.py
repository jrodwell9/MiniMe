import json
import os
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from ..models import SessionTrajectory, TrajectoryStep
from .base import AgentLogAdapter


def _clean_antigravity_arg(val: Any) -> Any:
    """Clean up stringified quotes/escapes in Antigravity tool call arguments."""
    if isinstance(val, str):
        val_str = val.strip()
        if (val_str.startswith('"') and val_str.endswith('"')) or (
            val_str.startswith("'") and val_str.endswith("'")
        ):
            try:
                # Try json loads to unescape safely
                return json.loads(val_str)
            except (json.JSONDecodeError, ValueError):
                return val_str[1:-1]
        return val_str
    if isinstance(val, dict):
        return {k: _clean_antigravity_arg(v) for k, v in val.items()}
    if isinstance(val, list):
        return [_clean_antigravity_arg(v) for v in val]
    return val


class AntigravityLogAdapter(AgentLogAdapter):
    """Log adapter for Google Antigravity session transcripts stored in ~/.gemini/antigravity/brain/."""

    agent_name: str = "antigravity"

    def __init__(
        self,
        antigravity_dir: str | Path | None = None,
        project_path: str | Path | None = None,
        mode: str = "auto",
        **kwargs: Any,
    ):
        super().__init__(mode=mode, **kwargs)
        self.antigravity_dir = Path(
            os.path.expanduser(antigravity_dir or "~/.gemini/antigravity")
        ).resolve()
        self.brain_dir = self.antigravity_dir / "brain"
        self.project_path = Path(project_path or os.getcwd()).resolve()

    def is_available(self) -> bool:
        """Check if Antigravity brain directory exists."""
        return self.brain_dir.exists() and self.brain_dir.is_dir()

    def get_latest_session_trajectory(
        self, since: str | None = None
    ) -> SessionTrajectory | None:
        if self.mode == "mock":
            return self._get_mock_session_trajectory()

        session_file = self._find_latest_session_file(since=since)
        if not session_file:
            return None

        return self.parse_session_file(session_file)

    def discover_unprocessed_sessions(
        self, processed_records: set[str]
    ) -> list[tuple[str, Path]]:
        """Scan all conversation directories under brain_dir for unprocessed transcripts."""
        if not self.is_available():
            return []

        results: list[tuple[str, Path]] = []
        for conv_folder in self.brain_dir.iterdir():
            if not conv_folder.is_dir():
                continue

            transcript_file = (
                conv_folder / ".system_generated" / "logs" / "transcript.jsonl"
            )
            if not transcript_file.exists():
                # Check directly in conv_folder as fallback
                transcript_file = conv_folder / "transcript.jsonl"
                if not transcript_file.exists():
                    continue

            conv_id = conv_folder.name
            record_key = f"antigravity:{conv_id}"
            if record_key in processed_records or conv_id in processed_records:
                continue

            results.append((record_key, transcript_file))

        return results

    def _find_latest_session_file(self, since: str | None = None) -> Path | None:
        if not self.is_available():
            return None

        candidate_files: list[Path] = []
        for conv_folder in self.brain_dir.iterdir():
            if not conv_folder.is_dir():
                continue
            t_file = conv_folder / ".system_generated" / "logs" / "transcript.jsonl"
            if t_file.exists():
                candidate_files.append(t_file)
            else:
                direct_t = conv_folder / "transcript.jsonl"
                if direct_t.exists():
                    candidate_files.append(direct_t)

        if not candidate_files:
            return None

        since_ts: float | None = None
        if since:
            try:
                dt = datetime.fromisoformat(since)
                since_ts = dt.timestamp()
            except ValueError as e:
                print(f"Warning: Failed to parse 'since' timestamp '{since}': {e}")

        # Sort files by modification time descending
        candidate_files.sort(key=lambda p: p.stat().st_mtime, reverse=True)

        for file_path in candidate_files:
            mtime = file_path.stat().st_mtime
            if since_ts is not None and mtime < since_ts:
                continue
            return file_path

        return None

    def parse_session_file(self, file_path: Path) -> SessionTrajectory | None:
        # Conversation ID is typically the folder name under brain/
        conv_id = (
            file_path.parents[2].name
            if file_path.parent.name == "logs" and len(file_path.parents) >= 3
            else file_path.parent.name
        )
        if conv_id in (".system_generated", "logs", "brain"):
            conv_id = file_path.stem

        timestamp: str = datetime.fromtimestamp(
            file_path.stat().st_mtime, tz=UTC
        ).isoformat()
        model_routed: str = "gemini-3.7"
        steps: list[TrajectoryStep] = []
        pending_tool_calls: list[dict[str, Any]] = []

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

                    if (
                        record.get("created_at")
                        and timestamp
                        == datetime.fromtimestamp(
                            file_path.stat().st_mtime, tz=UTC
                        ).isoformat()
                    ):
                        timestamp = record["created_at"]

                    rec_type = record.get("type")
                    status = record.get("status", "DONE")

                    # Check model settings changes
                    content_str = str(record.get("content", ""))
                    if "Model Selection" in content_str:
                        if "Gemini" in content_str or "Flash" in content_str:
                            model_routed = "gemini-3.7-flash"
                        elif "Pro" in content_str:
                            model_routed = "gemini-3.7-pro"

                    # Assistant Planner response containing tool calls
                    if rec_type == "PLANNER_RESPONSE":
                        raw_calls = record.get("tool_calls", [])
                        if isinstance(raw_calls, list):
                            for call in raw_calls:
                                if isinstance(call, dict):
                                    t_name = str(call.get("name", "unknown"))
                                    t_args = call.get("args", {})
                                    if isinstance(t_args, dict):
                                        t_args = {
                                            k: _clean_antigravity_arg(v)
                                            for k, v in t_args.items()
                                        }
                                    pending_tool_calls.append(
                                        {"name": t_name, "input": t_args}
                                    )

                    # Tool result / observation step
                    elif rec_type in ("GENERIC", "TOOL_RESULT") or (
                        record.get("source") in ("MODEL", "SYSTEM")
                        and pending_tool_calls
                    ):
                        if pending_tool_calls:
                            call_info = pending_tool_calls.pop(0)
                            obs_content = record.get("content", "")
                            if isinstance(obs_content, list):
                                observation = "\n".join(
                                    c.get("text", str(c))
                                    if isinstance(c, dict)
                                    else str(c)
                                    for c in obs_content
                                )
                            else:
                                observation = str(obs_content)

                            is_error = (
                                status == "ERROR"
                                or "Tool failed" in observation
                                or "Traceback (most recent call last)" in observation
                                or observation.startswith("Error:")
                            )

                            steps.append(
                                TrajectoryStep(
                                    step_number=len(steps) + 1,
                                    tool_name=call_info["name"],
                                    tool_input=call_info["input"],
                                    observation=observation,
                                    is_error=is_error,
                                    latency_ms=0.0,
                                )
                            )
        except OSError as e:
            print(f"Error reading Antigravity transcript {file_path}: {e}")
            return None

        return SessionTrajectory(
            session_id=conv_id,
            timestamp=timestamp,
            model_routed=model_routed,
            steps=steps,
            final_status="success",
        )

    def _get_mock_session_trajectory(self) -> SessionTrajectory:
        mock_steps = [
            TrajectoryStep(
                step_number=1,
                tool_name="view_file",
                tool_input={"AbsolutePath": "c:/Users/test/main.py"},
                observation="print('hello antigravity')",
                is_error=False,
                latency_ms=45.0,
            ),
            TrajectoryStep(
                step_number=2,
                tool_name="run_command",
                tool_input={"CommandLine": "uv run pytest"},
                observation="55 passed in 2.1s",
                is_error=False,
                latency_ms=120.0,
            ),
        ]
        return SessionTrajectory(
            session_id="mock-antigravity-conv-1",
            timestamp="2026-10-04T17:00:00Z",
            model_routed="gemini-3.7-flash",
            steps=mock_steps,
            final_status="success",
        )
