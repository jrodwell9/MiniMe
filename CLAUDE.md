# Project Operating Guide (CLAUDE.md)

## Core Philosophy: Specification-Driven & Loop-Driven TDD
1. **Never write implementation code without a spec.**
2. **Never modify production code without a failing test.**
3. **Loop containment:** Never run open-ended bash tasks; all actions follow deterministic check loops.

---

## 1. Development Lifecycle & Loop Rules

When given a task or issue, execute strictly in these four discrete phases. Do not blend phases.

### Phase 1: Specification (`/specs/<feature>.md`)
* Read the issue or user prompt.
* If a spec does not exist, draft one in `specs/<feature>.md` defining:
  - Acceptance criteria (Given/When/Then).
  - Public interfaces, signatures, and input/output contracts.
  - Failure/edge modes (invalid inputs, timeouts, exceptions).
* **Gate:** Stop and wait for user confirmation if the spec changes existing contracts.

### Phase 2: Red Loop (Test Generation)
* Write isolated unit/integration tests covering the spec requirements.
* Run the test suite:
  ```bash
  pytest tests/test_<feature>.py -v
```
Assertion Gate: Verify the tests fail for the expected reason (e.g., AttributeError or missing method, not a test syntax/import error).

### Phase 3: Green Loop (Minimal Implementation)
Implement the minimal production code needed to satisfy the failing test.

Avoid premature optimization or implementing speculative features outside the current test.

Run the test suite:
```bash
pytest tests/test_<feature>.py -v
```
Iteration Limit: You have a maximum of 3 correction attempts per failing test. If it does not pass after 3 tries:

Halt execution.

Revert recent code edits (git checkout -- <file>).

Report the failure, the diff, and the exact error log.

### Phase 4: Refactor Loop & Verification
Clean up code formatting, variable names, and remove dead code.

Ensure type safety, linting, and full regression pass:
```bash
ruff check .
uvx pyrefly check --summarize-errors
pytest
```
Ensure no regressions exist before declaring the task complete.

## 2. Environment & Tool Conventions
Language / Framework: Python 3.13+ (or your stack)

Package Manager: uv

Test Runner: pytest -v --tb=short

Linter/Formatter: ruff check . && ruff format --check .

Type Checker: uvx pyrefly check --summarize-errors

## 3. Agent Guardrails & File Operations
Atomic Commits: Do not stage or commit code without explicit instructions.

No Speculative Files: Never create utility modules or helper scripts unless explicitly specified in specs/.

State Preservation: If a loop step fails twice in a row, inspect the diff rather than applying additive patches. Do not add mock fallbacks or suppress errors with empty try/except blocks.

Context Budgeting: When checking test outputs, always use targeted flags (pytest -q -k "test_name") rather than printing massive full-suite logs into the context window.

### Tool Execution Guardrails: File Editing
- When using the `Edit` tool, `old_string` must be an EXACT literal character-for-character match from the file, including all whitespace, indentation, and newlines.
- Never guess or approximate `old_string`. Always use `View` to inspect the exact line range immediately before calling `Edit`.
- If an `Edit` call fails, do not guess another string; use `View` to re-fetch the lines.
- If an edit spans more than 50% of a file or more than 30 lines, use whole-file overwriting via `Write` instead of multiple fragile `Edit` calls.

## 4. Running the WikiSkill Harness

To run the `wikiskill_harness.py` script, use the `uv run` command with the `--post-session` argument.

```bash
uv run scripts/wikiskill_harness.py --post-session
```

For local testing, the harness is configured to use a mock SQLite database for session trajectories. This database is automatically created at `~/.claude-code-router/logs.db` if it does not already exist, and it's populated with sample session data. This allows for easy local development and testing without needing a live CCR instance.
