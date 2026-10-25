# Project Operating Guide (CLAUDE.md)

## Core Philosophy: Specification-Driven & Loop-Driven TDD
1. **Never write implementation code without a spec.**
2. **Never modify production code without a failing test.**
3. **Loop containment:** Never run open-ended bash tasks; all actions follow deterministic check loops.
4. **Documentation-only changes (e.g., README.md, comments) are exempt from spec and test loop requirements.

---

## 1. Development Lifecycle & Loop Rules

When given a task or issue, execute strictly in these four discrete phases. Do not blend phases.

### Phase 1: Specification (`/specs/<feature>.md` or `.claude/specs/<feature>.md`)
* Read the issue or user prompt.
* If a spec does not exist, draft one in `.claude/specs/<feature>.md` defining:
  - Acceptance criteria (Given/When/Then).
  - Public interfaces, signatures, and input/output contracts.
  - Failure/edge modes (invalid inputs, timeouts, exceptions).
* **Gate:** Stop and wait for user confirmation if the spec changes existing contracts.

### Phase 2: Red Loop (Test Generation)
* Write isolated unit/integration tests covering the spec requirements.
* Run the test suite:
  ```bash
  uv run pytest tests/test_<feature>.py -v
  ```
* **Assertion Gate:** Verify the tests fail for the expected reason (e.g., missing method/class, not a test syntax/import error).

### Phase 3: Green Loop (Minimal Implementation)
* Implement the minimal production code needed to satisfy the failing test.
* Avoid premature optimization or implementing speculative features outside the current test.
* Run the test suite:
  ```bash
  uv run pytest tests/test_<feature>.py -v
  ```
* **Iteration Limit:** You have a maximum of 3 correction attempts per failing test. If it does not pass after 3 tries:
  1. Halt execution.
  2. Revert recent code edits (`git checkout -- <file>`).
  3. Report the failure, the diff, and the exact error log.

### Phase 4: Refactor Loop & Verification
* Clean up code formatting, variable names, and remove dead code.
* Ensure type safety, linting, and full regression pass:
  ```bash
  uv run ruff check .
  uv run ruff format --check .
  uvx pyrefly check --summarize-errors
  uv run pytest
  ```
* Ensure no regressions exist before declaring the task complete.

---

## 2. Environment & Tool Conventions
- **Language / Framework:** Python 3.12+
- **Package Manager:** `uv` / Hatchling build backend
- **Test Runner:** `uv run pytest -v --tb=short`
- **Linter/Formatter:** `uv run ruff check . && uv run ruff format --check .`
- **Type Checker:** `uvx pyrefly check --summarize-errors`
- **Shell Runner:** Use Git Bash for command execution on Windows.

---

## 3. Agent Guardrails & File Operations
- **Atomic Commits:** Do not stage or commit code without explicit instructions.
- **No Speculative Files:** Never create utility modules or helper scripts unless explicitly specified in specs/.
- **State Preservation:** If a loop step fails twice in a row, inspect the diff rather than applying additive patches. Do not add mock fallbacks or suppress errors with empty try/except blocks.
- **Context Budgeting:** When checking test outputs, always use targeted flags (`pytest -q -k "test_name"`) rather than printing massive full-suite logs into the context window.

### Tool Execution Guardrails: File Editing
- When using the `Edit` tool, `old_string` must be an EXACT literal character-for-character match from the file, including all whitespace, indentation, and newlines.
- Never guess or approximate `old_string`. Always use `View` to inspect the exact line range immediately before calling `Edit`.
- If an `Edit` call fails, do not guess another string; use `View` to re-fetch the lines.
- If an edit spans more than 50% of a file or more than 30 lines, use whole-file overwriting via `Write` instead of multiple fragile `Edit` calls.

---

## 4. Running the WikiSkill Package & CLI

`wikiskill` is packaged as an installable tool with CLI entrypoints `wikiskill` and `wikiskill-harness`.

### 4.1 CLI Commands Reference

#### 1. Post-Session Evolution (`post-session`)
Run post-session evolution on the latest Claude Code transcript (with automated noise suppression for clean runs):
```bash
uv run wikiskill post-session [options]
# or legacy flag:
uv run wikiskill --post-session
```

Optional arguments:
- `--since <ISO-timestamp>`: Only process sessions modified at or after timestamp.
- `--project-dir <path>`: Target project directory (defaults to current working directory).
- `--wiki-dir <path>`: Custom location for wiki directory (default: `.claude/wiki`).
- `--skills-dir <path>`: Custom location for skills directory (default: `.claude/skills`).
- `--dry-run`: Preview updates without writing files.
- `--mock`: Run with synthetic trajectory.

#### 2. Project Initialization (`init`)
Scaffold `.claude/wiki/` and `.claude/skills/` in any repository:
```bash
uv run wikiskill init [--project-dir <path>]
```

#### 3. Status Inspection (`status`)
Inspect active patterns and skills:
```bash
uv run wikiskill status [--project-dir <path>]
```

#### 4. Central Hub Setup (`setup-hub`)
Initialize the central hub at `~/.claude/wikiskill-hub` for multi-workstation sync:
```bash
uv run wikiskill setup-hub --remote https://github.com/your-user/personal-wiki-skills.git
```

#### 5. Global Hub Synchronization & PR Gating (`sync`)
Synchronize universal patterns and skills with central Git hub and candidate PRs:
```bash
# Propose local universal learnings via PR candidate branch
uv run wikiskill sync --push

# Push directly to main (bypass PR gate)
uv run wikiskill sync --push --direct

# Pull latest global skills from central hub
uv run wikiskill sync --pull

# Pull and prune local skills/patterns deleted or rejected upstream
uv run wikiskill sync --pull --prune
```

#### 6. Background Watcher Daemon (`daemon`)
Monitor all Claude Code project logs continuously in the background:
```bash
# Run continuous watcher (default interval: 300s)
uv run wikiskill daemon

# Run single scan pass across all projects and exit
uv run wikiskill daemon --once

# Custom interval (e.g. 60s)
uv run wikiskill daemon --interval 60
```

### 4.2 Programmatic Python API
```python
from wikiskill import (
    GitHubSyncManager,
    WikiSkillDaemon,
    WikiSkillHarness,
)

# 1. Post-Session Evolution
harness = WikiSkillHarness(project_dir=".")
result = harness.run_post_session(since=None, dry_run=False)

# 2. Central Hub Synchronization
sync_manager = GitHubSyncManager()
sync_manager.init_hub()
sync_manager.sync_project_to_hub(".", prune=True)
sync_manager.sync_hub_to_project(".", prune=True)
```

