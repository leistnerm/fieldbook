# Setup

The quicker path is [[START HERE]]: deploy a configured starter vault.
This page is the manual fallback and reference.

Start with a working notebook, then add what you need. Scripts use Python on
Windows, macOS and Linux; see VALIDATION.md for installation checks. No tracker account, Git repository, or AI subscription is needed
for the core. Read [[UPGRADING]] instead if you already have a vault.

## 1. Open the notebook

1. Unzip the kit into your own folder and open it as an Obsidian vault.
2. Enable the core Bases plugin. Install community plugins TaskNotes and Templater.
3. Set Templater's folder to `Templates`; leave its automatic new-file trigger off.
   Leave Obsidian's separate core Templates plugin off to avoid confusion.
4. Enable automatic internal-link updates. Use shortest-path links.
5. Open [[Dashboard]]. Empty lists are normal: sample walkthroughs are not live notes.

If using OneDrive, mark the vault **Always keep on this device** first. The scoped
AI tools reject Windows reparse points, including some cloud-managed files; test a
read/write first. Use a regular local folder if your sync filesystem is rejected.

## 2. Configure TaskNotes

TaskNotes is the task editor; your files live in root-level `Tasks/` and `Views/`.
Names of settings may vary by installed version.

| Setting | Value |
|---|---|
| Task identification | Tag `task` |
| Tasks folder | `Tasks` |
| Folder for inline-created tasks | `Tasks` |
| Store title in filename | Off |
| Filename format | Task title (non-updating) |
| Projects: use parent note for inline/instant conversion | Off |
| Project autosuggest required tag | `project` |
| Task body template | `Templates/Task body.md` |
| Convert button beside checkboxes | On |

Replace default statuses with backlog, active, blocked, done, dropped. Mark done
and dropped as completed. Default: backlog. Priorities: 1-high, 2-normal, 3-low;
default 2-normal. Keep standard property keys: title, status, priority, due,
scheduled, projects, recurrence, complete_instances, completedDate, dateCreated,
dateModified. Add user fields: Type (`type`, text), Area (`area`, text), Assignee
(`assignee`, list), Requester (`requester`, text). Optional tracker fields are in
[[INTEGRATIONS]]. Keep TaskNotes-generated `*-default.base` files wherever your
installed plugin manages them; the kit's maintained views are in `Views/`.

Configure recurring tasks through TaskNotes' own form. This release deliberately
does not prescribe an unverified recurrence string.

## 3. First success

Create a task "Try Fieldbook" in TaskNotes, set scheduled to today and area to
personal, and confirm it appears under Dashboard → Now. Set it to blocked: it
moves out of Now and into Blocked. Complete it: it appears in recently completed.
Add a line to Inbox. That is enough to begin using the notebook without AI.

For manually created project/person/course notes, create and name the file in its
record folder (Projects/ or People/), switch it to **Editing view**, then open
the command palette and run **Templater: Open insert template modal**. Choose the
matching template and check that both its properties and body headings appear.
For people, start with Person; choose Person - Professional contact for business/academic context or Person - Direct report for
someone you manage. All go in People/ with tag person. Automatic stubs always use
Person, even in a manager vault. See [[Note types]] for contact fields and examples.

Alternatively, run **Templater: Create new note from template** from the command
palette. This also works while the current note is in Reading view. Choose a
template and complete any prompts, then check the new note's name and folder.
Meeting/Reference/Research templates prompt for a title and file themselves;
other templates may need you to name and move the new note in Obsidian. For a task
template whose title comes from the filename, prefer a named Tasks/ file in Editing
view so its title is correct when inserted.

**Do not insert into an existing note in Reading view.** In live testing with
Obsidian 1.14.4 and Templater 2.25.1, insertion there saved the properties but omitted
the body. Editing-view insertion and the create-new command retained the complete
note. If a new note contains properties only, switch to Editing view and insert
again; check for duplicate sections. Preserve existing text in populated notes and
add only the missing sections instead of applying a whole template over them.

Templater hotkeys are optional:
Create new note from template → Ctrl+Shift+M; insert template modal → Alt+E.
For tasks, prefer the TaskNotes form; Task / Task - Assignment / Task - Study session templates are
schema references or can be inserted into an already-named file in Tasks/ in Editing view.

