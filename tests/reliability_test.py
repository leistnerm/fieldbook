"""Regression tests for release review findings and optional human workflows."""
from datetime import date
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import zipfile
import vault_tools_test as fixtures
vt=fixtures.vt

class ReviewFixes(fixtures.VaultToolsTests):
    # Inherit fixtures, not duplicated baseline tests.
    def test_configured_task_defaults_and_explicit_template_precedence(self):
        c=vt.settings(self.root);c['defaults'].update(area='work',status='active',priority='1-high',type='planning');self.put('fieldbook.json',json.dumps(c))
        fm=vt.nb.frontmatter(vt.record_plan(self.root,'Task','A')['text'])
        self.assertEqual((fm['area'],fm['status'],fm['priority'],fm['type']),('work','active','1-high','planning'))
        fm=vt.nb.frontmatter(vt.record_plan(self.root,'Task - Assignment','B')['text'])
        self.assertEqual((fm['area'],fm['type']),('school','assignment'))
        self.assertEqual(vt.nb.frontmatter(vt.record_plan(self.root,'Project - Course','C')['text'])['area'],'school')
        with self.assertRaises(ValueError):vt.record_plan(self.root,'Project - Course','C','work')
        self.put('Templates/Task.md',(self.root/'Templates/Task.md').read_text().replace('status: backlog','status: blocked'))
        self.assertEqual(vt.nb.frontmatter(vt.record_plan(self.root,'Task','Custom')['text'])['status'],'blocked')
    def test_overdue_checkins_and_period_evidence(self):
        self.note('Notes/Yesterday.md',{'tags':['note'],'check_in':'2026-10-11'})
        self.note('People/A.md',{'tags':['person'],'relationship':'report'})
        self.note('Accomplishments/Period.md',{'tags':['accomplishment'],'area':'work','person':'[[A]]','period_start':'2026-09-01','period_end':'2026-10-01'})
        self.note('Accomplishments/Invalid.md',{'tags':['accomplishment'],'area':'work','person':'[[A]]','period_start':'2026-10-02','period_end':'2026-09-01'})
        r=vt.followups(self.root,today=date(2026,10,12))
        self.assertEqual(len(r['overdue_check_ins']),1)
        self.assertEqual(r['manager'][0]['evidence_in_window'],['Accomplishments/Period.md'])
        self.assertEqual(r['manager'][0]['undated_or_invalid_evidence'],['Accomplishments/Invalid.md'])
    def test_unreadable_walk_is_reported_and_identity_actions_refused(self):
        real=vt.os.walk
        def broken(top,*a,**kw):
            kw['onerror'](PermissionError('denied folder'))
            return iter(())
        with patch.object(vt.os,'walk',side_effect=broken):
            self.assertTrue(vt.records(self.root)[1])
            with self.assertRaisesRegex(ValueError,'scan'):vt.intake_plan(self.root,'paste','A',pasted='a')
    def test_intake_literal_blocks_and_commit_time_duplicates(self):
        source='![tracking](https://invalid.test/pixel)\n<img src="https://invalid.test/p">\n![[Private]]\n```\n## forged'
        first=vt.intake_plan(self.root,'paste','A',pasted=source);second=vt.intake_plan(self.root,'paste','B',pasted=source)
        self.assertIn('````text\n'+source+'\n````',first['text'])
        vt.commit_new(self.root,first)
        with self.assertRaisesRegex(ValueError,'already imported'):vt.commit_new(self.root,second)
    def test_message_identity_ignores_transport_headers_and_reports_changed_version(self):
        msg='Message-ID: <abc@example.test>\nSubject: X\nFrom: x@example.test\nContent-Type: text/plain\n\nbody'
        self.put('Attachments/a.eml',msg)
        vt.commit_new(self.root,vt.intake_plan(self.root,'Attachments/a.eml','Email'))
        self.put('Attachments/b.eml','Received: new export\n'+msg)
        with self.assertRaisesRegex(ValueError,'already imported'):vt.intake_plan(self.root,'Attachments/b.eml','Email2')
        self.put('Attachments/b.eml',msg+'changed')
        with self.assertRaisesRegex(ValueError,'changed message version'):vt.intake_plan(self.root,'Attachments/b.eml','Email3')

