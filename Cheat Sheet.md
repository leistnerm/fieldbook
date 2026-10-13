# Fieldbook cheat sheet

**AI setup:** `python fieldbook.py` → Setup → AI assistants and optional MCP.
Select your harnesses. Python scripts + shared instructions are the default; no
AI plugins or MCP are required. Workflow names such as `/people` can be requested
in plain language if your assistant does not expose that slash command.

**Portable tools:** `python fieldbook.py tool overview` or
`python fieldbook.py tool read --path "Inbox.md"`. Use the prepared Python environment.
For note changes: read → preview → user/host approval → write with `--apply` and
current hash. Host permission behavior varies. See [[Using AI assistants]].

**Optional MCP:** enable in the same menu, run the server check, then reopen your
harness. It starts the local server with its session; writes and remote reads are
separate opt-ins. No system service is installed. See [[MCP setup]].


## Start here

[[Dashboard]] for all areas · [[Inbox]] for capture · [[Setups]] for contexts/role
[[Setups/Dashboards|Dashboard and view guide]]

Tasks live in Tasks/, views in Views/, projects/courses in Projects/, people in
People/, general notes in Notes/. Find records by tags. Your settings live in
fieldbook.json; personal instructions in AGENTS.local.md.

## Dashboards at a glance

Shared Dashboard includes personal/work/school and blank areas. Personal, Work and
School pages share next actions, deadlines, blockers, projects and recent completion
sections. Blank-area notes stay on the shared page. **My open** selects your tasks;
other shared lists show all assignees. **No area** finds uncategorized open tasks.
Date-focused lists exclude recurrence; use TaskNotes for instances. Recent done
lists exclude dropped, future and undated completions.

Browse Items, Lists, People, Notes, Projects, Meetings, Decisions, Research and
Reference without choosing a role. Courses, manager/report tasks, formal reviews,
tracker links, birthdays, employment and purchase details are optional extra views.
Saved Bases remain available for existing notes. Active templates, specialized
commands/skills and daily Dashboards pages follow configure selections. Start from
Dashboard for enabled links; Setups/ contains instructions. /help explains an
inactive workflow when requested.
Existing view customizations are preserved on upgrade. Full map: [[Setups/Dashboards]].

## Everyday commands

| Need | Command example |
|---|---|
| Capture quickly | Add a line to Inbox; optional Windows Ctrl+Alt+I |
| Process captures | `/inbox` (batch preview), `/inbox one` |
| New task | `/task replace the hallway lightbulb Saturday` |
| Record progress | `/log search migration load test passed` |
| Finish/cancel | `/close search migration`, `/close old plan dropped` |
| Plan a week | `/plan-week personal school` |
| Start a project | `/kickoff prepare the spare room before November` |
| Find problems | `/triage` |
| Summarize a project | `/project Website relaunch` |
| Completion report | `/report 2026-10-01 2026-10-31` |
| Capture a reference | `/learn` followed by source text |
| Connect notes | `/synthesize notes about learning Spanish` |
| Check links/people | `/link-check`, `/people-check` |

## Obsidian templates: two ways

| Starting point | Steps |
|---|---|
| Existing empty note | Name it in its record folder, switch to **Editing view**, then command palette → **Templater: Open insert template modal**. |
| New note | Command palette → **Templater: Create new note from template**; complete any prompts, then check the name and folder. Works from Reading view too. |

Check that both properties and body headings appear. **Do not insert into an
existing note in Reading view:** some plugin/view combinations can save properties but omit
the body. For a new properties-only note, switch to Editing view and insert again,
checking for duplicate sections. Preserve populated notes; add only missing parts.
Use TaskNotes for tasks, or insert a task template into an already-named Tasks/
file in Editing view so its title property matches. Full instructions: [[SETUP]].

## Neutral defaults, optional detail

Use the smallest template that fits. Blank fields are optional; a setup does not
turn every note into a role-specific form. All shared templates support every area.
Manual Templater insertion leaves neutral area fields blank; AI creation uses your
request/project/configured default. Existing notes keep their fields and history.

| Default | Choose extra detail when useful |
|---|---|
| Person | Professional contact or Direct report |
| Item | Purchased item for purchase/receipt/warranty details |
| Research | Experiment for hypothesis/method/observations |
| Reference | Optional kind/topics; systems/verified only for technical material |
| Project / Task | Course / Assignment for formal coursework |
| Note / completion report | Review-format only for a requested formal work evaluation |

`/1on1 Sam` works for any relationship. `/study practice Spanish using these notes`
works in any area. `/learn` accepts recipes, concepts, procedures and other supplied
knowledge. `/list lab materials` and `/item borrowed textbook from Sam` need no
personal setup. Full template guide: [[Note types]].

