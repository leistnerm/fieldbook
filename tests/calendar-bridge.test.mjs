import test from 'node:test'
import assert from 'node:assert/strict'
import { calendar } from '../fieldbook_core/lib/calendar-bridge.js'
test('calendar permission denial occurs before credential or remote helper execution', async () => {
  let called = false
  await assert.rejects(calendar({ provider: 'google', instance: 'home', mode: 'events' }, {
    ask: async v => { assert.equal(v.permission, 'calendar_pull'); throw Error('denied') },
  }, async () => { called = true }), /denied/)
  assert.equal(called, false)
})
test('calendar permission includes selected calendar and date scope, then forwards exact arguments', async () => {
  const args = { provider: 'microsoft', instance: 'work', mode: 'series', calendarIds: ['opaque'], start: '2026-10-01', end: '2026-10-10' }
  const order = []
  const result = await calendar(args, { ask: async v => { order.push('ask'); assert.deepEqual(v.metadata.calendars, ['opaque']); assert.equal(v.metadata.start, args.start) } }, async v => { order.push('run'); assert.deepEqual(v, args); return { items: [], read_only: true } })
  assert.deepEqual(order, ['ask', 'run']); assert.equal(JSON.parse(result).read_only, true)
})
