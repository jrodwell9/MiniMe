from pathlib import Path
from typing import Any

from .sync import _parse_frontmatter


class SkillProposer:
    def __init__(self, base_path: str = ".claude/skills"):
        self.base_path = base_path

    def initialize_skills(self) -> None:
        """Ensure skills directory exists."""
        Path(self.base_path).mkdir(parents=True, exist_ok=True)

    def _extract_rejected_entities(
        self, wiki_context: str = ""
    ) -> tuple[set[str], set[str]]:
        """Extract rejected skills and patterns from skill frontmatter and wiki context."""
        rejected_skills = set()
        rejected_patterns = set()

        # 1. Inspect existing skill frontmatters on disk
        skills_path = Path(self.base_path)
        if skills_path.exists():
            for s_dir in skills_path.iterdir():
                if s_dir.is_dir() and (s_dir / "SKILL.md").exists():
                    try:
                        content = (s_dir / "SKILL.md").read_text(encoding="utf-8")
                        lower_content = content.lower()
                        if (
                            "status: rejected" in lower_content
                            or "status: deprecated" in lower_content
                        ):
                            rejected_skills.add(s_dir.name)
                    except OSError:
                        pass

        # 2. Inspect wiki context if provided (for backward compatibility and logs)
        if wiki_context:
            sections = wiki_context.split("## Session")
            for sec in sections:
                lower_sec = sec.lower()
                if "rejected" in lower_sec or "deprecated" in lower_sec:
                    for line in sec.splitlines():
                        if "target skill:" in line.lower() or "skill:" in line.lower():
                            parts = line.split(":", 1)
                            if len(parts) > 1:
                                skill_name = parts[1].strip().strip("`").strip()
                                if skill_name:
                                    rejected_skills.add(skill_name)
                        if (
                            "patterns addressed:" in line.lower()
                            or "patterns:" in line.lower()
                            or "pattern:" in line.lower()
                        ):
                            parts = line.split(":", 1)
                            if len(parts) > 1:
                                for p in parts[1].split(","):
                                    p_clean = p.strip().strip("`").strip()
                                    if p_clean:
                                        rejected_patterns.add(p_clean)

        return rejected_skills, rejected_patterns

    def call_llm_for_skill_proposal(
        self,
        wiki_context: str = "",
        patterns: list[dict[str, Any]] | None = None,
    ) -> list[dict[str, Any]]:
        """
        Synthesize newly consolidated wiki patterns into actionable Anthropic-style skill proposals.
        If no actionable patterns are provided, return an empty list without creating dummy skills.
        Guards against re-proposing skills or patterns that were rejected in skill frontmatter or wiki_context.
        """
        if not patterns:
            return []

        rejected_skills, rejected_patterns = self._extract_rejected_entities(
            wiki_context
        )

        active_patterns = [
            p for p in patterns if p.get("name") not in rejected_patterns
        ]
        if not active_patterns:
            return []

        proposals: list[dict[str, Any]] = []
        pattern_names = [p["name"] for p in active_patterns]

        if (
            "edit-string-mismatch-loop" in pattern_names
            and "file-editing" not in rejected_skills
        ):
            proposals.append(
                {
                    "action": "create",
                    "name": "file-editing",
                    "description": "Best practices and guardrails for safe, exact file modifications.",
                    "status": "active",
                    "rules": [
                        "Always inspect the exact line range with View immediately before Edit.",
                        "Never guess whitespace, indentation, or newlines in old_string.",
                        "If an edit spans more than 30 lines or 50% of a file, use whole-file write instead of Edit.",
                    ],
                    "patterns_addressed": ["edit-string-mismatch-loop"],
                }
            )

        if (
            "unprefixed-python-runner-loop" in pattern_names
            and "cli-tool-execution" not in rejected_skills
        ):
            proposals.append(
                {
                    "action": "create",
                    "name": "cli-tool-execution",
                    "description": "Rules for executing python tools, test runners, and linters in the project environment.",
                    "status": "active",
                    "rules": [
                        "Always prefix python commands and test runners with 'uv run' (e.g. 'uv run pytest', 'uv run ruff check .').",
                        "Never invoke bare 'pytest' or 'python' directly in shell subshells.",
                    ],
                    "patterns_addressed": ["unprefixed-python-runner-loop"],
                }
            )

        if (
            "missing-dependency-import-loop" in pattern_names
            and "dependency-management" not in rejected_skills
        ):
            proposals.append(
                {
                    "action": "create",
                    "name": "dependency-management",
                    "description": "Standards for adding dependencies and organizing package imports.",
                    "status": "active",
                    "rules": [
                        "Add new project dependencies using 'uv add <package>'.",
                        "Ensure package imports are aligned with workspace root hierarchy.",
                    ],
                    "patterns_addressed": ["missing-dependency-import-loop"],
                }
            )

        return proposals

    def apply_skill_proposal(
        self, proposal: dict[str, Any], session_id: str | None = None
    ) -> None:
        """
        Write or update the SKILL.md and PURPOSE.md files in the skills directory with frontmatter metadata.
        Preserves existing status, origin_session, and patterns_addressed if present.
        """
        skill_dir = Path(self.base_path) / proposal["name"]
        skill_dir.mkdir(parents=True, exist_ok=True)

        skill_file = skill_dir / "SKILL.md"
        purpose_file = skill_dir / "PURPOSE.md"

        existing_origin = ""
        existing_status = ""
        existing_patterns: list[str] = []

        if skill_file.exists():
            try:
                content = skill_file.read_text(encoding="utf-8")
                fm = _parse_frontmatter(content)
                existing_origin = fm.get("origin_session", "")
                existing_status = fm.get("status", "")
                raw_pats = fm.get("patterns_addressed") or fm.get("patterns") or []
                if isinstance(raw_pats, str):
                    existing_patterns = [raw_pats]
                else:
                    existing_patterns = list(raw_pats)
            except OSError:
                pass

        origin = (
            proposal.get("origin_session")
            or existing_origin
            or session_id
            or "in-flight"
        )
        status = proposal.get("status") or existing_status or "active"

        prop_patterns = proposal.get("patterns_addressed", [])
        combined_patterns = list(dict.fromkeys(prop_patterns + existing_patterns))
        patterns_yaml = "\n".join(f"  - {pat}" for pat in combined_patterns)
        patterns_markdown = "\n".join(f"- `{pat}`" for pat in combined_patterns)

        rules_markdown = "\n".join(f"- {rule}" for rule in proposal.get("rules", []))

        skill_content = f"""---
name: {proposal["name"]}
description: {proposal.get("description", "")}
status: {status}
origin_session: {origin}
patterns_addressed:
{patterns_yaml}
---

# Operational Rules

## Trigger
Apply when working with {proposal["name"]} operations in this codebase.

## Rules
{rules_markdown}
"""
        with open(skill_file, "w", encoding="utf-8") as f:
            f.write(skill_content)
        print(f"Applied skill update: {skill_file}")

        purpose_content = f"""# Purpose & Origin

## Origin
Generated by WikiSkill Harness following post-session pattern analysis.
Origin Session: {origin or "N/A"}
Status: {status}

## Patterns Addressed
{patterns_markdown}
"""
        with open(purpose_file, "w", encoding="utf-8") as f:
            f.write(purpose_content)
        print(f"Applied skill purpose: {purpose_file}")
