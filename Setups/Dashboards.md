# Dashboards and saved views

Start at [[Dashboard]] in every setup. It includes personal, work, school and
unassigned notes; switching setups does not erase or hide existing records.
`Dashboards/Personal`, `Dashboards/Work` and `Dashboards/School` offer the same basic
sections scoped to a note's explicit area: next actions, upcoming, overdue, blocked,
active projects and recent completions. An empty area stays on the shared dashboard.
Area is not inferred from a linked project by a Base; assign it explicitly when
needed. Filters organize notes, not access permissions.

## Shared defaults

| Base | Starting view / purpose | Optional views |
|---|---|---|
| Dashboard | Now across all areas and assignees | My open, No area, Open by area/project/type/tag, all tasks, recurring records, TaskNotes Kanban |
| Projects | Active projects grouped by actual area, including blank | By parent, paused, done/dropped, All |
| People | Directory by relationship, with contact details | Organization, systems supported, birthdays, direct reports, employment anniversaries, former contacts |
| Notes | General notes in every area | Filter by area/project as needed |
| Meetings | Last 30 calendar days through today | Upcoming, All, By series; Series is an embedded view |
| Decisions | Active records in every area | Revisit, project, superseded; Series is an embedded view |
| Reference | All knowledge with optional kind/topics | How-tos, technical queries and verification checks |
| Research | Open investigations, including ideas and unset status | Active only, ideas, concluded/dropped |
| Items | All items, with unknown ownership allowed | Loans, purchase details, recorded return/warranty dates |
| Lists | All checklists in every area | By category |
| Accomplishments | All sourced outcomes, including undated records | Recent = last 90 calendar days through today |
| Opportunities | Open opportunities in every area | Closed outcomes (including accepted), All |

Templates and Examples are excluded from every shipped Base. Missing optional
fields do not make a record invalid. Default project/person tables do not require
Jira, an employer, a course, report status, or HR fields. People uses emails/phones,
falling back to legacy workEmail/workPhone/workMobile when necessary; other contact
fields remain available in the note. No new contact metadata is invented.

## Task dates, scope and ownership

Now includes active tasks and open tasks scheduled/due today or earlier, except
blocked items. Blocked has its own list. Upcoming covers today through 14 days
from today; overdue means before today. These and completed-date views exclude
recurring tasks because a task record is not an individual recurring instance.
Use the TaskNotes agenda/calendar for instances and `/report` for completion counts.
Open/backlog/area tables still include recurring task records and show their status.

Recent completed views exclude dropped, undated and future completions. “Last seven
days” means today plus the previous six calendar days; the same rule applies to
30/90-day windows. The legacy Done in range tab now defaults to a rolling 90 days;
use `/report <from> <to>` or customize its filters for a specific period.

My open includes empty-assignee tasks (Fieldbook's convention for yours) and explicit
links to a self person record. Shared lists include other assignees and show that
column. Assigned/delegated tables never establish reporting relationships. The
manager dashboard's Report tasks specifically resolves assignees to current/blank
status person notes with relationship report. A missing link is not a report.

## Optional specialized views

- **Management:** `Dashboards/People management` shows your tasks, current reports
  and tasks assigned to those reports. Company/support/birthday/employment tabs in
  People are optional; the Directory does not display those details by default.
- **Formal reviews:** [[Views/Reviews.base]] is an explicit cross-person evaluation
  inventory. Task notes tagged review are excluded. It is never embedded in the
  shared Work dashboard. Review commands retain their role/feature requirements.
- **Courses:** extra Courses/Past courses tabs in School; active courses are not
  assumed to belong to the current term. School projects/tasks need no course tag.
- **Trackers:** [[Views/Trackers.base]] lists existing Jira, Agility, GitHub and Azure
  links on any record type in any area. It only reads local properties. The optional
  Jira candidates tab requires an explicitly Jira-linked project and an undecided
  task Jira field; a missing tracker field alone is never a problem. jira: none opts
  out. The old Dashboard No Jira decision tab has the same narrow scope for existing
  links. No equivalent guesses are made about other providers.
- **Technical knowledge:** query/verification tabs stay available in Reference;
  ordinary recipes, concepts and instructions do not require systems/verification.
- **Purchase detail:** receipt/warranty/return tabs stay in Items. A recorded date
  alone does not establish current coverage, ownership or an uncompleted action.

Extra views are selected by opening a Base and choosing its view tab/menu. They are
bundled in all kits and remain available even if a setup/feature is off: Bases do
not read fieldbook.json or dynamically hide tabs. Setup switches govern AI workflows,
not data access. TaskNotes may also create its own *-default.base files; those are
plugin-managed and are not replaced by Fieldbook's shipped views.

## Embedded views and existing vaults

Project and Person are context views for embedding in the corresponding record;
Meeting/Decision Series views belong in a series note. Open those notes to see the
correct context. A standalone context Base has no person/project note to match.
A self person's Open/Done views include empty-assignee tasks. Project rollups include
the current project and its direct children using actual links, not a name substring.
They do not roll up arbitrary depth; `/project` can traverse deeper chains.

Keep existing view customizations. The updater preserves modified dashboard/guide/
Base files and supplies .fieldbook-new candidates for manual merging. Existing view
names remain usable; no notes are recategorized, moved or retemplated. Linked-property
changes may need reopening a Base to refresh its results.

Syntax reference: [Obsidian Bases syntax](https://obsidian.md/help/bases/syntax) and
[functions](https://obsidian.md/help/bases/functions). Fixture tests exercise shipped
filters; native rendering and model decisions still need app acceptance checks.

Decision revisit dates: **Decisions → Due for revisit** includes any non-superseded
record with a revisit date within 14 days (including overdue), plus undated records
explicitly marked revisit. Setting a date does not require changing active status.

## Optional Upcoming dates

Open [[Views/Upcoming dates.base]] from Dashboard's link. Next 30 days spans all
areas (including blank and disabled setups), with the original date properties
visible: task due, opportunity closing_date, decision revisit, item return_by and
warranty_end. Items can appear in both Return and Warranty tabs. The combined tab
chooses the earliest future item date, so an old return date cannot hide a later
warranty date. Past dates to review is separate; an expired warranty is not an
overdue action or proof of coverage. Returned/disposed/sold/lost items, closed
opportunities, superseded decisions and done/dropped/recurring tasks are excluded.
Keep date fields as YYYY-MM-DD and retain exact source time/zone in note bodies.

This Base is a local inventory, not a sync, notification service or date-table
expander. Canvas stage dates stored only in the body remain visible in their note;
/study and /plan-week should review them. Request selected stage tasks if separate
deadlines need to appear on task dashboards. No role-specific templates are enabled
by opening this view, and no tasks are created automatically.

## Shared follow-ups

[[Dashboards/Follow-ups]] and `Views/Follow-ups.base` remain available in all
setups. Tabs cover blocked tasks, assigned tasks, upcoming check_in dates and
active projects. [[Vault tools]] computes project next-action gaps and recorded
commitments; optional manager context requires work + people-manager. Saved
Reports are snapshots, while Bases read current note properties.

## Additional optional shared views

`Views/Goals.base` lists explicitly tagged goals across all areas. Upcoming dates adds separate agreement renewal, cancellation-notice and expiration tabs (these dates are not folded into the existing combined task/return/warranty table). Follow-ups includes overdue check-ins. All these views work in core/personal/work/school; manager cadence stays in the gated human CLI follow-up report.
