// Canvas LMS metadata reads only. No arbitrary routes, impersonation or mutations.
const MODES = new Set(['courses', 'assignments', 'quizzes', 'discussions', 'planner', 'coursework', 'announcements', 'calendar'])
const MAX_RESPONSE = 2 * 1024 * 1024
const MAX_TOTAL = 8 * 1024 * 1024
const MAX_PAGES = 100
const idPattern = /^[1-9]\d{0,15}$/
export function canvasId(value, label = 'Canvas ID') {
  if ((typeof value !== 'string' && typeof value !== 'number') || !idPattern.test(String(value)) || !Number.isSafeInteger(Number(value))) throw new Error(`${label} must be a positive integer ID`)
  return String(value)
}
function instanceId(value) {
  if (typeof value !== 'string' || !/^[A-Za-z0-9][A-Za-z0-9_-]{0,63}$/.test(value)) throw new Error('Canvas instance must be a short configured ID')
  return value
}
function date(value) {
  if (typeof value !== 'string' || !/^\d{4}-\d{2}-\d{2}$/.test(value) || !Number.isFinite(Date.parse(value)) || new Date(value).toISOString().slice(0, 10) !== value) throw new Error('Canvas dates must use valid YYYY-MM-DD values')
  return value
}
export function canvasOptions(args, instance) {
  if (!args || typeof args !== 'object' || Array.isArray(args) || Object.keys(args).some(k => !['instance', 'mode', 'courseIds', 'start', 'end', 'limit'].includes(k))) throw new Error('Unsupported Canvas arguments')
  instanceId(args.instance)
  if (!MODES.has(args.mode)) throw new Error('Choose courses, assignments, quizzes, discussions, planner, coursework, announcements, or calendar')
  const limit = args.limit ?? 200
  if (!Number.isInteger(limit) || limit < 1 || limit > 500) throw new Error('Canvas limit must be 1..500')
  if (args.mode === 'courses') {
    if (args.courseIds !== undefined || args.start !== undefined || args.end !== undefined) throw new Error('Courses mode lists your active enrollments; courseIds and dates apply to other modes')
    return { mode: args.mode, limit, courseIds: [] }
  }
  const selected = args.courseIds ?? instance.courseIds
  if (!Array.isArray(selected) || !selected.length || selected.length > 10) throw new Error('Choose 1..10 explicit or configured Canvas courseIds; use courses mode to discover IDs')
  const courseIds = [...new Set(selected.map(id => canvasId(id, 'Course ID')))]
  if (['assignments', 'quizzes', 'discussions'].includes(args.mode)) {
    if (args.start !== undefined || args.end !== undefined) throw new Error('Course lists return all accessible items; start/end apply to planner, coursework planner context, announcements and calendar')
    return { mode: args.mode, limit, courseIds }
  }
  const start = date(args.start), end = date(args.end)
  if (end < start || (Date.parse(end) - Date.parse(start)) / 86400000 > 92) throw new Error('Choose an inclusive Canvas date window of at most 93 days')
  return { mode: args.mode, limit, courseIds, start, end }
}
function baseURL(instance) {
  instanceId(instance.id)
  let base
  try { base = new URL(instance.baseUrl) } catch { throw new Error('Configure a valid Canvas HTTPS baseUrl') }
  if (base.protocol !== 'https:' || base.username || base.password || base.search || base.hash || !['', '/'].includes(base.pathname)) throw new Error('Canvas baseUrl must be an HTTPS origin without a path, credentials, query or fragment')
  return base
}
function nextLink(header) {
  if (!header) return null
  if (header.length > 16384) throw new Error('Canvas pagination header exceeds its limit')
  const links = []
  // Canvas documents absolute Link URLs; commas inside <...> are not separators.
  const pattern = /<([^<>]+)>\s*((?:;\s*[^,]+)*)(?:,|$)/g
  let match, end = 0
  while ((match = pattern.exec(header))) {
    if (header.slice(end, match.index).trim()) throw new Error('Malformed Canvas pagination header')
    const relation = match[2].match(/;\s*rel\s*=\s*(?:"([^"]+)"|([^;\s,]+))/i)
    if (!relation) throw new Error('Canvas pagination link lacks rel')
    if ((relation[1] || relation[2]).split(/\s+/).includes('next')) links.push(match[1])
    end = pattern.lastIndex
  }
  if (!end || header.slice(end).trim() || links.length > 1) throw new Error('Malformed or ambiguous Canvas pagination header')
  return links[0] || null
}
function queryScope(url, first) {
  if (url.origin !== first.origin || ![first.pathname, first.pathname + '.json'].includes(url.pathname) || url.username || url.password || url.hash) throw new Error('Canvas pagination changed the origin or read route')
  const initial = new Set(first.searchParams.keys())
  for (const key of new Set(url.searchParams.keys())) if (!initial.has(key) && !['page', 'per_page'].includes(key)) throw new Error('Canvas pagination added an unsupported query parameter')
  for (const key of initial) {
    if (key === 'page' || key === 'per_page') continue
    if (JSON.stringify(url.searchParams.getAll(key).sort()) !== JSON.stringify(first.searchParams.getAll(key).sort())) throw new Error('Canvas pagination changed the selected scope')
  }
  if (url.searchParams.getAll('page').length > 1 || url.searchParams.getAll('per_page').length > 1) throw new Error('Ambiguous Canvas pagination parameters')
  const page = url.searchParams.get('page'), perPage = url.searchParams.get('per_page')
  if (page !== null && (!page || page.length > 2048)) throw new Error('Invalid Canvas page token')
  if (perPage !== null && (!/^\d+$/.test(perPage) || Number(perPage) < 1 || Number(perPage) > 100)) throw new Error('Canvas pagination page size exceeds its bound')
}
function initialQuery(endpoint, query) {
  if (!query || typeof query !== 'object' || Array.isArray(query)) throw new Error('Invalid Canvas query')
  const mode = endpoint === '/api/v1/courses' ? 'courses' : endpoint.endsWith('/assignments') ? 'assignments' : endpoint.endsWith('/quizzes') ? 'quizzes' : endpoint.endsWith('/discussion_topics') ? 'discussions' : endpoint === '/api/v1/planner/items' ? 'planner' : endpoint === '/api/v1/announcements' ? 'announcements' : 'calendar'
  const keys = mode === 'courses' ? ['enrollment_state', 'per_page'] : mode === 'assignments' ? ['override_assignment_dates', 'per_page', 'include[]'] : ['quizzes', 'discussions'].includes(mode) ? ['per_page'] : mode === 'planner' ? ['context_codes[]', 'start_date', 'end_date', 'per_page'] : mode === 'announcements' ? ['context_codes[]', 'start_date', 'end_date', 'per_page', 'active_only'] : ['context_codes[]', 'start_date', 'end_date', 'per_page', 'type', 'excludes[]']
  if (Object.keys(query).some(k => !keys.includes(k)) || keys.some(k => !(k in query))) throw new Error('Only allowlisted Canvas query parameters are permitted; impersonation is unavailable')
  if (!Number.isInteger(query.per_page) || query.per_page < 1 || query.per_page > 100) throw new Error('Invalid Canvas page size')
  if (mode === 'courses' && query.enrollment_state !== 'active' || mode === 'assignments' && query.override_assignment_dates !== true || mode === 'announcements' && query.active_only !== true) throw new Error('Canvas query must retain its active/current-user scope')
  if (mode === 'assignments' && JSON.stringify(query['include[]']) !== '["checkpoints"]') throw new Error('Canvas assignments include checkpoint dates only')
  if (['calendar', 'announcements', 'planner'].includes(mode)) {
    const contexts = query['context_codes[]']
    if (!Array.isArray(contexts) || !contexts.length || contexts.length > 10 || contexts.some(c => typeof c !== 'string' || !/^course_[1-9]\d{0,15}$/.test(c))) throw new Error('Canvas reads require selected course contexts only')
    contexts.forEach(c => canvasId(c.slice(7)))
    const start = date(query.start_date), end = date(query.end_date)
    if (end < start || (Date.parse(end) - Date.parse(start)) / 86400000 > 92) throw new Error('Canvas date window exceeds 93 days')
    if (mode === 'calendar' && (query.type !== 'event' || JSON.stringify(query['excludes[]']) !== '["child_events","assignment"]')) throw new Error('Canvas calendar reads omit assignments and child-event rosters')
  }
}
async function boundedJSON(response) {
  const declared = response.headers?.get('content-length')
  if (declared && (!/^\d+$/.test(declared) || Number(declared) > MAX_RESPONSE)) throw new Error('Canvas response exceeds 2 MiB')
  if (!response.body?.getReader) throw new Error('Canvas response has no bounded readable body')
  const reader = response.body.getReader(), chunks = []
  let size = 0
  try {
    for (;;) {
      const { value, done } = await reader.read()
      if (done) break
      size += value.byteLength
      if (size > MAX_RESPONSE) { await reader.cancel(); throw new Error('Canvas response exceeds 2 MiB') }
      chunks.push(value)
    }
  } finally { reader.releaseLock() }
  let data
  try { data = JSON.parse(Buffer.concat(chunks, size).toString('utf8').replace(/^\uFEFF/, '')) } catch { throw new Error('Canvas returned invalid JSON; no partial result returned') }
  if (!Array.isArray(data)) throw new Error('Canvas must return a list; no partial result returned')
  return { data, size }
}
export function validateCanvasInstance(instance) {
  const base = baseURL(instance)
  if (typeof instance.tokenVar !== 'string' || !/^CANVAS_[A-Z0-9_]+$/.test(instance.tokenVar)) throw new Error('Canvas tokenVar must start with CANVAS_')
  if (!['environment', 'keyring'].includes(instance.credentialStore || 'environment')) throw new Error('credentialStore must be environment or keyring')
  return base
}
export function canvasConnection(instance, env = process.env, fetcher = fetch, signal) {
  const base = validateCanvasInstance(instance)
  const token = env[instance.tokenVar]
  if (typeof token !== 'string' || !token || token.length > 16384 || /[\x00-\x20\x7f]/.test(token)) throw new Error(`${instance.tokenVar} is not set to a valid access token`)
  let requests = 0, totalBytes = 0
  return async function requestPages(endpoint, query, consume) {
    if (!['/api/v1/courses', '/api/v1/announcements', '/api/v1/calendar_events', '/api/v1/planner/items'].includes(endpoint) && !/^\/api\/v1\/courses\/[1-9]\d{0,15}\/(?:assignments|quizzes|discussion_topics)$/.test(endpoint)) throw new Error('Only allowlisted read-only Canvas endpoints are permitted')
    initialQuery(endpoint, query)
    const first = new URL(endpoint, base)
    for (const [key, raw] of Object.entries(query)) for (const value of Array.isArray(raw) ? raw : [raw]) first.searchParams.append(key, String(value))
    const seenURLs = new Set(), seenPages = new Set()
    let url = first
    for (;;) {
      queryScope(url, first)
      if (seenURLs.has(url.href) || ++requests > MAX_PAGES) throw new Error('Canvas pagination stalled or exceeded 100 requests; narrow the selection')
      seenURLs.add(url.href)
      let response
      try {
        response = await fetcher(url, { method: 'GET', redirect: 'error', signal: signal ? AbortSignal.any([signal, AbortSignal.timeout(30000)]) : AbortSignal.timeout(30000), headers: { Authorization: `Bearer ${token}`, Accept: 'application/json' } })
      } catch { throw new Error('Canvas request failed (network, timeout or redirect); no partial result returned') }
      if (!response.ok) throw new Error(`Canvas HTTP ${response.status}; check access or retry later. No partial result returned.`)
      if (response.url) queryScope(new URL(response.url), first)
      const next = nextLink(response.headers?.get('link'))
      let nextURL = null
      if (next) {
        try { nextURL = new URL(next) } catch { throw new Error('Canvas pagination URL must be absolute') }
        queryScope(nextURL, first) // Validate before returning even the first page's data.
      }
      let result
      try { result = await boundedJSON(response) } catch { throw new Error('Canvas response could not be read within its size/JSON limits; no partial result returned') }
      totalBytes += result.size
      if (totalBytes > MAX_TOTAL) throw new Error('Canvas selection exceeds 8 MiB; narrow it. No partial result returned.')
      const signature = JSON.stringify(result.data.map(item => endpoint === '/api/v1/planner/items' ? [item?.course_id, item?.plannable_type, item?.plannable_id] : item?.id))
      if (next && !result.data.length || result.data.length && seenPages.has(signature)) throw new Error('Canvas pagination returned an empty/repeated page; no partial result returned')
      seenPages.add(signature)
      consume(result.data)
      if (!nextURL) return
      url = nextURL
    }
  }
}
function text(value, field, limit = 4096, optional = true) {
  if (value == null && optional) return ''
  if (typeof value !== 'string') throw new Error(`Unexpected Canvas ${field}; no partial result returned`)
  return value.slice(0, limit)
}
function timestamp(value, field) {
  if (value == null) return null
  if (typeof value !== 'string' || !/^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+-]\d{2}:\d{2})$/.test(value) || !Number.isFinite(Date.parse(value))) throw new Error(`Unexpected Canvas ${field} timestamp; no partial result returned`)
  date(value.slice(0, 10))
  return value // Preserve the API's full deadline and offset; never truncate to a date.
}
function url(value, instance) {
  if (!value) return ''
  try { const parsed = new URL(value, baseURL(instance)); if (parsed.origin !== baseURL(instance).origin || parsed.protocol !== 'https:' || parsed.username || parsed.password) return ''; return parsed.href.slice(0, 2048) } catch { return '' }
}
function courseContext(record, selected, calendar = false) {
  const candidates = [record.context_code, ...(calendar ? [record.effective_context_code] : [])]
  const contexts = candidates.filter(v => typeof v === 'string' && /^course_[1-9]\d*$/.test(v)).map(v => v.slice(7))
  const matching = [...new Set(contexts.filter(id => selected.includes(id)))]
  if (matching.length !== 1) throw new Error('Canvas returned an unexpected or ambiguous course context; no partial result returned')
  return matching[0]
}

