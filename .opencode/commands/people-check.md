---
description: Find people named in notes but not linked, and people with no note (/people-check [days | all])
---
Scope: $ARGUMENTS (a number of days; `all` for every note; empty = 14 days). Today is !`powershell -NoProfile -Command "Get-Date -Format yyyy-MM-dd"`.

1. **Mentions of people who have a note.** Run
   `powershell -NoProfile -ExecutionPolicy Bypass -File .opencode/scripts/link-check.ps1 -Mentions`
   (add `-Since <days>` for a number, `-All` for `all`). It lists each place a
   person's name or alias is written without a link. If it fails, show the
   error and stop.
2. **People who may need a note.** Read the notes changed in the same scope
   (`all` = the 30 most recently changed) for names that look like people
   and match no person note, alias or username. This is judgement: list them
   as a table (name | where seen | why you think it's a person), and leave
   out product names, places and anything unsure.
3. Show both lists with counts, then go one at a time. For a mention: **link**
   (replace the first mention in that note with `[[Name]]`; if the script
   says AMBIGUOUS, ask which person) / **skip** / **never** (add nothing; just
   stop suggesting it this session). For a possible new person: **create**
   (a note from `Templates/Person.md` in `People/`; ask me for the relationship
   and company) / **skip**.
4. Change nothing until I answer for that item. Never link a name on a guess,
   and never create a person from a name that appears only in a quoted email
   or a pasted transcript line without asking first.
5. End with a one-line tally: linked, created, skipped.
