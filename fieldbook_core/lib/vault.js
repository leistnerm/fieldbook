import { readFile, readdir, lstat } from 'node:fs/promises'
import path from 'node:path'
import { parseDocument } from 'yaml'
export const SKIP = new Set(['.git', '.obsidian', 'fieldbook_core', '.trash', 'node_modules', 'Templates', 'Examples', 'tests', 'tools'])
export async function markdownFiles(root, rel = '') {
  const out = []; let bytes = 0
  async function walk(relative) {
    for (const e of await readdir(path.join(root, relative), { withFileTypes: true })) {
      if (e.name.startsWith('.') || SKIP.has(e.name) || ['Dashboards', 'Setups', '__pycache__'].includes(e.name)) continue
      const p = path.join(relative, e.name)
      if (e.isSymbolicLink()) continue
      if (e.isDirectory()) await walk(p)
      else if (e.isFile() && e.name.endsWith('.md')) {
        const info = await lstat(path.join(root, p))
        if (info.size > 1024 * 1024) throw new Error('Incomplete note scan: file exceeds 1 MiB: ' + p)
        bytes += info.size
        if (bytes > 64 * 1024 * 1024 || out.length >= 10000) throw new Error('Incomplete note scan: limit exceeded')
        out.push(p.split(path.sep).join('/'))
      }
    }
  }
  await walk(rel) // Read failures abort identity-dependent operations instead of hiding notes.
  return out.sort()
}
export function frontmatter(text) {
  const m = text.replace(/^\uFEFF/, '').match(/^---\r?\n([\s\S]*?)\r?\n---(?:\r?\n|$)/)
  if (!m) return {}
  if (Buffer.byteLength(m[1]) > 32768) throw new Error('Frontmatter exceeds 32 KiB')
  const doc = parseDocument(m[1], { uniqueKeys: true })
  if (doc.errors.length) throw new Error(doc.errors[0].message)
  const data = doc.toJS({ maxAliasCount: 50 })
  if (!data || Array.isArray(data) || typeof data !== 'object') throw new Error('Frontmatter must be a mapping')
  return data
}
export const list = value => value == null ? [] : Array.isArray(value) ? value : [value]
export async function settings(root) {
  try { return JSON.parse((await readFile(path.join(root, 'fieldbook.json'), 'utf8')).replace(/^\uFEFF/, '')) }
  catch (e) { if (e.code === 'ENOENT') return { setups: [], features: {} }; throw e }
}
export const windowsSafe = name => typeof name === 'string' && !!name.trim() && !/[\\/:*?"<>|#^[\]\x00-\x1f]/.test(name) && !/[. ]$/.test(name) && !/^(con|prn|aux|nul|com[1-9]|lpt[1-9])(?:\.|$)/i.test(name)
