"""Guided local onboarding and daily/weekly reviews; no remote requests."""
from datetime import date,timedelta
import json
from pathlib import Path
import re


def iso(value):
    try:return date.fromisoformat(str(value))
    except (ValueError,TypeError):return None


def review(vt,root,kind='daily',area='',today=None):
    if kind not in ('daily','weekly') or area not in ('','personal','work','school'):raise ValueError('Choose daily/weekly and a valid area')
    today=today or date.today();last=today+timedelta(days=0 if kind=='daily' else 6);first=today-timedelta(days=0 if kind=='daily' else 6)
    rows,warnings=vt.records(root)
    selected=[r for r in rows if not area or r['fm'].get('area')==area]
    unknown=[r['path'] for r in rows if area and not r['fm'].get('area')]
    sections={k:[] for k in ('overdue_deadlines','deadlines_in_window','planned_work','meetings','other_dates','recent_completions','recorded_accomplishments','goals','invalid_dates')}
    recurring=[]
    for row in selected:
        fm=row['fm'];path=row['path']
        def add(key,**values):sections[key].append({'path':path,**values})
        if vt.tagged(row,'task'):
            if fm.get('recurrence'):recurring.append(path);continue
            due=iso(fm.get('due'));planned=iso(fm.get('scheduled'));done=iso(fm.get('completedDate'))
            if vt.opened(row):
                if due and due<today:add('overdue_deadlines',due=str(due),status=fm.get('status',''))
                elif due and due<=last:add('deadlines_in_window',due=str(due),status=fm.get('status',''))
                if planned and today<=planned<=last:add('planned_work',scheduled=str(planned),due=fm.get('due',''))
            elif fm.get('status')=='done' and done and first<=done<=today:add('recent_completions',completed=str(done),suggestion='Review whether this outcome warrants an accomplishment; no impact inferred')
            for key in ('due','scheduled','completedDate'):
                if fm.get(key) and not iso(fm[key]):add('invalid_dates',field=key,value=str(fm[key])[:100])
        if vt.tagged(row,'meeting'):
            day=iso(str(fm.get('date',''))[:10])
            if day and today<=day<=last and fm.get('calendar_status')!='cancelled' and fm.get('status')!='cancelled':add('meetings',date=str(day),start=fm.get('calendar_start',''),series=fm.get('series',''))
        if vt.tagged(row,'goal') and fm.get('status') not in ('done','dropped','closed'):add('goals',target=fm.get('target',''),check_in=fm.get('check_in',''))
        if vt.tagged(row,'accomplishment'):
            start=iso(fm.get('period_start') or fm.get('date'));end=iso(fm.get('period_end') or fm.get('date') or fm.get('period_start'))
            if start and end and start<=end and start<=today and end>=first:add('recorded_accomplishments',period_start=str(start),period_end=str(end))
        fields=[]
        if vt.tagged(row,'item') and fm.get('status') not in ('disposed','sold','returned','lost','cancelled'):fields+=['return_by','warranty_end','renewal_date','cancellation_notice_by','expiration_date']
        if vt.tagged(row,'opportunity') and fm.get('status') not in ('closed','declined','accepted'):fields+=['closing_date']
        if vt.tagged(row,'decision') and fm.get('status')!='superseded':fields+=['revisit']
        for field in fields:
            d=iso(fm.get(field))
            if d and d<=last:add('other_dates',meaning=field,date=str(d),timing='past date to review' if d<today else 'in window')
            elif fm.get(field) and not d:add('invalid_dates',field=field,value=str(fm[field])[:100])
    follow=vt.followups(root,area,7 if kind=='weekly' else 30,today)
    # Inbox is global, so do not silently include mixed/private text in an area-scoped review.
    inbox={'path':'Inbox.md','included':False,'notice':'Open Inbox for capture triage; nothing is converted automatically.'}
    p=vt.admin.safe(root,'Inbox.md')
    if not area and p.is_file():inbox.update(included=True,text=vt.text(root,'Inbox.md')[:12000],truncated=p.stat().st_size>12000)
    for items in sections.values():items.sort(key=lambda r:(r.get('due',r.get('date',r.get('scheduled',''))),r['path']))
    return {'kind':kind,'date':str(today),'window':{'start':str(today),'end':str(last),'lookback_start':str(first)},'area':area or 'all including blank',
            'sections':sections,'followups':follow,'inbox':inbox,'unassigned_area_to_review':unknown,'recurring_tasks_use_TaskNotes':recurring,
            'scan_warnings':warnings,'changed':False,
            'coverage':'Local saved notes only; no live calendars or trackers were fetched. Missing meetings are not free time. Source-date tables in bodies and Canvas checkpoints require opening their notes.',
            'next_steps':['Choose up to three focus items','Review blockers and commitments','Check the selected calendar if needed','Record only confirmed outcomes','Save an optional snapshot; task edits remain separate']}


