# Using AI assistants

Fieldbook works without AI. When you want AI help, the default is **shared
instructions plus local Python scripts**. No AI plugins, MCP connection or
background service is required. Obsidian plugins are separate notebook features.

## Choose assistants

Run `python fieldbook.py` (Windows: `py fieldbook.py`) and choose **Setup > AI
assistants and optional MCP**. Select one or more profiles:

| Profile | Shared instruction entry point |
|---|---|
| OpenCode | AGENTS.md; built-in shell and read tools; no custom plugins |
| Claude Code | CLAUDE.md imports AGENTS.md |
| Codex | AGENTS.md |
| Cursor | Project rule referencing AGENTS.md |
| GitHub Copilot in VS Code | Repository instructions referencing AGENTS.md |
| Gemini CLI | GEMINI.md imports AGENTS.md |
| Other | Open AGENTS.md and this guide manually in an assistant with local command execution |

These are project-local configuration adapters. They do not install the assistants,
extensions, accounts or subscriptions. Use an agent-capable mode that can execute
local commands. A chat-only interface can help draft text but cannot run these tools.
Setup preserves unrelated settings and stops on conflicting custom adapter content.
Configuration backups are saved locally before changes. Rerun setup after moving a
vault to refresh optional MCP executable paths.

## First session

1. Open the vault root in your chosen assistant. Allow workspace trust only as
   appropriate for that application.
2. Ask: “Read AGENTS.md, then use Fieldbook's Python tools to summarize my tasks.”
3. Check that it uses `tools/notebook.py`, not direct replacement of note files.
4. Ask it to preview one small note edit. Approve or decline through the host.
5. Verify the note changes only when approved and that stale hashes are rejected.

Instructions guide the assistant; they are not a security sandbox. Native shell,
file access and approval prompts remain controlled by the selected harness and
your settings. The supplied OpenCode profile asks for shell/edit operations; other
harnesses retain their existing approval settings. No profile grants blanket shell
approval. Do not bypass a workplace restriction or a denied action.

## Portable commands

Use the prepared Python executable (`fieldbook_core/.venv/bin/python` on macOS/Linux,
`fieldbook_core\.venv\Scripts\python.exe` on Windows), or Python with the core
requirements installed. The launcher can prepare it with `python fieldbook.py`.
The `tool` shortcut below selects that environment without installing packages.

```text
python fieldbook.py tool today
python fieldbook.py tool overview
python fieldbook.py tool read --path "Inbox.md"
python fieldbook.py tool help --json '{"topic":"weekly review"}'
```

The last example uses POSIX shell quoting. For Windows or complex requests, send
one JSON object on stdin using the harness's process API. With no positional
operation, the request includes `operation`. No arbitrary root path or shell code
is accepted by the tool itself.

```json
{"operation":"search","query":"meeting","mode":"literal"}
```

Read the whole existing note, then preview a replacement with `operation: preview`,
its relative `path`, complete `text`, and `expected` SHA-256. Use `expected: missing`
for a new note. After approval, use the same data with `operation: write` and
`python fieldbook.py tool --apply`. A stale hash fails without overwriting the note.
The flag expresses intent; it cannot independently verify human approval.

Logical names like `notebook_read` in skills mean the script's `read` operation.
Use `help` to find installed workflows in `fieldbook_core/commands` and
`fieldbook_core/skills`. `/daily-review`, `/people`, and similar guide examples are
portable workflow names. If the harness does not register them as slash commands,
ask in plain language: “Run Fieldbook's daily-review workflow.”

## Integration reads

`tracker_pull`, `canvas_pull` and `calendar_pull` use the same Python entry point.
Configure and test accounts through the human-operated configuration CLI first.
The tools never change remote systems. Local sync changes require separate previews.

Local notebook tools and calendar readers use Python. Tracker and Canvas adapters
also need Node.js 22+ and `npm install --omit=dev --ignore-scripts --no-save` run from the `fieldbook_core` folder.
This installs a YAML parsing dependency for standalone readers, not an AI plugin.
Calendar sign-in uses `python fieldbook.py --install credentials`.

## Optional MCP

Enable MCP only if useful. The same tools can be exposed to supported clients
without changing the notebook. It defaults to local reads; writes and remote reads
are separate explicit choices. See [[MCP setup]].

## Official harness documentation

- [OpenCode rules](https://opencode.ai/docs/rules/) and [permissions](https://opencode.ai/docs/permissions/)
- [Claude Code shared instructions](https://code.claude.com/docs/en/memory)
- [Codex AGENTS.md](https://developers.openai.com/codex/guides/agents-md)
- [Cursor rules](https://cursor.com/docs/context/rules)
- [Copilot repository instructions](https://docs.github.com/en/copilot/customizing-copilot/adding-repository-custom-instructions-for-github-copilot)
- [Gemini CLI instructions](https://geminicli.com/docs/cli/gemini-md/)

## Refresh older records

Ask “Run Fieldbook's record-migration workflow for five existing people; preview
only.” `/migrate-records` is the shorthand. This works without plugins or MCP, uses
template name/version metadata, and requires a verified backup and approved diffs
before each changed batch. See [[UPGRADING]] for preservation and recovery details.
