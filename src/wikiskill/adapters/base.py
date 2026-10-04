from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any

from ..models import SessionTrajectory


class AgentLogAdapter(ABC):
    """Abstract base class for AI agent transcript and telemetry log adapters."""

    agent_name: str = "base"

    def __init__(self, mode: str = "auto", **kwargs: Any) -> None:
        self.mode = mode

    @abstractmethod
    def is_available(self) -> bool:
        """Check if this agent's environment or storage directories exist locally."""
        ...

    @abstractmethod
    def get_latest_session_trajectory(
        self, since: str | None = None
    ) -> SessionTrajectory | None:
        """Retrieve the most recent session trajectory for the active project/workspace."""
        ...

    @abstractmethod
    def discover_unprocessed_sessions(
        self, processed_records: set[str]
    ) -> list[tuple[str, Path]]:
        """
        Discover unhandled session records across projects/conversations for this agent.
        Returns a list of tuples: (record_key, session_file_path).
        """
        ...

    @abstractmethod
    def parse_session_file(self, file_path: Path) -> SessionTrajectory | None:
        """Parse a specific session transcript file into a normalized SessionTrajectory."""
        ...
