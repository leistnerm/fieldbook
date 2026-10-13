# Configuration CLI

Use the guided Python editor to select setups, toggle features, and configure
integration URLs, scopes and credentials without editing JSON by hand:

```text
python tools/configure.py
```

Run it from your vault, or add `--vault "path/to/vault"`. On macOS/Linux use
`python3` if that is your Python command. Python 3.10+ is required. The editor
stages changes, shows a preview, and saves only when you choose Save. Save returns
to the menu so you can continue with project selection and testing; **0 Exit**
discards only changes made since the last Save. It uses the same activation rules as manage-vault.py, so
templates, commands and dashboards follow your selection.

## Upgrade an existing vault

Choose **12 Upgrade an existing vault (backup + preview)**, or run the new source
release's CLI with `python tools/configure.py --upgrade`. Select the vault, release
and backup folder. Keep existing settings, use the work + people-manager shortcut,
or select other setups, roles, work focus and features. The preview is prepared in
a temporary copy; **7 Review, back up and apply** shows the final changes and requires
typing `upgrade` before a verified full backup and application. Cancelling does not
change your vault. The backup includes hidden files and attachments and stays outside
the vault. Connection credentials and user settings are preserved except for the
setup/feature changes you select. See [[UPGRADING]] for recovery and first-time use
from old releases. After a menu upgrade, this editor targets the upgraded vault.

The upgrade does not access remote services or OS credentials. Connection editing,
read tests and sign-in remain separate menu actions. Keep both apps closed during
the upgrade and review reported merge candidates afterward.

Release input can also be a starter kit or configured source folder. Disabled
resources are recovered from manifest-verified hidden copies without importing
source-vault notes or settings. The preview lists preserved removals, custom
defaults and merge candidates. Resolve edited candidates before retrying.

## Restore a vault from backup

Choose **13 Restore a vault from backup**, or run `python tools/configure.py --restore`
from a fresh source kit outside the vault. Close both apps and pause sync first.
Enter the original vault path, select the backup folder and pick a dated backup.
The CLI verifies it against its receipt and shows a preview; type `restore` to apply
or press Enter to cancel.

Restore replaces the whole vault with that snapshot, including its Fieldbook version
and settings. The current vault is kept in a new dated pre-restore backup beside it,
so newer notes remain recoverable. Select that backup later to undo the restore.
The CLI exits after success. No connections or credentials are accessed. The direct
command also works when the target vault's settings or CLI are broken or missing.
See [[UPGRADING]] for space requirements, optional arguments and manual recovery.

## Guided setup and testing for any integration

Choose **10 Guided integration setup/test**, or open it directly:

```text
python tools/configure.py --integration-setup
python tools/configure.py --integration-setup canvas
python tools/configure.py --integration-setup microsoft
python tools/configure.py --calendar-setup
```

All seven providers use the same numbered checklist: requirements, connection
details, preview/save, credentials or calendar sign-in, default scopes, read-access
test, local record linking and optional feature activation. The provider stays
selected throughout. Save staged changes before discovery, sign-in, testing or
record linking. A record link has its own immediate preview/Apply with backup.

Prerequisite screens are offline and can be explored before you have an app
registration or API key. Nothing signs in, retrieves credentials or reads a remote
service just because you open the menu. Calendar OAuth uses the Sign in action;
other integrations explain their existing token setup. Features remain off unless
you explicitly toggle and save them. Canvas activation still requires school.

`--calendar-setup` also explains which connection to use for a calendar displayed
in Outlook: Microsoft cloud uses Microsoft, Google uses Google, and local-only/PST
or on-premises calendars use an exported ICS file. Google Calendar does not read
Gmail messages. Main-menu **6** and `--test all` still test all saved integrations.
Missing configuration or scope stays unverified; a connection is not marked ready
merely because its URL responds. Future adapters must implement the same diagnostics
contract; developer instructions are in `tools/ADDING-INTEGRATIONS.md`.

