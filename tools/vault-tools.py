#!/usr/bin/env python3
"""Human-operated local vault tools. Preview before writes; no remote or model calls."""
from datetime import date, datetime, timedelta, timezone
import difflib
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import tempfile
import uuid

HERE=Path(__file__).resolve().parent

def load(name,path):
    spec=importlib.util.spec_from_file_location(name,path)
    m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m

admin=load('vault_tools_admin',HERE/'manage-vault.py')
nb=load('vault_tools_notebook',HERE.parent/'fieldbook_core/scripts/notebook.py')
backup=load('vault_tools_backup',HERE/'backup-vault.py')
CONTENT=nb.CONTENT
MAX_FILE=1024*1024
MAX_FILES=10000
MAX_SCAN=64*MAX_FILE
FOLDERS={'Task':'Tasks','Project':'Projects','Person':'People','Item':'Items','List':'Lists','Note':'Notes',
         'Meeting':'Meetings','Series':'Meetings/Series','Decision':'Decisions','Reference':'Reference',
         'Research':'Research','Accomplishment':'Accomplishments','Opportunity':'Opportunities','Review-format':'Reports/Reviews'}

def journeys():return load('fieldbook_review_workflows',HERE/'review-workflows.py')
def workflows():return load('fieldbook_local_workflows',HERE/'local-workflows.py')
def api():
    from types import SimpleNamespace
    return SimpleNamespace(**globals())

def now():return datetime.now(timezone.utc).isoformat()
def sha(data):return hashlib.sha256(data).hexdigest()
def text(root,name):
    p=admin.safe(root,name)
    if p.stat().st_size>MAX_FILE:raise ValueError('File exceeds 1 MiB: '+name)
    return p.read_bytes().decode('utf-8-sig')
def settings(root):return json.loads(text(root,'fieldbook.json'))
def label(value):
    if not isinstance(value,str) or not value.strip() or len(value)>150:raise ValueError('Use a name of 1..150 characters')
    value=re.sub(r'[\\/:*?"<>|\[\]#^\x00-\x1f\x7f]','-',value).strip().rstrip('. ')
    if not value or re.match(r'^(con|prn|aux|nul|com[1-9]|lpt[1-9])(?:\.|$)',value,re.I):raise ValueError('Choose a valid file name')
    return value

def unique(root,folder,title):
    title=label(title);name=f'{folder}/{title}.md';n=2
    while admin.safe(root,name).exists():
        name=f'{folder}/{title} ({n}).md';n+=1
        if n>1000:raise ValueError('Choose a more distinctive title')
    return name

def commit_new(root,plan):
    value=plan.get('text')
    if not isinstance(value,str) or '\x00' in value or len(value.encode('utf-8'))>MAX_FILE:raise ValueError('New note exceeds 1 MiB or is not valid text; narrow the selection')
    nb.frontmatter(value)
    for rel,expected in plan.get('inputs',{}).items():
        if sha(admin.safe(root,rel).read_bytes())!=expected:raise ValueError('Source changed after preview; start again')
    if plan.get('self_record'):
        rows,warnings=records(root)
        if warnings or any(tagged(r,'person') and r['fm'].get('relationship')=='self' for r in rows):raise ValueError('Self-record state changed or scan incomplete; preview again')
    if plan.get('calendar_event'):
        found=workflows().existing_meetings(api(),root,plan['calendar_event'])
        if found:raise ValueError('Existing meeting; preview again: '+', '.join(found))
    if plan.get('intake_identity'):
        intake_duplicates(root,plan['intake_identity'])
    name=plan['path']
    if name.split('/')[0] not in CONTENT or not name.endswith('.md'):raise ValueError('Output must be a record Markdown path')
    p=admin.safe(root,name);p.parent.mkdir(parents=True,exist_ok=True);admin.safe(root,name)
    fd,tmp=tempfile.mkstemp(prefix='.fieldbook-create-',dir=p.parent)
    try:
        with os.fdopen(fd,'w',encoding='utf-8',newline='') as f:f.write(plan['text']);f.flush();os.fsync(f.fileno())
        admin.safe(root,name)
        os.link(tmp,p)  # Fails if a note appeared after preview; never overwrite.
    finally:
        if os.path.exists(tmp):os.unlink(tmp)
    return {'created':name}

