---
description: Turn a Teams transcript into meeting notes (/transcript [file] [meeting or series])
---
Input: $ARGUMENTS. Today is !`powershell -NoProfile -Command "Get-Date -Format yyyy-MM-dd"`.

Transcripts are Teams `.vtt` files saved in `Transcripts/` (Teams → the
meeting's Recap → Transcript → Download → .vtt). The raw `.vtt` and the
unreviewed conversion are kept out of git; only a converted note you choose
to keep is tracked. Never quote transcript text at length, and never copy it into a meeting
note.

1. **Find the file.** The one named in the input (fuzzy), else the newest
   `.vtt` in `Transcripts/`. If it's a `.docx`, stop and ask for the `.vtt`.
   If `Transcripts/` has none, say how to get one.
2. **Date and title.** Date from the file name (Teams names look like
   `Title-20260929_…-Meeting Transcript.vtt`), else the input, else ask. Title
   = the meeting or series named in the input, else from the file name. If it
   matches a series note in `Meetings/Series/`, use that series.
3. **Convert.** Run
   `powershell -NoProfile -ExecutionPolicy Bypass -File .opencode/scripts/vtt-to-md.ps1 -Path "<file>" -Date <YYYY-MM-DD> -Title "<title>"`.
   It writes `Transcripts/.work/<date> <title> transcript.md` (speaker turns,
   git-ignored until kept) and prints the path. If it fails, show the error and stop.
4. **Read the converted note**, in parts if it is long, keeping running notes
   as you go.
5. **Find the meeting note** for that date and title/series. If there is
   none, offer to create `Meetings/<YYYY>/<YYYY-MM>/<date> <title>.md` (see
   AGENTS.md → Meetings; Windows-safe title), with `series` if it has one.
   If one exists, never overwrite anything in it: add to its sections.
6. **Draft**, following AGENTS.md → Meetings:
   - `attendees`: the people who spoke, as `"[[Name]]"` links. Match names to
     person notes per the People rules (same names, aliases). A Teams name
     that matches no note or several: list it under "Unclear".
   - **Notes**: 5–15 short bullets of what was discussed, no transcript
     quotes.
   - **Decisions**: one line each; only what was actually decided.
   - **Action items**: `- [ ] Person to X by <date>` for work the user or
     their team owns or that the user wants to track.
   - **Commitments**: `- [[Person]] (Department): what — by YYYY-MM-DD` for
     what others agreed to. ISO dates only: turn "by Friday" into a date
     using the meeting date; if none was stated, leave `by` off.
   - **Unclear**: anything you couldn't attribute to a person, or where an
     owner or date wasn't stated. Never guess an owner or a date.
7. **Show the draft and wait for my yes** (and edits). Then write it. Don't
   turn action items into tasks; I run `/actions` for that.
8. **Keep or delete.** The `.vtt` is deleted either way. Ask: keep the
   converted transcript, or delete it?
   - **Keep**: run
     `powershell -NoProfile -ExecutionPolicy Bypass -File .opencode/scripts/vtt-to-md.ps1 -Keep "<date> <title> transcript.md"`
     to move it into `Transcripts/`, then set
     `transcript: "[[<date> <title> transcript]]"` in the meeting note's
     properties (add the property if the note lacks it). Tell me it is now
     tracked by git, so deleting it later leaves it in history.
   - **Delete**: no link.
   Then in both cases remove the raw file, and for Delete the conversion
   too, with
   `powershell -NoProfile -ExecutionPolicy Bypass -File .opencode/scripts/vtt-to-md.ps1 -Remove "<file name>"`
   (one file per run).
   Only `-Keep` and `-Remove` may move or delete anything; never delete any
   other way. If a command is refused, tell me which file to delete in Obsidian.

Then list the Commitments due within 14 days as a reminder, and say the
meeting's Action items are ready for `/actions`.
