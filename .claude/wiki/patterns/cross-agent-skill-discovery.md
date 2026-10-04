# Cross-Agent Skill Discovery Pattern

## Problem
Different AI agent harnesses look for workspace skills in incompatible directories:
- **Claude Code** expects skills in `.claude/skills/<skill>/SKILL.md`
- **Antigravity** expects skills in `.agents/skills/<skill>/SKILL.md` (or `.agent/skills/`)

Without a linking mechanism, developers must choose between maintaining duplicate copies (which quickly drift out of sync) or having skills visible to only one agent tool.

## Root Cause
Disparate agent framework standards and directory search conventions across AI coding assistants.

## Fix
1. Establish `.claude/skills/` as the single canonical source of truth for all workspace skills.
2. Link the secondary discovery directory using a filesystem-level alias:
   - **Windows (NTFS Junction)**:
     ```powershell
     powershell -Command "New-Item -ItemType Directory -Path .agents -Force; New-Item -ItemType Junction -Path .agents\skills -Target (Resolve-Path .claude\skills).Path"
     ```
   - **POSIX (Symlink)**:
     ```bash
     mkdir -p .agents && ln -s ../.claude/skills .agents/skills
     ```
3. Add `.agents/` to `.gitignore` to prevent Git from indexing duplicate paths or junction links.