def templates(root):
    config=settings(root);catalog={e['path']:e for e in admin.setup_module().catalog(root,admin.safe,admin.read)}
    result=[]
    for p in sorted((root/'Templates').glob('*.md')):
        rel=p.relative_to(root).as_posix();admin.safe(root,rel)
        base=p.stem.split(' - ')[0]
        if base not in FOLDERS or p.stem=='Task body':continue
        if rel in catalog and not admin.setup_module().enabled(catalog[rel],config):continue
        result.append(p.stem)
    return result

def record_plan(root,template,title,area='',today=None):
    today=today or date.today()
    if template not in templates(root):raise ValueError('Choose an active record template')
    if area not in ('','personal','work','school'):raise ValueError('Choose personal, work, school or blank area')
    name=label(title);base=template.split(' - ')[0];folder=FOLDERS[base]
    if base=='Meeting':folder+=today.strftime('/%Y/%Y-%m');name=today.isoformat()+' '+name
    path=unique(root,folder,name);name=Path(path).stem
    rel='Templates/'+template+'.md';source=text(root,rel).replace('\r\n','\n');config=settings(root)
    blocks=json.loads(text(root,'tools/record-templates.json'))
    def block(match):
        if sha(match[0].encode())!=blocks.get(template):raise ValueError('Custom template script is unsupported by the CLI; use Templater in Editing view')
        return ''
    body=re.sub(r'<%\*[\s\S]*?-?%>\n?',block,source)
    expressions={'JSON.stringify(tp.file.title)':json.dumps(name,ensure_ascii=False),
                 'tp.date.now("YYYY-MM-DD")':today.isoformat()}
    def expression(match):
        value=match[1].strip()
        if value not in expressions:raise ValueError('Custom template expression is unsupported; use Templater in Editing view')
        return expressions[value]
    body=re.sub(r'<%([\s\S]*?)%>',expression,body)
    fm=nb.frontmatter(body)
    if not fm.get('tags'):raise ValueError('Template must contain record tags')
    defaults=config.get('defaults',{})
    selected=area or fm.get('area') or defaults.get('area','')
    if fm.get('area')=='school' and selected and selected!='school':raise ValueError('Course/Assignment requires school area; choose a shared template for another area')
    if 'area' in fm and not fm['area'] and selected:
        body=re.sub(r'^area:[ \t]*$', 'area: '+selected,body,count=1,flags=re.M)
    if base=='Task':
        canonical={'status':'backlog','priority':'2-normal','type':'task'}
        for key,initial in canonical.items():
            if fm.get(key)==initial and (key!='type' or template=='Task') and defaults.get(key):
                body=re.sub(r'^'+key+r':[^\n]*$',key+': '+json.dumps(defaults[key]),body,count=1,flags=re.M)
    nb.frontmatter(body)
    return {'path':path,'text':body,'inputs':{rel:sha(admin.safe(root,rel).read_bytes()),'fieldbook.json':sha(admin.safe(root,'fieldbook.json').read_bytes()),'tools/record-templates.json':sha(admin.safe(root,'tools/record-templates.json').read_bytes())}}

def records(root):
    rows=[];warnings=[];total=0
    try:paths=nb.Vault(root).files('notes')
    except (ValueError,OSError) as error:return [],['Incomplete note scan: '+str(error)]
    for rel in paths:
        try:
            p=admin.safe(root,rel);size=p.stat().st_size;total+=size
            if total>MAX_SCAN:return rows,warnings+['Scan stopped at 64 MiB; results are incomplete']
            if size>MAX_FILE:raise ValueError('Note exceeds 1 MiB: '+rel)
            data=p.read_bytes();s=data.decode('utf-8-sig');fm=nb.frontmatter(s)
            body=re.sub(r'^---\r?\n.*?\r?\n---(?:\r?\n|$)','',s,count=1,flags=re.S)
            rows.append({'path':rel,'fm':fm,'body':body,'text':s,'sha256':sha(data)})
        except (ValueError,UnicodeError,OSError) as e:warnings.append(rel+': '+str(e)[:200])
    return rows,warnings

def index(rows):
    out={}
    for r in rows:
        names=[r['path'][:-3],Path(r['path']).stem,*nb.values(r['fm'].get('aliases'))]
        for name in names:out.setdefault(str(name).casefold(),set()).add(r['path'])
    return out

def resolve(value,idx):return idx.get(nb.link_name(value),set())
def linked(value,idx):
    matches=resolve(value,idx)
    return matches if len(matches)==1 else set()
