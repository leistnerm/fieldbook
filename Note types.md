# Note types

Use a new note type when it stores a different kind of information. Use [[Types]]
for task subtypes; a task's `type` and a note's `tags` serve different purposes.
A folder helps you browse; a tag identifies the record in searches and views.

| Note tag | Stores | Folder / template | Helpful connection |
|---|---|---|---|
| task | One next action, status and dates | Tasks / Task | Project, course, opportunity |
| project | Outcome, scope, milestones | Projects / Project | Tasks, decisions, owner |
| course + project | Term, syllabus, assessments | Projects / Project - Course | School tasks, research |
| person | Supplied contact/context details | People / Person (default), Person - Professional contact, Person - Direct report | Meetings, projects, commitments |
| meeting | Agenda, notes and promises | Meetings / Meeting | People, actions, decisions |
| decision | What was decided and why | Decisions / Decision | Source meeting, affected project |
| reference | Reusable supplied knowledge | Reference / Reference | Related tasks/projects |
| research | Question, findings and sources | Research / Research | Project or decision brief |
| accomplishment | Contribution, result and evidence | Accomplishments / Accomplishment | Completed work, review, resume |
| opportunity | Opening, requirements and process status | Opportunities / Opportunity | Application tasks, people, resume |
| review | Formal draft/final evaluation | Reports/Reviews / Review-format | Goals and accomplishments |
| note | General context and working drafts | Notes / Note | Whatever makes it retrievable |

Accomplishment: `date` is the result date when known, `period_start/end` cover a
longer effort, `person` identifies whose contribution, and `sources` holds wikilinks.
Outcome claims remain provisional unless the sources support them. Use `/accomplishment`.

Opportunity `kind`: job, internship, scholarship, grant, volunteer, speaking, or
another supplied value. Status: exploring, preparing, applied, interview, offered,
accepted, declined, closed. Use `closing_date` for the opening's deadline and record
exact time/timezone in the body. Work to do remains linked task notes with their
own due dates. These records are optional in all setups. Use `/opportunity`.

Reuse ordinary notes for risks, runbooks, lessons learned, lesson plans, vendor
comparisons, account briefs and research ideas. Add topic tags before introducing
another schema. Make an actual new type only when repeated use needs distinct fields.

