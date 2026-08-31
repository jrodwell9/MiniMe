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