def tagged(row,tag):return tag in nb.values(row['fm'].get('tags'))
def opened(row):return row['fm'].get('status') not in ('done','dropped')

def doctor(root):
    rows,warnings=records(root);idx=index(rows);findings=[];identities={}
    for row in rows:
        rel,fm=row['path'],row['fm']
        if fm.get('tags') and not row['body'].strip():findings.append({'kind':'possible_incomplete_template','path':rel,'detail':'Properties only; this may be intentional. Add missing sections manually.'})
        if '<%' in row['text']:findings.append({'kind':'unexpanded_template','path':rel})
        for provider in ('jira','agility','github','azure'):
            value=fm.get(provider)
            if value and value!='none':
                instance=fm.get(provider+'_instance')
                if not instance:findings.append({'kind':'missing_tracker_instance','path':rel,'provider':provider});continue
                key=(provider,str(instance),str(value).casefold());identities.setdefault(key,[]).append(rel)
        if fm.get('canvas_assignment_id'):
            key=('canvas',str(fm.get('canvas_instance','')),str(fm.get('canvas_course_id','')),str(fm['canvas_assignment_id']))
            if not key[1] or not key[2]:findings.append({'kind':'missing_canvas_identity','path':rel})
            else:identities.setdefault(key,[]).append(rel)
        links=re.findall(r'\[\[([^\]\n]+)\]\]',row['text'])
        for value in sorted(set(links)):
            target=value.split('|')[0].split('#')[0]
            if not target:continue  # Same-note headings are not checked.
            matches=resolve(value,idx)
            if len(matches)>1:findings.append({'kind':'ambiguous_link','path':rel,'target':target})
            elif not matches:
                try:
                    candidates=[target,target+'.md',str(Path(rel).parent/target),str(Path(rel).parent/(target+'.md'))]
                    found=any(admin.safe(root,c).is_file() for c in candidates)
                except ValueError:found=False
                if not found:findings.append({'kind':'unresolved_link','path':rel,'target':target})
    for key,paths in identities.items():
        if len(paths)>1:findings.append({'kind':'shared_remote_identity','identity':list(key),'paths':paths,'detail':'May be intentional links from different note types; review before merging.'})
    health=admin.health(root)
    import shutil
    optional={'pdf_text':importlib.util.find_spec('pypdf') is not None,'image_ocr':shutil.which('tesseract') is not None}
    for plugin in ('tasknotes','templater-obsidian'):
        if not admin.safe(root,'.obsidian/plugins/'+plugin+'/main.js').is_file():warnings.append('Plugin not installed locally: '+plugin)
    return {'checked_at':now(),'notes_scanned':len(rows),'errors':health['errors'],'warnings':health['warnings']+warnings,
            'optional_intake_dependencies':optional,'findings':findings[:2000],'findings_truncated':len(findings)>2000,'changed':False,
            'notice':'Review findings; no automatic repairs. Link checks do not validate heading/block anchors or external URLs.'}

