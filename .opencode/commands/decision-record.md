---
description: Promote a decision to a full record (/decision-record <meeting line, or new decision>)
---
Input: $ARGUMENTS. Today is !`powershell -NoProfile -Command "Get-Date -Format yyyy-MM-dd"`.

Either:
- **Promote**: the input names a decision line in a meeting note (fuzzy match
  on text, meeting, or series; ask if ambiguous), or
- **New**: the input describes a decision made outside a meeting (email,
  chat, hallway) — no meeting link.

Draft a record from `Templates/Decision.md` per AGENTS.md:
- `date` = the meeting's date (promote) or today (new); copy `meeting`,
  `series`, `projects` from the meeting note; `deciders` from what the notes say.
- Fill Decision, Context, Options considered, Rationale, and Consequences &
  follow-ups from the meeting note and anything I've said. Don't invent
  reasoning — where the notes don't say, ask me or leave the section with a
  `?` line.
- If it replaces an earlier decision, set `supersedes` and say so.

Show me the draft and wait for my yes. Then:
1. Write `Decisions/<date> <short title>.md`.
2. Promote: replace the meeting's decision line with `- [[<record name>]]`.
3. If it supersedes a record: on the old one set `status: superseded`,
   `superseded_by: "[[<new record>]]"`, and add a log line.
4. Offer to create tasks for any follow-ups (per AGENTS.md).
