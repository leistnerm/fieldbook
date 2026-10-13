"""Evaluate shipped Base filters against fixtures, not a second set of predicates.

This intentionally small interpreter covers only the documented expression subset
used in this kit. It fails on unsupported syntax; it is not Obsidian's native engine
or a UI certification. Runtime fieldbook code does not import this test helper.
"""
import datetime as dt
from dataclasses import dataclass
import json
from pathlib import Path
import re
import unittest
import yaml

ROOT = Path(__file__).resolve().parents[1]
TODAY = dt.datetime(2026, 10, 10)
TOKEN = re.compile(r'\s*(?:("(?:\\.|[^"\\])*")|(\d+)|([A-Za-z_][A-Za-z_0-9]*)|(&&|\|\||==|!=|<=|>=|[().,!+<>-]))')

class Expression:
    levels = {'||':1,'&&':2,'==':3,'!=':3,'<':4,'<=':4,'>':4,'>=':4,'+':5,'-':5}
    def __init__(self, text):
        self.tokens=[]; pos=0
        while pos<len(text):
            m=TOKEN.match(text,pos)
            if not m:raise ValueError(f'Unsupported syntax: {text[pos:]}')
            self.tokens.append(next(x for x in m.groups() if x is not None));pos=m.end()
        self.i=0;self.tree=self.parse()
        if self.i!=len(self.tokens):raise ValueError(f'Unparsed: {text}')
    def peek(self):return self.tokens[self.i] if self.i<len(self.tokens) else None
    def pop(self):v=self.peek();self.i+=1;return v
    def expect(self,v):
        if self.pop()!=v:raise ValueError(f'Expected {v}')
    def parse(self,level=0):
        t=self.pop()
        if t=='!':a=('not',self.parse(6))
        elif t=='(':
            a=self.parse();self.expect(')')
        elif t and t.startswith('"'):a=('literal',json.loads(t))
        elif t and t.isdigit():a=('literal',int(t))
        elif t in ('true','false','null'):a=('literal',{'true':True,'false':False,'null':None}[t])
        elif t and re.fullmatch(r'[A-Za-z_][A-Za-z_0-9]*',t):a=('name',t)
        else:raise ValueError(f'Unexpected {t}')
        while self.peek() in ('.','('):
            if self.pop()=='.':a=('attr',a,self.pop())
            else:
                args=[]
                if self.peek()!=')':
                    args.append(self.parse())
                    while self.peek()==',':self.pop();args.append(self.parse())
                self.expect(')');a=('call',a,args)
        while self.peek() in self.levels and self.levels[self.peek()]>level:
            op=self.pop();a=('binary',op,a,self.parse(self.levels[op]))
        return a

@dataclass(frozen=True)
class Link:
    path: str

class File:
    def __init__(self,path,properties):self.path=path;self.properties=properties
    @property
    def name(self):return Path(self.path).stem
    @property
    def ext(self):return Path(self.path).suffix.lstrip('.')

