---
name: file-editing
description: Best practices and guardrails for safe, exact file modifications.
status: active
origin_session: in-flight
patterns_addressed:
  - edit-string-mismatch-loop
---

# Operational Rules

## Trigger
Apply when working with file-editing operations in this codebase.

## Rules
- Always inspect the exact line range with View immediately before Edit.
- Never guess whitespace, indentation, or newlines in old_string.
- If an edit spans more than 30 lines or 50% of a file, use whole-file write instead of Edit.
