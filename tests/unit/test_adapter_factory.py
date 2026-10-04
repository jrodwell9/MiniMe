from pathlib import Path
from typing import Any

import pytest

from wikiskill.adapters import (
    AgentLogAdapter,
    AgentLogAdapterFactory,
    AntigravityLogAdapter,
    ClaudeCodeLogAdapter,
)
from wikiskill.models import SessionTrajectory


class MockCursorLogAdapter(AgentLogAdapter):
    agent_name = "cursor"

    def __init__(self, cursor_dir: str | Path | None = None, **kwargs: Any):
        super().__init__(**kwargs)
        self.cursor_dir = Path(cursor_dir or "~/.cursor").resolve()

    def is_available(self) -> bool:
        return self.cursor_dir.exists()

    def get_latest_session_trajectory(
        self, since: str | None = None
    ) -> SessionTrajectory | None:
        return None

    def discover_unprocessed_sessions(
        self, processed_records: set[str]
    ) -> list[tuple[str, Path]]:
        return []

    def parse_session_file(self, file_path: Path) -> SessionTrajectory | None:
        return None


def test_factory_list_registered():
    registered = AgentLogAdapterFactory.list_registered()
    assert "claude" in registered
    assert "antigravity" in registered


def test_factory_get_adapter():
    claude_adapter = AgentLogAdapterFactory.get_adapter("claude")
    assert isinstance(claude_adapter, ClaudeCodeLogAdapter)

    antigravity_adapter = AgentLogAdapterFactory.get_adapter("antigravity")
    assert isinstance(antigravity_adapter, AntigravityLogAdapter)

    with pytest.raises(ValueError, match="Unknown agent adapter"):
        AgentLogAdapterFactory.get_adapter("nonexistent-agent")


def test_factory_register_custom_adapter():
    AgentLogAdapterFactory.register("cursor", MockCursorLogAdapter)
    assert "cursor" in AgentLogAdapterFactory.list_registered()

    cursor_inst = AgentLogAdapterFactory.get_adapter("cursor")
    assert isinstance(cursor_inst, MockCursorLogAdapter)
    assert cursor_inst.agent_name == "cursor"


def test_factory_detect_available_adapters(tmp_path: Path):
    claude_env = tmp_path / ".claude" / "projects"
    claude_env.mkdir(parents=True)

    antigravity_env = tmp_path / "gemini" / "antigravity" / "brain"
    antigravity_env.mkdir(parents=True)

    detected = AgentLogAdapterFactory.detect_available_adapters(
        claude_dir=tmp_path / ".claude",
        antigravity_dir=tmp_path / "gemini" / "antigravity",
    )

    agent_names = [a.agent_name for a in detected]
    assert "claude" in agent_names
    assert "antigravity" in agent_names


def test_factory_get_primary_adapter(tmp_path: Path):
    # Explicit override
    primary_explicit = AgentLogAdapterFactory.get_primary_adapter(
        agent_name="antigravity",
        antigravity_dir=tmp_path,
    )
    assert isinstance(primary_explicit, AntigravityLogAdapter)

    # Automatic detection when only antigravity exists
    antigravity_dir = tmp_path / "ag"
    (antigravity_dir / "brain").mkdir(parents=True)

    detected_primary = AgentLogAdapterFactory.get_primary_adapter(
        claude_dir=tmp_path / "nonexistent_claude",
        antigravity_dir=antigravity_dir,
    )
    assert isinstance(detected_primary, AntigravityLogAdapter)
