import test from 'node:test'
import assert from 'node:assert/strict'
import { canvasConnection, canvasOptions, pullCanvasData, normalizeCanvas, mergeCanvasItems } from '../fieldbook_core/lib/canvas.js'
const instance = { id: 'school', baseUrl: 'https://canvas.example.test', tokenVar: 'CANVAS_TEST_TOKEN', courseIds: ['12'] }
const due = '2026-10-20T23:59:00-04:00', reply = '2026-10-22T23:59:00-04:00'
const assignment = (id, extra = {}) => ({ id, course_id: 12, name: `Coursework ${id}`, due_at: due, unlock_at: null, lock_at: null, ...extra })
const planner = (type, id, extra = {}, plannable = {}) => ({ course_id: 12, context_type: 'Course', plannable_type: type, plannable_id: id, plannable_date: due, plannable: { id, title: `Item ${id}`, ...plannable }, ...extra })
const fixtures = () => ({
  assignments: [assignment(11, { quiz_id: 21 }), assignment(12, { discussion_topic: { id: 22, is_checkpointed: true }, has_sub_assignments: true,
    checkpoints: [{ tag: 'reply_to_topic', due_at: due, unlock_at: null, lock_at: null }, { tag: 'reply_to_entry', due_at: reply, unlock_at: null, lock_at: null }] }), assignment(13, { is_quiz_lti_assignment: true })],
  quizzes: [{ id: 21, title: 'Exam', assignment_id: 11, quiz_type: 'assignment', due_at: due }, { id: 23, title: 'Practice', quiz_type: 'practice_quiz', due_at: due }],
  discussion_topics: [{ id: 22, title: 'Discussion', assignment_id: 12, is_checkpointed: true, reply_to_entry_required_count: 2, todo_date: null }],
  items: [planner('quiz', 21, {}, { assignment_id: 11, due_at: due }), planner('quiz', 23),
    planner('sub_assignment', 71, { html_url: '/courses/12/assignments/12' }, { sub_assignment_tag: 'reply_to_topic' }),
    planner('sub_assignment', 72, { plannable_date: reply, html_url: '/courses/12/assignments/12/submissions/99' }, { sub_assignment_tag: 'reply_to_entry' }),
    planner('wiki_page', 44, {}, { todo_date: '2026-10-19' }), planner('planner_note', 45, {}, { todo_date: '2026-10-18T08:00:00Z' }),
    planner('calendar_event', 46, {}, { start_at: '2026-10-19T10:00:00Z', end_at: '2026-10-19T11:00:00Z', all_day: false }),
    planner('announcement', 47)],
})
async function pull(mode = 'coursework', data = fixtures(), extra = {}, fetchOverride) {
  const calls = []
  const request = canvasConnection(instance, { CANVAS_TEST_TOKEN: 'test-secret' }, async (url, options) => {
    calls.push({ url, options })
    assert.equal(options.method, 'GET'); assert.equal(options.body, undefined); assert.equal(options.redirect, 'error')
    return fetchOverride ? fetchOverride(url, options, calls.length) : new Response(JSON.stringify(data[url.pathname.split('/').at(-1)] ?? []))
  })
  const args = { instance: 'school', mode, ...(['coursework', 'planner'].includes(mode) ? { start: '2026-10-01', end: '2026-10-31' } : {}), ...extra }
  return { result: await pullCanvasData(instance, canvasOptions(args, instance), request), calls }
}
const tagged = (item, type, component = 'main') => item.dates.filter(d => d.type === type && d.component === component)

test('combined coursework collapses quizzes, assignments and checkpoint planner rows by verified IDs', async () => {
  const { result, calls } = await pull()
  assert.equal(result.items.length, 8)
  assert.deepEqual(calls.map(c => c.url.pathname), ['/api/v1/courses/12/assignments', '/api/v1/courses/12/quizzes', '/api/v1/courses/12/discussion_topics', '/api/v1/planner/items'])
  assert.deepEqual(calls[0].url.searchParams.getAll('include[]'), ['checkpoints'])
  const exam = result.items.find(i => i.assignment_id === '11'), discussion = result.items.find(i => i.assignment_id === '12')
  assert.equal(exam.identity, 'canvas:school:course:12:assignment:11')
  assert.deepEqual(exam.sources, ['assignments', 'quizzes', 'planner']); assert.equal(tagged(exam, 'due').length, 1)
  assert.deepEqual(tagged(exam, 'due')[0].sources, ['assignments', 'quizzes', 'planner'])
  assert.equal(discussion.required_replies, 2)
  assert.ok(discussion.aliases.includes('canvas:school:course:12:sub_assignment:71'))
  assert.equal(tagged(discussion, 'due', 'reply_to_topic')[0].at, due)
  assert.equal(tagged(discussion, 'due', 'reply_to_entry')[0].at, reply)
  assert.equal(discussion.needs_identity_review, false)
  assert.equal(discussion.date_conflicts.length, 0)
  assert.ok(result.items.some(i => i.assignment_id === '13' && i.coursework_type === 'quiz'))
  assert.match(result.window_scope, /planner context only/)
})

