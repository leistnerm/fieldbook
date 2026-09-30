---
description: Search meeting commitments (/commitments <who/dept/topic> <range>)
---
Query: $ARGUMENTS. Today is !`powershell -NoProfile -Command "Get-Date -Format yyyy-MM-dd"`.

Read it as a filter (a person, department, project, or topic — any mix) plus
an optional date range in any form ("last month", "Q3", "2026-08-01
2026-08-31"; default: last 90 days).

Search the `## Commitments` sections of meeting notes whose `date` is in
range. Match departments per AGENTS.md (person note `team` first, then the
line's parenthetical), loosely: "Fin" = "Finance".

Output a table sorted by meeting date: date | meeting (link) | person |
department | commitment | by. Then one line with the count. Don't edit files.
If a line is ambiguous (no clear person), list it separately under "Unclear".
A `by` that isn't a full YYYY-MM-DD date shows as written, marked "(no usable date)".