class Engine:
    def __init__(self, rows, host='Dashboard.md'):
        self.files={p:File(p,dict(fm)) for p,fm in rows.items()};self.host=self.files.get(host,File(host,{}))
        for f in self.files.values():f.properties={k:self.convert(v) for k,v in f.properties.items()}
    def convert(self,v):
        if isinstance(v,list):return [self.convert(x) for x in v]
        if isinstance(v,str) and v.startswith('[[') and v.endswith(']]'):
            target=v[2:-2].split('|')[0];p=target if target.endswith('.md') else target+'.md'
            if p not in self.files:
                matches=[f.path for f in self.files.values() if f.name==target]
                if len(matches)==1:p=matches[0]
            return Link(p)
        return v
    def env(self,file,base):
        return {**file.properties,'note':file.properties,'file':file,
                'this':{**self.host.properties,'file':self.host},'formula':('formulas',base.get('formulas',{}))}
    def expression(self,text,env):return self.eval(Expression(text).tree,env)
    def eval(self,a,e):
        kind=a[0]
        if kind=='literal':return a[1]
        if kind=='name':return e.get(a[1])
        if kind=='not':return not self.eval(a[1],e)
        if kind=='attr':
            v=self.eval(a[1],e);key=a[2]
            if isinstance(v,tuple) and v[0]=='formulas':return self.expression(v[1][key],e)
            if isinstance(v,dict):return v.get(key)
            if key=='length':return len(v) if v is not None else 0
            return getattr(v,key,None)
        if kind=='binary':
            op=a[1];left=self.eval(a[2],e)
            if op=='&&':return bool(left) and bool(self.eval(a[3],e))
            if op=='||':return bool(left) or bool(self.eval(a[3],e))
            right=self.eval(a[3],e)
            if op=='==':return left==right
            if op=='!=':return left!=right
            if left is None or right is None:return False
            if op in ('+','-'):
                if isinstance(left,dt.datetime) and isinstance(right,str):
                    if not re.fullmatch(r'\d+d',right):raise ValueError('Unsupported duration')
                    right=dt.timedelta(days=int(right[:-1]))
                return left+right if op=='+' else left-right
            return {'<':lambda:left<right,'<=':lambda:left<=right,'>':lambda:left>right,'>=':lambda:left>=right}[op]()
        if kind=='call':
            callee,args=a[1],a[2]
            if callee[0]=='name':
                name=callee[1]
                if name=='if':return self.eval(args[1] if self.eval(args[0],e) else args[2],e)
                values=[self.eval(x,e) for x in args]
                if name=='today':return TODAY
                if name=='list':return values[0] if isinstance(values[0],list) else [values[0]]
                if name=='date':return dt.datetime.fromisoformat(str(values[0])) if values[0] else None
                raise ValueError(f'Unsupported function {name}')
            obj=self.eval(callee[1],e);name=callee[2]
            if name=='filter':return [v for v in obj if self.eval(args[0],{**e,'value':v})]
            vals=[self.eval(x,e) for x in args]
            if name=='isEmpty':return obj is None or obj=='' or obj==[] or obj=={}
            if name=='isType':return vals[0]=='link' and isinstance(obj,Link)
            if name=='contains':return vals[0] in obj if obj is not None else False
            if name=='asLink':return Link(obj.path)
            if name=='asFile':return self.files.get(obj.path)
            if name=='hasTag':return any(t==vals[0] or t.startswith(vals[0]+'/') for t in obj.properties.get('tags',[]))
            if name=='inFolder':return obj.path.startswith(vals[0].rstrip('/')+'/')
            if name=='toString':return str(obj)
            raise ValueError(f'Unsupported method {name}')
        raise ValueError(f'Unsupported AST: {a}')
    def match(self,filters,e):
        if not filters:return True
        if isinstance(filters,str):return bool(self.expression(filters,e))
        if 'and' in filters:return all(self.match(x,e) for x in filters['and'])
        if 'or' in filters:return any(self.match(x,e) for x in filters['or'])
        if 'not' in filters:return not any(self.match(x,e) for x in filters['not'])
        raise ValueError(f'Unsupported filter {filters}')
    def rows(self,name,view):
        b=BASES[name];v=next(v for v in b['views'] if v['name']==view)
        return sorted(f.path for f in self.files.values() if self.match(b.get('filters'),self.env(f,b)) and self.match(v.get('filters'),self.env(f,b)))

BASES={p.stem:yaml.safe_load(p.read_text()) for p in (ROOT/'Views').glob('*.base')}
def task(**kw):return {'tags':['task'],'status':'active',**kw}
def record(tag,**kw):return {'tags':[tag],**kw}

