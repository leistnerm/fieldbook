# Canvas LMS

Canvas LMS is an optional **read-only school integration**. `/canvas-sync` can read
selected courses, coursework, quizzes, discussion checkpoints and the student
Planner, preview updates to linked notes, and offer selected missing records. Announcements and calendar entries are
available as selected context. Nothing is submitted, graded, posted or changed in
Canvas; no class roster is imported.

## Configure it

Need a token? Run `python tools/configure.py --credential-guide canvas` for steps
and official links, including school policy and administrator cases. The guide
distinguishes a personal test token from an institution's OAuth registration;
Fieldbook currently supports existing approved tokens, not Canvas OAuth sign-in.
The guide does not request credentials or change settings.

Run the guided [[Configuration CLI]] from your vault:

```text
python tools/configure.py
```

Enable school, add a Canvas instance, enter your school's Canvas base URL and a
short local instance ID (for example `school`), then select credential storage.
Use a masked API-key prompt with the optional OS credential-store dependency, or
an environment-variable reference. Preview and **Save** the connection. The editor
returns to its menu; choose **7** for default remote scopes, select Canvas
and your saved instance, then choose course numbers. Review the add/replace preview,
type `use`, and **Save** again. You can also enter course IDs manually in
**3 Integrations**. Restart AI assistant after enabling the workflow.

The picker reads only your active enrollments, inspects one response and offers at
most 50 courses. It reports when the list may be incomplete; older/inactive courses
or courses outside the first page may need manual IDs. Listing neither enables
Canvas nor verifies assignment access. No class roster is requested.

To bind a specific existing Course note, choose **8 Link a local Project, Course or Meeting Series**,
select that Course, Canvas and the saved school instance, then choose or enter one
course ID. Review the metadata and type `apply`; the CLI backs up the note and
updates only its binding immediately. This does not change the connection's default
course list. “Sync this course” uses that exact instance/course pair.

## Courses at different schools

Add a separate saved Canvas instance for each school/account destination, with
distinct instance IDs and credential references. Then link each local Course:

```yaml
# Projects/Biology at North School.md
canvas_instance: north-school
canvas_course_id: "123"

# Projects/History at South School.md
canvas_instance: south-school
canvas_course_id: "123"
```

The identical numeric course IDs do not conflict: the saved instance is part of
the identity. Assignment identity includes instance, course ID and assignment ID.
Course titles are display text. A course-specific request uses its binding even
when the connection's default list contains other courses. Requests covering both
schools make separate reads with their own saved credentials; the AI never moves
a Course to another school or broadens a missing binding to all default courses.
An assignment/event-bearing note needs its identity conflict resolved before a rebind.

## Connection file and checks

For manual configuration, `fieldbook_core/canvas.json` contains only connection details:

```json
{
  "instances": [{
    "id": "school",
    "baseUrl": "https://your-school.instructure.com",
    "tokenVar": "CANVAS_TOKEN",
    "credentialStore": "environment",
    "courseIds": ["12345", "67890"]
  }]
}
```

Use the root Canvas HTTPS URL, without `/api/v1`, credentials, query parameters or
fragments. Custom institution domains are supported when they serve Canvas's API.
The guided CLI stores a key separately; never paste it into this JSON or a note.
For environment mode, supply `CANVAS_TOKEN` to the process launching AI assistant.
For OS storage, `credentialStore` is `keyring`; configure it through the CLI so
its vault/instance/URL binding matches. Moving a vault or changing its URL requires
saving the key again on that device.

Test the saved connection before your first sync:

```text
python tools/configure.py --test canvas --instance school
```

This uses the saved environment or OS credential and performs read-only checks;
it can run while Canvas is disabled and never enables it or changes any notes.
Check the course-scope results as well as authentication: listing accessible
courses does not prove access to coursework in every intended course. Select
course IDs to verify the intended scope. The CLI tests assignment/checkpoint,
quiz, discussion-topic, planner, calendar and announcement reads separately for
each selected course, with endpoint/course labels. Planner/calendar/announcement
probes use today's UTC date and a one-item sample. An empty result proves the
route responded, not that every expected deadline exists or checkpoints are
supported. Missing scope remains not verified; a failed route stays visible.
The 45-second diagnostic budget can leave later reads unverified; test fewer
courses if needed.
Untouched starter URLs are skipped by `--test all`, while an explicit unconfigured
Canvas test reports that it could not run. See [[Configuration CLI]] for staged
results, common HTTP failures and the separate offline `--check` command.

