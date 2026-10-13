# Features

The shared core uses Inbox, Tasks, Projects, Notes, Views and Templates. Fieldbook makes active templates, commands, skills and dashboard navigation follow
the enabled setups and features. Configure through [[Setups]] instead of deleting
pieces of the kit. Shared workflows stay available; disabled optional resources
can be restored when enabled. Existing notes are preserved. Customized active
resources remain visible as explicit preservation exceptions; see [[UPGRADING]].
Disabled features do not run in the background.

| Module | Requirements | Entry points |
|---|---|---|
| Tasks and projects | Obsidian; TaskNotes/Bases for boards and views | /task, /log, /close, /project, /kickoff |
| Planning and inbox | AI for workflow requests; notebook works manually | /plan-week, /inbox, /triage |
| Notes and knowledge | Core | /learn, /synthesize |
| People and meetings | Core; Person default, shared Professional contact; Direct report layout belongs to people management | /meeting, /actions, /prep, /1on1 |
| Calendar meeting capture | Core + Python for local ICS; pasted details also work; no new people by default | /meeting; Calendar meetings |
| Google / Microsoft calendars | Any setup + selected provider feature + saved connection; OAuth uses OS keyring; read only | /meeting; Calendar connections; calendar_pull |
| Linked recurring Series | Core Series note; live discovery needs an authorized Google/Microsoft connection | Configuration menu 8; /meeting for selected occurrences |
| Personal | personal setup | /home; Dashboards/Personal |
| Learning and progress | Core, any area | /study, /report, /status-update |
| School courses and terms | school setup | /course, /term-close |
| Canvas LMS | school + canvas + configured connection + Node.js 22+; read only | /canvas-sync |
| Guided configuration | Python 3.10+; optional keyring for masked API keys, required for calendar OAuth; setup, scopes, record links and read-only tests | python tools/configure.py |
| Work evaluation | work + reviews, either work role | /evidence, /review me |
| People management | work + people-manager; formal evaluations also require reviews | /coach, /review report; Dashboards/People management |
| Jira / Agility / GitHub Issues / Azure Boards | Any setup + provider feature + connection; Python entry point + Node.js 22+ for tracker reads | /sync, /jira-sync, /agility-sync, /github-sync, /azure-sync |
| Remote change drafts | Local notes; no tracker credential needed | /tracker-draft |
| Decisions | Optional notes | /decisions, /decision-record |
| Research and reference | Optional notes in any area | /synthesize, /learn |
| Transcripts | Python; supplied WebVTT transcript (including Teams exports) | /transcript |
| Backups and history | Verified CLI backups; optional manually managed Git | Maintenance > Backup |
| Quick capture | Python; optional tkinter | capture.py window or manage-vault.py capture |

Tasks own status/deadlines; project and meeting notes link to them. Courses reuse
projects. General notes can link to any area. References preserve supplied source
material; research notes distinguish questions, sources, findings and conclusions.
Experiment and Purchased item are optional detailed templates; Reference and Item
remain neutral. /1on1 supports any relationship; /coach selects manager coaching.
See [[Note types]] for the full shared/optional template guide.
Skills package optional procedures; see [[Skills]].

A feature switch is workflow configuration, not a separate security sandbox.
The remote adapters themselves expose only reads. The host controls approvals; shared instructions are not a sandbox.
The portable scripts enforce path and hash restrictions. Preserve user configuration
and templates through updates; see [[UPGRADING]].

## Discovery, evidence and controlled AI access

- Contextual /help and a cross-setup /people directory/context workflow.
- Accomplishment and opportunity notes; sourced resume/CV/bio drafting.
- Shared decision briefs and handovers; optional work domain/subrole guidance.
- Python notebook read/write/search/query/link tools with relative paths, explicit
  AI assistant permissions, stale-write checks and bounded local regex/fuzzy/similar search.
- Suggested links and follow-up records after meaningful work, without unsolicited writes.
- A deployable starter vault; see START HERE.md. A separate work vault is recommended
  when employer data/device/provider rules differ from personal/college use.

## Dashboards and optional additions

[[Dashboard]] covers every area, including unassigned notes and records from
setups later disabled. Active context pages live under `Dashboards/`; `Setups/`
contains instructional guides. Personal, Work and School dashboards have matching
core sections. Navigation follows enabled contexts, work role and features.

Items and Lists have neutral browsing views. Saved view filters use actual note
metadata, so changing setup does not change existing records or their area.
Shared and retained helper views keep existing note embeds useful. See
[[Setups/Dashboards]] for the catalog and recurring/date behavior.

[[Calendar meetings]] explains local ICS/pasted events and selected live occurrences.
[[Calendar connections]] covers Google/Microsoft setup, sign-in and linked Series.
[[Canvas LMS]] provides optional read-only coursework, quizzes, discussion checkpoint
deadlines, Planner and calendar context, with verified identity matching and explicit date types.
[[Optional functionality]] separates implemented tools from future choices.
Selected local email/PDF/image intake is available; live mailbox readers
and background watchers remain unimplemented.
See [[INTEGRATIONS]] for the implemented remote readers.

## Local vault maintenance and selected intake

All setups can use [[Vault tools]]: standalone backup/optional retention, vault
checks, upgrade comparison, complete record creation from enabled templates,
explicitly saved integration activity and follow-up review. [[Selected intake]]
reads selected local email/text/PDF/images into a previewed Reference; PDF and
image OCR dependencies are optional. These human CLI workflows do not loosen
AI assistant permissions. [[Dashboards/Follow-ups]] is shared; only its CLI manager
context depends on work + people-manager, with review evidence separately gated.

## Optional shared capture and review

Fieldbook adds shared goals and agreement renewal/notice/expiration records, a human
calendar occurrence picker, selected evidence export, and explicit manager 1:1
cadence. Use the grouped Python CLI; no new feature switches are enabled by an
upgrade. See [[Vault tools]], [[Note types]] and [[Configuration CLI]].

## 1.0 usability workflows

Guided onboarding connects setup/defaults, an optional self record and first task
to the Dashboard. Shared daily/weekly reviews provide a consistent local review
sequence, with role-specific manager context kept optional. Deterministic sync
previews expose field-level conflicts and preserve local overrides; no additional
AI assistant permission or remote write capability is introduced.
