# Setup

Installing fieldbook, a notebook for tracking work and everything else you
follow up on, from scratch on Windows. You end up with Obsidian
(notes, task boards, dashboards) plus the opencode Desktop app, an AI assistant that
works inside the vault and files, updates and drafts things for you through
slash commands. Everything is plain markdown files on your PC.

Time: about an hour, plus whatever access approval your AI provider needs.

What each part is for, and how to keep only some of it: [[Features]].
Daily reference: [[Cheat Sheet]].

## What you need

- Windows 10 or 11, on a desktop or laptop (the vault is not built for phones).
- **Git for Windows** (`winget install Git.Git`, or git-scm.com). Check with
  `git --version` in PowerShell.
- Access to an AI model for opencode: an API key for a provider, or your
  company's internal endpoint (section 7).

The few commands below are for PowerShell (not Command Prompt). Day-to-day use
is all in the Obsidian and opencode Desktop windows.

## Layout

```
AGENTS.md              rules opencode follows (read automatically) — also the
                       one place that says where every kind of note lives
AGENTS.local.md        your own rules; updates never touch it
VERSION, CHANGELOG.md  release number and what changed
fieldbook-manifest.json, fieldbook-applied.json
                       what the update script compares (leave them alone)
opencode.json          model provider config and permissions
Cheat Sheet.md         commands and how-tos for daily use
Features.md            what each part does and how to remove it
Using opencode.md      how to use the assistant, and write your own commands
Dashboard.md, Types.md home page; allowed task `type` values
TaskNotes/Views/       the .base views (+ TaskNotes' own *-default.base files
                       — keep them)
Templates/             the Templater templates (incl. Review-format, the
                       company review form)
.opencode/commands/    the slash commands (list: Cheat Sheet)
.opencode/plugins/     auto-people.js, auto-commit.js
.opencode/scripts/     capture.ps1 (Ctrl+Alt+I), vtt-to-md.ps1,
                       jira-pull.ps1 (optional), update-fieldbook.ps1
Inbox.md               quick captures waiting for /inbox
Transcripts/           Teams transcripts for /transcript (raw .vtt never in git;
                       converted notes you keep are)
.gitignore             what git leaves out
.git                   one-line pointer to the history outside OneDrive
```

Note folders (People, Meetings, Decisions, Projects, Research, Reference, TaskNotes/Tasks)
and how notes are found: see the "Where things live" table in `AGENTS.md`.

Rule of thumb: `TaskNotes/` holds what TaskNotes reads; everything you write
and read yourself is at the root.

## 0. Put the vault in place

1. Unzip the kit where you want the vault, for example
   `%USERPROFILE%\Documents\Fieldbook` (or a OneDrive folder, if you want the files
   synced; the git history goes elsewhere, section 5).
2. If that folder is in OneDrive: right-click it → **Always keep on this
   device** *first*, so opencode, git and the plugins never hit cloud-only
   placeholder files.

## 1. Install Obsidian

1. `winget install Obsidian.Obsidian`, or download from obsidian.md.
2. Start Obsidian → **Open folder as vault** → pick the vault folder from
   step 0. Choose **Trust author and enable plugins** when asked.
3. Open `Dashboard.md`. Most embedded lists will look empty or broken until the
   plugins in sections 2–4 are installed; that is expected.
## 2. Plugins

- Core plugins → turn on **Bases**. Leave core **Templates** off; Templater
  handles every template.
- Community plugins → install **TaskNotes**, **Git** (by Vinzent03;
  configured in section 5), and **Templater** (by SilentVoid).
- Not needed: Dataview, Tasks, Kanban. Optional later: Split Groups (only if
  the dashboard's Delegated view needs a task with two assignees listed under
  each person — person notes already handle that).

## 3. Core settings

- Templater → Template folder location: `Templates`; leave "Trigger
  Templater on new file creation" off. All templates use Templater.
- Hotkeys → search "Templater: Create new note from template" → set
  **Ctrl+Shift+M**. Also set "Templater: Open insert template
  modal" to **Alt+E** — that's how you fill a note you already
  created, such as a Person or Project note.
- Files & links → New link format: *Shortest path when possible* (the
  default). Links then hold only the note name, so meeting notes can move
  between folders without breaking links.
