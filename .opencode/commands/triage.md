---
description: Review the open backlog for problems
---
Today is !`powershell -NoProfile -Command "Get-Date -Format yyyy-MM-dd"`. Scan open task notes (see AGENTS.md; status not done/dropped)
and report, in this order:
1. overdue
2. blocked, with how long since the last log line
3. active with no log line in 14+ days
4. missing or invalid fields (type not in @Types.md, bad priority, no title)
5. backlog items older than 60 days (candidates to drop)
6. active projects (tag `project`) with no task, meeting, or log activity in
   30 days, or past `target`
7. tasks that probably belong in Jira (AGENTS.md Jira rules): count, the top
   5, and "run /jira-check to go through them"
8. people links that can't be pinned to one person (AGENTS.md "Same name,
   different people"): a link with no note that matches a person's plain name
   or alias, a plain-named person note alongside a qualified note of the same
   name, and Commitments lines naming a person more than one note could be
9. Inbox.md: number of items and the date of the oldest ("run /inbox")

One line per item. Then propose changes, one at a time, and wait for my yes
before editing anything.