class Workflows(fixtures.VaultToolsTests):
    def flow(self):return vt.workflows()
    def event(self):return {'provider':'google','instance':'office','calendar_id':'c','event_id':'e','series_id':'s','occurrence_id':'2026-10-12T12:00:00Z','start':{'dateTime':'2026-10-12T13:00:00Z'},'end':{'dateTime':'2026-10-12T14:00:00Z'},'title':'Planning','status':'confirmed','description':'![x](https://invalid.test)','attendees':[]}
    def test_occurrence_identity_rechecked_before_save(self):
        e=self.event();a=self.flow().meeting_plan(vt,self.root,e,'A');b=self.flow().meeting_plan(vt,self.root,e,'B')
        vt.commit_new(self.root,a)
        with self.assertRaisesRegex(ValueError,'Existing meeting'):vt.commit_new(self.root,b)
        moved={**e,'event_id':'new-id','start':{'dateTime':'2026-10-13T14:00:00Z'}}
        self.assertEqual(self.flow().existing_meetings(vt,self.root,moved),[a['path']])
    def test_cancelled_and_master_events_never_create(self):
        for extra in ({'status':'cancelled'},{'requires_occurrence':True}):
            with self.assertRaises(ValueError):self.flow().meeting_plan(vt,self.root,{**self.event(),**extra},'No')
    def test_series_identity_conflicts_and_missing_contacts_refused(self):
        self.note('Meetings/Series/S.md',{'tags':['series'],'calendar_provider':'microsoft'})
        with self.assertRaisesRegex(ValueError,'conflicts'):self.flow().meeting_plan(vt,self.root,self.event(),'A',series='Meetings/Series/S.md')
        with self.assertRaisesRegex(ValueError,'existing selected'):self.flow().meeting_plan(vt,self.root,self.event(),'A',people=['People/Missing.md'])
        self.note('Meetings/Series/Work.md',{'tags':['series'],'area':'work'})
        with self.assertRaisesRegex(ValueError,'area conflicts'):self.flow().meeting_plan(vt,self.root,self.event(),'A',area='school',series='Meetings/Series/Work.md')
        plan=self.flow().meeting_plan(vt,self.root,self.event(),'A',series='Meetings/Series/Work.md')
        self.assertEqual(vt.nb.frontmatter(plan['text'])['area'],'work')
    def test_ics_existing_identity_does_not_depend_on_export_filename(self):
        e={'uid':'a','recurrence_id':'2026-10-12','start':'2026-10-12','title':'A','status':'confirmed'}
        plan=self.flow().meeting_plan(vt,self.root,e,'A');vt.commit_new(self.root,plan)
        self.assertEqual(self.flow().existing_meetings(vt,self.root,{**e,'source':'different.ics'}),[plan['path']])
    def test_explicit_cadence_excludes_group_cancelled_and_future(self):
        self.note('People/A.md',{'tags':['person'],'relationship':'report'})
        self.note('Meetings/Series/S.md',{'tags':['series'],'area':'work','meeting_kind':'one-on-one','person':'[[A]]','cadence_days':7})
        for name,day,kind,status in [('old','2026-09-01','one-on-one','confirmed'),('group','2026-10-11','group','confirmed'),('cancel','2026-10-12','one-on-one','cancelled'),('future','2026-10-15','one-on-one','confirmed')]:
            self.note('Meetings/'+name+'.md',{'tags':['meeting'],'area':'work','series':'[[S]]','date':day,'meeting_kind':kind,'calendar_status':status,'attendees':['[[A]]']})
        r=self.flow().cadence(vt,self.root,date(2026,10,12))[0]
        self.assertEqual(r['last_recorded'],'2026-09-01');self.assertEqual(r['next_recorded'],'2026-10-15');self.assertTrue(r['review_due'])
        self.config(['personal']);self.assertEqual(self.flow().cadence(vt,self.root),[])
    def test_selected_export_preserves_bytes_and_excludes_private_settings(self):
        self.note('Projects/P.md',{'tags':['project']},'[[Secret]]\n[Outside](https://example.test)\n')
        self.note('Notes/Secret.md',{'tags':['note']})
        self.put('Attachments/a.bin',b'\x00\xff')
        plan=self.flow().export_plan(vt,self.root,['Projects/P.md','Attachments/a.bin'])
        self.assertEqual(len(plan['links_to_review']),2)
        target=self.parent/'selected.zip';self.flow().export_save(vt,self.root,plan,target)
        with zipfile.ZipFile(target) as z:
            self.assertEqual(set(z.namelist()),{'Projects/P.md','Attachments/a.bin','EXPORT.json'})
            self.assertEqual(z.read('Attachments/a.bin'),b'\x00\xff')
        with self.assertRaises(FileExistsError):self.flow().export_save(vt,self.root,plan,target)
        for path in ['fieldbook_core/google.json','Attachments/../fieldbook.json']:
            with self.assertRaises(ValueError):self.flow().export_plan(vt,self.root,[path])
    def test_export_stale_sources_and_inside_destination_refused(self):
        self.note('Notes/A.md',{'tags':['note']});plan=self.flow().export_plan(vt,self.root,['Notes/A.md'])
        with self.assertRaises(ValueError):self.flow().export_save(vt,self.root,plan,self.root/'a.zip')
        self.put('Notes/A.md','changed')
        with self.assertRaisesRegex(ValueError,'changed'):self.flow().export_save(vt,self.root,plan,self.parent/'a.zip')

