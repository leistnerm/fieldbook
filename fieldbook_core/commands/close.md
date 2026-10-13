---
description: Close a task as done (or dropped) (/close <task> [note])
---
Input: $ARGUMENTS
Get today’s local date with notebook_today when needed.

Find the task note (fuzzy match on title; ask if ambiguous). Per
AGENTS.md: set `status: done` and `completedDate: <today>` in the same
edit and append a closing log line with the note if given. If the input says
dropped/cancelled/won't do, use `status: dropped` instead.
If it's a recurring task, don't edit it — tell me to tick it in TaskNotes.

After a successful close, follow AGENTS.md’s helpful-connection guidance. If the
work has a meaningful result or learning, briefly suggest capturing an accomplishment
with its source; do not create it unless requested or accepted.