def review_ui(vt,root,kind,ask,say):
    area=ask('Review area personal/work/school (Enter includes all and blank): ').strip()
    data=review(vt,root,kind,area)
    say(kind.capitalize()+' review | '+data['date']+' | '+data['area']);say(data['coverage'])
    for warning in data['scan_warnings']:say('INCOMPLETE SCAN: '+warning)
    for name,items in data['sections'].items():
        say('\n'+name.replace('_',' ').capitalize()+' ('+str(len(items))+')')
        for row in items[:100]:say(' | '.join(str(k)+': '+str(v) for k,v in row.items()))
        if len(items)>100:say('Showing first 100; request details for the complete bounded report.')
    follow=data['followups']
    for key in ('overdue_check_ins','upcoming_check_ins','waiting_or_assigned_tasks','active_projects_without_open_linked_task','recorded_commitments_to_review','one_on_one_cadence'):
        value=follow.get(key,[]);say('\n'+key.replace('_',' ').capitalize()+': '+str(len(value)))
        for row in value[:100]:say(str(row))
    if data['unassigned_area_to_review']:say('Unassigned-area notes need a separate scope decision: '+str(len(data['unassigned_area_to_review'])))
    say('Inbox: '+data['inbox']['notice'])
    if data['inbox'].get('included'):say(data['inbox']['text'])
    if ask('Type details for complete JSON, otherwise Enter: ').strip()=='details':say(json.dumps(data,indent=2,ensure_ascii=True))
    focus=[]
    while len(focus)<3:
        name=ask('Optional focus note path (Enter finishes; at most three): ').strip()
        if not name:break
        rows,warnings=vt.records(root)
        if warnings:raise ValueError('Resolve incomplete scans before selecting focus notes')
        allowed={r['path'] for r in rows if not area or r['fm'].get('area')==area}
        if name not in allowed:raise ValueError('Choose an exact existing note path within the review scope')
        if name not in focus:focus.append(name)
    data['selected_focus']=focus
    if ask('Save this review snapshot? [y/N]: ').strip().lower()=='y':
        plan=vt.report_plan(root,kind.capitalize()+' review '+data['date'],data)
        # Preserve literal imported text and Inbox source so it cannot render remote embeds.
        plan['text']='# '+kind.capitalize()+' review — '+data['date']+'\n\nScope: '+data['area']+'\n\n## Focus\n'+''.join('- [['+p[:-3]+']]\n' for p in focus)+'\n## Review snapshot — source data\n\n'+vt.literal_block(json.dumps(data,indent=2,ensure_ascii=False))+'\n'
        if len(plan['text'].encode('utf-8'))>vt.MAX_FILE:raise ValueError('Review snapshot exceeds 1 MiB; narrow the review scope or keep the on-screen summary')
        vt.show_plan(root,plan,ask,say)
    say('Review complete. No tasks, deadlines, calendar entries or tracker items were changed.')


