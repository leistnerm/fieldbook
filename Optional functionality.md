# Optional functionality

Start with the shared core and enable only useful setups, roles and connections.
[[Features]] describes current capabilities; this page separates implemented
additions from future choices. Work + people-manager does not install school or
personal workflows. Existing notes and customizations survive setup changes.

## Available now

| Need | Current entry point |
|---|---|
| Goals and agreements | `/goal`, `/renewal`, shared optional templates and separate notice/renewal/expiration views |
| Selected export | Daily use > Selected export, with file and privacy preview |
| Explicit manager cadence | Daily use > Manager 1:1 cadence; confirmed report/Series and explicitly marked meetings |
| Guided first use | Setup > Guided onboarding; optional self and first task, safe to rerun |
| Daily/weekly review | Shared CLI sequence and `/daily-review` / `/weekly-review` |
| Clear sync conflicts | Existing read-only notebook_preview compares mapped fields against reviewed source baselines |
| Reliable recovery | Guided upgrade with full backup, standalone backup/optional retention, verified restore; [[UPGRADING]] and [[Vault tools]] |
| Find local problems | Vault check: configuration, dependencies, links, incomplete templates and shared remote identities |
| Review upgrade changes | Compare preserved text candidates, keep custom settings, merge deliberately |
| Easier capture | Guided record creation, quick capture, Editing-view templates or Create new note from template |
| Selected email and document text | Local `.eml`/pasted text, PDF text layer and optional image OCR; [[Selected intake]] |
| Follow-ups | Shared live dashboard; local project gaps/commitments; optional manager meeting/evidence context |
| Understand coverage | Offline seven-provider summary and explicit saved read/test receipts; [[Integration coverage]] |
| Calendar meetings and series | Google/Microsoft read-only calendars; local Outlook/other exports through ICS; [[Calendar connections]] |
| School deadlines | Canvas coursework, quizzes, discussion checkpoints and bounded Planner context; [[Canvas LMS]] |
| Tracker records | Jira, Agility, GitHub Issues, Azure Boards; typed dates and bounded remote reads in every setup |
| Career and relationships | Neutral Person with optional contact/report layouts; sourced resume/CV, self-evaluation and optional report reviews |
| Domain workflows | Optional work focus guides for sales, security, education, procurement, executive and IT contexts |

These additions do not enable accounts, start background watchers, grant shell
access to AI, import all attendees, or write to remote services. Local creations
still have previews. [[Cheat Sheet]] lists the menus and commands.

## Useful next choices — not implemented

| Addition | Benefit and scope to decide first |
|---|---|
| Agenda and capacity review | Compare selected calendar windows with local planned work, include travel/focus buffers and keep overlapping invitations as suggestions rather than automatically merging them. |
| Guided term/semester rollover | Preview ongoing coursework, archival status and next-term courses while retaining old notes and never completing assignments automatically. |
| Mobile/browser capture polish | A simpler route into Inbox and selected-source provenance without broad browsing or mailbox permissions. |
| Richer selected-document extraction | Additional OCR languages, selected PDF page ranges and table handling after real-device testing. Current output always needs review. |
| Live selected email intake | A separate explicit account/scope decision for Gmail or Microsoft mail, bounded message selection and duplicate identity rules; current calendar authorization is insufficient. |
| Tracker portfolio context | Optional parent/child and iteration/project fields, preserving the distinction between an issue deadline and a portfolio target. GitHub Projects and pull requests are currently excluded. |

Prefer a new field or focused workflow over a new mandatory record type. Connect
existing records when evidence supports it: a significant completion may suggest
an accomplishment, a repeated discussion may suggest a decision or Reference, and
a meaningful commitment may suggest a task. Offer the connection without silently
creating records. No new integrations are implied by this roadmap.