- Files & links → Automatically update internal links: on (default)

## 4. TaskNotes settings

**General**
- Task identification: by tag, tag = `task`
- Tasks folder: `TaskNotes/Tasks` (the default)
- Filename format: the task **title** (so a task is `<Title>.md`; opencode and
  the examples find tasks by title). Not a timestamp or zettel id.
- Don't use TaskNotes' Archive — use status `dropped` instead

**Task properties** — keep the default keys (`title`, `status`, `priority`,
`due`, `scheduled`, `projects`, `recurrence`, `complete_instances`,
`completedDate`, `dateCreated`, `dateModified`).
- "Use parent note for inline/instant conversion": **off** — it
  would put meeting notes into `projects`.
- Projects → autosuggest filter: only notes with tag `project`, so
  the project picker offers project notes, not every note in the vault.

**Statuses** (value → label; mark "Completed" where shown):
| value   | label   | completed |
|---------|---------|-----------|
| backlog | Backlog | no        |
| active  | Active  | no        |
| blocked | Blocked | no        |
| done    | Done    | **yes**   |
| dropped | Dropped | **yes**   |

Default status: `backlog`. Delete the defaults (`none`, `open`, `in-progress`).

**Priorities** — number prefix because Bases sorts alphabetically:
| value    | label  |
|----------|--------|
| 1-high   | High   |
| 2-normal | Normal |
| 3-low    | Low    |

Default: `2-normal`. Delete the defaults (`none`, `low`, `normal`, `high`).

**User fields**:
| display name | property key | type |
|--------------|--------------|------|
| Type         | `type`       | text |
| Assignee     | `assignee`   | list |
| Requester    | `requester`  | text |
| Jira         | `jira`       | text |

In the task form, type Requester as a link, `[[Dana Lee]]` (a text box holds
it fine); `/task` fills it in that form for you.

**Task creation** — body template: `Templates/Task body.md`.

**Features** — "Show convert button next to checkboxes": **on**.

## 5. Change history (git)

Every change gets a commit: Obsidian Git commits your edits every 10 minutes,
and opencode's plugin commits its own after each reply, so you can always see
who changed what. The history stays on this PC. (OneDrive, if you use it, keeps its own
versions of the current files.)

The git data goes **outside** OneDrive: OneDrive syncing git's many small
files mid-write can corrupt them. Only a one-line `.git` pointer file lives in
the vault. (If your vault isn't in OneDrive you can skip `--separate-git-dir`
and run plain `git init`.)

1. In PowerShell, from the vault folder (adjust the path):
   ```powershell
   cd "$env:USERPROFILE\Documents\Fieldbook"   # your vault folder
   git init --separate-git-dir "$env:USERPROFILE\vault-history\work.git"
   git config user.name  "<your name>"
   git config user.email "<work email>"
   git config core.autocrlf false
   git add -A
   git commit -m "Initial vault"
   ```
      `.gitignore` (in the zip) keeps out Obsidian's window layout and opencode's
   installed packages.
2. Obsidian → Community plugins → install **Git** (by Vinzent03), enable it.
   Its settings (labels vary a little by version):
   - Auto commit-and-sync interval: `10` minutes
   - Auto commit-and-sync after stopping file edits: on
   - Push on commit-and-sync: **off**; Pull on commit-and-sync: **off**. There
     is no remote, so it only commits.
   - Commit message on auto commit-and-sync: `vault: {{date}}`
   - Pull on startup: off
