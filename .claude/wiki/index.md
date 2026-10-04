# Wiki Pattern Index

- [take-examine-move-loop](wiki/patterns/take-examine-move-loop.md): Agent takes item, examines it, puts it back. Cause: lack of destination checking. Fix: enforce destination verification before examine step.
- [cli-syntax-error-loop](wiki/patterns/cli-syntax-error-loop.md): Repeated execution of invalid shell flags. Cause: outdated CLI docs in context. Fix: pass --help flag prior to multi-flag execution.
- New pattern: example-pattern
- [edit-string-mismatch-loop](wiki/patterns/edit-string-mismatch-loop.md): Edit tool failed to find target string. Cause: whitespace or line mismatch. Fix: view exact line range before editing or use whole-file write.
- [unprefixed-python-runner-loop](wiki/patterns/unprefixed-python-runner-loop.md): Command not found when running python tools. Cause: bare invocation without virtualenv. Fix: prefix with 'uv run <command>'.
- [missing-dependency-import-loop](wiki/patterns/missing-dependency-import-loop.md): ModuleNotFoundError during execution. Cause: missing package or path issue. Fix: add via uv and align root package imports.
- [test-assertion-failure-loop](wiki/patterns/test-assertion-failure-loop.md): Test assertion failed. Cause: contract mismatch. Fix: inspect test failure and apply targeted minimal patch.
- [cross-agent-skill-discovery](wiki/patterns/cross-agent-skill-discovery.md): Incompatible skill search paths between Claude Code (.claude/skills) and Antigravity (.agents/skills). Cause: disparate agent directory standards. Fix: create NTFS directory junction or symlink and ignore alias in .gitignore.
- [hub-sync-stale-upstream-drift](wiki/patterns/hub-sync-stale-upstream-drift.md): Redundant proposal PRs generated during hub sync. Cause: hub local clone lagging behind origin/main and multiline YAML frontmatter list unparsed. Fix: synchronize main before staging, use robust YAML frontmatter parsing, and prune candidate branches.
