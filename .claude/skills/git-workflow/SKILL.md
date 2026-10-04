---
name: git-workflow
description: Best practices for git branch management, commit discipline, and safe updates.
status: active
origin_session: in-flight
patterns_addressed:
  - ide-diff-buffer-commit-race
---

# Operational Rules

## Trigger
Apply when staging, committing, modifying branches, or syncing state with remotes.

## Rule 1: No Speculative Commits & IDE Buffer Synchronization
- Never execute `git add` or `git commit` speculatively after modifying or creating files.
- Always leave file modifications unstaged in the working tree so the developer can review and accept IDE diff proposals in their editor tabs.
- Only run git commit commands when the developer explicitly requests a commit (e.g. "let's commit this").

## Rule 2: Safe Remote Syncing
- Always execute `git fetch origin` before rebasing.
- Never use `--force` unless explicitly instructed.