---
description: Create a task from a plain-English description
---
Create a new task following AGENTS.md, from this description:

$ARGUMENTS

Infer title, type (from @Types.md), priority, projects, assignee, requester,
jira, and due date from the description. Today is !`powershell -NoProfile -Command "Get-Date -Format yyyy-MM-dd"`.
If type or anything else is a guess, show the frontmatter and ask before
writing. Otherwise write the file and reply with the path and a one-line summary.

If no Jira key was given and the task meets the Jira rules in AGENTS.md, say
which rule and offer: draft the Jira issue now, mark `jira: none`, or later.