class ViewTests(unittest.TestCase):
    def test_active_decision_revisit_dates_surface_without_requiring_a_second_status_change(self):
        rows = {f'Decisions/{name}.md': record('decision', **fields) for name, fields in {
            'active-due': {'status': 'active', 'revisit': '2026-10-10'},
            'overdue': {'status': 'active', 'revisit': '2026-09-01'},
            'explicit-undated': {'status': 'revisit'},
            'future': {'status': 'active', 'revisit': '2026-12-01'},
            'superseded': {'status': 'superseded', 'revisit': '2026-10-10'},
            'ordinary': {'status': 'active'},
        }.items()}
        self.assertEqual(Engine(rows).rows('Decisions', 'Due for revisit'),
                         ['Decisions/active-due.md', 'Decisions/explicit-undated.md', 'Decisions/overdue.md'])

    def test_every_expression_parses_and_view_names_are_unique(self):
        def check(f):
            if isinstance(f,str):Expression(f)
            elif isinstance(f,dict):
                for xs in f.values():
                    for x in xs:check(x)
        for name,b in BASES.items():
            with self.subTest(base=name):
                self.assertEqual(len(b['views']),len({v['name'] for v in b['views']}))
                check(b.get('filters'))
                for s in b.get('formulas',{}).values():Expression(s)
                for v in b['views']:check(v.get('filters'))

    def test_shared_task_views_include_every_area_and_unknown_context(self):
        rows={f'Tasks/{a or "blank"}.md':task(area=a) for a in ('personal','work','school','')}
        rows['Tasks/missing.md']=task();rows['Tasks/assigned.md']=task(assignee=['[[Peer]]'])
        rows['People/Peer.md']=record('person',relationship='peer')
        e=Engine(rows);expected=sorted(p for p in rows if p.startswith('Tasks/'))
        for name in ['Now','Open by area','Open by priority','All tasks']:
            self.assertEqual(e.rows('Dashboard',name),expected,name)
        self.assertEqual(e.rows('Dashboard','No area'),['Tasks/assigned.md','Tasks/blank.md','Tasks/missing.md'])
        for a in ('Personal','Work','School'):
            self.assertEqual(e.rows(a,'Next actions'),[f'Tasks/{a.lower()}.md'])

    def test_all_bases_exclude_templates_and_examples_even_with_live_record_tags(self):
        for name,b in BASES.items():
            for v in b['views']:
                with self.subTest(base=name,view=v['name']):
                    fm={'tags':['task','project','person','meeting','decision','review','reference','research','note','item','list','accomplishment','opportunity'], 'area':'work','status':'active','jira':'APP-1'}
                    self.assertEqual(Engine({'Templates/Sample.md':fm,'Examples/Sample.md':fm}).rows(name,v['name']),[])

    def test_now_deadline_boundaries_and_recurring_instances(self):
        rows={'Tasks/active.md':task(), 'Tasks/due.md':task(status='backlog',due='2026-10-10'),
              'Tasks/overdue.md':task(status='backlog',due='2026-10-09'),
              'Tasks/scheduled.md':task(status='backlog',scheduled='2026-10-10'),
              'Tasks/future.md':task(status='backlog',due='2026-10-24'),
              'Tasks/later.md':task(status='backlog',due='2026-10-25'),
              'Tasks/blocked.md':task(status='blocked',due='2026-10-09'),
              'Tasks/dropped.md':task(status='dropped',due='2026-10-09'),
              'Tasks/recurring.md':task(recurrence='weekly',due='2026-10-01')}
        e=Engine(rows)
        self.assertEqual(e.rows('Dashboard','Now'),['Tasks/active.md','Tasks/due.md','Tasks/overdue.md','Tasks/scheduled.md'])
        self.assertEqual(e.rows('Dashboard','Upcoming'),['Tasks/due.md','Tasks/future.md'])
        self.assertEqual(e.rows('Dashboard','Overdue'),['Tasks/blocked.md','Tasks/overdue.md'])
        self.assertEqual(e.rows('Dashboard','Recurring'),['Tasks/recurring.md'])
        for a in ('Personal','Work','School'):
            scoped=Engine({p:{**fm,'area':a.lower()} for p,fm in rows.items()})
            for v in ('Upcoming','Overdue','Blocked'):self.assertEqual(scoped.rows(a,v),e.rows('Dashboard',v))

    def test_recent_completions_exclude_future_undated_dropped_and_recurring(self):
        rows={f'Tasks/{n}.md':task(status='done',**p) for n,p in {
            'today':{'completedDate':'2026-10-10'}, 'edge':{'completedDate':'2026-10-04'},
            'old':{'completedDate':'2026-10-03'}, 'future':{'completedDate':'2026-10-11'},
            'undated':{}, 'recurring':{'completedDate':'2026-10-10','recurrence':'weekly'}}.items()}
        rows['Tasks/dropped.md']=task(status='dropped',completedDate='2026-10-10')
        e=Engine(rows);self.assertEqual(e.rows('Dashboard','Done last 7 days'),['Tasks/edge.md','Tasks/today.md'])
        self.assertEqual(e.rows('Dashboard','Done in range'),['Tasks/edge.md','Tasks/old.md','Tasks/today.md'])
        for a in ('Personal','Work','School'):
            self.assertEqual(Engine({p:{**fm,'area':a.lower()} for p,fm in rows.items()}).rows(a,'Done last 7 days'),['Tasks/edge.md','Tasks/today.md'])

    def test_self_person_includes_unassigned_tasks_but_other_people_do_not(self):
        rows={'People/Me.md':record('person',relationship='self'),'People/Sam.md':record('person',relationship='classmate'),
              'Tasks/mine.md':task(),'Tasks/me-linked.md':task(assignee=['[[Me]]']),
              'Tasks/sam.md':task(assignee=['[[Sam]]']),'Tasks/requested.md':task(assignee=['[[Sam]]'],requester='[[Me]]')}
        self.assertEqual(Engine(rows,'People/Me.md').rows('Person','Open'),['Tasks/me-linked.md','Tasks/mine.md'])
        self.assertEqual(Engine(rows,'People/Sam.md').rows('Person','Open'),['Tasks/requested.md','Tasks/sam.md'])
        self.assertEqual(Engine(rows,'People/Me.md').rows('Person','Requested open'),['Tasks/requested.md'])
        self.assertEqual(Engine(rows).rows('Dashboard','My open'),['Tasks/me-linked.md','Tasks/mine.md'])

    def test_manager_report_tasks_require_current_explicit_report_relationship(self):
        people={'Report':{'relationship':'report','status':'current'},'Blank':{'relationship':'report'},
                'Former':{'relationship':'report','status':'former'},'Peer':{'relationship':'peer','manager':'[[Me]]'},
                'Vendor':{'relationship':'vendor'},'Me':{'relationship':'self'}}
        rows={f'People/{n}.md':record('person',**p) for n,p in people.items()}
        rows.update({f'Tasks/{n}.md':task(area='work',assignee=[f'[[People/{n}]]']) for n in [*people,'Missing']})
        rows['Tasks/unassigned.md']=task(area='work');rows['Tasks/school.md']=task(area='school',assignee=['[[People/Report]]'])
        rows['Notes/Not a person.md']=record('note',relationship='report')
        rows['Tasks/not-person.md']=task(area='work',assignee=['[[Notes/Not a person]]'])
        e=Engine(rows)
        self.assertEqual(e.rows('Work','Report tasks'),['Tasks/Blank.md','Tasks/Report.md'])
        self.assertEqual(e.rows('People','My team'),['People/Blank.md','People/Report.md'])
        self.assertEqual(len(e.rows('Work','Next actions')),9)

    def test_exact_project_links_support_paths_aliases_one_level_and_missing_links(self):
        rows={'Projects/A.md':record('project'), 'Projects/Child.md':record('project',parent='[[Projects/A|Main]]'),
              'Projects/Grandchild.md':record('project',parent='[[Child]]'), 'Projects/AA.md':record('project'),
              'Tasks/direct.md':task(projects=['[[Projects/A]]']), 'Tasks/child.md':task(projects=['[[Child|Phase]]']),
              'Tasks/grandchild.md':task(projects=['[[Grandchild]]']), 'Tasks/other.md':task(projects=['[[AA]]']),
              'Tasks/missing.md':task(projects=['[[Missing]]'])}
        e=Engine(rows,'Projects/A.md')
        self.assertEqual(e.rows('Project','Sub-projects'),['Projects/Child.md'])
        self.assertEqual(e.rows('Project','Open tasks'),['Tasks/child.md','Tasks/direct.md'])
        self.assertEqual(Engine(rows).rows('Project','Open tasks'),[])

    def test_tracker_inventory_and_jira_candidates_are_explicit_and_cross_context(self):
        rows={'Projects/App.md':record('project',jira='APP'),'Projects/No.md':record('project',jira='none'),
              'Tasks/candidate.md':task(area='school',projects=['[[App]]']), 'Tasks/plain.md':task(area='work'),
              'Tasks/optout.md':task(projects=['[[App]]'],jira='none'), 'Tasks/no-project.md':task(projects=['[[No]]']),
              'Tasks/missing.md':task(projects=['[[Missing]]']), 'Tasks/done.md':task(status='done',projects=['[[App]]'])}
        for provider in ('jira','agility','github','azure'):
            rows[f'Notes/{provider}.md']=record('note',area='personal',**{provider:'ABC-123',f'{provider}_instance':'test'})
        e=Engine(rows)
        self.assertEqual(e.rows('Trackers','Jira candidates'),['Tasks/candidate.md'])
        self.assertEqual(e.rows('Dashboard','No Jira decision'),['Tasks/candidate.md'])
        self.assertEqual(e.rows('Trackers','Linked'),['Notes/agility.md','Notes/azure.md','Notes/github.md','Notes/jira.md','Projects/App.md'])

    def test_neutral_record_directories_do_not_require_specialized_metadata(self):
        rows={'Items/book.md':record('item'), 'Items/drill.md':record('item',status='borrowed',area='school'),
              'Lists/materials.md':record('list',area='work'), 'Research/idea.md':record('research',status='idea'),
              'Research/unknown.md':record('research'),'Research/closed.md':record('research',status='concluded'),
              'Reference/recipe.md':record('reference',kind='recipe'),'People/Friend.md':record('person',relationship='friend'),
              'Opportunities/accepted.md':record('opportunity',status='accepted'), 'Opportunities/unknown.md':record('opportunity'),
              'Accomplishments/undated.md':record('accomplishment')}
        e=Engine(rows)
        self.assertEqual(e.rows('Items','All'),['Items/book.md','Items/drill.md'])
        self.assertEqual(e.rows('Items','Purchase details'),[])
        self.assertEqual(e.rows('Lists','All'),['Lists/materials.md'])
        self.assertEqual(e.rows('Research','Open'),['Research/idea.md','Research/unknown.md'])
        self.assertEqual(e.rows('Reference','All'),['Reference/recipe.md'])
        self.assertEqual(e.rows('Reference','Not verified in a year'),[])
        self.assertEqual(e.rows('People','Directory'),['People/Friend.md'])
        self.assertEqual(e.rows('Opportunities','Open'),['Opportunities/unknown.md'])
        self.assertEqual(e.rows('Opportunities','Closed'),['Opportunities/accepted.md'])
        self.assertEqual(e.rows('Accomplishments','All'),['Accomplishments/undated.md'])

    def test_meetings_default_is_not_series_bound_and_recent_is_not_future(self):
        rows={f'Meetings/{n}.md':record('meeting',date=d) for n,d in [('today','2026-10-10'),('edge','2026-09-11'),('old','2026-09-10'),('future','2026-10-11')]}
        e=Engine(rows);self.assertEqual(BASES['Meetings']['views'][0]['name'],'Recent')
        self.assertEqual(e.rows('Meetings','Recent'),['Meetings/edge.md','Meetings/today.md'])
        self.assertEqual(e.rows('Meetings','Upcoming'),['Meetings/future.md'])
        self.assertEqual(e.rows('Meetings','Series'),[])

    def test_role_sections_are_not_embedded_in_shared_dashboards(self):
        for file in ['Dashboard.md','Dashboards/Personal.md','Dashboards/Work.md','Dashboards/School.md','Dashboards/Work - Individual contributor.md']:
            embeds=re.findall(r'!\[\[([^\]]+)\]\]',(ROOT/file).read_text())
            self.assertFalse(any(any(x in e for x in ['Reviews.base','My team','Report tasks','#Courses','#Past courses','No Jira decision']) for e in embeds),file)
        self.assertNotIn('jira',BASES['Projects']['views'][0]['order'])
        self.assertFalse(any(p in BASES['People']['views'][0]['order'] for p in ['company','title','hireDate','workerType']))
        rows={'Tasks/review.md':task(tags=['task','review']), 'Reports/Review.md':record('review',status='draft')}
        self.assertEqual(Engine(rows).rows('Reviews','By year'),['Reports/Review.md'])

