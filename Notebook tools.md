# Notebook tools

Python 3.10+ performs local notebook operations through `tools/notebook.py`.
Paths are relative to the vault containing the script. There is no root parameter,
executable parameter or remote path. Local notebook tools do not call a network.
Optional integration operations read configured sources only. See [[Using AI assistants]].

## Install once

Run `python fieldbook.py` (Windows: `py fieldbook.py`). The launcher prepares the
Python environment under fieldbook_core/.venv. No AI plugins or MCP are needed.
See [[Using AI assistants]] for harness configuration. Tracker and Canvas reads
additionally use standalone Node.js 22+ adapters; install their dependency with
`npm install --omit=dev --ignore-scripts --no-save` run from the `fieldbook_core` folder. Local notebook
operations and calendar reads use Python. Sign-in uses the optional credentials
dependency group.

## Permissions

Run `python tools/notebook.py` with a JSON request on stdin. Logical notebook_*
names in workflows map to operations such as read, search, query, preview and write.
The current harness controls shell and file approvals; prompt behavior varies.
Local writes require --apply, a current hash and an allowed relative Markdown path.
Preview first and approve the actual change. The flag itself is not an approval UI.
Shared instructions cannot disable independent native editing tools. The scripts
never modify remote systems. Optional MCP uses the same core and defaults to local
read-only tools; see [[MCP setup]].

## Search examples

Tell the AI what you want; these are its underlying arguments:

```json
{"query":"APP-123","mode":"literal"}
{"query":"\\b(APP|SEC)-[0-9]+\\b","mode":"regex","filters":{"area":"work"}}
{"query":"Serch migraton","mode":"fuzzy"}
{"query":"reduce search latency","mode":"similar","filters":{"kind":"accomplishment"}}
```

Use regex for patterns, fuzzy for misspelled names/titles, similar for related
wording. Similar uses local TF-IDF word overlap; it is not embedding-based semantic
search and will miss synonyms with no shared words. Do not treat its scores as
proof of meaning, identity or relevance. Regex is line-based and runs in a separate
process with a two-second limit, including process startup. Literal/regex return
one representative line per matching file; read the file for other occurrences.

Structured query example:

```json
{"filters":{"kind":"task","type":"delivery","area":"work","status":"done","completed_from":"2026-01-01","completed_to":"2026-06-30"}}
```

Filters combine with AND and match exactly, ignoring case. kind matches a tag,
type a task subtype, relationship a person relationship (self/report/etc.),
project a projects link, person assignee/requester/attendees/
owner/stakeholders/manager/person. Date filters: due_from/to, completed_from/to,
modified_from. Ranges include both ends. Paths with duplicate short names remain
ambiguous; use a full relative link and inspect the result. Queries use real YAML,
keep scalar values as strings, reject duplicate keys, and report unsupported
anchors/aliases/tags or invalid dates instead of guessing. Follow next_offset for
more results. Warnings mean coverage is incomplete. Templates/examples are excluded
from note scans; use scope guides to search documentation/templates.

## Write rules and limits

Read gives a SHA-256 for the whole raw file, plus pages of text. Read all pages
before replacing a note. Write takes path, complete text and expected SHA-256;
expected missing creates a new file and refuses a collision. Existing BOM and
line endings are preserved. A stale hash fails without replacing the file. A
same-directory temporary file and atomic replacement reduce partial-write risk.
The last check cannot eliminate a simultaneous external edit between check and
replace; avoid editing the same note in Obsidian while approving an AI write.
Creation uses an exclusive hard link; filesystems without this support will fail
safely rather than overwrite. Test on your actual synced filesystem first.

Writes allow Inbox.md and Markdown under Tasks, Projects, People, Notes, Meetings,
Decisions, Reference, Research, Reports, Transcripts, Accomplishments, Opportunities, Items and Lists.
No deletes, moves, binary writes, settings edits or code execution. Finished review
notes are protected. Symlinks/reparse points, hard-linked files, absolute/parent
paths, case collisions, device names and hidden paths are rejected. Read exceptions
for exact guides, skills, commands and six config files support normal workflows;
credentials belong in environment variables or the OS credential store, not those
configuration files. [[Configuration CLI]] provides guided connection setup and masked key entry.

Limits: 1 MiB/file, 32 KiB/frontmatter, 10,000 files and 64 MiB per scan, bounded
results with pagination. Integration output is capped at 2 MiB; narrow large queries. No index persists; edits appear on the next scan.

These checks constrain the supplied tools, not the OS process or other installed
plugins. A user can change their config/code, and concurrent hostile filesystem
changes are outside the supported boundary. This is not an OS security sandbox.
Files read by the AI still go to its configured model provider even with web tools
disabled. Personal/work/school filters are not privacy boundaries.

## Manual use

Use `python tools/notebook.py read --path "Inbox.md"`, or send one JSON request
on stdin. See [[Using AI assistants]] for portable examples and approval behavior.
Maintenance uses the human-operated configuration menu. For local calendar exports,
see [[Calendar meetings]]; the bounded reader does not expand recurrence rules or
create contacts automatically.

## Human-operated local maintenance

[[Vault tools]] adds CLI menu 15 for standalone backup, vault checks, upgrade
comparison, guided record creation, saved integration activity, follow-up review
and selected email/PDF/image intake. These are terminal workflows with explicit
previews, not additional AI assistant shell permissions. Existing notebook tools still
own AI reads and writes. [[Selected intake]] explains optional dependencies and
which original files stay local.

## Field-level sync preview

`notebook_preview` accepts either the existing `text` diff or a `sync` proposal,
alongside path and current expected SHA. This uses the existing read-only preview
permission. `sync` supplies source, proposed mapped values, optional explicit_fields
and coverage; the tool reads the note's sync_baselines and scans for duplicate
identities. It makes no remote requests and writes no fields/baselines. Approved
edits still use notebook_write with its normal permission/diff and fresh SHA.
See [[Sync previews]] for classifications, source identity and baseline examples.

## Template provenance

`python fieldbook.py tool template_status` is a read-only inventory with optional
`filters`, `limit` and `offset`, using the same filters as query. It is also available
as `template_status` through optional MCP. Follow `next_offset` and resolve warnings
before treating an inventory as complete. See [[UPGRADING]] and `/migrate-records`
for reviewed, backed-up record refreshes.