3. Nothing to do for opencode: `auto-commit.js` finds the repo by itself.
4. Never add a remote. A push would copy personal data off the PC.
5. Moving to a new PC: the history doesn't come with OneDrive. Copy
   `%USERPROFILE%\vault-history\` across, then fix the path inside the vault's
   `.git` file (one line: `gitdir: C:/Users/…/vault-history/work.git`).

## 6. Install opencode Desktop

This kit uses the **opencode Desktop** app, not the terminal version.

1. Go to opencode.ai/download and download **Windows (x64)** under the desktop
   app. Run the installer.
2. Start opencode Desktop and open the vault folder as the project (the same
   folder Obsidian has open). opencode reads `AGENTS.md`, `opencode.json` and
   `.opencode/` from the project folder, so it must be the vault root, not a
   sub-folder.
3. Type `/` in the message box: the kit's commands (`/task`, `/log`, and so on)
   should be listed. If they aren't, you opened the wrong folder.
4. If the app reports a config error, fix `opencode.json` before going on: a
   broken file can mean none of the rules apply.

Keep opencode Desktop open while you work; the plugins in section 8 only run
while it is.

## 7. Add a model provider

opencode needs a model to talk to. The kit's `opencode.json` is set up for one
internal, OpenAI-compatible endpoint (a base URL, a model id and an API key
read from an environment variable). Choose one:

**A. An internal or self-hosted OpenAI-compatible endpoint**

Ask whoever runs your organization's AI service for the base URL, a model id
and an API key (and how access is approved). Then:

1. In `opencode.json`, replace `REPLACE-LLM-HOST` in `baseURL` and
   `REPLACE-MODEL-ID` (in `model` and under `models`) with the real values.
2. Store the key as a user environment variable, in PowerShell:
   `setx LLM_API_KEY "<your key>"`. Then **quit opencode Desktop
   completely and sign out of Windows and back in**, because a running app
   (and anything it was started from) won't see a new variable.

**B. A hosted provider (Anthropic, OpenAI, and others)**

In opencode Desktop, open its settings (or type `/connect`), choose the
provider and paste your API key. Then pick a model in the model selector (or
`/models`). To make it the default, set `"model"` in
`opencode.json` to `<provider>/<model-id>` and delete the `provider` block you
don't use. Note that a hosted provider sends your notes (which can name people)
to that provider, so check your company's rules first.

**C. A local model** (Ollama, LM Studio, and similar): add another
OpenAI-compatible entry in `opencode.json`, pointing `baseURL` at
`http://localhost:<port>/v1`. Small local models follow the rules in
`AGENTS.md` less reliably; expect to double-check the results.

Test: in opencode Desktop, with the vault open, ask "how many notes are in People?" It
should answer from the folder without asking for permission.

## 8. What opencode may do, and its plugins

`opencode.json` sets what opencode may do:
- Blocked: web fetch and web search, anything outside the vault,
  git commands that change history (commit, reset, checkout, restore, revert,
  rebase, stash, push, remote, clean, rm), and deleting files.
- Allowed without asking: editing notes, reading git history (log, diff, show,
  status), the date command the commands use, and the `/transcript` script's
  `-Keep` and `-Remove` modes, which can move or delete one named file inside
  `Transcripts/` and nothing else.
- Asks you first: any other shell command, and edits to `opencode.json`,
  `AGENTS.md`, `.opencode/`, `.obsidian/`, `.gitignore`. This stops opencode
  from loosening its own rules.

To change a rule, edit the `permission` block yourself. The last matching line
wins.

Two plugins in `.opencode/plugins/` load automatically while opencode is open.
Both are plain code with no model calls; delete a file to turn it off.
- `auto-people.js`: any `[[Name]]` in a frontmatter people field (attendees,
  assignee, owner, stakeholders, deciders, manager, requester) without a note
  gets `People/<Name>.md` from the Person template, about a minute after edits
  settle. If the name could be someone you already have (`John Smith` when
  `John Smith (Acme)` exists, or matches an alias), it shows a warning instead
  of creating a note.
- `auto-commit.js`: after each opencode reply, commits the vault as
  `opencode: <files>`. Needs section 5.