class UpcomingDatesTests(unittest.TestCase):
    def test_upcoming_spans_areas_and_keeps_both_item_dates(self):
        rows={
          'Tasks/work.md':task(area='work',due='2026-10-11'),
          'Tasks/school.md':task(area='school',due='2026-10-12'),
          'Tasks/recurring.md':task(due='2026-10-12',recurrence='FREQ=WEEKLY'),
          'Tasks/done.md':task(status='done',due='2026-10-12'),
          'Opportunities/personal.md':record('opportunity',area='personal',closing_date='2026-10-13'),
          'Opportunities/closed.md':record('opportunity',status='closed',closing_date='2026-10-13'),
          'Decisions/blank.md':record('decision',status='active',revisit='2026-10-14'),
          'Decisions/old.md':record('decision',status='superseded',revisit='2026-10-14'),
          'Items/both.md':record('item',return_by='2026-10-15',warranty_end='2026-10-20'),
          'Items/past-return.md':record('item',return_by='2026-09-01',warranty_end='2026-10-21'),
          'Items/returned.md':record('item',status='returned',return_by='2026-10-15'),
          'Items/far.md':record('item',return_by='2027-01-01'),
          'Items/none.md':record('item'),
        }
        e=Engine(rows)
        self.assertEqual(e.rows('Upcoming dates','Next 30 days'),sorted(['Tasks/work.md','Tasks/school.md','Opportunities/personal.md','Decisions/blank.md','Items/both.md','Items/past-return.md']))
        self.assertEqual(e.rows('Upcoming dates','Past dates to review'),['Items/past-return.md'])
        self.assertEqual(e.expression(BASES['Upcoming dates']['formulas']['upcomingDate'],e.env(e.files['Items/past-return.md'],BASES['Upcoming dates'])),'2026-10-21')
        self.assertIn('Items/both.md',e.rows('Upcoming dates','Return dates'))
        self.assertIn('Items/both.md',e.rows('Upcoming dates','Warranty dates'))

    def test_date_window_includes_today_and_day_30_but_not_day_31(self):
        e=Engine({f'Tasks/{i}.md':task(due=d) for i,d in enumerate(['2026-10-09','2026-10-10','2026-11-09','2026-11-10'])})
        self.assertEqual(e.rows('Upcoming dates','Next 30 days'),['Tasks/1.md','Tasks/2.md'])
        self.assertEqual(e.rows('Upcoming dates','Past dates to review'),['Tasks/0.md'])

