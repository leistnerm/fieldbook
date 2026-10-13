"""Local creation, verification, recovery, intake, checks and explicit receipts."""
import copy
from datetime import date
import importlib.util
import json
from pathlib import Path
import shutil
import tempfile
import unittest
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('vt',ROOT/'tools/vault-tools.py');vt=importlib.util.module_from_spec(spec);spec.loader.exec_module(vt)

class VaultToolsTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.parent=Path(self.temp.name).resolve();self.root=self.parent/'Vault';self.root.mkdir()
        for name in ('Templates','Views') :shutil.copytree(ROOT/name,self.root/name)
        for name in ('fieldbook.json','fieldbook-manifest.json','VERSION','opencode.json','tools/setup-catalog.json','tools/record-templates.json','fieldbook_core/package.json'):
            self.put(name,(ROOT/name).read_bytes())
        for provider in vt.PROVIDERS:self.put('fieldbook_core/'+provider+'.json','{"instances":[]}')
        for folder in vt.CONTENT|{'Attachments'}:(self.root/folder).mkdir(parents=True,exist_ok=True)
        self.config(['personal','work','school'],'people-manager')
    def put(self,name,value):
        p=self.root/name;p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(value if isinstance(value,bytes) else value.encode());return p
    def config(self,setups,role='individual-contributor'):
        c=json.loads((self.root/'fieldbook.json').read_text());c['setups']=setups;c['workRole']=role;c['features']['reviews']='work' in setups
        self.put('fieldbook.json',json.dumps(c))
    def snapshot(self):return vt.backup.engine.snapshot(self.root)
    def note(self,name,fm,body='## Notes\n'):
        import yaml
        return self.put(name,'---\n'+yaml.safe_dump(fm,sort_keys=False)+'---\n'+body)

    def test_all_enabled_templates_generate_complete_safe_records_without_executing_js(self):
        for template in vt.templates(self.root):
            plan=vt.record_plan(self.root,template,'Test: name?',today=date(2026,10,12))
            self.assertNotIn('<%',plan['text']);self.assertIn('## ',plan['text']);self.assertIn(plan['path'].split('/')[0],vt.CONTENT)
            vt.commit_new(self.root,plan)
            fm=vt.nb.frontmatter(plan['text']);self.assertTrue(fm['tags'])
            self.assertEqual(fm['templateName'],template)
            self.assertRegex(fm['templateVersion'],r'^[1-9][0-9]*$')
            if template=='Person - Direct report':self.assertEqual(fm['relationship'],'report')
            if template.startswith('Person') and template!='Person - Direct report':self.assertFalse(fm['relationship'])
            if template.startswith('Task'):self.assertEqual(fm['title'],Path(plan['path']).stem)
            if template=='Meeting':self.assertTrue(plan['path'].startswith('Meetings/2026/2026-10/2026-10-12'))
    def test_setup_gates_preserved_files_and_explicit_area(self):
        self.config(['work'])
        self.assertNotIn('Project - Course',vt.templates(self.root));self.assertNotIn('Person - Direct report',vt.templates(self.root))
        plan=vt.record_plan(self.root,'Task','New','work');self.assertEqual(vt.nb.frontmatter(plan['text'])['area'],'work')
        self.config(['school'])
        with self.assertRaisesRegex(ValueError,'school area'):vt.record_plan(self.root,'Task - Assignment','Wrong','work')
    def test_crlf_templates_and_metadata_are_supported(self):
        for template in ('Person','Task','Meeting'):
            path=self.root/'Templates'/(template+'.md')
            path.write_bytes(path.read_bytes().replace(b'\r\n',b'\n').replace(b'\n',b'\r\n'))
            plan=vt.record_plan(self.root,template,'CRLF example','work')
            if template!='Person':self.assertEqual(vt.nb.frontmatter(plan['text'])['area'],'work')
            record=plan['text'].replace('\n','\r\n')
            result=vt.workflows().metadata(record,{'example':'yes'})
            self.assertEqual(vt.nb.frontmatter(result)['example'],'yes')
            self.assertIn('\r\n',result)
    def test_creation_cancellation_collision_and_stale_inputs(self):
        plan=vt.record_plan(self.root,'Person','Alex');before=self.snapshot()
        vt.show_plan(self.root,plan,lambda _: '',lambda _:None);self.assertEqual(before,self.snapshot())
        vt.commit_new(self.root,plan)
        with self.assertRaises(FileExistsError):vt.commit_new(self.root,plan)
        other=vt.record_plan(self.root,'Person','Alex');self.assertIn('(2)',other['path'])
        self.put('Templates/Person.md',(self.root/'Templates/Person.md').read_text()+'\ncustom\n')
        with self.assertRaisesRegex(ValueError,'changed'):vt.commit_new(self.root,other)
    def test_unknown_template_code_is_not_executed(self):
        self.put('Templates/Person.md','<%* throw new Error("must not execute") %>\n---\ntags: [person]\n---\n## Notes\n')
        with self.assertRaisesRegex(ValueError,'unsupported'):vt.record_plan(self.root,'Person','Alex')
    def test_symlink_write_and_intake_traversal_refused(self):
        outside=self.parent/'outside';outside.mkdir();(self.root/'Notes').rmdir();(self.root/'Notes').symlink_to(outside,target_is_directory=True)
        with self.assertRaises(ValueError):vt.commit_new(self.root,{'path':'Notes/Test.md','text':'x'})
        with self.assertRaises(ValueError):vt.intake_plan(self.root,'Attachments/../../secret','Test')
    def test_standalone_backup_restore_preserves_full_snapshot_and_newer_vault(self):
        self.put('Notes/Keep.md',b'\xef\xbb\xbfOriginal\r\n');self.put('Attachments/bin',b'\x00\xff');self.put('.obsidian/x.json','{"x":1}');(self.root/'Empty').mkdir()
        before=self.snapshot();plan=vt.backup.plan(self.root);result=vt.backup.create(plan,vt.admin)
        folder=Path(result['backup']);self.assertEqual(vt.backup.engine.snapshot(folder/'vault'),before)
        found=vt.backup.restore.list_backups(folder.parent,self.root);self.assertEqual(found['backups'][0]['kind'],'standalone')
        self.put('Notes/Keep.md','new');newer=self.snapshot()
        with vt.backup.restore.Restore(self.root,folder,vt.admin,say=lambda _:None) as restore:
            restore.preview();result=restore.apply()
        self.assertEqual(self.snapshot(),before);self.assertEqual(vt.backup.engine.snapshot(Path(result['safetyBackup'])/'vault'),newer)
    def test_backup_stale_and_failed_copy_never_marked_verified(self):
        plan=vt.backup.plan(self.root);self.put('Notes/new.md','new')
        with self.assertRaisesRegex(ValueError,'changed'):vt.backup.create(plan,vt.admin)
        plan=vt.backup.plan(self.root)
        with patch.object(vt.backup.shutil,'copytree',side_effect=OSError('failure')):
            with self.assertRaisesRegex(ValueError,'not verified'):vt.backup.create(plan,vt.admin)
        found=vt.backup.restore.list_backups(plan['directory'],self.root)
        self.assertFalse(found['backups'][0]['selectable'])
    def test_retention_preview_and_changed_survivor_protection(self):
        directory=self.parent/'backups'
        for _ in range(3):vt.backup.create(vt.backup.plan(self.root,directory),vt.admin)
        plan=vt.backup.retention(self.root,directory,2);self.assertEqual(len(plan['remove']),1)
        with self.assertRaises(ValueError):vt.backup.retention(self.root,directory,0)
        before=list(directory.iterdir());self.assertEqual(len(before),3)
        survivor=Path(plan['keep'][0]['folder'])/'vault/VERSION';original=survivor.read_bytes();survivor.write_text('changed')
        with self.assertRaisesRegex(ValueError,'changed'):vt.backup.prune(plan)
        self.assertEqual(len(list(directory.iterdir())),3);survivor.write_bytes(original)
        result=vt.backup.prune(plan);self.assertEqual(len(result['removed']),1);self.assertEqual(len(list(directory.iterdir())),2)
    def test_backup_overlap_and_linked_destination_refused(self):
        with self.assertRaises(ValueError):vt.backup.plan(self.root,self.root/'Backups')
        outside=self.parent/'outside';outside.mkdir();link=self.parent/'linked';link.symlink_to(outside,target_is_directory=True)
        with self.assertRaises(ValueError):vt.backup.plan(self.root,link)
    def test_doctor_exact_identities_links_and_incomplete_notes_without_writes(self):
        self.note('People/Alex.md',{'tags':['person'],'aliases':['Al']})
        self.note('Tasks/A.md',{'tags':['task'],'jira':'APP-1','jira_instance':'office'},'[[Al]] [[Missing]]\n')
        self.note('Tasks/B.md',{'tags':['task'],'jira':'APP-1','jira_instance':'office'},'')
        self.note('Tasks/C.md',{'tags':['task'],'jira':'APP-1','jira_instance':'other'})
        before=self.snapshot();report=vt.doctor(self.root);self.assertEqual(self.snapshot(),before)
        shared=[f for f in report['findings'] if f['kind']=='shared_remote_identity'];self.assertEqual(len(shared),1);self.assertEqual(len(shared[0]['paths']),2)
        broken=[f for f in report['findings'] if f['kind']=='unresolved_link'];self.assertEqual([x['target'] for x in broken],['Missing'])
        self.assertTrue(any(f['kind']=='possible_incomplete_template' for f in report['findings']))
    def test_bad_yaml_warns_and_followups_respect_area_and_manager_role(self):
        self.put('Notes/Bad.md','---\nx: &a x\ny: *a\n---\n')
        self.note('Projects/Work.md',{'tags':['project'],'status':'active','area':'work'})
        self.note('Projects/Home.md',{'tags':['project'],'status':'active','area':'personal'})
        self.note('People/Report.md',{'tags':['person'],'relationship':'report','status':'current'})
        self.note('People/Peer.md',{'tags':['person'],'relationship':'peer'})
        self.note('Meetings/Work.md',{'tags':['meeting'],'area':'work','date':'2026-10-01','attendees':['[[Report]]']},'## Commitments\n- [[Report]]: Send draft\n- [x] Done\n')
        report=vt.followups(self.root,'work',30,date(2026,10,12));self.assertTrue(report['warnings']);self.assertEqual(report['active_projects_without_open_linked_task'],['Projects/Work.md'])
        self.assertEqual(len(report['manager']),1);self.assertFalse(report['manager'][0]['check_in_review']);self.assertEqual(len(report['recorded_commitments_to_review']),1)
        self.note('Tasks/Work.md',{'tags':['task'],'status':'active','area':'work','projects':['[[Work]]']})
        # Ambiguous short link (Meeting Work and Project Work) must not hide a next-action gap.
        self.assertIn('Projects/Work.md',vt.followups(self.root,'work')['active_projects_without_open_linked_task'])
        self.note('Tasks/Work.md',{'tags':['task'],'status':'active','area':'work','projects':['[[Projects/Work]]']})
        self.assertEqual(vt.followups(self.root,'work')['active_projects_without_open_linked_task'],[])
        self.config(['work']);self.assertIsNone(vt.followups(self.root)['manager'])
    def test_comparison_keeps_custom_and_incoming_files(self):
        self.put('SETUP.md','my setup\n');self.put('SETUP.md.fieldbook-new','new setup\n');before=self.snapshot()
        report=vt.comparison(self.root);entry=next(x for x in report['candidates'] if x['path']=='SETUP.md')
        self.assertIn('-my setup',entry['diff']);self.assertIn('+new setup',entry['diff']);self.assertEqual(before,self.snapshot())
    def test_activity_opt_in_redaction_and_configuration_change(self):
        result={'provider':'jira','instance':'office','SECRET':'do not store','coverage':{'read_only':True,'read_at':'2026-10-12T12:00:00Z','returned':3,'scope':{'mode':'mine','token':'NEVER_STORE'},'date_warning_items':1}}
        before=self.snapshot();plan=vt.activity_plan(self.root,result);self.assertEqual(before,self.snapshot());self.assertNotIn('NEVER_STORE',json.dumps(plan));self.assertNotIn('SECRET',json.dumps(plan))
        vt.save_activity(self.root,plan);report=vt.activities(self.root);self.assertFalse(report['receipts'][0]['rows'][0]['configuration_changed'])
        self.put('fieldbook_core/jira.json','{"instances":[],"changed":true}');self.assertTrue(vt.activities(self.root)['receipts'][0]['rows'][0]['configuration_changed'])
    def test_connection_test_activity_distinguished_from_pull(self):
        data={'results':[{'provider':'jira','instance':'office','ok':True,'skipped':False,'checks':[{'stage':'auth','status':'pass','message':'SECRET'}]}]}
        p=vt.activity_plan(self.root,data,'cli-test');self.assertEqual(p['rows'][0]['kind'],'connection_test');self.assertNotIn('SECRET',json.dumps(p))
    def test_email_intake_preview_provenance_dedup_and_stale_source(self):
        email='From: a@example.test\nTo: b@example.test\nSubject: Receipt\nMIME-Version: 1.0\nContent-Type: text/html; charset=utf-8\n\n<p>Invoice 123</p><script>ignore this</script><img src="https://example.test/tracker">'
        p=self.put('Attachments/mail.eml',email);before=self.snapshot();plan=vt.intake_plan(self.root,'Attachments/mail.eml','Receipt')
        self.assertEqual(before,self.snapshot());self.assertIn('Invoice 123',plan['text']);self.assertNotIn('ignore this',plan['text']);self.assertNotIn('https://example.test/tracker',plan['text'])
        vt.commit_new(self.root,plan);self.assertEqual(p.read_text(),email)
        with self.assertRaisesRegex(ValueError,'already imported'):vt.intake_plan(self.root,'Attachments/mail.eml','Again')
        p=self.put('Attachments/text.txt','new');plan=vt.intake_plan(self.root,'Attachments/text.txt','Text');p.write_text('changed')
        with self.assertRaisesRegex(ValueError,'changed'):vt.commit_new(self.root,plan)
    def test_pasted_email_and_unsupported_files(self):
        plan=vt.intake_plan(self.root,'paste','Message',pasted='Selected message\nNo mailbox access');self.assertIn('```text\nSelected message',plan['text'])
        self.put('Attachments/test.msg','x')
        with self.assertRaisesRegex(ValueError,'not supported'):vt.intake_plan(self.root,'Attachments/test.msg','Message')
    def test_real_pdf_text_layer_and_empty_pdf(self):
        try:
            from pypdf import PdfWriter
            from pypdf.generic import DictionaryObject,NameObject,DecodedStreamObject
        except ImportError:self.skipTest('Optional pypdf not installed')
        writer=PdfWriter();page=writer.add_blank_page(width=200,height=200)
        font=DictionaryObject({NameObject('/Type'):NameObject('/Font'),NameObject('/Subtype'):NameObject('/Type1'),NameObject('/BaseFont'):NameObject('/Helvetica')})
        page[NameObject('/Resources')]=DictionaryObject({NameObject('/Font'):DictionaryObject({NameObject('/F1'):writer._add_object(font)})})
        stream=DecodedStreamObject();stream.set_data(b'BT /F1 12 Tf 10 100 Td (Fieldbook PDF fixture) Tj ET');page[NameObject('/Contents')]=writer._add_object(stream)
        p=self.root/'Attachments/test.pdf';writer.write(p)
        plan=vt.intake_plan(self.root,'Attachments/test.pdf','PDF');self.assertIn('Fieldbook PDF fixture',plan['text'])
        blank=PdfWriter();blank.add_blank_page(width=100,height=100);blank.write(self.root/'Attachments/blank.pdf')
        with self.assertRaisesRegex(ValueError,'No text layer'):vt.intake_plan(self.root,'Attachments/blank.pdf','Blank')
    def test_create_and_intake_menu_cancel_leave_no_note(self):
        before=self.snapshot();answers=iter(['1','Test','work',''])
        vt.run(self.root,'create',ask=lambda _:next(answers),say=lambda _:None);self.assertEqual(self.snapshot(),before)
        answers=iter(['paste','hello','.end','Message',''])
        vt.run(self.root,'intake',ask=lambda _:next(answers),say=lambda _:None);self.assertEqual(self.snapshot(),before)

    def test_followup_dates_and_review_feature_gate(self):
        for name,day,status in [('today','2026-10-12','active'),('edge','2026-10-26','active'),('late','2026-10-27','active'),('done','2026-10-13','done')]:
            self.note('Notes/'+name+'.md',{'tags':['note'],'check_in':day,'status':status})
        self.note('People/Report.md',{'tags':['person'],'relationship':'report'})
        self.note('Accomplishments/Result.md',{'tags':['accomplishment'],'area':'work','person':'[[Report]]','date':'2026-10-12'})
        result=vt.followups(self.root,today=date(2026,10,12))
        self.assertEqual(sorted(x['path'] for x in result['upcoming_check_ins']),['Notes/edge.md','Notes/today.md'])
        self.assertEqual(result['manager'][0]['evidence_in_window'],['Accomplishments/Result.md'])
        config=vt.settings(self.root);config['features']['reviews']=False;self.put('fieldbook.json',json.dumps(config))
        self.assertIsNone(vt.followups(self.root,today=date(2026,10,12))['manager'][0]['evidence_in_window'])

    def test_intake_limits_timeout_and_local_ocr_fixed_arguments(self):
        from types import SimpleNamespace
        import subprocess
        import sys
        extractor=vt.load('test_intake',ROOT/'tools/intake.py')
        p=self.put('Attachments/large.txt',b'x'*(10*1024*1024+1))
        with self.assertRaisesRegex(ValueError,'10 MiB'):extractor.extract(p)
        p=self.put('Attachments/image.png',b'placeholder')
        with patch.object(extractor.subprocess,'run',side_effect=subprocess.TimeoutExpired('worker',35)):
            with self.assertRaisesRegex(ValueError,'35 seconds'):extractor.extract(p)
        worker=vt.load('test_intake_worker',ROOT/'tools/intake-worker.py')
        # Mock the process boundary, never lower this test process's memory limit.
        with patch.dict(sys.modules,{'resource':None}), patch.object(sys,'argv',['worker',str(p),'image']):
            with patch('shutil.which',return_value=None):
                with self.assertRaisesRegex(ValueError,'Install Tesseract'):worker.main()
            def fake_ocr(args,**kwargs):
                self.assertEqual(args,['/trusted/tesseract',str(p),str(p.parent/'ocr'),'-l','eng'])
                self.assertEqual(kwargs['timeout'],25);self.assertNotIn('shell',kwargs)
                (p.parent/'ocr.txt').write_text('Recognized selected text')
                return SimpleNamespace(returncode=0)
            with patch('shutil.which',return_value='/trusted/tesseract'),patch('subprocess.run',side_effect=fake_ocr):
                result=worker.main();self.assertEqual(result['text'],'Recognized selected text')

    def test_activity_and_creation_through_local_menu(self):
        menu=vt.templates(self.root);answers=iter(['4',str(menu.index('Person')+1),'Alex','','create','0'])
        vt.run(self.root,ask=lambda _:next(answers),say=lambda _:None)
        self.assertTrue((self.root/'People/Alex.md').is_file())
        last={'checked_at':'2026-10-12T12:00:00+00:00','result':{'results':[{'provider':'jira','instance':'office','ok':True}]}}
        answers=iter(['2','save'])
        vt.run(self.root,'activity',ask=lambda _:next(answers),say=lambda _:None,last_test=last)
        report=vt.activities(self.root);self.assertEqual(len(report['receipts']),1)
        self.assertEqual(report['receipts'][0]['origin'],'cli-test')

    def test_all_json_candidates_are_excluded(self):
        self.put('fieldbook.json.fieldbook-new','{"secret":"must not print"}')
        self.assertNotIn('must not print',json.dumps(vt.comparison(self.root)))

if __name__=='__main__':unittest.main()
