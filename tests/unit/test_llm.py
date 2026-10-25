from pathlib import Path
from unittest.mock import MagicMock

import dspy
import pytest

from wikiskill.llm import (
    LLMConfigurationError,
    PatternEntry,
    WikiPatternSynthesizer,
    WikiSkillLLMAdapter,
    WikiUpdateOutput,
)
from wikiskill.models import SessionTrajectory, TrajectoryStep


def test_llm_adapter_raises_when_unconfigured(monkeypatch):
    for key in (
        "WIKISKILL_MODEL",
        "OPENROUTER_API_KEY",
        "ANTHROPIC_API_KEY",
        "GEMINI_API_KEY",
        "GOOGLE_API_KEY",
        "OPENAI_API_KEY",
    ):
        monkeypatch.delenv(key, raising=False)

    adapter = WikiSkillLLMAdapter(mock=False)
    trajectory = SessionTrajectory(
        session_id="sess-unconf",
        timestamp="2026-10-24T12:00:00Z",
        model_routed="claude-3-7-sonnet",
        steps=[
            TrajectoryStep(
                step_number=1,
                tool_name="Bash",
                tool_input={"command": "pytest"},
                observation="command not found",
                is_error=True,
            )
        ],
    )
    with pytest.raises(LLMConfigurationError):
        adapter.synthesize_wiki_update(trajectory, "# Index\n")


@pytest.mark.parametrize(
    ("env_var", "expected_prefix"),
    [
        ("OPENROUTER_API_KEY", "openrouter/"),
        ("ANTHROPIC_API_KEY", "anthropic/"),
        ("GEMINI_API_KEY", "gemini/"),
        ("GOOGLE_API_KEY", "gemini/"),
        ("OPENAI_API_KEY", "openai/"),
    ],
)
def test_llm_adapter_resolves_provider_from_env(monkeypatch, env_var, expected_prefix):
    for key in (
        "WIKISKILL_MODEL",
        "OPENROUTER_API_KEY",
        "ANTHROPIC_API_KEY",
        "GEMINI_API_KEY",
        "GOOGLE_API_KEY",
        "OPENAI_API_KEY",
    ):
        monkeypatch.delenv(key, raising=False)

    monkeypatch.setenv(env_var, "test-dummy-key")
    adapter = WikiSkillLLMAdapter(mock=False)
    resolved = adapter.resolve_model_name()
    assert resolved.startswith(expected_prefix)


def test_llm_adapter_explicit_model_and_wikiskill_model_env(monkeypatch):
    monkeypatch.setenv("WIKISKILL_MODEL", "gemini/gemini-2.5-pro")
    adapter_env = WikiSkillLLMAdapter(mock=False)
    assert adapter_env.resolve_model_name() == "gemini/gemini-2.5-pro"

    adapter_explicit = WikiSkillLLMAdapter(
        model="anthropic/claude-3-7-sonnet-latest", mock=False
    )
    assert adapter_explicit.resolve_model_name() == "anthropic/claude-3-7-sonnet-latest"


def test_llm_adapter_dspy_wiki_synthesis_execution():
    fake_lm = MagicMock(spec=dspy.LM)
    adapter = WikiSkillLLMAdapter(lm=fake_lm, mock=False)

    expected_output = WikiUpdateOutput(
        create_patterns=[
            PatternEntry(
                name="custom-timeout-loop",
                content="# Custom Timeout Loop\n\n## Problem\nTimeout.\n\n## Root Cause\nSlow query.\n\n## Fix\nAdd index.",
            )
        ],
        update_patterns=[],
        index_additions=[
            "- [custom-timeout-loop](wiki/patterns/custom-timeout-loop.md): Slow query timeout."
        ],
        append_log="Session sess-99: Extracted custom-timeout-loop.",
    )
    adapter.wiki_synthesizer = MagicMock(
        return_value=dspy.Prediction(wiki_update=expected_output)
    )

    trajectory = SessionTrajectory(
        session_id="sess-99",
        timestamp="2026-10-24T12:00:00Z",
        model_routed="claude-3-7-sonnet",
        steps=[
            TrajectoryStep(
                step_number=1,
                tool_name="Bash",
                tool_input={"command": "run_db_query"},
                observation="TimeoutError: query exceeded 30s",
                is_error=True,
            )
        ],
    )

    res = adapter.synthesize_wiki_update(trajectory, "# Wiki Pattern Index\n")
    assert len(res["create_patterns"]) == 1
    assert res["create_patterns"][0]["name"] == "custom-timeout-loop"
    assert res["update_index"]["additions"] == [
        "- [custom-timeout-loop](wiki/patterns/custom-timeout-loop.md): Slow query timeout."
    ]
    assert res["append_log"] == "Session sess-99: Extracted custom-timeout-loop."
    adapter.wiki_synthesizer.assert_called_once()


def test_dspy_synthesizer_missing_compiled_path_raises(tmp_path: Path):
    missing_file = tmp_path / "non_existent_weights.json"
    with pytest.raises(FileNotFoundError):
        WikiPatternSynthesizer(compiled_path=missing_file)


def test_llm_adapter_passes_existing_patterns_to_dspy():
    fake_lm = MagicMock(spec=dspy.LM)
    adapter = WikiSkillLLMAdapter(lm=fake_lm, mock=False)

    adapter.wiki_synthesizer = MagicMock(
        return_value=dspy.Prediction(
            wiki_update=WikiUpdateOutput(
                create_patterns=[],
                update_patterns=[
                    PatternEntry(
                        name="uv-dependency-loop",
                        content="# UV Dependency Loop\n\n## Problem\n...\n\n## Root Cause\n...\n\n## Fix\n...",
                    )
                ],
                index_additions=[],
                append_log="Updated uv-dependency-loop.",
            )
        )
    )
    trajectory = SessionTrajectory(
        session_id="sess-consolidate",
        timestamp="2026-10-24T12:00:00Z",
        model_routed="claude-3-7-sonnet",
        steps=[
            TrajectoryStep(
                step_number=1,
                tool_name="Bash",
                tool_input={"command": "uv add --dry-run dspy"},
                observation="unexpected argument '--dry-run'",
                is_error=True,
            )
        ],
    )
    existing_patterns = [
        {"name": "uv-dependency-loop", "content": "# UV Dependency Loop"}
    ]
    wiki_res = adapter.synthesize_wiki_update(
        trajectory,
        "# Wiki Pattern Index\n",
        existing_patterns=existing_patterns,
    )
    assert len(wiki_res["update_patterns"]) == 1
    assert wiki_res["update_patterns"][0]["name"] == "uv-dependency-loop"
    wiki_call_kwargs = adapter.wiki_synthesizer.call_args.kwargs
    assert "existing_patterns_json" in wiki_call_kwargs
    assert "uv-dependency-loop" in wiki_call_kwargs["existing_patterns_json"]
