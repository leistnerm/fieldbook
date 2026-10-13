---
description: Read one Jira issue and compare with a local item
---
Input: $ARGUMENTS. Use the tracker-sync skill with provider jira and scope linked.
Resolve the configured instance and issue key, then use --ids with that key.
Show differences. Do not create missing tasks or edit files without approval.
For suggested remote changes use tracker-draft; never write to Jira.
