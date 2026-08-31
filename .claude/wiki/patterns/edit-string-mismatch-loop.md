# Edit String Mismatch Loop

## Problem
Encountered 45 failure(s) where string replacement failed because the specified target string did not match the file content exactly.

## Root Cause
Imprecise whitespace, indentation, or outdated line numbers passed into the Edit tool without inspecting the file immediately beforehand.

## Fix
1. Always run View on the exact line range immediately before performing an Edit.
2. Ensure character-for-character exact whitespace in old_string.
3. For edits spanning >30 lines or 50% of the file, use whole-file Write.
