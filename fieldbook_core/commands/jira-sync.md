---
description: Read Jira and preview Fieldbook updates
---
Input: $ARGUMENTS

Read AGENTS.md and fieldbook.json. Load the `tracker-sync` skill or read
`fieldbook_core/skills/tracker-sync/SKILL.md` directly if the skill tool is unavailable.
Provider is jira. Ask for a missing scope/instance; default to updating linked notes only.
Create missing tasks only when requested. All setups are supported.