test('practice quizzes and dated pages/reminders/events keep their own identities and date meanings', async () => {
  const { result } = await pull()
  const practice = result.items.find(i => i.quiz_id === '23'), page = result.items.find(i => i.kind === 'wiki_page'), note = result.items.find(i => i.kind === 'planner_note'), event = result.items.find(i => i.kind === 'event')
  assert.equal(practice.identity, 'canvas:school:course:12:quiz:23'); assert.equal(tagged(practice, 'due')[0].at, due)
  assert.equal(tagged(page, 'todo')[0].at, '2026-10-19'); assert.equal(tagged(page, 'due').length, 0)
  assert.equal(tagged(note, 'todo')[0].at, '2026-10-18T08:00:00Z'); assert.equal(tagged(note, 'due').length, 0)
  assert.equal(tagged(event, 'event_start')[0].at, '2026-10-19T10:00:00Z'); assert.equal(tagged(event, 'due').length, 0)
  assert.equal(tagged(result.items.find(i => i.kind === 'announcement'), 'due').length, 0)
})

test('planner display/creation dates never become page or ungraded discussion deadlines', async () => {
  const data = fixtures(); data.items = [planner('wiki_page', 90), planner('discussion_topic', 91)]
  const { result } = await pull('planner', data)
  assert.equal(result.items.length, 2)
  assert.ok(result.items.every(i => tagged(i, 'due').length === 0 && tagged(i, 'todo').length === 0))
  assert.ok(result.items.every(i => tagged(i, 'planner')[0].at === due))
})

test('standalone modes keep canonical identities, include New Quizzes assignments, and filter enrichment rows', async () => {
  const quiz = await pull('quizzes'), discussion = await pull('discussions'), plannerOnly = await pull('planner')
  assert.equal(quiz.result.items.length, 3)
  assert.equal(quiz.result.items.find(i => i.quiz_id === '21').assignment_id, '11')
  assert.equal(discussion.result.items.length, 1); assert.equal(discussion.result.items[0].assignment_id, '12')
  assert.equal(plannerOnly.result.items.length, 7)
  assert.ok(plannerOnly.result.items.every(i => i.sources.includes('planner')))
})

test('limits count merged output; cross-source duplicates do not consume duplicate slots', async () => {
  const data = fixtures(); data.assignments = [data.assignments[0]]; data.quizzes = [data.quizzes[0]]; data.discussion_topics = []; data.items = [data.items[0]]
  assert.equal((await pull('coursework', data, { limit: 1 })).result.items.length, 1)
  await assert.rejects(pull('coursework', fixtures(), { limit: 1 }), /exceeds 1 items/)
})

test('conflicting and removed effective dates remain visible; equivalent offsets are not conflicts', async () => {
  const data = fixtures(); data.items[0].plannable_date = reply
  const { result } = await pull('coursework', data)
  assert.equal(result.items.find(i => i.assignment_id === '11').date_conflicts[0].field, 'main:due')
  data.items[0].plannable_date = null
  assert.ok((await pull('coursework', data)).result.items.find(i => i.assignment_id === '11').date_conflicts.some(c => c.values.some(v => v.at === null)))
  data.items[0].plannable_date = '2026-10-21T03:59:00Z'
  assert.equal((await pull('coursework', data)).result.items.find(i => i.assignment_id === '11').date_conflicts.length, 0)
})

test('unresolved checkpoint parents, unknown types and missing checkpoint coverage are explicit review items', async () => {
  const data = fixtures(); data.items[2].html_url = 'https://evil.test/courses/12/assignments/12'; data.items.push(planner('future_item', 88))
  data.assignments[1].checkpoints = []
  const { result } = await pull('coursework', data)
  assert.equal(result.items.find(i => i.kind === 'sub_assignment').needs_identity_review, true)
  assert.equal(result.items.find(i => i.kind === 'future_item').needs_identity_review, true)
  assert.match(result.items.find(i => i.assignment_id === '12').warnings.join(' '), /both discussion checkpoint/)
})

