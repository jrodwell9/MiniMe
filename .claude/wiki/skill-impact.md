# Skill Impact Audit Log

## Session 20260831-045000
- Target Skill: `git-workflow`
- Proposal Action: `patch`
- Acceptance Outcome: `Rejected`
- Diff:
  ```diff
  --- skills/git-workflow/SKILL.md
  +++ skills/git-workflow/SKILL.md
  @@ -10,3 +10,5 @@
  + Always run git push --force on branch conflict.
  ```
- Rationale / Notes: Forced push violates safety rules; rejected by user gating.

## Session 20260831-051500
- Target Skill: `git-workflow`
- Proposal Action: `patch`
- Acceptance Outcome: `Accepted`
- Diff:
  ```diff
  --- skills/git-workflow/SKILL.md
  +++ skills/git-workflow/SKILL.md
  @@ -10,3 +10,5 @@
  + Run git fetch origin before rebasing local branches.
  ```## Session a392adc3-a92d-474d-9907-dbe94d0d2280
- Target Skill: git-workflow
- Proposal Action: patch
- Acceptance Outcome: Accepted (Mock)
- Diff: ```diff
  # Mock diff based on proposed edits
  ## Trigger
  ## Trigger
- Added by SkillProposer
```
## Session a392adc3-a92d-474d-9907-dbe94d0d2280
- Target Skill: git-workflow
- Proposal Action: patch
- Acceptance Outcome: Accepted (Mock)
- Diff: ```diff
  # Mock diff based on proposed edits
  ## Trigger
  ## Trigger
- Added by SkillProposer
```

## Session a392adc3-a92d-474d-9907-dbe94d0d2280
- Target Skill: `file-editing`
- Proposal Action: `create`
- Patterns Addressed: edit-string-mismatch-loop
- Acceptance Outcome: Accepted
- Rules Applied:
```markdown
  + Always inspect the exact line range with View immediately before Edit.
  + Never guess whitespace, indentation, or newlines in old_string.
  + If an edit spans more than 30 lines or 50% of a file, use whole-file write instead of Edit.
```

## Session a392adc3-a92d-474d-9907-dbe94d0d2280
- Target Skill: `cli-tool-execution`
- Proposal Action: `create`
- Patterns Addressed: unprefixed-python-runner-loop
- Acceptance Outcome: Accepted
- Rules Applied:
```markdown
  + Always prefix python commands and test runners with 'uv run' (e.g. 'uv run pytest', 'uv run ruff check .').
  + Never invoke bare 'pytest' or 'python' directly in shell subshells.
```

## Session a392adc3-a92d-474d-9907-dbe94d0d2280
- Target Skill: `dependency-management`
- Proposal Action: `create`
- Patterns Addressed: missing-dependency-import-loop
- Acceptance Outcome: Accepted
- Rules Applied:
```markdown
  + Add new project dependencies using 'uv add <package>'.
  + Ensure package imports are aligned with workspace root hierarchy.
```
