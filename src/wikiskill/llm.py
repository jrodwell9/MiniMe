import json
import os
from pathlib import Path
from typing import Any

import dspy
from pydantic import BaseModel, Field

from .models import SessionTrajectory


class LLMConfigurationError(RuntimeError):
    """Raised when an LLM call is attempted without a configured provider/API key and mock=False."""


class PatternEntry(BaseModel):
    name: str = Field(
        description="Kebab-case slug for the pattern (e.g. 'edit-string-mismatch-loop')"
    )
    content: str = Field(
        description="Markdown body with # Title, ## Problem, ## Root Cause, and ## Fix sections"
    )


class WikiUpdateOutput(BaseModel):
    create_patterns: list[PatternEntry] = Field(default_factory=list)
    update_patterns: list[PatternEntry] = Field(default_factory=list)
    index_additions: list[str] = Field(
        default_factory=list,
        description="Markdown bullet lines to append to index.md, e.g. '- [slug](wiki/patterns/slug.md): Summary.'",
    )
    append_log: str = Field(
        description="Single-line summary of session analysis for logs.md"
    )


class WikiPatternSynthesisSignature(dspy.Signature):
    """Analyze an AI agent session trajectory and existing wiki patterns to diagnose recurring tool execution failure patterns.
    1. Consolidate related session errors into a single cohesive pattern rather than creating multiple fragmented micro-patterns for the same tool/domain.
    2. Inspect existing_patterns_json first: when a session error belongs to a failure domain already covered by an existing pattern slug, use update_patterns with that existing pattern's name and an enriched markdown body rather than creating a duplicate file in create_patterns.
    3. Each pattern must include '# <Title>', '## Problem', '## Root Cause', and '## Fix'.
    4. Only extract actionable recurring failure patterns; if none exist, return empty lists."""

    session_id: str = dspy.InputField(desc="Unique identifier of the agent session")
    total_steps: int = dspy.InputField(
        desc="Total number of steps in the session trajectory"
    )
    error_steps_json: str = dspy.InputField(
        desc="JSON-serialized error steps with tool_name, tool_input, and observation"
    )
    wiki_context: str = dspy.InputField(desc="Existing wiki index.md content")
    existing_patterns_json: str = dspy.InputField(
        desc="JSON list of existing pattern files ({name, content}) currently in wiki/patterns/"
    )
    wiki_update: WikiUpdateOutput = dspy.OutputField(
        desc="Structured wiki update payload"
    )


class WikiPatternSynthesizer(dspy.Module):
    """DSPy module for extracting recurring failure patterns from session trajectories."""

    def __init__(self, compiled_path: str | Path | None = None) -> None:
        super().__init__()
        self.predict = dspy.ChainOfThought(WikiPatternSynthesisSignature)
        if compiled_path is not None:
            path_obj = Path(compiled_path)
            if not path_obj.exists():
                raise FileNotFoundError(
                    f"Compiled WikiPatternSynthesizer state not found at: {path_obj}"
                )
            self.load(str(path_obj))

    def forward(
        self,
        session_id: str,
        total_steps: int,
        error_steps_json: str,
        wiki_context: str,
        existing_patterns_json: str = "[]",
    ) -> Any:
        return self.predict(
            session_id=session_id,
            total_steps=total_steps,
            error_steps_json=error_steps_json,
            wiki_context=wiki_context,
            existing_patterns_json=existing_patterns_json,
        )


class WikiSkillLLMAdapter:
    """Adaptable multi-provider LLM execution layer powered by DSPy."""

    def __init__(
        self,
        model: str | None = None,
        lm: Any | None = None,
        mock: bool = False,
        api_key: str | None = None,
        api_base: str | None = None,
        compiled_wiki_module_path: str | Path | None = None,
        **lm_kwargs: Any,
    ) -> None:
        self.model = model
        self._lm = lm
        self.mock = mock
        self.api_key = api_key
        self.api_base = api_base
        self.lm_kwargs = lm_kwargs
        self.wiki_synthesizer = WikiPatternSynthesizer(
            compiled_path=compiled_wiki_module_path
        )

    def resolve_model_name(self) -> str:
        """Resolve the target DSPy model string from explicit args or environment variables."""
        if self.model:
            return self.model
        env_model = os.environ.get("WIKISKILL_MODEL")
        if env_model:
            return env_model
        if os.environ.get("OPENROUTER_API_KEY"):
            return "openrouter/google/gemini-2.5-flash"
        if os.environ.get("ANTHROPIC_API_KEY"):
            return "anthropic/claude-3-5-haiku-latest"
        if os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY"):
            return "gemini/gemini-2.5-flash"
        if os.environ.get("OPENAI_API_KEY"):
            return "openai/gpt-4o-mini"
        raise LLMConfigurationError(
            "No LLM provider configured for WikiSkill. Set WIKISKILL_MODEL or one of "
            "OPENROUTER_API_KEY, ANTHROPIC_API_KEY, GEMINI_API_KEY, GOOGLE_API_KEY, or OPENAI_API_KEY, "
            "pass --model <provider/model>, or run with --mock for heuristic mode."
        )

    def get_lm(self) -> Any:
        """Return the configured DSPy LM instance, initializing it lazily if needed."""
        if self._lm is not None:
            return self._lm
        model_name = self.resolve_model_name()
        kwargs: dict[str, Any] = dict(self.lm_kwargs)
        if self.api_key:
            kwargs["api_key"] = self.api_key
        if self.api_base:
            kwargs["api_base"] = self.api_base
        self._lm = dspy.LM(model_name, **kwargs)
        return self._lm

    def synthesize_wiki_update(
        self,
        trajectory: SessionTrajectory,
        wiki_context: str,
        existing_patterns: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        """Synthesize wiki pattern updates from a session trajectory via DSPy or mock heuristics."""
        if self.mock:
            return self._heuristic_wiki_update(trajectory)

        lm = self.get_lm()
        error_steps = [
            {
                "step_number": s.step_number,
                "tool_name": s.tool_name,
                "tool_input": s.tool_input,
                "observation": s.observation,
            }
            for s in trajectory.steps
            if s.is_error
        ]

        with dspy.context(lm=lm):
            prediction = self.wiki_synthesizer(
                session_id=trajectory.session_id,
                total_steps=len(trajectory.steps),
                error_steps_json=json.dumps(error_steps),
                wiki_context=wiki_context,
                existing_patterns_json=json.dumps(existing_patterns or []),
            )

        raw_update = getattr(prediction, "wiki_update", prediction)
        if isinstance(raw_update, WikiUpdateOutput):
            parsed = raw_update
        elif isinstance(raw_update, dict):
            parsed = WikiUpdateOutput.model_validate(raw_update)
        else:
            parsed = WikiUpdateOutput.model_validate_json(str(raw_update))

        return {
            "create_patterns": [
                {"name": p.name, "content": p.content} for p in parsed.create_patterns
            ],
            "update_patterns": [
                {"name": p.name, "content": p.content} for p in parsed.update_patterns
            ],
            "update_index": {"additions": list(parsed.index_additions)},
            "append_log": parsed.append_log,
        }

    @staticmethod
    def _heuristic_wiki_update(trajectory: SessionTrajectory) -> dict[str, Any]:
        """Deterministic heuristic pattern synthesis for --mock mode."""
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
            log_entry = (
                f"Session {trajectory.session_id}: Analyzed {len(trajectory.steps)} steps "
                f"({len(error_steps)} errors); clean execution, no new patterns required."
            )
            return {
                "create_patterns": [],
                "update_patterns": [],
                "update_index": {"additions": []},
                "append_log": log_entry,
            }

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
