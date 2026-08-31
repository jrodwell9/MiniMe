from unittest.mock import patch

import pytest

from ..scripts.skill_proposer import SkillProposer


@pytest.fixture
def skill_proposer():
    return SkillProposer()


# Test cases for SkillProposer
def test_skill_proposer_init(skill_proposer):
    assert skill_proposer.base_path == ".claude/skills"


@patch("MiniMe.scripts.skill_proposer.SkillProposer.call_llm_for_skill_proposal")
def test_skill_proposer_call_llm_for_skill_proposal(mock_call_llm, skill_proposer):
    mock_call_llm.return_value = {
        "action": "patch",
        "name": "git-workflow",
        "edits": [
            {
                "file": "git-workflow/SKILL.md",
                "old_string": "## Trigger",
                "new_string": "## Trigger\n- Added by SkillProposer",
            }
        ],
    }
    response = skill_proposer.call_llm_for_skill_proposal("mock wiki context")
    assert response["action"] == "patch"
    assert response["name"] == "git-workflow"
    assert len(response["edits"]) == 1
    assert response["edits"][0]["file"] == "git-workflow/SKILL.md"
