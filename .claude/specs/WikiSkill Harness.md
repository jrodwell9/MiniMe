# Technical Specification: WikiSkill Package & CLI Harness for Claude Code Agent Sessions

## 1. System Overview & Architecture
This specification defines the design and implementation of **WikiSkill** (`wikiskill`), an installable Python package and CLI tool. The system integrates the **WikiSkill** framework (Tang et al., 2026) with **Claude Code** to compile active agent session experiences into persistent, compounding knowledge across interactive coding sessions.

The package enables drop-in execution across any repository via:
- **CLI Commands**: `wikiskill post-session` (or `wikiskill --post-session`), `wikiskill init`, and `wikiskill status`.
- **Python Library**: Programmatic import via `from wikiskill import WikiSkillHarness, ClaudeCodeLogAdapter, WikiManager, SkillProposer`.

---

## 2. Package & Directory Structure

### 2.1 Package Layout (`src/wikiskill/`)
```
src/
└── wikiskill/
    ├── __init__.py               # Top-level exports and version definition
    ├── cli.py                    # CLI command-line interface & argument parser
    ├── dataclasses.py            # SessionTrajectory and TrajectoryStep models
    ├── claude_log_adapter.py     # Session JSONL parser and path slug resolver
    ├── wiki_manager.py           # Wiki maintainer & pattern synthesizer
    ├── skill_proposer.py         # Skill synthesizer & updater
    └── harness.py                # Core WikiSkillHarness runner orchestrator
```

### 2.2 Target Workspace Structure (`.claude/`)
```
<project-root>/
└── .claude/
    ├── wiki/
    │   ├── index.md              # Consolidated pattern index
    │   ├── logs.md               # Chronological evolution log
    │   ├── skill-impact.md       # Audit trail of proposed diffs & decisions
    │   └── patterns/             # Detailed root-cause & strategy pages
    │       ├── <pattern-1>.md
    │       └── <pattern-2>.md
    └── skills/
        └── <skill-name>/
            ├── SKILL.md          # Active Anthropic-formatted operational rules
            └── PURPOSE.md        # Origin, patterns addressed & history
```

---

## 3. CLI Specification & Public Interface

### 3.1 CLI Entrypoint (`wikiskill` / `wikiskill-harness`)
Defined in `pyproject.toml`:
```toml
[project.scripts]
wikiskill = "wikiskill.cli:main"
wikiskill-harness = "wikiskill.cli:main"
```

### 3.2 CLI Commands & Flags

#### 1. `post-session` (or `--post-session`)
Executes the self-evolution loop on the latest session transcript for the target project.
- **Flags**:
  - `--since <iso-timestamp>`: Process only sessions modified after `<timestamp>` (e.g. `2026-08-31T12:00:00Z`).
  - `--project-dir <path>`: Root directory of target project (default: current working directory `Path.cwd()`).
  - `--wiki-dir <path>`: Custom location for wiki directory (default: `<project-dir>/.claude/wiki`).
  - `--skills-dir <path>`: Custom location for skills directory (default: `<project-dir>/.claude/skills`).
  - `--claude-dir <path>`: Custom Claude home directory (default: `~/.claude`).
  - `--mock`: Run with synthetic trajectory for testing/sandbox environments.
  - `--dry-run`: Parse session and generate proposals without writing changes to disk.
  - `-v, --verbose`: Enable verbose debug logging.

#### 2. `init`
Scaffolds the `.claude/wiki/` (index.md, logs.md, skill-impact.md, patterns/) and `.claude/skills/` directories in the target project.

#### 3. `status`
Inspects and displays active wiki patterns and generated skills for the project.

---

## 4. Acceptance Criteria (Given / When / Then)

### 4.1 Signal Gating & Noise Suppression
1. **Clean Session Handling (No Jargon / No Dummy Skills)**:
   - **Given** a session trajectory with 0 errors or no recurring failure loops,
   - **When** `wiki_manager.call_llm_for_wiki_update(trajectory)` is called,
   - **Then** `create_patterns` is empty (`[]`), `update_index["additions"]` is empty (`[]`), and a clean execution note is appended to `wiki/logs.md`.
   - **When** `skill_proposer.call_llm_for_skill_proposal(wiki_context, patterns=[])` is called,
   - **Then** `proposals` is empty (`[]`), and no skill files or pattern files are created on disk.

2. **Actionable Failure Pattern Handling**:
   - **Given** a session trajectory with genuine tool errors (e.g. `Edit` string mismatches or `Bash` command not found),
   - **When** `harness.run_post_session()` is executed,
   - **Then** specific pattern files (e.g. `edit-string-mismatch-loop.md`) and operational skills (e.g. `file-editing`) are generated.

3. **Multi-Repository Path Overrides**:
   - **Given** `--project-dir <other_repo_path>`,
   - **When** `wikiskill post-session --project-dir <other_repo_path>` is run,
   - **Then** the adapter resolves the slug for `<other_repo_path>` and updates `<other_repo_path>/.claude/wiki` and `<other_repo_path>/.claude/skills`.

---

## 5. Python API Contract
```python
from wikiskill import (
    ClaudeCodeLogAdapter,
    SessionTrajectory,
    SkillProposer,
    TrajectoryStep,
    WikiManager,
    WikiSkillHarness,
)

harness = WikiSkillHarness(
    project_dir=".",
    wiki_dir=".claude/wiki",
    skills_dir=".claude/skills",
)
result = harness.run_post_session(since=None, dry_run=False)
```
