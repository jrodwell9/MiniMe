# Wiki Pattern Index

- [take-examine-move-loop](wiki/patterns/take-examine-move-loop.md): Agent takes item, examines it, puts it back. Cause: lack of destination checking. Fix: enforce destination verification before examine step.
- [cli-syntax-error-loop](wiki/patterns/cli-syntax-error-loop.md): Repeated execution of invalid shell flags. Cause: outdated CLI docs in context. Fix: pass --help flag prior to multi-flag execution.