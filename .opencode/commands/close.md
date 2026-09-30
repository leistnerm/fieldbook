---
description: Close a task as done (or dropped) (/close <task> [note])
---
Input: $ARGUMENTS
Today is !`powershell -NoProfile -Command "Get-Date -Format yyyy-MM-dd"`.

Find the task note (fuzzy match on title; ask if ambiguous). Per
AGENTS.md: set `status: done` and `completedDate: <today>` in the same
edit and append a closing log line with the note if given. If the input says
dropped/cancelled/won't do, use `status: dropped` instead.
If it's a recurring task, don't edit it — tell me to tick it in TaskNotes.
