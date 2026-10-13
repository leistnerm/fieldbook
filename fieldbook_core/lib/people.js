import { readFile, writeFile, mkdir } from 'node:fs/promises'
import path from 'node:path'
import { markdownFiles, frontmatter, list, windowsSafe } from './vault.js'
const FIELDS = ['attendees', 'assignee', 'owner', 'stakeholders', 'deciders', 'manager', 'requester', 'instructor']
const base = s => s.replace(/\s*\([^)]*\)\s*$/, '').trim().toLowerCase()
export async function scanPeople(root, notify = async () => {}, warned = new Set()) {
  const warn = async (key, message) => { if (!warned.has(key)) { warned.add(key); await notify(message, 'warning') } }
  const notes = []
  for (const file of await markdownFiles(root)) {
    try { notes.push({ file, name: path.basename(file, '.md'), data: frontmatter(await readFile(path.join(root, file), 'utf8')) }) }
    catch (e) { await warn(`yaml:${file}`, `Invalid YAML in ${file}: ${e.message}`) }
  }
  const people = notes.filter(n => list(n.data.tags).includes('person')).map(n => ({ ...n, keys: new Set([
    base(n.name), ...list(n.data.aliases).filter(x => typeof x === 'string').map(base),
    ...list(n.data.usernames).filter(x => typeof x === 'string').flatMap(x => { const cut = x.indexOf(': '); const v = (cut >= 0 ? x.slice(cut + 2) : x.replace(/^[^:]*:/, '')).trim().toLowerCase(); return [v, v.split('\\').pop()] })
  ]) }))
  const wanted = new Map()
  for (const n of notes) for (const f of FIELDS) for (const v of list(n.data[f])) {
    if (typeof v !== 'string') continue
    for (const m of v.matchAll(/\[\[([^\]|#]+)(?:[#|][^\]]*)?\]\]/g)) {
      const target = m[1].trim().replace(/\.md$/, '')
      const name = target.split('/').pop()
      if (!windowsSafe(name)) { await warn(`name:${target}`, `Invalid person filename: ${target}`); continue }
      const key = name.toLowerCase()
      const exact = notes.filter(x => x.name.toLowerCase() === key)
      if (exact.length) {
        const person = exact.filter(x => list(x.data.tags).includes('person'))
        const qualified = people.filter(x => x.name.toLowerCase() !== key && x.keys.has(key))
        if (person.length !== 1 || exact.length !== 1 || (base(name) === key && qualified.length))
          await warn(`collision:${key}`, `Ambiguous person link [[${target}]] in ${n.file}; check note tags and qualify the person's name.`)
        else if (target.includes('/') && person[0].file.replaceAll(path.sep, '/').replace(/\.md$/, '').toLowerCase() !== target.toLowerCase())
          await warn(`path:${target}`, `Person link [[${target}]] has the wrong folder; use [[${person[0].name}]].`)
        continue
      }
      if (target.includes('/') && target.toLowerCase() !== `people/${key}`) {
        await warn(`path:${target}`, `Missing person [[${target}]] uses a different folder; no note created.`); continue
      }
      wanted.set(key, { name, source: n.name })
    }
  }
  const created = []
  for (const [key, item] of wanted) {
    const matches = people.filter(p => p.keys.has(key))
    const incoming = [...wanted].filter(([k, p]) => k !== key && base(p.name) === key)
    if (base(item.name) === key && (matches.length || incoming.length)) {
      await warn(`ambiguous:${key}`, `Ambiguous [[${item.name}]]: ${[...matches.map(p => p.name), ...incoming.map(([, p]) => p.name)].join(', ')}. No plain-name note created.`); continue
    }
    const template = await readFile(path.join(root, 'Templates/Person.md'), 'utf8')
    if (template.includes('<%')) throw new Error('Person template contains Templater code; auto-people needs a plain template')
    const today = new Date().toLocaleDateString('en-CA')
    const body = template.replace(/## Notes\r?\n/, h => `${h}Auto-created ${today} from [[${item.source}]].\n`)
    await mkdir(path.join(root, 'People'), { recursive: true })
    try { await writeFile(path.join(root, 'People', `${item.name}.md`), body, { flag: 'wx' }); created.push(item.name); await notify(`Created person: ${item.name}`) }
    catch (e) { if (e.code !== 'EEXIST') throw e }
  }
  return created
}
