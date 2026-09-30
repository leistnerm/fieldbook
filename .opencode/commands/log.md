---
description: Append a dated log line to a task (/log <task> <note>)
---
Input: $ARGUMENTS
Today is !`powershell -NoProfile -Command "Get-Date -Format yyyy-MM-dd"`.

The first part names a task note (fuzzy match on title; ask if more than
one matches). The rest is the note. Append `- <today>: <note>` as the last
line of the task's `## Log` section. Don't change anything else unless the note
clearly says the status changed (e.g. "blocked on X", "started") — then update
`status` too and say so.
