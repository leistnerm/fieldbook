import test from 'node:test'
import assert from 'node:assert/strict'
import { azureId, azureQuery, normalizeAzure, pullAzure } from '../fieldbook_core/lib/azure.js'
import { connection } from '../fieldbook_core/lib/trackers.js'
const config={id:'office',baseUrl:'https://dev.azure.com/example',project:'Class Project',tokenVar:'AZURE_TOKEN',filter:"[System.WorkItemType] = 'Task'"}
const item=id=>({id,fields:{'System.Title':`Item ${id}`,'System.State':'Active','System.AssignedTo':{uniqueName:'alex@example.test',id:'guid',displayName:'Alex'},'System.TeamProject':'Class Project','System.WorkItemType':'Task','System.Description':'<p>Source</p>'}})

test('Azure discovery requires a project and builds stable, escaped owner filters',()=>{
  assert.throws(()=>azureQuery({...config,project:''},{scope:'all'}),/explicit/)
  assert.match(azureQuery(config,{scope:'mine'}),/AssignedTo\] = @Me/)
  const query=azureQuery(config,{scope:'team',self:'me@example.test',members:["o'brien@example.test"]})
  assert.match(query,/TeamProject\] = 'Class Project'/);assert.ok(query.includes('"o\'brien@example.test"'));assert.match(query,/ORDER BY \[System.Id\] ASC$/)
  assert.throws(()=>azureQuery(config,{scope:'mine',self:`bad'"identity`}),/both quote styles/)
  assert.throws(()=>azureQuery(config,{scope:'team'}),/report identities/)
  assert.throws(()=>azureQuery(config,{scope:'all',query:'SELECT * FROM WorkItems'}),/WHERE/)
  assert.throws(()=>azureId('12 OR 1=1'),/positive/)
})
test('Azure query caps results, batches at 200, preserves snapshot and returns selected fields',async()=>{
  const calls=[]
  const r=await pullAzure(config,{scope:'all',limit:201},async(p,q,b)=>{
    calls.push([p,q,b])
    return p.endsWith('/wiql')?{asOf:'2026-10-10T00:00:00Z',workItems:Array.from({length:202},(_,i)=>({id:i+1}))}:{value:b.ids.map(item)}
  })
  assert.equal(r.items.length,201);assert.equal(r.truncated,true)
  assert.equal(calls[0][0],'/Class%20Project/_apis/wit/wiql');assert.equal(calls[0][1].$top,202)
  assert.deepEqual(calls.slice(1).map(c=>c[2].ids.length),[200,1]);assert.equal(calls[1][2].asOf,'2026-10-10T00:00:00Z')
  assert.equal(calls[1][2].errorPolicy,'Fail');assert.equal(r.items[0].assignees[0].id,'alex@example.test')
})
test('Azure linked reads ignore discovery project/filter and deduplicate IDs without WIQL',async()=>{
  const calls=[]
  const r=await pullAzure({...config,project:''},{scope:'linked',ids:['42','42','43']},async(p,q,b)=>{calls.push([p,q,b]);return{value:b.ids.map(item).reverse()}})
  assert.equal(calls.length,1);assert.equal(calls[0][0],'/_apis/wit/workitemsbatch');assert.deepEqual(r.items.map(i=>i.id),['42','43'])
  assert.equal(r.truncated,false);assert.equal(r.items[0].url,'https://dev.azure.com/example/_workitems/edit/42')
})
test('Azure empty discovery is successful without batch requests; exact cap is not truncated',async()=>{
  let count=0
  const r=await pullAzure(config,{scope:'mine'},async()=>{count++;return {workItems:[]}})
  assert.deepEqual(r.items,[]);assert.equal(count,1)
  const exact=await pullAzure(config,{scope:'all',limit:1},async(p,q,b)=>p.endsWith('/wiql')?{workItems:[{id:1}]}:{value:b.ids.map(item)})
  assert.equal(exact.truncated,false)
})
test('Azure unavailable dates stay null; configured process field names are read explicitly',async()=>{
  assert.equal(normalizeAzure(item(1),config).due,null);assert.equal(normalizeAzure(item(1),config).completed,null)
  const configured={...config,dueField:'Custom.Due',completionField:'Microsoft.VSTS.Common.ClosedDate'}
  const r=await pullAzure(configured,{scope:'linked',ids:['1']},async(p,q,b)=>{
    assert.ok(b.fields.includes('Custom.Due'));const a=item(1);a.fields['Custom.Due']='2026-11-01';return {value:[a]}
  })
  assert.equal(r.items[0].due,'2026-11-01');assert.equal(r.items[0].completed,null)
  await assert.rejects(pullAzure({...config,dueField:'bad field'},{scope:'linked',ids:['1']},async()=>assert.fail()),/reference/)
})
test('Azure missing, extra or repeated batch records and later failures never return partial success',async()=>{
  for(const values of [[],[item(2)],[item(1),item(1)]]) await assert.rejects(pullAzure(config,{scope:'linked',ids:['1']},async()=>({value:values})),/missing or mismatches/)
  let calls=0
  await assert.rejects(pullAzure(config,{scope:'linked',ids:Array.from({length:201},(_,i)=>String(i+1))},async(p,q,b)=>{if(calls++)throw Error('offline');return {value:b.ids.map(item)}}),/offline/)
  await assert.rejects(pullAzure(config,{scope:'all'},async()=>({workItemRelations:[]})),/Unexpected/)
})
test('Azure permits only query/batch POST reads, uses PAT Basic auth, and blocks write routes',async()=>{
  const calls=[]
  const request=connection('azure',config,{AZURE_TOKEN:'fixture-pat'},async(u,o)=>{calls.push([u,o]);return Response.json({})})
  await request('/Class%20Project/_apis/wit/wiql',{'api-version':'7.1'},{query:'SELECT [System.Id] FROM WorkItems'})
  await request('/_apis/wit/workitemsbatch',{}, {ids:[1]})
  assert.equal(calls.length,2);assert.ok(calls.every(c=>c[1].method==='POST'))
  assert.equal(Buffer.from(calls[0][1].headers.Authorization.slice(6),'base64').toString(),':fixture-pat')
  for(const p of ['/_apis/wit/workitems/$Task','/_apis/wit/workitems/1','/_apis/wit/workitems/1/comments']) await assert.rejects(request(p,{},{}),/read-only/)
  await assert.rejects(request('/_apis/wit/workitemsbatch'),/read-only/)
  assert.equal(calls.length,2)
})