const CHECKPOINTS = new Set(['reply_to_topic', 'reply_to_entry'])
const PLANNER_TYPES = new Set(['assignment', 'quiz', 'discussion_topic', 'wiki_page', 'planner_note', 'calendar_event', 'announcement', 'sub_assignment', 'peer_review_sub_assignment', 'assessment_request'])
const identityFor = (instance, course, kind, id) => `canvas:${instance.id}:course:${course}:${kind}:${canvasId(id)}`
const optionalId = (value, label) => value == null ? null : canvasId(value, label)
function object(value, label) {
  if (!value || typeof value !== 'object' || Array.isArray(value)) throw new Error(`Unexpected Canvas ${label}; no partial result returned`)
  return value
}
function dateValue(value, label) {
  return typeof value === 'string' && /^\d{4}-\d{2}-\d{2}$/.test(value) ? date(value) : timestamp(value, label)
}
function dated(item, type, value, source, component = 'main') {
  if (value === undefined) return
  // Null is retained: a removed/unknown source date needs review, never an invented deadline.
  item.dates.push({ type, component, at: dateValue(value, type), sources: [source] })
}
function baseItem(instance, course, kind, id, title, source, htmlURL) {
  const identity = identityFor(instance, course, kind, id)
  return { provider: 'canvas', instance: instance.id, course_id: course, kind, id: canvasId(id), identity,
    aliases: [identity], sources: [source], title: text(title, 'title', 1024, false), url: url(htmlURL, instance),
    dates: [], checkpoint_tags: [], warnings: [] }
}
function description(item, value) {
  item.description_html = text(value, 'description')
  item.description_truncated = (value?.length || 0) > item.description_html.length
}
function courseworkDates(item, record, source, component = 'main') {
  for (const [field, type] of [['due_at', 'due'], ['unlock_at', 'available_from'], ['lock_at', 'closes_at']]) {
    const value = timestamp(record[field], field)
    if (component === 'main') item[field] = value
    dated(item, type, record[field], source, component)
  }
}
function checkpoints(item, record, source) {
  item.has_checkpoints = record.has_sub_assignments === true || record.is_checkpointed === true
  if (record.checkpoints == null) return
  if (!Array.isArray(record.checkpoints) || record.checkpoints.length > 2) throw new Error('Unexpected Canvas discussion checkpoints; no partial result returned')
  for (const value of record.checkpoints) {
    const checkpoint = object(value, 'checkpoint')
    if (!CHECKPOINTS.has(checkpoint.tag) || item.checkpoint_tags.includes(checkpoint.tag)) throw new Error('Unknown or repeated Canvas checkpoint tag; no partial result returned')
    item.checkpoint_tags.push(checkpoint.tag)
    courseworkDates(item, checkpoint, source, checkpoint.tag)
  }
  item.has_checkpoints ||= item.checkpoint_tags.length > 0
}
function checkCourse(record, course) {
  if (record.course_id != null && canvasId(record.course_id) !== course) throw new Error('Canvas returned an item from another course; no partial result returned')
}
function normalizeAssignment(record, instance, course) {
  if (canvasId(record.course_id, 'Assignment course ID') !== course) throw new Error('Canvas returned an assignment from another course; no partial result returned')
  const item = baseItem(instance, course, 'assignment', record.id, record.name, 'assignments', record.html_url)
  item.assignment_id = item.id
  item.quiz_id = optionalId(record.quiz_id, 'Quiz ID')
  item.discussion_id = optionalId(record.discussion_topic?.id, 'Discussion ID')
  if (item.quiz_id) item.aliases.push(identityFor(instance, course, 'quiz', item.quiz_id))
  if (item.discussion_id) item.aliases.push(identityFor(instance, course, 'discussion_topic', item.discussion_id))
  description(item, record.description)
  courseworkDates(item, record, 'assignments')
  checkpoints(item, record, 'assignments')
  item.has_checkpoints ||= record.discussion_topic?.is_checkpointed === true
  item.due_scope = 'Canvas assignment overrides applied for the current account; confirm the account is the intended student.'
  item.published = typeof record.published === 'boolean' ? record.published : null
  item.status = text(record.workflow_state, 'assignment status', 64)
  item.coursework_type = item.discussion_id ? 'discussion' : item.quiz_id || record.is_quiz_lti_assignment === true || record.is_quiz_assignment === true ? 'quiz' : 'assignment'
  return item
}
function normalizeQuiz(record, instance, course) {
  checkCourse(record, course)
  const item = baseItem(instance, course, 'quiz', record.id, record.title, 'quizzes', record.html_url)
  item.quiz_id = item.id
  item.assignment_id = optionalId(record.assignment_id, 'Quiz assignment ID')
  if (item.assignment_id) item.aliases.push(identityFor(instance, course, 'assignment', item.assignment_id))
  item.quiz_type = text(record.quiz_type, 'quiz type', 64)
  item.needs_identity_review = ['assignment', 'graded_survey'].includes(item.quiz_type) && !item.assignment_id
  item.coursework_type = 'quiz'
  description(item, record.description)
  courseworkDates(item, record, 'quizzes')
  return item
}
function normalizeDiscussion(record, instance, course) {
  checkCourse(record, course)
  const item = baseItem(instance, course, 'discussion_topic', record.id, record.title, 'discussions', record.html_url)
  item.discussion_id = item.id
  item.assignment_id = optionalId(record.assignment_id, 'Discussion assignment ID')
  if (item.assignment_id) item.aliases.push(identityFor(instance, course, 'assignment', item.assignment_id))
  item.coursework_type = 'discussion'
  // Only topic metadata. Never return author, participants, attachments or replies.
  dated(item, 'todo', record.todo_date, 'discussions')
  dated(item, 'available_from', record.delayed_post_at, 'discussions')
  dated(item, 'closes_at', record.lock_at, 'discussions')
  item.has_checkpoints = record.is_checkpointed === true
  const count = record.reply_to_entry_required_count
  if (count != null && (!Number.isInteger(count) || count < 0 || count > 10000)) throw new Error('Unexpected Canvas reply count')
  item.required_replies = count ?? null
  return item
}
function normalizePlanner(record, instance, selected) {
  const course = canvasId(record.course_id, 'Planner course ID')
  if (!selected.includes(course) || record.context_type && record.context_type !== 'Course') throw new Error('Canvas planner returned an unselected course context; no partial result returned')
  const p = object(record.plannable, 'planner learning object'), id = canvasId(record.plannable_id)
  checkCourse(p, course)
  if (p.id != null && canvasId(p.id) !== id) throw new Error('Canvas planner object IDs disagree; no partial result returned')
  const type = text(record.plannable_type, 'planner type', 64, false)
  if (!/^[a-z][a-z_]{0,63}$/.test(type)) throw new Error('Invalid Canvas planner type')
  const kind = type === 'calendar_event' ? 'event' : type
  const item = baseItem(instance, course, kind, id, p.title ?? p.name, 'planner', record.html_url)
  item.planner_type = type
  // plannable_date is a display/sort date; for pages/discussions it can fall back
  // to creation/publication. It is NEVER a generic due date.
  dated(item, 'planner', record.plannable_date, 'planner')
  if (type === 'assignment') item.assignment_id = id
  else if (['quiz', 'discussion_topic'].includes(type)) {
    item[type === 'quiz' ? 'quiz_id' : 'discussion_id'] = id
    item.assignment_id = optionalId(p.assignment_id, 'Planner assignment ID')
    if (item.assignment_id) item.aliases.push(identityFor(instance, course, 'assignment', item.assignment_id))
  }
  if (['assignment', 'quiz', 'sub_assignment', 'peer_review_sub_assignment'].includes(type)) {
    dated(item, 'due', 'plannable_date' in record ? record.plannable_date : p.due_at, 'planner')
  } else if (type === 'discussion_topic' && item.assignment_id) {
    // A graded discussion's planner date can also be its publication date. The
    // separately fetched assignment supplies the effective deadline.
    item.warnings.push('Discussion deadlines come from the linked assignment/checkpoints, not the planner display date.')
  }
  if (['wiki_page', 'planner_note', 'discussion_topic', 'assessment_request'].includes(type)) dated(item, 'todo', p.todo_date, 'planner')
  if (type === 'calendar_event') {
    dated(item, 'event_start', p.start_at, 'planner'); dated(item, 'event_end', p.end_at, 'planner')
    item.all_day = typeof p.all_day === 'boolean' ? p.all_day : null
  }
  if (type === 'sub_assignment') {
    item._checkpoint_tag = CHECKPOINTS.has(p.sub_assignment_tag) ? p.sub_assignment_tag : null
    item._parent_assignment_id = optionalId(p.parent_assignment_id, 'Checkpoint parent ID')
    // Canvas's planner omits parent_assignment_id on some versions. Only a
    // same-origin, exact course assignment route can supply a candidate; merge
    // still requires that fetched parent to contain the same checkpoint tag.
    if (!item._parent_assignment_id && item.url) {
      const match = new URL(item.url).pathname.match(/^\/courses\/([1-9]\d*)\/assignments\/([1-9]\d*)(?:\/submissions\/[1-9]\d*)?\/?$/)
      if (match && match[1] === course) item._parent_assignment_id = canvasId(match[2])
    }
    item.needs_identity_review = true
  }
  if (!PLANNER_TYPES.has(type)) {
    item.needs_identity_review = true
    item.warnings.push('Unrecognized planner item type: keep as context until its meaning and identity are reviewed.')
  }
  // Do not return submissions, scores, teacher feedback, planner completion,
  // user IDs or arbitrary embedded learning-object data.
  return item
}

