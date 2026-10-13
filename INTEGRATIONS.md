# Read-only tracker integrations

For help getting credentials, run `python tools/configure.py --credential-guide`
and select Jira, Agility, GitHub or Azure. Main-menu **11** offers the same steps,
official links, read permissions and Fieldbook field mapping. Then use guided
setup to configure, save, select scopes and test the connection. Guides do not
request secrets, create tokens or verify access themselves.

Use `python tools/configure.py` for guided connection details, project selection,
feature toggles and connection tests, including optional masked key entry. All seven
direct integrations share this editor. See [[Configuration CLI]]. Google/Microsoft
calendars use [[Calendar connections]]. Canvas LMS uses
the separate school workflow in [[Canvas LMS]]; the four trackers below work in
every setup.

Jira, Digital.ai Agility, GitHub Issues and Azure Boards work in **every setup**:
core, personal, work, school, or any combination. Each is optional and off initially.
`/sync` reads remote items and previews changes to Fieldbook. It updates linked
local notes by default and can propose missing tasks when requested.
`/tracker-draft` prepares changes for you to enter manually. No command creates,
comments on, assigns, closes, or transitions remote items.

## Quick start

1. Use menu **3 Integrations** in `python tools/configure.py`, or fill the matching
   `fieldbook_core/<provider>.json` configuration below. Each contains
   an instances list; use a unique stable ID per connection and never reuse it for
   a different host/organization. No secrets belong in these files.
2. Use the guided editor's OS credential store, or put the token in the environment
   variable named by tokenVar. Restart the app
   that launches AI assistant after changing its environment. Do not paste tokens into
   notes or commands shared with the AI. Use read-only credentials where supported.
   Save the connection, then choose menu **7** for default remote scopes to
   list choices from the provider. Review the proposed scope, type `use`, and Save
   again. Jira/Agility replace the existing filter; GitHub can add or replace
   repositories. The bounded first-page picker may omit a desired project; manual
   entry stays available. Listing does not prove issue access or enable a feature.
3. Enable only the providers you use. Run from the vault root, preview first, then
   add `--apply` (use python3 on macOS/Linux):

```text
python tools/manage-vault.py configure --github on --azure on
python tools/manage-vault.py configure --github on --azure on --apply
```

4. Test the saved connection with `python tools/configure.py --test github --instance personal`
   (substitute your provider and instance), or `--test all`. Inspect scope stages;
   a skipped/unknown scope has not passed. Tests can run before enabling a feature,
   and do not change its setting. See [[Configuration CLI]] for result meanings.
5. Try `/github-sync linked` or `/azure-sync linked`. For discovery, use mine or
   all with configured repositories/project. Add “also create missing tasks” when
   you want proposed local tasks. Review the local plan before approving writes.
6. For team scope, set up self/report person records as shown below. `/help /sync`
   explains the installed workflow without running it.

Run tracker_pull through `tools/notebook.py`. Tracker/Canvas reads additionally
need Node.js 22+ and `npm install --omit=dev --ignore-scripts --no-save` run from the `fieldbook_core` folder.
No AI plugin is installed. All starters ship the connection files, disabled and
without credentials. OS storage uses the optional Python keyring dependency.

## Connection checks

`python tools/configure.py --test all` checks saved non-placeholder connections;
`--test agility --instance office` selects one provider/instance. Jira, Agility,
GitHub and Azure are tested independently of their feature toggles. The diagnostic
uses your saved environment or OS credential, performs bounded reads, and prints
sanitized stage results without saving remote data or changing local files.
`python tools/configure.py --check` remains an offline settings check.

