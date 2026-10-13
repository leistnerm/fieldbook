import { readFileSync } from 'node:fs'
import { dateFields } from './tracker-dates.js'
const catalog = JSON.parse(readFileSync(new URL('../../tools/integration-coverage.json', import.meta.url), 'utf8'))
export function coverage(provider, instance, selection, result, limits = {}) {
  const capability = catalog.providers[provider]
  if (!capability) throw new Error('Missing integration coverage definition')
  const mappings = ['jira', 'agility', 'azure'].includes(provider) ? dateFields(provider, instance) : {}
  return { schema_version: 1, provider, read_only: true, read_at: new Date().toISOString(),
    scope: selection, supported: capability.objects, date_types: ['jira', 'agility', 'azure'].includes(provider) ? Object.keys(mappings) : capability.date_types,
    date_fields: mappings, excluded: capability.excluded, limits,
    returned: result.items.length, truncated: !!result.truncated,
    date_warning_items: result.items.filter(i => i.date_warnings?.length || i.date_conflicts?.length || i.warnings?.length).length,
    identity_review_items: result.items.filter(i => i.needs_identity_review).length,
    sources_read: result.sources_read || [],
    freshness: 'Snapshot at read_at; no background refresh or proof of later changes.',
    completeness: result.truncated ? 'Partial: narrow the scope or raise the permitted item limit.' : 'Selected scope only; absence is not deletion or completion evidence.' }
}
