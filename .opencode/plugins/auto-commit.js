// Commits the vault to git after each opencode reply, as "opencode: <files>",
// so opencode's edits are separate from Obsidian Git's timed "vault:" commits.
// When you send a prompt, your pending edits are committed first as "vault: …".
// Plain code, no model calls. Does nothing if the vault isn't a git repo.
// Delete this file to disable.
import { execFile } from "node:child_process"
import { promisify } from "node:util"

const run = promisify(execFile)
const MAX_LISTED = 3

async function git(directory, ...args) {
  const { stdout } = await run("git", ["-C", directory, ...args], { windowsHide: true })
  return stdout
}

async function commit(directory, prefix) {
  try {
    await git(directory, "rev-parse", "--git-dir")
  } catch {
    return null // not a repo
  }
  await git(directory, "add", "-A")
  const changed = (await git(directory, "diff", "--cached", "--name-only", "-z"))
    .split("\0")
    .filter(Boolean)
  if (!changed.length) return null
  const names = changed.map((f) => f.split("/").pop().replace(/\.md$/, ""))
  const more = names.length > MAX_LISTED ? ` +${names.length - MAX_LISTED} more` : ""
  const message = `${prefix}: ${names.slice(0, MAX_LISTED).join(", ")}${more}`
  await git(directory, "commit", "-q", "-m", message)
  return message
}

export const AutoCommit = async ({ client, directory }) => {
  let lastError = ""
  let snapshotted = false
  return {
    event: async ({ event }) => {
      const isPrompt = event.type === "message.updated" && event.properties?.info?.role === "user"
      if (event.type !== "session.idle" && !isPrompt) return
      if (isPrompt && snapshotted) return
      try {
        // On a new prompt, first save the user's own pending edits under "vault:"
        // so they aren't attributed to opencode's reply.
        await commit(directory, isPrompt ? "vault" : "opencode")
        if (isPrompt) snapshotted = true
        else snapshotted = false
        lastError = ""
      } catch (err) {
        // Usually Obsidian Git committing at the same moment; the next reply
        // picks the changes up. Show each distinct error once.
        const msg = String(err.stderr || err.message).trim().split("\n")[0]
        if (msg === lastError || /index\.lock/.test(msg)) return
        lastError = msg
        try {
          await client.tui.showToast({ body: { message: `auto-commit: ${msg}`, variant: "error" } })
        } catch {}
      }
    },
  }
}