## 4. Choose contexts and work role

Follow [[Setups]]. Personal, work and school can coexist. Work has individual
contributor and people-manager roles; both include self-evaluation preparation.
Setups only select workflows/defaults. They never delete or duplicate your notes.
Your choices live in fieldbook.json, which updates preserve. Run configure (preview
without --apply, apply with it) to synchronize optional templates, commands, skills
and daily dashboards. Editing JSON alone is not sufficient to refresh active files.
Start daily work from Dashboard and its enabled Dashboards/ links; Setups/ is the
instruction folder. See Setups.md for preservation exceptions and role choices.

## 5. Optional AI

Run `python fieldbook.py`, choose **Setup > AI assistants and optional MCP**, and
select one or more harnesses. The default uses shared instructions and Python
scripts with no AI plugins or MCP. Open the vault root in your chosen assistant.
See [[Using AI assistants]] for supported harnesses and permission checks.

## 6. Optional history

Use Maintenance > Backup for verified local snapshots. Git is optional and can be
managed separately in a vault-owned repository. No AI background plugins are
installed. Person creation remains an explicit workflow.

## 7. Optional integrations and quick capture

Use `python tools/configure.py` for the numbered setup menu, feature switches,
connection settings and optional read-only connection tests. Jira, Agility, GitHub
Issues and Azure Boards are available in any setup; follow [[INTEGRATIONS]].
Canvas LMS is optional for school; see [[Canvas LMS]]. Google/Microsoft calendar
accounts work in every setup; see [[Calendar connections]]. The configuration CLI uses
Python. Tracker/Canvas sync additionally needs Node.js 22+ and the standalone
reader dependency; see [[Using AI assistants]]. Connection tests use Python.

Quick capture works from a terminal:

```text
python tools/manage-vault.py capture --text "Remember the library books"
```

This appends a dated Inbox entry immediately because it is an explicit capture.
For a small desktop window, run `python fieldbook_core/scripts/capture.py` with a Python
build that includes tkinter. Ctrl+Enter saves; Escape cancels. On Windows you can
create a shortcut to pythonw.exe with the absolute capture.py path as its argument,
then assign Ctrl+Alt+I in the shortcut's Properties. The GUI is optional; no
PowerShell or WinForms component remains.

## 8. Check and recover

```text
python tools/manage-vault.py health
```

This checks JSON, Python syntax, layout, settings and optional prerequisites.
It reports failures without changing files or contacting a tracker. For deeper
checks/tests, see tools/TESTING.md. See VALIDATION.md for checks to run on your installation.

If views lag, run TaskNotes: Refresh cache. If a command or skill is absent,
reopen the vault root in AI assistant and check its logs/config. If a template fails,
check the filename, existing destination and Editing view; for a properties-only
note, follow the template insertion guidance above. If a sync fails, no local update is
implied; inspect the error and narrow/retry the read. Undo file changes using your
backup or a reviewed Git diff. Do not rely on chat history as your only backup.

Useful optional additions and what the starter enables: [[Obsidian additions]].

## 9. Optional local maintenance and intake

CLI **15 Vault tools** provides independent verified backups, checks, upgrade
comparison, guided record creation, saved integration activity and follow-up review.
[[Dashboards/Follow-ups]] is shared across all setups; manager details are optional.
[[Selected intake]] adds selected email/text/PDF/image capture into a new Reference.
Everything previews before creation; remote integrations remain read only.

For Python setup, follow [[Notebook tools]]. The ZIP does not contain a `.venv`
file: `python3 -m venv fieldbook_core/.venv` (Windows: `py -m venv fieldbook_core/.venv`)
creates the environment folder. Then install requirements with its Python.

## One-command Python preparation

Start with `python fieldbook.py` (`py fieldbook.py` on Windows). It creates the private `fieldbook_core/.venv` directory and installs core requirements. No activation step is needed. See [[Configuration CLI]] for optional dependencies and grouped menus.

## Guided first use in 1.0

The recommended path is `python fieldbook.py` > Setup > Guided onboarding. It
previews settings, preserves existing content, optionally selects a self Person and
captures a first task. You can skip optional steps and rerun it. See [[Everyday workflow]].
