# Fieldbook

A plain-Markdown notebook for personal life, work, and school. Keep tasks,
projects, people, notes, and the reasons behind your decisions together.
Use it in Obsidian; add TaskNotes for task management and an optional AI assistant for help.
The files belong to you and remain readable without those tools.

## Optional AI, your choice

The default AI interface uses Python scripts and shared instructions, with no AI
plugins or MCP required. The setup CLI supports OpenCode, Claude Code, Codex,
Cursor, GitHub Copilot in VS Code, Gemini CLI and a generic profile. MCP is an
optional local transport. See [[Using AI assistants]] and [[MCP setup]].

## Start small

For a configured new vault, start with [START HERE](<START HERE.md>). The deployment
helper installs pinned plugins and settings. Manual setup is also available.

Open the resulting folder as an Obsidian vault. Start with [Inbox](<Inbox.md>), [Dashboard](<Dashboard.md>),
and one task. [SETUP](<SETUP.md>) walks through a minimal setup before optional AI,
tracker connections, or Git history. Existing vault? Read [UPGRADING](<UPGRADING.md>) first.

## One core, optional setups

| Setup | Adds | Daily page installed when enabled |
|---|---|---|
| Shared core | Capture, tasks, projects, notes, planning and reports | [Dashboard](<Dashboard.md>) |
| Personal | Goals, hobbies, appointments and optional household workflows | `Dashboards/Personal` |
| Work — individual contributor | Tasks, projects, learning, optional self-evaluation | `Dashboards/Work` |
| Work — people manager | Shared work plus optional reports/coaching/evaluations | `Dashboards/Work`, `Dashboards/People management` |
| School | Learning/projects plus optional courses, terms and assignments | `Dashboards/School` |

Combine personal + work + school in one vault, or use the same kit in separate
vaults. Area filters keep contexts distinct. Work has one selected role per vault;
a people manager can still use all contributor workflows.

Jira, Digital.ai Agility, GitHub Issues and Azure Boards are optional and **read only**
in every setup. Team scope uses person relationships self/report. Sync previews local
updates and can propose missing tasks. Proposed changes to the trackers are
paste-ready drafts for you to enter yourself.

## Find your way

- [SETUP](<SETUP.md>) — install and first success
- [Setups](<Setups.md>) — choose contexts and work role
- [Configuration CLI](<Configuration CLI.md>) — menu-driven setup, features, integration URLs, masked key entry and connection tests
- [Cheat Sheet](<Cheat Sheet.md>) — everyday commands and examples
- [Skills](<Skills.md>) — reusable workflows and additions worth considering
- [Types](<Types.md>) — task vocabulary for each role
- [Note types](<Note types.md>) — accomplishments, opportunities and core records
- [Notebook tools](<Notebook tools.md>) — searches, writes, permissions and limits
- [Calendar meetings](<Calendar meetings.md>) — meeting notes from local ICS exports or pasted events, with selected people only
- [Calendar connections](<Calendar connections.md>) — live Google/Outlook calendar accounts, recurring series and read-only OAuth setup
- [Canvas LMS](<Canvas LMS.md>) — optional read-only coursework, quizzes, discussion deadlines and student Planner
- [INTEGRATIONS](<INTEGRATIONS.md>) — four read-only tracker connections, person identities and sync behavior
- [UPGRADING](<UPGRADING.md>) — migrate old Tasks/Views paths and update safely
- [Obsidian additions](<Obsidian additions.md>) — useful core features and optional plugins
- [Features](<Features.md>) — modules and their requirements

`Tasks/`, `Views/`, `Projects/`, `People/`, and `Notes/` are peers at the root.
No content folder is named after a plugin. Examples live in fenced walkthroughs
under `Examples/`, so they do not appear as your actual work.

## Get started

Run `python fieldbook.py` (Windows: `py fieldbook.py`; macOS may use `python3`).
Python 3.10+ is required. The launcher creates the local Python environment and
installs core requirements, then opens Setup / Daily use / Integrations / Maintenance.
Choose Setup > Guided onboarding to select contexts, defaults and optional features.

Use Daily review or Weekly review to plan from your notes. Read-only integration
previews distinguish source changes, local overrides and conflicts before you
approve local edits. See [[Everyday workflow]] and [[Sync previews]].

Optional dependencies: `python fieldbook.py --install credentials` for OS key
storage and calendar sign-in; `--install intake` for PDF text extraction.
Image OCR separately needs Tesseract. `--check` inspects launcher readiness offline.

## License

Fieldbook is a general-purpose tool for anyone to use and customize. Keep private
notes and credentials separate from the public kit. Licensed under Apache-2.0;
see LICENSE and the third-party notices included with starter vaults.
