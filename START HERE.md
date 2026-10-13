# Start a new Fieldbook

Already have a vault? Extract the new source kit separately and run
`python tools/configure.py --upgrade` for a guided upgrade with a verified full
backup and setup/role choices. See [[UPGRADING]]. Starter deployment below creates
a new vault; it is not the existing-vault upgrade flow.

Need to recover after an upgrade? Run `python tools/configure.py --restore` from
the separate source kit, or choose menu **13**. Pick a verified backup and preview
the restore. Your current vault is kept separately so you can recover newer notes
or undo the restore. Close both apps and pause sync first; see [[UPGRADING]].

Use the supplied ready-to-open starter ZIP, or create one from this source kit.
The recommended split is a personal + school vault and a separate work vault when
work data/device/AI rules differ. One combined vault is supported. Area filters
organize notes but do not provide privacy isolation; see [[Setups]].

## Deploy from the kit

Install Python 3.10+ once, then run from the extracted kit's folder in a terminal:

```text
python tools/deploy-vault.py --destination "C:/Notebooks/Personal and college" --setups personal,school
```

This prints a preview only. Add `--apply` to create the new vault and download the
pinned TaskNotes and Templater releases. Use `--setups work --work-role people-manager`
for a manager vault, `--setups personal,work,school` for one combined vault, or
`--setups core` for core only. The default is core. The destination must not exist;
it never merges into an existing vault. A failed download leaves no deployed vault.

For a pre-downloaded offline cache, pass `--plugin-cache <folder>` with files
under `<folder>/<plugin-id>/<version>/` (main.js, manifest.json, styles.css and
Templater source.tar.gz). Hashes are still checked; missing files fail without a
network fallback.

`--without-plugins` creates configuration/source only for offline/manual plugin
installation. A starter ZIP already includes the plugins and needs no deployment
command: unzip it into its own folder. Python is still needed for optional AI tools.

## First open

1. In Obsidian, Open folder as vault and choose the deployed folder. Use Obsidian
   1.13.0 or newer (also check the bundled plugin manifests if updating versions).
2. Accept Obsidian's community-plugin trust prompt when you are ready. TaskNotes
   and Templater are preinstalled/enabled in the profile; if Restricted mode keeps
   them off, enable community plugins, then enable those two. The kit does not
   bypass Obsidian's trust UI or install the Obsidian application itself.
3. Open [[Dashboard]]. Create a test task, schedule it for today, block it, then
   complete it. Confirm the lists update. This remains the first-use acceptance check.
4. Optional AI: follow the short Python installation in [[Notebook tools]], choose
   Setup > AI assistants and optional MCP, then open the vault in your selected
   harness. No AI plugins or MCP are required. See [[Using AI assistants]].
5. Optional connections: run `python tools/configure.py` for guided setup, feature
   switches, URLs and optional masked credential entry. Save a connection, choose
   its project/repository/course from the menu, save the scope, then run the
   read-only connection test to check authentication and selected read access;
   see [[Configuration CLI]]. Canvas is optional for school; see [[Canvas LMS]].
   Google Calendar and Microsoft 365/Outlook support named accounts and selected
   calendars in every setup; see [[Calendar connections]] for app registration and
   the menu sign-in step. Link existing Projects, Courses or Series using option 8.
   Option **10 Guided integration setup/test** keeps all those steps together for
   your selected provider; its setup requirements can be read without signing in.
   Need a key or app registration first? Choose **11** for a step-by-step guide
   with official links, or run `python tools/configure.py --credential-guide`.
6. Optional trackers: every starter includes Jira, Agility, GitHub Issues and Azure
   Boards support, all disabled initially. Follow [[INTEGRATIONS]], add self/report
   person identities as needed, then enable only the providers you use. Start with
   `/github-sync linked` or `/azure-sync linked`; remote trackers always stay read only.

Every starter includes Person (the neutral default) and Professional contact.
The people-manager starter also activates Direct report. School activates Course
and Assignment. Work with reviews activates Review-format. Shared Study session,
Purchased item and Experiment stay available in every setup. Create People/Name.md
and insert an active template in **Editing view**, or ask /people to create it.
See [[Note types]].

## Create a note from a template

- **Existing empty note:** create and name it in the appropriate record folder,
  switch to **Editing view**, then use the command palette → **Templater: Open
  insert template modal** and choose a template.
- **New note:** command palette → **Templater: Create new note from template**.
  This works from Reading view too. Complete any prompts, then check the new
  note's name and folder. For task templates, use an already-named Tasks/ note in
  Editing view so the title property starts with the right name, or use TaskNotes.

Check for both properties and body headings. If a new empty note lacks its body,
switch to Editing view and insert again, checking for duplicates. Preserve
populated notes and add only missing sections. See [[SETUP]].

## Included configuration

Open Dashboard for links to the installed daily dashboards in Dashboards/. A work
manager vault offers Work and People management; it does not offer Personal or
School. Source ZIPs contain the full module catalog; starter ZIPs are already
configured. Keep the hidden .fieldbook/modules folder when copying a starter.
Use configure to change the active selection later; see [[Setups]].

TaskNotes is configured for Tasks/, root Views/ command mappings, Fieldbook statuses
and priorities, task body template, project tags and custom fields. Templater points
to Templates/ with automatic/script startup features at their safe defaults. Bases, Bookmarks and Canvas
are enabled; Obsidian's separate core Templates plugin is off. Details and manual
fallback: [[SETUP]]. No live tasks, contacts, credentials, caches or window layout
are copied into the starter.

## Updating later

Plugin versions are pinned in tools/starter-plugins.json with SHA-256 hashes and
source URLs. The helper verifies downloaded bytes and never runs them itself.
Use Obsidian's plugin updater deliberately; a later version may change settings.
For Fieldbook kit updates use [[UPGRADING]], not deploy-vault.py. The pinned starter
settings are verified against source, but live rendering and host trust prompts
still need acceptance testing. The ready starter is a convenience, not proof of
compatibility with every device/sync provider.

See [[Integration coverage]] for provider coverage and date mappings.

## Optional local tools

Use configuration menu **15 Vault tools** to back up the vault, check it, compare
upgrade candidates, create a complete record, review saved integration activity,
import selected email/PDF/image text or review follow-ups. [[Vault tools]] explains
the previews and [[Selected intake]] covers optional PDF/OCR dependencies. Shared
[[Dashboards/Follow-ups]] works in every starter; manager context requires work +
people-manager. No live mailbox integration or automatic receipts are enabled.

The starter ZIP includes requirement lists, not a `.venv` environment. Create that
folder on your own machine using [[Notebook tools]], then install requirements.

## Simplest launch

Run `python fieldbook.py` (or `py fieldbook.py` on Windows) from this folder.
It prepares the private Python environment and opens the grouped setup menu.
For your existing vault, choose Maintenance > Upgrade from a separate extracted
release. Daily use contains calendar capture, follow-ups and selected export.

## Your first 1.0 session

1. Run `python fieldbook.py` (`py` on Windows), choose Setup > Guided onboarding.
2. Save chosen contexts/defaults; optionally identify yourself and capture a task.
3. Open Dashboard, then use Daily use > Daily review. At week's end use Weekly review.
4. Set up integrations only when useful; read tests and note sync remain separate.

See [[Everyday workflow]] for the short path and [[Sync previews]] for change decisions.