test('assignment links cannot merge two different assignments or two different quizzes', async () => {
  const data = fixtures(); data.quizzes[0].assignment_id = 13
  await assert.rejects(pull('coursework', data), /conflicting assignments/)
  data.quizzes[0].assignment_id = 11; data.quizzes.push({ id: 24, title: 'Other', assignment_id: 11 })
  await assert.rejects(pull('coursework', data), /Conflicting Canvas/)
})

test('same titles and numeric IDs across schools and courses remain separate', () => {
  const records = [normalizeCanvas(assignment(11), instance, 'assignments', ['12'], '12'), normalizeCanvas(assignment(11, { course_id: 34 }), instance, 'assignments', ['34'], '34'), normalizeCanvas(assignment(11), { ...instance, id: 'second' }, 'assignments', ['12'], '12')]
  assert.equal(mergeCanvasItems(records).length, 3)
})

test('planner shape/course/tag errors reject the entire result and incidental personal data is stripped', async () => {
  for (const change of [r => { r.course_id = 99 }, r => { r.plannable.course_id = 99 }, r => { r.plannable.id = 99 }, r => { r.plannable_date = 'tomorrow' }]) {
    const data = fixtures(); change(data.items[0]); await assert.rejects(pull('coursework', data), /Canvas/)
  }
  const data = fixtures(); data.items[0].submissions = { score: 'PRIVATE', feedback: { comment: 'PRIVATE' } }; data.items[0].planner_override = { marked_complete: true, user_id: 'PRIVATE' }; data.quizzes[0].access_code = 'PRIVATE'; data.discussion_topics[0].participants = ['PRIVATE']
  data.assignments[1].checkpoints[0].overrides = [{ student_ids: ['PRIVATE'] }]
  assert.ok(!JSON.stringify((await pull('coursework', data)).result).includes('PRIVATE'))
  data.assignments[1].checkpoints[0].tag = 'unknown'
  await assert.rejects(pull('coursework', data), /checkpoint tag/)
})

test('planner pagination uses typed object IDs, accepts distinct pages and rejects repeats', async () => {
  let page = 0
  const { result } = await pull('planner', {}, {}, url => {
    if (!url.pathname.endsWith('/items')) return new Response('[]')
    const next = new URL(url); next.searchParams.set('page', '2')
    return new Response(JSON.stringify([planner('wiki_page', ++page)]), { headers: page === 1 ? { Link: `<${next}>; rel="next"` } : {} })
  })
  assert.equal(result.items.length, 2)
  await assert.rejects(pull('planner', {}, {}, url => {
    if (!url.pathname.endsWith('/items')) return new Response('[]')
    const next = new URL(url); next.searchParams.set('page', '2')
    return new Response(JSON.stringify([planner('wiki_page', 1)]), { headers: { Link: `<${next}>; rel="next"` } })
  }), /repeated|stalled/)
})

test('new GET routes reject widened scopes, impersonation, replies, writes and arbitrary includes', async () => {
  let calls = 0
  const read = canvasConnection(instance, { CANVAS_TEST_TOKEN: 'fixture' }, async () => { calls++; return new Response('[]') })
  const q = { 'context_codes[]': ['course_12'], start_date: '2026-10-01', end_date: '2026-10-31', per_page: 50 }
  for (const path of ['/api/v1/planner_notes', '/api/v1/planner/overrides', '/api/v1/users/99/planner/items', '/api/v1/courses/12/discussion_topics/22/entries', '/api/v1/courses/12/quizzes/21/questions']) await assert.rejects(read(path, q, () => {}), /allowlisted/)
  for (const query of [{ ...q, observed_user_id: '99' }, { ...q, 'context_codes[]': ['user_99'] }, { ...q, filter: 'incomplete_items' }]) await assert.rejects(read('/api/v1/planner/items', query, () => {}))
  await assert.rejects(read('/api/v1/courses/12/assignments', { override_assignment_dates: true, per_page: 50, 'include[]': ['submission'] }, () => {}))
  assert.equal(calls, 0)
})

test('a failed planner/discussion page aborts the combined preview without partial success', async () => {
  await assert.rejects(pull('coursework', {}, {}, url => new Response(url.pathname.endsWith('/items') ? 'denied' : '[]', { status: url.pathname.endsWith('/items') ? 403 : 200 })), /HTTP 403.*No partial/)
})

test('planner windows and quiz/discussion scopes are validated before requesting data', () => {
  for (const mode of ['planner', 'coursework']) assert.throws(() => canvasOptions({ instance: 'school', mode }, instance), /dates/)
  for (const mode of ['quizzes', 'discussions']) assert.throws(() => canvasOptions({ instance: 'school', mode, start: '2026-10-01' }, instance), /start\/end/)
})
