# Skills and useful workflows

Commands are convenient entry points; skills contain reusable procedures. They
live in fieldbook_core/skills/ and load on demand. Shared skills use the context of your
request. Specialized commands and wholly specialized skills are installed only
when enabled; shared skills retain any conditional branches listed below.
An enabled role never makes every conversation a coaching session or every result
part of a performance review. All writes still use the existing permission checks.

| Skill | Useful to | Command | Result |
|---|---|---|---|
| record-migration | Everyone | /migrate-records | Version inventory and small previewed batches; verified backup before edits |
| weekly-planning | Everyone | /plan-week | Capacity-aware plan, deadlines kept intact |
| project-kickoff | Everyone | /kickoff | Outcome, scope, milestones and first tasks |
| calendar-meeting | Everyone; live reads require the selected calendar feature | /meeting | Meeting from supplied details, local ICS or read-only Google/Microsoft events; link a recurring Series and prepare selected occurrences; chosen contacts only |
| personal-admin | Personal | /home | Errands, maintenance and renewal follow-ups |
| canvas-school | School + Canvas enabled | /canvas-sync | Read coursework, quizzes, discussion checkpoints and Planner; deduplicate and label date types before local updates |
| study-planning | Everyone for /study; school for /course and /term-close | /study, /course, /term-close | Learning/practice plan; optional formal course/tasks and term closeout |
| knowledge-review | Everyone | /synthesize | Sourced findings, gaps and next questions |
| review-evidence | Both work roles | /evidence, /review | Evidence table and mid/year-end draft |
| manager-coaching | People manager | /coach | 1:1, feedback or delegation proposal |
| tracker-sync | Everyone | /sync, /jira-sync, /agility-sync, /github-sync, /azure-sync | Read-only pull and reviewed local plan |
| tracker-draft | Everyone | /tracker-draft | Manual-entry tracker proposal |

## Additions worth considering later

- Personal: trip planning with supplied bookings and a household maintenance calendar.
- Contributor: incident-learning summaries from evidence.
- Manager: broader workload discussion across confirmed reports; onboarding and explicit 1:1 cadence already exist.
- School: source-linked retrieval quizzes; rubric-based self-checks already exist.
- Everyone: better mobile capture; connected-calendar planning and the human calendar picker already exist.

These are future suggestions, not features this release claims to implement.
Extend a current skill first when its scope already fits. Avoid adding a new task
type for every workflow: use a type from [[Types]] plus project/area/topic tags.

## Finding and reusing knowledge

| Skill | Useful to | Command | Result |
|---|---|---|---|
| fieldbook-help | Everyone | /help, /help /people | Contextual help from installed files |
| people-context | Everyone | /people, /people Alex | Contact directory/context; requested creation with Person default or a professional/report profile |
| accomplishment-capture | Everyone | /accomplishment task name | Contribution, outcome, sources and gaps |
| resume-crafting | Everyone | /resume target role | Tailored draft plus private evidence ledger |
| opportunity-planning | Everyone | /opportunity internship details | Opportunity record and proposed linked actions |
| handover-planning | Everyone | /handover project name | Coverage/onboarding/transition brief |
| decision-brief | Everyone | /brief compare options for X | Sourced options and questions to resolve |

These workflows use local notebook tools; reads/searches run without prompts.
Saving follows the selected harness’s approval settings. Role-specific ideas are in [[Setups/Work specializations]].

| Skill | Useful to | Command | Result |
|---|---|---|---|
| list-management | Everyone | /list | Lightweight checklists and optional task promotion |
| item-records | Everyone | /item | Neutral owned/borrowed/shared item; optional purchase/warranty detail |

Household examples and the distinction between lists, projects and items:
Setups/Household.md is activated with personal.

## Optional workflow boundaries

- Shared: tasks, projects, people, meetings (including /meeting and /1on1), references, research,
  study/practice, lists, items, planning, reports, status summaries, briefs and handovers.
- Available on request in any setup: accomplishments, resume drafting, opportunities,
  experiments, purchase records and professional contact layouts. They never
  run just because you completed a task or chose a work setup.
- Personal setup: /home household workflow. Shared /item, /list and /task do not need it.
- School setup: /course and /term-close; /study alone needs neither school nor a course.
- School + Canvas: /canvas-sync; selected read-only learning context, no remote edits.
- Work + reviews: /evidence and /review for formal mid/year-end evaluation; reviewing
  someone else also needs people-manager and a confirmed report.
- Work + people-manager: Person - Direct report template and /coach. Ordinary /1on1 stays
  available for any relationship; relationship self/report remains valid in any setup.
- Each tracker: its feature and connection must be configured; all setups qualify.

/help describes these distinctions without running workflows. Unfiltered private
planning includes unassigned and older-context notes; explicit filters are respected.
Outgoing drafts use the intended audience and approved source context. See
[[Note types]] for every template and its optional detail.

## Fieldbook workflow additions

The existing skills now cover calendar-aware weekly capacity, stale project next
actions, waiting-on commitments, manager onboarding/delegation, handover ownership,
returns/renewals, multi-stage study deadlines and rubric self-checks. No additional
commands or mandatory note types are needed. Suggestions remain optional; actual
local writes require a current hash and user/host approval and remote services remain read only.
/plan-week, /study, /coach, /handover, /item, /home and /help explain the relevant
branches. Coverage/read-time/conflicts must accompany remote planning claims.

## Shared optional workflows

`/goal` uses project-kickoff for a Note - Goal with linked evidence. `/renewal` uses item-records for an Item - Agreement with distinct renewal, notice and expiration dates. Neither requires a role or new feature switch.

## Coherent daily and weekly reviews (1.0)

`/daily-review` and `/weekly-review` use the existing weekly-planning skill in every
setup. They combine capture triage, dated obligations, meeting preparation, blocked
work, commitments and focus selection; weekly review adds completed-work evidence
and project gaps. `/plan-week` remains the separate scheduling action. Sync skills
use the existing read-only notebook_preview field comparison before local writes.
