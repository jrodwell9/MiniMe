# IDE Diff Buffer & Premature Commit Race Pattern

## Problem
An AI coding assistant executes `git add .` and `git commit` immediately after making file edits, while the human developer still has pending diff proposals open in their IDE editor tabs. When the developer subsequently clicks "Accept" or saves in the editor, the IDE flushes its in-memory buffer back to disk with updated timestamps, immediately re-dirtying `git status` with unstaged modifications right after the commit.

## Root Cause
An asynchronous state race between the IDE's pending in-memory diff review buffer and Git's on-disk index:
1. The agent writes to disk and prematurely commits before the developer reviews or accepts the IDE diff view.
2. The user interacts with the IDE editor tab and accepts the change.
3. The IDE editor re-writes the accepted buffer to disk, changing file modification times and triggering Git to mark files as modified again.

## Fix
1. **Never Speculatively Commit**: Agents must leave all modified files unstaged in the working tree after running verification tests and linters.
2. **User-Gated Commit Step**: Only execute `git commit` when the user explicitly commands it (e.g., *"looks good, commit this"*), ensuring all IDE diff buffers have already been accepted and saved.
3. **Decouple Verification from Staging**: Keep automated verification (`pytest`, `ruff`) strictly separate from version control commits.