An unfiltered `/plan-week` includes tasks with no area and older-context notes;
`/plan-week school` scopes the plan. `/status-update` works in any area; provide an
audience and scope before making it suitable to send. `/coach` remains manager-only.

## Personal

`/home car inspection and registration renewal` · `/plan-week personal`
Use errand, maintenance, appointment, admin, routine. Due is the deadline;
scheduled is your intended work date. Configure repeating chores in TaskNotes.
Daily page when personal is enabled: `Dashboards/Personal`.

## Work — either role

`/status-update` · `/evidence me mid-year` · `/review me mid-year`
`/review me year-end 2026-01-01 2026-12-31`

Use the Person template for your self note, set relationship self, add goals under `### Goals YYYY`,
and log what you did and what changed. Both work roles prepare mid-year and year-end
self-evaluations. Edit Templates/Review-format.md for your actual form; updates
preserve it. Final reviews are immutable. No unsupported ratings or impact claims.

## Work — people manager

`/coach Alex priorities and development` (manager coaching)
`/1on1 Alex` (ordinary conversation, available in every setup)
`/review Alex mid-year` · `/review Alex year-end`

Work + people-manager activates Direct report; it starts with relationship report.
A manager link to your self note is optional.
Team sync uses those relationship values and labeled usernames in any setup;
manager links are optional for sync. Manager self-evaluations
separate your contribution from your team's results.

## School

Optional Canvas LMS: `/canvas-sync school list my courses`, then
`/canvas-sync school coursework for course 12345; planner context from 2026-10-01 to 2026-10-31`.
Enable school + Canvas first. Coursework combines assignment/quiz/discussion lists
with bounded Planner context; the date window limits Planner only. Use `quizzes`,
`discussions` or `assignments` for narrower reads. IDs/aliases prevent duplicate
records; review conflicts. Keep initial-post/reply deadlines separate, and distinguish
due dates from to-do reminders, events and opening/closing times.
Updates preserve study notes/checklists; no submissions, grade changes or roster
imports. Planner/coursework/announcements/calendar need selected courses and a date range. See [[Canvas LMS]].

`/course History Fall 2026` + syllabus · `/study History essay due October 16`
`/plan-week school` · `/term-close Fall 2026`

Course = project + course tags and term. Assignment/reading/study/exam = task.
For coursework, link each task to the course and set area school. General study
and unrelated school tasks do not require a course. Store exact submission time and
timezone in Notes. Term closeout preserves records and reviews unfinished work.
Daily page when school is enabled: `Dashboards/School`.

## Jira, Agility, GitHub Issues and Azure Boards — read only in every setup

`/jira-sync` · `/agility-sync` · `/github-sync` · `/azure-sync`
`/github-sync mine` · `/azure-sync team` · `/sync jira all in project APP`
Supply the instance if you have more than one. Default: update linked notes only;
add “also create missing tasks” to propose new tasks. No work setup is required.

| Scope | Meaning |
|---|---|
| linked | All linked local item types, using explicit provider instance |
| mine | Self person identity when mapped; otherwise configured/current remote user |
| team | Current person records with relationship self/report and exact tracker usernames |
| all | Everything in configured repositories (GitHub) or an explicit project/filter |

Choose update-only or also propose missing tasks. Review the numbered plan before
writes. Identity = provider + instance + ID. Duplicate/ambiguous links are flagged;
missing results do not delete or close anything. Partial results are labeled.

`/tracker-draft jira APP-123 describe the blocker`
`/tracker-draft agility S-01001 propose acceptance criteria`
`/tracker-draft github owner/repo#123 draft a comment`
`/tracker-draft azure 456 propose acceptance criteria`

Person identity examples: `"github:personal: your-login"`,
`"azure:office: you@example.com"` in usernames. Set your relationship to self and
your reports to report. Mark departed people former; missing identities stop team
sync. See [[INTEGRATIONS]] for a complete self/report example.

GitHub note link: `github: "owner/repo#123"` + `github_instance: personal`.
Azure link: `azure: "456"` + `azure_instance: office`. New tasks inherit their
project area or your chosen/default area. Closed is not automatically done.

Drafts are for you to enter manually. Fieldbook never changes a tracker. Setup,
limits, remote identity labels and credentials: [[INTEGRATIONS]].

## People: three templates, one record type

| Template | When to use it |
|---|---|
| **Person — default** | Friends, family, classmates, yourself, or anyone unspecified; neutral contact details and notes |
| **Professional contact** | Peer, customer, vendor, instructor or partner; organization, shared projects and commitments |
| **Direct report** | Someone you manage; goals, development, feedback, 1:1s and reviews |

