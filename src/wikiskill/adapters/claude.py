from pathlib import Path
from typing import Any
from .base import AgentLogAdapter
from ..models import SessionTrajectory

def sanitize_project_path(project_path: str | Path) -> str:
    path_str = str(project_path).replace("\\", "/")
    return path_str.replace(":", "-").replace("/", "-")

class ClaudeCodeLogAdapter(AgentLogAdapter):
    agent_name = "claude"
    def __init__(self, claude_dir: str | Path | None = None, **kwargs: Any):
        super().__init__(**kwargs)
        self.claude_dir = Path(claude_dir or "~/.claude").expanduser()
        self.projects_dir = self.claude_dir / "projects"
    def is_available(self) -> bool:
        return self.projects_dir.exists()
    def get_latest_session_trajectory(self, since: str | None = None) -> SessionTrajectory | None:
        return None
    def discover_unprocessed_sessions(self, processed_state: dict[str, Any] | set[str]) -> list[tuple[str, Path, dict[str, Any] | None]]:
        return []
    def parse_session_file(self, file_path: Path, since: str | None = None, start_step: int = 0) -> SessionTrajectory | None:
        return None
