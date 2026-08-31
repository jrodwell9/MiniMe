# Technical Specification: Local Post-Session WikiSkill Harness for Claude Code & CCR (v2 - Zero-Copy Adapter)

## 1. System Overview & Architecture
This specification defines the design and implementation of an automated self-evolution harness script (`wikiskill_harness.py`). The system integrates the **WikiSkill** framework (Tang et al., 2026) with **Claude Code Router (CCR)** to compile active agent session experiences into persistent, compounding knowledge across interactive coding sessions.

Rather than physically copying raw JSON execution traces to disk, this specification implements a **Zero-Copy CCR Log Adapter**. The adapter queries Claude Code Router's native local database/log store directly on-the-fly during post-session execution, eliminating redundant trace file duplication while maintaining complete isolation between execution logs, wiki knowledge, and active skills.

The architecture comprises three functional layers:
1. **Raw Layer (Zero-Copy CCR Adapter)**: Direct in-memory interface (`CCRLogAdapter`) querying CCR's native log store (SQLite DB / REST API / log streams) for the latest session telemetry.
2. **Wiki Layer (`wiki/`)**: Maintains persistent, compounding markdown pattern files, a consolidated index (`index.md`), an evolution log (`logs.md`), and a ground-truth proposal audit trail (`skill-impact.md`).
3. **Skills Layer (`skills/`)**: Contains active Anthropic-formatted skill directories (`SKILL.md` and `PURPOSE.md`).

---

## 2. Directory & Schema Definitions

### 2.1 Workspace Hierarchy
```
.claude/
├── raw/                                  # Optional / Virtual Layer (Zero-Copy Pointers). This directory should be gitignored.
│   └── pointers/                         # Lightweight session metadata pointers to CCR's native logs (zero payload duplication, for quick indexing and lookup)
│       └── session_<timestamp>.json
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

### 2.3 Wiki Schema & Formats

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
  ```
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

### 3.1 Step 1: Zero-Copy CCR Log Adapter (`CCRLogAdapter`)
* **CCR Log Source**: Queries native local storage (e.g., `~/.claude-code-router/logs.db` or CCR REST endpoint `http://127.0.0.1:3456/api/session/latest`).
* **In-Memory Normalization**:
  * Extracts prompt messages, tool invocations (shell, file read/write), error outputs, token counts, and routing decisions.
  * Formats logs directly into an in-memory `Trajectory` object:
    ```python
    @dataclass
    class TrajectoryStep:
        step_number: int
        tool_name: str
        tool_input: dict
        observation: str
        is_error: bool
        latency_ms: float

    @dataclass
    class SessionTrajectory:
        session_id: str
        timestamp: str
        model_routed: str
        steps: List[TrajectoryStep]
        final_status: str
    ```
* **Lightweight Pointer (Optional)**: Saves a tiny pointer JSON in `raw/pointers/session_<id>.json`:
  ```json
  {
    "session_id": "ccr-sess-20260831-0500",
    "timestamp": "2026-08-31T05:00:00Z",
    "total_steps": 14,
    "error_count": 2,
    "routed_model": "claude-3-7-sonnet"
  }
  ```
* **Wiki Isolation**: During active sessions, Claude Code is strictly restricted from reading `wiki/` files. Only active `skills/` are injected into the prompt.

### 3.2 Step 2: Wiki Maintainer (Pattern Consolidation)
* **LLM Agent**: Triggered post-session with input containing the in-memory `SessionTrajectory` from `CCRLogAdapter` and current `wiki/` context.
* **Root-Cause Analysis**: Compares successful vs. failing execution steps in the trajectory, identifies recurring error patterns or key workarounds, and outputs a structured JSON response:
  ```json
  {
    "create_patterns": [
      {
        "name": "pattern-name.md",
        "content": "# Pattern Title\n\n## Problem\n...\n\n## Root Cause\n...\n\n## Fix\n..."
      }
    ],
    "update_patterns": [
      {
        "name": "existing-pattern.md",
        "edits": [
          {"op": "append", "content": "\n\n## Fresh Evidence\nAdded in session 20260831..."}
        ]
      }
    ],
    "update_index": "# Complete Updated Wiki Index\n\n- [pattern-1]...",
    "append_log": "Session 20260831: Documented CLI flag error pattern."
  }
  ```

### 3.3 Step 3: Skill Proposer (ReAct Agent)
* **LLM Agent Loop**: Runs multi-turn Reason + Act (ReAct) reasoning over the updated `wiki/` state.
* **Tools**: `read_file(path)` and `finish(proposal)`.
* **Execution Constraint**: Must inspect `wiki/index.md` and `wiki/skill-impact.md` to ensure candidate proposals do not duplicate past rejected diffs. Must inspect at least 4 pattern pages or trajectory steps before proposing.
* **Output Format**:
  ```json
  {
    "action": "patch",
    "name": "git-workflow",
    "edits": [
      {
        "op": "replace",
        "target": "Old rule text",
        "content": "New refined rule text"
      }
    ]
  }
  ```

