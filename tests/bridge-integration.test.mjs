import test from 'node:test'
import assert from 'node:assert/strict'
import { existsSync } from 'node:fs'
import { mkdtemp, mkdir, copyFile, readFile, writeFile, rm } from 'node:fs/promises'
import os from 'node:os'
import path from 'node:path'
import { notebook, processJSON, root } from '../fieldbook_core/lib/notebook-bridge.js'

test('real Python bridge: preview, deny, approve, Unicode read, search and stale-write rejection', async t => {
  const vault = await mkdtemp(path.join(os.tmpdir(), 'fieldbook-bridge-'))
  t.after(() => rm(vault, { recursive: true, force: true }))
  const script = path.join(vault, 'fieldbook_core/scripts/notebook.py')
  await mkdir(path.dirname(script), { recursive: true })
  await copyFile(path.join(root, 'fieldbook_core/scripts/notebook.py'), script)
  await copyFile(path.join(root, 'fieldbook_core/scripts/calendar_events.py'), path.join(path.dirname(script), 'calendar_events.py'))
  const venv = path.join(root, 'fieldbook_core/.venv', process.platform === 'win32' ? 'Scripts/python.exe' : 'bin/python')
  const executable = process.env.FIELDBOOK_PYTHON || (existsSync(venv) ? venv : process.platform === 'win32' ? 'python' : 'python3')
  const run = args => processJSON(executable, ['-I', '-B', script], args)
  const args = { path: 'Tasks/College.md', text: '---\ntags: [task]\narea: school\nstatus: active\n---\nRésumé — café study\n', expected: 'missing' }
  await assert.rejects(notebook('write', args, { ask: async () => { throw Error('Denied') } }, run), /Denied/)
  assert.equal(existsSync(path.join(vault, args.path)), false)
  let approvals = 0
  const context = { ask: async request => {
    if (request.permission === 'notebook_write') {
      approvals++
      assert.match(request.metadata.diff, /Résumé — café/)
    }
  } }
  const created = JSON.parse(await notebook('write', args, context, run))
  assert.equal(created.created, true)
  const data = JSON.parse(await notebook('read', { path: args.path }, context, run))
  assert.equal(data.text, args.text)
  assert.equal(data.sha256, created.sha256)
  const search = JSON.parse(await notebook('search', { mode: 'regex', query: 'café.*study' }, context, run))
  assert.ok(JSON.stringify(search).includes(args.path))
  // Simulate another editor while the approval UI is open.
  const changedContext = { ask: async () => writeFile(path.join(vault, args.path), 'External edit\n') }
  await assert.rejects(notebook('write', { ...args, expected: data.sha256, text: args.text + 'New line\n' }, changedContext, run), /Conflict/)
  assert.equal(await readFile(path.join(vault, args.path), 'utf8'), 'External edit\n')
  assert.equal(approvals, 1)
  await mkdir(path.join(vault, 'Attachments'))
  const invite = 'BEGIN:VCALENDAR\r\nVERSION:2.0\r\nBEGIN:VEVENT\r\nUID:bridge@example.test\r\nDTSTART:20261015T140000Z\r\nSUMMARY:Planning\r\nEND:VEVENT\r\nEND:VCALENDAR\r\n'
  await writeFile(path.join(vault, 'Attachments/event.ics'), invite)
  const permissions = []
  const event = JSON.parse(await notebook('calendar', {path:'Attachments/event.ics'}, {ask:async request=>permissions.push(request.permission)}, run))
  assert.deepEqual(permissions, ['notebook_calendar'])
  assert.equal(event.events[0].uid, 'bridge@example.test')
  assert.equal(event.read_only, true)
  assert.equal(existsSync(path.join(vault, 'Meetings')), false)
  assert.equal(existsSync(path.join(vault, 'People')), false)
  assert.equal(await readFile(path.join(vault, 'Attachments/event.ics'), 'utf8'), invite)
})
