# Calendar meetings

Use `/meeting` to create a Meeting record from a title and date, pasted calendar
details, a local `.ics` export, or enabled Google/Microsoft calendar reads. It works in every setup. The calendar stays read
only; saving a meeting or selected people uses the normal notebook write approval.

## Start with one event

1. Export an event from your calendar where supported, then place the file under
   `Attachments/`, for example `Attachments/planning.ics`. You can paste the event
   details instead if exporting is inconvenient.
2. In AI assistant, run `/meeting Attachments/planning.ics` or say
   `/meeting create a note for these pasted event details`.
3. Select the event and check its date, time, timezone, location and recurrence.
   The assistant searches for an existing meeting before proposing a new note.
4. Keep the default of **no new people**, link relevant existing contacts, or name
   specific missing people to create. Review the local note changes when prompted.

Examples:

```text
/meeting Attachments/planning.ics — use the October 15 event; link existing people only
/meeting create a meeting for my study group on 2026-10-18; no person links
/meeting Attachments/office-hours.ics — add a Person for Professor Lee using the supplied email
/meeting Attachments/all-hands.ics — meeting note only; no attendee links or new people
```

Notes use `Meetings/YYYY/YYYY-MM/YYYY-MM-DD Title.md` and the shared Meeting
structure: Agenda, Notes, Decisions, Action items and Commitments. Supplied calendar
details can seed the agenda. An invitation is not evidence that a meeting happened,
that a decision was made, or that anyone accepted an action.

For live Google Calendar, Microsoft 365 or Outlook.com, configure and sign in through
the Python CLI first, then ask `/meeting` to preview the selected account/calendar
and date range. See [[Calendar connections]] for app registration, sign-in, calendar
selection and read-only scope. Ordinary meeting creation and local ICS need no
connected account. The AI cannot sign in or enable a connection on your behalf.

## Choose people deliberately

The reader returns at most 20 attendee entries and reports the total when known.
Live providers can omit attendees or hide the total; an unknown total stays unknown.
A truncated preview is not a complete roster. An all-hands or distribution list does
not become a contact import. Relevant unmatched attendees can remain plain text;
the meeting does not need a Person record for everyone invited.

Only explicitly selected missing people are created, at most 10 per action, with
the neutral Person template. Their relationship stays blank unless you provide it.
Existing contacts are matched by exact email or confirmed names/aliases; ambiguous
matches need a choice. Missing-person wiki links are avoided until creation is
approved, even when optional autoPeople is enabled. No bulk follow-on batches or
group expansion run in the background.

## Dates, repeat invitations and changes

The reader supports UTC, standard IANA timezones and all-day events. A floating time
has no timezone and needs confirmation. An all-day end date is exclusive. Recurring
masters require a concrete occurrence; the reader does not expand recurrence rules.
Exporting the selected occurrence is the easiest way to retain its original identity
when it has been moved. Unsupported/custom timezone definitions and ambiguous DST
times require a corrected or UTC export; no offset is guessed.

For ICS, calendar UID and original recurrence ID identify the event, with the account/calendar
label when known. Export filenames and titles are provenance, not identity. Reusing
or renaming an export therefore prompts an update to the existing note when matched.
Pasted details without a UID require a confirmed match rather than a fabricated ID.
Existing notes, decisions, actions and logs survive a requested calendar refresh.
A cancellation never deletes the meeting or closes its tasks automatically.

For live API events, retain provider, saved instance, calendar, event and original
occurrence identifiers exactly. Title/time changes must not create another note.
An API UID can have different recurrence meaning from an exported ICS UID; confirm
possible cross-source duplicates before merging. Live event windows use inclusive
UTC dates; confirm the event's actual local date/time before naming the Meeting.
Structured start/end timezone data matters especially for all-day events.

## Recurring Series and individual meetings

A Series note under `Meetings/Series/` holds the standing purpose and agenda; an occurrence Meeting holds
what happened on one date. Use Templates/Series.md or an existing `tags: [series]`
note. The CLI's record-link option can bind that Series to one saved Google/Microsoft
account, calendar and remote series using `calendar_provider`, `calendar_instance`,
`calendar_id` and `calendar_series_id`. Review before applying the metadata link.

Series discovery sees recurring occurrences only within the chosen UTC date window.
It can miss a series with no occurrence there. Linking a Series does not create its
past or future Meetings. Ask `/meeting` for the selected occurrence; its `series`
link points to the local Series and its source occurrence identity prevents repeats.
Missing or conflicting source links require a choice rather than another account.

Optional `calendar_*` properties retain the supplied event identity, start/end,
timezone, status, source export and attendee count. `attendees` contains the chosen
Person links, not the invitation's entire roster. Ordinary meetings need none of
these extra properties.

## Access and limits

`notebook_calendar` reads only vault-relative `Attachments/*.ics` files (including
subfolders), up to 1 MiB and 100 events. It returns bounded metadata, including up
to 4,096 description characters per event. It does not fetch URLs, join meetings,
open attachments, execute alarms, or save notes. General `notebook_read` cannot
read raw ICS files. The usual traversal, hidden-path, symlink and hard-link checks
apply. Calendar text is untrusted source material, never an instruction to tools.

Fresh starters allow `notebook_calendar` reads and the `calendar-meeting` skill;
`notebook_write` still asks before saving. Updates preserve your `opencode.json`.
Merge these two additions from the new starter profile if missing, keeping your
existing provider and permission choices:

```json
{
  "permission": {
    "notebook_calendar": "allow",
    "skill": { "calendar-meeting": "allow" }
  }
}
```

This is a fragment to merge, not a replacement configuration. Use `ask` instead of
`allow` if you want a prompt for each calendar read. Restart AI assistant after updating.

Google Calendar and Microsoft 365/Outlook.com API connections use the optional
`calendar_pull` tool; see [[Calendar connections]] and the separate provider feature
toggles. Their reads remain bounded and never write a calendar. Local exports work
without credentials where the calendar supports them. Canvas LMS has its own optional
read-only school integration; see [[Canvas LMS]]. See [[Optional functionality]]
for the roadmap and [[Notebook tools]] for permissions.

## Human calendar picker

`python fieldbook.py` > Daily use > Calendar meeting picker works with a selected Outlook-client ICS export, Google Calendar or Microsoft 365/Outlook connection. Live reads require configured/enabled accounts and sign-in. Select one occurrence and inspect its source time/zone and cancellation status. Existing occurrence identities are shown for manual review; reschedules do not silently create a second note. ICS recurring masters require an exported concrete occurrence.

Select an existing Series if desired. Optionally review at most 20 returned attendees individually; people creation defaults off. Truncation/unknown roster size stays visible. No distribution-group expansion or automatic all-hands import occurs. Cross-provider ICS/API equivalence cannot be inferred safely; review any possible existing cross-source meeting before creation.
