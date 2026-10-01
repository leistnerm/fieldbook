# Features

What the vault does, one module at a time, so you can adopt all of it or only
some. Install: [[SETUP]]. Day-to-day commands and how-tos: [[Cheat Sheet]]. Getting more out of
opencode, and writing your own commands: [[Using opencode]].
Field and folder rules: [[AGENTS]].

## How the pieces fit

- **Notes are plain markdown** with properties (frontmatter). Nothing is
  locked in.
- **Obsidian** shows them: **TaskNotes** manages task files and boards,
  **Bases** builds the lists and dashboards, **Templater** makes new notes from
  templates.
- **opencode** is the assistant. It follows `AGENTS.md` and offers the slash
  commands in `.opencode/commands/`. It edits notes but never posts anywhere,
  never rewrites git history, and never deletes files.
- **git** records every change, so anything can be undone.

## Removing a module

Delete its files, then remove its rows from the "Where things live" table and
its section in `AGENTS.md`, and its embeds in `Dashboard.md`. A command file
you don't delete just shows up in the `/` list; it does no harm.

## The modules

**Core: tasks** (keep this one)
- What: a task is a note with status, priority, type, due date, project,
  assignee, requester, and a dated log. Boards, overdue/blocked lists, by
  project, by type, recurring tasks, date-range views.
- Files: `TaskNotes/`, `Types.md`, `Templates/Task body.md`, `Dashboard.md`.
- Commands: `/task`, `/log`, `/close`, `/triage`, `/report`, `/status-update`.
- Needs: TaskNotes, Bases.

**Projects and sub-projects**
- What: a project note with owner, status and purpose; sub-projects roll up
  into their parent; `/project` summarizes status across the tree.
- Files: `Projects/`, `Templates/Project.md`, `Project.base`, `Projects.base`.
- Commands: `/project`.

**People**
- What: one note per person: company, team, manager, birthday, hire date,
  employee number, work email and phones, other emails, phones and
  addresses, usernames on other systems, the systems they support,
  goals by year, feedback, plus live lists of their tasks, meetings and
  reviews. Handles two people with the same name. Notes are created for you
  when you link a new name. A username ("jira: jsmith") also counts as a
  name for that person, so a stray `[[jsmith]]` warns instead of creating a
  duplicate note.
- Files: `People/`, `Templates/Person.md`, `Person.base`, `People.base`,
  `.opencode/plugins/auto-people.js`.
- Remove the auto-creation only: delete `auto-people.js`.
- `/people-check` lists people written in plain text without a link (by name
  or alias) and names that may need a note; you answer link / create / skip
  for each. `/link-check` lists every `[[link]]` that points at no note
  (a missing project, a typo) and offers fix / create / unlink. Both read
  through `.opencode/scripts/link-check.ps1`, which changes nothing; the
  commands change a note only after you answer. Remove: delete the two
  commands and the script.
- Personal details: see the Personal data note in [[SETUP]].

**Team management** (delegating and 1:1s)
- What: give a task an `assignee`; it appears on that person's note and on the
  Delegated list. `/1on1` builds an agenda from open items, recent
  commitments and feedback.
- Commands: `/1on1`. Needs: People.

**Meetings**
- What: dated meeting notes, filed by year and month, with Action items
  (become tasks), Decisions, and Commitments (what others agreed to, with no
  checkbox, searchable later).
- Files: `Meetings/`, `Templates/Meeting.md`, `Meetings.base`.
- Commands: `/actions`, `/commitments`.

**Recurring meetings**
- What: a series note (cadence, attendees, standing agenda) and `/prep`, which
  drafts the next agenda from open actions, due commitments and decisions to
  revisit, and creates the meeting note.
- Files: `Meetings/Series/`, `Templates/Series.md`. Commands: `/prep`.
- Needs: Meetings.

**Decisions**
- What: one-line decisions in meetings; a full record (context, options,
  rationale, superseded-by) for the important ones; a revisit date that
  surfaces on the Dashboard.
- Files: `Decisions/`, `Templates/Decision.md`, `Decisions.base`.
- Commands: `/decisions`, `/decision-record`.

**Reviews** (mid-year and year-end)
- What: `/review` drafts a review or self-assessment in your company's form,
  from the tasks, feedback, meetings and decisions you logged, citing a note
  for every statement. It never rates anyone.
- Files: `Reports/Reviews/`, `Templates/Review-format.md` (edit to your form),
  `Reviews.base`. Needs: People goals and feedback lines.

**Reports and look-back**
- What: what got done in any date range, by type and project.
- Files: `Reports/`. Commands: `/report`.

**Jira link (optional)**
- What: tasks carry a `jira` key or `none`; `/jira-check` finds work that
  belongs in Jira and drafts the issue for you to paste; `/jira-comment`
  drafts updates. Nothing is ever posted or created for you.
- Remove: delete `jira-check.md`, `jira-comment.md`, `jira-status.md`, `jira-pull.ps1` and `jira.json`, the "Jira" section of
  `AGENTS.md`, the `jira` user field in TaskNotes, and the "No Jira decision"
  embed in `Dashboard.md`.

**Jira status pull (optional, read-only)**
- What: `/jira-status <task, project or ABC-123>` reads the current state
  and latest comments of an issue, compares them with your task's status,
  due date and log, and suggests a task change or a comment for you to
  paste. It only sends GET requests to a Jira you listed in `jira.json`, and
  writes nothing to Jira.
