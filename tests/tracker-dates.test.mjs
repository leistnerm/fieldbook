import test from 'node:test'
import assert from 'node:assert/strict'
import { dateFields, mappedDates, validDate } from '../fieldbook_core/lib/tracker-dates.js'
import { pullJira, pullAgility } from '../fieldbook_core/lib/trackers.js'
import { pullAzure } from '../fieldbook_core/lib/azure.js'
import { coverage } from '../fieldbook_core/lib/integration-coverage.js'

test('date mappings reject expressions, unknown meanings, duplicates and malformed references before reading', () => {
  for (const dateFields of [[], {deadline:'due'}, {due:'Scope[EndDate]'}, {due:'X',target:'X'}, {due:null}, {due:'x..y'}])
    assert.throws(() => mappedDates('agility',{dateFields},{}))
  assert.deepEqual(dateFields('azure',{dueField:'Custom.Due',completionField:'Custom.Closed'}),{due:'Custom.Due',completed:'Custom.Closed'})
  assert.deepEqual(dateFields('jira',{dateFields:{due:''}}),{completed:'resolutiondate'})
})
test('date facts preserve exact time and distinguish null, omitted, invalid, target and timezone uncertainty', () => {
  const result=mappedDates('agility',{dateFields:{due:'Due',completed:'Closed',start:'Start',target:'Scope.EndDate',review:'Review',closes_at:'Closes'}},
    {Due:null,Start:'2026-02-30', 'Scope.EndDate':'2026-10-12T14:00:00-04:00',Review:'2026-10-14T14:00:00',Closes:{date:'2026-10-15'}})
  assert.equal(result.due,null);assert.equal(result.completed,null)
  assert.deepEqual(result.dates.map(d=>[d.type,d.at]),[['due',null],['target','2026-10-12T14:00:00-04:00'],['review','2026-10-14T14:00:00']])
  assert.deepEqual(result.date_warnings.map(w=>w.reason),['not_returned','invalid_date','timezone_unspecified','invalid_date'])
  for (const value of ['tomorrow','2026-01-01T25:00:00Z','2026-02-29','2026-01-01T12:00:00+24:00']) assert.equal(validDate(value),false)
  assert.equal(validDate('2024-02-29'),true)
})
test('Jira custom due overrides its default; target never replaces due and requested fields match mappings', async () => {
  let fields
  const result=await pullJira({id:'j',flavor:'cloud',baseUrl:'https://jira.test',dateFields:{due:'customfield_123',target:'customfield_456'}},{scope:'mine'},async (p,q)=>{
    fields=q.fields.split(',');return {issues:[{key:'APP-1',fields:{duedate:'2026-01-01',customfield_123:'2026-10-12',customfield_456:'2026-12-31'}}],isLast:true}
  })
  assert.ok(fields.includes('customfield_123'));assert.ok(!fields.includes('duedate'))
  assert.equal(result.items[0].due,'2026-10-12');assert.equal(result.items[0].dates[1].type,'target')
})
test('Agility and Azure request mapped fields and keep timebox/iteration target distinct', async () => {
  const a={id:'a',where:{Scope:'Scope:1'},dateFields:{target:'Timebox.EndDate'}}
  const agility=await pullAgility(a,{scope:'all'},async(p,q,b)=>{
    assert.equal(p,'/query.v1');assert.ok(b.select.includes('Timebox.EndDate'))
    return [[{Number:'S-1','Timebox.EndDate':'2026-10-12'}]]
  })
  assert.equal(agility.items[0].due,null);assert.equal(agility.items[0].dates[0].type,'target')
  const azure=await pullAzure({id:'a',baseUrl:'https://dev.azure.com/acme',dateFields:{due:'Custom.Due',target:'Custom.Target'}},{scope:'linked',ids:['1']},async(p,q,b)=>{
    assert.equal(p,'/_apis/wit/workitemsbatch');assert.ok(b.fields.includes('Custom.Due'))
    return {value:[{id:1,fields:{'System.Title':'Task','System.State':'New','Custom.Target':'2026-10-20'}}]}
  })
  assert.equal(azure.items[0].due,null);assert.equal(azure.items[0].date_warnings[0].reason,'not_returned')
})
test('coverage distinguishes selected scope, warnings, limits, exclusions and snapshot freshness', () => {
  const result={items:[{date_warnings:[{reason:'not_returned'}]}],truncated:true}
  const report=coverage('jira',{dateFields:{target:'customfield_1'}},{mode:'linked',ids:['ABC-1']},result,{items:1})
  assert.equal(report.read_only,true);assert.equal(report.date_warning_items,1);assert.equal(report.truncated,true)
  assert.deepEqual(report.scope.ids,['ABC-1']);assert.match(report.completeness,/Partial/)
  assert.ok(report.excluded.length);assert.ok(Date.parse(report.read_at));assert.equal(report.limits.items,1)
})
