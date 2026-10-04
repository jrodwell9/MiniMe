from pathlib import Path

import pytest

from wikiskill.skill_proposer import SkillProposer


@pytest.fixture
def skill_proposer(tmp_path):
    skills_path = tmp_path / ".claude" / "skills"
    skills_path.mkdir(parents=True)
    return SkillProposer(base_path=str(skills_path))


def test_skill_proposer_init(skill_proposer, tmp_path):
    assert skill_proposer.base_path == str(tmp_path / ".claude" / "skills")


def test_skill_proposer_call_llm_for_skill_proposal_from_patterns(skill_proposer):
    patterns = [
        {
            "name": "edit-string-mismatch-loop",
            "content": "# Edit String Mismatch\n\n## Fix\nInspect lines before edit.",
        },
        {
            "name": "unprefixed-python-runner-loop",
            "content": "# Unprefixed Python Runner\n\n## Fix\nAlways run with uv run.",
        },
    ]
    proposals = skill_proposer.call_llm_for_skill_proposal(
        "Wiki Index context", patterns=patterns
    )
    assert len(proposals) >= 2
    skill_names = [p["name"] for p in proposals]
    assert "file-editing" in skill_names
    assert "cli-tool-execution" in skill_names


def test_skill_proposer_call_llm_for_skill_proposal_empty_patterns(skill_proposer):
    proposals = skill_proposer.call_llm_for_skill_proposal(
        "Wiki Index context", patterns=[]
    )
    assert proposals == []

    proposals_none = skill_proposer.call_llm_for_skill_proposal(
        "Wiki Index context", patterns=None
    )
    assert proposals_none == []


def test_skill_proposer_apply_skill_proposal_create(skill_proposer, tmp_path):
    proposal = {
        "action": "create",
        "name": "file-editing",
        "description": "Rules for safe and accurate file modifications.",
        "rules": [
            "Always inspect the exact line range with View immediately before Edit.",
            "If an edit spans more than 30 lines, use whole-file write.",
        ],
        "patterns_addressed": ["edit-string-mismatch-loop"],
    }
    skill_proposer.apply_skill_proposal(proposal)

    skill_dir = Path(skill_proposer.base_path) / "file-editing"
    assert (skill_dir / "SKILL.md").exists()
    assert (skill_dir / "PURPOSE.md").exists()

    skill_content = (skill_dir / "SKILL.md").read_text(encoding="utf-8")
    assert "name: file-editing" in skill_content
    assert "Always inspect the exact line range" in skill_content

    purpose_content = (skill_dir / "PURPOSE.md").read_text(encoding="utf-8")
    assert "edit-string-mismatch-loop" in purpose_content


def test_skill_proposer_rejects_tombstoned_proposal(skill_proposer):
    patterns = [
        {
            "name": "edit-string-mismatch-loop",
            "content": "# Edit String Mismatch\n\n## Fix\nInspect lines before edit.",
        },
        {
            "name": "unprefixed-python-runner-loop",
            "content": "# Unprefixed Python Runner\n\n## Fix\nAlways run with uv run.",
        },
    ]

    wiki_context_with_rejection = """
# Wiki Index
- [edit-string-mismatch-loop](wiki/patterns/edit-string-mismatch-loop.md)

# Skill Impact Log
## Session sess-old-001
- Target Skill: `file-editing`
- Status: Rejected
- Patterns Addressed: edit-string-mismatch-loop
- Rationale: User prefers manual edits for this repository.
"""

    proposals = skill_proposer.call_llm_for_skill_proposal(
        wiki_context_with_rejection, patterns=patterns
    )
    skill_names = [p["name"] for p in proposals]

    # file-editing was rejected, so only cli-tool-execution should be proposed
    assert "file-editing" not in skill_names
    assert "cli-tool-execution" in skill_names


def test_skill_proposer_rejects_frontmatter_tombstone(skill_proposer, tmp_path):
    rejected_dir = tmp_path / ".claude" / "skills" / "file-editing"
    rejected_dir.mkdir(parents=True, exist_ok=True)
    (rejected_dir / "SKILL.md").write_text(
        "---\nname: file-editing\nstatus: rejected\n---\n", encoding="utf-8"
    )

    patterns = [
        {
            "name": "edit-string-mismatch-loop",
            "content": "# Edit String Mismatch",
        },
        {
            "name": "unprefixed-python-runner-loop",
            "content": "# Unprefixed Python Runner",
        },
    ]

    proposals = skill_proposer.call_llm_for_skill_proposal(patterns=patterns)
    skill_names = [p["name"] for p in proposals]

    assert "file-editing" not in skill_names
    assert "cli-tool-execution" in skill_names
