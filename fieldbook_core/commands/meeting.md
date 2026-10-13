---
description: Prepare a meeting note or recurring Series from supplied details, exports or enabled read-only calendars
---
Input: $ARGUMENTS

Read AGENTS.md and fieldbook.json. Load the `calendar-meeting` skill, or read
`fieldbook_core/skills/calendar-meeting/SKILL.md` if the skill tool is unavailable.
Use ordinary meeting details, pasted event details, a local Attachments/*.ics
export, or calendar_pull for an explicitly selected enabled Google/Microsoft
connection. This shared workflow works in every setup; live providers are optional.
For a recurring Series, retain its source identity and prepare only requested
occurrences. Read-only event previews and Series links do
not authorize note edits or contact creation; use notebook_write for approved
local changes. Never change an external calendar or sign in through an AI tool.