### 3.4 Step 4: Gating & Audit Logging
* **GitHub Pull Request Gating**: Creates a GitHub Pull Request with the proposed skill edit for human review and approval.
* **Acceptance Path**:
  * Upon GitHub Pull Request merge, the candidate patch is applied to `skills/<skill-name>/SKILL.md`.
  * Appends accepted audit entry to `wiki/skill-impact.md`.
* **Rejection Path**:
  * If the GitHub Pull Request is closed without merging, modifications to `skills/` are discarded (reverts to previous state).
  * **Critical Rule**: `wiki/` modifications are **never rolled back**. Appends rejected audit entry (including full proposed diff) to `wiki/skill-impact.md`.

### 3.5 Error Handling & Robustness
*   **CCR Log Adapter (`CCRLogAdapter`)**:
    *   Implement robust retry mechanisms with exponential backoff for querying CCR's native log store (database or REST API).
    *   Gracefully handle cases where CCR logs are unavailable or malformed, logging errors and potentially skipping post-session processing for that specific session.
*   **Wiki Maintainer / Skill Proposer (LLM Agents)**:
    *   Validate LLM output JSON schemas strictly. If an LLM produces malformed JSON, log the error, retry the prompt a limited number of times (e.g., 2-3), and if persistent, log the raw LLM output for debugging and skip the current update step.
    *   Implement safeguards for file operations (read/write), handling `IOError` or permission issues.
*   **Harness-level Failures**:
    *   Ensure the overall `wikiskill_harness.py` script has top-level exception handling to prevent crashes. Log all unhandled exceptions with full stack traces.
    *   Consider a "quarantine" mechanism for sessions that consistently cause errors during processing to prevent repeated failures.

---

## 4. Further Considerations

### 4.1 Concurrency & Multi-Session Handling
*   The current design assumes sequential processing of session logs. For environments with multiple concurrent Claude Code sessions, consider mechanisms to prevent race conditions when updating shared `wiki/` or `skills/` resources. This might involve locking mechanisms, atomic file operations, or a dedicated queue for post-session processing requests.

### 4.2 Wiki Scalability
*   As the `wiki/patterns/` directory grows, the efficiency of LLM agents in querying and processing this knowledge may degrade. Future enhancements could include:
    *   **Indexing**: Implement a simple search index (e.g., based on keywords or embeddings) for pattern files to help LLMs quickly retrieve relevant knowledge.
    *   **Summarization**: Periodically summarize older or less frequently accessed patterns to reduce context window pressure for LLM agents.

### 4.3 LLM Prompting Strategy (High-Level)
*   While specific prompts are implementation details, the harness should employ clear, structured prompts for the Wiki Maintainer and Skill Proposer agents. This includes:
    *   **Few-shot examples**: Provide examples of desired JSON output formats.
    *   **Constraint definitions**: Clearly articulate constraints such as inspecting `wiki/index.md` and `wiki/skill-impact.md` to avoid past rejections.
    *   **Role-playing**: Instruct the agents to adopt specific roles (e.g., "You are an experienced Wiki maintainer").

### 4.4 Dependency Management
*   The `wikiskill_harness.py` script and its dependencies should be managed using `uv`, consistent with the project's conventions. A `requirements.txt` or `pyproject.toml` should define these dependencies.

### 4.5 Access Control to CCR Logs

### 4.6 Atomic Commits & CLAUDE.md Alignment
*   The `wikiskill_harness.py` will adhere to the atomic commit principles outlined in `CLAUDE.md`. Specifically:
    *   **No Speculative Commits**: Changes to `skills/` or `wiki/` will only be staged and committed after successful verification (e.g., skill application, new pattern integration).
    *   **User Gating**: Any proposed skill modifications will require explicit user approval (as per Section 3.4 Gating & Audit Logging) before being committed.
    *   **Revert on Failure**: If a proposed change fails post-gating verification, the system will ensure a clean revert to the previous stable state, logging the failure in `wiki/skill-impact.md`.

*   If CCR logs contain sensitive information, ensure that the `wikiskill_harness.py` has appropriate, minimal access privileges to query the CCR native log store. Consider the security implications of direct database access or API calls.

---

## 5. Teardown Hook & CLI Integration

### 5.1 Shell Hook Integration
Add an auto-trigger hook to your shell configuration (`~/.bashrc` or `~/.zshrc`) or Claude Code wrapper:
```bash
claude_code_session() {
    # 1. Capture session start time & launch Claude Code through CCR
    SESSION_START=$(date -u +"%Y-%m-%dT%H:%M:%SZ")
    claude --api-base-url http://127.0.0.1:3456 "$@"

    # 2. Trigger Post-Session WikiSkill Self-Evolution Loop with Zero-Copy CCR Adapter
    echo "Running WikiSkill Post-Session Self-Evolution (Zero-Copy CCR)..."
    python3 /path/to/wikiskill_harness.py --post-session --since "$SESSION_START"
}
alias claude=claude_code_session
```
