---
name: cross-agent-skill-linking
description: Standards for sharing and linking skills across different agent harnesses (Claude Code, Antigravity) without file duplication using filesystem junctions.
status: active
origin_session: in-flight
patterns_addressed:
  - cross-agent-skill-discovery
---

# Operational Rules

## Trigger
Apply when configuring agent workspaces, setting up multi-agent environments, or adding new skill definitions.

## Rules
- Always maintain `.claude/skills/` as the single canonical source of truth for workspace skills.
- To enable Antigravity skill discovery on Windows without administrator privileges, create an NTFS directory junction:
  ```powershell
  powershell -Command "New-Item -ItemType Directory -Path .agents -Force; New-Item -ItemType Junction -Path .agents\skills -Target (Resolve-Path .claude\skills).Path"
  ```
- On POSIX/Linux/macOS systems, create a relative directory symlink:
  ```bash
  mkdir -p .agents && ln -s ../.claude/skills .agents/skills
  ```
- Always ensure `.agents/` is listed in `.gitignore` so Git only tracks `.claude/skills/` and avoids tracking duplicate paths or filesystem junctions.
- Never manually copy skill files between `.claude/skills/` and `.agents/skills/`.
