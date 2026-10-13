import test from 'node:test'
import assert from 'node:assert/strict'
import { canvasConnection, canvasOptions, pullCanvasData, normalizeCanvas } from '../fieldbook_core/lib/canvas.js'
const instance = { id: 'school', baseUrl: 'https://canvas.example.test', tokenVar: 'CANVAS_TEST_TOKEN', courseIds: ['12', '34'] }
const env = { CANVAS_TEST_TOKEN: 'fixture-secret' }
const response = (value, link, extra = {}) => new Response(JSON.stringify(value), { headers: { 'Content-Type': 'application/json', ...(link ? { Link: link } : {}), ...extra } })
const assignment = (id, course = '12', extra = {}) => ({ id, course_id: course, name: `Assignment ${id}`, description: '<p>Source text only</p>', due_at: '2026-10-20T23:59:00-04:00', unlock_at: null, lock_at: null, html_url: `https://canvas.example.test/courses/${course}/assignments/${id}`, ...extra })
const query = { enrollment_state: 'active', per_page: 50 }
const course = id => ({ id, name: `Course ${id}`, course_code: 'C101', time_zone: 'America/New_York' })

test('courses GET uses current-user active enrollments and follows short pages with Link headers', async () => {
  const calls = []
  const request = canvasConnection(instance, env, async (url, options) => {
    calls.push([url, options])
    const next = new URL(url); next.searchParams.set('page', 'opaque:two')
    return calls.length === 1 ? response([course(12)], `<${next}>; rel="next"`) : response([course(34)])
  })
  const result = await pullCanvasData(instance, canvasOptions({ instance: 'school', mode: 'courses' }, instance), request)
  assert.deepEqual(result.items.map(v => v.id), ['12', '34'])
  assert.equal(calls[1][0].searchParams.get('page'), 'opaque:two')
  assert.ok(calls.every(([, options]) => options.method === 'GET' && options.redirect === 'error' && options.body === undefined))
  assert.equal(calls[0][1].headers.Authorization, 'Bearer fixture-secret')
  assert.equal(result.read_only, true)
  assert.equal(result.truncated, false)
})

test('assignments preserve user-effective exact deadlines/nulls and instance/course identity', async () => {
  const calls = []
  const request = canvasConnection(instance, env, async url => {
    calls.push(url)
    return response([assignment(1, url.pathname.split('/')[4], { due_at: url.pathname.includes('/34/') ? null : '2026-10-20T23:59:00-04:00', submission: { grade: 'private' }, assignment_overrides: [{ student_ids: [99] }] })])
  })
  const result = await pullCanvasData(instance, canvasOptions({ instance: 'school', mode: 'assignments' }, instance), request)
  assert.equal(result.items[0].due_at, '2026-10-20T23:59:00-04:00')
  assert.equal(result.items[1].due_at, null)
  assert.notEqual(result.items[0].identity, result.items[1].identity)
  assert.ok(calls.every(url => url.searchParams.get('override_assignment_dates') === 'true'))
  assert.ok(result.items.every(v => !('submission' in v) && !('assignment_overrides' in v)))
  const alternate = normalizeCanvas(assignment(1), { ...instance, id: 'other' }, 'assignments', ['12'], '12')
  assert.notEqual(result.items[0].identity, alternate.identity)
})

test('announcements and calendar enforce selected courses and explicit bounded windows', async () => {
  const calls = []
  for (const mode of ['announcements', 'calendar']) {
    const request = canvasConnection(instance, env, async url => {
      calls.push(url)
      return response([{ id: 1, title: 'Class', context_code: mode === 'calendar' ? 'course_section_4' : 'course_12', effective_context_code: 'course_12',
        posted_at: '2026-10-20T09:00:00Z', start_at: '2026-10-20T10:00:00Z', end_at: '2026-10-20T11:00:00Z', all_day: false, all_day_date: '2026-10-20',
        user: { name: 'Private reservation' }, child_events: [{ user: { id: 9 } }] }])
    })
    const result = await pullCanvasData(instance, canvasOptions({ instance: 'school', mode, start: '2026-10-01', end: '2026-10-31' }, instance), request)
    assert.equal(result.items[0].course_id, '12')
    assert.ok(!JSON.stringify(result).includes('Private reservation'))
  }
  assert.deepEqual(calls[0].searchParams.getAll('context_codes[]'), ['course_12', 'course_34'])
  assert.equal(calls[0].searchParams.get('active_only'), 'true')
  assert.equal(calls[1].searchParams.get('type'), 'event')
  assert.deepEqual(calls[1].searchParams.getAll('excludes[]'), ['child_events', 'assignment'])
})

