import json
import os
import sqlite3

from .wikiskill_dataclasses import SessionTrajectory, TrajectoryStep


class CCRLogAdapter:
    def __init__(self, ccr_log_source: str = "mock", db_path: str = "~/.claude-code-router/logs.db"):
        self.ccr_log_source = ccr_log_source
        self.db_path = os.path.expanduser(db_path)

    def get_latest_session_trajectory(self) -> SessionTrajectory | None:
        if self.ccr_log_source == "mock":
            return self._get_mock_session_trajectory()
        elif self.ccr_log_source == "sqlite":
            return self._get_sqlite_session_trajectory()
        # TODO: Implement actual logic for REST API if needed
        return None

    def _get_sqlite_session_trajectory(self) -> SessionTrajectory | None:
        if not os.path.exists(self.db_path):
            print(f"Error: SQLite database not found at {self.db_path}")
            return None

        conn = None
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            # Fetch the latest session
            cursor.execute(
                "SELECT session_id, timestamp, model_routed, final_status FROM sessions ORDER BY timestamp DESC LIMIT 1"
            )
            session_data = cursor.fetchone()

            if not session_data:
                return None

            session_id, timestamp, model_routed, final_status = session_data
            steps: list[TrajectoryStep] = []

            # Fetch steps for the latest session
            cursor.execute(
                "SELECT step_number, tool_name, tool_input, observation, is_error, latency_ms FROM steps WHERE session_id = ? ORDER BY step_number",
                (session_id,),
            )
            for step_data in cursor.fetchall():
                (
                    step_number,
                    tool_name,
                    tool_input_json,
                    observation,
                    is_error,
                    latency_ms,
                ) = step_data
                steps.append(
                    TrajectoryStep(
                        step_number=step_number,
                        tool_name=tool_name,
                        tool_input=json.loads(tool_input_json)
                        if tool_input_json
                        else {},
                        observation=observation,
                        is_error=bool(is_error),
                        latency_ms=latency_ms,
                    )
                )

            return SessionTrajectory(
                session_id=session_id,
                timestamp=timestamp,
                model_routed=model_routed,
                steps=steps,
                final_status=final_status,
            )
        except sqlite3.Error as e:
            print(f"SQLite error: {e}")
            return None
        except json.JSONDecodeError as e:
            print(f"JSON decode error in tool_input: {e}")
            return None
        finally:
            if conn:
                conn.close()

    def _get_mock_session_trajectory(self) -> SessionTrajectory:
        # This is a placeholder for testing.
        # In a real scenario, this would involve parsing actual CCR logs.
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
            session_id="test-session-123",
            timestamp="2026-08-31T10:00:00Z",
            model_routed="claude-3-opus",
            steps=mock_steps,
            final_status="success",
        )