`/people create Sam, a family friend`
`/people create a professional contact for Alex, our vendor at Acme`
`/people create a direct report for Jordan`

All use person tags and People/. For manual notes, insert the template from
Templates/ in Editing view, or use Templater: Create new note from template.
Automatic stubs always use Person. Relationship stays unknown until supplied, except
Direct report starts with report. Your record uses self, regardless of layout.
Existing records keep their content; add sections rather than replacing the note.
Optional report employment fields and contact formats: [[Note types]].

## Meetings and decisions

`/meeting Attachments/invite.ics` · `/meeting create a note from these pasted calendar details`

Choose one occurrence. Default: no new people. Link existing contacts or explicitly
select a few missing people; all-hands never trigger bulk creation. Calendar reads
are read only; saving asks permission. Local ICS needs no connection. For live
Google/Microsoft calendars: configure → Save → **9 sign in** → **7 choose calendars**
→ Save → **6 test**, then enable the chosen feature. Use **8** to link an existing
Series to a remote calendar series; `/meeting` prepares only requested occurrences.
See [[Calendar meetings]] and [[Calendar connections]].

`/prep Platform sync 2026-10-16` · `/actions meeting name` · `/transcript file.vtt`
`/commitments Alex last month` · `/decisions migration` · `/decision-record meeting line`

Action checkboxes become linked tasks after preview. Commitments remain promises;
they are not automatically completed tasks. Relative deadlines use the meeting's
date. Transcript retention is an explicit choice; kept text remains in Git history
if history is enabled.

## Fields at a glance

Status: backlog → active / blocked → done or dropped. Priority: 1-high, 2-normal,
3-low. Type: [[Types]]. Area: personal, work, school, or blank. Empty assignee = me.
Due = final deadline; scheduled = planned work day. Projects = most specific link.
Do not manually complete recurrence instances; tick them in TaskNotes.

## Setup, checks and updates

**Upgrade with a backup:** extract the new source ZIP outside the existing vault,
close both apps, then run `python tools/configure.py --upgrade` from the new release.
Select vault/release/backup folder → **2 Work + people manager + reviews** (or keep
settings/custom setups/features) → **7 Review, back up and apply** → type `upgrade`.
Main-menu **12** offers the same flow. A verified full backup precedes changes;
cancel leaves the original unchanged. See [[UPGRADING]] for merge/recovery steps.

**Restore a backup:** close both apps, pause sync, and run
`python tools/configure.py --restore` from an extracted source kit outside the vault,
or choose main-menu **13**. Select the original vault path → backup folder → dated
backup → review → type `restore`. The whole current vault is kept in a separate
pre-restore backup before replacement. Newer notes stay there; select that backup
to undo a restore. Works even with broken or missing target settings.

`python tools/configure.py` — guided setups, feature toggles, URLs and masked key
entry for Jira, Agility, GitHub, Azure, Canvas, Google and Microsoft. Save returns to the menu.
**3 Integrations → 5 Save → 7 choose default scopes → review/use →
5 Save → 6 Test saved connections**. GitHub/Canvas support add or replace; Jira/
Agility replace the filter. The picker shows at most 50 first-response choices;
use manual entry for unlisted scopes. **0 Exit** discards only changes since the
last Save. `--check` validates locally without network access. See [[Configuration CLI]].

**8 link a local Project, Course or Series** → local note → provider/instance → remote
scope → preview → `apply`. This immediately saves that note's binding with a backup;
connection defaults stay unchanged. A Course can link to its own Canvas school,
independent of other Courses. Ask to sync that Project/Course by name; missing or
conflicting source links require a choice. See [[Canvas LMS]] and [[INTEGRATIONS]].
Google/Microsoft Series links retain account + calendar + series identity; they
do not create notes for every occurrence. OAuth sign-in uses **9** after Save.

```text
python tools/configure.py --check
python tools/configure.py --integration-setup
python tools/configure.py --integration-setup canvas
python tools/configure.py --calendar-setup
python tools/configure.py --credential-guide
python tools/configure.py --credential-guide microsoft
python tools/configure.py --test all
python tools/configure.py --test jira --instance office
python tools/configure.py --test canvas --instance school
```

Main-menu **10** is the guided setup/test checklist for any provider. Requirements
stay offline; configure/save, calendar sign-in, scope selection, read tests and
local record links are separate actions. **6** still tests saved connections.
Outlook with Microsoft cloud uses Microsoft; Outlook with Google uses Google.
Local-only Outlook calendars use ICS. Gmail mail is not part of Google Calendar reads.