test('empty selection, excessive course/window/limit and unknown arguments fail before reads', () => {
  const cases = [
    { instance: 'school', mode: 'assignments', courseIds: [] },
    { instance: 'school', mode: 'assignments', courseIds: Array(11).fill('1') },
    { instance: 'school', mode: 'assignments', courseIds: ['12/assignments'] },
    { instance: 'school', mode: 'calendar', start: '2026-01-01', end: '2026-12-31' },
    { instance: 'school', mode: 'calendar', start: '2026-02-30', end: '2026-03-01' },
    { instance: 'school', mode: 'calendar' },
    { instance: 'school', mode: 'courses', courseIds: ['12'] },
    { instance: 'school', mode: 'courses', userId: '99' },
    { instance: 'school', mode: 'courses', limit: 501 },
  ]
  for (const args of cases) assert.throws(() => canvasOptions(args, instance))
})

test('transport refuses mutation routes, arbitrary query filters and impersonation', async () => {
  let reads = 0
  const request = canvasConnection(instance, env, async () => { reads++; return response([]) })
  for (const endpoint of ['/api/v1/users/99/calendar_events', '/api/v1/courses/12/users', '/api/v1/courses/12/assignments/1/submissions', '/api/v1/courses/12/assignments/1', 'https://evil.test/api/v1/courses']) await assert.rejects(request(endpoint, query, () => {}), /allowlisted/)
  for (const params of [{ ...query, as_user_id: '99' }, { ...query, 'include[]': 'total_scores' }, { ...query, enrollment_state: 'all' }]) await assert.rejects(request('/api/v1/courses', params, () => {}))
  await assert.rejects(request('/api/v1/calendar_events', { 'context_codes[]': ['user_99'], start_date: '2026-10-01', end_date: '2026-10-31', per_page: 50, type: 'event', 'excludes[]': ['child_events', 'assignment'] }, () => {}), /course contexts/)
  assert.equal(reads, 0)
})

test('HTTPS origin and safe credential references are required', () => {
  for (const baseUrl of ['http://canvas.example.test', 'https://user:pass@canvas.example.test', 'https://canvas.example.test/canvas', 'https://canvas.example.test?token=1']) assert.throws(() => canvasConnection({ ...instance, baseUrl }, env), /HTTPS/)
  assert.throws(() => canvasConnection({ ...instance, tokenVar: 'OTHER_TOKEN' }, env), /CANVAS_/)
  assert.throws(() => canvasConnection(instance, {}), /not set/)
  assert.throws(() => canvasConnection(instance, { CANVAS_TEST_TOKEN: 'bad\nheader' }), /valid access token/)
})

test('hostile pagination origin, route, credentials and expanded scope never receive a request', async () => {
  const paths = [
    'https://evil.test/api/v1/courses?enrollment_state=active&per_page=50&page=2',
    'https://canvas.example.test/api/v1/users/99?enrollment_state=active&per_page=50&page=2',
    'https://user:pass@canvas.example.test/api/v1/courses?enrollment_state=active&per_page=50&page=2',
    'https://canvas.example.test/api/v1/courses?enrollment_state=active&per_page=50&page=2&as_user_id=99',
    'https://canvas.example.test/api/v1/courses?enrollment_state=all&per_page=50&page=2',
    '/api/v1/courses?page=2',
  ]
  for (const next of paths) {
    let reads = 0, consumed = 0
    const request = canvasConnection(instance, env, async () => { reads++; return response([course(12)], `<${next}>; rel="next"`) })
    await assert.rejects(request('/api/v1/courses', query, () => { consumed++ }))
    assert.equal(reads, 1); assert.equal(consumed, 0)
  }
})

test('repeated, empty, and cyclic pagination never reports partial success', async () => {
  for (const kind of ['repeated', 'empty', 'cycle']) {
    let reads = 0
    const request = canvasConnection(instance, env, async url => {
      reads++
      const next = new URL(url); next.searchParams.set('page', kind === 'cycle' ? '1' : String(reads + 1))
      return response(kind === 'empty' ? [] : [course(12)], `<${next}>; rel="next"`)
    })
    await assert.rejects(pullCanvasData(instance, canvasOptions({ instance: 'school', mode: 'courses' }, instance), request), /pagination|repeated/)
    assert.ok(reads <= 2)
  }
})

