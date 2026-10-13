"""1.0 workflows: first use, coherent review and read-only field conflict previews."""
import copy
from datetime import date
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import vault_tools_test as fixtures
vt=fixtures.vt
sync=vt.load('sync100',vt.HERE.parent/'fieldbook_core/scripts/sync_preview.py')

class SyncTests(unittest.TestCase):
    def setUp(self):
        self.source={'provider':'jira','instance':'office','id':'APP-1'}
        self.fm={'tags':['task'],'jira':'APP-1','jira_instance':'office','status':'backlog','due':'2026-10-13'}
        self.key=sync.source_key('jira','office','APP-1')
    def preview(self,values,**options):return sync.compare(self.fm,{'source':self.source,'proposed':values,**options})
    def baseline(self,values):self.fm['sync_baselines']={self.key:{'source':self.source,'fields':values}}
    def test_first_sync_and_unchanged_are_distinct(self):
        rows=self.preview({'status':'active','due':'2026-10-13'})['fields']
        self.assertEqual([r['classification'] for r in rows],['first_sync','unchanged'])
    def test_three_way_remote_local_and_conflict(self):
        self.baseline({'status':'backlog','due':'2026-10-13'})
        self.assertEqual(self.preview({'status':'active'})['fields'][0]['classification'],'remote_change')
        self.fm['status']='blocked'
        self.assertEqual(self.preview({'status':'backlog'})['fields'][0]['classification'],'local_override')
        self.assertEqual(self.preview({'status':'active'})['fields'][0]['classification'],'conflict')
    def test_null_dates_never_clear_and_planning_fields_stay_local(self):
        rows=self.preview({'due':None,'priority':'1-high','scheduled':'2026-10-15','title':'Renamed'})['fields']
        self.assertEqual([r['classification'] for r in rows],['unavailable','protected','protected','protected'])
        self.assertEqual(self.preview({'priority':'1-high'},explicit_fields=['priority'])['fields'][0]['classification'],'first_sync')
    def test_invalid_dates_states_and_closure_evidence(self):
        for field,value in [('due','2026-02-30'),('status','Resolved')]:self.assertEqual(self.preview({field:value})['fields'][0]['classification'],'invalid')
        self.assertEqual(self.preview({'status':'done'})['fields'][0]['classification'],'needs_review')
        self.assertEqual(self.preview({'status':'done','completedDate':'not-a-date'})['fields'][0]['classification'],'needs_review')
        self.assertEqual(self.preview({'completedDate':'2026-10-12'})['fields'][0]['classification'],'needs_review')
    def test_final_reviews_and_recurrence_are_protected(self):
        self.fm.update(tags=['review'],status='final')
        self.assertEqual(self.preview({'completedDate':'2026-10-12'})['fields'][0]['classification'],'protected')
        self.fm.update(tags=['task'],status='active',recurrence='user recurrence')
        self.assertEqual(self.preview({'due':'2026-10-14'})['fields'][0]['classification'],'protected')
    def test_source_conflicts_identity_and_invalid_payload(self):
        self.fm['github']='a/b#1';self.baseline({'status':'backlog'})
        self.assertEqual(self.preview({'status':'active'})['fields'][0]['classification'],'source_conflict')
        for payload in [{'source':{**self.source,'id':'APP-2'},'proposed':{'status':'active'}},{'source':self.source,'proposed':{'body':'overwrite'}},{'source':self.source,'proposed':{'status':['bad']}},{'source':self.source,'proposed':{'due':'x'*65536}}]:
            with self.assertRaises(ValueError):sync.compare(self.fm,payload)
    def test_other_providers_have_exact_identities(self):
        cases=[({'provider':'canvas','instance':'school','id':'12/77'},{'tags':['task'],'canvas_instance':'school','canvas_course_id':'12','canvas_assignment_id':'77'},'due','2026-10-13'),
               ({'provider':'google','instance':'office','id':json.dumps(['cal','series','occ'],separators=(',',':'))},{'tags':['meeting'],'calendar_provider':'google','calendar_instance':'office','calendar_id':'cal','calendar_series_id':'series','calendar_occurrence_id':'occ'},'calendar_status','cancelled'),
               ({'provider':'ics','instance':'local export','id':json.dumps(['uid',''],separators=(',',':'))},{'tags':['meeting'],'calendar_uid':'uid'},'location','Room A')]
        for source,fm,key,value in cases:self.assertEqual(sync.compare(fm,{'source':source,'proposed':{key:value}})['fields'][0]['classification'],'first_sync')

    def test_calendar_identity_cannot_collide_on_separator_characters(self):
        fm={'tags':['meeting'],'calendar_provider':'google','calendar_instance':'office','calendar_id':'a|b','calendar_series_id':'c','calendar_occurrence_id':'d'}
        wrong={'provider':'google','instance':'office','id':json.dumps(['a','b|c','d'],separators=(',',':'))}
        self.assertFalse(sync.identity_matches(fm,wrong))
        right={**wrong,'id':json.dumps(['a|b','c','d'],separators=(',',':'))}
        self.assertTrue(sync.identity_matches(fm,right))
        compact=sync.compare(fm,{'source':right,'proposed':{'location':'A'}})
        spaced=sync.compare(fm,{'source':{**right,'id':json.dumps(['a|b','c','d'])},'proposed':{'location':'A'}})
        self.assertEqual(compact['baseline_key'],spaced['baseline_key'])