Need a key or app registration? Main-menu **11** (or **9** within guided setup)
walks through each provider with official links and read-permission instructions.
**Enter** = next, **b** = back, **open 1** = open the displayed link, **q** = return.
No credentials are requested or created in this guide. Then configure/save, sign
in for calendars, select scopes and test from the guided setup menu.

`--test` reads saved connections using their environment or OS credentials,
including configured features that are off. It never enables features or writes
remote data/local notes. `all` skips unconfigured starter connections. Inspect
scope results: skipped/unknown is not passed, and a successful read does not prove
the key lacks write permissions. Menu: **Test saved connections** after saving or
discarding edits; after Save, testing is optional and defaults to No.

Work-only manager vault (also enables self/report evaluation preparation):

```text
python tools/manage-vault.py configure --setups work --work-role people-manager --reviews on --apply
```

Personal and school commands/templates disappear from active folders when they are
kit defaults. Customized files remain as reported preservation exceptions. Restart
AI assistant after changing commands; reopen daily dashboards in Obsidian. Preview
with configure without --apply; plain JSON edits need configure --apply to sync.

For a combined vault:

```text
python tools/manage-vault.py configure --setups personal,work,school --work-role people-manager --apply
python tools/manage-vault.py health
```

Automation switches: --auto-people on, --auto-commit on. Tracker switches: --jira on,
--agility on, --github on, --azure on (configure the connection first). Unspecified settings are preserved.
Preview changes by omitting --apply. For an old TaskNotes/ layout or release update,
follow [[UPGRADING]]; do not unzip over a live vault.

## Find, connect and reuse

`/help` · `/help /people` · `/people` · `/people Alex`
`/accomplishment search migration` · `/opportunity summer internship details`
`/resume security engineer using work evidence` · `/handover project name`
`/brief compare the documented vendor options`

Ask naturally: "find tasks tagged school due this week", "find names like Jon Smyth",
"regex search APP-[0-9]+", "find notes similar to reducing latency", or "what links
to this project?" Reads/searches need no approval; saves ask with a diff. See
[[Notebook tools]] for scope, limits and optional permission settings.
After a meaningful action, the AI may suggest one useful link or new record—for
example an accomplishment after major completed work. It finishes your action first
and waits for acceptance before creating the additional item.

## Lists and item records

`/list groceries add milk and 6 eggs` · `/list packing for camping`
`/item washing machine purchase and warranty details` · `/home annual maintenance`

Item is the neutral default for owned, borrowed or shared things in any area.
Purchased item adds purchase/warranty sections when requested. Ideas stay in lists
until you want a project/task. Receipts/manuals are attachments
linked from Items/; AI needs supplied text to extract their contents. See
Setups/Household.md (personal setup) for repairs, returns, renewals, subscriptions and more.

## Dates, coverage and grouped templates

- **CLI menu 14** or `python tools/configure.py --coverage`: offline coverage and
  saved scopes. **Menu 6** tests reads; the actual sync reports scope/read time/limits.
- **Menu 3 → connection → dateFields**: choose explicit Jira/Agility/Azure date
  meanings and field IDs. Deadline, target, start, review and availability stay distinct.
- Open [[Views/Upcoming dates.base|Upcoming dates]] for the next 30 days, past dates
  to review, and separate deadline/revisit/return/warranty tabs. No new tasks or alerts.
- `/plan-week` can include requested enabled calendars and waiting-on commitments;
  `/study` keeps multi-stage deadlines separate; `/coach` supports onboarding and
  delegation; `/handover`, `/item` and `/home` help with coverage, returns and renewals.
- Shared default templates stay simple. Specialized picker names: **Person -
  Professional contact**, **Person - Direct report**, **Item - Purchased**,
  **Project - Course**, **Task - Assignment**, **Task - Study session**,
  **Research - Experiment**. School/manager layouts still require their setups.

See [[Integration coverage]], [[INTEGRATIONS]] and [[Note types]] for details.

## Local maintenance and capture

`python tools/configure.py` → **15 Vault tools**:

| Pick | Action |
|---|---|
| 1 | Back up now, verify, optionally prune older verified backups after a separate preview |
| 2 | Check settings, dependencies, links, incomplete templates and shared remote identities; no repairs |
| 3 | Compare `.fieldbook-new` text with your custom version; merge manually; JSON excluded |
| 4 | Choose an enabled template and create a complete record after preview |
| 5 | Show/save selected integration metadata; tests are not syncs; no automatic receipts |
| 6 | Selected `.eml`, text, PDF or image → reviewed new Reference; no mailbox access |
| 7 | Follow-up review, optional dated Reports snapshot; manager context only when enabled |