# Do not rerun inherited baseline tests; keep the reusable fixture helpers.
for cls in (ReviewFixes,Workflows):
    for name in dir(fixtures.VaultToolsTests):
        if name.startswith('test_') and name not in cls.__dict__:setattr(cls,name,None)

class PreflightTests(unittest.TestCase):
    def test_temp_failures_are_actionable_and_low_space_is_refused(self):
        from types import SimpleNamespace
        engine=vt.backup.engine
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp)/'vault';root.mkdir()
            with patch.object(engine.shutil,'disk_usage',return_value=SimpleNamespace(free=1)):
                with self.assertRaisesRegex(ValueError,'insufficient free space'):engine.preflight(root,Path(temp)/'backups')
            with patch.object(engine.tempfile,'TemporaryDirectory',side_effect=PermissionError('denied')):
                with self.assertRaisesRegex(ValueError,'create temporary folder'):engine.preflight(root,Path(temp)/'backups')
            self.assertEqual(list(root.iterdir()),[])
    def test_menu_grouping_is_offline_and_cancellable(self):
        configure=vt.load('review_configure',vt.HERE/'configure.py')
        with tempfile.TemporaryDirectory() as temp:
            # Help/exit does not load credentials, write or contact any integration.
            class Session:
                root=Path(temp)
                config={}
                def unchanged(self):return True
            ui=configure.Wizard(Session(),ask=iter(['5','0']).__next__ if False else lambda _:next(answers),say=lambda _:None)
            answers=iter(['5','0'])
            with patch.object(ui,'finish',return_value=True):self.assertTrue(ui.menu())

class CliCaptureTests(fixtures.VaultToolsTests):
    def test_ics_picker_saves_one_occurrence_without_creating_attendees(self):
        self.put('Attachments/meeting.ics','BEGIN:VCALENDAR\r\nVERSION:2.0\r\nBEGIN:VEVENT\r\nUID:event-a\r\nDTSTART:20261012T120000Z\r\nDTEND:20261012T130000Z\r\nSUMMARY:Planning\r\nATTENDEE;CN=Unknown:mailto:unknown@example.test\r\nEND:VEVENT\r\nEND:VCALENDAR\r\n')
        answers=iter(['1','Attachments/meeting.ics','1','','work','','','create']);output=[]
        vt.workflows().calendar_ui(vt,self.root,lambda _:next(answers),output.append)
        rows,warnings=vt.records(self.root);meetings=[r for r in rows if vt.tagged(r,'meeting')]
        self.assertEqual(len(meetings),1);self.assertFalse(meetings[0]['fm']['attendees']);self.assertEqual(list((self.root/'People').iterdir()),[])
        answers=iter(['1','Attachments/meeting.ics','1'])
        vt.workflows().calendar_ui(vt,self.root,lambda _:next(answers),output.append)
        self.assertIn('Open existing meeting','\n'.join(output));self.assertEqual(len(list((self.root/'Meetings').rglob('*.md'))),1)
    def test_goal_and_agreement_templates_are_shared(self):
        self.config([])
        for template,tag in [('Note - Goal','goal'),('Item - Agreement','agreement')]:
            plan=vt.record_plan(self.root,template,'Optional');self.assertIn(tag,vt.nb.frontmatter(plan['text'])['tags'])
    def test_custom_content_and_hidden_backups_have_consistent_scan_rules(self):
        self.note('Custom/Real.md',{'tags':['person']});self.note('.fieldbook/config-backups/old/People/Hidden.md',{'tags':['person']})
        paths=[r['path'] for r in vt.records(self.root)[0]]
        self.assertIn('Custom/Real.md',paths);self.assertNotIn('.fieldbook/config-backups/old/People/Hidden.md',paths)
    def test_cadence_config_preserves_original_and_confirms_report(self):
        self.note('People/A.md',{'tags':['person'],'relationship':'report'})
        self.note('Meetings/Series/S.md',{'tags':['series'],'area':'work'},'## My custom agenda\nKeep this\n')
        original=(self.root/'Meetings/Series/S.md').read_bytes();answers=iter(['y','1','1','14','apply'])
        vt.workflows().cadence_ui(vt,self.root,lambda _:next(answers),lambda _:None)
        self.assertIn('Keep this',(self.root/'Meetings/Series/S.md').read_text())
        self.assertEqual(vt.nb.frontmatter((self.root/'Meetings/Series/S.md').read_text())['cadence_days'],'14')
        self.assertEqual(next((self.root/'.fieldbook/config-backups').rglob('S.md')).read_bytes(),original)