def followups(root,area='',days=30,today=None):
    if area not in ('','personal','work','school') or type(days) is not int or not 1<=days<=366:raise ValueError('Choose a valid area and 1..366-day window')
    today=today or date.today();all_rows,warnings=records(root);idx=index(all_rows)
    rows=[r for r in all_rows if not area or r['fm'].get('area')==area]
    tasks=[r for r in rows if tagged(r,'task') and opened(r)]
    waiting=[r['path'] for r in tasks if r['fm'].get('status')=='blocked' or r['fm'].get('assignee')]
    projects=[]
    for p in rows:
        if tagged(p,'project') and p['fm'].get('status')=='active' and not any(p['path'] in linked(link,idx) for t in tasks for link in nb.values(t['fm'].get('projects'))):projects.append(p['path'])
    promises=[]
    for r in rows:
        if not (tagged(r,'meeting') or tagged(r,'series')):continue
        section=re.search(r'^## Commitments\s*\n(.*?)(?=^## |\Z)',r['body'],re.M|re.S)
        if section:
            for line in section[1].splitlines():
                if re.match(r'^\s*-\s+',line) and not re.match(r'^\s*-\s+\[[xX]\]',line):promises.append({'source':r['path'],'recorded':line.strip()[:1000]})
    config=settings(root);manager=None
    if 'work' in config.get('setups',[]) and config.get('workRole')=='people-manager' and area in ('','work'):
        reports=[r for r in all_rows if tagged(r,'person') and r['fm'].get('relationship')=='report' and r['fm'].get('status','') in ('','current')]
        manager=[]
        start=today-timedelta(days=days)
        for person in reports:
            dates=[];evidence=[];undated=[]
            for r in all_rows:
                fm=r['fm']
                if fm.get('area')!='work':continue
                if tagged(r,'meeting') and person['path'] in set().union(*(linked(v,idx) for v in nb.values(fm.get('attendees')))):
                    try:d=date.fromisoformat(str(fm.get('date',''))[:10])
                    except ValueError:continue
                    if d<=today:dates.append(d)
                if tagged(r,'accomplishment') and person['path'] in linked(fm.get('person',''),idx):
                    try:
                        first=date.fromisoformat(str(fm.get('period_start') or fm.get('date') or ''))
                        last=date.fromisoformat(str(fm.get('period_end') or fm.get('date') or fm.get('period_start') or ''))
                        if last<first:raise ValueError('Reversed period')
                    except ValueError:undated.append(r['path']);continue
                    if first<=today and last>=start:evidence.append(r['path'])
            latest=max(dates) if dates else None
            manager.append({'person':person['path'],'last_recorded_work_meeting':latest.isoformat() if latest else None,
                            'undated_or_invalid_evidence':undated if config.get('features',{}).get('reviews') else None,
                            'check_in_review':latest is None or latest<start,'evidence_in_window':evidence if config.get('features',{}).get('reviews') else None,
                            'notice':'Recorded group meetings also count. Missing records are not evidence of missed meetings or poor performance.'})
    checkins=[];overdue=[]
    for r in rows:
        if r['fm'].get('status') in ('done','dropped','superseded'):continue
        try:check=date.fromisoformat(str(r['fm'].get('check_in',''))[:10])
        except ValueError:continue
        if check<today:overdue.append({'path':r['path'],'check_in':r['fm']['check_in']})
        if today<=check<=today+timedelta(days=14):checkins.append({'path':r['path'],'check_in':r['fm']['check_in']})
    return {'one_on_one_cadence':workflows().cadence(api(),root,today) if not warnings and area in ('','work') else [],'overdue_check_ins':overdue,'upcoming_check_ins':checkins,'generated_at':now(),'area':area or 'all including blank','lookback_days':days,'warnings':warnings,
            'waiting_or_assigned_tasks':waiting,'active_projects_without_open_linked_task':projects,
            'recorded_commitments_to_review':promises,'manager':manager,'changed':False}

def report_plan(root,title,data):
    body='# '+title+'\n\nGenerated '+now()+'. Snapshot only; refresh from Vault tools.\n\n'
    for key,value in data.items():
        if key in ('changed','generated_at'):continue
        body+='## '+key.replace('_',' ').capitalize()+'\n\n'
        if isinstance(value,list):
            body+='\n'.join('- [['+v+']]' if isinstance(v,str) and v.endswith('.md') else '- '+json.dumps(v,ensure_ascii=False,default=str) for v in value) if value else 'None recorded.'
        else:body+=json.dumps(value,ensure_ascii=False,default=str)
        body+='\n\n'
    return {'path':unique(root,'Reports',title+' '+datetime.now().strftime('%Y-%m-%d %H%M%S')),'text':body,'inputs':{}}

def comparison(root):
    manifest=json.loads(text(root,'fieldbook-manifest.json'));names=set(manifest['files'])
    names.update(('opencode.json','fieldbook.json'))
    result=[]
    for name in sorted(names):
        if name.endswith('.json'):continue
        candidate=admin.safe(root,name+'.fieldbook-new')
        if not candidate.is_file():continue
        current=admin.safe(root,name);a=text(root,name) if current.exists() else '';b=text(root,name+'.fieldbook-new')
        # Comparison only: no automatic replacement or deletion of either copy.
        diff=''.join(difflib.unified_diff(a.splitlines(True),b.splitlines(True),fromfile=name,tofile=name+'.fieldbook-new'))
        result.append({'path':name,'current_sha256':sha(a.encode()),'candidate_sha256':sha(b.encode()),'same':a==b,'diff':diff[:100000],'diff_truncated':len(diff)>100000})
    return {'candidates':result,'changed':False,'notice':'Compare and merge deliberately in your editor. No candidate is accepted or removed automatically. All JSON settings are excluded; compare those locally in your editor.'}