Direct example: `python tools/configure.py --vault-tools backup`. Other actions:
`doctor`, `compare`, `create`, `activity`, `intake`, `followups`. Restore stays in
main-menu **13**. [[Vault tools]] has full instructions and limits.

[[Dashboards/Follow-ups]] works across all areas. Optional `check_in: YYYY-MM-DD`
is a date to review a record, separate from its deadline. Assigned tasks can be
yours; missing meeting/evidence notes are not performance judgments.

No `.venv`? It is a folder you generate, inside `fieldbook_core`:

```text
# macOS/Linux, from the extracted kit or vault folder
python3 -m venv fieldbook_core/.venv
fieldbook_core/.venv/bin/python -m pip install -r fieldbook_core/requirements.txt
fieldbook_core/.venv/bin/python tools/configure.py
```

On Windows use `py -m venv fieldbook_core/.venv`, then
`fieldbook_core\.venv\Scripts\python.exe` for the other commands. See [[Notebook tools]].
PDF text extraction additionally uses `requirements-intake.txt`; image OCR needs
local Tesseract. [[Selected intake]] explains setup, provenance and review.

**Windows preview access error:** Check folder permissions and close applications.
For a restricted default temporary location, the new `--upgrade --temp-dir
"existing local folder"` option routes all staging copies elsewhere. Keep this
folder outside the vault/release/backups; see [[UPGRADING]].

## Quick actions

| Need | Action |
|---|---|
| Prepare Python and open menus | `python fieldbook.py` (Windows: `py fieldbook.py`) |
| Work + manager upgrade | Maintenance > Upgrade > select vault > Work + people manager > review > verified backup/apply |
| Backup / restore / check | Maintenance menu |
| Meeting from calendar | Daily use > Calendar meeting picker; select one occurrence; optional Series/people |
| Manager 1:1 cadence | Daily use > Manager 1:1 cadence; explicitly mark Series and meetings |
| Overdue follow-ups | `Views/Follow-ups.base` > Overdue check-ins |
| Goal / renewal agreement | `/goal`, `/renewal`; optional in every setup |
| Share selected project/course/evidence | Daily use > Selected export; review scope/privacy before export |
| Existing numbered instructions | Advanced numbered menu or `tools/configure.py --advanced` |

Manual templates: switch the target note to **Editing view** before insertion, or use **Templater: Create new note from template**. Confirm properties and body headings. Integrations remain read-only; proposed remote edits use `/tracker-draft`.

## 1.0 everyday path

| Goal | CLI | AI assistant |
|---|---|---|
| First use / revisit setup | `python fieldbook.py` > Setup > Guided onboarding | `/help` explains setup; settings stay human-operated |
| Review today | Daily use > Daily review | `/daily-review [area]` |
| Review the week | Daily use > Weekly review | `/weekly-review [area]` |
| Schedule chosen work | Create/review local records | `/plan-week`; date changes need approval |
| Compare a sync | Integrations > Sync conflict preview (selected JSON proposal) | `/sync` uses notebook_preview for field comparisons |
| Recover safely | Maintenance > Backup / Upgrade / Restore | Explain the human workflow; no AI settings or shell bypass |

Sync table: Field · Last reviewed source · Local · Proposed · Result. Keep local
changes unless you choose otherwise. First sync and conflicting changes need a
choice; missing values never clear notes. Baselines are saved only with the
approved local edit. All remote integrations remain read-only.

Reviews keep deadlines separate from planned work and other date types. Local
meeting notes do not prove calendar availability. A work-scoped review leaves mixed
Inbox text out. Focus and saved snapshots do not silently change tasks. Read
[[Everyday workflow]] and [[Sync previews]] for the full sequence.

## Adapt a performance review

With Work and reviews enabled, `/review me mid-year` or `/review me year-end`
uses `Templates/Review-format.md`. Its generic prompts cover goals, outcomes,
collaboration, challenges, learning, next priorities and support. Customize the
prompts to your needs; no organization-specific criteria are assumed. See
[[Examples/Work walkthrough]] for a fictional illustration, never review evidence.

## Refresh existing records

- `/migrate-records people, first 5` or “Run Fieldbook's record-migration workflow.”
- `python fieldbook.py tool template_status` lists stored versus installed template versions; it changes nothing.
- Preview exact paths and diffs, create a verified Maintenance > Backup, then approve one batch. The AI pauses after each batch.
- Preserve all information, custom properties, links and remote identities. Unknown provenance needs review; newer records are never downgraded.
- New records carry `templateName` and integer `templateVersion`; these are independent of the Fieldbook release. See [[UPGRADING]].
