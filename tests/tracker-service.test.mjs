import test from 'node:test'
import assert from 'node:assert/strict'
import { mkdtemp, mkdir, writeFile, readFile, rm } from 'node:fs/promises'
import os from 'node:os'
import path from 'node:path'
import { pullTracker } from '../fieldbook_core/lib/tracker-service.js'
const providers=['jira','agility','github','azure']
async function put(root,file,text) { await mkdir(path.dirname(path.join(root,file)),{recursive:true});await writeFile(path.join(root,file),text) }
async function fixture(t, features = Object.fromEntries(providers.map(p=>[p,true])), setups = []) {
  const root = await mkdtemp(path.join(os.tmpdir(), 'fieldbook-service-'))
  t.after(() => rm(root, { recursive: true, force: true }))
  await put(root,'fieldbook.json',JSON.stringify({ setups, workRole:'individual-contributor', features }))
  for (const provider of providers) {
    const name=`${provider.toUpperCase()}_FIELDBOOK_TEST_TOKEN`, saved=process.env[name]
    process.env[name]='fixture-only'
    t.after(()=>{if(saved===undefined)delete process.env[name];else process.env[name]=saved})
    await put(root,`fieldbook_core/${provider}.json`,JSON.stringify({instances:[{
      id:'office',flavor:'cloud',baseUrl:'https://example.test',tokenVar:name,email:'test@example.test',memberId:'Member:1',
      repositories:['owner/repo'],login:'me',project:'School',
    }]}))
  }
  return root
}
function mockReads(t) {
  const calls=[]
  t.mock.method(globalThis,'fetch',async(url,options)=>{
    calls.push([url,options])
    const data=String(url).includes('/repos/')?[]:String(url).includes('/wiql')?{workItems:[]}:String(url).includes('/query.v1')?[[]]:{issues:[],isLast:true}
    return Response.json(data)
  })
  return calls
}
const accounts={jira:['self-id','report-id'],agility:['Member:1','Member:2'],github:['me','alex'],azure:['me@example.test','alex@example.test']}
async function person(root, name, relationship, index, extra = '') {
  const usernames=providers.map(p=>`"${p}:office: ${accounts[p][index]}"`).join(', ')
  await put(root,`People/${name}.md`,`---\ntags: [person]\nrelationship: ${relationship}\nusernames: [${usernames}]\n${extra}---\nPrivate local note\n`)
}