export function normalizeCanvas(record, instance, mode, selected, courseId) {
  object(record, 'record')
  if (mode === 'planner') return normalizePlanner(record, instance, selected)
  if (mode === 'assignments') return normalizeAssignment(record, instance, courseId)
  if (mode === 'quizzes') return normalizeQuiz(record, instance, courseId)
  if (mode === 'discussions') return normalizeDiscussion(record, instance, courseId)
  const id = canvasId(record.id)
  if (mode === 'courses') return { provider: 'canvas', instance: instance.id, id, kind: 'course', course_id: id, identity: `canvas:${instance.id}:course:${id}`, title: text(record.name, 'course name', 1024, false), code: text(record.course_code, 'course code', 256), status: text(record.workflow_state, 'course status', 64), time_zone: text(record.time_zone, 'course timezone', 128), starts_at: timestamp(record.start_at, 'course start'), ends_at: timestamp(record.end_at, 'course end'), url: `${baseURL(instance).origin}/courses/${id}` }
  const course = courseContext(record, selected, mode === 'calendar')
  const item = baseItem(instance, course, mode === 'announcements' ? 'announcement' : 'event', id, record.title, mode, record.html_url)
  description(item, mode === 'announcements' ? record.message : record.description)
  if (mode === 'announcements') {
    item.posted_at = timestamp(record.posted_at, 'announcement post'); dated(item, 'posted', item.posted_at, mode)
    return item
  }
  item.start_at = timestamp(record.start_at, 'event start'); item.end_at = timestamp(record.end_at, 'event end')
  dated(item, 'event_start', item.start_at, mode); dated(item, 'event_end', item.end_at, mode)
  return { ...item, all_day: typeof record.all_day === 'boolean' ? record.all_day : null,
    all_day_date: record.all_day_date == null ? null : date(record.all_day_date),
    location: text(record.location_name, 'event location', 1024), status: text(record.workflow_state, 'event status', 64),
    series_id: text(record.series_uuid, 'event series', 256), recurrence_rule: text(record.rrule, 'event recurrence', 1024),
    hidden: typeof record.hidden === 'boolean' ? record.hidden : null }
}

