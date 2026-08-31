# Technical Specification: Local Post-Session WikiSkill Harness for Claude Code (Native Session Transcript Adapter)

## 1. System Overview & Architecture
This specification defines the design and implementation of an automated self-evolution harness script (`wikiskill_harness.py`). The system integrates the **WikiSkill** framework (Tang et al., 2026) with **Claude Code** to compile active agent session experiences into persistent, compounding knowledge across interactive coding sessions.

The architecture comprises three functional layers:
1. **Raw Layer (Claude Code Native Session Adapter)**: Direct parser (`ClaudeCodeLogAdapter`) querying Claude Code's native, persistent session JSONL transcripts under `~/.claude/projects/<project-slug>/` for the latest session trajectory telemetry.
2. **Wiki Layer (`wiki/`)**: Maintains persistent, compounding markdown pattern files, a consolidated index (`index.md`), an evolution log (`logs.md`), and a ground-truth proposal audit trail (`skill-impact.md`).
3. **Skills Layer (`skills/`)**: Contains active Anthropic-formatted skill directories (`SKILL.md` and `PURPOSE.md`).

---

## 2. Directory & Schema Definitions

### 2.1 Workspace Hierarchy
```
.claude/
├── wiki/
│   ├── index.md                          # Concise pattern catalog
│   ├── logs.md                           # Chronological evolution log
│   ├── skill-impact.md                   # Audit log of proposed diffs & decisions
│   └── patterns/                         # Detailed root-cause & strategy pages
│       ├── <pattern-name-1>.md
│       └── <pattern-name-2>.md
└── skills/
    └── <skill-name>/
        ├── SKILL.md                      # Operational instructions & frontmatter
        └── PURPOSE.md                    # Origin, patterns addressed & history
```

---

### 2.2 Wiki Schema & Formats

#### `wiki/index.md`
Must strictly adhere to the single-line pattern reference format:
```markdown
# Wiki Pattern Index

- [take-examine-move-loop](wiki/patterns/take-examine-move-loop.md): Agent takes item, examines it, puts it back. Cause: lack of destination checking. Fix: enforce destination verification before examine step.
- [cli-syntax-error-loop](wiki/patterns/cli-syntax-error-loop.md): Repeated execution of invalid shell flags. Cause: outdated CLI docs in context. Fix: pass --help flag prior to multi-flag execution.
```

#### `wiki/skill-impact.md`
Records the full audit history of all proposed skill changes to prevent repeating rejected approaches:
```markdown
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
```

#### `skills/<skill-name>/SKILL.md`
```markdown
---
name: git-workflow
description: Best practices for git branch management and safe updates.
---

# Operational Rules

## Trigger
Apply when modifying local branches or sync state with remotes.

## Rule: Safe Remote Syncing
- Always execute `git fetch origin` before rebasing.
- Never use `--force` unless explicitly instructed.
```

---

## 3. Core Workflow Components & Algorithms

### 3.1 Step 1: Claude Code Native Log Adapter (`ClaudeCodeLogAdapter`)
* **Log Source**: Queries native persistent session files located at:
  `~/.claude/projects/<sanitized-project-path>/<session-id>.jsonl`
* **Path Sanitization**: Translates filesystem paths to Claude Code project directory names (e.g. `C:\Users\jrodw\Documents\MiniMe` -> `C--Users-jrodw-Documents-MiniMe`).
* **In-Memory Normalization**:
  * Scans the latest session file matching the optional `--since` ISO timestamp constraint.
  * Streams JSONL entries, recording `sessionId`, `timestamp`, `model_routed`, and pairing `tool_use` + `tool_result` into `TrajectoryStep`.

---

### 3.2 Step 2: Wiki Maintainer (Pattern Consolidation)
* Triggered post-session with input containing the in-memory `SessionTrajectory` and current `wiki/` context.
* **Trajectory Error & Pattern Analysis**:
  * Scans all `steps` where `is_error == True` and categorizes recurring failure modes:
    1. **`edit-string-mismatch-loop`**: Tool `Edit` failing with string mismatch or target not found.
    2. **`unprefixed-python-runner-loop`**: Tool `Bash` failing with exit code 127 (`command not found`) when invoking tools directly instead of via `uv run`.
    3. **`test-assertion-failure-loop`**: Tool `Bash` failing with exit code 1 / assertion failures when running test suites.
    4. **`missing-dependency-import-loop`**: Tool failures with `ModuleNotFoundError` or missing packages.
    5. **`generic-tool-error-loop`**: Unclassified tool execution errors.
  * Generates markdown pattern files under `wiki/patterns/<pattern-name>.md` with structured sections:
    - `# Pattern Title`
    - `## Problem`: Description of error observation, frequency, and sample tool inputs.
    - `## Root Cause`: Technical explanation of why the failure occurred.
    - `## Fix`: Concrete instructions on how to avoid or resolve the issue.
  * Appends one-line pattern summaries to `wiki/index.md`.
  * Appends a summary log entry to `wiki/logs.md`.

#### Acceptance Criteria:
- **Given** a `SessionTrajectory` with 96 error steps including `Edit` string mismatches and `Bash` command not found errors,
- **When** `wiki_manager.call_llm_for_wiki_update(trajectory, current_index)` is invoked,
- **Then** it generates concrete `create_patterns` entries (e.g. `edit-string-mismatch-loop.md`, `unprefixed-python-runner-loop.md`), index additions, and a log entry.
- **When** `wiki_manager.process_llm_wiki_response(response)` is invoked,
- **Then** files are created in `wiki/patterns/`, `wiki/index.md` is updated, and `wiki/logs.md` is appended.

---

### 3.3 Step 3: Skill Proposer (Proposal & Application)
* **Skill Generation**:
  * Analyzes the newly created/updated pattern files.
  * For each pattern, formulates operational rules and generates structured skill proposals (`create` or `patch`):
    - `edit-string-mismatch-loop` -> creates/patches `skills/file-editing/SKILL.md` and `PURPOSE.md`.
    - `unprefixed-python-runner-loop` -> creates/patches `skills/cli-tool-execution/SKILL.md` and `PURPOSE.md`.
* **Skill Application**:
  * `skill_proposer.apply_skill_proposal(proposal)` writes the `SKILL.md` and `PURPOSE.md` files to `.claude/skills/<skill-name>/`.

#### Acceptance Criteria:
- **Given** proposed skill changes for `file-editing` or `cli-tool-execution`,
- **When** `skill_proposer.apply_skill_proposal(proposal)` is called,
- **Then** `.claude/skills/<skill-name>/SKILL.md` is written with valid frontmatter and operational rules, and `PURPOSE.md` is created with pattern history.

---

### 3.4 Step 4: Gating & Audit Logging
* `wikiskill_harness.py` applies the proposals and appends a detailed audit record with diffs to `wiki/skill-impact.md`.

---

## 4. Teardown Hook & CLI Integration
```bash
uv run scripts/wikiskill_harness.py --post-session
```
Or with `--since`:
```bash
uv run scripts/wikiskill_harness.py --post-session --since "2026-08-31T12:00:00Z"
```