Authentication and access to selected data are separate. Check the repository,
project/filter or scope stage before assuming sync is ready. A missing configured
scope stays unverified. HTTP 401, 403 and 404 can have different causes; an inaccessible
resource may be hidden as 404. No diagnostic tries a remote mutation or claims that
a successful read proves the credential lacks write permission. Review the actual
token restrictions in the provider. A Jira account-profile check can also need
user-read scopes beyond issue access; one endpoint's denial does not by itself
invalidate every read. [Jira current-user permissions](https://developer.atlassian.com/cloud/jira/platform/rest/v3/api-group-myself/#api-rest-api-3-myself-get).

For an actual first sync, choose one known item or a narrow configured selection
and review the returned identity and local plan. A connection check is not a full
sync, an exhaustive permission audit or proof of access to every linked item.

## Link a Fieldbook Project

In the configuration CLI, **8 Link a local Project, Course or Meeting Series** selects a local note,
one saved provider instance and one remote scope. Preview the metadata and type
`apply`; the CLI backs up and updates just that note's binding. It preserves the
body and connection defaults. You can choose a listed remote scope or enter its
known ID/name manually. The exact properties are:

- Jira: `jira_instance: office` and `jira_project_key: TEAM`.
- Agility: `agility_instance: office` and `agility_scope_id: "Scope:123"`.
- GitHub: `github_instance: personal` and `github_repository: owner/repository`.
- Azure: `azure_instance: office` and `azure_project: Exact project name`.

Ask `/sync jira this project, only mine` or name the Project in a normal sync
request. The AI confirms the local record and binding. For mine/team/all discovery,
the tool's `projectScope` selects that project for this read, leaving saved settings
and credential bindings alone. Jira uses only the bound project's JQL selection;
Agility retains other configured where conditions, GitHub retains label filters,
and Azure retains its WHERE filter. `projectScope` cannot combine with a separate
query. Review those restrictions before treating the result as complete.

For linked-only updates, the AI collects exact tracker IDs from notes associated
with that local Project, then reads those IDs. It does not use projectScope or
broaden to every linked item in the vault. Missing/ambiguous bindings require a
choice; multiple linked providers do not mean all should run. Ticket-bearing
Project notes cannot silently change their instance identity. Remote writes remain
unavailable, and creation of missing local tasks still needs an accepted plan.

## GitHub Issues (`github`)

Edit `fieldbook_core/github.json`. For GitHub.com use:

```json
{
  "instances": [{
    "id": "personal",
    "baseUrl": "https://api.github.com",
    "apiVersion": "2026-03-10",
    "tokenVar": "GITHUB_TOKEN",
    "repositories": ["example-org/example-project"],
    "login": "",
    "labels": [],
    "statusMap": {"open": "backlog"},
    "resolutionMap": {"completed": "done", "not_planned": "dropped", "duplicate": "dropped"}
  }]
}
```

The mappings above are examples to review, not bundled defaults. Use a fine-grained
personal access token restricted to the selected repositories with **Issues: Read**
(and GitHub's required metadata access). Token access never exceeds the account's
repository access; organization approval/SSO may also apply. For private repositories,
select them explicitly. This adapter does not need Contents write or Projects access.

Repositories are mandatory for mine/team/all; there is no implicit account-wide
scan. Optional labels narrow those scopes; linked reads ignore discovery filters
and fetch the exact repository-qualified IDs. All scopes include open and closed
issues so existing local links can be reconciled. Pull requests returned by the
Issues API are excluded. An explicitly linked PR is reported as skipped.

For mine, a mapped self person supplies the login. Otherwise use configured login,
or the authenticated user returned by GitHub. If a configured login and self
mapping disagree, resolve the conflict first. Exact GitHub usernames are required;
display names do not identify accounts. GitHub Enterprise can use its HTTPS REST
API base (usually https://HOST/api/v3) and supported apiVersion; verify with your
server before relying on it. GitHub.com is the documented default.

Returned fields include title, body, open/closed state, closure reason, assignees,
labels and milestone context. A milestone deadline is not an issue deadline.
Closed does not necessarily mean completed: the local preview uses resolutionMap
for completed/not_planned/duplicate and asks about unknown reasons. GitHub Projects,
PR synchronization, full comments and code/repository content are outside this adapter.

## Azure Boards (`azure`)

Edit `fieldbook_core/azure.json`:

```json
{
  "instances": [{
    "id": "office",
    "baseUrl": "https://dev.azure.com/YOUR-ORGANIZATION",
    "tokenVar": "AZURE_TOKEN",
    "project": "Your Project",
    "filter": "[System.WorkItemType] IN ('Task', 'Bug', 'User Story')",
    "dueField": "",
    "completionField": "",
    "statusMap": {}
  }]
}
```

Use an Azure DevOps PAT with **Work Items: Read** only. The adapter authenticates
with that PAT over HTTPS and uses REST API 7.1. The base URL includes the organization,
not the project. Configure one instance ID per organization. A project is required
for mine/team/all; the optional filter is a WHERE expression, without SELECT or
ORDER BY. Adapt item types and state mappings to your actual process. Azure DevOps
Services is the documented target; older Server API versions are not implemented.

The WIQL POST selects matching IDs; workitemsbatch POST reads up to 200 records per
batch. Both are read operations. No work-item create/update/delete endpoint is
available. Linked scope reads exact IDs within the organization and ignores the
discovery project/filter, so a moved item is not silently hidden.

For mine, use the self person mapping when supplied; otherwise WIQL uses @Me.
For team, store the exact Assigned To uniqueName (usually email/UPN) on each person,
not their display name. Fields include title, state, assignee, type, project, area
and iteration. Descriptions are returned as source HTML, never executed. Optional
dueField/completionField must be real field reference names from your process,
e.g. Microsoft.VSTS.Common.ClosedDate if it exists and means the intended date.
Unconfigured or missing dates are unavailable and never erase local dates. A
closed date is only completion evidence after the workflow state is understood.

## Jira (`jira`) and Digital.ai Agility (`agility`)

Jira uses `fieldbook_core/jira.json`, tokenVar JIRA_*, and an HTTPS base URL including
any application context. Cloud requires email plus an API token (flavor cloud);
Data Center uses a personal access token (flavor server). Cloud reads
/rest/api/3/search/jql with continuation tokens; Data Center reads /rest/api/2/search.
Use your admin-approved API base for gateways/scoped tokens. Optional filter is
JQL without ORDER BY, e.g. `project = APP`; it is mandatory for all scope.

Agility uses `fieldbook_core/agility.json`, tokenVar AGILITY_*, an HTTPS instance URL,
and memberId such as Member:123 (or a mapped self person). Its POST /query.v1 is
read only. It queries Workitem with paging; portfolio-specific schemas and custom
date fields require explicit mappings (below); portfolio hierarchy traversal is outside this adapter. Optional where is a mapping such
as `{"Scope":"Scope:1000"}` and is mandatory for all. Set statusMap to actual
workflow labels. Both providers now work in any setup; removing work leaves their
feature flags unchanged. Never infer that Closed means done rather than cancelled.

## Person relationships and team scope

Yes: **relationship self means you; relationship report means your direct report**.
There is no people-manager setup requirement for tracker scope. Person is the
neutral default; Professional contact and Direct report are optional layouts of
the same person record. Direct report starts with report; set self on your own
Person note. Templates do not otherwise determine tracker membership. Manager links are
optional context; a team name, manager link alone or repository membership does
not select someone for team sync. Only person-tagged notes with current or blank
status participate. Other statuses (including former) are excluded. Update a
person's relationship/status when the reporting relationship changes.

Example self note (People/Me.md):

```yaml
---
tags: [person]
status: current
relationship: self
usernames:
  - "github:personal: your-login"
  - "azure:office: you@example.com"
  - "jira:office: your-account-id"
  - "agility:office: Member:123"
---
```

Example report note (People/Alex.md):

```yaml
---
tags: [person]
status: current
relationship: report
usernames:
  - "github:personal: alex-login"
  - "azure:office: alex@example.com"
  - "jira:office: alex-account-id"
  - "agility:office: Member:456"
---
```

These are illustrative accounts, not real contacts. Each username has the label
provider:instance, followed by `: ` and the exact account. Include only the
providers/instances you use. Jira Cloud uses accountId; Data Center uses username;
Agility uses Member:number; GitHub uses login; Azure uses Assigned To uniqueName.
Do not store access tokens in these fields.

Team sync requires exactly one current self note and at least one current report.
Every selected person needs one mapping for the chosen provider/instance. Missing,
duplicate or conflicting mappings stop before requests; no report is silently
omitted. The result names the roster used. An explicitly requested account list
can override automatic report selection; the AI must show that different scope.
Mine can fall back to the configured/authenticated user when no self mapping exists.

## Local links and scopes

Any tagged note can carry a source link; include only the providers it uses:

```yaml
jira: APP-123
jira_instance: office
agility: S-01001
agility_instance: office
github: "example-org/example-project#123"
github_instance: personal
azure: "456"
azure_instance: office
```

Identity is provider + instance + ID, never a title. GitHub includes owner/repository
to distinguish issue #123 in different repositories. Azure IDs are unique within
an organization; use a separate instance ID for each organization. Legacy links
without an instance require explicit mapping before bulk sync. If sources describe
the same work, keep one note where useful and resolve conflicting fields explicitly.

| Scope | Reads |
|---|---|
| linked | Exact IDs from all tagged local note types for the instance; ignores discovery filters |
| mine | Self person identity, or configured/authenticated user; discovery filters apply |
| team | Self plus current relationship report records with exact identities; discovery filters apply |
| all | Configured repositories (GitHub), project (Azure), or explicit filter (Jira/Agility) |

Optional Obsidian/TaskNotes text properties are provider and provider_instance
(e.g. github / github_instance). They need not exist on every task; the starter
keeps its task form small. AI saves can add these properties to linked notes.
New tasks inherit their local project area, then your requested/default area, or
leave it blank. A GitHub/Azure/Jira/Agility task is not automatically work-related.

## Local changes and limits

The AI shows a numbered update/create plan. Your body text, priorities, scheduled
dates and goals are preserved unless included explicitly. Duplicate links are
conflicts. If a non-task note already links a ticket, the AI asks before proposing
a separate task. Final reviews and recurrence state are protected. Repeat sync
with unchanged data adds no notes or log entries. Missing/inaccessible results
never imply deletion or completion. Saving still uses notebook_write permissions.

Default cap: 500 items, configurable from 1 to 5000. Truncated output is labeled
and cannot support complete-coverage claims. Narrow the scope or raise the cap.
Failures, malformed data, missing Azure batch IDs and stalled pagination return
no usable partial result. Requests time out after 30 seconds and never follow
redirects carrying credentials. No background polling is enabled. The HTTP layer
allows only the implemented read routes, including Agility/Azure query POSTs.

This is an AI-reviewed local editing workflow, not an unattended sync engine.
Fixture tests do not verify your live authentication, custom fields or mappings;
start with linked/mine and a small reviewed plan in your own environment.

## Optional standalone read command

The Python entry point is recommended. The underlying read-only tracker adapter
can also be run directly with Node.js 22+ after configuring access:

```text
node fieldbook_core/scripts/tracker-pull.mjs --provider github --instance personal --scope mine
node fieldbook_core/scripts/tracker-pull.mjs --provider azure --instance office --scope team
node fieldbook_core/scripts/tracker-pull.mjs --provider github --instance personal --scope linked --ids "owner/repo#123,owner/repo#124"
node fieldbook_core/scripts/tracker-pull.mjs --provider azure --instance office --scope linked --ids "456,457"
node fieldbook_core/scripts/tracker-pull.mjs --provider jira --instance office --scope linked
node fieldbook_core/scripts/tracker-pull.mjs --provider agility --instance office --scope mine
```

Omit --members for automatic self/report scope. --members is an explicit comma-separated
alternative list of confirmed report accounts. --query overrides Jira JQL or Azure
WHERE for the call; GitHub/Agility filters come from config. --ids applies only to
linked scope. The script prints JSON, never writes files, and has no approval UI;
the person invoking it authorizes the read.

## Manual-entry drafts

`/tracker-draft github owner/repo#123 explain the blocker` or
`/tracker-draft azure 456 propose acceptance criteria` produces a paste-ready
proposal and fields checklist. Jira and Agility use the same skill. No credential
or enabled integration is needed to draft from supplied/local facts. A draft is
not a posted change. Confirm posting and provide the real ID before recording a
new local link. Fieldbook never submits the proposal to the remote tracker.

## API references

- [GitHub repository issues and read permissions](https://docs.github.com/en/rest/issues/issues#list-repository-issues)
- [Azure WIQL read query](https://learn.microsoft.com/en-us/rest/api/azure/devops/wit/wiql/query-by-wiql?view=azure-devops-rest-7.1)
- [Azure WIQL syntax](https://learn.microsoft.com/en-us/azure/devops/boards/queries/wiql-syntax?view=azure-devops)
- [Azure batch reads and Work Items read scope](https://learn.microsoft.com/en-us/rest/api/azure/devops/wit/work-items/get-work-items-batch?view=azure-devops-rest-7.1)
- [Jira Cloud search](https://developer.atlassian.com/cloud/jira/platform/rest/v3/api-group-issue-search/)
- [Jira Data Center REST](https://docs.atlassian.com/software/jira/docs/api/REST/1000.1000.0/)
- [Agility query endpoint](https://docs.digital.ai/agility/docs/developerlibrary/query)
- [Agility query syntax and paging](https://docs.digital.ai/agility/docs/developerlibrary/tour-query-v-1)
- [Agility authentication](https://docs.digital.ai/agility/docs/developerlibrary/api-authentication)

## Calendars, Canvas and other connections

Fieldbook includes `/meeting` and the read-only `notebook_calendar` preview for
local ICS files under Attachments. Pasted event details also work. Selected
events can become Meeting notes through the normal local preview/write approval;
missing people are created only when specifically selected, never as a bulk
invitation/class roster. See [[Calendar meetings]] for bounds and recurrence limits.

Live Google Calendar and Microsoft Graph calendar reads are optional in every
setup. The same CLI configures, signs in, selects calendars, tests access and links
local Series records. `/meeting` prepares selected occurrences through
`calendar_pull`; linking a Series does not create meetings automatically. M365/
Outlook.com uses Graph regardless of the Outlook client; client-only/PST calendars
can use ICS exports. No Gmail/Outlook mailbox permission or remote event mutation
is requested. See [[Calendar connections]]. Mailbox readers, Zotero, cloud-document
reads and GitHub pull-request evidence remain unimplemented.

The optional [[Canvas LMS]] adapter reads selected courses, signed-in-user assignment
deadlines, announcements and calendar entries. /canvas-sync previews local school
records while preserving study notes/checklists; no classmate roster is imported.
It accepts your own permitted access token or an institution-approved OAuth access
token, without an OAuth authorization/refresh flow. The guided CLI supports its URL,
course scope and credential reference alongside the four tracker connections.

See [[Optional functionality]] for the prioritized roadmap, official support
matrix, exact permission choices and local-content preservation requirements.

## Explicit date mappings

In CLI menu **3 Integrations**, edit the connection's **dateFields** JSON object.
Map a meaning to an exact readable field reference; the adapter requests that field
and returns a typed fact. This does not write to the service or change local notes.

| Meaning | Use | Local handling |
|---|---|---|
| due | Actual item deadline | Propose task due only after review; retain exact time/zone in the body |
| completed | Source completion/resolution date | Also requires a reviewed status/resolution mapping |
| start | Source start date | Source context; does not replace your scheduled work day |
| target | Target, release or timebox end | Context, never silently due |
| review | Source review/check-in date | Context or a chosen follow-up |
| available_from | Availability opens | Separate from deadline |
| closes_at | Access/submission closes | Separate from deadline |

Examples below show syntax, not guaranteed fields in your installation:

```json
{"dateFields":{"due":"customfield_12345","target":"customfield_12346"}}
```

Jira maps due to `duedate` and completed to `resolutiondate` by default. Override
individual meanings with exact IDs (not display labels). Use an empty string to
disable a meaning, e.g. `{"due":""}`. An empty object keeps the defaults.

```json
{"dateFields":{"target":"Timebox.EndDate"}}
```

Agility has no default dates. Use your instance's scalar date attributes supported
by the Workitem query. Confirm with your administrator/metadata; not every subtype
has the same attributes. A timebox end must be labeled target, not due.

```json
{"dateFields":{"completed":"Microsoft.VSTS.Common.ClosedDate","target":"Custom.TargetDate"}}
```

Azure uses exact process field references. Existing dueField/completionField still
work; dateFields overrides those meanings when supplied. No iteration dates are
inferred. GitHub milestone targets stay context; GitHub Projects custom dates are
not added by this release. Canvas and calendars retain their provider date types.

Save, then choose **6 Test saved connections**. Jira/Agility sample reads request
mapped fields; Azure queries a sample ID and reads its title/state/mapped fields
through workitemsbatch. Diagnostics distinguish present, unset, not returned and
invalid values without printing values. Empty results cannot prove field access.
They do not discover every schema or establish the business meaning of a field.
An inaccessible field can fail the request; remove/correct its mapping and retry.

Every mapped result includes a source field and meaning. Null, absent and invalid
values are distinct; none authorize clearing local dates. Invalid formats are
withheld from usable date facts. Timestamps without a timezone remain flagged;
no timezone is invented. A sync previews local changes and preserves local plans.

Field references: [Jira fields](https://developer.atlassian.com/cloud/jira/platform/rest/v3/api-group-issue-fields/),
[Agility attributes](https://docs.digital.ai/agility/docs/developerlibrary/attributes),
[Azure batch reads](https://learn.microsoft.com/en-us/rest/api/azure/devops/wit/work-items/get-work-items-batch?view=azure-devops-rest-7.1).
See [[Integration coverage]] for supported scopes, limits and freshness.

## Review local conflicts before saving (1.0)

A successful read is not permission to overwrite a local change. All sync skills
now use the deterministic field comparison in notebook_preview. A reviewed source
baseline distinguishes remote changes from local overrides and conflicting edits.
First-time/ambiguous records require a choice. Baselines live in the note and are
saved only with an approved local edit. Missing/null or inaccessible values never
clear, close or delete records. See [[Sync previews]]. Remote writes remain excluded.
