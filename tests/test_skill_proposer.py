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
