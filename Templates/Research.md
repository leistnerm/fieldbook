<%*
// Templater: asks for the title, then files the note as Research/<Title>.md
let title = ((await tp.system.prompt("Research or experiment title")) || "Untitled research")
  .replace(/[\\/:*?"<>|]/g, "-").trim()
if (app.vault.getAbstractFileByPath(`Research/${title}.md`)) title += ` ${tp.date.now("YYYY-MM-DD")}`
if (!app.vault.getAbstractFileByPath("Research")) await app.vault.createFolder("Research")
await tp.file.move(`Research/${title}`)
-%>
---
tags: [research]
kind: research
status: idea
question:
projects: []
started: <% tp.date.now("YYYY-MM-DD") %>
concluded:
---
## Question

## Hypothesis
(experiments only; delete if not needed)

## Method

## Findings

## Conclusion

## Next

## Log
- <% tp.date.now("YYYY-MM-DD") %>: created
