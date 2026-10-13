---
description: Append a dated log line to a task (/log <task> <note>)
---
Input: $ARGUMENTS
Get today’s local date with notebook_today when needed.

The first part names a task note (fuzzy match on title; ask if more than
one matches). The rest is the note. Append `- <today>: <note>` as the last
line of the task's `## Log` section. Don't change anything else unless the note
clearly says the status changed (e.g. "blocked on X", "started") — then update
`status` too and say so.
