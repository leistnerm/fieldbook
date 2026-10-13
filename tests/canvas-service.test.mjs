import test from 'node:test'
import assert from 'node:assert/strict'
import { mkdtemp, mkdir, readFile, writeFile, rm, symlink } from 'node:fs/promises'
import os from 'node:os'
import path from 'node:path'
import { pullCanvas, canvas } from '../fieldbook_core/lib/canvas-service.js'
async function fixture(t, config = { setups: ['school'], features: { canvas: true } }) {
  const root = await mkdtemp(path.join(os.tmpdir(), 'fieldbook-canvas-'))
  t.after(() => rm(root, { recursive: true, force: true }))
  await mkdir(path.join(root, 'fieldbook_core'))
  await writeFile(path.join(root, 'fieldbook.json'), JSON.stringify(config))
  await writeFile(path.join(root, 'fieldbook_core/canvas.json'), JSON.stringify({ instances: [{ id: 'school', baseUrl: 'https://canvas.example.test', tokenVar: 'CANVAS_TEST_TOKEN', courseIds: ['12'] }] }))
  return root
}
const args = { instance: 'school', mode: 'courses' }
const dependencies = { env: { CANVAS_TEST_TOKEN: 'fixture-secret' }, fetch: async () => new Response('[]') }

test('school feature gate is required before credentials/network and every read leaves files intact', async t => {
  const root = await fixture(t)
  const before = await readFile(path.join(root, 'fieldbook_core/canvas.json'))
  const result = await pullCanvas(args, root, undefined, dependencies)
  assert.equal(result.read_only, true); assert.deepEqual(result.items, [])
  assert.deepEqual(await readFile(path.join(root, 'fieldbook_core/canvas.json')), before)
  for (const config of [{ setups: ['work'], features: { canvas: true } }, { setups: ['school'], features: { canvas: false } }]) {
    await writeFile(path.join(root, 'fieldbook.json'), JSON.stringify(config))
    await assert.rejects(pullCanvas(args, root, undefined, { credentialEnvironment: () => assert.fail('must not read credentials'), fetch: () => assert.fail('must not access network') }), /requires school/)
  }
})

test('invalid selections/configuration and duplicate instances fail before credentials', async t => {
  const root = await fixture(t), deps = { credentialEnvironment: () => assert.fail('must validate before credential access') }
  await assert.rejects(pullCanvas({ ...args, mode: 'calendar' }, root, undefined, deps), /dates/)
  await assert.rejects(pullCanvas({ ...args, userId: '99' }, root, undefined, deps), /Unsupported/)
  await assert.rejects(pullCanvas({ ...args, instance: 'missing' }, root, undefined, deps), /unique/)
  await writeFile(path.join(root, 'fieldbook_core/canvas.json'), JSON.stringify({ instances: [{ id: 'school', baseUrl: 'http://canvas.example.test', tokenVar: 'CANVAS_TEST_TOKEN' }] }))
  await assert.rejects(pullCanvas(args, root, undefined, deps), /HTTPS/)
  await writeFile(path.join(root, 'fieldbook_core/canvas.json'), JSON.stringify({ instances: [{ id: 'school' }, { id: 'school' }] }))
  await assert.rejects(pullCanvas(args, root, undefined, deps), /unique/)
})

test('stored credential resolution receives only configured Canvas identity and never returns the token', async t => {
  const root = await fixture(t), lookups = []
  const result = await pullCanvas(args, root, undefined, { env: {}, credentialEnvironment: async (...values) => { lookups.push(values); return { CANVAS_TEST_TOKEN: 'stored-secret' } }, fetch: async (url, options) => { assert.equal(options.headers.Authorization, 'Bearer stored-secret'); return new Response('[]') } })
  assert.equal(lookups[0][0], root); assert.equal(lookups[0][1], 'canvas'); assert.equal(lookups[0][2].id, 'school')
  assert.ok(!JSON.stringify(result).includes('stored-secret'))
})

test('symlinked configuration files are refused', async t => {
  const root = await fixture(t), original = path.join(root, 'fieldbook_core/canvas.json')
  await writeFile(path.join(root, 'linked.json'), await readFile(original)); await rm(original); await symlink(path.join(root, 'linked.json'), original)
  await assert.rejects(pullCanvas(args, root, undefined, dependencies), /linked files/)
})

test('canvas tool approval denial prevents all reads and approved metadata exposes no secret', async () => {
  let runs = 0
  const run = async received => { runs++; assert.deepEqual(received, args); return { items: [], read_only: true } }
  await assert.rejects(canvas(args, { ask: async () => { throw Error('Denied') } }, run), /Denied/)
  assert.equal(runs, 0)
  const result = JSON.parse(await canvas(args, { ask: async request => { assert.equal(request.permission, 'canvas_pull'); assert.deepEqual(request.patterns, ['school:courses']); assert.ok(!JSON.stringify(request).includes('TOKEN')) } }, run))
  assert.equal(runs, 1); assert.equal(result.read_only, true)
  await assert.rejects(canvas(args, {}, run), /permission support/)
})

test('all expanded modes preserve local files, expose read coverage and require permission before enrichment', async t => {
  const root = await fixture(t), filenames = ['fieldbook.json', 'fieldbook_core/canvas.json']
  const before = await Promise.all(filenames.map(n => readFile(path.join(root, n))))
  for (const mode of ['assignments', 'quizzes', 'discussions', 'planner', 'coursework']) {
    const request = { instance: 'school', mode, ...(['planner', 'coursework'].includes(mode) ? { start: '2026-10-01', end: '2026-10-31' } : {}) }
    let reads = 0, approved = false
    const runner = async received => {
      assert.equal(approved, true)
      return pullCanvas(received, root, undefined, { ...dependencies, fetch: async (_, options) => { reads++; assert.equal(options.method, 'GET'); return new Response('[]') } })
    }
    await assert.rejects(canvas(request, { ask: async () => { throw Error('Denied') } }, runner), /Denied/)
    assert.equal(reads, 0)
    const output = JSON.parse(await canvas(request, { ask: async permission => {
      approved = true
      assert.ok(permission.metadata.reads.includes('assignments'))
      assert.equal(permission.metadata.courseIds, 'configured selection')
    } }, runner))
    assert.equal(reads, output.sources_read.length)
    assert.match(output.read_at, /^\d{4}-\d{2}-\d{2}T/)
    assert.equal(output.read_only, true)
  }
  assert.deepEqual(await Promise.all(filenames.map(n => readFile(path.join(root, n)))), before)
  await assert.rejects(pullCanvas({ instance: 'school', mode: 'coursework' }, root, undefined, { credentialEnvironment: () => assert.fail('invalid dates must stop before credentials') }), /dates/)
})
