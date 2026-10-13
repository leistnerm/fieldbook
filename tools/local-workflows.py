"""Optional human-operated calendar capture, cadence and selected export."""
from datetime import date, datetime, timedelta, timezone
import json
import os
from pathlib import Path
import re
import tempfile
import zipfile
import yaml


def metadata(text,fields):
    # Serialize the existing parsed frontmatter with additions; never run template code.
    match=re.match(r'^\ufeff?---\r?\n(.*?)\r?\n---(?:\r?\n|$)',text,re.S)
    if not match:raise ValueError('Record has no frontmatter')
    fm=yaml.safe_load(match[1]);fm.update(fields)
    newline='\r\n' if '\r\n' in match[0] else '\n'
    return ('---\n'+yaml.safe_dump(fm,sort_keys=False,allow_unicode=True)+'---\n').replace('\n',newline)+text[match.end():]


def scanned(vt,root):
    rows,warnings=vt.records(root)
    if warnings:raise ValueError('Resolve incomplete note scan before identity-dependent actions: '+'; '.join(warnings[:3]))
    return rows


def event_fields(event):
    if event.get('provider') in ('google','microsoft'):
        return {'calendar_provider':event['provider'],'calendar_instance':event['instance'],'calendar_id':event['calendar_id'],
                'calendar_event_id':event['event_id'],'calendar_series_id':event['series_id'],'calendar_occurrence_id':event['occurrence_id']}
    return {'calendar_uid':event['uid'],'calendar_recurrence_id':event.get('recurrence_id',''),'calendar_source':event.get('calendar_source','local export')}


def existing_meetings(vt,root,event):
    fields=event_fields(event);matches=[]
    for row in scanned(vt,root):
        if not vt.tagged(row,'meeting'):continue
        fm=row['fm']
        if 'calendar_provider' in fields:
            keys=['calendar_provider','calendar_instance','calendar_id']
            same=all(str(fm.get(k,''))==str(fields[k]) for k in keys)
            same=same and ((fields['calendar_series_id'] and str(fm.get('calendar_series_id',''))==fields['calendar_series_id'] and str(fm.get('calendar_occurrence_id',''))==fields['calendar_occurrence_id']) or str(fm.get('calendar_event_id',''))==fields['calendar_event_id'])
        else:
            # A matching exported UID/occurrence with unknown source needs review, not duplication.
            same=str(fm.get('calendar_uid',''))==fields['calendar_uid'] and str(fm.get('calendar_recurrence_id','') or '')==str(fields['calendar_recurrence_id'] or '')
        if same:matches.append(row['path'])
    return matches


def meeting_plan(vt,root,event,title,area='',series=None,people=()):
    if event.get('requires_occurrence'):raise ValueError('Export/select a concrete occurrence; recurrence rules are not expanded')
    if event.get('cancelled') or event.get('status')=='cancelled':raise ValueError('Cancelled event: review the existing record; no new meeting is created')
    matches=existing_meetings(vt,root,event)
    if matches:raise ValueError('Existing meeting; open and review instead: '+', '.join(matches))
    start=event.get('start')
    start=(start.get('dateTime') or start.get('date')) if isinstance(start,dict) else start
    when=date.fromisoformat(str(start)[:10])
    rows=scanned(vt,root);by_path={r['path']:r for r in rows}
    fields=event_fields(event)
    if series:
        row=by_path.get(series)
        if not row or not vt.tagged(row,'series'):raise ValueError('Select an existing Series')
        for key in ('calendar_provider','calendar_instance','calendar_id','calendar_series_id'):
            if row['fm'].get(key) and row['fm'][key]!=fields.get(key):raise ValueError('Series calendar identity conflicts with this occurrence')
        series_area=row['fm'].get('area','')
        if area and series_area and area!=series_area:raise ValueError('Selected area conflicts with the linked Series')
        area=area or series_area
        fields['series']='[['+series[:-3]+']]'
    for person in people:
        if person not in by_path or not vt.tagged(by_path[person],'person'):raise ValueError('Only existing selected people may be linked')
    fields.update({'date':when.isoformat(),'attendees':['[['+p[:-3]+']]' for p in people],
                   'calendar_start':event.get('start'),'calendar_end':event.get('end'),'calendar_timezone':event.get('time_zone',''),
                   'calendar_all_day':event.get('all_day',False),'calendar_status':event.get('status',''),
                   'calendar_attendee_count':event.get('attendee_total'),'calendar_attendees_truncated':event.get('attendees_truncated',False)})
    plan=vt.record_plan(root,'Meeting',title,area,today=when)
    plan['text']=metadata(plan['text'],fields)+'\n## Calendar source — unreviewed\n\n'+vt.literal_block(json.dumps({k:event.get(k) for k in ('title','location','description','description_truncated')},ensure_ascii=False,indent=2))+'\n'
    plan['calendar_event']=event
    for path in [*people,*([series] if series else [])]:plan['inputs'][path]=vt.sha(vt.admin.safe(root,path).read_bytes())
    return plan