PROVIDERS=('jira','agility','github','azure','canvas','google','microsoft')

def activity_plan(root,result,origin='imported',checked_at=None):
    if origin not in ('imported','cli-test'):raise ValueError('Invalid activity origin')
    captured=checked_at or now();rows=[]
    def identity(provider,instance):
        if provider not in PROVIDERS or not isinstance(instance,str) or not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_-]{0,63}',instance):
            raise ValueError('A known provider and exact instance are required')
    if isinstance(result,dict) and isinstance(result.get('results'),list):
        if len(result['results'])>200:raise ValueError('Too many diagnostic results')
        for item in result['results']:
            if not isinstance(item,dict):raise ValueError('Invalid diagnostic row')
            if item.get('instance') is None:continue
            identity(item.get('provider'),item.get('instance'))
            stages=[]
            for c in item.get('checks',[]):
                if isinstance(c,dict) and re.fullmatch('[a-zA-Z_ -]{1,50}',str(c.get('stage',''))) and c.get('status') in ('pass','fail','skip','unknown','not_verified'):
                    stages.append({'stage':c['stage'],'status':c['status']})
            status='skipped' if item.get('skipped') is True else 'passed' if item.get('ok') is True else 'failed_or_incomplete'
            rows.append({'provider':item['provider'],'instance':item['instance'],'kind':'connection_test','status':status,'stages':stages})
    else:
        if not isinstance(result,dict):raise ValueError('Choose a diagnostic or pull JSON result')
        cov=result.get('coverage')
        if not isinstance(cov,dict) or cov.get('read_only') is not True:raise ValueError('Expected read-only coverage metadata')
        provider=result.get('provider',cov.get('provider'));instance=result.get('instance')
        identity(provider,instance)
        read_at=cov.get('read_at')
        if read_at is not None:
            try:
                if not isinstance(read_at,str) or len(read_at)>50 or datetime.fromisoformat(read_at.replace('Z','+00:00')).tzinfo is None:raise ValueError()
            except (ValueError,TypeError):raise ValueError('Invalid source read timestamp') from None
        row={'provider':provider,'instance':instance,'kind':'pull','read_at':read_at,'status':'reported_partial' if cov.get('truncated') else 'reported_read' if read_at else 'no_remote_read','truncated':cov.get('truncated') is True}
        for k in ('returned','date_warning_items','identity_review_items'):
            value=cov.get(k)
            if type(value) is int and 0<=value<=1000000:row[k]=value
        scope=cov.get('scope',{})
        if isinstance(scope,dict):
            mode=scope.get('mode')
            if mode in ('linked','mine','team','all','events','series','coursework','assignments','quizzes','discussions','planner'):row['scope_mode']=mode
            row['scope_fingerprint']=sha(json.dumps(scope,sort_keys=True,default=str).encode())[:16]
        rows.append(row)
    if not rows:raise ValueError('No instance-specific activity to save')
    # Pin to a configuration fingerprint; reports warn when current settings differ.
    for row in rows:
        name='fieldbook_core/'+row['provider']+'.json'
        row['configuration_sha256']=sha(admin.safe(root,name).read_bytes())
    return {'schemaVersion':1,'captured_at':captured,'origin':origin,'rows':rows,
            'notice':'Explicitly saved metadata only. Imported results are reported evidence, not independently verified. Connection tests are not notebook syncs.'}

def save_activity(root,receipt):
    # Only plans produced by this process reach here through the human preview flow.
    rel='.fieldbook/activity/'+datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ-')+uuid.uuid4().hex[:8]+'.json'
    p=admin.safe(root,rel);p.parent.mkdir(parents=True,exist_ok=True);admin.safe(root,rel)
    with p.open('x',encoding='utf-8') as f:json.dump(receipt,f,indent=2);f.write('\n')
    return {'saved':rel}

