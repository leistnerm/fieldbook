---
description: Turn a meeting's action items into tasks (/actions <meeting>)
---
Meeting: $ARGUMENTS (fuzzy match on meeting notes; default to the most recent
one if blank). Today is !`powershell -NoProfile -Command "Get-Date -Format yyyy-MM-dd"`.

For each unconverted `- [ ]` line under `## Action items` (never touch
`## Commitments`):
1. Work out owner, title, due, and priority from the wording
   ("Alice to send deck by Friday" → assignee Alice, due this Friday). If the
   owner is the user (`relationship: self`) or unstated, leave `assignee` empty.
2. Pick a type from @Types.md (usually `task`, or `management` for
   people/team items).
3. Copy the meeting's `projects` onto the task.

Show me the full list of proposed tasks (title, assignee, due, priority, type)
and wait for my yes. Then, per AGENTS.md:
- create each task in `TaskNotes/Tasks/` with log line
  `- <today>: from [[<meeting note name>]]`
- replace each converted line in the meeting note with `- [[<task title>]]`
- create any missing person notes from `Templates/Person.md`

Leave lines I tell you to skip untouched.

After writing, list the new tasks that meet the Jira rules in AGENTS.md and
offer to go through them as `/jira-check` does.