## Get an API key or register an app

Choose **11 Get an API key / register an app** from the main menu, or **9** inside
an integration's guided setup. You can also start with a provider directly:

```text
python tools/configure.py --credential-guide
python tools/configure.py --credential-guide jira
python tools/configure.py --credential-guide google
python tools/configure.py --credential-guide microsoft
```

The numbered walkthrough explains where to go, which credential type and read
permissions to choose, and which details belong. Jira offers separate
Cloud scoped-token, Cloud compatibility and Data Center paths. Each provider has
official documentation links; institution-specific URLs are explained in the steps.

- Press **Enter** for the next step, **b** for back, or **q** to return.
- Type **open 1** (or another displayed link number) to open that official link in
  your browser. Links also remain visible for copying; none opens automatically.
- Finish the provider's registration yourself, then return to guided setup to
  configure, save, choose scopes and test. Calendar sign-in is a separate action.

These instructions can be read before you have credentials. The guide does not
ask for keys, create registrations, inspect a credential store or change settings.
Never paste a secret into its navigation prompt. Token entry uses the masked Save
prompt when OS storage is selected; Google client-secret entry happens at Sign in.
Completing the guide does not verify credentials or read access. Organization or
school policy may require an administrator; the walkthrough describes those cases
and identifies unsupported registration flows. Existing remote access remains read only.

The maintained steps and links are in `tools/integration-guides.json`, with a
documentation-check date. Future providers must supply a guide and automated
coverage as described in `tools/ADDING-INTEGRATIONS.md`.

## What to configure

- **Setups and role:** core, personal, work, school, or combinations; work individual
  contributor or people manager. Existing notes remain available after a switch.
- **Features:** the four trackers, Canvas, Google/Microsoft calendars, reviews and optional background automation.
  Canvas requires school; reviews require work. Nothing is enabled implicitly by an
  AI request.
- **Connections:** add/edit an instance's URL, account details and selection/filter.
  Jira, Agility, GitHub Issues, Azure Boards, Canvas, Google and Microsoft have provider-specific fields.
  Keep stable instance IDs because notes use them as source identities.
- **Validation and preview:** check settings before saving. Unknown custom properties
  are preserved. Configuration validation does not prove live authentication.

For each connection, start with the base URL and the smallest useful scope. Review
status/resolution mappings before a tracker sync changes local task statuses.
Canvas uses selected course IDs and student-effective deadlines; see [[Canvas LMS]].
Its connection test now probes assignments/checkpoints, quizzes, discussion topics,
Planner, calendar and announcements separately for every selected course. A successful
sample is read access evidence, not proof that every deadline or checkpoint is present.
Remote services remain read only regardless of how credentials are stored.

## Choose default remote scopes

All seven direct integrations can be configured in this editor. For a new connection:

1. Choose **3 Integrations**, then select a provider by number or name. Add its URL,
   stable instance ID, account details and environment-variable or OS-key choice.
   You may leave the project/repository/course selection empty initially.
2. Choose **5 Save** to store those connection details and, if requested, enter the
   key in the masked prompt. The editor returns to the menu.
3. For a Google/Microsoft OAuth connection, choose **9** to sign in explicitly after
   saving; see [[Calendar connections]] for app registration and read-only consent.
   Then choose **7** for default scopes and select the provider and saved instance.
   This sends a read request using the saved credential and displays a numbered list.
4. Select an entry (multiple entries are supported for GitHub, Canvas and calendars). Review
   the current and proposed settings, then type `use` to stage the change.
   Choose **5 Save** again to apply it; use **6 Test saved connections** afterward.