export function mergeCanvasItems(rows) {
  const assignments = new Map(rows.filter(r => r.sources.includes('assignments')).map(r => [r.identity, r]))
  for (const row of rows) {
    if (row.kind !== 'sub_assignment' || !row._checkpoint_tag || !row._parent_assignment_id) continue
    const parent = `canvas:${row.instance}:course:${row.course_id}:assignment:${row._parent_assignment_id}`
    if (!assignments.get(parent)?.checkpoint_tags.includes(row._checkpoint_tag)) continue
    row.aliases.push(parent)
    row.dates.forEach(d => { d.component = row._checkpoint_tag })
    row.checkpoint_tags = [row._checkpoint_tag]
    row.needs_identity_review = false
  }
  const owners = new Map(), groups = []
  for (const row of rows) {
    const matches = [...new Set(row.aliases.map(a => owners.get(a)).filter(Boolean))]
    const group = matches.shift() || { rows: [], aliases: new Set() }
    if (!groups.includes(group)) groups.push(group)
    for (const other of matches) {
      group.rows.push(...other.rows)
      for (const alias of other.aliases) { group.aliases.add(alias); owners.set(alias, group) }
      groups.splice(groups.indexOf(other), 1)
    }
    group.rows.push(row)
    for (const alias of row.aliases) { group.aliases.add(alias); owners.set(alias, group) }
  }
  return groups.map(group => {
    const assignmentAliases = [...group.aliases].filter(a => /:assignment:\d+$/.test(a))
    if (assignmentAliases.length > 1) throw new Error('Canvas identities link one item to conflicting assignments; no partial result returned')
    for (const field of ['quiz_id', 'discussion_id']) if (new Set(group.rows.map(r => r[field]).filter(Boolean)).size > 1) throw new Error('Conflicting Canvas learning-object identities; no partial result returned')
    const ranked = [...group.rows].sort((a, b) => ['assignments', 'quizzes', 'discussions', 'planner', 'calendar', 'announcements'].indexOf(a.sources[0]) - ['assignments', 'quizzes', 'discussions', 'planner', 'calendar', 'announcements'].indexOf(b.sources[0]))
    const item = { ...ranked[0], aliases: [...group.aliases].sort(), sources: [...new Set(ranked.flatMap(r => r.sources))], dates: [],
      warnings: [...new Set(ranked.flatMap(r => r.warnings))], checkpoint_tags: [...new Set(ranked.flatMap(r => r.checkpoint_tags))],
      has_checkpoints: ranked.some(r => r.has_checkpoints), date_conflicts: [] }
    if (assignmentAliases.length) {
      item.identity = assignmentAliases[0]; item.assignment_id = item.identity.split(':').at(-1); item.id = item.assignment_id; item.kind = 'assignment'
    }
    for (const field of ['quiz_id', 'discussion_id', 'quiz_type', 'required_replies']) {
      const value = ranked.find(r => r[field] != null)?.[field]
      if (value != null) item[field] = value
    }
    const dateKeys = new Map()
    for (const row of ranked) for (const fact of row.dates) {
      const key = JSON.stringify([fact.component, fact.type, fact.at])
      const existing = dateKeys.get(key)
      if (existing) existing.sources = [...new Set([...existing.sources, ...fact.sources])]
      else { const value = { ...fact, sources: [...fact.sources] }; dateKeys.set(key, value); item.dates.push(value) }
    }
    const datedFields = new Map()
    for (const fact of item.dates) {
      const key = fact.component + ':' + fact.type
      if (!datedFields.has(key)) datedFields.set(key, [])
      datedFields.get(key).push(fact)
    }
    for (const [field, values] of datedFields) {
      // Equal instants with different offsets are not conflicting deadlines.
      const valueKeys = values.map(v => v.at == null ? 'null' : v.at.length === 10 ? v.at : Date.parse(v.at))
      if (new Set(valueKeys).size > 1) item.date_conflicts.push({ field, values })
    }
    item.needs_identity_review = ranked.some(r => r.needs_identity_review) && !ranked.some(r => r.sources.includes('assignments'))
    if (item.needs_identity_review) item.warnings.push('Parent/assignment identity is unresolved; do not create a local record until matched or explicitly reviewed.')
    if (item.has_checkpoints && item.checkpoint_tags.length < 2) item.warnings.push('Canvas did not supply both discussion checkpoint dates; verify the missing deadline in Canvas.')
    if (item.date_conflicts.length) item.warnings.push('Sources disagree about dates; review each conflict before changing local dates.')
    delete item._checkpoint_tag; delete item._parent_assignment_id
    return item
  })
}

