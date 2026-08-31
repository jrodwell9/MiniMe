import dataclasses
from typing import Any


@dataclasses.dataclass
class TrajectoryStep:
    step_number: int
    tool_name: str
    tool_input: dict[str, Any]
    observation: str
    is_error: bool
    latency_ms: float


@dataclasses.dataclass
class SessionTrajectory:
    session_id: str
    timestamp: str
    model_routed: str
    steps: list[TrajectoryStep]
    final_status: str
