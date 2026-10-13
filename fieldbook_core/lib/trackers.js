import { dateFields, mappedDates } from './tracker-dates.js'
// Remote adapters return data only. They never edit the vault or a tracker.
const validScopes = new Set(['linked', 'mine', 'team', 'all'])
export const providers = ['jira', 'agility', 'github', 'azure']
export const identity = item => `${item.provider}:${item.instance}:${item.id}`.toLowerCase()
export const TRACKER_LIMITS = Object.freeze({ responseBytes: 2 * 1024 * 1024, totalBytes: 8 * 1024 * 1024, requests: 100, outputBytes: 2 * 1024 * 1024 })
export function connection(provider, instance, env = process.env, fetcher = fetch, signal, limits = TRACKER_LIMITS) {
  for (const key of ['responseBytes', 'totalBytes', 'requests']) {
    if (!Number.isSafeInteger(limits[key]) || limits[key] < 1 || limits[key] > TRACKER_LIMITS[key]) throw new Error('Invalid tracker read budget')
  }
  let requests = 0, totalBytes = 0
  const deadline = AbortSignal.timeout(120_000)
  const pullSignal = signal ? AbortSignal.any([signal, deadline]) : deadline
  if (!providers.includes(provider)) throw new Error('Unknown tracker provider')
  const base = new URL(instance.baseUrl)
  if (base.protocol !== 'https:' || base.username || base.password || base.search || base.hash) throw new Error('Use an HTTPS baseUrl without credentials, query, or fragment')
  const prefix = `${provider.toUpperCase()}_`
  if (!instance.tokenVar?.startsWith(prefix) || !/^[A-Z][A-Z0-9_]+$/.test(instance.tokenVar)) throw new Error(`tokenVar must start with ${prefix}`)
  const token = env[instance.tokenVar]
  if (!token) throw new Error(`${instance.tokenVar} is not set`)
  let authorization = `Bearer ${token}`
  if (provider === 'azure') authorization = `Basic ${Buffer.from(`:${token}`).toString('base64')}`
  if (provider === 'jira' && instance.flavor === 'cloud') {
    const email = instance.email || env.JIRA_EMAIL
    if (!email) throw new Error('Jira Cloud needs an email in its instance config or JIRA_EMAIL')
    authorization = `Basic ${Buffer.from(`${email}:${token}`).toString('base64')}`
  }
  return async (endpoint, query, body) => {
    // Endpoint is adapter-owned, never a URL from a note or API response.
    // Allow only the exact read routes implemented below, including the two
    // Azure POST reads. Arbitrary endpoints/methods are not a capability here.
    const post = body !== undefined
    const allowed = provider === 'jira' ? !post && ['/rest/api/3/search/jql', '/rest/api/2/search'].includes(endpoint)
      : provider === 'agility' ? post && endpoint === '/query.v1'
      : provider === 'github' ? !post && (endpoint === '/user' || /^\/repos\/[A-Za-z0-9_.-]+\/[A-Za-z0-9_.-]+\/issues(?:\/[1-9]\d*)?$/.test(endpoint))
      : post && (endpoint === '/_apis/wit/workitemsbatch' || /^\/[^/]+\/_apis\/wit\/wiql$/.test(endpoint))
    if (!allowed || /(?:^|\/)\.{1,2}(?:\/|$)|[?#\\]/.test(endpoint)) throw new Error('Only allowlisted read-only tracker endpoints are permitted')
    const url = new URL(base.href.replace(/\/$/, '') + endpoint)
    for (const [k, v] of Object.entries(query || {})) if (v !== undefined) url.searchParams.set(k, String(v))
    if (url.origin !== base.origin) throw new Error('Unexpected tracker origin')
    if (++requests > limits.requests) throw new Error(`${provider}: request budget exceeded; narrow the scope; no partial result returned`)
    let response
    try { response = await fetcher(url, { method: post ? 'POST' : 'GET', redirect: 'error', signal: AbortSignal.any([pullSignal, AbortSignal.timeout(30_000)]), headers: { Authorization: authorization, Accept: provider === 'github' ? 'application/vnd.github+json' : 'application/json', ...(provider === 'github' ? { 'X-GitHub-Api-Version': instance.apiVersion || '2026-03-10' } : {}), ...(post ? { 'Content-Type': 'application/json' } : {}) }, ...(post ? { body: JSON.stringify(body) } : {}) }) }
    catch { throw new Error(`${provider}: request failed (network, timeout, or redirect); no partial result returned`) }
    if (!response.ok) throw new Error(`${provider}: HTTP ${response.status}; check access, configuration, or retry later`)
    let reader
    try {
      const size = Number(response.headers?.get('content-length'))
      const type = response.headers?.get('content-type') || ''
      if ((type && !/application\/(?:[\w.+-]+\+)?json(?:;|$)/i.test(type)) || size > limits.responseBytes || size + totalBytes > limits.totalBytes)
        throw new Error('Invalid response')
      if (!response.body?.getReader) throw new Error('Streaming response required')
      reader = response.body.getReader()
      const chunks = []; let bytes = 0
      for (;;) {
        const { done, value } = await reader.read()
        if (done) break
        bytes += value.byteLength; totalBytes += value.byteLength
        if (bytes > limits.responseBytes || totalBytes > limits.totalBytes) throw new Error('Read budget exceeded')
        chunks.push(value)
      }
      const parsed = JSON.parse(new TextDecoder('utf-8', { fatal: true }).decode(Buffer.concat(chunks)))
      // Limit nesting before the provider-specific normalizers traverse descriptions.
      const stack = [[parsed, 0]]
      while (stack.length) {
        const [value, depth] = stack.pop()
        if (depth > 40) throw new Error('Excessive nesting')
        if (value && typeof value === 'object') for (const child of Object.values(value)) stack.push([child, depth + 1])
      }
      return parsed
    } catch {
      throw new Error(`${provider}: invalid, oversized or interrupted JSON response; narrow the scope; no partial result returned`)
    } finally {
      if (reader) { try { await reader.cancel() } catch {} reader.releaseLock() }
      else { try { await response.body?.cancel() } catch {} }
    }
  }
}
const quoteJql = s => `"${String(s).replaceAll('\\', '\\\\').replaceAll('"', '\\"')}"`
export function jiraQuery(instance, { scope, ids = [], members = [], query, self }) {
  if (!validScopes.has(scope)) throw new Error('Choose linked, mine, team, or all')
  if (scope === 'linked') {
    if (!ids.length || ids.some(id => !/^[A-Za-z][\w]*-\d+$/.test(id))) throw new Error('Linked scope requires valid Jira issue keys')
    return `key in (${ids.map(quoteJql).join(',')}) ORDER BY key ASC`
  }
  const clauses = []
  const me = self ? quoteJql(self) : 'currentUser()'
  if (scope === 'mine') clauses.push(`assignee = ${me}`)
  if (scope === 'team') {
    if (!members.length) throw new Error('Team scope needs confirmed report account IDs/usernames')
    clauses.push(`(assignee = ${me} OR assignee in (${members.map(quoteJql).join(',')}))`)
  }
  const filter = query || instance.filter
  if (filter) {
    if (/\border\s+by\b/i.test(filter)) throw new Error('Use a JQL filter without ORDER BY; stable ordering is added by the adapter')
    clauses.push(`(${filter})`)
  }
  if (scope === 'all' && !filter) throw new Error('All scope requires an explicit project/filter; it never scans an entire instance implicitly')
  return clauses.join(' AND ') + ' ORDER BY key ASC'
}
export function plainText(value) {
  if (!value) return ''
  if (typeof value === 'string') return value
  if (Array.isArray(value)) return value.map(plainText).join(' ')
  return [value.text || '', ...((value.content || []).map(plainText))].filter(Boolean).join(' ')
}
export function normalizeJira(issue, instance) {
  if (!issue || typeof issue !== 'object' || !/^[A-Za-z][\w]*-\d+$/.test(issue.key || '') || !issue.fields || typeof issue.fields !== 'object' || Array.isArray(issue.fields)) throw new Error('Unexpected Jira issue shape; no partial result returned')
  const f = issue.fields
  return { provider: 'jira', instance: instance.id, id: issue.key, title: f.summary || '', status: f.status?.name || '', statusCategory: f.status?.statusCategory?.key || '', resolution: f.resolution?.name || '', ...mappedDates('jira', instance, f), updated: f.updated || '', assignees: f.assignee ? [{ id: f.assignee.accountId || f.assignee.name, name: f.assignee.displayName }] : [], project: f.project?.key || '', kind: f.issuetype?.name || '', description: plainText(f.description), url: `${instance.baseUrl.replace(/\/$/, '')}/browse/${issue.key}` }
}
export async function pullJira(instance, opts, request) {
  const mapped = Object.values(dateFields('jira', instance))
  const jql = jiraQuery(instance, opts), items = [], seenTokens = new Set(), seenItems = new Set()
  const limit = opts.limit || 500, cloud = instance.flavor === 'cloud'
  let startAt = 0, nextPageToken
  for (;;) {
    const page = await request(cloud ? '/rest/api/3/search/jql' : '/rest/api/2/search', { jql, maxResults: Math.min(100, limit - items.length), fields: [...new Set(['summary','status','assignee','project','issuetype','updated','resolution','description', ...mapped])].join(','), ...(cloud ? { nextPageToken } : { startAt }) })
    if (!Array.isArray(page.issues)) throw new Error('Unexpected Jira response; no partial result returned')
    for (const issue of page.issues) { const item = normalizeJira(issue, instance); const key = identity(item); if (!seenItems.has(key)) { seenItems.add(key); items.push(item) } }
    const next = page.nextPageToken
    const more = cloud ? page.isLast === false || !!next : startAt + page.issues.length < page.total
    if (!more) return { items, truncated: false }
    if (items.length >= limit) return { items: items.slice(0, limit), truncated: true }
    if (!page.issues.length || (cloud && (!next || seenTokens.has(next)))) throw new Error('Jira pagination stalled; no partial result returned')
    if (next) seenTokens.add(next)
    nextPageToken = next; startAt += page.issues.length
  }
}
export function agilityQueries(instance, opts) {
  if (!validScopes.has(opts.scope)) throw new Error('Choose linked, mine, team, or all')
  if (opts.scope === 'linked' && (!opts.ids?.length || opts.ids.some(id => !/^[A-Za-z]+-\d+$/.test(id)))) throw new Error('Linked scope requires Agility work item numbers')
  const me = opts.self || instance.memberId
  const members = opts.scope === 'team' ? [me, ...(opts.members || [])] : [me]
  if (['mine','team'].includes(opts.scope) && members.some(id => !/^Member:\d+$/.test(id || ''))) throw new Error('Configure memberId and report identities as Member:123')
  if (opts.scope === 'team' && !opts.members?.length) throw new Error('Team scope needs confirmed report member IDs')
  if (opts.scope === 'all' && !Object.keys(instance.where || {}).length) throw new Error('All scope requires an explicit Agility where filter in the instance config')
  const queries = []
  const scopes = opts.scope === 'linked' ? opts.ids.map(Number => ({ Number })) : ['mine','team'].includes(opts.scope) ? [...new Set(members)].map(Owners => ({ Owners })) : [{}]
  for (const where of scopes) queries.push({ from: 'Workitem', select: ['Number','Name','Description','Status.Name','Owners.Name','Owners.ID','Scope.Name','AssetState','ChangeDate', ...Object.values(dateFields('agility', instance))], where: { ...(opts.scope === 'linked' ? {} : instance.where || {}), ...where } })
  return queries
}
export function normalizeAgility(asset, instance) {
  const names = Array.isArray(asset['Owners.Name']) ? asset['Owners.Name'] : asset['Owners.Name'] ? [asset['Owners.Name']] : []
  const ids = Array.isArray(asset['Owners.ID']) ? asset['Owners.ID'] : asset['Owners.ID'] ? [asset['Owners.ID']] : []
  return { provider: 'agility', instance: instance.id, id: asset.Number, oid: asset._oid, title: asset.Name || '', status: asset['Status.Name'] || '', assetState: asset.AssetState, updated: asset.ChangeDate || '', assignees: ids.map((id, i) => ({ id: String(id).startsWith('Member:') ? String(id) : `Member:${id}`, name: names[i] || '' })), project: asset['Scope.Name'] || '', kind: asset._oid?.split(':')[0] || '', description: asset.Description || '', ...mappedDates('agility', instance, asset) }
}
export async function pullAgility(instance, opts, request) {
  const unique = new Map(), limit = opts.limit || 500
  for (const q of agilityQueries(instance, opts)) {
    let start = 0
    const seenPages = new Set()
    for (;;) {
      // POST to query.v1 is a read-only query, not an asset mutation.
      const result = await request('/query.v1', {}, { ...q, page: { start, size: 100 } })
      if (!Array.isArray(result) || !Array.isArray(result[0])) throw new Error('Unexpected Agility response; no partial result returned')
      const page = result[0]
      const signature = JSON.stringify(page.map(x => x._oid || x.Number))
      if (page.length && seenPages.has(signature)) throw new Error('Agility pagination stalled; no partial result returned')
      seenPages.add(signature)
      for (const asset of page) {
        if (!asset.Number) throw new Error('Agility result is missing Number')
        const item = normalizeAgility(asset, instance)
        unique.set(identity(item), item)
        if (unique.size > limit) return { items: [...unique.values()].slice(0, limit), truncated: true }
      }
      if (page.length < 100) break
      start += page.length
      if (start > 100000) throw new Error('Agility pagination limit exceeded')
    }
  }
  return { items: [...unique.values()], truncated: false }
}