def activities(root):
    directory=admin.safe(root,'.fieldbook/activity');rows=[];warnings=[]
    if not directory.is_dir():return {'receipts':[],'warnings':[],'notice':'No saved activity. Reads do not save receipts automatically.'}
    paths=sorted(directory.glob('*.json'),reverse=True)
    for p in paths[:500]:
        rel=p.relative_to(root).as_posix()
        try:
            data=json.loads(text(root,rel))
            if data.get('schemaVersion')!=1 or not isinstance(data.get('rows'),list):raise ValueError('Invalid receipt')
            # Re-sanitize stored/imported files instead of trusting arbitrary added keys.
            cleaned=[]
            for row in data['rows'][:200]:
                if row.get('provider') not in PROVIDERS or not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_-]{0,63}',str(row.get('instance',''))):continue
                allowed=('provider','instance','kind','status','read_at','truncated','returned','date_warning_items','identity_review_items','scope_mode','scope_fingerprint','configuration_sha256')
                safe_row={k:row[k] for k in allowed if k in row and isinstance(row[k],(str,int,bool,type(None))) and len(str(row[k]))<=100}
                config=admin.safe(root,'fieldbook_core/'+row['provider']+'.json')
                safe_row['configuration_changed']=not config.is_file() or sha(config.read_bytes())!=row.get('configuration_sha256')
                cleaned.append(safe_row)
            rows.append({'file':rel,'captured_at':str(data.get('captured_at',''))[:50],'origin':data.get('origin') if data.get('origin') in ('imported','cli-test') else 'unknown','rows':cleaned})
        except (ValueError,OSError,AttributeError):warnings.append('Unreadable activity receipt: '+rel)
    return {'receipts':rows,'warnings':warnings,'truncated':len(paths)>500,'notice':'Last saved snapshots only; no background polling. Imported results and connection tests do not prove a completed sync.'}

def literal_block(value):
    fence='`'*max(3,1+max((len(x) for x in re.findall(r'`+',value)),default=0))
    return fence+'text\n'+value+'\n'+fence

def intake_duplicates(root,identity):
    rows,warnings=records(root)
    if warnings:raise ValueError('Resolve note scan warnings with Vault check before duplicate-safe intake')
    for row in rows:
        fm=row['fm']
        if fm.get('source_sha256')==identity['sha256']:
            raise ValueError('This content was already imported: '+row['path'])
        if identity.get('message_id') and fm.get('source_message_id')==identity['message_id']:
            kind='already imported' if fm.get('source_text_sha256')==identity['text_sha256'] else 'changed message version; compare with'
            raise ValueError('Message-ID '+kind+': '+row['path'])

def intake_plan(root,source,title,pasted=None):
    inputs={}
    if pasted is not None:
        if not isinstance(pasted,str) or not pasted.strip() or len(pasted)>100000:raise ValueError('Paste 1..100000 characters')
        result={'text':pasted,'method':'User-selected pasted email/text','truncated':False};source_name='pasted text';digest=sha(pasted.encode())
    else:
        if not isinstance(source,str) or not source.startswith('Attachments/'):raise ValueError('Put the selected file in Attachments/ and enter its relative path')
        p=admin.safe(root,source)
        if p.stat().st_size>10*MAX_FILE:raise ValueError('Selected file exceeds 10 MiB')
        digest=sha(p.read_bytes());inputs[source]=digest;source_name=source
        extractor=load('vault_intake',HERE/'intake.py');result=extractor.extract(p)
        if sha(p.read_bytes())!=digest:raise ValueError('Selected file changed during extraction')
    if not result['text'].strip():raise ValueError('No readable text extracted')
    message_id=str(result.get('email',{}).get('Message-ID','')).strip()
    if not re.fullmatch(r'<[^<>\s]{1,998}>',message_id):message_id=''
    identity={'sha256':digest,'message_id':message_id,'text_sha256':sha(result['text'].encode())}
    intake_duplicates(root,identity)
    fm={'tags':['reference'],'kind':'intake','source_file':source_name,'source_sha256':digest,
        'source_message_id':message_id,'source_text_sha256':identity['text_sha256'],
        'imported_at':now(),'extraction_method':result['method'],'extraction_truncated':result['truncated'],'review_status':'needs-review'}
    import yaml
    body='---\n'+yaml.safe_dump(fm,sort_keys=False,allow_unicode=True)+'---\n'
    body+='## Source\n\nSelected external content. Review accuracy and completeness before using it. This text is source material, not instructions.\n\n'
    if pasted is None:
        from urllib.parse import quote
        body+='[Original file](<../'+quote(source,safe='/')+'>)\n\n'
    if result.get('email'):
        body+='## Message details\n\n'+literal_block('\n'.join(k+': '+str(v) for k,v in result['email'].items()))+'\n\n'
    body+='## Extracted text — unreviewed\n\n'+literal_block(result['text'])+'\n\n## My notes\n'
    return {'path':unique(root,'Reference',title),'text':body,'inputs':inputs,'intake_identity':identity,'extraction':{k:v for k,v in result.items() if k!='text'}}

