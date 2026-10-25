"""
WikiSkill: Compounding knowledge and self-evolving skill harness for AI agents.
"""

from .adapters import (
    AgentLogAdapter,
    AgentLogAdapterFactory,
    AntigravityLogAdapter,
    ClaudeCodeLogAdapter,
    sanitize_project_path,
)
from .models import SessionTrajectory, TrajectoryStep
from .wiki_manager import WikiManager

__version__ = "0.1.0"

__all__ = [
    "AgentLogAdapter",
    "AgentLogAdapterFactory",
    "AntigravityLogAdapter",
    "ClaudeCodeLogAdapter",
    "SessionTrajectory",
    "TrajectoryStep",
    "WikiManager",
    "sanitize_project_path",
]
