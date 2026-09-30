// Creates a People/<Name>.md note (from Templates/Person.md) for any person
// linked in a frontmatter people field that has no note yet. If the name could
// be an existing person ("John Smith" when "John Smith (Acme)", an alias or a
// username exists), it warns instead of creating. Plain code, no model calls. Runs only
// while opencode is open. Delete this file to disable.
import { readdir, readFile, writeFile } from "node:fs/promises"
import path from "node:path"

const PEOPLE_DIR = "People"
const TEMPLATE = "Templates/Person.md"
// Frontmatter fields that hold people. Commitments lines are in the body, so
// names there never get notes.
const FIELDS = ["attendees", "assignee", "owner", "stakeholders", "deciders", "manager", "requester"]
const SKIP_DIRS = new Set([".obsidian", ".opencode", ".git", ".trash", "node_modules", "Templates"])
// Wait for edits to settle so a half-typed [[Na]] doesn't become a person.
const DEBOUNCE_MS = 60_000
const MAX_WAIT_MS = 300_000
const BAD_NAME = /[\\/:*?"<>|#^[\]]/

async function listMarkdown(root, rel = "") {
  const out = []
  for (const entry of await readdir(path.join(root, rel), { withFileTypes: true })) {
    const r = path.join(rel, entry.name)
    if (entry.isDirectory()) {
      if (!SKIP_DIRS.has(entry.name)) out.push(...(await listMarkdown(root, r)))
    } else if (entry.name.endsWith(".md")) {
      out.push(r)
    }
  }
  return out
}

function frontmatter(text) {
  const m = text.match(/^---\r?\n([\s\S]*?)\r?\n---/)
  return m ? m[1] : ""
}

// Values of one frontmatter key: inline (`key: a`, `key: [a, b]`) or a list
// on the following lines.
function field(fm, name) {
  const values = []
  let inField = false
  for (const line of fm.split(/\r?\n/)) {
    const key = line.match(/^([A-Za-z_][\w-]*)\s*:(.*)$/)
    if (key) {
      inField = key[1] === name
      if (inField) values.push(...splitInline(key[2]))
    } else if (!/^(\s|-)/.test(line)) inField = false
    else if (inField) values.push(...splitInline(line.replace(/^\s*-\s*/, "")))
  }
  return values.filter(Boolean)
}

function splitInline(v) {
  v = v.trim()
  if (v.startsWith("[") && !v.startsWith("[[")) v = v.slice(1, -1)
  return v.split(/,(?![^[]*\]\])/).map((x) => x.trim().replace(/^["']|["']$/g, ""))
}

function personLinks(fm) {
  const links = []
  for (const f of FIELDS)
    for (const v of field(fm, f))
      for (const l of v.matchAll(/\[\[([^\]|#]+)(?:[#|][^\]]*)?\]\]/g)) links.push(l[1].trim())
  return links
}

// "John Smith (Acme)" -> "john smith"
const baseName = (name) => name.replace(/\s*\([^)]*\)\s*$/, "").trim().toLowerCase()

// "jira: jsmith" or "windows: CORP\\\\jsmith" -> "jsmith" (and the whole value)
function usernameKeys(entry) {
  const v = entry.replace(/^[^:]*:\s*/, "").replace(/\\\\/g, "\\").trim().toLowerCase()
  return [v, v.split("\\").pop()].filter(Boolean)
}

// `warned` persists between scans so each warning shows once per opencode run.
async function scan(directory, notify, warned = new Set()) {
  const files = await listMarkdown(directory)
  const existing = new Set(files.map((f) => path.basename(f, ".md").toLowerCase()))
  const texts = new Map()
  for (const f of files) texts.set(f, frontmatter(await readFile(path.join(directory, f), "utf8")))

  // Every name a person note answers to: its base name, aliases and usernames.
  const people = []
  for (const [f, fm] of texts) {
    if (!field(fm, "tags").includes("person")) continue
    const name = path.basename(f, ".md")
    people.push({ name, keys: new Set([baseName(name), ...field(fm, "aliases").map(baseName), ...field(fm, "usernames").flatMap(usernameKeys)]) })
  }
  const candidates = (key) => people.filter((p) => p.keys.has(key) && p.name.toLowerCase() !== key)

  const warn = async (id, message) => {
    if (warned.has(id)) return
    warned.add(id)
    await notify(message, "warning")
  }

  // A plain "John Smith" note next to "John Smith (Acme)": ask for a rename.
  for (const p of people) {
    const key = p.name.toLowerCase()
    const others = candidates(key)
    if (others.length && key === baseName(p.name))
      await warn(
        `clash:${key}`,
        `Same-name people: rename "${p.name}" in Obsidian (e.g. "${p.name} (Company)") — clashes with ${others.map((o) => o.name).join(", ")}`,
      )
  }

  const missing = new Map()
  for (const [f, fm] of texts) {
    if (!fm) continue
    const source = path.basename(f, ".md")
    for (const link of personLinks(fm)) {
      const name = link.split("/").pop().trim()
      const key = name.toLowerCase()
      if (!name || BAD_NAME.test(name) || existing.has(key) || missing.has(key)) continue
      // A qualified name ("John Smith (Contoso)") is a deliberate new person.
      const maybe = baseName(name) === key ? candidates(key) : []
      if (maybe.length) {
        await warn(
          `ambiguous:${key}:${source}`,
          `Ambiguous: [[${name}]] in ${source} — did you mean ${maybe.map((m) => m.name).join(" or ")}? No note created.`,
        )
        continue
      }
      missing.set(key, { name, source })
    }
  }
  if (!missing.size) return []

  const template = await readFile(path.join(directory, TEMPLATE), "utf8")
  const today = new Date().toLocaleDateString("en-CA")
  const created = []
  for (const { name, source } of missing.values()) {
    const body = template.replace(
      /## Personal notes\r?\n/,
      (h) => `${h}Auto-created ${today} from [[${source}]].\n`,
    )
    try {
      await writeFile(path.join(directory, PEOPLE_DIR, `${name}.md`), body, { flag: "wx" })
      created.push(name)
      await notify(`Created person note: ${name} (from ${source})`)
    } catch (err) {
      if (err.code !== "EEXIST") await notify(`auto-people: couldn't create ${name}: ${err.message}`, "error")
    }
  }
  return created
}

export const AutoPeople = async ({ client, directory }) => {
  let timer = null
  const warned = new Set()
  const notify = async (message, variant = "info") => {
    try {
      await client.tui.showToast({ body: { message, variant } })
    } catch {}
  }
  let cap = null
  const run = () => {
    clearTimeout(timer)
    clearTimeout(cap)
    cap = null
    return scan(directory, notify, warned).catch((err) => notify(`auto-people error: ${err.message}`, "error"))
  }
  const schedule = () => {
    clearTimeout(timer)
    timer = setTimeout(run, DEBOUNCE_MS)
    if (!cap) cap = setTimeout(run, MAX_WAIT_MS)
  }
  schedule()
  return {
    event: async ({ event }) => {
      if (event.type === "file.watcher.updated") {
        const file = String(event.properties?.file ?? "").replace(/\\/g, "/")
        if (/(^|\/)\.(obsidian|git|opencode)\//.test(file)) return
        schedule()
      } else if (event.type === "session.idle") schedule()
    },
  }
}
