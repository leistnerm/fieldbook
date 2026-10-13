# Everyday workflow

## First use

Run `python fieldbook.py` (`py fieldbook.py` on Windows). Choose **Setup > Guided
onboarding**, or launch with `python fieldbook.py -- --onboard`.

1. Choose core, personal, work, school, or a combination. Work adds contributor or
   people-manager; only selected specializations are activated. Use separate vaults
   when work/school policies or privacy boundaries call for it.
2. Choose defaults for CLI/AI assistant-created tasks. Blank area is useful for a combined vault. Preview the
   settings and activation changes, then type `save`. A local configuration backup
   is made when settings change; this is separate from a full vault backup.
3. Optionally identify your Person record with `relationship: self`. Use an existing
   neutral record or create one; no report profile is implied. Duplicate selves or
   another existing relationship require manual review. Existing content is preserved.
4. Optionally capture one task. Each note has its own preview and create/apply action.
5. Open Dashboard in Obsidian. Use Editing view for template insertion or Templater:
   Create new note from template. Configure optional integrations later through
   Integrations > Guided setup; remote reads require the selected account and scope.

Manual templates keep their template values, and customized TaskNotes defaults
are preserved. Use CLI/AI assistant capture to apply these configured task defaults;
inspect TaskNotes settings or your templates if you use those capture paths instead.
The managed area default is aligned when it can be updated without replacing a
TaskNotes customization.

You can rerun onboarding. It recognizes an existing self record and never treats a
checkbox as evidence that an integration was tested. Cancelling before save leaves
settings staged in that menu; exit to discard. Cancelling later leaves earlier
confirmed saves intact. No background sync, bulk contact import or remote writes
are enabled by onboarding. A first task is optional; rerunning does not invent one.

## Daily review — a few focused decisions

Choose **Daily use > Daily review**, or `/daily-review` in AI assistant. Select an area
or include all existing areas, including blank area and disabled-setup records.

- Triage captures; nothing is automatically turned into a task or deleted.
- See overdue deadlines, today's deadlines and planned work as separate lists.
- Prepare for recorded meetings and inspect blockers, commitments and check-ins.
- Review other dates according to their meaning: notice deadlines, renewals,
  warranties and decision revisits are not all overdue tasks.
- Select up to three focus notes. Incomplete records and missing meetings remain
  questions; do not infer free calendar time or poor performance.

The human CLI reads **local saved notes only**. It never refreshes calendars or
trackers automatically. A work-only review does not display the global Inbox's
mixed private text; inspect it separately. Use the calendar picker or an explicitly
requested read-only pull when fresh remote context is needed. Recurring instances
stay in TaskNotes. Canvas checkpoint/source-date tables in bodies need source-note
review; they are not flattened into local date fields.

## Weekly review — close loops and choose the next outcomes

Choose **Daily use > Weekly review**, or `/weekly-review`. Look back seven calendar
days including today and ahead seven including today. Add project next-action gaps,
recent completions, recorded accomplishments, goals and unresolved commitments to
the daily sequence. Meaningful, supported outcomes may deserve an accomplishment;
a completion alone does not prove impact. Manager 1:1 cadence remains optional and
requires explicitly marked records and work + people-manager.

Choose a small focus set and realistic capacity. `/plan-week` remains the scheduling
workflow; review does not silently reschedule, reprioritize, complete or create tasks.
Only user-requested/approved changes use notebook_write. You may save a review
snapshot to Reports after preview. Source text stays literal and untrusted; a saved
report is not a completed task or an external-ready performance evaluation.

## Before syncing or upgrading

Sync first shows source coverage and field conflicts; see [[Sync previews]].
Accept, keep local, or leave unresolved. No remote write follows any choice.

Maintenance contains Backup, Check, Upgrade, Restore and Compare. Upgrade from a
separate extracted release, close apps/pause sync, preview and keep the verified
full backup until you have checked your notes. Restore preserves newer files in a
pre-restore snapshot. See [[UPGRADING]] and [[Vault tools]].
