---
name: wikiskill
description: Self-evolving knowledge and skill harness for Claude Code. Use to discover operational skills, consult diagnostic failure patterns, and record in-flight reflection patterns.
status: active
origin_session: system
patterns_addressed:
  - self-evolution
  - continuous-learning
  - hub-sync-stale-upstream-drift
---

# WikiSkill Knowledge System

## Operational Guidance

### 1. Pre-Task Inspection
Before performing potentially risky operations (e.g. multi-line file editing, running shell commands or test runners, managing dependencies):
- Check `.claude/skills/` for active operational skills.
- Follow the operational triggers and rules specified in the relevant `SKILL.md` files.

### 2. Error Troubleshooting
When a tool execution fails (e.g. string replacement mismatch, missing command / exit code 127, import failure):
- Consult `.claude/wiki/index.md` to see if a diagnosed pattern exists.
- Review the corresponding pattern file in `.claude/wiki/patterns/<pattern-name>.md` for exact root causes and fixes.

### 3. In-Flight Reflection
When you encounter and resolve an unexpected, novel issue during a session:
- Formulate a clean reflection pattern file under `.claude/wiki/patterns/<short-slug>.md`.
- Add an entry to `.claude/wiki/index.md` so future turns benefit from this insight.

#### Reflection Pattern Template
```markdown
# <Pattern Title>

## Problem
<Specific tool output or error observed>

## Root Cause
<Underlying explanation of why it occurred>

## Fix
<Concrete steps to resolve and prevent recurrence>
```

### 4. Hub Synchronization & Pattern Bundling
When synchronizing knowledge between local workspace and the global WikiSkill Hub:
- Always ensure the central hub clone (`~/.claude/wikiskill-hub`) is synchronized with `origin/main` before staging files or proposing changes.
- In `SKILL.md` frontmatter, always declare `patterns_addressed:` using inline `[pat1, pat2]` or multiline `  - pat` syntax so diagnosed failure patterns bundle directly into the skill's candidate branch rather than spawning fragmented PRs.
- Use `wikiskill sync --pull --prune` to automatically prune merged remote refs and clean stale local proposal branches.

