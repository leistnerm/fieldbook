---
description: Process the inbox individually or as a reviewed batch
---
Input: $ARGUMENTS. Read Inbox.md and AGENTS.md.
Default: propose a numbered batch table: source line, destination, exact change,
and any question. Keep uncertain entries separate. The user can approve all,
selected numbers, edits, skip, or drop. `/inbox one` processes one at a time.
After approval, re-read Inbox.md and destination notes. Apply only approved
changes; remove a captured line only after its destination write succeeds.
Never remove a matching line twice, reorder remaining entries, or lose captures
added while the preview was being reviewed. An identical duplicate capture needs
its own source position/context. Preserve failed/skipped lines and report them.
Destinations can be a task, existing log, note, project, person, or explicit drop.