class JourneyTests(fixtures.VaultToolsTests):
    def review(self,kind='daily',area=''):return vt.journeys().review(vt,self.root,kind,area,date(2026,10,12))
    def test_daily_and_weekly_date_meanings_and_scope(self):
        self.note('Tasks/Overdue.md',{'tags':['task'],'area':'work','status':'active','due':'2026-10-11','scheduled':'2026-10-12'})
        self.note('Tasks/Later.md',{'tags':['task'],'area':'school','status':'backlog','due':'2026-10-16'})
        self.note('Items/Renew.md',{'tags':['item'],'cancellation_notice_by':'2026-10-11','renewal_date':'2026-10-16'})
        self.note('Tasks/Recurring.md',{'tags':['task'],'recurrence':'rrule','due':'2026-10-11'})
        before=self.snapshot();daily=self.review();weekly=self.review('weekly')
        self.assertEqual(len(daily['sections']['overdue_deadlines']),1);self.assertEqual(len(daily['sections']['planned_work']),1)
        self.assertEqual(len(daily['sections']['deadlines_in_window']),0);self.assertEqual(len(weekly['sections']['deadlines_in_window']),1)
        self.assertEqual({r['meaning'] for r in weekly['sections']['other_dates']},{'cancellation_notice_by','renewal_date'})
        self.assertIn('Tasks/Recurring.md',daily['recurring_tasks_use_TaskNotes'])
        self.assertEqual(self.review('weekly','work')['sections']['deadlines_in_window'],[])
        self.assertEqual(before,self.snapshot())
    def test_disabled_setup_notes_stay_visible_and_private_inbox_is_scoped(self):
        self.config(['work']);self.note('Tasks/School.md',{'tags':['task'],'area':'school','due':'2026-10-12'})
        self.note('Tasks/Unknown.md',{'tags':['task'],'due':'2026-10-12'});self.put('Inbox.md','Private mixed capture')
        self.assertEqual(len(self.review()['sections']['deadlines_in_window']),2)
        scoped=self.review(area='work');self.assertNotIn('text',scoped['inbox']);self.assertIn('Tasks/Unknown.md',scoped['unassigned_area_to_review'])
    def test_completions_and_calendar_cancellations(self):
        self.note('Tasks/Done.md',{'tags':['task'],'status':'done','completedDate':'2026-10-10'})
        self.note('Meetings/Cancelled.md',{'tags':['meeting'],'date':'2026-10-12','calendar_status':'cancelled'})
        self.note('Meetings/Future.md',{'tags':['meeting'],'date':'2026-10-16'})
        self.assertEqual(self.review()['sections']['meetings'],[])
        self.assertEqual(len(self.review('weekly')['sections']['meetings']),1)
        self.assertEqual(len(self.review('weekly')['sections']['recent_completions']),1)
    def test_review_ui_cancels_without_writes_and_snapshot_is_literal(self):
        before=self.snapshot();answers=iter(['','','',''])
        vt.journeys().review_ui(vt,self.root,'daily',lambda _:next(answers),lambda _:None)
        self.assertEqual(before,self.snapshot())
        self.put('Inbox.md','![pixel](https://invalid.test/x)\n![[Private]]')
        answers=iter(['','','','y','create'])
        vt.journeys().review_ui(vt,self.root,'weekly',lambda _:next(answers),lambda _:None)
        saved=next((self.root/'Reports').glob('Weekly review*.md')).read_text();self.assertIn('```text',saved)
    def test_self_record_resume_conflicts_and_preservation(self):
        self.note('People/Me.md',{'tags':['person'],'relationship':'','aliases':['Myself']},'## Custom\nKeep this\n')
        answers=iter(['1','1','apply']);vt.journeys().self_record(vt,self.root,lambda _:next(answers),lambda _:None)
        self.assertIn('Keep this',(self.root/'People/Me.md').read_text());self.assertEqual(len(list((self.root/'.fieldbook/config-backups').rglob('Me.md'))),1)
        before=self.snapshot();vt.journeys().self_record(vt,self.root,lambda _:self.fail('must not prompt again'),lambda _:None);self.assertEqual(before,self.snapshot())
    def test_duplicate_self_creation_and_preview_staleness(self):
        plan=vt.record_plan(self.root,'Person','Me');plan['text']=vt.workflows().metadata(plan['text'],{'relationship':'self'});plan['self_record']=True
        self.note('People/Existing.md',{'tags':['person'],'relationship':'self'})
        with self.assertRaises(ValueError):vt.commit_new(self.root,plan)
    def test_notebook_sync_preview_uses_current_hash_and_shared_identity_scan(self):
        self.note('Tasks/A.md',{'tags':['task'],'jira':'APP-1','jira_instance':'office','status':'backlog'})
        vault=vt.nb.Vault(self.root);sha=vt.sha((self.root/'Tasks/A.md').read_bytes());before=self.snapshot()
        request={'path':'Tasks/A.md','expected':sha,'sync':{'source':{'provider':'jira','instance':'office','id':'APP-1'},'proposed':{'status':'active'}}}
        result=vault.preview(request);self.assertEqual(result['fields'][0]['classification'],'first_sync');self.assertEqual(before,self.snapshot())
        self.note('Projects/Also.md',{'tags':['project'],'jira':'APP-1','jira_instance':'office'})
        self.assertEqual(vault.preview(request)['fields'][0]['classification'],'identity_conflict')
        with self.assertRaisesRegex(ValueError,'Conflict'):vault.preview({**request,'expected':'stale'})

