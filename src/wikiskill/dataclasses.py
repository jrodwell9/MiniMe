from dataclasses import dataclass, field
from typing import Any


@dataclass
class TrajectoryStep:
    step_number: int
    tool_name: str
    tool_input: dict[str, Any]
    observation: str
    is_error: bool
    latency_ms: float = 0.0


@dataclass
class SessionTrajectory:
    session_id: str
    timestamp: str
    model_routed: str
    steps: list[TrajectoryStep] = field(default_factory=list)
    final_status: str = "success"
