---
description: Prep the next meeting in a series (/prep <series> [date])
---
Input: $ARGUMENTS. Today is !`powershell -NoProfile -Command "Get-Date -Format yyyy-MM-dd"`.

Find the series note (tag `series`, fuzzy match on name). Meeting date = the
date given, else today. Then gather:
1. The series note's Standing agenda.
2. From the last 3 meetings in the series (`series` links to it, by `date`):
   - Action items still open — unconverted `- [ ]` lines, or linked tasks not
     done/dropped (with assignee, due, and last log line).
   - Decisions that call for a revisit or follow-up, plus decision records in
     this series with `status: revisit` and `revisit` date on or before the
     meeting date.
   - Commitments whose `by` date (YYYY-MM-DD) has passed or is within 7 days.
     A commitment with no date, or one that isn't a full date, goes in a
     separate "No usable date" list, as written.
3. Open tasks whose `projects` overlap the series' `projects`, if any: just
   blocked and overdue ones.

Output a draft agenda: standing items first, then "Follow-ups from last time"
(open actions, commitments due, decisions to revisit), then anything from 3.
Keep it to one line per item.

Offer to create `Meetings/<YYYY>/<YYYY-MM>/<date> <series name>.md` from
`Templates/Meeting.md` with `date`, `series`, `attendees`, and `projects`
copied from the series note and the agenda filled in. Wait for my yes.
