---
description: File something you found as a Reference note (/learn <what you found>)
---
Input: $ARGUMENTS. Today is !`powershell -NoProfile -Command "Get-Date -Format yyyy-MM-dd"`.

The input is something the user found and wants to find again: pasted text,
steps, a query, request instructions, or "<person> supports <system>".
Follow AGENTS.md → Reference notes and People.

1. Who supports what: if it says a person supports a system, add it to that
   person's `supports` (match the person per the People rules; ask if more
   than one fits) and say so. That alone is not a Reference note; make one
   only if there is also something to write down.
2. Otherwise choose `kind` (how-to, query, instructions, other) and `systems`.
   Reuse existing spellings of system names; ask before adding a new one.
   Ask only for what you can't tell.
3. Look for an existing Reference note on the same thing. If there is one,
   offer to update it (add to Details, add a Log line) instead of duplicating.
4. Otherwise create `Reference/<Title>.md` from `Templates/Reference.md`, with
   a short specific title ("Reset a locked AD account"). Summary is one line
   from the user's words. Leave `verified` empty. Details hold what they gave you, with queries and
   commands in code blocks unchanged. Add nothing they didn't say.
5. A password, token or key in the input: leave it out of the note and tell
   the user it was left out.

Reply with the note's name (or the person updated), and nothing else.
