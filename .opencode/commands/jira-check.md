---
description: Find tasks that should be in Jira and draft the issues (/jira-check [project/person/filter])
---
Filter (optional): $ARGUMENTS. Today is !`powershell -NoProfile -Command "Get-Date -Format yyyy-MM-dd"`.

Apply the Jira rules in AGENTS.md to every task with an empty `jira` field
(narrowed to the filter if given):

1. List candidates, most important first: title | project | assignee | why
   (which rule(s) it meets). Then, separately, "Done recently, not in Jira"
   (last 14 days). Then a count of tasks you skipped as not-Jira.
2. For each candidate, ask me: **draft / none / skip**. Go one at a time.
   - draft → show the Jira draft (per AGENTS.md) in a code block, ready to
     paste. Then ask for the key; when I give it, set `jira` and log it.
     If I say "later", leave `jira` empty and move on.
   - none → set `jira: none` (never suggest it again).
   - skip → leave it for next time.
3. End with a one-line tally: drafted, linked, marked none, skipped.

Also flag any project (tag `project`, status active) with no `jira` epic that
has 3+ tasks meeting the rules — it probably needs an epic.
