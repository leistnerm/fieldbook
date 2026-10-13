import { dateFields, mappedDates } from './tracker-dates.js'
// Azure Boards work items. Both POST routes below are documented read operations.
const quote = value => {
  const text = String(value)
  // WIQL supports either delimiter. Avoid assuming SQL-style escape rules.
  if (/[\x00-\x1f]/.test(text)) throw new Error('Azure query identities must be single-line values')
  if (!text.includes("'")) return `'${text}'`
  if (!text.includes('"')) return `"${text}"`
  throw new Error('Azure query value contains both quote styles; use an unambiguous project/account identity')
}
const fields = ['System.Id', 'System.Title', 'System.State', 'System.AssignedTo', 'System.TeamProject',
  'System.WorkItemType', 'System.Description', 'System.ChangedDate', 'System.AreaPath', 'System.IterationPath']
export function azureId(value) {
  if (!/^[1-9]\d*$/.test(String(value)) || !Number.isSafeInteger(Number(value))) throw new Error('Azure Boards IDs must be positive work item numbers')
  return Number(value)
}
export function azureQuery(instance, opts) {
  if (!['mine', 'team', 'all'].includes(opts.scope)) throw new Error('Choose mine, team, or all for an Azure query')
  if (typeof instance.project !== 'string' || !instance.project.trim() || /[\/\\\x00-\x1f]/.test(instance.project) || ['.', '..'].includes(instance.project))
    throw new Error('Configure an explicit Azure project name for mine, team, or all')
  const clauses = [`[System.TeamProject] = ${quote(instance.project)}`]
  const me = opts.self ? quote(opts.self) : '@Me'
  if (opts.scope === 'mine') clauses.push(`[System.AssignedTo] = ${me}`)
  if (opts.scope === 'team') {
    if (!opts.members?.length) throw new Error('Team scope needs confirmed Azure report identities')
    clauses.push(`([System.AssignedTo] = ${me} OR [System.AssignedTo] IN (${[...new Set(opts.members)].map(quote).join(',')}))`)
  }
  const filter = opts.query || instance.filter
  if (filter) {
    if (typeof filter !== 'string' || /\b(select|from|order\s+by|asof)\b|;|--|\/\*/i.test(filter)) throw new Error('Use an Azure WHERE expression only; SELECT and stable ordering are added by the adapter')
    clauses.push(`(${filter})`)
  }
  return `SELECT [System.Id] FROM WorkItems WHERE ${clauses.join(' AND ')} ORDER BY [System.Id] ASC`
}
export function normalizeAzure(item, instance) {
  const id = azureId(item?.id), f = item.fields
  if (!f || typeof f['System.Title'] !== 'string' || typeof f['System.State'] !== 'string') throw new Error('Unexpected Azure work item; no partial result returned')
  const owner = f['System.AssignedTo']
  return {
    provider: 'azure', instance: instance.id, id: String(id), title: f['System.Title'], status: f['System.State'],
    updated: f['System.ChangedDate'] || '',
    ...mappedDates('azure', instance, f),
    assignees: owner ? [typeof owner === 'string' ? { id: owner, name: owner } : { id: owner.uniqueName || owner.id, name: owner.displayName || '', accountId: owner.id }] : [],
    project: f['System.TeamProject'] || '', kind: f['System.WorkItemType'] || '',
    areaPath: f['System.AreaPath'] || '', iterationPath: f['System.IterationPath'] || '',
    description: f['System.Description'] || '', descriptionFormat: 'html',
    url: `${instance.baseUrl.replace(/\/$/, '')}/_workitems/edit/${id}`,
  }
}
export async function pullAzure(instance, opts, request) {
  const limit = opts.limit || 500, requestedFields = [...fields]
  for (const field of Object.values(dateFields('azure', instance))) {
    if (typeof field !== 'string' || !/^[A-Za-z][A-Za-z0-9_.]*$/.test(field)) throw new Error('Azure date fields must use exact field reference names')
    requestedFields.push(field)
  }
  let ids, asOf
  if (opts.scope === 'linked') {
    if (!opts.ids?.length) throw new Error('Linked scope requires Azure work item IDs')
    ids = [...new Set(opts.ids.map(azureId))]
  } else {
    const query = azureQuery(instance, opts)
    const page = await request(`/${encodeURIComponent(instance.project)}/_apis/wit/wiql`, { 'api-version': '7.1', '$top': limit + 1 }, { query })
    if (!Array.isArray(page.workItems)) throw new Error('Unexpected Azure query response; no partial result returned')
    ids = [...new Set(page.workItems.map(item => azureId(item.id)))]
    asOf = page.asOf
  }
  const truncated = ids.length > limit, selected = ids.slice(0, limit), items = []
  for (let start = 0; start < selected.length; start += 200) {
    const batch = selected.slice(start, start + 200)
    const data = await request('/_apis/wit/workitemsbatch', { 'api-version': '7.1' }, { ids: batch, fields: [...new Set(requestedFields)], errorPolicy: 'Fail', ...(asOf ? { asOf } : {}) })
    if (!Array.isArray(data.value)) throw new Error('Unexpected Azure batch response; no partial result returned')
    const found = new Map(data.value.map(item => [azureId(item.id), item]))
    if (data.value.length !== batch.length || found.size !== batch.length || batch.some(id => !found.has(id)))
      throw new Error('Azure batch is missing or mismatches requested work items; no partial result returned')
    items.push(...batch.map(id => normalizeAzure(found.get(id), instance)))
  }
  return { items, truncated }
}