def calendar_ui(vt,root,ask,say):
    choice=vt.choose(ask,say,['Local ICS export (including Outlook client)','Google Calendar','Microsoft 365 / Outlook'],'Calendar source')
    if choice is None:return
    inputs={}
    if choice==0:
        source=ask('Relative Attachments/*.ics file (Enter cancels): ').strip()
        if not source:return
        if not source.startswith('Attachments/') or not source.lower().endswith('.ics'):raise ValueError('Select an Attachments/*.ics file')
        data=vt.text(root,source);inputs[source]=vt.sha(vt.admin.safe(root,source).read_bytes())
        result=vt.load('calendar_events_ui',vt.HERE.parent/'fieldbook_core/scripts/calendar_events.py').parse_calendar(data,source)
        events=result['events'];say('Warnings: '+json.dumps(result.get('warnings',[])))
    else:
        provider=('google','microsoft')[choice-1]
        if not vt.settings(root).get('features',{}).get(provider):raise ValueError('Enable and configure this provider in Integrations first')
        instances=json.loads(vt.text(root,'fieldbook_core/'+provider+'.json')).get('instances',[])
        n=vt.choose(ask,say,[i['id'] for i in instances],'Saved account')
        if n is None:return
        identity=instances[n]['id'];service=vt.load('calendar_service_ui',vt.HERE.parent/'fieldbook_core/scripts/calendar_service.py')
        result=service.pull_calendar(root,{'provider':provider,'instance':identity,'mode':'calendars'})
        say('Calendar listing truncated: '+str(result['truncated']))
        n=vt.choose(ask,say,[c['name']+' | '+c['id'] for c in result['items']],'Calendar')
        if n is None:return
        calendar=result['items'][n]['id']
        start=ask('First UTC date YYYY-MM-DD: ').strip();end=ask('Last UTC date YYYY-MM-DD (max 93 inclusive days): ').strip()
        result=service.pull_calendar(root,{'provider':provider,'instance':identity,'mode':'events','calendarIds':[calendar],'start':start,'end':end,'limit':100})
        say('Read-only coverage: '+json.dumps(result['coverage']));events=result['items']
    n=vt.choose(ask,say,[str(e['start'])+' | '+e['title']+' | '+e['status'] for e in events],'Occurrence')
    if n is None:return
    event=events[n];matches=existing_meetings(vt,root,event)
    if matches:
        say('Open existing meeting in Obsidian; review source changes manually:\n'+'\n'.join(str(root/p) for p in matches));return
    if event.get('requires_occurrence') or event.get('status')=='cancelled':raise ValueError('Select a concrete non-cancelled occurrence')
    say(json.dumps(event,indent=2,ensure_ascii=True))
    title=ask('Meeting note title (Enter uses event title): ').strip() or event['title']
    area=ask('Area personal/work/school (Enter uses default): ').strip()
    rows=scanned(vt,root);series=[r for r in rows if vt.tagged(r,'series')]
    n=vt.choose(ask,say,[r['path'] for r in series],'Optional existing Series')
    selected_series=series[n]['path'] if n is not None else None
    people=[]
    say('People are optional. No attendees are created automatically; choose individuals only, never an entire roster.')
    if ask('Review the bounded attendee list for individual links/creation? [y/N]: ').strip().lower()=='y':
        for contact in event.get('attendees',[])[:20]:
            email=contact.get('email','').strip().casefold()
            if not email:continue
            rows=scanned(vt,root)
            candidates=[r for r in rows if vt.tagged(r,'person') and any(email==str(v).split(':')[-1].strip().casefold() for k in ('emails','workEmail','otherEmails') for v in vt.nb.values(r['fm'].get(k)))]
            if len(candidates)>1:say('Ambiguous email; skipped: '+email);continue
            if candidates:
                if ask('Link '+candidates[0]['path']+' ('+email+')? [y/N]: ').strip().lower()=='y':people.append(candidates[0]['path'])
            elif ask('Create Person for '+email+'? [y/N]: ').strip().lower()=='y':
                name=ask('Confirmed person name (Enter skips): ').strip()
                if not name:continue
                if vt.resolve(name,vt.index(rows)):raise ValueError('That name or alias already exists; review the existing person before creating another')
                plan=vt.record_plan(root,'Person',name,area);plan['text']=metadata(plan['text'],{'emails':[email]})
                vt.show_plan(root,plan,ask,say)
                if vt.admin.safe(root,plan['path']).is_file():people.append(plan['path'])
    plan=meeting_plan(vt,root,event,title,area,selected_series,people);plan['inputs'].update(inputs)
    if selected_series and ask('Is this occurrence explicitly a one-on-one conversation? [y/N]: ').strip().lower()=='y':
        plan['text']=metadata(plan['text'],{'meeting_kind':'one-on-one'})
    vt.show_plan(root,plan,ask,say)


