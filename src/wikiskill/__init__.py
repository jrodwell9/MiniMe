"""
WikiSkill: Compounding knowledge harness for Claude Code agent sessions.
"""

from .claude_log_adapter import ClaudeCodeLogAdapter, sanitize_project_path
from .daemon import WikiSkillDaemon
from .dataclasses import SessionTrajectory, TrajectoryStep
from .harness import WikiSkillHarness
from .skill_proposer import SkillProposer
from .sync import GitHubSyncManager
from .wiki_manager import WikiManager

__version__ = "0.1.0"

__all__ = [
    "ClaudeCodeLogAdapter",
    "GitHubSyncManager",
    "SessionTrajectory",
    "SkillProposer",
    "TrajectoryStep",
    "WikiManager",
    "WikiSkillDaemon",
    "WikiSkillHarness",
    "sanitize_project_path",
]
