import test from 'node:test'
import assert from 'node:assert/strict'
import { connection, jiraQuery, pullJira, pullAgility, agilityQueries, identity, normalizeJira } from '../fieldbook_core/lib/trackers.js'
const jira={id:'office',flavor:'cloud',baseUrl:'https://example.test',tokenVar:'JIRA_TOKEN',email:'a@example.test'}
const agility={id:'office',baseUrl:'https://example.test/agility',tokenVar:'AGILITY_TOKEN',memberId:'Member:1',where:{Scope:'Scope:100'}}
const issue=(id)=>({key:id,fields:{summary:'A task',status:{name:'Done',statusCategory:{key:'done'}},assignee:{accountId:'u1',displayName:'Alex'},description:{type:'doc',content:[{type:'paragraph',content:[{type:'text',text:'Evidence'}]}]}}})
test('all is explicitly bounded; linked never inherits a scope that could hide tickets',()=>{
 assert.throws(()=>jiraQuery(jira,{scope:'all'}),/explicit/)
 assert.match(jiraQuery({...jira,filter:'project = APP'},{scope:'mine'}),/currentUser\(\).*project = APP/)
 assert.equal(jiraQuery({...jira,filter:'project = OTHER'},{scope:'linked',ids:['APP-1']}),'key in ("APP-1") ORDER BY key ASC')
 assert.throws(()=>jiraQuery(jira,{scope:'team'}),/report/)
})
test('Cloud pagination uses nextPageToken; content is normalized',async()=>{
 const calls=[]; const result=await pullJira(jira,{scope:'mine'},async(p,q)=>{calls.push([p,q]);return calls.length===1?{issues:[issue('APP-1')],isLast:false,nextPageToken:'next'}:{issues:[issue('APP-2')],isLast:true}})
 assert.equal(result.items.length,2); assert.equal(result.items[0].description,'Evidence');assert.equal(calls[1][1].nextPageToken,'next');assert.equal(calls[0][0],'/rest/api/3/search/jql')
})
test('Data Center pagination advances startAt',async()=>{
 const calls=[];await pullJira({...jira,flavor:'server'},{scope:'mine'},async(p,q)=>{calls.push(q.startAt);return {issues:[issue(`APP-${q.startAt+1}`)],total:2}});assert.deepEqual(calls,[0,1])
})
test('sync caps are explicit; failed second pages do not return success',async()=>{
 const r=await pullJira(jira,{scope:'mine',limit:1},async()=>({issues:[issue('APP-1')],isLast:false,nextPageToken:'x'}));assert.equal(r.truncated,true)
 let n=0;await assert.rejects(pullJira(jira,{scope:'mine'},async()=>{if(n++)throw Error('offline');return {issues:[issue('APP-1')],nextPageToken:'x',isLast:false}}),/offline/)
})
test('repeated Cloud continuation token terminates',async()=>assert.rejects(pullJira(jira,{scope:'mine'},async()=>({issues:[issue('APP-1')],nextPageToken:'same',isLast:false})),/stalled/))
test('Agility team queries include self and each report; linked ignores configured project scope',()=>{
 const q=agilityQueries(agility,{scope:'team',members:['Member:2','Member:1']});assert.equal(q.length,2);assert.deepEqual(q.map(x=>x.where.Owners),['Member:1','Member:2'])
 assert.deepEqual(agilityQueries(agility,{scope:'linked',ids:['S-1']})[0].where,{Number:'S-1'})
})
test('Agility deduplicates multi-owner work across team queries, and unknown dates stay unavailable',async()=>{
 const r=await pullAgility(agility,{scope:'team',members:['Member:2']},async()=>[[{_oid:'Story:1',Number:'S-1',Name:'Shared', 'Owners.ID':[1,2],'Owners.Name':['Me','Alex']}]])
 assert.equal(r.items.length,1);assert.equal(r.items[0].due,null);assert.equal(r.items[0].assignees[1].id,'Member:2');assert.equal(r.truncated,false)
})
test('Agility pagination progresses and caps results',async()=>{
 const starts=[];const r=await pullAgility(agility,{scope:'mine',limit:101},async(p,q,b)=>{starts.push(b.page.start);return [Array.from({length:100},(_,i)=>({Number:`S-${b.page.start+i}`,Name:'Task'}))]})
 assert.deepEqual(starts,[0,100]);assert.equal(r.items.length,101);assert.equal(r.truncated,true)
})
test('provider and instance are part of identity',()=>assert.notEqual(identity({provider:'jira',instance:'a',id:'APP-1'}),identity({provider:'jira',instance:'b',id:'APP-1'})))
test('HTTP adapter only permits reads, keeps credentials out of errors, and rejects redirects',async()=>{
 const calls=[];const req=connection('jira',jira,{JIRA_TOKEN:'secret'},async(u,o)=>{calls.push(o);return Response.json({})})
 await req('/rest/api/3/search/jql',{jql:'project = APP'});assert.equal(calls[0].method,'GET');assert.equal(calls[0].redirect,'error')
 await assert.rejects(req('/rest/api/3/issue',{},{}),/read-only/)
 const areq=connection('agility',agility,{AGILITY_TOKEN:'secret'},async(u,o)=>{calls.push(o);return Response.json([[]])})
 await areq('/query.v1',{},{});assert.equal(calls.at(-1).method,'POST')
 await assert.rejects(areq('/rest-1.v1/Data/Story',{},{}),/read-only/)
 assert.throws(()=>connection('jira',{...jira,baseUrl:'http://example.test'},{JIRA_TOKEN:'secret'}),/HTTPS/)
})

