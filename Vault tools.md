# Vault tools

Open `python tools/configure.py` in your vault and choose **15 Vault tools**.
These are human-operated local commands: no model calls or remote connections.
Use your Python environment from [[Notebook tools]]. Every creation shows a
preview; press Enter to cancel. Existing notes are never replaced by Create or
Intake. The existing upgrade and restore flows remain in menus 12 and 13.

| Menu | Purpose | Direct command suffix |
|---|---|---|
| 1 Back up now | Full verified snapshot, optional retention | `--vault-tools backup` |
| 2 Check vault | Settings, dependencies, links and record findings | `--vault-tools doctor` |
| 3 Compare upgrade candidates | Review preserved `.fieldbook-new` text | `--vault-tools compare` |
| 4 Create a record | Choose an enabled template and preview a complete note | `--vault-tools create` |
| 5 Saved integration activity | Review or explicitly save read/test metadata | `--vault-tools activity` |
| 6 Selected file/email intake | Extract selected local content into a Reference | `--vault-tools intake` |
| 7 Follow-up review | Local commitments, tasks, projects and optional manager context | `--vault-tools followups` |

For example, `python tools/configure.py --vault-tools doctor`. To operate on a
different vault, add `--vault "absolute path to your vault"`. Do not point this at
the release source folder when you mean your real vault. These terminal commands
do not grant the AI shell access or change AI assistant's notebook-write permissions.

## Back up independently of an upgrade

Close Obsidian and AI assistant and pause sync first. Choose a folder outside the
vault, or accept the sibling `<vault name>-fieldbook-backups` folder. Preview the
file count, size and destination, then type `backup`. Fieldbook copies all files,
including notes, attachments, hidden settings and local runtimes, and verifies
the snapshot before marking it usable. Allow space for the entire vault. Linked
files are preserved as links, without copying their external targets.

Backups contain the same private data as your vault; keep the destination somewhere
appropriate. OS credential-store entries are outside the vault and are not backed
up. A copy interrupted or changed during verification stays incomplete and cannot
be selected for automatic restore. The source vault is not rewritten.

Retention is optional after a successful backup. Enter the number of newest
verified snapshots to keep (at least one), review the exact folders to remove,
then type `prune` only to delete that list permanently. Enter keeps everything.
Invalid or incomplete backups are skipped. A changed retained snapshot blocks
pruning. Nothing runs on a schedule. For recovery use menu **13 Restore** or
`python tools/configure.py --restore`; it preserves the current vault in a
pre-restore snapshot before restoring a verified backup. See [[UPGRADING]].

## Check and compare

Check vault reports configuration/activation problems, runtime dependencies,
missing locally installed TaskNotes/Templater, optional PDF/OCR availability,
unexpanded template expressions, properties-only records, unresolved/ambiguous
wiki links and shared tracker/Canvas assignment identities. Findings are review
suggestions: a properties-only record or multiple note types linked to one ticket
can be intentional. No repair, deletion, metadata change or remote read occurs.

Record scans cover the standard content folders, at most 10,000 Markdown notes,
64 MiB total and 1 MiB per note. Warnings mean incomplete coverage. Templates,
examples, dashboards, attachments and arbitrary custom folders are not record
inventories. Wiki-link checks do not validate heading/block anchors, external URLs
or every Obsidian attachment-resolution convention. Confirm a finding in Obsidian.

Compare upgrade candidates lists manifest-owned text files with `.fieldbook-new`
copies. Select one for a unified diff and both file paths. Each file is capped at
1 MiB and displayed diffs at 100,000 characters. Compare all JSON settings manually
in your editor; the CLI excludes them to avoid printing connection settings. No
candidate is accepted or deleted automatically. Merge the parts you want into
your customized file, then remove the reviewed candidate yourself.

## Create a complete record

Choose an active template, name and optional area, inspect the full note, then
type `create`. Work, school and manager templates follow your enabled setups;
shared Person, Task, Project, Reference and other core templates remain available.
Inactive templates preserved for customization are not offered as active workflows.
The CLI fills known title/date expressions, removes recognized setup scripts,
uses the record's standard folder and selects a distinct name on a collision.
It never runs JavaScript. Custom template scripts/expressions require Templater
in Editing view or **Templater: Create new note from template** instead.

