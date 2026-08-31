---
name: cli-tool-execution
description: Rules for executing python tools, test runners, and linters in the project environment.
---

# Operational Rules

## Trigger
Apply when working with cli-tool-execution operations in this codebase.

## Rules
- Always prefix python commands and test runners with 'uv run' (e.g. 'uv run pytest', 'uv run ruff check .').
- Never invoke bare 'pytest' or 'python' directly in shell subshells.