| Provider | Listed choices | Staged selection |
| --- | --- | --- |
| Jira | Visible projects | A JQL filter such as `project = "TEAM"` |
| Agility | Accessible project scopes | `where: {"Scope": "Scope:123"}` |
| GitHub | Your accessible repositories with Issues enabled | Repository list; add or replace |
| Azure Boards | Accessible organization projects | Exact project name |
| Canvas | Your active course enrollments | Course IDs; add or replace, maximum 10 |
| Google/Microsoft | Accessible calendars for the signed-in account | Calendar IDs; add or replace, maximum 10 |

Jira and Agility selections replace their existing filter/where setting; review
the preview before accepting, then add any narrower conditions under Integrations.
Selecting a project does not enable a feature. Listing and testing require saved
settings: save or discard pending edits first. Neither action writes remote data.

The picker inspects one response and offers at most 50 choices. A full page or a
pagination indicator produces an incomplete-list notice; the CLI never follows
returned links. An empty list does not mean no projects exist. Permissions, token
scope and the first-page limit can hide choices. Use **3 Integrations** for manual
entry when a project is absent or listing is unavailable. Listing permission can
differ from task-reading permission: Azure's project list, for example, needs
project/profile read access. A successful listing is not a connection or task-access
test. [Azure project-list permissions](https://learn.microsoft.com/en-us/rest/api/azure/devops/core/projects/list?view=azure-devops-rest-7.1).

The picker uses the providers' documented read routes: [Jira Cloud projects](https://developer.atlassian.com/cloud/jira/platform/rest/v3/api-group-projects/#api-rest-api-3-project-search-get),
[Jira Data Center projects](https://developer.atlassian.com/server/jira/platform/rest/v10005/api-group-project/),
[Agility queries](https://docs.digital.ai/agility/docs/developerlibrary/tour-query-v-1),
[GitHub repositories](https://docs.github.com/en/rest/repos/repos#list-repositories-for-the-authenticated-user),
and [Canvas courses](https://developerdocs.instructure.com/services/canvas/resources/courses).

## Link one local Project, Course or Series

Connection defaults answer “what should this connection usually read?” A record
link answers “which remote source belongs to this local note?” Use
**8** to link a local Project, Course or Series:

1. Create the local Project, Course or Series note and save its connection under Integrations.
2. Choose **8**, select the local record, provider and saved instance.
3. List remote scopes and choose one, or enter its known exact ID/name manually.
4. Review the metadata changes, then type `apply` to update that record immediately
   with a local backup. Enter cancels. This action has its own preview/apply step;
   it is not waiting for the menu's configuration Save.

The record body, other records and connection defaults are preserved. Existing
bindings are shown before replacement, and concurrent note edits stop the apply.
An existing ticket/assignment identity can prevent an unsafe rebind; resolve the
identity conflict rather than moving the source implicitly. Feature activation is
separate. A Course can link to Canvas or a tracker; ordinary Projects use trackers.
A Series links to Google/Microsoft after selecting the account, calendar and remote
series. Discovery uses a requested UTC date window, so an unlisted series may need
a wider window or a known exact ID. Linking it does not create occurrence Meetings.

| Provider | Local binding properties |
| --- | --- |
| Jira | `jira_instance`, `jira_project_key` |
| Agility | `agility_instance`, `agility_scope_id` |
| GitHub | `github_instance`, `github_repository` |
| Azure | `azure_instance`, `azure_project` |
| Canvas | `canvas_instance`, `canvas_course_id` |
| Google/Microsoft Series | `calendar_provider`, `calendar_instance`, `calendar_id`, `calendar_series_id` |

For “sync this project/course,” the AI reads that binding and previews the selected
instance and scope. It does not substitute a connection default when a link is
missing. Project-specific linked-only updates read the associated notes' exact
ticket IDs; project discovery uses the selected project and assignment scope.
See [[INTEGRATIONS]] for tracker restrictions and [[Canvas LMS]] for multiple schools.
See [[Calendar connections]] for account sign-in and recurring meeting identities.

## Enter a key securely

You can use environment-variable references with no extra dependency. To paste a
key into a masked prompt and keep it in the OS credential store, install the optional
dependency into the same Python environment used by the notebook tools:

```text
fieldbook_core/.venv/Scripts/python -m pip install -r fieldbook_core/requirements-credentials.txt
fieldbook_core/.venv/Scripts/python tools/configure.py
```

On macOS/Linux use `fieldbook_core/.venv/bin/python` for both commands. See
[[Notebook tools]] to create the environment first. The editor asks for the secret
only when you save; it is never a command-line argument, displayed in a preview,
or saved to configuration, notes or backups. Calendar OAuth instead uses **9 Sign
in to Google or Microsoft calendar** after the connection is saved; type `signin`
to start browser/device consent. Its client secret and tokens stay in the OS store.
See [[Calendar connections]] for the one-time app registration.

Supported stores are macOS Keychain, Windows Credential Manager and Linux Secret
Service. The reader selects these OS backends directly; it refuses a missing or
locked backend and never falls back to a plaintext key file. Linux needs a running
Secret Service; headless machines can use environment variables. The OS may ask
for access/unlock approval. [Python keyring backends](https://keyring.readthedocs.io/en/stable/).

A saved key is tied to the absolute vault location, provider, instance ID and URL.
Copied/moved vaults and new devices therefore need their keys configured again.
Changing a connection's destination never silently reuses its saved key. Environment
mode uses the named variable; keyring mode reads only the saved credential, without
falling back to an old environment value. Keys are private to the runtime transport
and are not returned by an AI tool.

## Save, recovery and checks

Save validates the full proposed configuration and previews activation. It checks
for edits made while the editor was open, then backs up affected local files under
`.fieldbook/config-backups/` before applying. Customized kit resources remain in
place; merge candidates provide updated defaults. Changing a setup never rewrites
your notes. Backups are local recovery files, not copies of the OS credential store.
The backup's `restore.json` lists affected paths; `files/` keeps their original
bytes. A null entry identifies a newly created path with no original to restore.
Review those entries before restoring files manually, with both apps closed.

Changing only a saved API key reports a credential update without creating a
configuration backup. OS credential storage and file updates are separate actions:
if a later key or file save fails, an earlier saved key may remain in the OS store.
The editor reports this; cancelling remaining edits does not undo a saved key.

Restart AI assistant after saving so it discovers the newly active commands/skills.
Then use `/help`, or try one small read from the integration. Remote reads and local
note writes keep their own permission prompts. The configuration CLI itself is a
human-operated maintenance tool; the AI's scoped tools cannot change settings.

Read-only local configuration check:

```text
python tools/configure.py --check
python tools/manage-vault.py health
```

`--check` does not access a credential store or the network. It reports local
configuration issues; it does not certify that credentials are valid or that a
service is reachable.

## Test a saved connection

Use a live **read-only diagnostic** after saving a connection:

```text
python tools/configure.py --test all
python tools/configure.py --test jira --instance office
python tools/configure.py --test github --instance personal
python tools/configure.py --test canvas --instance school
python tools/configure.py --test google --instance personal
python tools/configure.py --test microsoft --instance work
python tools/configure.py --vault "path/to/vault" --test azure --instance office
```

Provider choices are `jira`, `agility`, `github`, `azure`, `canvas`, `google`, `microsoft`, or `all`.
Use `--instance` only with a named provider. Run with the notebook's Python
environment when the saved connection uses the optional OS credential store.
`--check` and `--test` are separate modes: the former stays entirely offline.

The editor also offers **Test saved connections**. Save or discard pending edits
before testing; diagnostics read saved files, not the staged preview. After a
successful Save, an optional test is offered with **No** as the default.

Tests use each saved environment-variable reference or OS credential and contact
the configured provider. They can test a connection while its Fieldbook feature is
disabled; they never enable it, change settings, create notes or save remote data.
`all` skips empty connections and untouched starter URLs. Selecting an unconfigured
provider explicitly reports that it could not be tested instead of claiming success.

Read the individual stages as well as the overall result. Diagnostics distinguish
local URL/credential problems, authenticated reads and selected-scope checks. A
successful account read does not prove access to a repository, Jira filter, Azure
project, Agility scope or Canvas course. Missing scope stays **not verified**; an
empty result may be a valid empty query, not proof that an expected item is visible.
Skipped and unknown stages do not count as successful checks.

The JSON summary includes `status`, verified/failed/not-verified/skipped counts and
each provider/instance's stages. For scripts, exit **0** means the required checks
passed (other unconfigured providers may be skipped), **1** means a failed check,
and **2** means incomplete/not verified, including a run where everything was
skipped. A provider can prove its protected read works while an optional account
identity remains unknown; inspect that stage before assuming which person it is.

An HTTP 401 generally calls for checking the credential and authentication method.
A 403 can reflect access, token scopes, organization policy or rate limiting; a
404 can mean a wrong path, missing resource or a resource hidden from that account.
Use the reported stage and the provider's access settings rather than treating
every failure as a bad key. For example, GitHub deliberately uses 404 for some
inaccessible private resources, and public issue reads alone do not prove a token
has private access. [GitHub API troubleshooting](https://docs.github.com/en/rest/using-the-rest-api/troubleshooting-the-rest-api).

The output contains sanitized results, never a key, Authorization header or raw
response body. Diagnostics issue only read requests; Agility query and Azure WIQL
POSTs are reads. They never attempt a write to test permissions. Successful reads
prove only the reported read operations worked: they cannot certify that a token
has no write permissions. Select the narrowest appropriate token permissions in
the provider's own settings. Detailed connection fields: [[INTEGRATIONS]],
[[Canvas LMS]] and [[Calendar connections]]. OAuth refresh can update its OS token
bundle during a live read; tests do not write vault files or remote calendar data.

The original script remains available for repeatable feature changes. Omit
`--apply` to preview, then add it to save:

```text
python tools/manage-vault.py configure --setups work --work-role people-manager --reviews on --jira on
python tools/manage-vault.py configure --github off --azure on --apply
python tools/manage-vault.py configure --setups personal,school --canvas on --apply
```

`--setups` replaces the enabled selection. Omitting it preserves that selection.
For the rest of the connection fields, use the guided editor or [[INTEGRATIONS]].

## Coverage and date fields

**14 Integration coverage** shows the saved configuration offline (staged edits
appear after Save). `python tools/configure.py --coverage` returns the same JSON;
it does not read credentials or contact services. See [[Integration coverage]].

In **3 Integrations**, Jira/Agility/Azure offer a dateFields object. Use meanings
`due`, `completed`, `start`, `target`, `review`, `available_from`, `closes_at` with
exact field references; see [[INTEGRATIONS#Explicit date mappings]]. Leave
an object empty for defaults, use an empty string to disable a specific mapping.
The editor validates field syntax and meanings before saving. It does not discover
field IDs or guess their meaning. Test after saving; empty samples/unreturned
fields are explicitly unverified. Azure now tests batch detail access after WIQL.

## Local vault tools

Choose **15 Vault tools** for **1 Back up now**, **2 Check vault**, **3 Compare
upgrade candidates**, **4 Create a record**, **5 Saved integration activity**,
**6 Selected file/email intake**, or **7 Follow-up review**. Save staged
configuration before entering this menu. Every creation has a concrete preview
and confirmation; checks and comparisons make no changes. All work is local.

Direct entry: `python tools/configure.py --vault-tools backup` (or `doctor`,
`compare`, `create`, `activity`, `intake`, `followups`). Add `--vault` with an
absolute path to operate on a different vault. To save the last connection test,
use the main menu in the same session: **6 → test → 15 → 5 → 2**. No receipt is
saved automatically by `--test`. See [[Vault tools]] and [[Selected intake]].

If `.venv` is missing, create that folder with Python as shown in [[Notebook tools]].
It is machine-specific and deliberately absent from the release ZIPs.

## Windows preview access errors

An error naming `...Temp/fieldbook-upgrade-.../vault/TaskNotes/Tasks` is inside
the temporary legacy-layout migration. The real vault is unchanged if preparation
stops before the final preview/backup/apply. Fieldbook handles Windows'
read-only attribute when removing an empty old directory. It never clears
attributes on note files, changes ACLs or recursively deletes a nonempty folder.
Other access denials still stop with the failing preparation phase and path.

If your normal temporary location is restricted, create a separate local working
folder you can write to, outside the vault, extracted release and backups. The
new CLI routes all preview and release copies through it:

```text
fieldbook_core\.venv\Scripts\python.exe tools/configure.py --upgrade --temp-dir "C:\Users\YOURNAME\FieldbookTemp"
```

Replace that path with your existing folder. Close Obsidian/AI assistant for the vault
and pause sync before retrying. Keep the original error if it still fails; a
read-only attribute, an open handle and an access-control rule require different
remedies. Do not run as administrator or broadly change folder permissions just
to get past an unexplained denial. This option is available in the new release,
not older ZIPs.

## Simple entry point and grouped menus

`python fieldbook.py` prepares the private Python environment and opens the grouped menu. Add `--install credentials` for OS credential storage or `--install intake` for PDF text. `--install calendar` is an alias for the credential dependency. Requirements are pinned and reused until they change. The launcher checks selected installed package versions and repairs missing or mismatched packages on the next launch.

- **Setup:** enabled setups/work role, features, preview, save.
- **Daily use:** create record, calendar meeting picker, follow-ups, manager cadence, selected intake, selected export.
- **Integrations:** guided setup, sign-in, tests, scoped Project/Course/Series links, coverage and saved activity.
- **Maintenance:** full backup, checks, upgrade, restore, candidate comparison.

`python tools/configure.py --menu` opens this menu in an already prepared environment; `--advanced` retains original numbers. Launcher forwarding: `python fieldbook.py -- --upgrade --vault "C:/Notes/Work" --from "C:/Downloads/fieldbook-1.0.0"`. All writes have their own preview; Setup selections stay staged until saved. Integrations remain remote read-only.

Grouped-menu report actions show readable rows and offer `details` for full JSON.
Direct command output and the advanced menu retain JSON for scripts. The grouped
navigation is read from `tools/menu-catalog.json`; new menu entries belong there.

## Guided onboarding and reviews (1.0)

Setup > Guided onboarding stages contexts, work role and new-task defaults, shows
activation/setting changes and asks for `save`. It then offers an existing/new
neutral self record and one first task, each with a separate preview. Reruns find
an existing self record; duplicate identities and conflicting relationships need
review. Cancelling after a confirmed step preserves that step. Direct route:
`python tools/configure.py --onboard --vault PATH`.

Daily use now starts with Daily review and Weekly review. Direct routes are
`--vault-tools daily` and `--vault-tools weekly`; they read local notes only, allow
up to three focus paths and optionally save a snapshot. Selected area never
silently imports global Inbox text. Integrations > Sync conflict preview reads one
selected Attachments JSON proposal and prints a field table; it changes nothing.
See [[Everyday workflow]] and [[Sync previews]].

Onboarding task defaults govern CLI/AI assistant capture. Manual templates keep their own values and customized TaskNotes defaults are preserved; onboarding states this before asking.

## AI assistants and optional MCP

Use Setup > AI assistants and optional MCP, or `python fieldbook.py -- --ai-setup`.
Choose one or more harness profiles, preview the adapter files and save. The default
uses Python scripts and shared instructions. MCP is opt-in, starts with the harness,
and defaults to local read-only tools. The same menu tests the server or displays
its launch command. See [[Using AI assistants]] and [[MCP setup]].
