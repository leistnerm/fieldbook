# Upgrading Fieldbook

## Recommended: guided upgrade with a full backup

Extract the **new source release** outside your existing vault. Close Obsidian and
AI assistant, open a terminal in the extracted release folder, and run:

```text
python fieldbook.py -- --upgrade
```

Use Python 3.10+ (`python3` on some systems). The launcher prepares the required
Python environment. Run it from the separate source release, not from your vault.

1. Select your existing vault. Accept the current source release, or select a
   separate release folder/ZIP. The release must be outside the target vault.
2. Accept the suggested backup folder beside your vault, or choose another folder
   outside both the vault and release. Allow space for a temporary full copy and
   the full backup, plus upgrade files. Backups remain until you remove them.
3. Keep your existing settings, choose **2 Work + people manager + reviews**, or
   choose contributor/custom setups and toggle features. Custom setups support any
   combination of personal, work and school, plus work focus/subrole. Connections
   and credentials stay as configured; edit them in the normal menu afterward.
4. Choose **7 Review, back up and apply**. Review the file changes, selected settings,
   merge candidates and any manual migration issues. Type `upgrade` to proceed.
   Also check `preservedRemovals`: deliberately deleted commands/templates stay
   deleted even if you select their setup. Custom TaskNotes area defaults are kept
   and reported; they can differ from the new AI default area.
5. The CLI copies and verifies the **entire vault** before changing the original.
   It includes notes, attachments, empty folders, hidden settings, Git history and
   local runtimes. The backup lives in a dated folder containing `vault/`,
   `receipt.json` and `RESTORE.txt`. OS credential-store entries are outside the vault
   and are not copied. Runtime links are copied as links without reading their
   targets; linked notebook/managed paths remain unsupported. Filesystem special
   files/junctions stop the upgrade.
6. Review any `.fieldbook-new` candidates, merge wanted new AI assistant permissions
   into your retained `opencode.json`, refresh the vault Python dependencies, then
   restart both apps. Check your notes and Work/People management dashboards before
   discarding a backup. Customized inactive templates/pages can remain as preservation
   exceptions; old notes are never removed merely because a setup is disabled.

The CLI performs the existing layout migration and kit update in a temporary copy
before showing the final preview. Cancelling leaves the original vault unchanged.
Backup failure or edits after preview stop application. A write failure triggers
rollback of reviewed changes where the files still match the upgrader's writes;
concurrent edits are preserved and reported for manual recovery. Keep both apps
closed throughout. No multi-file updater can make concurrent editing atomic.

For recovery, use the guided restore below. It verifies the chosen backup and keeps
the entire current vault separately before replacing it.

Main-menu **12 Upgrade an existing vault** opens the same flow and returns to the
upgraded vault's configuration menu after success. Direct arguments are optional:

```text
python tools/configure.py --upgrade --vault "path/to/existing-vault" --from "path/to/new-release.zip"
```

Always run the new release's CLI. An older upgrader refuses a newer kit and tells
you to start its CLI; the wizard does not download or execute another release's code.
The manual commands below remain available for scripted maintenance.


## Restore a vault from backup

Close Obsidian and AI assistant and pause any vault sync. Extract the latest source kit
**outside the vault**, open a terminal in that kit, and run:

```text
python tools/configure.py --restore
```

Use Python 3.10+ (`python3` on some systems). Restore itself uses only Python's
standard library. Run Python from outside the target vault too, especially on
Windows, where open files or a terminal inside the vault can block its move.

1. Enter the vault's **original path**, even if it is missing or its configuration
   is broken. The parent folder must exist. A backup for a different path is refused.
2. Accept the suggested `<vault-name>-fieldbook-backups` folder beside the vault,
   or enter the custom backup folder you chose during upgrade. You may also enter
   a single dated folder containing `receipt.json` and `vault/`.
3. Pick a dated backup. The list shows its Fieldbook version, date, completion status
   and whether it came from an upgrade or an earlier restore. Incomplete backups
   cannot be selected.
4. The CLI verifies every entry against the receipt, prepares a separate copy on
   the vault's filesystem, and shows the changed paths. Type `list` to see all paths.
   Allow enough free space for that complete copy. Enter cancels without changing
   the vault or selected backup.
5. Type **`restore`** to proceed. The whole current vault is moved into a new dated
   **pre-restore backup** beside the vault, then the verified copy takes its place.
   Both backups remain. If the vault was already missing, no pre-restore backup is
   needed. If it already matches the selected snapshot, nothing changes.
6. The CLI exits after a successful restore. Reopen the restored vault and check
   your notes and settings. **Newer notes and edits are in the pre-restore backup;
   they are not merged into the older snapshot.** To undo the restore, run this
   command again and select that pre-restore backup. You can also copy individual
   newer notes back deliberately after reviewing them.

Main-menu **13 Restore a vault from backup** opens the same flow. Save or cancel
pending configuration edits first. For a damaged vault, prefer the direct command
above, which does not need to load the vault's settings. Optional direct arguments:

```text
python tools/configure.py --restore --vault "path/to/original-vault" --backup "path/to/dated-backup"
```

Restore returns all files and settings to the selected snapshot, including the
Fieldbook version, plugins, local runtimes, notes, hidden folders and Git history.
Links remain links; their external targets are not backed up or restored. OS-stored
credentials and remote services are untouched. Using the original vault path keeps
existing credential bindings. Restore accepts local Fieldbook backup folders with
receipts; arbitrary ZIPs and the small configuration-save backups are not full-vault
restore sources. Keep backup contents private just as you would the vault.

Failed verification leaves the current vault unchanged. A failed move attempts to
return the previous vault to its original location. If another process changes that
location, the CLI preserves those edits and reports recovery folders rather than
overwriting them. After a crash or forced shutdown, inspect the original path and
reported backup folders before retrying. Keep apps and sync closed throughout;
filesystem/OS failures can require manual recovery.

For manual recovery, move the current vault aside, then copy the selected backup's
entire `vault/` folder to the original location, including hidden files. Follow its
`RESTORE.txt`; do not merge it over a partly upgraded folder. Keep the displaced
vault until you have checked for newer notes you want to recover.


## Preview and preservation

Use Maintenance > Compare upgrade before applying changes. A pristine kit file
can be replaced; custom files and protected settings stay in place. Review
`.fieldbook-new` candidates and merge changes deliberately. Edited candidates
must be resolved before retrying. Repeating an unchanged upgrade makes no new backup.
Disabled resources may be stored in `.fieldbook/modules`; keep hidden files when
copying a starter. If required release files fail verification, extract a fresh source ZIP.

## Temporary folder access

If the default temporary folder is restricted, use
`python fieldbook.py -- --upgrade --temp-dir "path/to/existing-local-folder"`.
Keep that folder outside the vault, release and backups. Preflight checks copying,
renaming, removal and available space before application. Close apps and pause
sync; resolve filesystem permissions before retrying.

## After changing setups

Enabled setups control templates, commands, skills and dashboards. Existing notes
remain, and customized resources can remain as preservation exceptions. Review
Dashboard after configuration. Onboarding is optional for an existing vault and
does not overwrite manual template or TaskNotes defaults.

## Portable AI layout

The guided upgrade moves an existing `.opencode` runtime into
`.fieldbook/legacy-ai-runtime` in its preview, preserves provider configuration in
`fieldbook_core`, and retains all original files in the full backup. Archived
plugins are no longer auto-loaded. Custom old commands and scripts remain in the
archive for manual review. No dependency environment is copied into the new runtime;
prepare it with the launcher after upgrade. OS credential-store identities stay
bound to the same vault path.

Existing harness settings are preserved. If an older `opencode.json` denies shell
commands, review its permissions to allow approved calls to the portable Python
entry point, keeping your own provider settings. Shared/custom instructions can
produce merge candidates; review them before using an assistant. Then run Setup >
AI assistants and optional MCP. Never treat an old permission profile as proof that
the new harness has equivalent restrictions.

## Refresh record layouts separately

A kit upgrade never bulk-rewrites your records to match new templates. Ask your AI
assistant to run `/migrate-records` (plain language works in every supported harness):
“Preview the first five Person records against the current templates; preserve all
information and identifiers.” The shared record-migration skill reads complete
records and previews changes before saving. It uses the existing human-operated
Maintenance > Backup workflow **before every changed batch**, followed by approval
of those exact diffs. Notebook writes alone do not create backups.

Every complete shipped template declares `templateName` (stable identity, initially
the template filename without .md) and `templateVersion` (positive integer, initially
1). New records retain these properties. Template versions advance independently
when a template's structure or semantics changes; release numbers do not advance
them automatically. A template rename should retain its identity unless deliberately
creating a new specialization. For local changes, use your own unique identity or
bump the local version; preserved custom templates are the local reference.
`Task body` is a fragment with its own name/version comment; inserting it does not
change a task's provenance. Plugin-created records that do not use a complete
template may therefore remain unversioned.

Run `python fieldbook.py tool template_status` to compare records with installed
templates. Results are **unknown**, **older**, **current**, **newer**, or
**unavailable**. Unknown includes old notes without stamps; unavailable includes
missing/ambiguous template identities. These labels are advisory, not validation
of the note's content or proof a template is enabled. No automatic downgrade,
missing-template substitution or stamp-only bulk update occurs.

The skill keeps original metadata, prose, links, anchors, filenames and integration
IDs. It adds useful structure while keeping unmatched details; it does not invent
data, summarize history or merge duplicates. Current records can remain customized.
AI review is not a guarantee of semantic equivalence: inspect the diff and verify
representative records. Batches are not atomic; a failed write stops the batch and
reports already-saved paths. The normal restore workflow keeps the current vault
as a separate backup, including later edits, before restoring an older snapshot.
