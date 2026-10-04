# Hub Sync Upstream Drift & Redundant Proposal Pattern

## Problem
Running `wikiskill sync --push` creates redundant pull requests and branches for skills or patterns that have already been merged to `origin/main` on the remote hub, or splits failure pattern diagnoses into disconnected standalone PRs rather than bundling them with their associated skills.

## Root Cause
1. **Local Hub Clone Drift**: The central hub clone (`~/.claude/wikiskill-hub`) lagged behind `origin/main` commits. When project files were copied into the hub prior to pulling upstream changes, `git status` misidentified already-merged skills and patterns as untracked new files.
2. **YAML Frontmatter Parser Rigidity**: Naive regex/line parsing only extracted inline YAML lists (`patterns_addressed: [a, b]`) and failed to parse multiline lists (`patterns_addressed:\n  - pattern-name`). Consequently, pattern files were left unassociated with their skill proposals and spun off into separate standalone pattern PRs.
3. **Stale Proposal Branch Accumulation**: Ephemeral proposal branches (`proposal/*`) accumulated in the local hub repository after PR creation.

## Fix
1. **Upfront Upstream Synchronization**: Always switch to `main`, execute `git pull origin main`, and fetch upstream changes with `--prune` before computing diffs or staging files in `sync_project_to_hub()` and `push_patterns()`.
2. **Robust Frontmatter Parsing**: Use structured YAML frontmatter parsing that supports both inline and multiline list syntax (`- item`) for `patterns_addressed`, `description`, `origin_session`, and `status`.
3. **Automated Pruning**: Incorporate branch pruning into `wikiskill sync --pull --prune` to automatically delete merged or orphaned local `proposal/*` candidate branches.
