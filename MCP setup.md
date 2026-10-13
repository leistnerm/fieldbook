# Optional MCP setup

The standard Fieldbook setup needs no MCP. The included local stdio server is an
optional transport around the same Python tools. It has no separate SDK, listener,
port, hosted account or daemon to install. Prepare core Python dependencies with
`python fieldbook.py` first. This is separate from installing an AI application.

## Configure and test

1. Open **Setup > AI assistants and optional MCP** in the CLI.
2. Choose the harnesses to configure and answer yes to optional MCP.
3. Leave local writes and remote integration reads off unless you want those tools
   exposed. Enabled remote integrations still require their own saved connections.
4. Review the changed file list and save. Existing unrelated settings remain.
5. Choose **Check optional MCP server**. This tests initialization, tool discovery
   and a local read without contacting a model or remote integration.
6. Reopen the harness, approve its MCP trust prompt if appropriate, and confirm
   Fieldbook appears in its server/tools list. Request `today` or `overview`.

| Harness | Project configuration written by setup |
|---|---|
| OpenCode | `opencode.json`, `mcp.fieldbook` |
| Claude Code | `.mcp.json`, `mcpServers.fieldbook` |
| Codex | Managed `mcp_servers.fieldbook` block in `.codex/config.toml` |
| Cursor | `.cursor/mcp.json`, `mcpServers.fieldbook` |
| GitHub Copilot in VS Code | `.vscode/mcp.json`, `servers.fieldbook` |
| Gemini CLI | `.gemini/settings.json`, `mcpServers.fieldbook` |
| Other | `.fieldbook/mcp-connection.json` connection details to copy into the client |

The client launches the configured executable when it starts/connects the server
and closes it with the session. This is **harness-managed startup**, not operating
system login autostart. Some clients require workspace trust, reload or manual
server enablement. Fieldbook does not change global settings or bypass those checks.
For an unsupported client, select Show manual launch command and copy the command
and argument array into its stdio MCP settings. Keep each argument separate.

## Running directly

```text
python tools/ai-setup.py --check
python tools/mcp-server.py
```

The server waits for newline-delimited JSON-RPC on stdin; it is not an interactive
terminal menu. Do not expect a browser page. Optional arguments are `--allow-writes`
and `--allow-remote`. All protocol output goes to stdout; no startup text is mixed
into it. The server root is fixed to its containing vault, not selected by a model.

## Approval and disabling

MCP tool annotations are hints, not authorization. Configure the host to approve
local write calls; enabling the write tool does not itself create an approval UI.
The server still enforces permitted note paths, protected files and expected hashes.
It exposes no remote write operation. Host shell tools remain independently governed.

To disable MCP, rerun AI setup and answer no. It removes only the managed Fieldbook
server entries, preserving other servers and settings. Restart the client to stop
an already-running connection. Select no assistants to remove unmodified generated
instruction adapters as well. Customized files cause a visible conflict rather than
being overwritten. Plain Python workflows remain available.

Client connection formats and controls: [OpenCode](https://opencode.ai/docs/mcp-servers/),
[Claude Code](https://code.claude.com/docs/en/mcp),
[Codex](https://developers.openai.com/codex/mcp),
[Cursor](https://cursor.com/docs/context/mcp),
[VS Code](https://code.visualstudio.com/docs/copilot/customization/mcp-servers),
[Gemini CLI](https://geminicli.com/docs/tools/mcp-server/).
