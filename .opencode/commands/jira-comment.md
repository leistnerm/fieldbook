---
description: Draft a Jira comment from a task's log (/jira-comment <KEY or task>)
---
Input: $ARGUMENTS

Find the task whose `jira` field matches the key (or whose title matches).
Read its Notes and Log. Draft a Jira comment covering log entries since the
last "posted to Jira" line (or all, if none): outcome/progress first, then
next steps, then blockers or asks. Follow AGENTS.md style. Output only the
comment text in a code block for me to paste.

Then ask whether I posted it. If yes, append `- <today>: posted to Jira` to the
log.
