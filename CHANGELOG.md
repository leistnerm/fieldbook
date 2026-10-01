# Changelog

Newest first. The update script shows the entries newer than the version you
have. Format: `## x.y.z - date`.

## 0.3.0 - 2026-10-01
- New `/link-check` (links that point at no note) and `/people-check` (people
  named but not linked, and people with no note), both reading through the
  read-only script `.opencode/scripts/link-check.ps1`.
- SETUP: the Obsidian settings steps match current TaskNotes and Obsidian Git
  (inline-task folder, filename format, project settings, Git plugin
  appearing after the repo exists and a restart, push/pull toggles); the
  Jira step points at Features.md.

## 0.2.0 - 2026-09-30
- People get `workerType` (employee, contractor, consultant, vendor,
  government, competitor, other) and `contractEnd`; the People views show
  `workerType`. Migration 0002 lets `-Backfill` add both to existing notes.
- Update script: a kit file you deleted stays deleted; several pending
  migrations apply to one note without losing any; a field that is already a
  block list is reported for a hand edit instead of being rewritten.
- New Reference notes start with `verified` empty, and the "Not verified in a
  year" view lists empty and old dates.
- Jira status pull shows the newest comments on long issues, and a bad
  `baseUrl` in `jira.json` is named in the error.
- Docs: the assistant guide says to put your own rules in `AGENTS.local.md`;
  the Cheat Sheet covers the person fields and the update script.

## 0.1.0 - 2026-09-30
First numbered release: tasks, projects, people (contact lists, usernames,
supports), meetings and series, decisions, reviews, Reference notes and
`/learn`, research, quick capture, optional Jira link and status pull,
transcripts, and the update script. Migration 0001 moves the old
`personalEmail` / `personalPhone` fields into `otherEmails` / `otherPhones`.