test('linked scope with omitted lists returns empty without network or credentials in core',async t=>{
  const root=await fixture(t);const calls=mockReads(t)
  for(const provider of providers){const r=await pullTracker({provider,instance:'office',scope:'linked'},root);assert.deepEqual(r.items,[]);assert.equal(r.message,'No linked items')}
  assert.equal(calls.length,0)
})
test('all four providers work in core, personal, school, contributor and manager configurations',async t=>{
  const root=await fixture(t);const calls=mockReads(t)
  for(const setups of [[],['personal'],['school'],['personal','school'],['work']]) for(const workRole of ['individual-contributor','people-manager']) {
    await put(root,'fieldbook.json',JSON.stringify({setups,workRole,features:Object.fromEntries(providers.map(p=>[p,true]))}))
    for(const provider of providers) {
      const result=await pullTracker({provider,instance:'office',scope:'mine'},root)
      assert.deepEqual(result.items,[]); assert.equal(result.read_only,true)
      assert.equal(result.coverage.scope.mode,'mine'); assert.equal(result.coverage.returned,0)
      assert.equal(result.read_at,result.coverage.read_at); assert.ok(Date.parse(result.read_at))
    }
  }
  assert.equal(calls.length,40)
  assert.ok(calls.every(([url,o])=>o.method==='GET'||/\/(query.v1|wiql)$/.test(url.pathname)))
})
test('disabled features, invalid provider/scope/instance and unbounded queries fail',async t=>{
  const root=await fixture(t,{jira:false,agility:true,github:true,azure:true});const calls=mockReads(t)
  await assert.rejects(pullTracker({provider:'jira',instance:'office',scope:'mine'},root),/Enable jira/)
  await assert.rejects(pullTracker({provider:'unknown',instance:'office',scope:'mine'},root),/provider/)
  await assert.rejects(pullTracker({provider:'azure',instance:'office',scope:'bad'},root),/Choose/)
  await assert.rejects(pullTracker({provider:'agility',instance:'missing',scope:'linked'},root),/unique/)
  await assert.rejects(pullTracker({provider:'github',instance:'office',scope:'all',query:'anything'},root),/configured filters/)
  assert.equal(calls.length,0)
})
test('team resolves relationship self/report for every provider without work or manager links',async t=>{
  const root=await fixture(t);await person(root,'Me','self',0);await person(root,'Alex','report',1)
  await put(root,'People/Former.md','---\ntags: [person]\nrelationship: report\nstatus: former\n---\n')
  await put(root,'People/Peer.md','---\ntags: [person]\nrelationship: peer\nmanager: "[[Me]]"\nteam: Same team\n---\n')
  await put(root,'Templates/Fake.md','---\ntags: [person]\nrelationship: self\n---\n')
  const calls=mockReads(t)
  const before=await readFile(path.join(root,'People/Alex.md'),'utf8')
  for(const provider of providers) {
    const r=await pullTracker({provider,instance:'office',scope:'team'},root)
    assert.equal(r.membershipSource,'person relationships');assert.deepEqual(r.people.map(p=>p.relationship),['self','report'])
    assert.deepEqual(r.members,[accounts[provider][1]]);assert.equal(r.self,accounts[provider][0])
  }
  assert.equal(await readFile(path.join(root,'People/Alex.md'),'utf8'),before)
  assert.match(calls[0][0].searchParams.get('jql'),/self-id.*report-id/)
  assert.deepEqual(calls.filter(([u])=>u.pathname==='/query.v1').map(([,o])=>JSON.parse(o.body).where.Owners),['Member:1','Member:2'])
  assert.deepEqual(calls.filter(([u])=>u.pathname.includes('/repos/')).map(([u])=>u.searchParams.get('assignee')),['me','alex'])
  assert.match(JSON.parse(calls.at(-1)[1].body).query,/me@example.test.*alex@example.test/)
})
test('missing report identity stops before any remote requests, including when other reports map',async t=>{
  const root=await fixture(t);await person(root,'Me','self',0);await person(root,'Alex','report',1)
  await put(root,'People/Unmapped.md','---\ntags: [person]\nrelationship: report\n---\n')
  const calls=mockReads(t)
  for(const provider of providers)await assert.rejects(pullTracker({provider,instance:'office',scope:'team'},root),/Unmapped.md/)
  assert.equal(calls.length,0)
})
test('duplicate self or duplicate account mapping is ambiguous, not guessed',async t=>{
  const root=await fixture(t);await person(root,'Me','self',0);await person(root,'Other me','self',0);const calls=mockReads(t)
  await assert.rejects(pullTracker({provider:'github',instance:'office',scope:'mine'},root),/Multiple current/)
  await rm(path.join(root,'People/Other me.md'));await person(root,'Duplicate','report',0)
  await assert.rejects(pullTracker({provider:'github',instance:'office',scope:'team'},root),/Duplicate github/)
  assert.equal(calls.length,0)
})
test('self relationship and reports are required for automatic team selection; no role fallback',async t=>{
  const root=await fixture(t);const calls=mockReads(t)
  await assert.rejects(pullTracker({provider:'azure',instance:'office',scope:'team'},root),/relationship: self/)
  await person(root,'Me','self',0)
  await assert.rejects(pullTracker({provider:'azure',instance:'office',scope:'team'},root),/No current relationship: report/)
  assert.equal(calls.length,0)
})
test('self account mapping must match configured identity when one is set',async t=>{
  const root=await fixture(t);await put(root,'People/Me.md','---\ntags: [person]\nrelationship: self\nusernames: ["github:office: different"]\n---\n')
  const calls=mockReads(t)
  await assert.rejects(pullTracker({provider:'github',instance:'office',scope:'mine'},root),/conflicts/)
  assert.equal(calls.length,0)
})
test('explicit account list is labeled as an override; irrelevant member/ID arguments fail',async t=>{
  const root=await fixture(t);const calls=mockReads(t)
  const r=await pullTracker({provider:'github',instance:'office',scope:'team',members:['confirmed']},root)
  assert.equal(r.membershipSource,'explicit members');assert.deepEqual(r.members,['confirmed'])
  assert.equal(calls.length,2)
  await assert.rejects(pullTracker({provider:'github',instance:'office',scope:'mine',members:['confirmed']},root),/only to team/)
  await assert.rejects(pullTracker({provider:'github',instance:'office',scope:'mine',ids:['owner/repo#1']},root),/only to linked/)
})
test('linked notes of any type require an instance; untagged notes and templates are excluded',async t=>{
  const root=await fixture(t);const calls=mockReads(t)
  await put(root,'Notes/Example.md','---\ntags: [note]\ngithub: owner/repo#1\n---\n')
  await assert.rejects(pullTracker({provider:'github',instance:'office',scope:'linked'},root),/Assign github_instance/)
  await put(root,'Notes/Example.md','---\ngithub: owner/repo#1\n---\n')
  const empty=await pullTracker({provider:'github',instance:'office',scope:'linked'},root)
  assert.equal(empty.message,'No linked items'); assert.equal(empty.coverage.read_at,null)
  assert.equal(calls.length,0)
})
test('wrong-instance identity does not satisfy a report mapping; duplicate label is rejected',async t=>{
  const root=await fixture(t);await person(root,'Me','self',0);const calls=mockReads(t)
  for(const names of ['"github:another: alex"','"github:office: alex", "github:office: alex"']) {
    await put(root,'People/Alex.md',`---\ntags: [person]\nrelationship: report\nusernames: [${names}]\n---\n`)
    await assert.rejects(pullTracker({provider:'github',instance:'office',scope:'team'},root),/one confirmed/)
  }
  assert.equal(calls.length,0)
})

