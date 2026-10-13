---
name: tracker-draft
description: Draft Jira, Agility, GitHub Issues or Azure Boards additions, comments, or changes for the user to enter manually; never execute them.
---

Use the requested provider and linked note. No integration credential is needed
for a local draft; do not make API calls unless separately asked to read context.
Identify whether the user needs a new item, description update, comment, assignee
change, or status transition. For a new item provide summary, suggested item type,
project/parent when known, description, acceptance criteria, owner and due date.
For an existing item provide provider/instance/ID, current value if known, proposed
value, and the reason/evidence. Clearly mark unknown current state and suggested
mappings. Keep operational details in the provider's vocabulary without inventing
custom fields or workflow transitions. Quote no secrets or private person notes.

Output a paste-ready text block plus a concise checklist of fields to change.
Never POST/PUT/PATCH/DELETE a tracker asset, submit UI forms, or send a comment.
A draft is not a completed update: do not log "posted" or link a new ticket until
the user confirms posting and supplies its real ID. If they confirm, update only
the requested local link/log. This skill grants no external write authorization.
