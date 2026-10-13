"""Read-only, bounded three-way sync comparison. Never fetches or writes anything."""
import hashlib
import json
from datetime import date

PROVIDERS={'jira','agility','github','azure','canvas','google','microsoft','ics'}
FIELDS={'status','due','assignee','completedDate','title','priority','scheduled','start','target','revisit',
        'calendar_start','calendar_end','calendar_timezone','calendar_status','location'}
PROTECTED={'title','priority','scheduled'}

def source_key(provider,instance,identity):
    return hashlib.sha256(json.dumps([provider,instance,identity],ensure_ascii=True,separators=(',',':')).encode()).hexdigest()

def scalar(value):
    if value is None:return None
    if isinstance(value,str) and len(value)<=4096:return value
    if isinstance(value,list) and len(value)<=50 and all(isinstance(v,str) and len(v)<=500 for v in value):return value
    if isinstance(value,dict) and len(value)<=5 and all(isinstance(k,str) and isinstance(v,str) and len(v)<=200 for k,v in value.items()):return value
    raise ValueError('Sync values must be bounded text, string lists or timestamp objects')

def identity_matches(fm,source):
    p,i,key=source['provider'],source['instance'],source['id']
    if p in {'jira','agility','github','azure'}:return str(fm.get(p,''))==key and str(fm.get(p+'_instance',''))==i
    if p=='canvas':return str(fm.get('canvas_instance',''))==i and key==str(fm.get('canvas_course_id',''))+'/'+str(fm.get('canvas_assignment_id',''))
    try:parts=json.loads(key)
    except (ValueError,TypeError):return False
    if not isinstance(parts,list) or any(not isinstance(v,str) for v in parts):return False
    if p=='ics':return parts==[str(fm.get('calendar_uid','')),str(fm.get('calendar_recurrence_id','') or '')] and str(fm.get('calendar_source','local export'))==i
    return (fm.get('calendar_provider')==p and fm.get('calendar_instance')==i and
            parts==[str(fm.get('calendar_id','')),str(fm.get('calendar_series_id','') or fm.get('calendar_event_id','')),str(fm.get('calendar_occurrence_id',''))])