export function canvasReadModes(mode) {
  return ['planner', 'coursework'].includes(mode) ? ['assignments', 'quizzes', 'discussions', 'planner'] : ['quizzes', 'discussions'].includes(mode) ? ['assignments', mode] : [mode]
}
export async function pullCanvasData(instance, options, requestPages) {
  const rows = [], seen = new Set(); let rawCount = 0
  const consume = (mode, courseId) => records => {
    for (const record of records) {
      if (++rawCount > 2500) throw new Error('Canvas selection exceeds 2500 source items; narrow the selection. No partial result returned.')
      const item = normalizeCanvas(record, instance, mode, options.courseIds, courseId)
      const key = mode + ':' + item.identity
      if (seen.has(key)) throw new Error('Canvas returned a repeated item across pages; no partial result returned')
      seen.add(key); rows.push(item)
    }
  }
  const list = async mode => {
    if (mode === 'courses') return requestPages('/api/v1/courses', { enrollment_state: 'active', per_page: 50 }, consume(mode))
    if (['assignments', 'quizzes', 'discussions'].includes(mode)) {
      for (const course of options.courseIds) await requestPages(`/api/v1/courses/${course}/${mode === 'discussions' ? 'discussion_topics' : mode}`,
        mode === 'assignments' ? { override_assignment_dates: true, per_page: 50, 'include[]': ['checkpoints'] } : { per_page: 50 }, consume(mode, course))
    } else {
      const query = { 'context_codes[]': options.courseIds.map(id => `course_${id}`), start_date: options.start, end_date: options.end, per_page: 50 }
      if (mode === 'announcements') await requestPages('/api/v1/announcements', { ...query, active_only: true }, consume(mode))
      else if (mode === 'planner') await requestPages('/api/v1/planner/items', query, consume(mode))
      else await requestPages('/api/v1/calendar_events', { ...query, type: 'event', 'excludes[]': ['child_events', 'assignment'] }, consume(mode))
    }
  }
  const modes = canvasReadModes(options.mode)
  for (const mode of modes) await list(mode)
  let items = options.mode === 'courses' ? rows : mergeCanvasItems(rows)
  if (['planner', 'quizzes', 'discussions'].includes(options.mode)) items = items.filter(item => item.sources.includes(options.mode) || options.mode === 'quizzes' && item.coursework_type === 'quiz' || options.mode === 'discussions' && item.coursework_type === 'discussion')
  if (items.length > options.limit) throw new Error(`Canvas selection exceeds ${options.limit} items; choose fewer courses or a smaller planner window. No partial result returned.`)
  if (Buffer.byteLength(JSON.stringify(items), 'utf8') > 2 * 1024 * 1024) throw new Error('Canvas preview exceeds 2 MiB; narrow the selection. No partial result returned.')
  return { items, truncated: false, read_only: true, sources_read: modes,
    ...(options.mode === 'coursework' ? { window_scope: 'The date window applies to planner context only; assignment, quiz and discussion lists include all accessible items in the selected courses.' } : {}) }
}
