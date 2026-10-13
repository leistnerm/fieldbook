import { readFile } from 'node:fs/promises'
import path from 'node:path'
import { markdownFiles, frontmatter, list } from './vault.js'

export function accountFor(person, provider, instance, required = true) {
  const label = `${provider}:${instance}:`
  const matches = list(person.data.usernames).filter(v => typeof v === 'string' && v.startsWith(label)).map(v => v.slice(label.length).trim())
  if (!matches.length && !required) return undefined
  if (matches.length !== 1 || !matches[0] || matches[0].length > 256 || /[\x00-\x1f]/.test(matches[0]))
    throw new Error(`Set one confirmed "${label} account" username on ${person.path}`)
  const account = matches[0]
  if (provider === 'github' && !/^[A-Za-z0-9][A-Za-z0-9-]*$/.test(account)) throw new Error(`Use a GitHub login on ${person.path}`)
  if (provider === 'agility' && !/^Member:[1-9]\d*$/.test(account)) throw new Error(`Use an Agility Member:number on ${person.path}`)
  return account
}

export async function trackerPeople(root, provider, instance, scope, explicitMembers = []) {
  if (!['mine', 'team'].includes(scope)) return { people: [] }
  const people = []
  for (const file of await markdownFiles(root)) {
    const data = frontmatter(await readFile(path.join(root, file), 'utf8'))
    if (list(data.tags).includes('person') && (!data.status || data.status === 'current')) people.push({ path: file, data })
  }
  const self = people.filter(p => p.data.relationship === 'self')
  if (self.length > 1) throw new Error('Multiple current relationship: self person records; resolve them before syncing')
  const derive = scope === 'team' && !explicitMembers.length
  if (derive && self.length !== 1) throw new Error('Team scope requires one current person record with relationship: self')
  const selected = self.slice()
  if (derive) {
    const reports = people.filter(p => p.data.relationship === 'report')
    if (!reports.length) throw new Error('No current relationship: report person records; use mine scope or supply confirmed members')
    selected.push(...reports)
  }
  const resolved = selected.map(p => ({ path: p.path, relationship: p.data.relationship, account: accountFor(p, provider, instance, derive) }))
  const seen = new Set()
  for (const p of resolved.filter(p => p.account)) {
    const key = p.account.toLowerCase()
    if (seen.has(key)) throw new Error(`Duplicate ${provider}:${instance} account across self/report person records; resolve before syncing`)
    seen.add(key)
  }
  return { self: resolved.find(p => p.relationship === 'self')?.account,
    members: derive ? resolved.filter(p => p.relationship === 'report').map(p => p.account) : explicitMembers,
    people: resolved, membershipSource: derive ? 'person relationships' : scope === 'team' ? 'explicit members' : 'self or authenticated/configured user' }
}
