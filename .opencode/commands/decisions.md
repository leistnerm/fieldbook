---
description: Search decisions (/decisions <topic/series/project/person> <range>)
---
Query: $ARGUMENTS. Today is !`powershell -NoProfile -Command "Get-Date -Format yyyy-MM-dd"`.

Read it as a filter (topic, series, project, or person — any mix) plus an
optional date range in any form (default: last 180 days).

Search both kinds of decision per AGENTS.md:
- plain lines in `## Decisions` of meeting notes whose `date` is in range
- decision records (tag `decision`) whose `date` is in range; a meeting line
  that links to a record counts once, as the record

For each match, check whether a later decision on the same subject replaced
or changed it — a record's `superseded_by`, or a later meeting line that
reverses or revises it.

Output a table sorted by date: date | decision | where (meeting or record
link) | status (active / revisit / superseded → by what). Then flag any plain
line that looks important enough for a full record (big impact, contested,
likely to be questioned later) and offer `/decision-record` for it.
Don't edit files.