for name in dir(fixtures.VaultToolsTests):
    if name.startswith('test_') and name not in CliCaptureTests.__dict__:setattr(CliCaptureTests,name,None)

class BootstrapTests(unittest.TestCase):
    def test_check_is_offline_and_reports_missing_environment(self):
        bootstrap=vt.load('review_bootstrap',vt.HERE.parent/'fieldbook.py')
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);(root/'fieldbook_core').mkdir();(root/'fieldbook_core/requirements.txt').write_text('PyYAML==6.0.3\n')
            with patch.object(bootstrap,'ROOT',root),patch.object(bootstrap.subprocess,'run') as run,patch.object(bootstrap.venv.EnvBuilder,'create') as create:
                self.assertEqual(bootstrap.main(['--check']),1);run.assert_not_called();create.assert_not_called()
            self.assertFalse((root/'fieldbook_core/.venv').exists())
    def test_launcher_reuses_matching_dependencies_and_forwards_cli(self):
        bootstrap=vt.load('review_bootstrap',vt.HERE.parent/'fieldbook.py')
        from types import SimpleNamespace
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);env=root/'fieldbook_core/.venv';python=env/('Scripts/python.exe' if bootstrap.os.name=='nt' else 'bin/python');python.parent.mkdir(parents=True);python.touch()
            req=root/'fieldbook_core/requirements.txt';req.write_text('PyYAML==6.0.3\n')
            (env/'fieldbook-dependencies.json').write_text(json.dumps({'core':vt.sha(req.read_bytes())}))
            with patch.object(bootstrap,'ROOT',root),patch.object(bootstrap.subprocess,'run',return_value=SimpleNamespace(returncode=0)) as run,patch.object(bootstrap.subprocess,'call',return_value=0) as call:
                self.assertEqual(bootstrap.main(['--','--check']),0)
                self.assertFalse(any('install' in c.args[0] for c in run.call_args_list));self.assertEqual(call.call_args.args[0][-1],'--check')

class AddedViewsTests(unittest.TestCase):
    def test_overdue_and_distinct_agreement_dates(self):
        import views_test as views
        import yaml
        root=vt.HERE.parent
        follow=yaml.safe_load((root/'Views/Follow-ups.base').read_text())
        dates=yaml.safe_load((root/'Views/Upcoming dates.base').read_text())
        # Use the shipped expressions and the existing small Base interpreter.
        engine=views.Engine({'Notes/Past.md':{'check_in':'2026-10-09'},'Notes/Today.md':{'check_in':'2026-10-10'},'Items/Agreement.md':{'tags':['item'],'renewal_date':'2026-12-01','cancellation_notice_by':'2026-11-01','expiration_date':'2026-12-31'}})
        selected=next(v for v in follow['views'] if v['name']=='Overdue check-ins')
        for path,wanted in [('Notes/Past.md',True),('Notes/Today.md',False)]:
            env=engine.env(engine.files[path],follow)
            self.assertEqual(all(engine.expression(e,env) for e in selected['filters']['and']),wanted)
        for name,field in [('Agreement renewals','renewal_date'),('Cancellation notice deadlines','cancellation_notice_by'),('Agreement expirations','expiration_date')]:
            view=next(v for v in dates['views'] if v['name']==name)
            self.assertEqual(view['sort'][0]['property'],field)
            env=engine.env(engine.files['Items/Agreement.md'],dates)
            self.assertTrue(all(engine.expression(e,env) for e in view['filters']['and']))