Quick capture hotkey: Windows blocks scripts that came from a download, so
first unblock the kit's scripts. Then create a Start-menu shortcut with the
hotkey. In PowerShell (set your vault path):
```powershell
$vault = "$env:USERPROFILE\Documents\Fieldbook"
Get-ChildItem "$vault\.opencode\scripts" | Unblock-File
$lnk = (New-Object -ComObject WScript.Shell).CreateShortcut(
  "$env:APPDATA\Microsoft\Windows\Start Menu\Programs\Inbox capture.lnk")
$lnk.TargetPath = "powershell.exe"
$lnk.Arguments = "-NoProfile -WindowStyle Hidden -ExecutionPolicy Bypass -File `"$vault\.opencode\scripts\capture.ps1`""
$lnk.Hotkey = "CTRL+ALT+I"
$lnk.WindowStyle = 7
$lnk.Save()
```
Ctrl+Alt+I now works from any app. The first press after sign-in can take a
few seconds. If Ctrl+Alt+I clashes with something, change `Hotkey` and run it
again, or right-click the shortcut → Properties → Shortcut key.

## 9. Make it yours

1. In Obsidian, rename `People/Your Name.md` to your own name (right-click →
   Rename, so links update). It is your own person note (`relationship: self`);
   fill in what you like.
2. Edit `Templates/Review-format.md` (a generic form that works as it is) to
   match your organization's review form and values, or delete it and don't
   use `/review`.
3. In `AGENTS.md`, the "Jira" section describes what belongs in Jira. Edit it
   to your team's practice, or remove the section and the `jira` nudges if you
   don't use Jira (see [[Features]]).
4. Delete the example notes (everything named `Example …`) and the three
   `Website` sample projects once the checks in section 10 pass.

## 10. Check once after setup

First confirm the Desktop app itself: the kit's slash commands are listed when
you type `/`; asking it to edit a note works; and when it wants to run an
unlisted shell command it shows a permission prompt you can refuse. If the
plugins don't run in the Desktop app (check 10 and 12), that part of the kit
needs the terminal version of opencode instead.

Open the example notes (`People/Example Person.md`, the two example meetings,
`Meetings/Series/Example Platform sync.md`) and confirm:

1. Example Person's note shows the example task under **Assigned — open** and
   the example 1:1 under **Meetings**.
2. `People/Your Name.md` (or your renamed note) shows Example Person under **Direct reports**.
3. Dashboard **Now** sorts 1-high first.
4. People.base **Birthdays this month** / **Anniversaries this month** show
   Example Person (birthday and hire date are in October — check once
   October starts, or temporarily set a date in this month).
5. Every embed on `Dashboard.md` renders (no broken links).
6. The example series note lists the 2026-09-22 meeting under **Meetings**
   and the example record under **Decision records**, and
   `/prep Example Platform sync 2026-10-06` picks up the open action item,
   Raj's overdue commitment, and the decision due for revisit.
7. Dashboard **Decisions to revisit soon** shows the example record (its
   revisit date is 2026-10-06; it disappears from that list once you set a
   date more than 14 days out).
8. `Projects/Website relaunch` lists both sub-projects under **Sub-projects**,
   and **Open tasks** shows "Example - Blog URL mapping" even though that
   task links only to `Website - Blog migration`. If the sub-project list works but the
   roll-up doesn't, the `inTree` formula at the top of `Project.base` is the
   one thing to fix; `/project` rolls up regardless.
9. Open `Projects/Website - Blog migration`: if TaskNotes adds its own "project
   tasks" panel there as well, you can remove one of the two.
10. With opencode open, add `"[[Test Person]]"` to an example meeting's
    `attendees`. Within ~1–2 minutes `People/Test Person.md` should appear
    (and a toast in opencode). If it doesn't until you send opencode a
    message, the plugin isn't seeing Obsidian's edits (see Troubleshooting). Then delete
    the test note and the attendee.
11. Same names. In Obsidian, rename `People/Example Person` to
    `Example Person (Example Co)`, then set its `aliases` to `[Example Person]`.
    Confirm the example task's `assignee` and the 1:1's `attendees` now read
    `[[Example Person (Example Co)]]`, and its note still shows the task
    under **Assigned — open**. That shows Obsidian updates links in
    properties. Then add `"[[Example Person]]"` to the other example
    meeting's `attendees`: after about a minute opencode should show an
    "Ambiguous … did you mean Example Person (Example Co)?" warning and **no**
    new note. Remove that attendee.
12. History. After opencode edits something, run `git log --oneline -5` in the
    vault. The top commit should read `opencode: <file>`. Within about 10
    minutes of your own edit, a `vault: …` commit should appear. If Obsidian
    Git reports "not a git repository", the `.git` pointer file isn't being
    followed (see Troubleshooting).
13. Templates stay out of views: the People directory doesn't list "Person",
    Recent meetings doesn't list "Meeting", and Reviews.base is empty. Also
    check TaskNotes' project picker: if it offers the "Project" template,
    the autosuggest filter in section 4 isn't set.
14. Reviews: run `/review Example Person mid-year`, say yes to save, and
    confirm the file appears under **Reviews** on Example Person's note and
    in Reviews.base under 2026. Delete it afterwards.
15. Meeting folders: press Ctrl+Shift+M, pick *Meeting*, type "Test". A
    note `YYYY-MM-DD Test` should land in `Meetings/<year>/<year-month>/`
    with today's `date` and no Templater code left at the top. Delete it.
16. Permissions. In opencode, ask in turn:
    - "show the last 3 git commits": runs without asking.
    - "fetch https://example.com": refused.
    - "commit everything to git": refused.
    - "delete the example 1-1 note": refused.
    - "add a comment to opencode.json": asks you (say no).
    - "add a blank line to .opencode/commands/task.md": asks you (say no).
    If any of these goes through when it should be refused, the permission
    patterns don't match how opencode runs commands on your setup: tighten
    them in `opencode.json`.
17. Capture: with Outlook in front, press Ctrl+Alt+I, type "test capture",
    press Enter. `Inbox.md` should end with `- <today> <time> test capture`.
    If the box opens behind other windows or doesn't take your typing, see
    Troubleshooting. Then run `/inbox` and drop it.
18. Research: press Ctrl+Shift+M, pick *Research*, type "Test". A note
    `Test` should land in `Research/` with status `idea`. Set `status:
    active`: it should appear under "Research and experiments in progress"
    on the Dashboard (reopen the Dashboard if it doesn't update). Delete it.
    Reference works the same: pick *Reference*, type "Test"; the note lands in
    `Reference/`, and shows in `Reference.base`. Delete it.
19. Recurrence format (do this early — the example task depends on it). In
    TaskNotes, create a task "Test recurring" repeating weekly on Fridays
    through its own form. Open the new file and look at its `recurrence` line. Then open `Send weekly
    status update`: its recurrence should show as weekly on Fridays in the
    Recurring view, and ticking it should move `scheduled` a week on. If not,
    the kit's `recurrence` format doesn't match your TaskNotes version: copy
    what TaskNotes wrote into the example task and into the recurring-task
    section of `AGENTS.md`. Delete the test task.
20. Transcripts (needs any Teams `.vtt`, or make one: a `WEBVTT` line, then
    a cue like `00:00:01.000 --> 00:00:04.000` and `<v Test Person>We will
    send the quote by Friday.</v>`). Save it in `Transcripts/`, run
    `/transcript`, and approve the conversion script when opencode asks (keep and remove run without asking). Confirm: a
    `… transcript.md` appears there with speaker turns; a draft meeting note
    is shown before anything is written; a commitment or action has a full
    `YYYY-MM-DD` date; and after you choose keep, the note has a `transcript`
    link. The `.vtt` is gone; `git status` does not list the `.vtt` or
    `Transcripts/.work`, but lists the kept note. Delete the
    test meeting and files.

If one fails, rebuild that filter/sort from the view's Filter or Sort menu —
Obsidian then writes the exact syntax — or ask opencode. Then delete the
example notes.

If views look stale after opencode edits: run **TaskNotes: Refresh cache**.

## Troubleshooting

- **Views look stale after opencode edits**: command palette → *TaskNotes:
  Refresh cache*.
- **Plugin doesn't seem to notice Obsidian's edits** (auto-people): it acts
  after opencode sees the change or the session goes idle. Send opencode any
  message and it should catch up.
- **Obsidian Git says "not a git repository"**: check the vault's `.git` file
  holds one line, `gitdir: C:/Users/<you>/vault-history/work.git`, and that the
  folder exists.
- **PowerShell refuses to run a script**: run `Unblock-File` on it (section 8)
  and start it with `-ExecutionPolicy Bypass`, as the shortcut does.
- **opencode says a config error on start**: `opencode.json` is invalid JSON.
  Undo your last edit.

## Personal data

People notes hold personal details (family, birthdays, personal contacts).
Check your company's policy on keeping that on a work laptop. Anything opencode reads is sent to
the model provider you chose in section 7, so pick one your company allows.
