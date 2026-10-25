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
                return json.loads(val_str)
            except json.JSONDecodeError, ValueError:
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

        return self.parse_session_file(session_file, since=since)

    def discover_unprocessed_sessions(
        self, processed_state: dict[str, Any] | set[str]
    ) -> list[tuple[str, Path, dict[str, Any] | None]]:
        """Scan all conversation directories under brain_dir for unhandled or updated transcripts."""
        if not self.is_available():
            return []

        results: list[tuple[str, Path, dict[str, Any] | None]] = []
        for conv_folder in self.brain_dir.iterdir():
            if not conv_folder.is_dir():
                continue

            transcript_file = (
                conv_folder / ".system_generated" / "logs" / "transcript.jsonl"
            )
            if not transcript_file.exists():
                transcript_file = conv_folder / "transcript.jsonl"
                if not transcript_file.exists():
                    continue

            conv_id = conv_folder.name
            record_key = f"antigravity:{conv_id}"
            file_mtime = transcript_file.stat().st_mtime

            if isinstance(processed_state, dict):
                checkpoint = processed_state.get(record_key) or processed_state.get(
                    conv_id
                )
                if checkpoint is None:
                    results.append((record_key, transcript_file, None))
                elif isinstance(checkpoint, dict):
                    last_mtime = checkpoint.get("mtime", 0.0)
                    if file_mtime > last_mtime + 0.001:
                        results.append((record_key, transcript_file, checkpoint))
                elif (
                    isinstance(checkpoint, (int, float))
                    and file_mtime > checkpoint + 0.001
                ):
                    results.append((record_key, transcript_file, {"mtime": checkpoint}))
            else:
                if record_key not in processed_state and conv_id not in processed_state:
                    results.append((record_key, transcript_file, None))

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

        candidate_files.sort(key=lambda p: p.stat().st_mtime, reverse=True)

        for file_path in candidate_files:
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
        all_steps: list[TrajectoryStep] = []
        pending_tool_calls: list[dict[str, Any]] = []

        since_dt: datetime | None = None
        if since:
            try:
                since_dt = datetime.fromisoformat(since)
                if since_dt.tzinfo is None:
                    since_dt = since_dt.replace(tzinfo=UTC)
            except ValueError:
                since_dt = None

        try:
            raw_records: list[tuple[int, int, dict[str, Any]]] = []
            with open(file_path, "r", encoding="utf-8", errors="replace") as f:
                for line_idx, line in enumerate(f):
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        record = json.loads(line)
                    except json.JSONDecodeError:
                        continue

                    if not isinstance(record, dict):
                        continue

                    raw_step_idx = record.get("step_index")
                    step_idx = (
                        int(raw_step_idx)
                        if isinstance(raw_step_idx, (int, float))
                        else line_idx
                    )
                    raw_records.append((step_idx, line_idx, record))

            raw_records.sort(key=lambda item: (item[0], item[1]))

            for _, _, record in raw_records:
                rec_created = record.get("created_at")
                if (
                    rec_created
                    and timestamp
                    == datetime.fromtimestamp(
                        file_path.stat().st_mtime, tz=UTC
                    ).isoformat()
                ):
                    timestamp = rec_created

                rec_type = record.get("type")
                status = record.get("status", "DONE")

                content_str = str(record.get("content", ""))
                if "Model Selection" in content_str:
                    if "Gemini" in content_str or "Flash" in content_str:
                        model_routed = "gemini-3.7-flash"
                    elif "Pro" in content_str:
                        model_routed = "gemini-3.7-pro"

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
                                    {
                                        "name": t_name,
                                        "input": t_args,
                                        "created_at": rec_created,
                                    }
                                )

                elif rec_type in ("GENERIC", "TOOL_RESULT") or (
                    record.get("source") in ("MODEL", "SYSTEM") and pending_tool_calls
                ):
                    if pending_tool_calls:
                        call_info = pending_tool_calls.pop(0)
                        obs_content = record.get("content", "")
                        if isinstance(obs_content, list):
                            observation = "\n".join(
                                c.get("text", str(c)) if isinstance(c, dict) else str(c)
                                for c in obs_content
                            )
                        else:
                            observation = str(obs_content)

                        non_zero_exit = (
                            "The command exited with code " in observation
                            and "The command exited with code 0." not in observation
                        )
                        is_error = (
                            status == "ERROR"
                            or "Tool failed" in observation
                            or "Encountered error in tool execution" in observation
                            or "Traceback (most recent call last)" in observation
                            or observation.startswith("Error:")
                            or non_zero_exit
                        )

                        all_steps.append(
                            TrajectoryStep(
                                step_number=len(all_steps) + 1,
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

        # Filter steps based on start_step and since timestamp
        filtered_steps = all_steps
        if start_step > 0 and start_step < len(all_steps):
            filtered_steps = all_steps[start_step:]
        elif start_step >= len(all_steps):
            filtered_steps = []

        return SessionTrajectory(
            session_id=conv_id,
            timestamp=timestamp,
            model_routed=model_routed,
            steps=filtered_steps,
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
                observation="65 passed in 2.1s",
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
