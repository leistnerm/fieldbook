# Choose your setup

Prefer a guided menu? Run `python tools/configure.py` to select setups, roles,
features and integration details. See [[Configuration CLI]].

The shared core is always present. `fieldbook.json` is your local configuration;
updates preserve it. Shared templates stay neutral in every setup; optional templates/sections are
chosen from the request, never from role alone. See [[Note types]] and [[Skills]].
The source kit carries every optional module. Deploy and configure install only
its enabled templates, commands, skills and daily dashboards into the active
folders. Inactive resources are retained under .fieldbook/modules/ for later use;
they do not appear in Templater or the normal command menu. Shared templates and
saved Bases remain available. /help can explain a disabled workflow when asked.

| Choice | Good for | Dashboard |
|---|---|---|
| Core only | A small task/project notebook | [[Dashboard]] |
| personal | Home, errands, appointments, personal projects | `Dashboards/Personal` |
| work + individual-contributor | Your delivery, learning, optional self-evaluation | `Dashboards/Work` |
| work + people-manager | The above plus optional reports/coaching | `Dashboards/Work`; `Dashboards/People management` |
| school | A term of courses and coursework | `Dashboards/School` |

In a terminal from the vault, preview a choice, then add `--apply`:

```text
python tools/manage-vault.py configure --setups personal,work,school --work-role individual-contributor
python tools/manage-vault.py configure --setups personal,work,school --work-role individual-contributor --apply
```

Switch work role with `--work-role people-manager --apply`. The role changes the
assistant's workflows, not existing notes. Remove contexts by supplying a new
complete `--setups` list; `--setups core` selects none. It never deletes their data.
An omitted option preserves its setting. A single setup becomes the default area;
multiple setups leave area empty unless supplied or inherited from a project.

Work enables review preparation for either role. Independent optional switches:
`--jira on`, `--agility on`, `--github on`, `--azure on`, `--reviews off`,
`--auto-people on`, `--auto-commit on`. Automation and trackers default off.
All four trackers work with any setup, including core only; configure them in
[[INTEGRATIONS]]. Disabling work turns off reviews and preserves tracker choices.
For example: `python tools/manage-vault.py configure --setups personal,school --github on --apply`.

Use configure when changing setups so files and menus follow the settings. If you
edit fieldbook.json manually, run `python tools/manage-vault.py configure --apply`
to reconcile it, then restart AI assistant and reopen affected Obsidian pages. Without
--apply, configure previews activation, inactive resources, and preserved exceptions.
Health reports configuration drift. See [[SETUP]] for a health check.

## What appears in your vault

| Requirement | Added to active folders |
|---|---|
| Shared core | Neutral templates, everyday commands/skills, Dashboard, all saved Bases |
| personal | Personal dashboard, /home and household guidance |
| school | School dashboard, Project - Course and Task - Assignment templates, /course and /term-close |
| work | Work dashboard and the selected role dashboard |
| work + people-manager | Person - Direct report template, People management dashboard, /coach and coaching skill |
| work + reviews | Review-format, /evidence, /review and review-evidence skill |
| Each tracker feature | Its provider-specific sync command; /sync and /tracker-draft stay shared |

Professional contact, Purchased item, Experiment and Study session stay shared.
A work laptop, professional training or a vendor contact does not require personal
or school. Existing notes retain all their fields and relationships in every setup.

Disable archives only files proven unchanged from the kit. Customized active files
are kept in place and reported as exceptions, so a customized optional template or
command can remain visible until you move it yourself. Customized dashboards are
preserved with a .fieldbook-new candidate. Re-enabling restores optional defaults
without overwriting your changes. Do not edit the hidden canonical module copies.

Daily work starts at [[Dashboard]] or the enabled pages in Dashboards/. Setups/ is
for instructions, not daily navigation. The table above is a catalog; a disabled
module does not have an active dashboard file.

## One notebook or several?

A single vault supports personal, work and school at once. A useful starting
recommendation is **personal + school together, work separate** when employer data,
managed devices, retention rules or AI policies differ. Choose one combined vault
when those boundaries are compatible and convenience matters more.

Area filters organize content; they do not isolate it. Searches, model context,
backups, Git snapshots and cloud sync can include every area in a vault. Use separate
folders opened as separate Obsidian vaults and AI assistant projects for real separation.
Each gets its own fieldbook.json, integrations and approved model provider. Do not
nest one vault inside another or link them through symlinks. Notebook tools stay in
one vault. Copy only selected permitted evidence for a cross-context resume.

## Domain specializations

Keep the contributor/manager choice; optionally add workFocus and workSubrole.
See [[Setups/Work specializations]] for sales, cybersecurity, education, procurement,
executive, IT and other ideas. Focus affects guidance, never tool permissions.

All area dashboards share the same basic structure. Optional course, management,
review and tracker views are selected explicitly; see [[Setups/Dashboards]].
