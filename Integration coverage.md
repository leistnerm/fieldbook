# Integration coverage

Use CLI **14 Integration coverage**, or `python tools/configure.py --coverage`,
to see saved selections, enabled features, supported objects/date types and
exclusions. This is offline: no credential lookup, connection test or data cache.
Use **6 Test saved connections** for an explicit bounded read test. A test reports
checked_at and per-stage results; it never proves complete access or that a token
lacks write permissions. See [[Configuration CLI]] and [[INTEGRATIONS]].

Actual tracker, Canvas and live-calendar pulls return a coverage object with
read_at, requested scope/window, item limits, truncation, exclusions and returned
count. Trackers/Canvas also count date or identity review warnings. Read time is a
snapshot timestamp, not a scheduled refresh; no background polling was added.
A future provider must add its capability definition to tools/integration-coverage.json
and supply actual scope/limits in its pull and diagnostics. Unknown coverage must
stay unknown; a successful login is never a complete notebook sync.

| Source | Covered | Important exclusions / date rules |
|---|---|---|
| Jira | Selected issue scope, typed configured dates; default due/resolution dates | No automatic hierarchy, comments, attachments or unmapped dates |
| Agility | Workitem scope and configured scalar date attributes | No inferred timebox deadlines or portfolio traversal |
| GitHub Issues | Issues, assignees, completion reason, milestone context | PRs and Projects fields excluded; milestone date is a target |
| Azure Boards | Work items, area/iteration paths, configured fields | No inferred iteration dates; CLI checks one available item’s details |
| Canvas | Selected courses and mode: assignments/quizzes/discussions/Planner, or events/announcements | sources_read records endpoints used; Planner uses the selected window, other coursework lists are not window-filtered; no grades, rosters or submissions |
| Google Calendar | Selected calendars, dated occurrences/cancellations, series observed in the window | No mail/attachments/group expansion; series outside the window are unknown |
| Microsoft calendar | Signed-in account’s selected Graph calendars and occurrences | No shared/delegated mailbox routes or local PST access; export local Outlook to ICS |
| ICS | Local export snapshot and explicit occurrence identity | No live refresh, recurrence expansion or custom timezone rules |

Do not claim an empty result means something was deleted or completed. Truncation
means partial coverage. Empty/missing date fields and unrecognized identities need
review. Calendar attendee lists are capped and never a bulk-person import plan.
Canvas aliases prevent duplicate assignment/quiz/discussion records, while source
conflicts remain visible. No coverage report authorizes a write.

Default tracker pulls cap at 500 items (up to 5,000 when explicitly selected).
Tracker transport also caps each response at 2 MiB, each pull at 8 MiB/100 requests,
and serialized output at 2 MiB. A pull has a 120-second overall budget with
30-second requests; malformed, interrupted or oversized data fails without a
partial-success result. All tracker endpoint restrictions remain read only.
Canvas caps responses at 2 MiB each, 8 MiB total and 100 requests; the selected item
limit and output bound also apply. Live calendars cap total response data at 8 MiB,
output at 2 MiB and attendees at 20 per event. ICS accepts at most 1 MiB/100 events.
Provider guides retain exact limits and error behavior. Reports summarize metadata;
remote payloads and credentials are not persistently cached.

For planning, combine only the requested accounts/areas. Check freshness, missing
scopes and conflicts, then propose local changes. /tracker-draft writes suggested
remote changes locally for you to apply; all integrations remain read only.

## Keep a selected activity summary

CLI **15 → 5 Saved integration activity** can retain a metadata-only receipt for
a test run in the same session, or import a selected pull/diagnostic JSON file.
Saving is explicit; ordinary pulls and tests remain free of notebook writes.
View saved timestamps, counts and partial results, or export a dated Reports
snapshot. Changed configuration is flagged. Imported metadata is unverified,
connection tests are not syncs, and old receipts do not establish current access.
See [[Vault tools]] for storage, redaction and limits.
