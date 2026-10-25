"""
WikiSkill: Compounding knowledge and self-evolving skill harness for AI agents (Claude Code, Antigravity, and beyond).
"""

from .adapters import (
    AgentLogAdapter,
    AgentLogAdapterFactory,
    AntigravityLogAdapter,
    ClaudeCodeLogAdapter,
    sanitize_project_path,
)
from .curator import (
    CuratorSandboxError,
    CuratorSandboxTools,
    WikiSkillCuratorAgent,
    bump_plugin_version,
)
from .daemon import WikiSkillDaemon
from .harness import WikiSkillHarness
from .llm import (
    LLMConfigurationError,
    PatternEntry,
    WikiPatternSynthesisSignature,
    WikiPatternSynthesizer,
    WikiSkillLLMAdapter,
    WikiUpdateOutput,
)
from .marketplace import MarketplaceManager
from .models import SessionTrajectory, TrajectoryStep
from .sync import GitHubSyncManager, ensure_agent_links
from .wiki_manager import WikiManager

__version__ = "0.1.0"

__all__ = [
    "AgentLogAdapter",
    "AgentLogAdapterFactory",
    "AntigravityLogAdapter",
    "ClaudeCodeLogAdapter",
    "CuratorSandboxError",
    "CuratorSandboxTools",
    "GitHubSyncManager",
    "LLMConfigurationError",
    "MarketplaceManager",
    "PatternEntry",
    "SessionTrajectory",
    "TrajectoryStep",
    "WikiManager",
    "WikiPatternSynthesisSignature",
    "WikiPatternSynthesizer",
    "WikiSkillCuratorAgent",
    "WikiSkillDaemon",
    "WikiSkillHarness",
    "WikiSkillLLMAdapter",
    "WikiUpdateOutput",
    "bump_plugin_version",
    "ensure_agent_links",
    "sanitize_project_path",
]
