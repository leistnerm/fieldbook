# Sync previews

Integrations remain **remote read-only**. A pull retrieves source data; comparison
is another read-only step; an approved local note edit is a separate action.
Never send changes, comments, transitions, RSVPs or submissions to a remote service.

## What you see

For `/sync` and provider sync commands, the AI maps source values into the local
schema, then calls `notebook_preview` with a `sync` proposal and the note's current
SHA. The tool compares each field against the last reviewed source value stored
in that note. It does not fetch data, save baselines or apply proposed changes.

| Result | Meaning / action |
|---|---|
| unchanged | Local and proposed values agree; no field edit needed |
| first_sync | No reviewed baseline exists; choose whether to accept or keep local |
| remote_change | Local still matches the baseline; source changed; include in the approval plan |
| local_override | Source matches the baseline but local changed; preserve local |
| conflict | Both changed differently; choose the intended value |
| source_conflict | Multiple sources could govern this field; choose the authority |
| identity_conflict | Several local notes link the same source; select intended records; never auto-merge |
| unavailable | Null/empty source values do not clear local values |
| invalid / needs_review | Bad mapping/date or insufficient closure evidence; resolve before editing |
| protected | Local planning/title/priority unless explicitly included, wrong note type, recurring state or final review |

The table is **Field · Last reviewed source · Local · Proposed · Result**. It
includes the note, source identity and supplied read time/truncation/warnings.
This is a comparison of a supplied, mapped proposal, not proof that the proposal
accurately reflects a remote service. Source errors and missing results never mean
that a task was deleted or completed. Stale note hashes or incomplete scans stop
comparison; reread and re-preview before writing. Body, logs, identity fields and
TaskNotes instance data cannot be proposed through this comparison.

## Baselines and local choices

Baselines are optional `sync_baselines` frontmatter in the note. Existing notes
start without them, so first-sync review is expected. After approval, save only
reviewed field values under the returned `baseline_key`:

```yaml
sync_baselines:
  "<baseline_key returned by preview>":
    source: {provider: jira, instance: office, id: APP-123}
    fields: {status: active, due: '2026-10-20'}
```

These are the **last reviewed mapped source values**, not a copy of all local
properties. If you intentionally keep a local override, keep the local field and
record the reviewed source value. An unchanged source will then preserve that
override next time. Never advance skipped/unreviewed, unavailable, invalid or
protected fields. Baseline changes require the same approved `notebook_write` and
fresh SHA as the note edit; no additional permission is granted. Keep baseline
metadata small (at most 16 source identities, frontmatter at most 32 KiB). No remote
bodies, credentials or automatic pull timestamps belong in it. An unchanged sync
must not create notes or append log lines just to say it ran.

## Source identity

| Provider | instance | id |
|---|---|---|
| Jira / Agility / GitHub / Azure | Exact configured instance | Exact linked ticket ID; GitHub uses owner/repo#number |
| Canvas assignment-backed coursework | Exact configured instance | course_id/assignment_id |
| Google / Microsoft | Exact configured instance | JSON-encoded array `[calendar_id, series_id-or-event_id, occurrence_id]` |
| Local ICS | calendar_source, or `local export` if absent | JSON-encoded array `[UID, recurrence_id]` (retain empty second value) |

For calendar identities use compact JSON (no added whitespace), for example the
string `["cal","series","2026-10-12T12:00:00Z"]`; encoding the tuple avoids separator
collisions in real event IDs. Use normalized original recurrence identity, not the new start of a moved event.
Unknown Canvas aliases, planner-only identities and ICS/API equivalence need
explicit identity review first. Exact date times and checkpoint meanings remain
in source context; do not coerce them into due dates just to fit the table.

## Human CLI inspection

Normal users can use `/sync`; no JSON authoring is required. For inspecting a
selected proposal without AI, put a JSON file under Attachments and choose
Integrations > Sync conflict preview, or `--vault-tools sync-preview`. It contains:

```json
{
  "path": "Tasks/Example.md",
  "expected": "<current SHA-256 from notebook_read>",
  "sync": {
    "source": {"provider":"jira","instance":"office","id":"APP-123"},
    "proposed": {"status":"active","due":"2026-10-20"},
    "coverage": {"read_at":"2026-10-12T12:00:00Z","truncated":false}
  }
}
```

The CLI only prints the comparison. Resolve and save local edits through the
ordinary approved notebook workflow; use `/tracker-draft` for changes you intend
to enter manually in the remote service.
