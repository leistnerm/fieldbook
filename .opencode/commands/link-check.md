---
description: Find [[links]] that point at no note, and fix them (/link-check)
---
Today is !`powershell -NoProfile -Command "Get-Date -Format yyyy-MM-dd"`.

1. Run
   `powershell -NoProfile -ExecutionPolicy Bypass -File .opencode/scripts/link-check.ps1`.
   It lists each `[[link]]` that matches no note, with the notes it appears
   in, whether it is in the body or a frontmatter field, and a "maybe" when
   it looks like a typo of a note or is a note's alias. People fields
   (attendees, assignee, owner and so on) are left out: the auto-people
   plugin creates those notes. If it fails, show the error and stop.
2. If nothing is listed, say so and stop. Otherwise show the count, then go
   one target at a time, most-used first. For each, say what it most likely
   is (project, person, reference, meeting, typo), using the field it was in
   and the notes around it, and offer:
   - **fix** — a "maybe" is right: change the link in each source note to the
     existing note (`[[Note|alias]]` for an alias).
   - **create** — make the note from the matching template in `Templates/`
     (project → `Project.md`, person → `Person.md`, reference →
     `Reference.md`), in its usual folder, and ask me for anything the
     template needs that you can't infer.
   - **unlink** — turn the link into plain text in the source notes.
   - **skip** — leave it.
3. Change nothing until I answer for that target. Never create a note, or
   edit a source note, on a guess.
4. End with a one-line tally: fixed, created, unlinked, skipped.
