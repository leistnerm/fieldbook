import { fileURLToPath } from 'node:url'
import path from 'node:path'
import { parseArgs } from 'node:util'
import { pullTracker } from '../lib/tracker-service.js'
try {
  const { values } = parseArgs({ options: { provider: { type: 'string' }, instance: { type: 'string' }, scope: { type: 'string' }, ids: { type: 'string' }, members: { type: 'string' }, query: { type: 'string' }, limit: { type: 'string', default: '500' } } })
  const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '../..')
  console.log(JSON.stringify(await pullTracker(values, root), null, 2))
} catch (e) { console.error(e.message); process.exitCode = 1 }
