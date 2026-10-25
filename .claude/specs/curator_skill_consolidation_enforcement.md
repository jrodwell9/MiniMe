# Technical Specification: Curator Skill Consolidation Enforcement & Fallback Reconciliation

## 1. Problem Statement & Failure Mode Analysis
During post-session consolidation on sessions with multiple diagnosed failure patterns (e.g., Antigravity session `55c65f04-d660-4fa7-a079-5cc8c5e80608` with 8 patterns):
1. **ReAct Loop Short-Circuit & Pattern Echoing**:
   The `CuratorLocalSessionSignature` prompt lacked explicit negative constraints against returning raw failure pattern names in the `proposals` list. Consequently, the ReAct LLM exhausted its iteration budget inspecting environment context and echoed raw pattern slugs (e.g. `file-not-found-access-error` with `group: None`) directly in `proposals`.
2. **Missing Disk Persistence**:
   The ReAct agent failed to execute `write_local_file("skills/<name>/SKILL.md", ...)` for the domain skills. `WikiSkillCuratorAgent.curate_local_session` blindly returned the raw JSON output without verifying that any skill files were actually modified or created on disk.
3. **Orphaned Pattern PRs in `sync --push`**:
   Because `.agents/skills/` had no file diff, `wikiskill sync --push` detected zero skill changes in the hub repository, marked all pattern files as `unclaimed_patterns`, and created a standalone patterns PR without proposing or updating any operational skills.

---

## 2. Proposed Architecture & Component Contracts

### 2.1 Reinforced Signature (`CuratorLocalSessionSignature`)
- Enhance the system docstring and parameter descriptions with explicit negative constraints:
  - "Under NO circumstances should `proposals` list raw pattern slugs or failure pattern names. Each entry in `proposals` MUST be a broad operational domain skill (e.g., `file-editing`, `cli-tool-execution`, `dependency-management`)."
  - "When `dry_run=False`, you MUST invoke `write_local_file('skills/<name>/SKILL.md', ...)` and `write_local_file('skills/<name>/PURPOSE.md', ...)` to persist the updated skill and its frontmatter/rules to disk."

### 2.2 Skill Proposal Validator & File Persistence
In `WikiSkillCuratorAgent.curate_local_session`:
- Filter out any proposal whose `name` matches an extracted pattern slug or where `name` is not a valid skill identifier.
- For each valid proposal returned by the ReAct agent:
  - If `dry_run=False` and the skill files have not yet been written to disk (or are missing the new rules/patterns), the curator automatically constructs and writes `skills/<name>/SKILL.md` and `skills/<name>/PURPOSE.md` using `tools.write_local_file`.

### 2.3 Deterministic Pattern-to-Skill Fallback Reconciliation
If the ReAct agent returns zero valid skill proposals or fails to update any skills on disk:
- The curator triggers `reconcile_patterns_into_skills(tools, session_id, patterns, dry_run)`:
  - Maps pattern slugs and text to canonical domain skills and groups:
    - `file-*`, `system-*` $\to$ `file-editing` (`group: global`)
    - `cli-*`, `*subcommand*`, `*command-not-found*`, `unprefixed-*` $\to$ `cli-tool-execution` (`group: python`)
    - `python-*`, `*import*`, `*module*`, `*dependency*`, `*linting*` $\to$ `dependency-management` (`group: python`)
    - `refactor-*`, `*contract*`, `*mismatch*` $\to$ `refactoring-api-management` (`group: python`)
    - `test-*`, `*assertion*` $\to$ `test-debugging` (`group: python`)
    - `git-*` $\to$ `git-workflow` (`group: global`)
    - `llm-*`, `*model-config*` $\to$ `llm-configuration` (`group: ai-engineer`)
    - `*plugin*`, `*marketplace*`, `*validation*` $\to$ `wikiskill` (`group: global`)
  - Merges the pattern into the target skill's `patterns_addressed` in frontmatter and appends rule / problem / fix sections to `SKILL.md` and `PURPOSE.md`.
  - When `dry_run=False`, writes the updated skill files via `tools.write_local_file`.
  - Returns the reconciled proposals with valid `name`, `group`, `rules`, and `patterns_addressed`.

---

## 3. Acceptance Criteria (Given / When / Then)

### Scenario 1: Curator Rejects Pattern Echoes and Reconciles Skills on Disk
- **Given** an extracted patterns list containing `file-not-found-access-error` and `cli-external-command-not-found`,
- **When** the ReAct LLM returns `proposals` containing raw pattern names with `group: None` and does not call `write_local_file`,
- **Then**:
  - The curator detects the invalid pattern-name proposals,
  - Reconciles `file-not-found-access-error` into `file-editing` (`group: global`) and `cli-external-command-not-found` into `cli-tool-execution` (`group: python`),
  - When `dry_run=False`, writes the updated `SKILL.md` files to disk with `patterns_addressed` containing the pattern slugs,
  - Returns valid skill proposals with non-None `group`, `rules`, and `patterns_addressed`.

### Scenario 2: Dry Run Mode Preserves Disk State
- **Given** extracted patterns and `dry_run=True`,
- **When** `curate_local_session` executes with fallback reconciliation,
- **Then** valid skill proposals are returned with `status: dry_run`, but no files in `.agents/skills` are written to disk.

### Scenario 3: Real Run Generates Skill Proposals in `sync --push`
- **Given** a workspace where `curate_local_session` consolidated patterns into `file-editing` and `cli-tool-execution` on disk,
- **When** `wikiskill sync --push` runs,
- **Then** `skills_changed` detects the updated skills in the hub, and isolated skill proposal PR branches (`proposal/skill-file-editing-*`, `proposal/skill-cli-tool-execution-*`) are generated with their addressed patterns bundled.

