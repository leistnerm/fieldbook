---
description: Project status summary, rolled up across sub-projects (/project <name> [range])
---
Input: $ARGUMENTS. Get today’s local date with notebook_today when needed.

Find the project note (tag `project`, fuzzy match). Collect the project and
all its sub-projects at any depth (projects whose `parent` chain leads to it).
Optional range for "done"/"recent" (default: last 30 days).

Report:
1. Header: status, owner, target, tracker links; one line per sub-project with its
   status, target, and open-task count.
2. Blocked and overdue tasks (title, sub-project, assignee, last log line).
3. Active work — open tasks grouped by sub-project.
4. Done in range, grouped by sub-project.
5. Decisions in range — meeting lines and records (per AGENTS.md).
6. Commitments by others in range from meetings linked to these projects,
   plus any Commitments line that names the project or a sub-project.
7. Risks: sub-projects past `target`, active ones with no task or meeting
   activity in 30 days.

Omit empty sections and fields. A missing owner, stakeholder or meeting is not
a problem by itself. Offer a short status summary; make it audience-ready only
when an audience is supplied, using just the selected context. Don't edit files.

Respect an area/person filter. Count recurring completions separately from non-recurring done tasks. Include Jira, Agility, GitHub or Azure identities when present; never infer impact from assignment alone.