def self_record(vt,root,ask,say):
    rows,warnings=vt.records(root)
    if warnings:raise ValueError('Resolve incomplete scans before setting up your self record')
    people=[r for r in rows if vt.tagged(r,'person')]
    selves=[r for r in people if r['fm'].get('relationship')=='self']
    if len(selves)>1:say('Multiple self records: '+', '.join(r['path'] for r in selves)+'. Resolve these deliberately; none were changed.');return
    if selves:say('Your self record: '+selves[0]['path']);return
    say('A self record helps personal context, tracker identity and optional reviews. Skip it if not useful.')
    choice=ask('1 Use an existing person\n2 Create a neutral Person\nEnter skips\nChoose: ').strip()
    if choice=='2':
        name=ask('Your name for the note (Enter skips): ').strip()
        if not name:return
        if vt.resolve(name,vt.index(rows)):raise ValueError('That name/alias already exists; select the existing person instead')
        plan=vt.record_plan(root,'Person',name);plan['text']=vt.workflows().metadata(plan['text'],{'relationship':'self'});plan['self_record']=True
        vt.show_plan(root,plan,ask,say)
    elif choice=='1':
        n=vt.choose(ask,say,[r['path'] for r in people],'Your existing Person')
        if n is None:return
        row=people[n]
        if row['fm'].get('relationship') not in ('','self',None):raise ValueError('This person already has another relationship; review it manually instead of replacing it during onboarding')
        content=vt.workflows().metadata(row['text'],{'relationship':'self'})
        say(row['path']+'\n'+content)
        if ask('Type apply to mark this record as self and back up its original: ').strip()!='apply':return
        fresh,warnings=vt.records(root)
        if warnings or any(vt.tagged(r,'person') and r['fm'].get('relationship')=='self' for r in fresh):raise ValueError('Self-record state changed; review again')
        p=vt.admin.safe(root,row['path'])
        if vt.sha(p.read_bytes())!=row['sha256']:raise ValueError('Person changed; preview again')
        backup=vt.admin.safe(root,'.fieldbook/config-backups/'+vt.uuid.uuid4().hex+'-self/'+row['path']);backup.parent.mkdir(parents=True,exist_ok=True)
        with backup.open('xb') as stream:stream.write(p.read_bytes())
        vt.admin.write(p,content);say('Self record saved; original backed up.')
    elif choice:raise ValueError('Choose 1, 2 or Enter')


def finish_onboarding(vt,root,ask,say):
    self_record(vt,root,ask,say)
    say('\nStart at '+str(root/'Dashboard.md')+' in Obsidian. Enabled area dashboards are linked there.')
    say('For manual templates: use Editing view or Templater: Create new note from template.')
    if ask('Capture one first task now? [y/N]: ').strip().lower()=='y':
        title=ask('Task title (Enter skips): ').strip()
        if title:vt.show_plan(root,vt.record_plan(root,'Task',title),ask,say)
    say('Next: Daily use > Daily review; Weekly review for a broader check. Integrations > Guided setup is optional; it walks through credentials and read tests. Maintenance > Back up vault creates a full snapshot.')
    say('You can rerun onboarding to inspect or adjust settings. Existing people, notes and customizations are preserved; no background sync or remote writes were enabled.')


def sync_ui(vt,root,ask,say):
    path=ask('Selected Attachments/*.json proposal (Enter cancels): ').strip()
    if not path:return
    if not path.startswith('Attachments/') or not path.endswith('.json'):raise ValueError('Choose a selected Attachments JSON proposal')
    args=json.loads(vt.text(root,path))
    if not isinstance(args,dict) or set(args)!={'path','expected','sync'}:raise ValueError('Proposal needs path, expected SHA and sync object; see Sync previews.md')
    result=vt.nb.Vault(root).preview(args)
    say('Sync preview: '+result['path']+' | '+json.dumps(result['source']))
    say('FIELD | LAST REVIEWED SOURCE | LOCAL | PROPOSED | RESULT')
    for row in result['fields']:say(' | '.join(json.dumps(row[k],ensure_ascii=True) for k in ('field','last_reviewed_source','local','proposed','classification'))+' | '+row['reason'])
    say(result['notice']);say('Coverage: '+json.dumps(result['coverage']))