class FollowupViewsTests(unittest.TestCase):
    def test_shared_followup_tabs_boundaries_status_and_neutral_assignments(self):
        rows={
            'Tasks/blocked.md':task(area='personal',status='blocked'),
            'Tasks/self.md':task(area='school',assignee=['[[Me]]']),
            'Tasks/done.md':task(status='done',assignee=['[[Peer]]']),
            'Notes/today.md':record('note',check_in='2026-10-10'),
            'Notes/edge.md':record('note',check_in='2026-10-24'),
            'Notes/late.md':record('note',check_in='2026-10-25'),
            'Notes/old.md':record('note',check_in='2026-10-09'),
            'Notes/closed.md':record('note',status='superseded',check_in='2026-10-12'),
            'Projects/work.md':record('project',area='work',status='active'),
            'Projects/paused.md':record('project',status='paused'),
            'Templates/Test.md':task(status='blocked',check_in='2026-10-12'),
            'Examples/Test.md':task(status='blocked',check_in='2026-10-12'),
        }
        e=Engine(rows)
        self.assertEqual(e.rows('Follow-ups','Blocked tasks'),['Tasks/blocked.md'])
        self.assertEqual(e.rows('Follow-ups','Assigned tasks'),['Tasks/self.md'])
        self.assertEqual(e.rows('Follow-ups','Upcoming check-ins'),['Notes/edge.md','Notes/today.md'])
        self.assertEqual(e.rows('Follow-ups','Projects to review'),['Projects/work.md'])

if __name__=='__main__':unittest.main()
