import test from 'node:test'
import assert from 'node:assert/strict'
import { mkdtemp, mkdir, writeFile, readFile, rm, unlink, symlink, realpath } from 'node:fs/promises'
import { tmpdir } from 'node:os'
import path from 'node:path'
import { fileURLToPath } from 'node:url'
import { createHash } from 'node:crypto'
import { spawnSync } from 'node:child_process'

const validator=fileURLToPath(new URL('../tools/validate.mjs',import.meta.url))
const hash=text=>createHash('sha256').update(text).digest('hex')
async function fixture(t){
 const root=await realpath(await mkdtemp(path.join(tmpdir(),'fieldbook-validation-')))
 t.after(()=>rm(root,{recursive:true,force:true}))
 const put=async(name,text)=>{await mkdir(path.dirname(path.join(root,name)),{recursive:true});await writeFile(path.join(root,name),text)}
 const course='---\ntags: [project, course]\narea: school\n---\n'
 const task='---\ntags: [task]\n---\n'
 const config={setups:[],workRole:'individual-contributor',features:{reviews:false}}
 const catalog={schemaVersion:1,resources:[{path:'Templates/Project - Course.md',setup:'school'}]}
 const contents={'VERSION':'0.7.0\n','Templates/Task.md':task,'Templates/Project - Course.md':course,'tools/setup-catalog.json':JSON.stringify(catalog)}
 const manifest={version:'0.7.0',files:Object.fromEntries(Object.entries(contents).map(([n,text])=>[n,hash(text)]))}
 for(const [name,text] of Object.entries(contents))await put(name,text)
 await put('fieldbook-manifest.json',JSON.stringify(manifest))
 await put('fieldbook.json',JSON.stringify(config))
 const state={schemaVersion:1,resources:{'Templates/Project - Course.md':{enabled:false,removed:false,preserved:false,activeHash:hash(course),bankHash:hash(course)}}}
 const activate=async()=>{
  await put('.fieldbook/modules/files/Templates/Project - Course.md',course)
  await put('.fieldbook/modules/state.json',JSON.stringify(state))
  await unlink(path.join(root,'Templates/Project - Course.md'))
 }
 const run=()=>{
  const result=spawnSync(process.execPath,[validator,root],{encoding:'utf8'})
  assert.ok(result.stdout, result.stderr)
  return {code:result.status,...JSON.parse(result.stdout)}
 }
 return {root,put,course,contents,config,catalog,manifest,state,activate,run}
}

test('validator checks full source and the verified disabled canonical copy',async t=>{
 const f=await fixture(t)
 let result=f.run();assert.equal(result.code,0);assert.equal(result.mode,'source-kit')
 await f.activate()
 result=f.run();assert.equal(result.code,0,JSON.stringify(result.errors));assert.equal(result.mode,'configured-vault');assert.equal(result.canonicalCount,1)
})

test('disabled status cannot hide a missing or changed canonical copy or missing core file',async t=>{
 const f=await fixture(t);await f.activate()
 await f.put('.fieldbook/modules/files/Templates/Project - Course.md','tampered')
 let result=f.run();assert.equal(result.code,1);assert.ok(result.errors.some(x=>x.includes('Canonical module hash')))
 await f.put('.fieldbook/modules/files/Templates/Project - Course.md',f.course)
 await unlink(path.join(f.root,'.fieldbook/modules/files/Templates/Project - Course.md'))
 result=f.run();assert.equal(result.code,1);assert.ok(result.errors.some(x=>x.startsWith('Templates/Project - Course.md:')))
 await f.put('.fieldbook/modules/files/Templates/Project - Course.md',f.course)
 await unlink(path.join(f.root,'Templates/Task.md'))
 result=f.run();assert.equal(result.code,1);assert.ok(result.errors.some(x=>x.includes('Templates/Task.md')))
})

test('source and activation metadata cannot silently skip missing optional files',async t=>{
 const f=await fixture(t)
 await unlink(path.join(f.root,'Templates/Project - Course.md'))
 assert.equal(f.run().code,1)
 await f.put('.fieldbook/modules/state.json',JSON.stringify({schemaVersion:1,resources:{}}))
 assert.ok(f.run().errors.some(x=>x.includes('Missing or invalid activation record')))
})

