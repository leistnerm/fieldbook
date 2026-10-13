import test from 'node:test'
import assert from 'node:assert/strict'
import { notebook, tracker } from '../fieldbook_core/lib/notebook-bridge.js'

test('a denied write stops after a non-mutating preview', async () => {
  const operations = []
  const run = async args => { operations.push(args.operation); return { diff: '+hello' } }
  const context = { ask: async req => { assert.equal(req.permission, 'notebook_write'); assert.equal(req.metadata.diff, '+hello'); throw Error('denied') } }
  await assert.rejects(notebook('write', {path:'Notes/Hello.md',text:'hello',expected:'missing'}, context, run), /denied/)
  assert.deepEqual(operations, ['preview'])
})
test('write approval includes exact path and preserves conflict token', async () => {
  const calls=[]
  const args={path:'Notes/Hello.md',text:'hello',expected:'abc'}
  const run=async input=>{calls.push(input);return {diff:'+hello'}}
  const context={ask:async req=>{calls.push(req);assert.deepEqual(req.always,['Notes/Hello.md'])}}
  await notebook('write',args,context,run)
  assert.equal(calls[2].expected,'abc')
  assert.equal(calls[2].operation,'write')
})
test('read/search permission is checked before running the process', async () => {
  let ran=false
  await assert.rejects(notebook('search',{query:'x'},{ask:async()=>{throw Error('denied')}},async()=>{ran=true}),/denied/)
  assert.equal(ran,false)
})
test('tracker permission denied never starts network adapter', async () => {
  for (const provider of ['jira','agility','github','azure']) {
    let ran=false
    await assert.rejects(tracker({provider,instance:'office',scope:'mine'},{ask:async()=>{throw Error('denied')}},async()=>{ran=true}),/denied/)
    assert.equal(ran,false)
  }
})
test('tracker passes JQL as data to the in-process read adapter', async () => {
  const query='project = APP AND text ~ "$(echo no)"'
  await tracker({provider:'jira',instance:'office',scope:'all',query},{ask:async()=>{}},async(args,root)=>{
    assert.equal(args.query,query);assert.ok(root);return {items:[]}
  })
})

test('calendar read permission is checked before parsing and cannot silently create notes', async () => {
  let ran = false
  await assert.rejects(notebook('calendar', {path:'Attachments/event.ics'}, {ask:async request=>{
    assert.equal(request.permission,'notebook_calendar')
    assert.deepEqual(request.patterns,['Attachments/event.ics'])
    throw Error('denied')
  }}, async()=>{ran=true}), /denied/)
  assert.equal(ran,false)
})

test('sync field preview reuses read-only preview permission without a write or tracker call',async()=>{
  const args={path:'Tasks/A.md',expected:'sha',sync:{source:{provider:'jira',instance:'office',id:'APP-1'},proposed:{status:'active'}}}
  const operations=[]
  const result=await notebook('preview',args,{ask:async request=>assert.equal(request.permission,'notebook_preview')},async request=>{
    operations.push(request.operation);assert.deepEqual(request.sync,args.sync);return {changed:false,fields:[{classification:'first_sync'}]}
  })
  assert.deepEqual(operations,['preview']);assert.equal(JSON.parse(result).changed,false)
})
