// Explicit read mappings only; these facts never authorize changing a local date.
export const dateTypes = ['due', 'completed', 'start', 'target', 'review', 'available_from', 'closes_at']
export function dateFields(provider, instance) {
  const configured = Object.hasOwn(instance, 'dateFields') ? instance.dateFields : {}
  if (!configured || typeof configured !== 'object' || Array.isArray(configured)) throw new Error('dateFields must be an object')
  const pattern = provider === 'jira' ? /^[A-Za-z][A-Za-z0-9_]{0,127}$/ : /^[A-Za-z][A-Za-z0-9_]*(?:\.[A-Za-z][A-Za-z0-9_]*)*$/
  const defaults = provider === 'jira' ? { due: 'duedate', completed: 'resolutiondate' }
    : provider === 'azure' ? { due: instance.dueField || '', completed: instance.completionField || '' } : {}
  const mapping = { ...defaults, ...configured }
  for (const [type, field] of Object.entries(mapping)) {
    if (!dateTypes.includes(type) || typeof field !== 'string' || field.length > 128 || (field && !pattern.test(field)))
      throw new Error('Use supported date meanings and exact field references in dateFields')
  }
  const entries = Object.entries(mapping).filter(([, field]) => field)
  if (new Set(entries.map(([, field]) => field)).size !== entries.length) throw new Error('Map a source date field to only one meaning')
  return Object.fromEntries(entries)
}
export function validDate(value) {
  if (typeof value !== 'string' || !/^\d{4}-\d{2}-\d{2}(?:T\d{2}:\d{2}:\d{2}(?:\.\d{1,9})?(?:Z|[+-]\d{2}:?\d{2})?)?$/.test(value)) return false
  const day = value.slice(0, 10), parsed = new Date(day + 'T00:00:00Z')
  if (!Number.isFinite(parsed.valueOf()) || parsed.toISOString().slice(0, 10) !== day) return false
  if (value.length === 10) return true
  const match = value.match(/T(\d{2}):(\d{2}):(\d{2})(?:\.\d+)?(?:Z|([+-])(\d{2}):?(\d{2}))?$/)
  return !!match && +match[1] < 24 && +match[2] < 60 && +match[3] < 60 && (!match[4] || (+match[5] < 24 && +match[6] < 60))
}
export function mappedDates(provider, instance, fields) {
  const dates = [], date_warnings = [], mapping = dateFields(provider, instance)
  for (const [type, field] of Object.entries(mapping)) {
    if (!Object.hasOwn(fields, field)) { date_warnings.push({ type, field, reason: 'not_returned' }); continue }
    const value = fields[field]
    if (value === null || value === '') { dates.push({ type, field, at: null }); continue }
    if (!validDate(value)) { date_warnings.push({ type, field, reason: 'invalid_date' }); continue }
    dates.push({ type, field, at: value })
    if (value.includes('T') && !/(Z|[+-]\d{2}:?\d{2})$/.test(value)) date_warnings.push({ type, field, reason: 'timezone_unspecified' })
  }
  const get = type => dates.find(d => d.type === type)?.at ?? null
  return { due: get('due'), completed: get('completed'), dates, date_warnings }
}
