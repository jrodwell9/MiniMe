"""
Backward compatibility proxy for ClaudeCodeLogAdapter.
Canonical implementation now lives in wikiskill.adapters.claude.
"""

from .adapters.claude import ClaudeCodeLogAdapter, sanitize_project_path

__all__ = ["ClaudeCodeLogAdapter", "sanitize_project_path"]
