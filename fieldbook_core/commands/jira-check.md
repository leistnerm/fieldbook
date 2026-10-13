---
description: Find relevant tasks that may need Jira visibility and draft issues
---
Input: $ARGUMENTS. Require features.jira. Respect the requested area/project; any setup is supported.
Look for tasks in a Jira-linked project or tasks the user explicitly wants visible
there. Exclude jira: none and already-linked tasks. Do not assume every request,
personal chore, or school assignment belongs in Jira. Show candidates with reasons.
For chosen items use the tracker-draft skill to prepare paste-ready issues. Never
create them remotely. When the user supplies a real key and configured instance,
update the local link and append a log. Respect skip/none choices.
