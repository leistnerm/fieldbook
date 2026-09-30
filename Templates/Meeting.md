<%*
// Templater: asks for the title, then files the note as
// Meetings/YYYY/YYYY-MM/YYYY-MM-DD <Title>.md
const title = (await tp.system.prompt("Meeting title")) || "Meeting"
const folder = `Meetings/${tp.date.now("YYYY")}/${tp.date.now("YYYY-MM")}`
if (!app.vault.getAbstractFileByPath(folder)) await app.vault.createFolder(folder)
await tp.file.move(`${folder}/${tp.date.now("YYYY-MM-DD")} ${title}`)
-%>
---
date: <% tp.date.now("YYYY-MM-DD") %>
series:
attendees: []
projects: []
transcript:
tags: [meeting]
---
## Agenda

## Notes

## Decisions

## Action items

## Commitments
