---
description: Draft a review or self-assessment (/review <person|me> <mid-year|year-end> [from] [to])
---
Input: $ARGUMENTS
Today is !`powershell -NoProfile -Command "Get-Date -Format yyyy-MM-dd"`.

Person: match to a person note (ask if ambiguous); `me` = the person note with
`relationship: self`. Kind: `mid-year` or `year-end` (ask if not given).
Period: the from/to dates given, else January 1 of this year to today.
Sections and values come from @Templates/Review-format.md — follow it
exactly.

Gather, within the period:
1. Tasks with them in `assignee` (for `me`: tasks with no assignee, or my
   note in `assignee`): done (`completedDate` in range), recurring tasks'
   `complete_instances` in range (as counts), and log lines in range on tasks
   still open.
2. Their person note: the goals under `### Goals <year>` for the year the
   period ends in (if there's no such heading, say so and ask), and Feedback
   & recognition lines in range.
3. Meeting notes in range they attended: decisions, Action items assigned to
   them, and Commitments lines naming them (list these; the vault can't tell
   whether a commitment was kept).
4. Decision records and project notes where they're `owner` or in
   `deciders`, dated or active in range.
5. Their most recent earlier review (tag `review`, same `person`, latest
   `to`): for a year-end, normally that year's mid-year. Note goals it said
   were behind, and don't repeat its accomplishments as new ones.

Draft into the format's sections:
- **Goals**: each of that year's goals, how far it got, with evidence — for
  a mid-year, whether it's on track. A goal with no evidence: say so.
- **What was achieved**: 4–8 accomplishments, impact first, biggest first.
- **How it was achieved**: one short paragraph per value that has
  evidence (if the format lists no values, one paragraph on how the work
  was done). List values with no evidence under Evidence gaps — never stretch
  evidence to cover a value.
- **Evidence gaps**: goals and values with nothing behind them, and stretches
  with no recorded work, for me to fill in from memory.

Rules: every statement cites its source as a `[[link]]`. Nothing that isn't in
the vault. No ratings, no rankings, no comparisons with other people. First
person for `me`; third person otherwise. Plain, specific wording (AGENTS.md
style).

Show the draft, then ask whether to save it (create `Reports/Reviews/` if it's
missing) as
`Reports/Reviews/<Person> - <YYYY-MM> <kind> review.md` (YYYY-MM = the month
the period ends), from the format with `person`, `kind`, `year`, `from`, `to`
filled in and `status: draft`. If that file exists and is a draft, show what
would change and wait for my yes. If it's `final`, never touch it — say so.
Edit no other file.