def compare(fm,request):
    if len(json.dumps(request,ensure_ascii=True).encode())>65536:raise ValueError('Sync preview exceeds 64 KiB; split the proposal')
    if not isinstance(request,dict) or set(request)-{'source','proposed','explicit_fields','coverage'}:raise ValueError('Invalid sync preview fields')
    source=request.get('source',{})
    if not isinstance(source,dict) or set(source)!={'provider','instance','id'} or not isinstance(source.get('provider'),str) or source.get('provider') not in PROVIDERS:raise ValueError('Supply source provider, instance and id')
    if any(not isinstance(v,str) or not v or len(v)>2048 or any(ord(c)<32 for c in v) for v in source.values()):raise ValueError('Supply bounded exact source identities')
    if source['provider'] in {'google','microsoft','ics'}:
        try:source={**source,'id':json.dumps(json.loads(source['id']),ensure_ascii=True,separators=(',',':'))}
        except ValueError:raise ValueError('Calendar source id must be a JSON-encoded identity tuple') from None
    if not identity_matches(fm,source):raise ValueError('Source identity does not match this note; resolve identity before comparing fields')
    proposed=request.get('proposed')
    if not isinstance(proposed,dict) or not 1<=len(proposed)<=20 or set(proposed)-FIELDS:raise ValueError('Select 1..20 supported fields; logs, body, identity and recurrence state are protected')
    explicit=request.get('explicit_fields',[])
    if not isinstance(explicit,list) or any(not isinstance(v,str) or v not in FIELDS for v in explicit):raise ValueError('Invalid explicitly requested fields')
    coverage=request.get('coverage',{})
    if not isinstance(coverage,dict) or set(coverage)-{'read_at','truncated','warning'}:raise ValueError('Coverage accepts read_at, truncated and warning')
    if 'truncated' in coverage and type(coverage['truncated']) is not bool:raise ValueError('truncated must be a boolean')
    if any(not isinstance(coverage[k],str) or len(coverage[k])>2000 for k in ('read_at','warning') if k in coverage):raise ValueError('Invalid coverage text')
    key=source_key(source['provider'],source['instance'],source['id'])
    baselines=fm.get('sync_baselines') or {}
    if not isinstance(baselines,dict) or len(baselines)>16:raise ValueError('Invalid or oversized sync_baselines; review metadata')
    baseline=baselines.get(key,{})
    if not isinstance(baseline,dict) or (baseline and baseline.get('source')!=source):raise ValueError('Stored baseline identity is invalid')
    prior=baseline.get('fields',{})
    if not isinstance(prior,dict) or set(prior)-FIELDS:raise ValueError('Invalid stored field baseline')
    rows=[]
    tags=fm.get('tags',[]);tags=tags if isinstance(tags,list) else [tags]
    final='review' in tags and str(fm.get('status','')).lower()=='final'
    recurring=bool(fm.get('recurrence'))
    other_sources=len(baselines)>int(bool(baseline)) or sum(bool(fm.get(p)) for p in ('jira','agility','github','azure'))>1
    for field,value in proposed.items():
        incoming=scalar(value);current=scalar(fm.get(field));previous=scalar(prior[field]) if field in prior else None
        for v in (incoming,current,previous):
            if v is not None and not isinstance(v,str) and not (field=='assignee' and isinstance(v,list)) and not (field in ('calendar_start','calendar_end') and isinstance(v,dict)):
                raise ValueError('Invalid value type for '+field)
        has_baseline=field in prior and previous is not None and previous!=''
        if final:state='protected';reason='Final reviews are immutable'
        elif recurring and field in {'status','due','scheduled','completedDate'}:state='protected';reason='Recurring task state belongs to TaskNotes'
        elif field in {'status','due','assignee','completedDate'} and 'task' not in tags:state='protected';reason='Task fields do not apply to this note type'
        elif (field.startswith('calendar_') or field=='location') and 'meeting' not in tags:state='protected';reason='Calendar fields require a meeting record'
        elif incoming is None or incoming=='':state='unavailable';reason='Missing remote value does not authorize clearing a local value'
        elif field in PROTECTED and field not in explicit:state='protected';reason='Local planning/title/priority requires explicit inclusion'
        elif current==incoming:state='unchanged';reason='Local and proposed values agree'
        elif other_sources:state='source_conflict';reason='Multiple source bindings/baselines; choose which source governs this field'
        elif not has_baseline:state='first_sync';reason='No reviewed baseline; choose the intended value explicitly'
        elif current==previous:state='remote_change';reason='Only the source proposal changed from the reviewed baseline'
        elif incoming==previous:state='local_override';reason='Only the local value changed; preserve it'
        else:state='conflict';reason='Both local and source values changed differently'
        if field in {'due','scheduled','completedDate','start','target','revisit'} and incoming and state!='protected':
            try:date.fromisoformat(incoming)
            except (ValueError,TypeError):state='invalid';reason='Use an explicitly mapped YYYY-MM-DD value; keep exact source times separately'
        if field=='status' and incoming and 'task' in tags and incoming not in {'backlog','active','blocked','done','dropped'}:state='invalid';reason='Map the source state to a supported local status before previewing'
        if field=='completedDate' and incoming and proposed.get('status',fm.get('status')) not in ('done','dropped') and state not in ('protected','invalid'):
            state='needs_review';reason='A completion date requires a reviewed closed status; a date alone does not prove completion'
        if field=='status' and incoming in ('done','dropped') and state not in ('protected','invalid'):
            try:date.fromisoformat(proposed.get('completedDate') or fm.get('completedDate') or '')
            except (ValueError,TypeError):state='needs_review';reason='Closing requires a valid verified completion date in the same edit; do not stamp an old import today'
        rows.append({'field':field,'baseline_present':has_baseline,'last_reviewed_source':previous,'local':current,'proposed':incoming,'classification':state,'reason':reason})
    counts={name:sum(r['classification']==name for r in rows) for name in sorted({r['classification'] for r in rows})}
    return {'source':source,'baseline_key':key,'fields':rows,'counts':counts,'coverage':coverage,
            'changed':False,'remote_read_only':True,'notice':'Preview only. No field or baseline was saved. Review each choice; preserve local overrides. Missing results never mean deletion/completion. Save approved baseline values only with the approved note edit and fresh SHA.'}