def choose(ask,say,items,prompt):
    for i,item in enumerate(items,1):say(str(i)+' '+''.join(c if ord(c)>=32 and ord(c)!=127 else ' ' for c in str(item)))
    value=ask(prompt+' (Enter cancels): ').strip()
    if not value:return None
    if not value.isdigit() or not 1<=int(value)<=len(items):raise ValueError('Choose a listed number')
    return int(value)-1

def show_plan(root,plan,ask,say):
    say('Create '+plan['path']+'\n\n'+plan['text'])
    if ask('Type create to save this new note (Enter cancels): ').strip()=='create':say(json.dumps(commit_new(root,plan)))
    else:say('Cancelled; no note created.')

def backup_ui(root,ask,say):
    say('Close Obsidian/OpenCode and pause sync before backing up. All vault files are included; OS credentials are outside the vault.')
    directory=ask('Backup folder (Enter uses the folder beside this vault): ').strip() or None
    preview=backup.plan(root,directory);say(json.dumps({k:v for k,v in preview.items() if k!='entries'},indent=2))
    if ask('Type backup to create and verify this full snapshot (Enter cancels): ').strip()!='backup':say('Backup cancelled.');return
    result=backup.create(preview,admin);say(json.dumps(result,indent=2))
    keep=ask('Optional retention: keep how many newest verified backups? (Enter keeps everything): ').strip()
    if not keep:return
    if not keep.isdigit():raise ValueError('Choose a positive number')
    retention=backup.retention(root,preview['directory'],int(keep))
    say(json.dumps({'retain':[x['folder'] for x in retention['keep']],'remove':[x['folder'] for x in retention['remove']],'skipped':retention['skipped']},indent=2))
    if retention['remove'] and ask('Type prune to permanently remove only the listed older backups (Enter keeps all): ').strip()=='prune':
        say(json.dumps(backup.prune(retention),indent=2))

def create_ui(root,ask,say):
    available=templates(root);n=choose(ask,say,available,'Template number')
    if n is None:return
    title=ask('Note name (Enter cancels): ').strip()
    if not title:return
    area=ask('Area: personal/work/school (Enter uses template or configured default): ').strip()
    show_plan(root,record_plan(root,available[n],title,area),ask,say)

def intake_ui(root,ask,say):
    say('Local selected-file intake. Place a file in Attachments/; no mailbox, remote links or cloud OCR are read.')
    source=ask('Relative Attachments/file path, or paste (Enter cancels): ').strip()
    if not source:return
    pasted=None
    if source=='paste':
        say('Paste selected email/text. Finish with a line containing .end');lines=[];size=0
        while True:
            line=ask('')
            if line=='.end':break
            size+=len(line)+1
            if size>100000:raise ValueError('Pasted text exceeds 100000 characters')
            lines.append(line)
        pasted='\n'.join(lines)
    title=ask('New Reference note name (Enter cancels): ').strip()
    if title:show_plan(root,intake_plan(root,source,title,pasted),ask,say)

def comparison_ui(root,ask,say):
    result=comparison(root);say(result['notice'])
    if not result['candidates']:say('No preserved upgrade candidates to compare.');return
    n=choose(ask,say,[x['path'] for x in result['candidates']],'Compare which file')
    if n is None:return
    chosen=result['candidates'][n];say(chosen['diff'] or 'Files are identical.')
    if chosen['diff_truncated']:say('Diff exceeds 100000 characters; open both files for the full comparison.')
    say('Current: '+str(root/chosen['path'])+'\nIncoming: '+str(root/(chosen['path']+'.fieldbook-new')))

