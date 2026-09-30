---
description: What got done in a date range (/report <from> <to> [focus])
---
Range: $1 to $2 (inclusive, YYYY-MM-DD). Optional focus: $3

Scan the task notes (see AGENTS.md). Completed work in range =
- tasks with `status: done` and `completedDate` in range, and
- for recurring tasks, each date in `complete_instances` in range (count them).

Exclude `dropped` unless the focus asks for it. If a focus is given (a
project, type, tag, or person), filter to it.

Output markdown: a 3–5 sentence summary, then items grouped by type, then by
project, each as `- YYYY-MM-DD — Title (Jira key if any)` with one line of
substance from its log when useful. Recurring tasks as one line with a count.

Ask whether to save it as `Reports/$1_to_$2.md` (create `Reports/` if it's missing).
