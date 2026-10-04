from .antigravity import AntigravityLogAdapter
from .base import AgentLogAdapter
from .claude import ClaudeCodeLogAdapter, sanitize_project_path
from .factory import AgentLogAdapterFactory

# Register standard supported agent adapters
AgentLogAdapterFactory.register("claude", ClaudeCodeLogAdapter)
AgentLogAdapterFactory.register("antigravity", AntigravityLogAdapter)

__all__ = [
    "AgentLogAdapter",
    "AgentLogAdapterFactory",
    "AntigravityLogAdapter",
    "ClaudeCodeLogAdapter",
    "sanitize_project_path",
]