test('HTTP/network/invalid JSON failures are sanitized and fail the whole pull', async () => {
  const failures = [async () => new Response('fixture-secret', { status: 401 }), async () => { throw Error('fixture-secret') }, async () => new Response('fixture-secret')]
  for (const fetcher of failures) {
    const request = canvasConnection(instance, env, fetcher)
    await assert.rejects(request('/api/v1/courses', query, () => {}), error => !error.message.includes('fixture-secret') && /Canvas/.test(error.message))
  }
  let reads = 0
  const request = canvasConnection(instance, env, async url => {
    if (reads++) throw Error('offline')
    const next = new URL(url); next.searchParams.set('page', '2')
    return response([course(12)], `<${next}>; rel="next"`)
  })
  await assert.rejects(pullCanvasData(instance, canvasOptions({ instance: 'school', mode: 'courses' }, instance), request), /no partial/)
})

test('record and response caps reject instead of presenting incomplete course work', async () => {
  const capped = canvasConnection(instance, env, async () => response([course(1), course(2)]))
  await assert.rejects(pullCanvasData(instance, canvasOptions({ instance: 'school', mode: 'courses', limit: 1 }, instance), capped), /exceeds 1 items/)
  const huge = canvasConnection(instance, env, async () => response([], null, { 'Content-Length': String(2 * 1024 * 1024 + 1) }))
  await assert.rejects(huge('/api/v1/courses', query, () => {}), /size\/JSON limits/)
  const streaming = canvasConnection(instance, env, async () => new Response(' '.repeat(2 * 1024 * 1024 + 1)))
  await assert.rejects(streaming('/api/v1/courses', query, () => {}), /size\/JSON limits/)
})

test('schema drift and cross-course results fail; descriptions are bounded with disclosure', () => {
  assert.throws(() => normalizeCanvas(assignment(1, '34'), instance, 'assignments', ['12'], '12'), /another course/)
  assert.throws(() => normalizeCanvas({ id: 1, title: 'Bad', context_code: 'course_99' }, instance, 'announcements', ['12']), /context/)
  assert.throws(() => normalizeCanvas(assignment(1, '12', { due_at: '2026-02-30T12:00:00Z' }), instance, 'assignments', ['12'], '12'), /dates/)
  const item = normalizeCanvas(assignment(1, '12', { description: 'x'.repeat(5000), html_url: 'javascript:alert(1)' }), instance, 'assignments', ['12'], '12')
  assert.equal(item.description_html.length, 4096); assert.equal(item.description_truncated, true); assert.equal(item.url, '')
})

test('duplicate calendar context codes do not create ambiguity for the same course', () => {
  const item = normalizeCanvas({ id: 1, title: 'Class', context_code: 'course_12', effective_context_code: 'course_12' }, instance, 'calendar', ['12'])
  assert.equal(item.course_id, '12')
})

test('pagination requires all context filters and rejects malformed or duplicate next links', async () => {
  const base = 'https://canvas.example.test/api/v1/courses?enrollment_state=active&per_page=50&page=2'
  for (const link of [`<${base}>; rel="next", <${base}>; rel="next"`, `<${base}>`, 'garbage']) {
    const request = canvasConnection(instance, env, async () => response([course(1)], link))
    await assert.rejects(request('/api/v1/courses', query, () => {}), /pagination/)
  }
  const announcementQuery = { 'context_codes[]': ['course_12'], start_date: '2026-10-01', end_date: '2026-10-31', per_page: 50, active_only: true }
  const request = canvasConnection(instance, env, async url => {
    const next = new URL(url); next.searchParams.delete('context_codes[]'); next.searchParams.set('page', '2')
    return response([{ id: 1, title: 'Notice', context_code: 'course_12' }], `<${next}>; rel="next"`)
  })
  await assert.rejects(request('/api/v1/announcements', announcementQuery, () => {}), /selected scope/)
})

test('total preview and request-count limits terminate a continuing selection', async () => {
  let reads = 0
  const many = canvasConnection(instance, env, async url => {
    const next = new URL(url); next.searchParams.set('page', String(++reads + 1))
    return response(Array.from({ length: 100 }, (_, index) => assignment((reads - 1) * 100 + index + 1, '12', { description: 'x'.repeat(4096) })), reads < 5 ? `<${next}>; rel="next"` : undefined)
  })
  await assert.rejects(pullCanvasData(instance, canvasOptions({ instance: 'school', mode: 'assignments', courseIds: ['12'], limit: 500 }, instance), many), /preview exceeds 2 MiB/)
  reads = 0
  const forever = canvasConnection(instance, env, async url => {
    const next = new URL(url); next.searchParams.set('page', String(++reads + 1))
    return response([course(reads)], `<${next}>; rel="next"`)
  })
  await assert.rejects(pullCanvasData(instance, canvasOptions({ instance: 'school', mode: 'courses', limit: 500 }, instance), forever), /100 requests/)
  assert.equal(reads, 100)
})
