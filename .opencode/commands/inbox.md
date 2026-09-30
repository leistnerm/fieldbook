---
description: Sort the inbox into tasks, people, meetings, projects, research (/inbox)
---
Today is !`powershell -NoProfile -Command "Get-Date -Format yyyy-MM-dd"`.

Read @Inbox.md. Items are the lines starting with `- ` after the intro. If
there are none, say the inbox is empty and stop.

Say how many items there are, then take them oldest first, **one per turn**:
1. Show the line.
2. Propose one destination and the exact change, following AGENTS.md:
   - a new task (fill only what the line says; leave other fields empty)
   - a log line on an existing task
   - a detail or Feedback & recognition line on a person note
   - a Commitments line in a meeting note
   - a line in a project note
   - a new task flagged as a Jira candidate (`jira` empty, for /jira-check)
   - a new research note (`status: idea`) for something to look into or try
   - drop
   If the line names a person or task that more than one note could be, ask
   which (AGENTS.md same-name rules).
3. Wait for my answer: yes, a different destination, skip, or drop.
   - yes / other destination: make the change, then remove that line from
     Inbox.md.
   - skip: leave the line; move on.
   - drop: remove the line.
4. Then the next item. Never file more than one item per turn.

In Inbox.md, only ever remove a sorted line; never edit or reorder the rest.
