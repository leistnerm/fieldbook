---
description: Project status summary, rolled up across sub-projects (/project <name> [range])
---
Input: $ARGUMENTS. Today is !`powershell -NoProfile -Command "Get-Date -Format yyyy-MM-dd"`.

Find the project note (tag `project`, fuzzy match). Collect the project and
all its sub-projects at any depth (projects whose `parent` chain leads to it).
Optional range for "done"/"recent" (default: last 30 days).

Report:
1. Header: status, owner, target, Jira; one line per sub-project with its
   status, target, and open-task count.
2. Blocked and overdue tasks (title, sub-project, assignee, last log line).
3. Active work — open tasks grouped by sub-project.
4. Done in range, grouped by sub-project.
5. Decisions in range — meeting lines and records (per AGENTS.md).
6. Commitments by others in range from meetings linked to these projects,
   plus any Commitments line that names the project or a sub-project.
7. Risks: sub-projects past `target`, active ones with no task or meeting
   activity in 30 days.

End with a short draft status update I could send. Don't edit files.