Enable the feature with a preview first, then repeat with `--apply`:

```text
python tools/manage-vault.py configure --setups school --canvas on
python tools/manage-vault.py configure --setups school --canvas on --apply
```

`--setups` replaces the selection: use `personal,school` to retain personal or
`personal,work,school` for a combined vault. Canvas stays off in every starter until
you enable it. Disabling school also disables Canvas; existing notes are kept.

## Account access

For your own account, Canvas documents manually generated access tokens where
institution policy permits. A distributed app acting for other users must use
Canvas's OAuth authorization process, typically with a school-approved developer
key. This first version accepts an existing token or approved OAuth access token;
it does not register an app, perform OAuth sign-in or refresh expired tokens.
Follow your school's access policy. [Canvas authentication](https://developerdocs.instructure.com/services/canvas/oauth2/file.oauth).

Where the institution scopes access, request only these GET endpoints:

- `/api/v1/courses`
- `/api/v1/courses/:course_id/assignments` (with `include[]=checkpoints`)
- `/api/v1/courses/:course_id/quizzes` (classic quiz metadata)
- `/api/v1/courses/:course_id/discussion_topics` (topic metadata, never replies)
- `/api/v1/planner/items` (current account, selected courses and date window)
- `/api/v1/announcements`
- `/api/v1/calendar_events`