test('configuration drift and unexpected active optional files fail validation',async t=>{
 const f=await fixture(t);await f.activate()
 await f.put('Templates/Project - Course.md',f.course)
 assert.ok(f.run().errors.some(x=>x.includes('Inactive module remains installed')))
 await unlink(path.join(f.root,'Templates/Project - Course.md'))
 await f.put('fieldbook.json',JSON.stringify({...f.config,setups:['school']}))
 assert.ok(f.run().errors.some(x=>x.includes('activation differs')))
})

test('explicit preservation exceptions warn without deleting or rejecting custom content',async t=>{
 const f=await fixture(t);await f.activate()
 await f.put('Templates/Project - Course.md',f.course+'My own section\n')
 f.state.resources['Templates/Project - Course.md'].preserved=true
 await f.put('.fieldbook/modules/state.json',JSON.stringify(f.state))
 const result=f.run()
 assert.equal(result.code,0,JSON.stringify(result.errors))
 assert.ok(result.warnings.some(x=>x.includes('Customized module preserved while setup disabled')))
})

test('a forged activeHash cannot bless an altered active module',async t=>{
 const f=await fixture(t);await f.activate()
 const altered=f.course+'Untracked changes\n'
 await f.put('fieldbook.json',JSON.stringify({...f.config,setups:['school']}))
 await f.put('Templates/Project - Course.md',altered)
 Object.assign(f.state.resources['Templates/Project - Course.md'],{enabled:true,activeHash:hash(altered)})
 await f.put('.fieldbook/modules/state.json',JSON.stringify(f.state))
 assert.ok(f.run().errors.some(x=>x.includes('Active module differs')))
})

test('linked canonical recovery files are never followed',async t=>{
 const f=await fixture(t);await f.activate()
 await f.put('Other.md',f.course)
 await unlink(path.join(f.root,'.fieldbook/modules/files/Templates/Project - Course.md'))
 try{await symlink(path.join(f.root,'Other.md'),path.join(f.root,'.fieldbook/modules/files/Templates/Project - Course.md'))}
 catch(error){if(['EPERM','EACCES'].includes(error.code)){t.skip('Host cannot create symlinks');return}throw error}
 assert.ok(f.run().errors.some(x=>x.includes('Linked path refused')))
})

test('generated navigation is checked against enabled setups, not just a stored hash',async t=>{
 const f=await fixture(t);await f.activate()
 const start='<!-- fieldbook:setup-navigation:start -->',end='<!-- fieldbook:setup-navigation:end -->'
 const canonical=`# Fieldbook\n${start}\n[[Dashboards/School|School dashboard]]\n${end}\n`
 const rendered=`# Fieldbook\n${start}\nShared Dashboard is ready. Enable optional setups in [[Setups]].\n${end}\n`
 f.catalog.resources.push({path:'Dashboard.md',navigation:'dashboard'})
 const catalogText=JSON.stringify(f.catalog)
 f.manifest.files['tools/setup-catalog.json']=hash(catalogText)
 f.manifest.files['Dashboard.md']=hash(canonical)
 await f.put('tools/setup-catalog.json',catalogText)
 await f.put('fieldbook-manifest.json',JSON.stringify(f.manifest))
 await f.put('.fieldbook/modules/files/Dashboard.md',canonical)
 await f.put('Dashboard.md',rendered)
 f.state.resources['Dashboard.md']={enabled:true,removed:false,preserved:false,bankHash:hash(canonical),activeHash:hash(rendered)}
 await f.put('.fieldbook/modules/state.json',JSON.stringify(f.state))
 assert.equal(f.run().code,0)
 await f.put('Dashboard.md',canonical)
 f.state.resources['Dashboard.md'].activeHash=hash(canonical)
 await f.put('.fieldbook/modules/state.json',JSON.stringify(f.state))
 assert.ok(f.run().errors.some(x=>x.startsWith('Dashboard.md: Active module differs')))
})