![[Views/Accomplishments.base#Recent]]

![[Views/Opportunities.base#Open]]

## Shared defaults and optional detail

A template is a starting point, not a form you must finish. Blank fields and empty
sections can stay empty or be omitted from a new note. Add detail when useful;
never replace a populated note to switch templates. Changing setups does not
rewrite existing records or hide them from an unfiltered plan.

All shared templates work in personal, work, school, core-only and combined vaults.
For AI-created records, area comes from your request or linked project, then your
configured default; contradictions need clarification. Inserting a template manually
in Obsidian leaves neutral area fields blank: set them yourself when useful.
Configure activates the appropriate template files; it does not fill or rewrite
existing records. Shared template bodies keep their neutral defaults.

For manual insertion, create and name an empty note in its record folder, switch
to **Editing view**, then run **Templater: Open insert template modal**. Check for
both properties and body headings. Insertion in Reading view omitted the body in
live testing. Alternatively, **Templater: Create new note from template** works
from Reading view too; complete prompts and check the new note's name and folder.
Use a named Tasks/ file in Editing view for task templates that derive their title
from the filename. See [[SETUP]] for recovery if a new note contains properties only.

| Shared starting point | Optional detail or specialization |
|---|---|
| Task / Task body | Generic action and log; Assignment adds coursework context only when chosen. Task body is TaskNotes' body fragment, not a standalone record. |
| Project | Goal, scope and notes; owner, stakeholders, milestones, subprojects, meetings and decisions are useful only when applicable. Course adds formal school/term context. |
| Note | Free-form thinking, drafts, reflections, lesson plans or runbooks; no review framework required. |
| Person | Professional contact or Direct report when the relationship/request calls for it; see the profiles below. |
| Meeting / Series | Any conversation or repeating gathering; agenda, decisions and commitments only as relevant. A 1:1 does not imply management. |
| Decision | A household, work or school choice; meeting, deciders, formal options and revisit date are optional. |
| Reference | Reusable supplied knowledge: recipe, concept, instructions, policy or query. kind is optional; topics, area and projects help retrieval. Add systems/verified only for relevant technical material; no invented verification dates. |
| Research | Question, sources, findings, conclusion and next questions; no hypothesis required. Experiment adds hypothesis, method and observations when explicitly chosen; both use tag research and Research/. |
| Item | Owned, borrowed or shared things, with no presumed ownership/area. Purchased item adds purchase/warranty fields in the same Items/ folder. |
| List | Shopping, materials, reading, packing or project checklists; a checkbox does not require a separate task. |
| Study session | A study task for a hobby, professional training or school; no course or deadline required. |
| Accomplishment | Contribution, result and evidence in any area; metrics and career reuse are optional. person identifies whose contribution, so the template does not assume it is yours. |
| Opportunity | Any supplied opening and next steps; employment, scholarship/grant and volunteer details only as applicable. |

Optional templates are retained in the module catalog and activated by setup.
Course and Assignment require school; Direct report requires work + people-manager;
Review-format requires work + reviews. Professional contact, Purchased item and
Experiment remain shared. A customized disabled template can remain in Templates/
as an explicit preservation exception; configure reports it.
A template does not enable a feature or grant permission to evaluate someone.

For example, the same shared templates handle a borrowed drill, a work laptop and
a library textbook; a recipe, a troubleshooting procedure and lecture concepts;
a travel comparison, vendor comparison and literature review. Add purchase terms,
technical testing fields or an experimental method only where those facts belong.

## People: choose a starting template

Use **Person by default**. All three templates create ordinary notes tagged person
in People/. Person and Professional contact are always active; Direct report is
activated for people-manager work. A template chooses the starting sections;
relationship describes the person relative to you. No separate customer/vendor
note type or folder is needed.

| Template | Use for | Included |
|---|---|---|
| [[Templates/Person]] | Friends, family, classmates, yourself, or an unspecified person | Aliases, relationship, contact details, optional birthday, notes, shared context, open tasks and meetings |
| [[Templates/Person - Professional contact]] | Peers, customers, vendors, instructors, partners | Organization (company), role (title), team, contact details, shared projects, conversations, commitments and linked tasks/meetings |
| Person - Direct report (work + people-manager) | Someone you manage | Professional context plus reporting line, goals, development, feedback, recognition, 1:1 notes, completed assignments and reviews |

Only Direct report starts with relationship report. Person and Professional contact
leave it empty until supplied; choosing a work setup never makes a person a report.
Set your own record to self and add goals/career sections when useful. Do not use
the report template for yourself. Nothing requires a friend or vendor to have goals,
performance feedback, an employer or HR information.

New contacts use emails and phones lists, optionally labeled, for example
`emails: ["personal: alex@example.com"]`. Keep existing workEmail, otherEmails,
workPhone, workMobile and otherPhones properties if older records already use them;
no automatic contact-field migration or deletion is needed. Optional birthday and
addresses belong in Person when useful. Add workerType, hireDate, contractEnd or
employeeNumber to a Direct report only when you need and have those details.

Use `/people create Sam, a family friend` for the default profile,
`/people create a professional contact for Alex, our vendor at Acme`, or
`/people create a direct report for Jordan`. Confirm ambiguous names first. For
manual creation, make People/Name.md, switch to Editing view and insert the chosen
Templater template, or use Templater: Create new note from template.
Automatic person stubs always use Person and leave the relationship unknown.

Templates are starting points. Changing an existing person's layout means adding
only the requested sections while preserving their facts, logs and links; do not
paste a whole template over a populated note. The Directory view groups by
relationship and shows common contact details; organization and report views remain
available for professional context.

## People and tracker identities

`relationship: self` identifies you; `relationship: report` identifies your direct
report. One current self record per vault. These values are available in any setup.
Use `status: current` (or leave status empty) for current contacts and `status: former`
for people who should be excluded from team sync. Manager links remain optional
context and do not select the sync team.

Store exact accounts in `usernames`, for example `"github:personal: your-login"` or
`"azure:office: you@example.com"`. The middle value is the configured instance ID.
See [[INTEGRATIONS]] for self/report examples and Jira/Agility formats. Never store
tokens in a person note. `/people Alex` can help inspect or fill supplied identities.

## Lists and items in any area

- `list` → Lists/ and Templates/List.md: groceries, packing, wishes, gifts or ideas.
  category identifies the list purpose; individual checkboxes are usually enough.
- `item` → Items/ and Templates/Item.md: neutral details, optional owner/location,
  links and history for owned, borrowed or shared things. Status and area start
  blank; record them from context. Choose Templates/Item - Purchased.md for purchase,
  receipt/manual, warranty/return terms and maintenance details. It is still an item
  in the same folder. Dates: purchased, warranty_end, return_by; prices keep currency.

Attachments/ holds PDFs/images saved by the user. Link them; the notebook AI tools
do not parse binary files. Personal setup also activates Setups/Household.md
with household examples.

## Template names

Specialized layouts use **Base type - Specialization** in the picker:

| Previous name | Current template | Availability |
|---|---|---|
| Professional contact | Person - Professional contact | Shared |
| Direct report | Person - Direct report | Work + people manager |
| Purchased item | Item - Purchased | Shared |
| Course | Project - Course | School |
| Assignment | Task - Assignment | School |
| Study session | Task - Study session | Shared |
| Experiment | Research - Experiment | Shared |

Person, Task, Project, Research and Item remain the neutral defaults. This changes
layout names, not record tags, task types or note folders. Task body keeps its name
because TaskNotes uses it as a fragment; Review-format keeps its name because it is
a protected user-customizable form, not another default review profile.

## Optional shared specializations

- **Note - Goal:** tags `note, goal`, stored in Notes; optional success measure, target, check-in, projects and evidence. Open `Views/Goals.base` or use `/goal`.
- **Item - Agreement:** tags `item, agreement`, stored in Items; separate `renewal_date`, `cancellation_notice_by`, `expiration_date`. Use `/renewal` and the corresponding Upcoming dates tabs. These are recorded terms, not an automatic cancellation or reminder service.

Both templates are available in every setup; using them is optional. Shared tasks use configured defaults when their template retains the standard initial values; customized template values and specialized task types take precedence. A Course/Assignment keeps its school area over a work default; an explicit conflicting area is refused.