The sync adapter itself permits only these reads. The CLI's separate connection
diagnostic also tries `GET /api/v1/users/self/profile` to check account authentication;
a narrowly scoped key can allow course/assignment reads while leaving that identity
check unverified. Inspect each stage before changing token permissions.
[Canvas profile-read scope](https://developerdocs.instructure.com/services/canvas/resources/users#method.profile.settings).
A token's wider account permissions
are not exercised by Fieldbook. Scope availability is controlled by the institution;
a read-only workflow cannot bypass that. [Developer keys and scopes](https://developerdocs.instructure.com/services/canvas/oauth2/file.developer_keys).

## First use

```text
/canvas-sync school list my courses
/canvas-sync school assignments for courses 12345 and 67890; update linked notes only
/canvas-sync school assignments for course 12345; offer missing assignments too
/canvas-sync school coursework for course 12345; planner context from 2026-10-01 to 2026-10-31
/canvas-sync school quizzes for course 12345
/canvas-sync school discussions for course 12345; show initial-post and reply deadlines
/canvas-sync school planner for course 12345 from 2026-10-12 to 2026-10-18
/canvas-sync school announcements for course 12345 from 2026-10-01 to 2026-10-15
/canvas-sync school calendar for course 12345 from 2026-10-12 to 2026-10-18
```

The assistant shows a local update/create plan. Select the records you want before
saving; the normal notebook write prompts still apply. Calendar copies of an
assignment link back to its Assignment rather than becoming a second task. Use
`/meeting` only for an actual event you want to prepare for, with selective people
handling. Announcements are source context, not automatic tasks or instructions.

Course identity is instance + course ID. Assignment identity adds assignment ID.
Records carry `canvas_instance`, `canvas_course_id` and, for assignments,
`canvas_assignment_id`, plus a source URL. The same title in two courses is not a
match. Keep institution instance IDs stable; do not reuse an ID for another school.

`due_at` is the deadline effective for the signed-in user, including overrides.
Keep its exact time and timezone in the note, separately from unlock/lock times.
A missing deadline stays unknown. Local `scheduled` study dates, priority,
checklists, notes and logs are preserved. A changed deadline is shown for review;
submission status, missing access or a closed course never automatically completes
or deletes your task. [Assignment dates](https://developerdocs.instructure.com/services/canvas/resources/assignments).

## Coursework coverage and date meanings

`coursework` combines assignments, classic quiz metadata, discussion-topic metadata
and Planner. It merges assignment-backed quiz/discussion copies and Planner
checkpoint entries using verified source identities, never titles. The date window
limits **Planner only**; course lists include all accessible items. Ask for a
specific deadline window to filter the typed dates in the resulting preview.
`planner` uses those same lists to resolve identities but returns Planner-linked
records only. `quizzes` and `discussions` read assignments as supporting context.
`assignments` remains a smaller read and now requests available checkpoint dates.

| Item | Coverage |
|---|---|
| Assignments and New Quizzes | Assignment metadata and effective dates; no questions/attempts |
| Classic graded/practice quizzes and surveys | Quiz metadata and dates; assignment-backed copies merge |
| Graded discussion | Associated assignment, plus separate initial-post/reply checkpoint dates when Canvas supplies them |
| Ungraded discussion | Topic to-do/availability dates, when present |
| Pages/readings and course reminders | Selected course Planner entries; no page body/file download |
| Events and announcements | Planner context or separate event/announcement reads; no automatic notes |

The returned `dates` list labels meaning and stage independently:

| Date type | Meaning and local handling |
|---|---|
| `due` | Actual deadline; keep exact time/offset. Discussion stages are `reply_to_topic` and `reply_to_entry`. |
| `todo` | Source reminder; does not overwrite your local study schedule or become a deadline. |
| `event_start`, `event_end` | Scheduled event boundaries; preserve all-day dates. |
| `available_from`, `closes_at` | Availability opens/closes; not the deadline. |
| `posted` | Publication time. |
| `planner` | Canvas display/sort date; can be a creation date and is not necessarily actionable. |

Null/missing dates stay unknown. Different returned dates are shown as conflicts
for review; equivalent timestamps with different offsets are not conflicts.
Checkpoint dates remain together in one assignment note by default. TaskNotes'
single `due` field cannot display both stage deadlines: request separate linked
stage tasks when you want both on task dashboards. Each uses its verified parent
assignment identity plus checkpoint tag, so syncing again does not recreate it.

For new/updated linked notes retain `canvas_identity` and `canvas_aliases`, alongside
instance/course IDs and existing `canvas_assignment_id`. Also keep supplied
`canvas_quiz_id`, `canvas_discussion_id` or `canvas_event_id`. Search all aliases and
legacy IDs before creating; conflicting existing notes need a choice. Titles and
same numeric IDs from different schools/courses never establish identity. Unknown
planner types or unresolved checkpoint parents are flagged for review before creation.

Only explicitly selected courses are read. General reminders without a course,
group-only planner entries, concluded courses omitted by Canvas, inaccessible or
unpublished items, dates written only in prose, and external-tool internal deadlines
are not guaranteed coverage. Checkpoints depend on the institution's Canvas version
and feature settings. An accepted `include[]=checkpoints` parameter does not prove
support; reported checkpointed discussions with incomplete stage data show warnings.
No reader can prove every course deadline is present from an empty response.

API references: [Planner](https://developerdocs.instructure.com/services/canvas/resources/planner),
[Quizzes](https://developerdocs.instructure.com/services/canvas/resources/quizzes),
[Discussion topics](https://developerdocs.instructure.com/services/canvas/resources/discussion_topics).
Canvas's implementation also documents the optional checkpoint representation:
[assignment serializer](https://github.com/instructure/canvas-lms/blob/master/lib/api/v1/assignment.rb),
[checkpoint fields](https://github.com/instructure/canvas-lms/blob/master/lib/checkpoint.rb).

## Limits and permissions

`canvas_pull` asks before a remote read. It requires school + `features.canvas`, a
configured instance and its credential. Course-scoped requests accept up to 10
chosen course IDs. Planner/coursework/announcement/calendar reads require an
explicit date range of at most 93 days. Results are bounded (up to 500 merged items,
2,500 source items, 100 requests and 8 MiB of response data), paginated and checked; a
failed page, malformed response or exceeded limit returns an error rather than a
usable partial sync. Narrow the request and retry. No background polling runs.

The adapter does not call grade, submission, roster, file, quiz-question/attempt or
discussion-reply APIs. Planner responses can include incidental status/feedback;
normalization discards it, including completion flags. Descriptions and announcements
are bounded source text; local task completion is always a separate decision. Do not upload
course materials to your AI provider unless your course/institution permits it.

Fresh profiles include `canvas_pull: ask` and skill `canvas-school: allow` in the
respective permission entries. Upgrades preserve `opencode.json`; merge those
entries from `tools/starter-seeds.json` if absent, keeping your provider and other
permissions. See [[Notebook tools]] and [[UPGRADING]].

API behavior is covered by fixture tests. Your school's live authentication and
access still need a small first-run check; begin with one selected course.
Connection diagnostics never try a submission or other write to test permissions,
and successful reads cannot establish that the token itself has no write scopes.
