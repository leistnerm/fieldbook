<%*
// Templater: asks for the title, then files the note as Reference/<Title>.md
let title = ((await tp.system.prompt("Reference note title")) || "Untitled reference")
  .replace(/[\\/:*?"<>|]/g, "-").trim()
if (app.vault.getAbstractFileByPath(`Reference/${title}.md`)) title += ` ${tp.date.now("YYYY-MM-DD")}`
if (!app.vault.getAbstractFileByPath("Reference")) await app.vault.createFolder("Reference")
await tp.file.move(`Reference/${title}`)
-%>
---
tags: [reference]
kind: how-to
systems: []
verified:
source:
---
## Summary
One line: what this is and when to use it.

## Details

## Log
- <% tp.date.now("YYYY-MM-DD") %>: created
