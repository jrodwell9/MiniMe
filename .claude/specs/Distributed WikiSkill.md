# Technical Specification: Distributed WikiSkill via MCP Sidecar & Central Git Sync

## 1. System Overview & Architecture
This specification defines the extension of **WikiSkill** (`wikiskill`) into a distributed, multi-workstation, cross-repository knowledge compounding engine. 

The architecture consists of three interconnected layers:
1. **MCP Sidecar (`wikiskill mcp`)**: Standard Model Context Protocol (MCP) server running via stdio in Claude Code. Provides active agent sessions with dynamic pattern lookup, active skill retrieval, and in-flight reflection recording.
2. **Central Git Sync Hub (`src/wikiskill/sync.py`)**: Manages a centralized Git repository (`~/.claude/wikiskill-hub` or remote) containing `global/` universal engineering rules and `projects/<slug>/` repository-specific knowledge.
3. **Cross-Project Watcher Daemon (`wikiskill daemon`)**: Background service that monitors `~/.claude/projects/**/*.jsonl` across all repositories on the machine, automatically runs the self-evolution harness for completed sessions, and syncs newly discovered patterns to the central hub.

---

## 2. Directory & Knowledge Schema

### 2.1 Central Hub Directory Structure (`~/.claude/wikiskill-hub/`)
```
~/.claude/wikiskill-hub/
├── .processed_sessions.json              # State tracker of processed session IDs
├── global/
│   ├── wiki/
│   │   ├── index.md                      # Global universal pattern catalog
│   │   ├── logs.md                       # Global evolution log
│   │   └── patterns/                     # Cross-repo patterns (e.g. edit-string-mismatch-loop.md)
│   └── skills/
│       ├── file-editing/SKILL.md
│       └── cli-tool-execution/SKILL.md
└── projects/
    └── <sanitized-project-slug>/
        ├── wiki/
        │   ├── index.md                  # Project-specific pattern catalog
        │   ├── logs.md                   # Project evolution log
        │   └── patterns/                 # Project-specific patterns
        └── skills/
            └── <project-skill>/SKILL.md
```

---

## 3. Public Interfaces & Component Contracts

### 3.1 MCP Sidecar Server (`src/wikiskill/mcp.py`)
Provides standard JSON-RPC MCP handlers over stdio:
- **Tools**:
  - `lookup_pattern(query: str, project_dir: str = "") -> dict`: Searches compiled pattern index and returns matching problem/cause/fix guidance.
  - `get_active_skills(project_dir: str = "") -> dict`: Returns active operational rules combining project-specific and global rules.
  - `record_reflection(summary: str, error_encountered: str, fix_applied: str, project_dir: str = "") -> dict`: Direct in-flight pattern capture during agent reasoning.
- **Resources**:
  - `wiki://index`: Returns current combined pattern index.
  - `skills://active`: Returns active operational rules.

### 3.2 Central Git Sync Manager (`src/wikiskill/sync.py`)
```python
class GitHubSyncManager:
    def __init__(self, hub_dir: Path | None = None, remote_url: str | None = None): ...
    def init_hub(self, remote_url: str | None = None) -> bool: ...
    def pull(self) -> bool: ...
    def push_patterns(self, commit_message: str) -> bool: ...
    def sync_project_to_hub(self, project_dir: Path) -> dict[str, Any]: ...
    def sync_hub_to_project(self, project_dir: Path) -> dict[str, Any]: ...
```

### 3.3 Cross-Project Watcher Daemon (`src/wikiskill/daemon.py`)
```python
class WikiSkillDaemon:
    def __init__(
        self,
        claude_dir: Path | None = None,
        hub_dir: Path | None = None,
        interval: int = 300,
    ): ...
    def scan_and_process_sessions(self) -> list[dict[str, Any]]: ...
    def run_loop(self, once: bool = False) -> None: ...
```

### 3.4 CLI Entrypoints (`src/wikiskill/cli.py`)
- `wikiskill mcp`: Runs stdio MCP server for Claude Code integration.
- `wikiskill sync [--pull | --push] [--hub-dir <path>]`: Executes remote Git sync.
- `wikiskill daemon [--interval <seconds>] [--once]`: Starts background session monitor.
- `wikiskill setup-hub [--remote <git-url>] [--hub-dir <path>]`: Initializes central hub and registers MCP in Claude configuration.

---

## 4. Acceptance Criteria (Given / When / Then)

### 4.1 MCP Server Operations
1. **Pattern Lookup**:
   - **Given** an initialized wiki containing `edit-string-mismatch-loop.md`,
   - **When** `lookup_pattern("edit mismatch")` is called via MCP,
   - **Then** it returns the root-cause and fix instructions for the edit string mismatch pattern.
2. **In-Flight Reflection**:
   - **Given** an agent encountering a new error during execution,
   - **When** `record_reflection("Custom CLI flag error", "Flag --foo failed", "Use --bar instead")` is invoked,
   - **Then** a new pattern is created in `wiki/patterns/` and indexed immediately.

### 4.2 Git Hub Sync & Multi-Repo Isolation
1. **Hub Synchronization**:
   - **Given** a local project `.claude/wiki` with newly discovered patterns,
   - **When** `sync_project_to_hub(project_dir)` is called,
   - **Then** patterns are copied to `hub/projects/<slug>/wiki/patterns/` and universal patterns are merged to `hub/global/`.
2. **Git Auto-Commit**:
   - **Given** changes in the central hub,
   - **When** `push_patterns()` is called with a git remote configured,
   - **Then** git commit and push are executed cleanly.

### 4.3 Daemon Execution
1. **Multi-Project Auto-Discovery**:
   - **Given** multiple session files in `~/.claude/projects/`,
   - **When** `daemon.scan_and_process_sessions()` runs,
   - **Then** all unrecorded sessions are processed, patterns extracted, and recorded in `.processed_sessions.json`.

