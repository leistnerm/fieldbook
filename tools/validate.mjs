// Offline release/schema/link validation. Requires npm install --ignore-scripts --no-save inside fieldbook_core.
import { readdir, readFile, lstat } from 'node:fs/promises'
import { createRequire } from 'node:module'
import { createHash } from 'node:crypto'
import { spawnSync } from 'node:child_process'
import path from 'node:path'
import { frontmatter } from '../fieldbook_core/lib/vault.js'
const require = createRequire(new URL('../fieldbook_core/package.json', import.meta.url))
const { parseDocument } = require('yaml')
const root = path.resolve(process.argv[2] || '.')
const errors=[], warnings=[]
let jsonCount=0,baseCount=0,skillCount=0,scriptCount=0,embedCount=0,canonicalCount=0
const normalized = text => text.replace(/^\ufeff/,'').replaceAll('\r\n','\n')
const hash = text => createHash('sha256').update(normalized(text)).digest('hex')
async function safe(rel) {
 if(typeof rel!=='string'||!rel||rel.includes('\\')||rel.includes(':')||rel.split('/').some(p=>!p||p==='.'||p==='..')) throw Error(`Unsafe relative path: ${rel}`)
 let target=root
 for(const part of rel.split('/')){
  target=path.join(target,part)
  try {const info=await lstat(target);if(info.isSymbolicLink()||(info.isFile()&&info.nlink!==1))throw Error(`Linked path refused: ${rel}`)}
  catch(e){if(e.code!=='ENOENT')throw e}
 }
 return target
}
async function read(rel) {return readFile(await safe(rel),'utf8')}
async function optional(rel) {try{return await read(rel)}catch(e){if(e.code==='ENOENT')return null;throw e}}
async function walk(dir, rel='') {
 const out=[]
 for(const e of await readdir(path.join(dir,rel),{withFileTypes:true})) {
  if(['node_modules','.git','.obsidian','.venv','.fieldbook','__pycache__'].includes(e.name)) continue
  const p=[rel,e.name].filter(Boolean).join('/')
  if(e.isSymbolicLink()){errors.push(`${p}: Linked path refused`);continue}
  if(e.isDirectory())out.push(...await walk(dir,p));else out.push(p)
 }
 return out
}
async function inspect(rel,text,count=true) {
 try {
  if(rel.endsWith('.json')){JSON.parse(text);if(count)jsonCount++}
  if(rel.endsWith('.base')){const doc=parseDocument(text);if(doc.errors.length)throw Error(doc.errors[0].message);if(count)baseCount++}
  if(rel.endsWith('SKILL.md')){const fm=frontmatter(text);if(fm.name!==path.basename(path.dirname(rel))||!fm.description||fm.description.length>1024)throw Error('Invalid skill identity/description');if(count)skillCount++}
  if(count&&/\.(mjs|js)$/.test(rel)) {const result=spawnSync(process.execPath,['--check',await safe(rel)],{encoding:'utf8'});if(result.status!==0)throw Error(result.stderr);scriptCount++}
  if(rel.endsWith('.md'))for(const match of text.matchAll(/!\[\[([^\]#|]+)(?:#([^\]|]+))?(?:\|[^\]]+)?\]\]/g)){
    const target=match[1]; if(/[<>]/.test(target))continue
    const content=await read(target)
    if(target.endsWith('.base')&&match[2]){const data=parseDocument(content).toJS();if(!data.views?.some(v=>v.name===match[2]))throw Error(`Missing view ${target}#${match[2]}`)}
    if(count)embedCount++
  }
 }catch(e){errors.push(`${rel}: ${e.message}`)}
}
const files=await walk(root)
for(const rel of files){try{await inspect(rel,await read(rel))}catch(e){errors.push(`${rel}: ${e.message}`)}}
const config=JSON.parse(await read('fieldbook.json'))
if(!Array.isArray(config.setups)||config.setups.some(s=>!['personal','work','school'].includes(s)))errors.push('Invalid setup')
if(!['individual-contributor','people-manager'].includes(config.workRole))errors.push('Invalid workRole')
const manifest=JSON.parse(await read('fieldbook-manifest.json'))
const catalogText=await optional('tools/setup-catalog.json'), stateText=await optional('.fieldbook/modules/state.json')
const resources=new Map()
const resourceName = name => typeof name==='string'&&/^(Templates|Setups|Dashboards)\/.+\.md$|^(fieldbook_core|\.opencode)\/(commands\/.+\.md|skills\/.+\/SKILL\.md)$|^Dashboard\.md$/.test(name)
const sha = value => typeof value==='string'&&/^[0-9a-f]{64}$/.test(value)
if(catalogText){
 try {
  const catalog=JSON.parse(catalogText)
  if(catalog.schemaVersion!==1||!Array.isArray(catalog.resources))throw Error('Unsupported setup catalog')
  for(const entry of catalog.resources){
   await safe(entry.path)
   if(resources.has(entry.path)||!resourceName(entry.path))throw Error(`Invalid setup resource: ${entry.path}`)
   if(![undefined,'personal','work','school'].includes(entry.setup)||![undefined,'individual-contributor','people-manager'].includes(entry.workRole)||![undefined,'reviews','jira','agility','github','azure','canvas','google','microsoft'].includes(entry.feature)||![undefined,'dashboard','work'].includes(entry.navigation))throw Error(`Invalid setup gate: ${entry.path}`)
   if(entry.seed&&entry.path!=='Templates/Review-format.md')throw Error(`Unexpected setup seed: ${entry.path}`)
   if(!entry.seed&&!Object.hasOwn(manifest.files,entry.path))throw Error(`Setup resource missing from manifest: ${entry.path}`)
   resources.set(entry.path,entry)
  }
 }catch(e){errors.push(`tools/setup-catalog.json: ${e.message}`)}
}
let state=null
if(stateText){
 try {
  state=JSON.parse(stateText)
  if(state.schemaVersion!==1||!state.resources||typeof state.resources!=='object'||Array.isArray(state.resources))throw Error('Unsupported setup activation state')
  if(!catalogText)throw Error('Setup state requires its catalog')
  for(const [name,record] of Object.entries(state.resources)){
   await safe(name)
   if(!resourceName(name)||!record||typeof record!=='object'||Array.isArray(record)||(!resources.has(name)&&record.retired!==true))throw Error(`Unknown or invalid activation resource: ${name}`)
  }
 }catch(e){errors.push(`.fieldbook/modules/state.json: ${e.message}`);state=null}
}
const enabled = entry => (!entry.setup||config.setups.includes(entry.setup))&&(!entry.workRole||entry.workRole===config.workRole)&&(!entry.feature||config.features?.[entry.feature]===true)
function navigation(text,kind,settings=config) {
 if(!kind)return text
 const start='<!-- fieldbook:setup-navigation:start -->',end='<!-- fieldbook:setup-navigation:end -->'
 if(text.split(start).length!==2||text.split(end).length!==2)throw Error('Setup navigation needs exactly one marker pair')
 const links=[]
 if(kind==='dashboard')for(const setup of ['personal','work','school'])if(settings.setups.includes(setup)){
  const title=setup[0].toUpperCase()+setup.slice(1);links.push(`[[Dashboards/${title}|${title} dashboard]]`)
 }
 if(settings.setups.includes('work')){
  const manager=settings.workRole==='people-manager',role=manager?'People manager':'Individual contributor'
  links.push(`[[Dashboards/${manager?'People management':'Work - Individual contributor'}|${role}]]`)
  if(settings.features?.reviews)links.push('[[Views/Reviews.base|Formal reviews]]')
  if(kind==='work')links.push('[[Setups/Work specializations|Domain ideas]]')
 }
 return text.slice(0,text.indexOf(start)+start.length)+'\n'+(links.length?links.join(' · '):'Shared Dashboard is ready. Enable optional setups in [[Setups]].')+'\n'+text.slice(text.indexOf(end))
}
async function proof(name){
 if(typeof name!=='string'||!/^\.fieldbook\/modules\/proofs\/[0-9a-f]{64}\.json$/.test(name))throw Error('Invalid historical proof path')
 const text=await read(name)
 if(hash(text)!==path.basename(name,'.json'))throw Error('Historical proof content/hash mismatch')
 return {text,data:JSON.parse(text)}
}
async function proven(name,source){
 if(!source||typeof source!=='object'||Array.isArray(source)||!source.manifest||Object.keys(source).some(k=>!['manifest','seeds'].includes(k)))throw Error('Invalid historical module source')
 const historical=(await proof(source.manifest)).data
 let expected=historical.files?.[name]
 if(source.seeds!==undefined){
  if(name!=='Templates/Review-format.md')throw Error('Unexpected historical module seed')
  const seedProof=await proof(source.seeds)
  if(hash(seedProof.text)!==historical.files?.['tools/starter-seeds.json']||typeof seedProof.data[name]!=='string')throw Error('Historical seed differs from verified source')
  expected=hash(seedProof.data[name])
 }
 if(!sha(expected))throw Error('Missing historical source hash')
 return expected
}
async function candidate(name,record){
 if(record.candidateHash===undefined&&record.candidateSource===undefined)return
 if(!sha(record.candidateHash))throw Error('Invalid candidate ownership hash')
 const source=record.candidateSource
 if(!source||typeof source!=='object'||Array.isArray(source)||Object.keys(source).sort().join(',')!=='config,content,manifest,navigation')throw Error('Invalid candidate source proof')
 const expected=await proven(name,{manifest:source.manifest}),content=(await proof(source.content)).data,settings=source.config
 if(content?.path!==name||typeof content?.text!=='string'||hash(content.text)!==expected)throw Error('Candidate canonical differs from historical manifest')
 if(![null,'dashboard','work'].includes(source.navigation)||!settings||!Array.isArray(settings.setups)||settings.setups.some(s=>!['personal','work','school'].includes(s))||!['individual-contributor','people-manager'].includes(settings.workRole)||typeof settings.features?.reviews!=='boolean')throw Error('Invalid candidate render inputs')
 if(hash(navigation(content.text,source.navigation,settings))!==record.candidateHash)throw Error('Candidate hash differs from reconstructed content')
 const actual=await optional(name+'.fieldbook-new')
 if(actual===null)warnings.push(`Previously generated merge candidate is absent: ${name}.fieldbook-new`)
 else if(hash(actual)!==record.candidateHash)warnings.push(`Edited merge candidate preserved: ${name}.fieldbook-new`)
}
const seedsText=state?await optional('tools/starter-seeds.json'):null
const seeds=seedsText?JSON.parse(seedsText):{}
for(const [rel,expected] of Object.entries(manifest.files)){
 if(state&&resources.has(rel))continue // Verified below against its canonical bank and active state.
 try {if(hash(await read(rel))!==expected)errors.push(`Manifest mismatch: ${rel}`)}catch(e){errors.push(`Manifest file missing or unsafe: ${rel}: ${e.message}`)}
}
if(state)for(const [name,entry] of resources){
 try {
  const installed=state.resources[name]
  if(!installed||typeof installed.enabled!=='boolean'||typeof installed.removed!=='boolean')throw Error('Missing or invalid activation record')
  const wanted=enabled(entry)
  if(installed.enabled!==wanted)throw Error('Setup activation differs from fieldbook.json; run configure')
  const canonical=await read('.fieldbook/modules/files/'+name)
  const expected=entry.seed?(typeof seeds[name]==='string'?hash(seeds[name]):null):manifest.files[name]
  if(!expected||hash(canonical)!==expected||installed.bankHash!==expected)throw Error('Canonical module hash differs from verified manifest/seed')
  canonicalCount++
  await inspect(name,canonical,false)
  const active=await optional(name)
  if(active===null){
   if(wanted&&!installed.removed)throw Error('Enabled module is missing')
   if(installed.removed)warnings.push(`User-removed module remains absent: ${name}`)
  }else if(installed.preserved===true){
   warnings.push(`Customized module preserved${wanted?'':' while setup disabled'}: ${name}`)
  }else{
   if(!wanted)throw Error('Inactive module remains installed without a preservation exception')
   const rendered=navigation(canonical,entry.navigation)
   if(hash(active)!==hash(rendered)||installed.activeHash!==hash(rendered))throw Error('Active module differs from expected configured content')
  }
 }catch(e){errors.push(`${name}: ${e.message}`)}
}
if(state)for(const [name,record] of Object.entries(state.resources)){
 try{
  await candidate(name,record)
  if(resources.has(name))continue
  if(record.retired!==true||record.enabled!==false||typeof record.removed!=='boolean'||typeof record.preserved!=='boolean'||!(record.activeHash===null||sha(record.activeHash))||!sha(record.bankHash))throw Error('Invalid retired module record')
  const expected=await proven(name,record.source),canonical=await read('.fieldbook/modules/files/'+name)
  if(record.bankHash!==expected||hash(canonical)!==expected)throw Error('Retired canonical differs from historical manifest/seed')
  canonicalCount++
  // A resource that became shared is already covered by the current manifest.
  if(Object.hasOwn(manifest.files,name))continue
  const active=await optional(name)
  if(active!==null){
   if(!record.preserved)throw Error('Pristine retired module remains installed')
   warnings.push(`Retired customized module preserved: ${name}`)
  }
 }catch(e){errors.push(`${name}: ${e.message}`)}
}
if(manifest.version!==(await read('VERSION')).trim())errors.push('Manifest version differs from VERSION')
console.log(JSON.stringify({mode:state?'configured-vault':'source-kit',jsonCount,baseCount,skillCount,scriptCount,embedCount,canonicalCount,manifestFiles:Object.keys(manifest.files).length,warnings,errors},null,2))
if(errors.length)process.exitCode=1