async function addProof(f,data){
 const text=JSON.stringify(data),name=`.fieldbook/modules/proofs/${hash(text)}.json`
 await f.put(name,text)
 return name
}
async function retire(f){
 await f.activate()
 const prior=JSON.parse(JSON.stringify(f.manifest))
 f.catalog.resources=[]
 const catalogText=JSON.stringify(f.catalog)
 f.manifest.files['tools/setup-catalog.json']=hash(catalogText)
 delete f.manifest.files['Templates/Project - Course.md']
 await f.put('tools/setup-catalog.json',catalogText)
 await f.put('fieldbook-manifest.json',JSON.stringify(f.manifest))
 Object.assign(f.state.resources['Templates/Project - Course.md'],{retired:true,source:{manifest:await addProof(f,prior)}})
 await f.put('.fieldbook/modules/state.json',JSON.stringify(f.state))
}

test('retired modules require historical proof and preserve only marked custom active copies',async t=>{
 const f=await fixture(t);await retire(f)
 assert.equal(f.run().code,0)
 await f.put('Templates/Project - Course.md',f.course)
 assert.ok(f.run().errors.some(x=>x.includes('Pristine retired module remains installed')))
 f.state.resources['Templates/Project - Course.md'].preserved=true
 await f.put('Templates/Project - Course.md',f.course+'My custom history\n')
 await f.put('.fieldbook/modules/state.json',JSON.stringify(f.state))
 const result=f.run();assert.equal(result.code,0);assert.ok(result.warnings.some(x=>x.includes('Retired customized')))
 await f.put('.fieldbook/modules/files/Templates/Project - Course.md','altered cache')
 assert.ok(f.run().errors.some(x=>x.includes('Retired canonical differs')))
})

test('retired state cannot bless edited or unknown historical sources',async t=>{
 const f=await fixture(t);await retire(f)
 const source=f.state.resources['Templates/Project - Course.md'].source.manifest
 await f.put(source,'{}')
 assert.ok(f.run().errors.some(x=>x.includes('proof content/hash mismatch')))
 delete f.state.resources['Templates/Project - Course.md'].retired
 await f.put('.fieldbook/modules/state.json',JSON.stringify(f.state))
 assert.ok(f.run().errors.some(x=>x.includes('Unknown or invalid activation')))
})

test('retired modules that became shared still undergo normal manifest validation',async t=>{
 const f=await fixture(t);await retire(f)
 f.manifest.files['Templates/Project - Course.md']=hash(f.course)
 await f.put('fieldbook-manifest.json',JSON.stringify(f.manifest))
 await f.put('Templates/Project - Course.md',f.course)
 assert.equal(f.run().code,0)
 await unlink(path.join(f.root,'Templates/Project - Course.md'))
 assert.ok(f.run().errors.some(x=>x.includes('Manifest file missing or unsafe: Templates/Project - Course.md')))
})

test('candidate ownership is reconstructed from proofs and edited candidates are warnings',async t=>{
 const f=await fixture(t);await f.activate()
 Object.assign(f.state.resources['Templates/Project - Course.md'],{
  candidateHash:hash(f.course),candidateSource:{manifest:await addProof(f,f.manifest),
   content:await addProof(f,{path:'Templates/Project - Course.md',text:f.course}),navigation:null,
   config:{setups:[],workRole:'individual-contributor',features:{reviews:false}}}})
 await f.put('.fieldbook/modules/state.json',JSON.stringify(f.state))
 await f.put('Templates/Project - Course.md.fieldbook-new',f.course)
 assert.equal(f.run().code,0)
 await f.put('Templates/Project - Course.md.fieldbook-new','My pending edits\n')
 const result=f.run();assert.equal(result.code,0);assert.ok(result.warnings.some(x=>x.includes('Edited merge candidate preserved')))
 f.state.resources['Templates/Project - Course.md'].candidateHash=hash('My pending edits\n')
 await f.put('.fieldbook/modules/state.json',JSON.stringify(f.state))
 assert.ok(f.run().errors.some(x=>x.includes('Candidate hash differs from reconstructed')))
})