test('invalid tracker IDs, filters and destinations fail before credential lookup',async t=>{
  const root=await fixture(t),deps={credentialEnvironment:()=>assert.fail('must validate before consulting keyring'),fetch:()=>assert.fail('must not request')}
  for(const provider of providers) await assert.rejects(pullTracker({provider,instance:'office',scope:'linked',ids:['invalid-id']},root,undefined,deps),/ID|Linked|numbers|keys/)
  await assert.rejects(pullTracker({provider:'jira',instance:'office',scope:'all'},root,undefined,deps),/explicit/)
  await assert.rejects(pullTracker({provider:'agility',instance:'office',scope:'all'},root,undefined,deps),/explicit/)
  await assert.rejects(pullTracker({provider:'azure',instance:'office',scope:'mine',query:'SELECT * FROM WorkItems'},root,undefined,deps),/WHERE expression/)
  for(const provider of providers){
    const file=path.join(root,`fieldbook_core/${provider}.json`),config=JSON.parse(await readFile(file,'utf8'))
    config.instances[0].baseUrl='http://invalid.test';await writeFile(file,JSON.stringify(config))
    await assert.rejects(pullTracker({provider,instance:'office',scope:'mine'},root,undefined,deps),/HTTPS/)
  }
})

test('tracker keyring lookup happens once after validation and key stays out of result',async t=>{
  const root=await fixture(t),lookups=[]
  const result=await pullTracker({provider:'github',instance:'office',scope:'all'},root,undefined,{
    credentialEnvironment:async(...args)=>{lookups.push(args);return {GITHUB_FIELDBOOK_TEST_TOKEN:'saved-fixture'}},
    fetch:async(url,opts)=>{assert.equal(opts.headers.Authorization,'Bearer saved-fixture');return Response.json([])},
  })
  assert.equal(lookups.length,1);assert.equal(lookups[0][2].baseUrl,'https://example.test')
  assert.ok(!JSON.stringify(result).includes('saved-fixture'))
})

test('explicit local Project scopes constrain all four providers without changing saved defaults or credentials',async t=>{
  const root=await fixture(t),calls=[],lookups=[]
  const selected={jira:'LOCAL',agility:'Scope:123',github:'team/project',azure:'Bound Project'}
  const before={}
  for(const provider of providers){
    const file=path.join(root,`fieldbook_core/${provider}.json`),data=JSON.parse(await readFile(file,'utf8'))
    const item=data.instances[0]
    if(provider==='jira')item.filter='project = OLD AND status = Open'
    if(provider==='agility')item.where={Scope:'Scope:9','Status.Name':'Ready'}
    if(provider==='github')item.labels=['selected-label']
    if(provider==='azure')item.filter="[System.State] = 'Active'"
    await writeFile(file,JSON.stringify(data));before[provider]=await readFile(file,'utf8')
  }
  for(const provider of providers){
    const result=await pullTracker({provider,instance:'office',scope:'all',projectScope:selected[provider]},root,undefined,{
      credentialEnvironment:async(root,p,instance)=>{
        lookups.push([p,instance]);assert.deepEqual(instance,JSON.parse(before[p]).instances[0])
        return {[instance.tokenVar]:'scoped-secret'}
      },
      fetch:async(url,opts)=>{
        calls.push([provider,url,opts])
        return Response.json(provider==='jira'?{issues:[],isLast:true}:provider==='agility'?[[]]:provider==='github'?[]:{workItems:[]})
      },
    })
    assert.equal(result.projectScope,selected[provider]);assert.equal(result.instance,'office')
    assert.ok(!JSON.stringify(result).includes('scoped-secret'))
    assert.equal(await readFile(path.join(root,`fieldbook_core/${provider}.json`),'utf8'),before[provider])
  }
  assert.equal(lookups.length,4)
  assert.equal(calls[0][1].searchParams.get('jql'),'(project = "LOCAL") ORDER BY key ASC')
  assert.deepEqual(JSON.parse(calls[1][2].body).where,{Scope:'Scope:123','Status.Name':'Ready'})
  assert.equal(calls[2][1].pathname,'/repos/team/project/issues');assert.equal(calls[2][1].searchParams.get('labels'),'selected-label')
  assert.equal(calls[3][1].pathname,'/Bound%20Project/_apis/wit/wiql')
  assert.match(JSON.parse(calls[3][2].body).query,/TeamProject\] = 'Bound Project'.*State\] = 'Active'/)
})