def activity_ui(root,ask,say,last_test=None):
    choice=ask('1 Show saved activity\n2 Save last CLI connection-test summary\n3 Import selected pull/diagnostic JSON metadata\n4 Export saved summary to Reports\nEnter cancels\nChoose: ').strip()
    if choice in ('1','4'):
        result=activities(root)
        if choice=='1':say(json.dumps(result,indent=2))
        else:show_plan(root,report_plan(root,'Integration activity',result),ask,say)
    elif choice in ('2','3'):
        if choice=='2':
            if not last_test:raise ValueError('Run a connection test in this CLI session first')
            plan=activity_plan(root,last_test['result'],'cli-test',last_test['checked_at'])
        else:
            rel=ask('Relative Attachments/result.json path (Enter cancels): ').strip()
            if not rel:return
            if not rel.startswith('Attachments/') or not rel.endswith('.json'):raise ValueError('Select an Attachments/*.json file')
            plan=activity_plan(root,json.loads(text(root,rel)))
        say(json.dumps(plan,indent=2))
        if ask('Type save to keep this metadata-only activity receipt (Enter cancels): ').strip()=='save':say(json.dumps(save_activity(root,plan)))
    elif choice:raise ValueError('Choose a listed activity option')

def followups_ui(root,ask,say):
    area=ask('Area: personal/work/school (Enter includes all and blank): ').strip()
    value=ask('Manager meeting/evidence lookback days [30]: ').strip() or '30'
    if not value.isdigit():raise ValueError('Choose a whole number of days')
    result=followups(root,area,int(value));say(json.dumps(result,indent=2))
    if ask('Save a dated snapshot in Reports? [y/N]: ').strip().lower()=='y':show_plan(root,report_plan(root,'Follow-ups',result),ask,say)

def show_summary(result,ask,say):
    def render(value,prefix=''):
        if isinstance(value,dict):
            for key,item in value.items():
                title=key.replace('_',' ').capitalize()
                if isinstance(item,(dict,list)):
                    say(prefix+title+':');render(item,prefix+'  ')
                else:say(prefix+title+': '+str(item))
        elif isinstance(value,list):
            if not value:say(prefix+'None')
            for item in value:
                if isinstance(item,dict):
                    scalar=[str(k).replace('_',' ')+': '+str(v) for k,v in item.items() if not isinstance(v,(dict,list))]
                    say(prefix+' | '.join(scalar))
                    for key,child in item.items():
                        if isinstance(child,(dict,list)):say(prefix+key+':');render(child,prefix+'  ')
                else:say(prefix+str(item))
    render(result)
    if ask('Type details for the full JSON (Enter continues): ').strip()=='details':say(json.dumps(result,indent=2,ensure_ascii=True))

def run(root,action=None,ask=input,say=print,last_test=None,human=False):
    root=backup.ordinary(root)
    if human:
        original_say=say
        def say(value):
            try:result=json.loads(value)
            except (ValueError,TypeError):original_say(value);return
            if isinstance(result,(dict,list)):show_summary(result,ask,original_say)
            else:original_say(value)
    actions={'1':'backup','2':'doctor','3':'compare','4':'create','5':'activity','6':'intake','7':'followups','8':'calendar','9':'cadence','10':'export','11':'daily','12':'weekly','13':'sync-preview'}
    while True:
        selected=action
        if selected is None:
            value=ask('Vault tools\n1 Back up now and optional retention\n2 Check vault\n3 Compare upgrade candidates\n4 Create a record\n5 Saved integration activity\n6 Selected file/email intake\n7 Follow-up review\n8 Calendar meeting picker\n9 Explicit 1:1 cadence (manager)\n10 Selected export\n11 Daily review\n12 Weekly review\n13 Sync conflict preview (read only)\n0 Back\nChoose: ').strip()
            if value in ('','0'):return
            selected=actions.get(value)
            if not selected:say('Choose a listed option.');continue
        if selected=='backup':backup_ui(root,ask,say)
        elif selected=='doctor':say(json.dumps(doctor(root),indent=2))
        elif selected=='compare':comparison_ui(root,ask,say)
        elif selected=='create':create_ui(root,ask,say)
        elif selected=='activity':activity_ui(root,ask,say,last_test)
        elif selected=='intake':intake_ui(root,ask,say)
        elif selected=='followups':followups_ui(root,ask,say)
        elif selected=='calendar':workflows().calendar_ui(api(),root,ask,say)
        elif selected=='cadence':workflows().cadence_ui(api(),root,ask,say)
        elif selected=='export':workflows().export_ui(api(),root,ask,say)
        elif selected in ('daily','weekly'):journeys().review_ui(api(),root,selected,ask,say)
        elif selected=='sync-preview':journeys().sync_ui(api(),root,ask,say)
        else:raise ValueError('Unknown vault tool')
        if action:return
