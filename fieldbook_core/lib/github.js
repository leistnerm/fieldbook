// GitHub Issues only. Projects and pull requests are separate workflows.
const repoPattern = /^[A-Za-z0-9][A-Za-z0-9-]*\/[A-Za-z0-9_.-]+$/
const loginPattern = /^[A-Za-z0-9][A-Za-z0-9-]*$/
export function githubId(value) {
  const match = String(value).match(/^(.+)#([1-9]\d*)$/)
  if (!match || !repoPattern.test(match[1]) || ['.', '..'].includes(match[1].split('/')[1]) || !Number.isSafeInteger(Number(match[2])))
    throw new Error('GitHub IDs must be owner/repository#number')
  return { repo: match[1], number: Number(match[2]), id: `${match[1]}#${match[2]}` }
}
export function normalizeGitHub(issue, instance, repo) {
  if (!Number.isSafeInteger(issue?.number) || issue.number < 1 || typeof issue.title !== 'string' || !['open', 'closed'].includes(issue.state))
    throw new Error('Unexpected GitHub issue; no partial result returned')
  return {
    provider: 'github', instance: instance.id, id: `${repo}#${issue.number}`,
    title: issue.title, status: issue.state, resolution: issue.state_reason || '',
    // closed_at is a closure date, not evidence that the work was completed.
    completed: issue.state === 'closed' && issue.state_reason === 'completed' ? issue.closed_at || null : null,
    closed: issue.closed_at || null, updated: issue.updated_at || '', due: null,
    assignees: (issue.assignees || []).map(a => ({ id: a.login, name: a.login })),
    project: repo, kind: issue.type?.name || 'Issue', description: issue.body || '',
    labels: (issue.labels || []).map(l => typeof l === 'string' ? l : l.name),
    milestone: issue.milestone ? { title: issue.milestone.title, due: issue.milestone.due_on || null } : null,
    url: issue.html_url || '',
  }
}
export async function pullGitHub(instance, opts, request) {
  if (!['linked', 'mine', 'team', 'all'].includes(opts.scope)) throw new Error('Choose linked, mine, team, or all')
  const limit = opts.limit || 500, items = new Map(), skipped = []
  const add = (issue, repo) => {
    if (issue.pull_request) return false
    const item = normalizeGitHub(issue, instance, repo)
    items.set(item.id.toLowerCase(), item)
    return items.size > limit
  }
  const result = truncated => ({ items: [...items.values()].slice(0, limit), truncated, skipped })
  if (opts.scope === 'linked') {
    if (!opts.ids?.length) throw new Error('Linked scope requires GitHub issue IDs')
    const ids = [...new Map(opts.ids.map(githubId).map(id => [id.id.toLowerCase(), id])).values()]
    for (const { repo, number, id } of ids.slice(0, limit)) {
      const issue = await request(`/repos/${repo}/issues/${number}`)
      if (issue?.number !== number) throw new Error('GitHub returned a different issue; no partial result returned')
      if (issue.pull_request) skipped.push({ id, reason: 'Pull request; this adapter reads issues only' })
      else add(issue, repo)
    }
    return result(ids.length > limit)
  }
  if (!Array.isArray(instance.repositories) || !instance.repositories.length) throw new Error('Configure explicit GitHub repositories as owner/repository')
  // Validate the complete scope before any network request.
  const repos = [...new Set(instance.repositories.map(repo => githubId(`${repo}#1`).repo.toLowerCase()))]
  let me = opts.self || instance.login
  if (['mine', 'team'].includes(opts.scope) && !me) me = (await request('/user')).login
  const members = opts.scope === 'all' ? [undefined] : opts.scope === 'mine' ? [me] : [me, ...(opts.members || [])]
  if (opts.scope === 'team' && !opts.members?.length) throw new Error('Team scope needs confirmed report logins')
  if (opts.scope !== 'all' && members.some(m => typeof m !== 'string' || !loginPattern.test(m))) throw new Error('GitHub identities must be exact user logins')
  if (instance.labels !== undefined && (!Array.isArray(instance.labels) || instance.labels.some(l => typeof l !== 'string'))) throw new Error('GitHub labels must be a list of names')
  for (const repo of repos) for (const assignee of [...new Set(members)]) {
    const seenPages = new Set()
    for (let page = 1; ; page++) {
      const issues = await request(`/repos/${repo}/issues`, { state: 'all', sort: 'created', direction: 'asc', per_page: 100, page, assignee, ...(instance.labels?.length ? { labels: instance.labels.join(',') } : {}) })
      if (!Array.isArray(issues)) throw new Error('Unexpected GitHub response; no partial result returned')
      const signature = JSON.stringify(issues.map(i => i.number))
      if (issues.length && seenPages.has(signature)) throw new Error('GitHub pagination stalled; no partial result returned')
      seenPages.add(signature)
      for (const issue of issues) if (add(issue, repo)) return result(true)
      if (issues.length < 100) break
      if (page >= 1000) throw new Error('GitHub pagination limit exceeded; narrow repositories or labels')
    }
  }
  return result(false)
}
