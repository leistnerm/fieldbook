import test from 'node:test'
import assert from 'node:assert/strict'
import { credentialEnvironment } from '../fieldbook_core/lib/credentials.js'
const instance={id:'school',baseUrl:'https://school.example.test',tokenVar:'CANVAS_TOKEN',credentialStore:'keyring'}

test('environment credentials do not access the keyring or mutate environment', async()=>{
  const env={CANVAS_TOKEN:'fixture'}
  const result=await credentialEnvironment('/vault','canvas',{id:'school',tokenVar:'CANVAS_TOKEN'},env,undefined,()=>{throw Error('unexpected')})
  assert.equal(result,env)
})
test('keyring mode is explicit, overrides only the requested key, and never mutates global environment',async()=>{
  const env={CANVAS_TOKEN:'stale',OTHER:'preserved'}
  const result=await credentialEnvironment('/vault','canvas',instance,env,undefined,async(root,provider,expected)=>{
    assert.equal(root,'/vault');assert.equal(provider,'canvas');assert.deepEqual(expected,{id:'school',baseUrl:'https://school.example.test',tokenVar:'CANVAS_TOKEN'});return 'saved-key'
  })
  assert.deepEqual(result,{CANVAS_TOKEN:'saved-key',OTHER:'preserved'})
  assert.equal(env.CANVAS_TOKEN,'stale')
})
test('keyring failures never use a stale environment key and invalid references fail before lookup',async()=>{
  await assert.rejects(credentialEnvironment('/vault','canvas',instance,{CANVAS_TOKEN:'stale'},undefined,async()=>{throw Error('locked')}),/locked/)
  for(const instance of [{tokenVar:'OTHER_TOKEN'},{tokenVar:'CANVAS_TOKEN',credentialStore:'plaintext'}]){
    await assert.rejects(credentialEnvironment('/vault','canvas',instance,{},undefined,()=>{throw Error('lookup must not run')}),/Invalid credential|credentialStore/)
  }
})
test('keys with header controls and oversized responses fail',async()=>{
  for(const key of ['','key\nheader','x'.repeat(16385)]){
    await assert.rejects(credentialEnvironment('/vault','canvas',instance,{},undefined,async()=>key),/invalid key/)
  }
})
test('invalid destination and instance fail before attempting a saved key lookup',async()=>{
  for(const change of [{id:'../other'},{baseUrl:'http://school.test'},{baseUrl:'https://school.test?token=fixture-secret'},{baseUrl:'https://user:fixture-secret@school.test'},{baseUrl:'https://school.test/\u001bpath'}]) {
    await assert.rejects(credentialEnvironment('/vault','canvas',{...instance,...change},{},undefined,()=>assert.fail('must not look up credentials')),/Invalid credential/)
  }
})