School specializations require school area. An explicit area wins for shared
templates, followed by the configured default; unknown area stays blank. This is
a starting note, not a ticket pull or completed review. Fill only useful details.

## Saved integration activity

Reads and connection tests do not automatically write receipts. To keep a test
summary, run a test in the main CLI, then choose **15 → 5 → 2 Save last CLI
connection-test summary** before leaving that session. Preview and type `save`.
Alternatively import a selected pull or diagnostic JSON result saved in
`Attachments/`; the import is explicitly labeled as reported, unverified evidence.

Receipts keep provider/instance, timestamps, read/test status, available counts,
partial-result warnings and scope/configuration fingerprints. They omit remote
bodies, raw query scopes, credential values and diagnostic message text. They live
in `.fieldbook/activity/`, separately from your notes. The activity screen reads
up to 500 recent receipts and can create a dated summary in Reports after preview.
Changed configuration is flagged. A successful connection test is not a notebook
sync, and the most recent saved receipt does not prove current access. There is no
background refresh. [[Integration coverage]] explains each adapter's limits.

## Follow-up review

[[Dashboards/Follow-ups]] is shared across personal, work and school. Its live Bases
show blocked tasks, assigned tasks, upcoming `check_in` dates and active projects.
An assignee can be yourself; assignment alone is not someone else's promise.
Add optional `check_in: YYYY-MM-DD` to a relevant record for a reminder to review
it within the next 14 days. This is distinct from a deadline and sends no alert.

The CLI also finds active projects without an unambiguously linked open task and
shows recorded bullets from meeting/series Commitments sections. Review whether
each promise is still outstanding; unchecked prose is not proof. All areas includes
blank area and existing records from disabled setups. An explicit area filter uses
the record's own area, so unset or conflicting metadata may leave apparent gaps.

Work + people-manager adds current explicit `relationship: report` people, their
last recorded work meeting and a selectable lookback (default 30 days). Group
meetings count. Reviews, when enabled, add linked accomplishment evidence in that
window. Missing notes do not prove missed meetings or poor performance. No ranking
or invented feedback is produced. You may save a dated Reports snapshot after
preview; it does not refresh itself or update any source note.

For selected email, PDF and image text, see [[Selected intake]].

## Optional daily workflows

Use `python fieldbook.py` > Daily use. Direct equivalents are `python tools/configure.py --vault-tools calendar`, `cadence`, or `export` (add `--vault PATH` for another vault).

Calendar capture selects a local ICS export or saved Google/Microsoft account, calendar and bounded UTC window, then one occurrence. It shows existing matches for manual review instead of overwriting them. Optional existing Series and individual people are selected separately. Missing people default off; no all-hands roster import. Cancelled events and unexpanded recurrence masters cannot become new meetings. Source descriptions stay literal, untrusted text. People saved before cancelling the meeting remain saved.

Manager cadence requires work + people-manager. Configure an existing work Series with a confirmed report, `meeting_kind: one-on-one`, `person` link and `cadence_days`. Meeting notes must independently carry `meeting_kind: one-on-one`, that Series link and the person attendee. Group or cancelled meetings never count; future meetings appear separately. Missing records do not establish missed meetings or poor performance.

Selected export starts from a Project/Course, review or accomplishment. Choose related notes individually and enter any additional exact note/Attachments paths. The preview lists all files, hashes, size and unresolved/outgoing links. Review confidentiality before typing `export`. Only those files enter a new ZIP outside the vault; relative folders and original bytes are preserved. Settings, credentials and hidden backups are excluded. No automatic redaction or claim of complete evidence is made.

Follow-ups now include overdue check-ins separately from the next 14 days. Review evidence includes overlapping valid date periods and separately lists undated/invalid periods. Identity-dependent actions stop on incomplete scans; note searches exclude hidden backups, templates and examples, including when content is stored in custom folders.

## 1.0: guided reviews

Daily use > Daily review / Weekly review gathers local deadlines, planned work,
meetings, goals, other date types and follow-ups. Weekly review includes recent
completions and accomplishments. Optional focus selection/snapshot saves do not
edit source tasks or remote services. Incomplete scans are visibly flagged; focus
selection stops until resolved. Notes and snapshots must fit the 1 MiB read/write
limit. See [[Everyday workflow]]. The selected-proposal sync inspector is read-only;
see [[Sync previews]].
