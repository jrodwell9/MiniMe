# Technical Specification: Distributed WikiSkill via Native Skills, Hub Sync & Watcher Daemon

## 1. System Overview & Architecture
This specification defines the extension of **WikiSkill** (`wikiskill`) into a distributed, multi-workstation, cross-repository knowledge compounding engine using native Claude Code markdown skills, a background watcher daemon, and a centralized Git Hub with PR gating.

The architecture consists of three interconnected layers:
1. **Native Claude Code Companion (`plugins/wikiskill/plugin.json` & `.claude/skills/wikiskill/SKILL.md`)**: Operates directly in the filesystem without background process overhead, allowing Claude to inspect skills and wiki patterns natively.
2. **Central Git Sync Hub (`src/wikiskill/sync.py`)**: Manages a centralized Git repository (`~/.claude/wikiskill-hub` or remote) containing `global/` universal engineering rules, enforcing a Pull Request gate per skill via GitHub CLI (`gh`).
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
│       ├── file-editing/
│       │   ├── SKILL.md                  # Operational rules with frontmatter metadata
│       │   └── PURPOSE.md                # Skill purpose & trigger definition
│       └── cli-tool-execution/
│           ├── SKILL.md
│           └── PURPOSE.md
```

---

## 3. Public Interfaces & Component Contracts

### 3.1 Central Git Sync Manager (`src/wikiskill/sync.py`)
```python
class GitHubSyncManager:
    def __init__(self, hub_dir: Path | None = None, remote_url: str | None = None): ...
    def init_hub(self, remote_url: str | None = None) -> bool: ...
    def pull(self) -> bool: ...
    def push_patterns(
        self,
        commit_message: str = "Auto-sync WikiSkill patterns",
        direct: bool = False,
        branch_name: str | None = None,
        interactive: bool = True,
    ) -> dict[str, Any]: ...
    def sync_project_to_hub(
        self, project_dir: Path, prune: bool = False
    ) -> dict[str, Any]: ...
    def sync_hub_to_project(
        self, project_dir: Path, prune: bool = False
    ) -> dict[str, Any]: ...
```

### 3.2 Cross-Project Watcher Daemon (`src/wikiskill/daemon.py`)
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

### 3.3 CLI Entrypoints (`src/wikiskill/cli.py`)
- `wikiskill sync [--pull | --push] [--hub-dir <path>] [--direct] [--prune]`: Executes remote Git sync and candidate PR creation.
- `wikiskill daemon [--interval <seconds>] [--once]`: Starts background session monitor.
- `wikiskill setup-hub [--remote <git-url>] [--hub-dir <path>]`: Initializes central hub.

---

## 4. Acceptance Criteria (Given / When / Then)

### 4.1 Git Hub Sync & PR Gating
1. **Hub Synchronization**:
   - **Given** a local project `.claude/wiki` with newly discovered patterns,
   - **When** `sync_project_to_hub(project_dir)` is called,
   - **Then** universal patterns and skills are promoted to `hub/global/`.
2. **PR Gated Push**:
   - **Given** modified skills in the central hub and `gh` installed,
   - **When** `push_patterns()` is called,
   - **Then** an isolated candidate branch and Pull Request are generated per skill via `gh pr create`.

### 4.2 Daemon Execution
1. **Multi-Project Auto-Discovery**:
   - **Given** multiple session files in `~/.claude/projects/`,
   - **When** `daemon.scan_and_process_sessions()` runs,
   - **Then** all unrecorded sessions are processed, patterns extracted, and recorded in `.processed_sessions.json`.
