from pathlib import Path
from typing import Any
from .base import AgentLogAdapter
from ..models import SessionTrajectory

class AntigravityLogAdapter(AgentLogAdapter):
    agent_name = "antigravity"
    def __init__(self, antigravity_dir: str | Path | None = None, **kwargs: Any):
        super().__init__(**kwargs)
        self.antigravity_dir = Path(antigravity_dir or "~/.gemini/antigravity").expanduser()
        self.brain_dir = self.antigravity_dir / "brain"
    def is_available(self) -> bool:
        return self.brain_dir.exists()
    def get_latest_session_trajectory(self, since: str | None = None) -> SessionTrajectory | None:
        return None
    def discover_unprocessed_sessions(self, processed_state: dict[str, Any] | set[str]) -> list[tuple[str, Path, dict[str, Any] | None]]:
        return []
    def parse_session_file(self, file_path: Path, since: str | None = None, start_step: int = 0) -> SessionTrajectory | None:
        return None
