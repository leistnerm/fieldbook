# Work specializations

Keep two independent choices: **responsibility** (individual contributor or people
manager) and **domain** (what you work on). You can have several domain interests
and a more specific subrole. They add context and suggestions, never permissions.
All use the same tasks/projects/people/meetings/decisions/evidence core.

| Domain (`workFocus`) | Possible subroles | Useful records and workflows |
|---|---|---|
| sales | Account executive, account manager, sales engineer, customer success | Account/project context, discovery meetings, commitments, proposal tasks; /people, /prep, /brief, /handover |
| cybersecurity | SOC analyst, incident responder, security engineer, GRC, security architect | Incident projects, evidence references, remediation tasks, risk/decision notes; /brief, /handover, /accomplishment |
| education | School teacher, lecturer, professor, advisor, researcher | Teaching projects, lesson notes, assessment tasks, source-linked research; /study, /brief, /handover |
| procurement | Buyer, sourcing specialist, category manager, vendor manager | Sourcing projects, vendor people, comparison research, approvals recorded as decisions; /brief, /people, /commitments |
| executive | Founder, business-unit leader, functional executive, chief of staff | Strategic projects, decision briefs, delegated commitments, outcome evidence; /brief, /project, /review, /handover |
| information-technology | Service desk, sysadmin, network engineer, cloud/platform engineer, IT service manager | Service projects, incident/change tasks, runbook references, handovers; /triage, /brief, /handover, /accomplishment |
| project-program | Project/program manager, delivery lead, PMO | Milestones, dependencies, decisions, stakeholder commitments; /project, /brief, /commitments |
| research | Research assistant, scientist, analyst | Questions, evidence, reproducible method references, findings; /synthesize, /brief, /resume |
| operations | Operations coordinator, service owner, facilities lead | Procedures, maintenance/routine tasks, exceptions and coverage plans; /plan-week, /handover |
| creative | Designer, writer, content producer | Briefs, project drafts, feedback notes, portfolio evidence; /kickoff, /brief, /accomplishment, /resume |

For example, a security engineer can be an individual contributor; a SOC lead may
be a people manager with cybersecurity + operations focus. A professor can use
work for teaching/research and school for their own study. Institution/course names
and area make the distinction explicit; do not infer that every course is coursework.
A sales opportunity may be an ordinary project; the Opportunity note is optional
when the opening/process fields fit. Neither replaces an official CRM.

Configure once in a terminal (preview by omitting --apply):

```text
python tools/manage-vault.py configure --setups work --work-role individual-contributor --work-focus cybersecurity,information-technology --work-subrole "Security engineer" --apply
```

WorkFocus is a list and may include your own labels. WorkSubrole is descriptive
text. Set either to none to clear; omit to preserve. Fields have no effect when
work is disabled. They never infer a manager/report relationship or grant access.

## Focus questions

- Sales: what was explicitly agreed, who owns the next step, and when is it due?
  Separate the customer's statement from an estimated chance of winning.
- Cybersecurity: what was observed, which source supports it, what is unverified,
  and who owns remediation? These notes do not authorize scans or system changes.
- Education: what is the learning objective, actual assessment deadline and feedback?
  Keep student records within institutional rules; do not infer grades or traits.
- Procurement: what are the stated requirements, comparable costs, exclusions,
  evaluation evidence and recorded approver? A recommendation is not approval to buy.
- Executive: which outcome, decision or dependency needs attention, and what is the
  user's own contribution versus the team's? Avoid unsupported forecasts/ratings.
- IT: what is the observed symptom, current state, known procedure and rollback
  reference? Preparing a runbook never authorizes executing commands on systems.

## Later additions, driven by actual use

Potential focused skills: sales discovery prep, incident learning, teaching/lesson
planning, vendor comparison, executive decision review, and change/runbook review.
The shared /brief and /handover skills provide the initial workflows now; these
specialized skills are suggestions, not installed commands. Add one when a repeated
workflow needs domain rules that the shared skill cannot express clearly.

A teacher's work planning uses Project/Note and work-area tasks; it does not require
a student Course template or school setup. /course and /term-close are optional
school workflows when recording formal study. A work focus informs only relevant
work requests; it does not add professional fields to personal/school records.
