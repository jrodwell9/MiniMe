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
        self, processed_state: dict[str, Any] | set[str]
    ) -> list[tuple[str, Path, dict[str, Any] | None]]:
        """
        Discover unhandled or updated session records across projects/conversations.
        Returns a list of tuples: (record_key, session_file_path, checkpoint_or_None).
        """
        ...

    @abstractmethod
    def parse_session_file(
        self,
        file_path: Path,
        since: str | None = None,
        start_step: int = 0,
    ) -> SessionTrajectory | None:
        """
        Parse a specific session transcript file into a normalized SessionTrajectory.
        If `since` timestamp or `start_step` is provided, parses only incremental delta steps.
        """
        ...