- Files: `.opencode/jira.json`, `.opencode/scripts/jira-pull.ps1`,
  `.opencode/commands/jira-status.md`, and the `jira_url` field on project
  notes. Windows only. Off until you set it up.
- Per project: put the project's Jira address in its `jira_url` (a
  sub-project without one uses its parent's). Projects that live in different
  Jira instances just use different addresses; several projects in one
  instance can share one. `jira_url` only picks the instance by host name.
  The addresses the script may talk to are listed in `jira.json`, so a note
  can never send your token to a host you didn't list.
- Set up once (check your organization's policy on API tokens first):
  1. In `.opencode/jira.json`, describe each Jira instance you use (copy the
     block for more): `baseUrl` (for example `https://jira.example.com`, or
     `https://yourname.atlassian.net`), `flavor` (`server` for Jira Data
     Center / Server, `cloud` for Jira Cloud) and `tokenVar`, the name of the
     environment variable for that instance's token. It must start with
     `JIRA_` (for example `JIRA_TOKEN`, `JIRA_TOKEN_OTHER`).
  2. Make a token per instance. Data Center / Server (8.14 or later):
     profile → Personal Access Tokens → Create token. Older Server versions
     that only accept a password are not supported. Cloud: id.atlassian.com →
     Security → API tokens.
  3. Store each as a user environment variable in PowerShell:
     `setx JIRA_TOKEN "<token>"`. For cloud also `setx JIRA_EMAIL "<your
     Atlassian email>"` (or set `email` in `jira.json`). Quit opencode Desktop
     and sign out of Windows and back in.
  4. Set `jira_url` on the project (`https://jira.example.com/browse/ABC` or
     just the host address), then run `/jira-status ABC-123` with a real key;
     approve the script when opencode asks (it asks every time unless you add
     an allow rule).
- The token carries your own Jira permissions, so "read-only" is enforced by
  the script (GET only), not by the token. Don't put a token in a note, in
  `opencode.json`, or in git. Web access stays denied for the model itself.

**Research and experiments**
- What: a private notebook of questions and experiments with method,
  findings, log and a status (idea, active, concluded, dropped). Never linked
  from tasks or Jira. `/triage` flags research active 30+ days with no recent
  Log line, and a project page shows its linked research.
- Files: `Research/`, `Templates/Research.md`, `Research.base`.

**Reference notes**
- What: one note per thing you found and want to find again: a how-to,
  a query, request instructions. `/learn` files it from what you paste; each
  has a kind, the systems it's about and a date you last verified it (empty until you say you did). Who
  supports which system lives on the person (`supports`), not in a note.
  Never store passwords or tokens in one.
- Files: `Reference/`, `Templates/Reference.md`, `Reference.base`,
  `.opencode/commands/learn.md`.

**Updating the kit**
- What: `VERSION` says which release you have. To move to a newer one,
  download its zip from the GitHub releases page and run
  `.opencode\scripts\update-fieldbook.ps1 -From <the zip>`. It first only
  shows what it would do; add `-Apply` to do it. Files you haven't edited are
  replaced, files you edited are kept and the new copy is saved beside them
  as `.fieldbook-new`, and renamed note fields are migrated. Your notes and
  settings are never overwritten. A kit file you deleted stays deleted (the
  update lists it, it doesn't bring it back). Put your own rules in `AGENTS.local.md`,
  not in `AGENTS.md`.
- Files: `VERSION`, `CHANGELOG.md`, `fieldbook-manifest.json`,
  `fieldbook-applied.json`, `.opencode/scripts/update-fieldbook.ps1`,
  `.opencode/migrations/`. Windows only. Commit the vault first (the script
  checks); git is your undo.

**Quick capture and inbox**
- What: Ctrl+Alt+I from any app opens a one-line box; the text goes to
  `Inbox.md`. `/inbox` later sorts each line into a task, person note,
  commitment, project, research idea or Jira item.
- Files: `Inbox.md`, `.opencode/scripts/capture.ps1`. Windows only; needs the
  shortcut from SETUP section 8.

**Transcripts to meeting notes** (optional)
- What: `/transcript` turns a downloaded Teams transcript into a meeting note:
  attendees, notes, decisions, action items and commitments (ISO dates), asks
  before writing, always deletes the raw `.vtt`, and lets you keep the
  converted transcript (linked from the note, tracked by git) or delete it.
- Files: `Transcripts/`, `.opencode/commands/transcript.md`,
  `.opencode/scripts/vtt-to-md.ps1`. Needs: Meetings. The most sensitive data
  in the vault; check your company's policy.

**Change history and undo**
- What: every change is committed to git (yours through Obsidian Git,
  opencode's by a plugin); ask opencode what changed or to restore an older
  version.
- Files: `.gitignore`, `.git` pointer, `.opencode/plugins/auto-commit.js`.
- Needs: git (SETUP section 5).

## What you can adopt alone

- Only tasks: Core + Projects. Delete the rest of the folders and commands.
- Tasks + meetings: add Meetings, Recurring meetings, Decisions, Transcripts.
- Managers: add People, Team management, Reviews.
- Anything else stands alone; Research, Reference notes and Quick capture need only the Core.

To add your own kind of note: a folder, a template, a section in `AGENTS.md`
saying where it lives and which fields it has, and optionally a `.base` view
and a command file in `.opencode/commands/`. Task types: just add a row to
[[Types]].
