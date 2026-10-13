---
description: Turn a meeting's action items into tasks (/actions <meeting>)
---
Meeting: $ARGUMENTS (fuzzy match on meeting notes; default to the most recent
one if blank). Get today’s local date with notebook_today when needed.

For each unconverted `- [ ]` line under `## Action items` (never touch
`## Commitments`):
1. Work out owner, title, due, and priority from the wording
   ("Alice to send deck by Friday" → assignee Alice, due the Friday relative to the meeting's `date`, not today). If the
   owner is the user (`relationship: self`) or unstated, leave `assignee` empty.
2. Use `task` unless a more specific type from @Types.md matches the action.
   People/team mentions alone do not imply `management`; that type is for an
   explicit staffing, delegation or people-management action.
3. Copy the meeting's `projects` and known area onto the task; resolve any
   conflicting project areas before writing.

Show me the full list of proposed tasks (title, assignee, due, priority, type)
and wait for my yes. Then, per AGENTS.md:
- create each task in `Tasks/` with log line
  `- <today>: from [[<meeting note name>]]`
- replace each converted line in the meeting note with `- [[<task title>]]`
- handle missing people per AGENTS.md; create them only when requested

Leave lines I tell you to skip untouched.

After writing, suggest an enabled tracker only when the request/project makes it
relevant. All four providers are available in any area; do not nudge routinely.
