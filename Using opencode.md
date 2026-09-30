# Using opencode

How to get more out of the assistant. It is written for opencode Desktop on
Windows. Menu names and buttons change between versions, so where this says
"settings" or "the prompt box", look for the nearest equivalent, and check
opencode.ai/docs for anything that has moved. Install: [[SETUP]]. Commands
and how-tos: [[Cheat Sheet]]. What each part does: [[Features]].

## The basics

- **Open the vault folder** as the project. opencode reads `AGENTS.md` there
  automatically; that file is how it knows the vault's folders, fields and
  rules.
- **Type in the prompt box** in plain words, or start with `/` to pick a
  command from the list (the files in `.opencode/commands/`).
- **Attach a note** by typing `@` and part of its name, so it reads that exact
  file instead of guessing.
- **Permission prompts:** when opencode wants to do something the config
  doesn't already allow, it asks. Read what it wants to run, then allow once,
  allow always, or deny. Prefer allow once until you trust the pattern.
- **One topic per session.** A long session gets slower and forgets earlier
  details. Start a new session for a new topic; the notes hold the state, not
  the chat.
- **Undo:** everything opencode changes is committed to git, so ask "what did
  you just change?" and "put back the previous version of X". Never rely on
  the chat's undo alone.
- **Do not use `/share`.** It uploads the conversation, which can name people,
  to a public link.

## Plain requests that work well

You don't need a command for everything:
- "Alice's hire date is 2021-03-01."
- "What's blocked, and on whom?"
- "Summarize the decisions from the last three Platform sync meetings."
- "Which tasks have I not touched in a month?"
- "Rewrite the Notes on this meeting note as bullets. Don't change anything
  else."

Be specific about scope ("only this note"), and ask it to show a draft before
it writes when the change is large.

## Make your own command

A command is one markdown file in `.opencode/commands/`. The file name is the
command name.

1. Create `.opencode/commands/standup.md`:

   ```markdown
   ---
   description: Draft my standup from yesterday's log lines (/standup)
   ---
   Today is !`powershell -NoProfile -Command "Get-Date -Format yyyy-MM-dd"`.

   Read the task notes in TaskNotes/Tasks with a Log line dated yesterday or
   today. Draft three short lines: done, doing, blocked. Cite each as a
   [[link]]. Show it; don't edit any note.
   ```

2. Restart opencode (or reopen the vault) so it appears in the `/` list.
3. Use it: `/standup`.

What a command file can contain:
- `description:` in the front block, shown in the `/` list.
- `$ARGUMENTS` for everything typed after the command, or `$1`, `$2` for the
  first and second words (`/log runbook waiting on IT` → `$1` is `runbook`).
- `` !`command` `` runs a shell command and pastes its output in. Each one is
  a permission check, so keep them to harmless reads like the date.
- `@path/to/note.md` pastes that file's contents in.

Look at `.opencode/commands/log.md` (short) and `review.md` (long) for models.
Good commands say what to read, what to produce, what never to touch, and
"show a draft and wait for my yes" before writing. Bad ones say "be helpful".

## Make it follow your habits

Rules that apply every time belong in `AGENTS.local.md` (your own file; kit
updates never touch it), not in each prompt and not in `AGENTS.md`, which
updates replace. Add a
line ("Always file meeting notes for the Platform team under the Platform
project") and it holds from the next session. Keep the file short and direct;
long, chatty rules get followed less well. If you want a rule for one
situation only, put it in a command instead.

## Control what it may do

`opencode.json` has a `permission` block: `allow`, `ask` or `deny` per tool
(read, edit, bash, and so on), with wildcard patterns for shell commands. The
last matching rule wins. To let it run a script without asking, add an allow
line for that exact command; keep the patterns narrow. Edits to
`opencode.json`, `AGENTS.md` and `.opencode/` are set to ask, so it can't
loosen its own rules unseen.

## Going further

- **Plugins** (`.opencode/plugins/`) run code on events, such as after each
  reply. The kit's `auto-people.js` and `auto-commit.js` are examples; delete a
  file to turn it off.
- **Custom agents** (`.opencode/agents/`) are named personas with their own
  instructions, model and tool limits, such as a read-only "reviewer".
- **Other models:** any OpenAI-compatible endpoint, or a hosted provider, can
  be added in `opencode.json` or through the provider settings. A hosted
  provider sends your notes to that company, so check your organization's
  rules first.
- **Everything else** (MCP servers, themes, keybindings): opencode.ai/docs.
  Web access is denied in this kit; loosen it only on purpose.

## When it goes wrong

- **It ignored a rule:** name the rule and the file ("AGENTS.md says
  ISO dates"); if it keeps happening, the rule is too vague or buried, so
  reword it or move it up.
- **It changed something you didn't ask for:** say what you expected, then
  restore from git and reword the request with tighter scope.
- **A command isn't in the list:** check the file is in
  `.opencode/commands/`, ends in `.md`, and has the `---` front block, then
  restart.
- **A model gives shaky answers:** small local models follow long rules less
  reliably; use a stronger model for reviews and transcripts.