def cadence(vt,root,today=None):
    cfg=vt.settings(root)
    if 'work' not in cfg.get('setups',[]) or cfg.get('workRole')!='people-manager':return []
    clock=datetime.now(timezone.utc)
    today=today or date.today();rows=scanned(vt,root);idx=vt.index(rows);out=[]
    reports={r['path'] for r in rows if vt.tagged(r,'person') and r['fm'].get('relationship')=='report' and r['fm'].get('status','') in ('','current')}
    for series in rows:
        fm=series['fm']
        if not vt.tagged(series,'series') or fm.get('meeting_kind')!='one-on-one' or fm.get('area')!='work':continue
        person=vt.linked(fm.get('person',''),idx)&reports
        try:days=int(fm.get('cadence_days',''))
        except (ValueError,TypeError):continue
        if len(person)!=1 or not 1<=days<=366:continue
        past=[];future=[]
        for meeting in rows:
            m=meeting['fm']
            if m.get('area')!='work' or not vt.tagged(meeting,'meeting') or m.get('meeting_kind')!='one-on-one' or m.get('calendar_status')=='cancelled' or m.get('status')=='cancelled':continue
            if series['path'] not in vt.linked(m.get('series',''),idx) or not person<=set().union(*(vt.linked(v,idx) for v in vt.nb.values(m.get('attendees')))):continue
            try:day=date.fromisoformat(str(m.get('date',''))[:10])
            except ValueError:continue
            start=m.get('calendar_start')
            start=(start.get('dateTime') or start.get('date')) if isinstance(start,dict) else start
            upcoming=day>today
            if day==today and isinstance(start,str) and 'T' in start:
                try:
                    moment=datetime.fromisoformat(start.replace('Z','+00:00'))
                    if moment.tzinfo:upcoming=moment>clock
                except ValueError:pass
            (future if upcoming else past).append(day)
        last=max(past) if past else None;next_day=min(future) if future else None
        out.append({'series':series['path'],'person':next(iter(person)),'cadence_days':days,'last_recorded':str(last) if last else None,
                    'next_recorded':str(next_day) if next_day else None,'review_due':not last or today>last+timedelta(days=days),
                    'notice':'Only explicitly marked one-on-one notes count. A missing record is not proof a meeting was missed.'})
    return out


def export_plan(vt,root,selected):
    rows=scanned(vt,root);by_path={r['path']:r for r in rows}
    if not selected or len(set(selected))!=len(selected) or len(selected)>200:raise ValueError('Select 1..200 unique files')
    files={};total=0
    for name in selected:
        if name not in by_path and not name.startswith('Attachments/'):raise ValueError('Only selected live notes and Attachments files may be exported')
        if any(p.startswith('.') for p in Path(name).parts):raise ValueError('Hidden files cannot be exported')
        p=vt.admin.safe(root,name);size=p.stat().st_size;total+=size
        if size>10*vt.MAX_FILE or total>64*vt.MAX_FILE:raise ValueError('Export exceeds 10 MiB per file or 64 MiB total')
        files[name]=vt.sha(p.read_bytes())
    idx=vt.index(rows);unresolved=[]
    for name in selected:
        if name not in by_path:continue
        for link in re.findall(r'\[\[([^\]\n]+)\]\]',by_path[name]['text']):
            target=vt.resolve(link,idx)
            if len(target)!=1 or not target<=set(selected):unresolved.append({'source':name,'link':link})
        # Markdown links remain intact and are disclosed rather than followed.
        for target in re.findall(r'\]\(([^\n)]+)\)',by_path[name]['text']):unresolved.append({'source':name,'markdown_link_to_review':target})
    return {'files':files,'bytes':total,'links_to_review':unresolved,'notice':'Selected files only. Review every file for personal/confidential content; no automatic redaction. Relative folders are preserved; omitted or external links may not resolve.'}