test('project scope rejects linked reads, query replacement and invalid identities before credentials or network',async t=>{
  const root=await fixture(t),deps={credentialEnvironment:()=>assert.fail('unexpected key lookup'),fetch:()=>assert.fail('unexpected network')}
  const cases={jira:['X" OR project = OTHER','bad-key',''],agility:['123','Scope:0','Scope:1 OR Scope:2'],github:['owner/../repo','owner/.','https://host/repo'],azure:['../Project','Bad/Project','Bad\nProject','Both\'"']}
  const good={jira:'KEY',agility:'Scope:1',github:'owner/repo',azure:'Project'}
  for(const provider of providers){
    await assert.rejects(pullTracker({provider,instance:'office',scope:'linked',projectScope:good[provider]},root,undefined,deps),/only to mine/)
    await assert.rejects(pullTracker({provider,instance:'office',scope:'all',projectScope:good[provider],query:'anything'},root,undefined,deps),/without query/)
    for(const projectScope of [...cases[provider],{},' leading','control\u202ename'])
      await assert.rejects(pullTracker({provider,instance:'office',scope:'all',projectScope},root,undefined,deps))
  }
})

test('project scope combines with mine and team assignment selection',async t=>{
  const root=await fixture(t);await person(root,'Me','self',0);await person(root,'Alex','report',1)
  const calls=mockReads(t)
  const selected={jira:'LOCAL',agility:'Scope:123',github:'team/project',azure:'Bound Project'}
  for(const scope of ['mine','team']) for(const provider of providers)
    assert.equal((await pullTracker({provider,instance:'office',scope,projectScope:selected[provider]},root)).projectScope,selected[provider])
  for(const [url,opts] of calls){
    if(url.pathname.includes('/search/')) assert.match(url.searchParams.get('jql'),/assignee.*project = "LOCAL"/)
    if(url.pathname==='/query.v1') assert.deepEqual(JSON.parse(opts.body).where.Scope,'Scope:123')
    if(url.pathname.includes('/repos/')) assert.equal(url.pathname,'/repos/team/project/issues')
    if(url.pathname.endsWith('/wiql')) assert.match(JSON.parse(opts.body).query,/TeamProject\] = 'Bound Project'.*AssignedTo/)
  }
})

test('hidden connection backups never add linked tickets or duplicate people',async t=>{
  const root=await fixture(t);const calls=mockReads(t)
  await put(root,'.fieldbook/config-backups/previous/Projects/Old.md','---\ntags: [project]\njira: APP-OLD\n---\n')
  await put(root,'Projects/Current.md','---\ntags: [project]\njira: APP-2\njira_instance: office\n---\n')
  const result=await pullTracker({provider:'jira',instance:'office',scope:'linked'},root)
  assert.deepEqual(result.coverage.scope.ids,['APP-2']);assert.equal(calls.length,1)
})
test('oversized tracker input fails before credentials or network',async t=>{
  const root=await fixture(t);const calls=mockReads(t)
  for(const fields of [{ids:Array(10001).fill('APP-1')},{members:['x'.repeat(1025)]},{query:'x'.repeat(16001)}]) {
    await assert.rejects(pullTracker({provider:'jira',instance:'office',scope:'linked',...fields},root),/input limits/)
  }
  assert.equal(calls.length,0)
})
