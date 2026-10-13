import test from 'node:test'
import assert from 'node:assert/strict'
import { pullGitHub, githubId, normalizeGitHub } from '../fieldbook_core/lib/github.js'
import { connection, identity } from '../fieldbook_core/lib/trackers.js'
const config = { id: 'personal', baseUrl: 'https://api.github.com', tokenVar: 'GITHUB_TOKEN', repositories: ['owner/one'], login: 'me' }
const issue = (number, extra = {}) => ({ number, title: `Issue ${number}`, state: 'open', body: 'Source text', assignees: [{ login: 'me' }], ...extra })

test('GitHub IDs are repository-qualified; malformed and traversal IDs are refused', () => {
  assert.deepEqual(githubId('owner/repo#42'), { repo: 'owner/repo', number: 42, id: 'owner/repo#42' })
  for (const id of ['42', 'owner/repo#0', '../repo#1', 'owner/..#1', 'owner/repo/other#1', 'owner/repo#9007199254740992']) assert.throws(() => githubId(id), /owner\/repository/)
  assert.notEqual(identity(normalizeGitHub(issue(1), config, 'owner/one')), identity(normalizeGitHub(issue(1), config, 'owner/two')))
})
test('GitHub all is bounded by explicit repositories; mine uses self mapping and configured labels', async () => {
  await assert.rejects(pullGitHub({ ...config, repositories: [] }, { scope: 'all' }, async () => assert.fail('network')), /explicit/)
  const calls = []
  const result = await pullGitHub({ ...config, labels: ['school'] }, { scope: 'mine', self: 'student' }, async (p, q) => { calls.push([p,q]); return [issue(1)] })
  assert.equal(result.items.length, 1)
  assert.equal(calls[0][1].state, 'all'); assert.equal(calls[0][1].assignee, 'student'); assert.equal(calls[0][1].labels, 'school')
})
test('GitHub mine falls back to authenticated user only when no explicit identity exists', async () => {
  const calls = []
  await pullGitHub({ ...config, login: '' }, { scope: 'mine' }, async (p,q) => { calls.push([p,q]); return p === '/user' ? { login: 'actual-me' } : [] })
  assert.equal(calls[0][0], '/user'); assert.equal(calls[1][1].assignee, 'actual-me')
})
test('GitHub excludes PRs while paging and deduplicates shared issues across team queries', async () => {
  const calls = []
  const result = await pullGitHub(config, { scope: 'team', self: 'me', members: ['alex'] }, async (p,q) => {
    calls.push(q)
    return q.page === 1 ? Array.from({ length:100 }, (_, i) => issue(i + 1, i < 99 ? { pull_request: {} } : {})) : [issue(101)]
  })
  assert.deepEqual(result.items.map(i => i.id), ['owner/one#100', 'owner/one#101'])
  assert.deepEqual(calls.map(q => [q.assignee,q.page]), [['me',1],['me',2],['alex',1],['alex',2]])
  assert.equal(result.truncated, false)
})
test('GitHub linked reads ignore discovery filters, detect PR links and never follow URLs from content', async () => {
  const calls = []
  const result = await pullGitHub({ ...config, repositories: ['other/repo'], labels: ['elsewhere'] }, { scope:'linked', ids: ['owner/repo#1', 'owner/repo#2'] }, async (p,q) => {
    calls.push([p,q]); return issue(Number(p.split('/').at(-1)), p.endsWith('/2') ? { pull_request: {}, url: 'https://evil.test' } : {})
  })
  assert.deepEqual(calls.map(x=>x[0]), ['/repos/owner/repo/issues/1','/repos/owner/repo/issues/2'])
  assert.equal(result.items.length, 1); assert.equal(result.skipped[0].id, 'owner/repo#2')
  assert.equal(calls[0][1], undefined)
})
test('GitHub cap is explicit; duplicate results at the cap do not falsely truncate', async () => {
  const r = await pullGitHub(config, { scope: 'all', limit: 1 }, async () => [issue(1), issue(2)])
  assert.equal(r.items.length,1); assert.equal(r.truncated,true)
  const exact = await pullGitHub(config, { scope:'team', members:['alex'], limit:1 }, async () => [issue(1)])
  assert.equal(exact.truncated,false)
  let calls=0
  const linked = await pullGitHub(config, { scope:'linked', ids:['owner/repo#1','owner/repo#2'], limit:1 }, async () => { calls++;return issue(1) })
  assert.equal(calls,1);assert.equal(linked.truncated,true)
})
test('GitHub preserves closure reasons and milestone dates without claiming task completion/deadlines', () => {
  const extra = { state: 'closed', closed_at: '2026-10-01T12:00:00Z', state_reason:'not_planned', milestone:{ title:'October', due_on:'2026-10-31' } }
  const item = normalizeGitHub(issue(1, extra), config, 'owner/one')
  assert.equal(item.resolution,'not_planned'); assert.equal(item.completed,null); assert.equal(item.due,null); assert.equal(item.milestone.due,'2026-10-31')
  assert.equal(normalizeGitHub(issue(1, {...extra,state_reason:'completed'}), config, 'owner/one').completed,extra.closed_at)
})
test('GitHub repeated pages, malformed items and later request errors never yield success', async () => {
  await assert.rejects(pullGitHub(config,{scope:'all'},async()=>Array.from({length:100},(_,i)=>issue(i+1))),/stalled/)
  await assert.rejects(pullGitHub(config,{scope:'all'},async()=>[{}]),/Unexpected/)
  await assert.rejects(pullGitHub(config,{scope:'linked',ids:['owner/one#1']},async()=>issue(2)),/different issue/)
  let calls=0
  await assert.rejects(pullGitHub(config,{scope:'all'},async()=>{if(calls++)throw Error('rate limit');return Array.from({length:100},(_,i)=>issue(i+1))}),/rate limit/)
})
test('GitHub HTTP permits only implemented GET routes; authentication and failures are bounded', async () => {
  const calls=[]
  const req=connection('github',config,{GITHUB_TOKEN:'fixture-secret'},async(u,o)=>{calls.push([u,o]);return Response.json([])})
  await req('/repos/owner/one/issues',{state:'all'})
  assert.equal(calls[0][1].method,'GET');assert.equal(calls[0][1].headers.Authorization,'Bearer fixture-secret')
  assert.equal(calls[0][1].headers['X-GitHub-Api-Version'],'2026-03-10');assert.equal(calls[0][1].redirect,'error')
  for (const endpoint of ['/repos/owner/one/issues','/repos/owner/one/issues/1/comments','/graphql']) await assert.rejects(req(endpoint,{},{}),/read-only/)
  for (const endpoint of ['/repos/owner/one/contents/file','/repos/owner/../issues','https://evil.test']) await assert.rejects(req(endpoint),/read-only/)
  assert.equal(calls.length,1)
  const denied=connection('github',config,{GITHUB_TOKEN:'fixture-secret'},async()=>({ok:false,status:403}))
  await assert.rejects(denied('/repos/owner/one/issues'), e=>/HTTP 403/.test(e.message)&&!e.message.includes('fixture-secret'))
})
