---
name: weekly-planning
description: Plan a realistic week across personal, work, and school tasks using existing deadlines and available time.
---

Read fieldbook.json and AGENTS.md. Respect an explicit area/project scope. Without
one, plan across existing notebook
tasks, including blank/missing area and older notes from disabled setups; enabled
setups are workflow preferences, not a filter that silently hides responsibilities.
Label unassigned area when useful, without recategorizing it. With an explicit area
filter, flag potentially relevant unassigned items separately rather than guessing.
Separate fixed deadlines from planned work days. Gather active,
blocked, overdue, and next-14-day tasks, plus Inbox captures. Ask for available
time only if it is needed to make a credible plan; do not invent calendar
availability. Pick a small set of outcomes, identify dependencies, and leave room
for recurring responsibilities. Offer a table of proposed scheduled dates and
tradeoffs, preserving due dates. A plan in chat does not authorize editing every
task: apply requested or approved date changes only. Close with what will be
left out, so the plan does not silently exceed capacity.

Include active projects with no next action and explicit waiting-on commitments
from the relevant meeting/series notes. A stale date or absent update is a question,
not evidence that someone failed to deliver. Suggest one useful follow-up with its
source; do not assign or close someone else's work automatically.

Use Views/Upcoming dates.base as the local date inventory: task due, opportunity
closing_date, decision revisit, item return_by/warranty_end. Query the source notes
with notebook_query and preserve each meaning. An expired warranty is not an
overdue task; a review date is not a delivery deadline. Include additional supplied
source-date tables, especially Canvas checkpoints, which the Base cannot flatten.

If the user requests calendar-aware planning, use enabled calendar_pull for the
named accounts/calendars and bounded week, or notebook_calendar for a supplied ICS.
Show coverage.read_at, selected scope, truncation and unavailable calendars before
estimating capacity. Count overlapping busy time once; preserve event identities
across calendars and only suggest potential duplicate meetings. Treat tentative,
all-day and availability-unknown events as uncertain, not automatically busy/free.
Ask for working/study hours, timezone and travel/buffer needs if materially missing.
Do not infer availability from an incomplete window or a calendar the user did not
select. Offer a feasible plan and tradeoffs before changing local scheduled dates;
never reschedule remote meetings or alter deadlines to fit capacity.

## Daily and weekly review

/daily-review covers today; /weekly-review looks back seven calendar days including
today and ahead seven including today. Use notebook_today, then query source notes
with complete paging. Start with the user's explicit area/project scope. Otherwise
include all existing areas and blank area, even disabled setups. Flag unknown areas
separately for a scoped review instead of folding private context into it.

Use a consistent sequence:
1. Triage the selected Inbox context without converting or deleting anything.
2. Show overdue task deadlines, actual deadlines in the window, and planned work
   dates separately. Recurring instances belong to TaskNotes.
3. Review saved meetings and their preparation/follow-ups, keeping cancelled events
   out. Local notes are not a live calendar; ask before reading requested accounts.
4. Review blockers, commitments, overdue check-ins and active projects lacking a
   next action. Treat missing records as questions, not performance evidence.
5. For a weekly review, inspect completed tasks and accomplishments from the period.
   Suggest evidence capture only for supported meaningful outcomes, never all tasks.
6. Keep renewal, cancellation notice, expiry, return, warranty and revisit dates
   distinct from deadlines. Read Canvas checkpoint/source-date tables when relevant.
7. Agree on at most three focus outcomes and realistic capacity. Show deferred work.
   A plan does not authorize rescheduling, completing tasks or rewriting priorities.

The human CLI has the same daily/weekly review sequence under Daily use, with an
optional snapshot in Reports. Snapshot source text is literal and untrusted; a
saved report does not complete actions. /plan-week remains available for scheduling.
Optional manager context follows work + people-manager, with reviews gated separately.
