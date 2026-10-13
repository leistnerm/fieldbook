<%*
const input = await tp.system.prompt("Meeting title")
if (input === null) throw new Error("Cancelled")
let title = input.replace(/[\\/:*?"<>|]/g, "-").replace(/[. ]+$/, "").trim()
if (!title || /^(con|prn|aux|nul|com[1-9]|lpt[1-9])(?:\.|$)/i.test(title)) throw new Error("Choose a valid title")
const folder = `Meetings/${tp.date.now("YYYY")}/${tp.date.now("YYYY-MM")}`
if (!app.vault.getAbstractFileByPath(folder)) await app.vault.createFolder(folder)
const stem = `${tp.date.now("YYYY-MM-DD")} ${title}`
let target = `${folder}/${stem}`, n = 2
while (app.vault.getAbstractFileByPath(`${target}.md`)) target = `${folder}/${stem} (${n++})`
await tp.file.move(target)
-%>
---
templateName: "Meeting"
templateVersion: 1
date: <% tp.date.now("YYYY-MM-DD") %>
series:
attendees: []
projects: []
area:
transcript:
tags: [meeting]
---
## Agenda

## Notes

## Decisions

## Action items

## Commitments
