import os
from typing import Any

from .dataclasses import SessionTrajectory


class WikiManager:
    def __init__(self, base_path: str = ".claude/wiki"):
        self.base_path = base_path
        self.patterns_path = os.path.join(base_path, "patterns")
        self.index_path = os.path.join(base_path, "index.md")
        self.logs_path = os.path.join(base_path, "logs.md")
        self.skill_impact_path = os.path.join(base_path, "skill-impact.md")

    def initialize_wiki(self) -> None:
        """Ensure wiki directory and core index/log files exist."""
        os.makedirs(self.patterns_path, exist_ok=True)
        if not os.path.exists(self.index_path):
            self._write_file(self.index_path, "# Wiki Pattern Index\n\n")
        if not os.path.exists(self.logs_path):
            self._write_file(self.logs_path, "# Wiki Evolution Log\n\n")
        if not os.path.exists(self.skill_impact_path):
            self._write_file(self.skill_impact_path, "# Skill Impact Audit Log\n\n")

    def _read_file(self, file_path: str) -> str | None:
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                return f.read()
        except FileNotFoundError:
            return None

    def _write_file(self, file_path: str, content: str, mode: str = "w"):
        os.makedirs(os.path.dirname(file_path), exist_ok=True)
        with open(file_path, mode, encoding="utf-8") as f:
            f.write(content)

    def get_wiki_index(self) -> str | None:
        return self._read_file(self.index_path)

    def get_skill_impact_log(self) -> str | None:
        return self._read_file(self.skill_impact_path)

    def create_pattern(self, pattern_name: str, content: str):
        file_path = os.path.join(self.patterns_path, f"{pattern_name}.md")
        self._write_file(file_path, content)
        print(f"Created new pattern file: {file_path}")

    def update_pattern(self, pattern_name: str, content: str):
        file_path = os.path.join(self.patterns_path, f"{pattern_name}.md")
        if os.path.exists(file_path):
            self._write_file(file_path, content)
            print(f"Updated pattern file: {file_path}")
        else:
            print(f"Warning: Pattern file {file_path} not found for update.")

    def update_index(self, additions: list[str]):
        current_content = self._read_file(self.index_path) or ""
        if current_content.endswith("\n"):
            current_content = current_content.rstrip("\n")

        updated_lines = current_content.splitlines()

        for addition in additions:
            if addition not in updated_lines:
                updated_lines.append(addition)

        new_content = "\n".join(updated_lines) + "\n"
        self._write_file(self.index_path, new_content)
        print(f"Updated wiki index: {self.index_path}")

    def append_log(self, entry: str):
        self._write_file(self.logs_path, f"{entry}\n", mode="a")
        print(f"Appended to wiki log: {self.logs_path}")

    def process_llm_wiki_response(self, llm_response: dict[str, Any]):
        for pattern in llm_response.get("create_patterns", []):
            self.create_pattern(pattern["name"], pattern["content"])
        for pattern in llm_response.get("update_patterns", []):
            self.update_pattern(pattern["name"], pattern["content"])
        if "update_index" in llm_response:
            self.update_index(llm_response["update_index"].get("additions", []))
        if "append_log" in llm_response:
            self.append_log(llm_response["append_log"])

    def call_llm_for_wiki_update(
        self, trajectory: SessionTrajectory, wiki_context: str
    ) -> dict[str, Any]:
        create_patterns: list[dict[str, str]] = []
        update_patterns: list[dict[str, str]] = []
        additions: list[str] = []

        error_steps = [s for s in trajectory.steps if s.is_error]
        error_types: dict[str, list[Any]] = {}

        for s in error_steps:
            obs = s.observation.lower()
            if s.tool_name == "Edit" and ("not found" in obs or "replace" in obs):
                error_types.setdefault("edit-string-mismatch-loop", []).append(s)
            elif s.tool_name == "Bash" and ("command not found" in obs or "127" in obs):
                error_types.setdefault("unprefixed-python-runner-loop", []).append(s)
            elif "modulenotfounderror" in obs or "importerror" in obs:
                error_types.setdefault("missing-dependency-import-loop", []).append(s)
            elif "assertionerror" in obs or "failed" in obs:
                error_types.setdefault("test-assertion-failure-loop", []).append(s)
            else:
                error_types.setdefault("generic-tool-error-loop", []).append(s)

        if "edit-string-mismatch-loop" in error_types:
            count = len(error_types["edit-string-mismatch-loop"])
            content = f"""# Edit String Mismatch Loop

## Problem
Encountered {count} failure(s) where string replacement failed because the specified target string did not match the file content exactly.

## Root Cause
Imprecise whitespace, indentation, or outdated line numbers passed into the Edit tool without inspecting the file immediately beforehand.

## Fix
1. Always run View on the exact line range immediately before performing an Edit.
2. Ensure character-for-character exact whitespace in old_string.
3. For edits spanning >30 lines or 50% of the file, use whole-file Write.
"""
            create_patterns.append(
                {
                    "name": "edit-string-mismatch-loop",
                    "content": content,
                }
            )
            additions.append(
                "- [edit-string-mismatch-loop](wiki/patterns/edit-string-mismatch-loop.md): Edit tool failed to find target string. Cause: whitespace or line mismatch. Fix: view exact line range before editing or use whole-file write."
            )

        if "unprefixed-python-runner-loop" in error_types:
            count = len(error_types["unprefixed-python-runner-loop"])
            content = f"""# Unprefixed Python Runner Loop

## Problem
Encountered {count} command failure(s) with 'command not found' (Exit code 127) when attempting to run tools or test suites directly.

## Root Cause
Executing bare 'pytest', 'ruff', or python scripts in subshells where tools are not globally symlinked in the system PATH.

## Fix
Always execute commands using the uv virtual environment runner:
- `uv run pytest -v`
- `uv run ruff check .`
- `uv run python <script.py>`
"""
            create_patterns.append(
                {
                    "name": "unprefixed-python-runner-loop",
                    "content": content,
                }
            )
            additions.append(
                "- [unprefixed-python-runner-loop](wiki/patterns/unprefixed-python-runner-loop.md): Command not found when running python tools. Cause: bare invocation without virtualenv. Fix: prefix with 'uv run <command>'."
            )

        if "missing-dependency-import-loop" in error_types:
            count = len(error_types["missing-dependency-import-loop"])
            content = f"""# Missing Dependency Import Loop

## Problem
Encountered {count} import error(s) with ModuleNotFoundError.

## Root Cause
Import paths were not aligned with workspace package hierarchy or dependency was missing from pyproject.toml.

## Fix
Add missing dependencies with `uv add` and ensure package imports are referenced from the project root.
"""
            create_patterns.append(
                {
                    "name": "missing-dependency-import-loop",
                    "content": content,
                }
            )
            additions.append(
                "- [missing-dependency-import-loop](wiki/patterns/missing-dependency-import-loop.md): ModuleNotFoundError during execution. Cause: missing package or path issue. Fix: add via uv and align root package imports."
            )

        if "test-assertion-failure-loop" in error_types:
            count = len(error_types["test-assertion-failure-loop"])
            content = f"""# Test Assertion Failure Loop

## Problem
Encountered {count} test assertion failure(s) during test runner execution.

## Root Cause
Implementation did not fulfill expected contract or test expectations were outdated.

## Fix
Review failure logs, make minimal targeted code adjustments, and re-run tests until green.
"""
            create_patterns.append(
                {
                    "name": "test-assertion-failure-loop",
                    "content": content,
                }
            )
            additions.append(
                "- [test-assertion-failure-loop](wiki/patterns/test-assertion-failure-loop.md): Test assertion failed. Cause: contract mismatch. Fix: inspect test failure and apply targeted minimal patch."
            )

        if not create_patterns:
            content = f"""# Clean Execution Pattern

## Problem
No critical execution errors detected in session {trajectory.session_id}.

## Root Cause
Commands and tool calls executed cleanly across {len(trajectory.steps)} steps.

## Fix
Continue standard TDD workflow.
"""
            create_patterns.append(
                {
                    "name": "clean-execution-pattern",
                    "content": content,
                }
            )
            additions.append(
                f"- [clean-execution-pattern](wiki/patterns/clean-execution-pattern.md): Clean session execution for session {trajectory.session_id}."
            )

        pattern_names = [p["name"] for p in create_patterns]
        log_entry = (
            f"Session {trajectory.session_id}: Analyzed {len(trajectory.steps)} steps "
            f"({len(error_steps)} errors); extracted patterns: {', '.join(pattern_names)}."
        )

        return {
            "create_patterns": create_patterns,
            "update_patterns": update_patterns,
            "update_index": {"additions": additions},
            "append_log": log_entry,
        }
