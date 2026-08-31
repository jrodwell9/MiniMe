# Unprefixed Python Runner Loop

## Problem
Encountered 6 command failure(s) with 'command not found' (Exit code 127) when attempting to run tools or test suites directly.

## Root Cause
Executing bare 'pytest', 'ruff', or python scripts in subshells where tools are not globally symlinked in the system PATH.

## Fix
Always execute commands using the uv virtual environment runner:
- `uv run pytest -v`
- `uv run ruff check .`
- `uv run python <script.py>`
