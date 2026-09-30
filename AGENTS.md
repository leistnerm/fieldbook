# Rules for this vault

If `AGENTS.local.md` exists, read it too and follow it; where it conflicts with
this file, it wins. Don't edit this file for the user's own rules; put those
in `AGENTS.local.md`.

This is the user's work-task system. Obsidian + TaskNotes own the task files; you
edit them on request. You act only when asked. Never create, close, or change
a task, meeting, or person note the user didn't ask about. Exceptions: the
`/actions` command creates missing person notes for the people it assigns, and
the `auto-people` plugin creates a stub for any new name in a people field.
When you add a new person to a note, link `[[Name]]` and let the plugin create
their note (it appears within a minute); don't write person notes yourself.

`opencode.json` blocks web access, git writes, and file deletion (the one
exception is `/transcript`, which keeps or removes files in `Transcripts/`
through its script, after the user says to). When a
permission blocks you, stop and tell the user. Never find another way to do the
same thing.

## Where things live

| what             | how to find it                    | where new ones go            |
|------------------|-----------------------------------|------------------------------|
| tasks            | `tags` include `task`             | `TaskNotes/Tasks/<Title>.md` |
| people           | `tags` include `person`           | `People/<Full Name>.md`      |
| meetings         | `tags` include `meeting`          | `Meetings/YYYY/YYYY-MM/YYYY-MM-DD <Title>.md` (year and month of the meeting's `date`; create the folders if missing) |
| transcripts      | `tags` include `transcript`       | `Transcripts/<date> <title> transcript.md` (made by `/transcript`; only kept ones; raw `.vtt` and `Transcripts/.work/` are git-ignored) |
| meeting series   | `tags` include `series`           | `Meetings/Series/<Name>.md`  |
| decision records | `tags` include `decision`         | `Decisions/YYYY-MM-DD <Short title>.md` |
| projects         | `tags` include `project`          | `Projects/<Name>.md`         |
| research         | `tags` include `research`         | `Research/<Title>.md`        |
| reference notes | `tags` include `reference`        | `Reference/<Title>.md`       |
| inbox            | `Inbox.md` (one line per capture) | appended by the user's hotkey; only /inbox removes lines |
| reports          | —                                 | `Reports/`                   |
| reviews          | `tags` include `review`           | `Reports/Reviews/<Person> - YYYY-MM <mid-year\|year-end> review.md` |
| views (.base)    | —                                 | `TaskNotes/Views/` (don't edit unless asked) |
| templates        | —                                 | `Templates/`                 |

Find notes by tag, never by folder. Never move or rename files.

## Tasks

Frontmatter is the only source of truth. Don't restate status, dates, or
assignees in the body.

```yaml
title: Short imperative title
status: backlog            # backlog | active | blocked | done | dropped
priority: 2-normal         # 1-high | 2-normal | 3-low
type: task                 # must be a value listed in Types.md
projects: []               # optional; "[[Project]]" links; may be several
tags: [task]               # always include task; add topic tags freely
assignee: []               # optional; "[[Person]]" links; empty = the user's own
requester:                 # optional; who asked for it, one "[[Person]]" link
jira:                      # issue key (PROJ-123), `none` = decided not to, empty = not yet
due:                       # optional; YYYY-MM-DD
scheduled:                 # optional; YYYY-MM-DD
dateCreated: 2026-09-29
completedDate:             # set when closing
```

TaskNotes manages these — never write them: `dateModified`, `recurrence`
(unless creating a recurring task on request), `complete_instances`,
`skipped_instances`, `timeEntries`.

- Leave optional fields present but empty; never delete keys.
- `type` must be in `Types.md`. If nothing fits, ask the user — don't invent a type.
  If they approve a new one, add it to `Types.md` in the same change.
- Assignee links must point at a person note, chosen per the People rules on
  same names. The `auto-people` plugin creates missing ones for frontmatter
  people fields within a minute.

Body:

```markdown
## Notes
Context, links, acceptance criteria.

## Log
- 2026-09-29: what happened (newest last)
```

Log lines are dated, one line each, append-only — never edit or delete an old
line. When a Jira comment is posted, log `- YYYY-MM-DD: posted to Jira`. A task
created from a meeting gets `- YYYY-MM-DD: from [[<meeting note>]]`.

### Operations

- **Create**: fill title, status `backlog` (or `active` if the user says they're on
  it), priority `2-normal` unless told, type, `dateCreated` today. Show the user the
  frontmatter before writing if any field was a guess.
- **Close**: `status: done` and `completedDate: <today>` in the same edit, plus
  a closing log line. Use `dropped` (also with `completedDate`) for things that
  won't be done — never `done`.
- **Recurring tasks**: never complete an occurrence yourself; tell the user to tick
  it in TaskNotes (it advances `scheduled` and records `complete_instances`).
  To create one, set `recurrence` as an RRULE, e.g.
  `DTSTART:20261002;FREQ=WEEKLY;BYDAY=FR`.
- **Reports**: completed work = non-recurring tasks with `completedDate` in
  range (exclude `dropped` unless asked) + each date in `complete_instances`
  within range for recurring tasks.

## Jira

Work often never reaches Jira; help the user catch it. `/jira-status` (optional)
reads an issue and compares it with the task; nothing is ever written to Jira. The `jira` field
has three states: an issue key, `none` (they decided it doesn't belong — never
suggest it again), or empty (not decided yet).

A task with empty `jira` **probably belongs in Jira** if any of these hold:
- its project, or any project up its `parent` chain, has a `jira` epic
- it's assigned to someone else
- it's a `request`, or has a `requester`
- it's engineering work: code, config, deployment, an import/integration, a
  bug, an incident follow-up
- it's more than about half a day of work, has 3+ log lines, or has been
  active 7+ days
- it's blocked on, or needed by, another team
- it came from a meeting action item or a decision's follow-ups

It **doesn't** if its type is `training`, `poll`, `corporate`, or `routine`,
or it's people management (reviews, 1:1 follow-ups, hiring admin) — unless
the user says their team tracks that in Jira.

Done tasks from the last 14 days that meet the criteria are worth logging
retroactively (so the work is visible) — list them separately, lower priority.

**Drafting an issue** (never create it — the user pastes it):
- Summary: the task title, rewritten as a clear Jira summary.
- Issue type: Task, Story, or Bug — best guess, say so.
- Parent/epic: the nearest `jira` epic up the project's `parent` chain.
- Assignee: the task's assignee (name), else the user.
- Due date, and priority mapped High/Medium/Low from `1-high`/`2-normal`/`3-low`.
- Description: goal and context from Notes, acceptance criteria if stated,
  current state from the Log. Plain, no filler.

When the user gives the key: set `jira: <KEY>` and log
`- YYYY-MM-DD: added to Jira as <KEY>`. When they say no: set `jira: none`.

## Meetings

```yaml
date: YYYY-MM-DD
series:              # optional; "[[Series Name]]" for recurring meetings
attendees: []        # "[[Person]]" links
projects: []
transcript:          # optional; "[[<date> <title> transcript]]" if one is kept
tags: [meeting]
```

Every file in `Templates/` is a Templater template for the user. When you create
a note from one, leave out any `<%* … -%>` block and write real values in
place of every `<% … %>` expression (dates as `YYYY-MM-DD`). Never copy
template code into a note.

A series note (`Meetings/Series/<Name>.md`, from `Templates/Series.md`) holds
the recurring meeting's cadence, usual attendees, projects, purpose, and
standing agenda. New meetings in a series copy `attendees` and `projects` from
it. 1:1s don't use series — they're found by attendee.

A 1:1 is an ordinary meeting note named `YYYY-MM-DD 1on1 <Person>` (person's
note name without a qualifier), with that person in `attendees`.

Every note title must be Windows-safe: never use `: ? * " < > | \ /` — write
`-` instead.

Sections: Agenda, Notes, Decisions, Action items, Commitments.

- **Decisions** are plain lines by default. An important one can be promoted
  to a decision record (below); its line then becomes a `[[record]]` link —
  the record holds the text from then on.
- **Action items** become tasks. An unconverted item is a `- [ ]` line; a
  converted one is a `[[task]]` link.
- **Commitments** are a record of what others agreed to — never tasks. Format:
  `- [[Person Name]] (Department): what — by YYYY-MM-DD` (department and date
  optional). The date is always ISO, never `10/10`: turn "by Friday" into a
  real date from the meeting's `date`, and if no date was given leave `by` off. Never convert a commitment, add checkboxes to it, or create a
  person note for a name in it. When writing one, keep that format.
- A person's department comes from their person note's `team` (or
  `company`, for people outside the user's company) if the note exists,
  otherwise from the line's parenthetical.
- Never rewrite the user's notes — only replace action lines with links when asked.

## Projects

Project notes are optional — a `projects` link to a note that doesn't exist
is fine. Create one only when the user asks, from `Templates/Project.md`.

```yaml
tags: [project]
status: active       # active | paused | done | dropped
parent:              # "[[Parent project]]" for a sub-project; empty = top level
owner:               # "[[Person]]"
stakeholders: []     # "[[Person]]" links
jira:                # epic key
jira_url:            # this project's Jira address (optional; used by /jira-status; empty = parent's)
start:               # YYYY-MM-DD
target:              # YYYY-MM-DD
```

Body: Goal, Scope, Notes, Log (dated, append-only), then embedded views —
never edit the embeds.

- **Link to the most specific project only.** A blog-migration task gets
  `projects: ["[[Website - Blog migration]]"]` — never also `[[Website relaunch]]`; the
  parent rolls it up through `parent` (one level: a grandparent doesn't see
  its grandchildren's work).
- Sub-project names start with the parent's short name: `Website - Blog migration`.
- New sub-area → new project note with `parent` set. Small one-offs can link
  to the parent directly instead.
- When a project finishes: `status: done` and a log line. Never delete it.

## Research and experiments

The user's own notebook for things to look into or try. Never goes into Jira, and
nothing in Jira or in tasks links to it. Created only when the user asks, from
`Templates/Research.md`.

```yaml
tags: [research]
kind: research         # research | experiment
status: idea           # idea | active | concluded | dropped
question:              # one line
projects: []           # optional "[[Project]]" links
started: YYYY-MM-DD
concluded:             # set with status concluded or dropped
```

Body: Question, Hypothesis (experiments only), Method, Findings, Conclusion,
Next, Log (dated, append-only).

- Findings and Conclusion hold only what the user says or what a logged run
  showed — never invent results; mark gaps with `?`.
- Closing: `status: concluded` (or `dropped`) with `concluded` set and a log
  line. Never delete a note, and never delete a dropped one — a dead end is
  still a result.

## Reference notes

Things the user found and wants to find again: how-tos, queries, request
instructions. One note per finding, in `Reference/`, from
`Templates/Reference.md` (`/learn`, or Ctrl+Shift+M).

```yaml
tags: [reference]
kind: how-to           # how-to | query | instructions | other
systems: []            # names, reused from people's `supports` where they match
verified:              # YYYY-MM-DD, empty until the user confirms it still works
source:                # where it came from (optional)
```

Body: Summary (one line: what it is, when to use it), Details, Log (dated,
append-only).

- Details hold the user's own words. Put queries and commands in code blocks
  exactly as given; never add steps, fix, or improve them; mark gaps with `?`.
- Never store a password, token or key. If the input has one, leave it out and
  say so.
- Leave `verified` empty on a new note. Set it only when the user says they
  confirmed it; when they do, update it and add a Log line. The "Not verified
  in a year" view lists empty and old dates.
- One note per finding: before making one, look for an existing note on the
  same thing and offer to update it instead.
- Who supports a system is not a Reference note; it goes in the person's
  `supports`.
- Never delete a note; if it is obsolete, say so in its Log.

## Decision records

For decisions important enough to need a full record. Created only when the user
asks (`/decision-record`), from a meeting line or from scratch.

```yaml
date: YYYY-MM-DD       # when decided
status: active         # active | revisit | superseded
meeting:               # "[[meeting note]]" if decided in one
series:                # copied from the meeting
projects: []
deciders: []           # "[[Person]]" links
revisit:               # YYYY-MM-DD, with status: revisit
supersedes:            # "[[older record]]"
superseded_by:         # "[[newer record]]"
tags: [decision]
```

Body: Decision, Context, Options considered, Rationale, Consequences &
follow-ups, Log (dated, append-only).

- Never invent rationale or options — use what the notes and the user say; mark
  gaps with `?`.
- Never edit a superseded record's Decision text; supersede it with a new
  record and link both ways (`supersedes` / `superseded_by`, `status:
  superseded` on the old one, log line on both).

## People

```yaml
tags: [person]
aliases: []          # other names they go by; the plain name once qualified
status: current      # current | former
relationship:        # self | report | manager | skip-level | peer | stakeholder | vendor | other
workerType:          # employee | contractor | consultant | vendor | government | competitor | other
company:             # employer — the user's company for colleagues, else vendor/partner/customer
title:
team:
manager:             # "[[Person]]"
location:
timezone:
hireDate:            # YYYY-MM-DD (drives work anniversaries)
contractEnd:         # YYYY-MM-DD, for contractors and consultants
birthday:            # YYYY-MM-DD; year 1900 = year unknown
employeeNumber:      # text, quoted, so leading zeros survive
workEmail:
workPhone:
workMobile:
otherEmails: []      # "label: value", e.g. "personal: a@example.com"
otherPhones: []      # "personal mobile: 555-0102"
addresses: []        # "personal: 2 Oak Ave, Springfield"
usernames: []        # "system: name", e.g. "jira: jsmith"
supports: []         # systems they support, e.g. ["LDAP", "SSO"]
```

Body sections: Family, Personal notes, Job history (table), Goals &
development, Feedback & recognition, then the embedded views — never edit the
embeds.

- Only record personal details the user gives you. Never guess or fill in
  family, contact, or date fields from anywhere else.
- `otherEmails`, `otherPhones`, `addresses` and `usernames` are lists of
  `"label: value"` strings. A value given without a label: ask for the
  label. Reuse the label spellings already in the vault (`personal`,
  `personal mobile`, `home`, `jira`); never guess one.
- `supports` holds system names. Reuse the spelling already used in any
  person's `supports` or any Reference note's `systems`; ask before adding a
  new spelling. "Who supports X?" is answered from `supports` (ignore
  case), then point to Reference notes whose `systems` include X.
- `workerType` is what they are (employment kind); `relationship` is how they
  relate to the user. They are independent: a contractor can be a report.
  Ask if unclear; never guess it from a company name.
- Feedback & recognition is dated and append-only, like a task log.
- Goals go under a `### Goals YYYY` heading in Goals & development, one per
  line. They're set per person, per year, and usually few. A new year gets
  a new heading above the last; never edit or delete a past year's goals.
- When someone leaves: `status: former`. Never delete a person note.

### Same name, different people

- A person note is named `First Last` (the user's own note is just their name). When two people share a name, both
  are qualified: `First Last (Company)` for people outside the user's company,
  `First Last (Team)` for colleagues. Each gets the plain name in `aliases`.
- Before linking or creating a person, check every person note's name and
  `aliases`. More than one could match: ask the user which, showing each one's
  company, team, and title. Never guess.
- Adding a person whose name is already taken: create the new note with its
  qualifier, add the plain name to its `aliases` and to the existing note's
  `aliases`, then tell the user to rename the existing note in Obsidian (right-click
  → Rename) to its qualified name, so Obsidian updates every link to it. Don't
  rename it yourself — links would break.
- In frontmatter, link the full note name with no display text:
  `"[[John Smith (Acme)]]"`. In body text, `[[John Smith (Acme)|John Smith]]`
  is fine.
- Commitments lines use the qualified name too, so /commitments finds the
  right person.

## Reviews

Any help with a performance review or self-assessment follows
`.opencode/commands/review.md` and `Templates/Review-format.md`: the form's
sections and values, every statement cited from the vault, nothing
invented, no ratings or comparisons between people. A review with
`status: final` was submitted: never edit it.

## History

The vault is a git repository. The `auto-commit` plugin commits after each of
your replies as `opencode: …`; Obsidian Git commits the user's edits as `vault: …`.

- You may read history (`git log`, `git diff`, `git show`) to answer "what
  changed" or "what did this say before" questions.
- Never run `git commit`, `reset`, `checkout`, `restore`, `revert`, `rebase`,
  `stash`, or `push`. To bring back an old version, show the user the diff and, on
  their yes, write the old content into the file as a normal edit.

## Style for drafted text (Jira comments, status updates)

Plain, specific, short. Lead with outcome, then what's next, then blockers.
No filler. Never post anything anywhere — output text for the user to paste.
