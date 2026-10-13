import test from 'node:test'
import assert from 'node:assert/strict'
import { mkdtemp, mkdir, writeFile, readFile, rm } from 'node:fs/promises'
import os from 'node:os'
import path from 'node:path'
import { frontmatter, windowsSafe } from '../fieldbook_core/lib/vault.js'
import { scanPeople } from '../fieldbook_core/lib/people.js'
import { snapshot } from '../fieldbook_core/lib/history.js'
async function vault(t, files) {
  const root = await mkdtemp(path.join(os.tmpdir(), 'fieldbook-test-'))
  t.after(() => rm(root, { recursive: true, force: true }))
  await mkdir(path.join(root, 'Templates'))
  await writeFile(path.join(root, 'Templates/Person.md'), '---\ntags: [person]\n---\n## Notes\n')
  for (const [file, text] of Object.entries(files)) { await mkdir(path.dirname(path.join(root, file)), { recursive: true }); await writeFile(path.join(root, file), text) }
  return root
}
test('YAML parser handles BOM, CRLF, quoted comma aliases, and block lists', () => {
  const fm = frontmatter('\ufeff---\r\ntags:\r\n  - person\r\naliases: ["Smith, Alex"]\r\n---\r\n')
  assert.deepEqual(fm, { tags: ['person'], aliases: ['Smith, Alex'] })
})
test('duplicate YAML keys fail rather than inventing identity', () => assert.throws(() => frontmatter('---\ntags: [person]\ntags: [task]\n---\n')))
test('person creation is idempotent and ignores template bodies', async t => {
  const root = await vault(t, { 'meeting.md': '\ufeff---\nattendees: ["[[Alex Smith]]"]\n---\n' })
  assert.deepEqual(await scanPeople(root), ['Alex Smith'])
  assert.deepEqual(await scanPeople(root), [])
})
test('comma alias does not create a duplicate person', async t => {
  const root = await vault(t, { 'People/Alex Smith.md': '---\ntags: [person]\naliases: ["Smith, Alex"]\n---\n', 'meeting.md': '---\nattendees: ["[[Smith, Alex]]"]\n---\n' })
  const warnings=[]
  assert.deepEqual(await scanPeople(root, x=>warnings.push(x)), [])
  assert.match(warnings.join(), /Ambiguous/)
})
test('non-person filename collision warns, never silently resolves', async t => {
  const root = await vault(t, { 'Notes/Alex.md': '---\ntags: [note]\n---\n', 'meeting.md': '---\nattendees: ["[[Alex]]"]\n---\n' })
  const warnings=[]; assert.deepEqual(await scanPeople(root,x=>warnings.push(x)),[]); assert.match(warnings.join(),/Ambiguous person/)
})
test('same scan containing plain and qualified names only creates qualified name', async t => {
  const root=await vault(t,{'meeting.md':'---\nattendees: ["[[Alex Smith]]", "[[Alex Smith (Acme)]]"]\n---\n'})
  assert.deepEqual(await scanPeople(root),['Alex Smith (Acme)'])
})
test('unsafe Windows filenames are rejected',()=>{for(const x of ['CON','aux.txt','Alex.','Alex/Smith','A:B'])assert.equal(windowsSafe(x),false);assert.equal(windowsSafe('Alex Smith (Acme)'),true)})
test('history refuses parent repository before any staging/commit', async()=>{
  const calls=[]; const run=async(_,args)=>{calls.push(args);return {stdout:'/parent\n'}}
  await assert.rejects(snapshot('/parent/vault','fieldbook',run,async x=>x),/repository root/)
  assert.equal(calls.length,1)
})
test('history snapshots a verified vault root and labels the trigger',async()=>{
  const calls=[];const run=async(_,args)=>{calls.push(args);return {stdout:args.includes('--show-toplevel')?'/vault\n':args.includes('--cached')?'Tasks/A.md\0':''}}
  assert.equal(await snapshot('/vault','fieldbook',run,async x=>x),'fieldbook: A.md')
  assert.deepEqual(calls[1],['-C','/vault','add','-A','--','.'])
})

test('real shipped Person is the automatic default even in a manager vault', async t => {
  const files = { 'Meetings/Planning.md': '---\ntags: [meeting]\nattendees: ["[[Sam Rivera]]"]\n---\n',
    'fieldbook.json': JSON.stringify({setups:['work'],workRole:'people-manager',features:{autoPeople:true}}) }
  for (const name of ['Person','Person - Professional contact','Person - Direct report'])
    files[`Templates/${name}.md`] = await readFile(new URL(`../Templates/${name}.md`, import.meta.url), 'utf8')
  const root = await vault(t, files)
  assert.deepEqual(await scanPeople(root), ['Sam Rivera'])
  const record = await readFile(path.join(root,'People/Sam Rivera.md'),'utf8')
  const fm = frontmatter(record)
  assert.deepEqual(fm.tags,['person']); assert.equal(fm.relationship,null)
  assert.deepEqual(fm.emails,[]); assert.deepEqual(fm.phones,[])
  assert.equal('manager' in fm,false); assert.equal('employeeNumber' in fm,false)
  assert.ok(!record.includes('## Goals & development')); assert.ok(!record.includes('## Reviews'))
  assert.match(record,/from \[\[Planning\]\]/)
  assert.deepEqual(await scanPeople(root),[])
  assert.equal(await readFile(path.join(root,'People/Sam Rivera.md'),'utf8'),record)
})

test('all shipped person profiles share identity matching; relationship selects tracker roster', async t => {
  const { trackerPeople } = await import('../fieldbook_core/lib/tracker-people.js')
  const files={ 'Meetings/Planning.md':'---\ntags: [meeting]\nattendees: ["[[Me]]", "[[Alex Vendor]]", "[[Jordan]]"]\n---\n' }
  for (const [template,name,relationship,account] of [
    ['Person','Me','self','owner'],['Person - Professional contact','Alex Vendor','vendor','alex'],['Person - Direct report','Jordan','report','jordan']]) {
    let text=await readFile(new URL(`../Templates/${template}.md`,import.meta.url),'utf8')
    text=text.replace(/^relationship:.*$/m,`relationship: ${relationship}`).replace('usernames: []',`usernames: ["github:personal: ${account}"]`)
    files[`People/${name}.md`]=text
  }
  const root=await vault(t,files)
  assert.deepEqual(await scanPeople(root),[])
  const scope=await trackerPeople(root,'github','personal','team')
  assert.equal(scope.self,'owner');assert.deepEqual(scope.members,['jordan'])
  assert.deepEqual(scope.people.map(p=>p.path).sort(),['People/Jordan.md','People/Me.md'])
  for(const name of ['Me','Alex Vendor','Jordan'])assert.equal(await readFile(path.join(root,`People/${name}.md`),'utf8'),files[`People/${name}.md`])
})