for name in dir(fixtures.VaultToolsTests):
    if name.startswith('test_') and name not in JourneyTests.__dict__:setattr(JourneyTests,name,None)

import configure_wizard_test as config_fixtures
class OnboardingTests(config_fixtures.WizardTests):
    def setup_templates(self):
        for name in ('Templates/Person.md','Templates/Task.md','tools/record-templates.json'):
            self.put(name,(vt.HERE.parent/name).read_text())
    def test_guided_save_self_first_task_and_repeat(self):
        self.setup_templates();answers=iter(['','people-manager','','','none','active','1-high','task','save','2','Me','create','y','First task','create'])
        ui=config_fixtures.wizard.Wizard(config_fixtures.wizard.Session(self.root),lambda _:next(answers),lambda _:None)
        ui.onboard()
        c=json.loads((self.root/'fieldbook.json').read_text());self.assertEqual(c['workRole'],'people-manager');self.assertEqual(c['defaults'],{'area':'','status':'active','priority':'1-high','type':'task'})
        self.assertEqual(vt.nb.frontmatter((self.root/'People/Me.md').read_text())['relationship'],'self')
        task=vt.nb.frontmatter((self.root/'Tasks/First task.md').read_text());self.assertEqual(task['status'],'active');self.assertEqual(task['priority'],'1-high')
        before=self.snapshot();answers=iter(['','','','','','','','','save',''])
        ui=config_fixtures.wizard.Wizard(config_fixtures.wizard.Session(self.root),lambda _:next(answers),lambda _:None);ui.onboard()
        self.assertEqual(before,self.snapshot())
    def test_cancel_onboarding_does_not_save_or_make_people(self):
        self.setup_templates();before=self.snapshot();answers=iter(['school','','active','2-normal','study',''])
        ui=config_fixtures.wizard.Wizard(config_fixtures.wizard.Session(self.root),lambda _:next(answers),lambda _:None);ui.onboard()
        self.assertEqual(before,self.snapshot())

for name in dir(config_fixtures.WizardTests):
    if name.startswith('test_') and name not in OnboardingTests.__dict__:setattr(OnboardingTests,name,None)

class DefaultPreservationTests(config_fixtures.WizardTests):
    def test_unchanged_custom_defaults_survive_setup_save(self):
        config=json.loads((self.root/'fieldbook.json').read_text())
        config['defaults'].update(status='custom-status',priority='custom-priority',type='Custom Type',area='')
        self.put('fieldbook.json',json.dumps(config))
        session=config_fixtures.wizard.Session(self.root);session.config['workRole']='people-manager'
        session.commit()
        self.assertEqual(json.loads((self.root/'fieldbook.json').read_text())['defaults'],config['defaults'])

for name in dir(config_fixtures.WizardTests):
    if name.startswith('test_') and name not in DefaultPreservationTests.__dict__:setattr(DefaultPreservationTests,name,None)
