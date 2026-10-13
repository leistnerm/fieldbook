<%*
const input = await tp.system.prompt("Research title")
if (input === null) throw new Error("Cancelled")
let title = input.replace(/[\\/:*?"<>|]/g, "-").replace(/[. ]+$/, "").trim()
if (!title || /^(con|prn|aux|nul|com[1-9]|lpt[1-9])(?:\.|$)/i.test(title)) throw new Error("Choose a valid title")
const folder = `Research`
if (!app.vault.getAbstractFileByPath(folder)) await app.vault.createFolder(folder)
const stem = `${title}`
let target = `${folder}/${stem}`, n = 2
while (app.vault.getAbstractFileByPath(`${target}.md`)) target = `${folder}/${stem} (${n++})`
await tp.file.move(target)
-%>
---
templateName: "Research"
templateVersion: 1
tags: [research]
kind: research
status: idea
question:
projects: []
area:
started: <% tp.date.now("YYYY-MM-DD") %>
concluded:
---
## Question

## Sources

## Findings

## Conclusion

## Next

## Log
- <% tp.date.now("YYYY-MM-DD") %>: created
