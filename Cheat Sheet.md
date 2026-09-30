# Cheat Sheet

Home: [[Dashboard]] · Install: [[SETUP]] · What each part does: [[Features]] · Using the assistant: [[Using opencode]] · Task types: [[Types]]

## Where things live

Folders, fields, statuses and naming rules are in [[AGENTS]] ("Where things
live" and each note type's section) — the one place they're written down.

Move or rename files **only inside Obsidian**, so links update.

## opencode commands

Open the vault folder in opencode Desktop. Plain requests work too ("Alice's hire
date is 2021-03-01", "what's blocked on Raj?").

| command | does | example |
|---------|------|---------|
| `/task` | create a task from a description | `/task Alice to update the runbook by Fri, high, PROJ-88` |
| `/log` | add a dated log line (updates status if it says so) | `/log runbook blocked on infra access` |
| `/jira-status` | (optional) read a Jira issue and compare it with the task; never writes to Jira | `/jira-status ABC-123` · `/jira-status runbook` |
| `/close` | mark done (or dropped) and set completion date | `/close runbook` · `/close vendor eval dropped` |
| `/actions` | turn a meeting's Action items into tasks (asks first) | `/actions` · `/actions platform sync` |
| `/commitments` | search meeting Commitments | `/commitments Finance last month` |
| `/decisions` | search decisions (meeting lines + records), flags superseded ones | `/decisions migration this quarter` |
| `/decision-record` | promote a decision to a full record, or record one made outside a meeting | `/decision-record migration after freeze` |
| `/prep` | prep the next meeting in a series; offers to create the note | `/prep platform sync` · `/prep platform sync 2026-10-06` |
| `/1on1` | prep a 1:1 agenda; offers to create the meeting note | `/1on1 Alice` |
| `/project` | project status rolled up across sub-projects + draft update | `/project website relaunch` · `/project blog migration last quarter` |
| `/jira-check` | find tasks that belong in Jira, draft the issues, record the keys | `/jira-check` · `/jira-check blog` |
| `/jira-comment` | draft a Jira comment from a task's log | `/jira-comment PROJ-88` |
| `/status-update` | draft the weekly status update | `/status-update` |
| `/report` | what got done in a range | `/report 2026-07-01 2026-09-30` · `/report 2026-07-01 2026-09-30 Alice` |
| `/triage` | find overdue, blocked, stale, broken items | `/triage` |
| `/learn` | file something you found (how-to, query, instructions) as a Reference note, or record who supports a system | `/learn to find the server locking an account: <query>` · `/learn Alice supports LDAP and SSO` |
| `/inbox` | sort captured lines one at a time into tasks, people, meetings, projects | `/inbox` |
| `/transcript` | turn a Teams transcript into meeting notes: attendees, decisions, actions, commitments | `/transcript` · `/transcript platform sync` |
| `/review` | draft a mid-year or year-end review / self-assessment in the company form | `/review Alice mid-year` · `/review me year-end` |

opencode never posts anywhere — drafts are for you to paste.

## Task fields

Statuses, priorities and fields: [[AGENTS]] → Tasks. Two habits: `blocked` means
log what you're waiting on; a task that won't be done is `dropped`, never
`done`. Allowed `type` values: [[Types]].

## How to…

**Capture anything, fast** — **Ctrl+Alt+I** from any app (Outlook, Teams,
Obsidian closed): type one line, Enter. It lands in [[Inbox]] with the date
and time. Don't decide what it is yet. Later, `/inbox` goes through them one
at a time and files each where it belongs (task, person note, commitment,
project, Jira) or drops it.

**Add a task** — TaskNotes' create-task command (fill the form), or `/task …`.
Quick one-liners are fine; opencode asks if it had to guess.

**Projects and sub-projects**
- Big project (e.g. [[Website relaunch]]) → note in `Projects/` from template
  *Project*.
- Distinct area inside it (a new import, a workstream) → its own project note
  named `Parent - Area` (e.g. `Website - Blog migration`) with
  `parent: "[[Website relaunch]]"`. Quickest: type the link somewhere, click it
  to create the note, insert the template, set `parent`.
- Random one-off under the big project → just link the task to the parent.
- Tasks, meetings, decisions link to the **most specific** project only. The
  parent page rolls up its sub-projects' tasks, meetings, and decisions —
  one level down only, so keep project nesting to parent and sub-project.
- Status of the whole thing → `/project website relaunch`.
- Done → set `status: done`; it moves to the Done view in
  [[TaskNotes/Views/Projects.base|Projects]].
- A project can be just a link with no note — make the note when it's worth it.

**Delegate** — set `assignee` to the person (`[[Alice]]`; several allowed).
It shows in their person note and the Delegated view.

**Update progress** — `/log <task> <what happened>`. Change status on the
kanban or in the task; the log is the history.

**Finish** — `/close <task>`, or set status Done in TaskNotes. Won't happen →
`dropped`, never `done`. Don't use TaskNotes' Archive.

**Recurring task** (weekly status, monthly report…) — create it in TaskNotes
with a recurrence. **Always tick occurrences in TaskNotes**, not opencode —
that's what records the completion history.

**Run a meeting**
1. **Ctrl+Shift+M** (Templater: *Create new note from template* → *Meeting*),
   type the title. The note is dated today and filed in this month's
   folder. Fill `attendees` (and `projects` if relevant). For a meeting
   on another day, use `/prep`, or fix `date` and drag the note to its
   month.
2. During: Agenda / Notes / Decisions as you go.
3. Things you'll track → **Action items** as `- [ ] Alice to X by Friday`.
4. Things others took on that you just want on record → **Commitments**,
   no checkbox: `- [[Dana Lee]] (Finance): circulate budget — by 2026-10-10` (always a full date).
5. After: `/actions` (or the convert button per line). Commitments stay as
   they are.

**Recurring meeting** (weekly sync, staff meeting…)
1. Once: new note in `Meetings/Series/`, insert template *Series*; fill
   cadence, attendees, projects, purpose, standing agenda.
2. Before each one: `/prep <series>` → draft agenda from the standing agenda +
   open action items, due commitments, and decisions to revisit from recent
   meetings. Say yes and it creates the meeting note, linked to the series.
3. Making a note by hand instead? Fill `series: "[[<Series name>]]"`.
4. The series note lists every meeting in it.

**From a Teams transcript** — in Teams, open the meeting's Recap → Transcript →
Download → `.vtt`, and save it in the vault's `Transcripts/` folder. Run
`/transcript`. It converts the file, drafts the meeting note (or fills an
existing one), and shows you the draft first. It leaves Action items as
checkboxes for `/actions`. Finally it asks: **keep** the converted transcript (linked from
the note's `transcript` property, and tracked by git, so it stays in history
even if you delete it later) or **delete** it. The raw `.vtt` is always
deleted, and is never committed. Use only transcripts you're allowed to keep and to send to your
model provider.

**1:1** — `/1on1 <person>` before; say yes to create the meeting note with the
agenda. 1:1s are ordinary meeting notes with the person in `attendees`.

**"What did X agree to?"** — `/commitments <person or department> <range>`.

**Decisions**
- In a meeting: one line each under **Decisions**. That's enough for most.
- "What did we decide about X?" → `/decisions X <range>`; it also says if a
  later decision changed it.
- Important one (big impact, contested, will be questioned later) →
  `/decision-record <which>`. opencode drafts context, options, rationale from
  the meeting and asks you for what's missing; the meeting line becomes a link.
- Decided outside a meeting (email, chat) → `/decision-record <what was decided>`.
- Changed your mind → `/decision-record` the new one; it marks the old record
  superseded and links both.
- Want to revisit later → set `status: revisit` and a `revisit` date; it shows
  on the Dashboard and in `/prep`.

**New person** — easiest: just link them (`[[Full Name]]`) as an attendee,
assignee, owner, stakeholder, decider, or manager. With opencode open, their
note appears in `People/` within about a minute (toast in opencode; the note
says where they came from). Names in **Commitments** never get notes.
Or by hand: new note in `People/`, insert template *Person*.
Then set `company`, `relationship` (report / manager / peer / …), and
`manager`. Tell opencode details as you learn them; it files them in the
right field or section: `workerType` (employee, contractor, consultant,
vendor, government, competitor), `contractEnd`, `employeeNumber`, work and other emails and phones,
`addresses`, `usernames` on other systems ("jira: jsmith"; a stray
`[[jsmith]]` then warns instead of making a duplicate person) and `supports`
(systems they support). Typo'd a name and got a stray note? Just delete it.

**Two people, same name** — rules: [[AGENTS]] → People → Same name. Your part:
link the new one as `[[John Smith (Contoso)]]` (its note is created), then
rename the old note **in Obsidian** (right-click → Rename) to its qualified
name, so links update. Ask opencode to do the aliases ("add John Smith from
Contoso"). A bare `[[John Smith]]` that could be either gets a warning toast
and no note; fix the link. `/triage` lists any you missed. Typing
`[[John Smith` in Obsidian offers both notes (via their aliases).

**Record feedback or recognition** — "log feedback for Alice: …" → dated line
in their Feedback & recognition section (feeds reviews and `/1on1`).

**Someone leaves** — set `status: former`. Never delete the note.

**Jira**
- `jira` field: a key (`PROJ-123`), `none` (decided it doesn't belong — never
  asked again), or empty (not decided).
- Getting things into Jira: `/jira-check` → for each candidate answer
  **draft** (it writes the issue to paste; give it the key after),
  **none**, or **skip**. The rules for what belongs are in `AGENTS.md` → Jira.
- You're also nudged by `/task` and `/actions` when a new task qualifies,
  by `/triage` weekly, and by the Dashboard's "No Jira decision yet" list.
- Already created an issue yourself? Tell opencode "Blog URL mapping is
  PROJ-456" and it links and logs it.
- Updates: keep the task log current, `/jira-comment <KEY>` to draft a
  comment, paste into Jira, say yes when asked so it logs "posted to Jira".

**Research and experiments** — a private notebook; it never goes to Jira and
nothing links to it. **Ctrl+Shift+M** → *Research*, type the title; it's filed
in `Research/`. Set `kind` (research or experiment), `question`, then `status`:
`idea` → `active` → `concluded` (or `dropped` — keep dead ends). Write Method
and Findings as you go, and add dated Log lines. Ideas captured in the inbox
become `idea` notes via `/inbox`. Active ones show on the Dashboard; all of
them in [[TaskNotes/Views/Research.base]].

**Reference notes** — things you found and want back later. `/learn <what
you found>`, or **Ctrl+Shift+M** → *Reference*. One note per finding in
`Reference/`, with a `kind` (how-to, query, instructions), the `systems` it's
about and `verified` (when you last confirmed it). Find them in
[[TaskNotes/Views/Reference.base]] or ask opencode. "Who supports LDAP?"
reads the `supports` list on people; the People view *Supports* shows it.
Never put passwords or tokens in a note.

**Update the kit** — `VERSION` is your release. Download a newer release zip
from the GitHub releases page, commit your vault, then run
`.opencode\scripts\update-fieldbook.ps1 -From <zip>` (it only shows what it
would do until you add `-Apply`). Files you edited are kept and the new copy
lands beside them as `.fieldbook-new`. Put your own rules in `AGENTS.local.md`.
Details: [[Features]] → Updating the kit.

**Look back** — `/report <from> <to>`, or the *Done in range* view in
Dashboard.base (edit its two dates).

**Performance review / self-assessment**
- Goals: at the start of each year, tell opencode "Alice's 2027 goals: …".
  They go under `### Goals 2027` in her note, and past years stay.
- `/review <person> mid-year` or `/review <person> year-end` (`me` for your
  own). The period runs from January 1 to today unless you give dates. It
  drafts Goals, What was achieved, and How it was achieved (by the values in your form),
  cites a note for every statement, and lists evidence gaps for you to fill
  from memory. It never gives ratings. A year-end draft builds on that year's
  mid-year review.
- Say yes to save as `Reports/Reviews/Alice - 2026-06 mid-year review.md`.
  Edit it until done, then set `status: final` when submitted; after that
  it's never changed.
- Look back: each person note's **Reviews** section lists theirs, newest
  first. [[TaskNotes/Views/Reviews.base]] shows everyone's by year, plus
  open drafts.
- The form's sections and the values live in `Templates/Review-format.md`.
  Edit that when the form changes.
- Reviews are only as good as what you logged, so the habit that pays off is
  recording feedback and task log lines as they happen.

**History — what changed, and undo** (every change is in git: yours every
10 minutes as `vault: …`, opencode's after each reply as `opencode: …`)
- One note: ask opencode "what changed in <note> this week".
- Whole vault: command palette → *Git: Open history view* (click a commit to
  see its files), or ask opencode "what did you change today".
- Undo: ask opencode "put <note> back the way it was on Monday". It shows the
  diff and restores it on your yes. It never rewrites git history, so the
  undo is itself a new change you can undo.
- Deleted a note by accident: same thing — "bring back <note>".

**New task type** — add a row to [[Types]].

**Views look stale after opencode edits** — command palette →
*TaskNotes: Refresh cache*.

## Suggested rhythm

- **Daily**: Dashboard → Now and Overdue; `/inbox` if it has anything.
- **Monday**: `/triage`, then `/jira-check` if it flags anything.
- **Friday**: `/status-update`, then tick the recurring task.
- **Before each 1:1**: `/1on1 <person>`. Before each recurring meeting:
  `/prep <series>`.
- **Month/quarter end**: `/report` → save to `Reports/`.
- **Start of month**: Dashboard → This month (birthdays, anniversaries).
- **Review season** (mid-year and year-end): `/review me <kind>`, then
  `/review <person> <kind>` for each report — a few weeks early, so the
  evidence gaps have time to be filled.
- **Start of year**: record each report's goals for the year.