def export_save(vt,root,plan,destination):
    dest=vt.backup.ordinary(destination)
    if vt.backup.engine.overlap(root,dest):raise ValueError('Export destination must be outside the vault')
    if dest.suffix.lower()!='.zip' or not dest.parent.is_dir():raise ValueError('Choose a new .zip in an existing outside folder')
    fresh=export_plan(vt,root,list(plan['files']))
    if fresh!=plan:raise ValueError('Export sources changed; preview again')
    fd,tmp=tempfile.mkstemp(prefix='.fieldbook-export-',dir=dest.parent);os.close(fd)
    try:
        with zipfile.ZipFile(tmp,'w',zipfile.ZIP_DEFLATED) as archive:
            for name,digest in plan['files'].items():
                data=vt.admin.safe(root,name).read_bytes()
                if vt.sha(data)!=digest:raise ValueError('Export source changed: '+name)
                archive.writestr(name,data)
            archive.writestr('EXPORT.json',json.dumps(plan,indent=2))
        os.link(tmp,dest)
    finally:os.unlink(tmp)
    return {'exported':str(dest),'files':len(plan['files'])}


def export_ui(vt,root,ask,say):
    rows=scanned(vt,root)
    anchors=[r for r in rows if any(vt.tagged(r,t) for t in ('project','review','accomplishment'))]
    n=vt.choose(ask,say,[r['path'] for r in anchors],'Project/course/review/evidence record')
    if n is None:return
    anchor=anchors[n];idx=vt.index(rows)
    candidates=[r for r in rows if r==anchor or any(anchor['path'] in vt.linked(link,idx) for link in re.findall(r'\[\[([^\]\n]+)\]\]',r['text']))]
    say('Related-note suggestions are not proof of evidence or permission to share.')
    selected=[anchor['path']]
    for row in candidates:
        if row==anchor:continue
        if ask('Include '+row['path']+'? [y/N]: ').strip().lower()=='y':selected.append(row['path'])
    while True:
        extra=ask('Additional exact note/Attachments path (Enter finishes selection): ').strip()
        if not extra:break
        selected.append(extra)
    plan=export_plan(vt,root,selected);say(json.dumps(plan,indent=2,ensure_ascii=True))
    destination=ask('New export .zip path outside the vault (Enter cancels): ').strip()
    if destination and ask('Type export after reviewing scope and privacy (Enter cancels): ').strip()=='export':say(json.dumps(export_save(vt,root,plan,destination)))


def cadence_ui(vt,root,ask,say):
    cfg=vt.settings(root)
    if 'work' not in cfg.get('setups',[]) or cfg.get('workRole')!='people-manager':raise ValueError('Cadence setup requires work + people manager')
    say(json.dumps(cadence(vt,root),indent=2))
    if ask('Configure an explicitly agreed 1:1 cadence? [y/N]: ').strip().lower()!='y':return
    rows=scanned(vt,root)
    series=[r for r in rows if vt.tagged(r,'series') and r['fm'].get('area')=='work']
    reports=[r for r in rows if vt.tagged(r,'person') and r['fm'].get('relationship')=='report' and r['fm'].get('status','') in ('','current')]
    n=vt.choose(ask,say,[r['path'] for r in series],'Existing work Series')
    if n is None:return
    record=series[n]
    n=vt.choose(ask,say,[r['path'] for r in reports],'Confirmed direct report')
    if n is None:return
    person=reports[n]
    days=ask('Agreed cadence in days (1..366): ').strip()
    if not days.isdigit() or not 1<=int(days)<=366:raise ValueError('Choose 1..366 days')
    content=metadata(record['text'],{'meeting_kind':'one-on-one','person':'[['+person['path'][:-3]+']]','cadence_days':int(days)})
    say(record['path']+'\n'+content)
    if ask('Type apply to update only this Series; its original is backed up (Enter cancels): ').strip()!='apply':return
    p=vt.admin.safe(root,record['path'])
    if vt.sha(p.read_bytes())!=record['sha256'] or vt.sha(vt.admin.safe(root,person['path']).read_bytes())!=person['sha256']:raise ValueError('Source changed; preview again')
    backup='.fieldbook/config-backups/'+vt.uuid.uuid4().hex+'-cadence/'+record['path']
    b=vt.admin.safe(root,backup);b.parent.mkdir(parents=True,exist_ok=True)
    with b.open('xb') as stream:stream.write(p.read_bytes())
    vt.admin.write(p,content);say('Updated '+record['path']+'; original: '+backup)
