import test from 'node:test'
import assert from 'node:assert/strict'
import { readFile, readdir } from 'node:fs/promises'
import { frontmatter } from '../fieldbook_core/lib/vault.js'

// Execute the actual shipped template expressions with a small Templater/vault
// fixture. This checks generated text and movement, not Obsidian's rendering UI.
const AsyncFunction = Object.getPrototypeOf(async function () {}).constructor
async function render(name, { title = 'Shared learning', prompt = 'Topic: compare options?', existing = [] } = {}) {
  const source = await readFile(new URL(`../Templates/${name}.md`, import.meta.url), 'utf8')
  const paths = new Set(existing), moved = [], created = []
  const tp = {
    file: { title, move: async p => { moved.push(p); paths.add(`${p}.md`) } },
    system: { prompt: async () => prompt },
    date: { now: format => ({ 'YYYY-MM-DD':'2026-10-10', YYYY:'2026', 'YYYY-MM':'2026-10' }[format] ?? format) }
  }
  const app = { vault: {
    getAbstractFileByPath: p => paths.has(p),
    createFolder: async p => { created.push(p); paths.add(p) }
  } }
  let output = '', cursor = 0
  for (const match of source.matchAll(/<%(\*)?([\s\S]*?)(-?)%>/g)) {
    output += source.slice(cursor, match.index)
    const result = await new AsyncFunction('tp','app',match[1] ? match[2] : `return (${match[2]})`)(tp,app)
    if (!match[1]) output += result ?? ''
    cursor = match.index + match[0].length
    if (match[3] && source[cursor] === '\n') cursor++
  }
  output += source.slice(cursor)
  return { text: output, fm: frontmatter(output), moved, created }
}

test('every shipped template renders valid metadata; only explicit school templates assign an area', async () => {
  const names = (await readdir(new URL('../Templates/',import.meta.url))).filter(x=>x.endsWith('.md'))
  for (const file of names) {
    const name = file.slice(0,-3), {text,fm} = await render(name, {title:'Practice "Spanish": chapter 2'})
    assert.ok(!text.includes('<%'), name)
    if (name === 'Task body') { assert.deepEqual(fm,{}); continue }
    assert.ok(Array.isArray(fm.tags) && fm.tags.length, name)
    if (['Project - Course','Task - Assignment'].includes(name)) assert.equal(fm.area,'school',name)
    else assert.ok(fm.area == null, `${name} unexpectedly selects ${fm.area}`)
    // Person profiles use title for a supplied job role, not the note title.
    if ('title' in fm && !fm.tags.includes('person')) assert.equal(fm.title,'Practice "Spanish": chapter 2',name)
  }
})

test('generic defaults and explicit variants retain shared record identity without inventing facts', async () => {
  const item = (await render('Item')).fm, purchase = (await render('Item - Purchased')).fm
  assert.deepEqual(item.tags,['item']); assert.deepEqual(purchase.tags,item.tags)
  for (const fm of [item,purchase]) { assert.equal(fm.status,null);assert.equal(fm.owner,null);assert.equal(fm.area,null) }
  assert.ok(!('purchase_price' in item));assert.ok('purchase_price' in purchase)
  const research = (await render('Research')).fm, experiment = (await render('Research - Experiment')).fm
  assert.deepEqual(research.tags,['research']);assert.deepEqual(experiment.tags,research.tags)
  assert.equal(research.kind,'research');assert.equal(experiment.kind,'experiment')
  const reference = (await render('Reference')).fm
  assert.equal(reference.kind,null);assert.deepEqual(reference.topics,[])
  assert.ok(!('systems' in reference));assert.ok(!('verified' in reference))
  const study = (await render('Task - Study session')).fm
  assert.equal(study.type,'study');assert.equal(study.area,null);assert.deepEqual(study.projects,[])
  assert.equal(study.due,null)
})

test('actual prompted templates use their existing folders, safe names and collision suffixes', async () => {
  for (const [name,folder] of [['Reference','Reference'],['Research','Research'],['Research - Experiment','Research'],['Meeting','Meetings/2026/2026-10']]) {
    const first = await render(name), dest = first.moved[0]
    assert.ok(dest?.startsWith(`${folder}/`),`${name}: ${dest}`)
    assert.ok(!/[?:]/.test(dest),name)
    const again = await render(name,{existing:[folder,`${dest}.md`]})
    assert.equal(again.moved[0],`${dest} (2)`)
    assert.ok(!again.created.includes(folder))
  }
})

test('new Experiment and existing prompted templates respect cancellation and invalid titles', async () => {
  for (const name of ['Reference','Research','Research - Experiment','Meeting']) {
    await assert.rejects(render(name,{prompt:null}),/Cancelled/)
    await assert.rejects(render(name,{prompt:'CON'}),/valid title/)
  }
})