test('tracker response and total-byte budgets cancel streams without exposing body text',async()=>{
 let cancelled=0
 const response=()=>new Response(new ReadableStream({pull(c){c.enqueue(new TextEncoder().encode('SECRET_TOO_LARGE'));},cancel(){cancelled++}}),{headers:{'content-type':'application/json'}})
 const req=connection('jira',jira,{JIRA_TOKEN:'secret'},async()=>response(),undefined,{responseBytes:8,totalBytes:16,requests:2})
 await assert.rejects(req('/rest/api/3/search/jql'),e=>/oversized/.test(e.message)&&!e.message.includes('SECRET'))
 assert.equal(cancelled,1)
 const total=connection('jira',jira,{JIRA_TOKEN:'secret'},async()=>Response.json({}),undefined,{responseBytes:8,totalBytes:3,requests:3})
 await total('/rest/api/3/search/jql');await assert.rejects(total('/rest/api/3/search/jql'),/oversized/)
})
test('tracker request budget counts all calls, including pages with duplicate identities',async()=>{
 let calls=0;const req=connection('jira',jira,{JIRA_TOKEN:'secret'},async()=>{calls++;return Response.json({})},undefined,{responseBytes:100,totalBytes:100,requests:2})
 await req('/rest/api/3/search/jql');await req('/rest/api/3/search/jql');await assert.rejects(req('/rest/api/3/search/jql'),/request budget/);assert.equal(calls,2)
})
test('HTML, malformed JSON, nesting, content length and broken streams fail cleanly',async()=>{
 const fixtures=[new Response('<html>SECRET</html>',{headers:{'content-type':'text/html'}}),new Response('SECRET',{headers:{'content-type':'application/json'}}),Response.json({x:'a'},{headers:{'content-length':'99999999'}}),Response.json(Array.from({length:45}).reduce(x=>[x],0)),new Response(new ReadableStream({start(c){c.error(Error('SECRET'))}}))]
 for(const fixture of fixtures){const req=connection('jira',jira,{JIRA_TOKEN:'secret'},async()=>fixture);await assert.rejects(req('/rest/api/3/search/jql'),e=>/JSON response/.test(e.message)&&!e.message.includes('SECRET'))}
})
test('Jira rejects missing identity and malformed fields before producing usable results',async()=>{
 for(const issue of [null,{}, {key:'APP-1',fields:[]},{key:'invalid',fields:{}}]) await assert.rejects(pullJira(jira,{scope:'mine'},async()=>({issues:[issue],isLast:true})),/shape/)
})