test('real deploy and configure output validates for core, combined and work manager setups',async t=>{
 const f=await fixture(t)
 const sourceRoot=fileURLToPath(new URL('../',import.meta.url))
 const start='<!-- fieldbook:setup-navigation:start -->',end='<!-- fieldbook:setup-navigation:end -->'
 const dashboard=`# Fieldbook\n${start}\nDistribution navigation\n${end}\n`
 f.catalog.resources.push({path:'Dashboard.md',navigation:'dashboard'}, {path:'Dashboards/Work.md',setup:'work',navigation:'work'})
 const config={...f.config,defaults:{area:''}}
 const contents={...f.contents,'tools/setup-catalog.json':JSON.stringify(f.catalog),
  'Dashboard.md':dashboard,'Dashboards/Work.md':dashboard,'LICENSE':'Test fixture\n',
  'tools/starter-seeds.json':JSON.stringify({'fieldbook.json':JSON.stringify(config)}),
  'tools/starter-plugins.json':'{"plugins":[]}',
  'tools/starter-settings.json':JSON.stringify({'.obsidian/plugins/tasknotes/data.json':{userFields:[]}})}
 for(const [name,text]of Object.entries(contents))await f.put(name,text)
 f.manifest.files=Object.fromEntries(Object.entries(contents).map(([name,text])=>[name,hash(text)]))
 await f.put('fieldbook-manifest.json',JSON.stringify(f.manifest))
 const destination=f.root+'-deployed'
 t.after(()=>rm(destination,{recursive:true,force:true}))
 const python=process.env.PYTHON||(process.platform==='win32'?'python':'python3')
 function call(code,args=[]){
  const result=spawnSync(python,['-c',code,sourceRoot,f.root,destination,...args],{encoding:'utf8'})
  assert.equal(result.status,0,result.stderr||result.stdout)
 }
 call(`import importlib.util,sys\nfrom pathlib import Path\np=Path(sys.argv[1])/'tools/deploy-vault.py'\ns=importlib.util.spec_from_file_location('deploy',p);m=importlib.util.module_from_spec(s);s.loader.exec_module(m)\nm.deploy(Path(sys.argv[2]),Path(sys.argv[3]),[],'individual-contributor',True,False)\n`)
 function verify(){
  const result=spawnSync(process.execPath,[validator,destination],{encoding:'utf8'})
  assert.equal(result.status,0,result.stdout||result.stderr)
  assert.equal(JSON.parse(result.stdout).mode,'configured-vault')
 }
 verify()
 for(const setups of ['personal,work,school','work','core']){
  call(`import importlib.util,sys,argparse\nfrom pathlib import Path\np=Path(sys.argv[1])/'tools/manage-vault.py'\ns=importlib.util.spec_from_file_location('admin',p);m=importlib.util.module_from_spec(s);s.loader.exec_module(m)\na=argparse.Namespace(setups=sys.argv[4],work_role='people-manager',work_focus=None,work_subrole=None,jira=None,agility=None,github=None,azure=None,canvas=None,reviews=None,auto_people=None,auto_commit=None,apply=True)\nm.configure(Path(sys.argv[3]),a)\n`,[setups])
  verify()
  if(setups==='work'){
   const file=path.join(destination,'Dashboard.md')
   await writeFile(file,(await readFile(file,'utf8'))+'\nMy custom dashboard section.\n')
  }
 }
})

test('retired protected review form proves its seed against the historical manifest',async t=>{
 const f=await fixture(t);await retire(f)
 const name='Templates/Review-format.md',form='---\ntags: [review]\n---\nOriginal organization form\n'
 const seedText=JSON.stringify({[name]:form})
 const historical={version:'earlier',files:{'tools/starter-seeds.json':hash(seedText)}}
 const seedPath=`.fieldbook/modules/proofs/${hash(seedText)}.json`
 await f.put(seedPath,seedText)
 f.state.resources[name]={retired:true,enabled:false,removed:false,preserved:false,activeHash:hash(form),bankHash:hash(form),
  source:{manifest:await addProof(f,historical),seeds:seedPath}}
 await f.put('.fieldbook/modules/files/'+name,form)
 await f.put('.fieldbook/modules/state.json',JSON.stringify(f.state))
 assert.equal(f.run().code,0)
 f.state.resources[name].source.seeds=await addProof(f,{[name]:'A different form'})
 await f.put('.fieldbook/modules/state.json',JSON.stringify(f.state))
 assert.ok(f.run().errors.some(x=>x.includes('Historical seed differs from verified source')))
})
