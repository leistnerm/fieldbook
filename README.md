# fieldbook

A plain-markdown notebook for keeping track of work (or anything else you
follow up on), built on [Obsidian](https://obsidian.md) and the
[opencode](https://opencode.ai) AI assistant. Tasks, projects, people,
meetings, decisions, commitments, reviews and research notes are all ordinary
`.md` files with properties. Nothing is locked in, and git records every
change.

## What you get

- **Tasks and projects**: boards, overdue and blocked lists, sub-projects,
  recurring tasks, date-range look-backs (TaskNotes + Bases).
- **People and team management**: one note per person, delegated work, 1:1
  agendas, goals and feedback.
- **Meetings**: notes filed by date, recurring series with `/prep`, action
  items that become tasks, and commitments others made, kept searchable.
- **Decisions**: one-liners or full records, with revisit dates.
- **Reviews**: `/review` drafts a mid-year or year-end review from what you
  logged, citing a note for every statement. It never rates anyone.
- **Transcripts**: `/transcript` turns a Teams transcript into meeting notes.
- **Quick capture**, an optional Jira link (never posts anything) and research
  notes.

Every part is optional; see `Features.md` for what each does and how to remove
it.

## Get started

1. Read `SETUP.md`. It walks through a from-scratch install on Windows:
   Obsidian, its plugins, git, opencode Desktop and a model provider.
2. Keep `Cheat Sheet.md` open for daily use, and read `Using opencode.md` to
   get more from the assistant and to write your own commands.

The rules opencode follows are in `AGENTS.md`; the slash commands are in
`.opencode/commands/`.

## Status

Early and lightly tested. Windows is the primary
target. The Bases views, the PowerShell scripts, the permission patterns and
the way opencode Desktop loads commands and plugins have not all been checked
on a fresh install, so expect to tweak. Issues and pull requests are welcome.

## Your data stays yours

This repository holds the kit only: no personal, company or meeting data.
Keep your own notes in a separate, private vault, and never commit a live
vault to a public repository. The review form (`Templates/Review-format.md`)
is a generic default; put your organization's real form and values only in the
vault your organization owns.

## License

Apache License 2.0. See `LICENSE` and `NOTICE`.
