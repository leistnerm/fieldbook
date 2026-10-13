import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import zipfile

spec=importlib.util.spec_from_file_location('admin',Path(__file__).resolve().parents[1]/'tools/manage-vault.py')
admin=importlib.util.module_from_spec(spec);spec.loader.exec_module(admin)

class AdminTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name).resolve();self.vault=self.root/'vault';self.vault.mkdir();self.kit=self.root/'release';self.kit.mkdir()
    def put(self,root,name,text):
        p=root/name;p.parent.mkdir(parents=True,exist_ok=True);p.write_text(text);return p
    def manifest(self,root,files,version='0.5.0'):
        self.put(root,'fieldbook-manifest.json',json.dumps({'version':version,'files':{n:hashlib.sha256(t.encode()).hexdigest() for n,t in files.items()}}))
        for n,t in files.items():self.put(root,n,t)
    def args(self,**kw):
        d=dict(setups=None,work_role=None,work_focus=None,work_subrole=None,jira=None,agility=None,github=None,azure=None,reviews=None,auto_people=None,auto_commit=None,apply=False);d.update(kw);return argparse.Namespace(**d)
    def config(self):
        self.put(self.vault,'fieldbook.json',json.dumps({'setups':[],'workRole':'individual-contributor','features':{'jira':False,'agility':False,'reviews':False,'autoPeople':False,'autoCommit':False},'defaults':{'area':''}}))
    def test_grouped_specializations_retire_only_pristine_known_kit_templates(self):
        mapping = {'Professional contact':'Person - Professional contact','Direct report':'Person - Direct report',
                   'Purchased item':'Item - Purchased','Course':'Project - Course','Assignment':'Task - Assignment',
                   'Study session':'Task - Study session','Experiment':'Research - Experiment'}
        old = {'Templates/'+name+'.md':'original '+name for name in mapping}
        new = {'Templates/'+name+'.md':'new '+name for name in mapping.values()}
        self.manifest(self.vault,old,'0.7.8');self.manifest(self.kit,new,'0.7.9')
        custom='Templates/Professional contact.md'
        self.put(self.vault,custom,'My custom contact template')
        self.put(self.vault,'People/Alex.md','My real person record')
        report=admin.update(self.vault,self.kit,True,False,True)
        self.assertEqual((self.vault/custom).read_text(),'My custom contact template')
        self.assertEqual((self.vault/'People/Alex.md').read_text(),'My real person record')
        self.assertEqual(set(report['retired_unmodified_templates']),set(old)-{custom})
        for name in new:self.assertTrue((self.vault/name).exists())

    def test_configure_preview_roles_features_and_clear(self):
        self.config();before=(self.vault/'fieldbook.json').read_bytes()
        result=admin.configure(self.vault,self.args(setups='personal,work,school',work_role='people-manager',work_focus='cybersecurity,information-technology',work_subrole='Security lead',jira='on'))
        self.assertEqual((self.vault/'fieldbook.json').read_bytes(),before)
        self.assertTrue(result['settings']['features']['reviews'])
        admin.configure(self.vault,self.args(setups='work',jira='on',work_role='people-manager',apply=True))
        result=admin.configure(self.vault,self.args(setups='personal,school',work_focus='none',work_subrole='none',apply=True))
        self.assertTrue(result['settings']['features']['jira']);self.assertEqual(result['settings']['defaults']['area'],'')
        self.assertEqual(result['settings']['workFocus'],[])
        with self.assertRaises(ValueError):admin.configure(self.vault,self.args(reviews='on'))
    def test_all_trackers_can_be_enabled_in_every_setup_and_survive_context_changes(self):
        for setups in ('core','personal','school','personal,school','work'):
            self.config()
            result=admin.configure(self.vault,self.args(setups=setups,jira='on',agility='on',github='on',azure='on',apply=True))
            for p in ('jira','agility','github','azure'):self.assertTrue(result['settings']['features'][p])
            result=admin.configure(self.vault,self.args(setups='core',apply=True))
            for p in ('jira','agility','github','azure'):self.assertTrue(result['settings']['features'][p])
            self.assertFalse(result['settings']['features']['reviews'])
    def test_update_adds_new_provider_seeds_without_replacing_connections_or_settings(self):
        seeds=json.dumps({'fieldbook_core/github.json':'{"instances": []}', 'fieldbook_core/azure.json':'{"instances": []}'})
        self.manifest(self.kit,{'tools/starter-seeds.json':seeds})
        self.config();before=(self.vault/'fieldbook.json').read_bytes()
        custom='{"instances": [{"id":"my-server","project":"My project"}]}'
        self.put(self.vault,'fieldbook_core/azure.json',custom)
        preview=admin.update(self.vault,self.kit)
        self.assertFalse((self.vault/'fieldbook_core/github.json').exists())
        self.assertTrue(any(p['path']=='fieldbook_core/github.json' for p in preview['files']))
        admin.update(self.vault,self.kit,True,False,True)
        self.assertEqual((self.vault/'fieldbook_core/azure.json').read_text(),custom)
        self.assertEqual((self.vault/'fieldbook.json').read_bytes(),before)
        self.assertEqual(json.loads((self.vault/'fieldbook_core/github.json').read_text()),{'instances':[]})
        self.assertFalse(admin.update(self.vault,self.kit)['files'])

    def test_unused_original_jira_placeholder_gets_editable_identity_only(self):
        self.manifest(self.kit,{'README.md':'kit'});self.config()
        legacy={'instances':[{'baseUrl':'REPLACE-JIRA-URL','flavor':'server','tokenVar':'JIRA_TOKEN','email':''}]}
        path=self.put(self.vault,'fieldbook_core/jira.json',json.dumps(legacy));original=path.read_bytes()
        preview=admin.update(self.vault,self.kit)
        self.assertEqual(path.read_bytes(),original)
        self.assertIn('modernize-unused-jira-placeholder',{p['action'] for p in preview['files']})
        admin.update(self.vault,self.kit,True,False,True)
        instance=json.loads(path.read_text())['instances'][0]
        self.assertEqual(instance,{'id':'office','baseUrl':'https://REPLACE-JIRA-HOST','flavor':'server','tokenVar':'JIRA_TOKEN','email':''})
        self.assertFalse(json.loads((self.vault/'fieldbook.json').read_text())['features']['jira'])
        self.assertFalse(admin.update(self.vault,self.kit)['files'])

    def test_single_configured_legacy_jira_gets_identity_preserving_all_details(self):
        self.manifest(self.kit,{'README.md':'kit'});self.config()
        original='{"instances":[{"baseUrl":"https://jira.example.test","flavor":"server","tokenVar":"JIRA_TOKEN","email":""}]}\r\n'
        path=self.put(self.vault,'fieldbook_core/jira.json',original)
        admin.update(self.vault,self.kit,True,False,True)
        value=json.loads(path.read_text());self.assertEqual(value['instances'][0].pop('id'),'office')
        self.assertEqual(value,json.loads(original))

    def test_multiple_legacy_jira_accounts_are_not_assigned_ambiguous_identities(self):
        self.manifest(self.kit,{'README.md':'kit'});self.config()
        original=json.dumps({'instances':[{'baseUrl':'https://first.example.test'},{'baseUrl':'https://second.example.test'}]})
        path=self.put(self.vault,'fieldbook_core/jira.json',original)
        admin.update(self.vault,self.kit,True,False,True)
        self.assertEqual(path.read_bytes(),original.encode())
    def test_migration_preview_collision_and_idempotence(self):
        self.put(self.vault,'TaskNotes/Tasks/A.md','---\ntags: [task]\n---\n![[TaskNotes/Views/A.base]]')
        self.put(self.vault,'TaskNotes/Views/A.base','views: []')
        self.put(self.vault,'.obsidian/plugins/tasknotes/data.json','{"tasksFolder":"TaskNotes/Tasks"}')
        admin.migrate(self.vault);self.assertTrue((self.vault/'TaskNotes/Tasks/A.md').exists())
        p=self.put(self.vault,'Tasks/A.md','collision')
        with self.assertRaises(ValueError):admin.migrate(self.vault,True,True)
        p.unlink();admin.migrate(self.vault,True,True)
        self.assertIn('[[Views/A.base]]',(self.vault/'Tasks/A.md').read_text())
        self.assertEqual(json.loads((self.vault/'.obsidian/plugins/tasknotes/data.json').read_text())['tasksFolder'],'Tasks')
        self.assertFalse((self.vault/'TaskNotes').exists());self.assertEqual(admin.migrate(self.vault)['moves'],[])

    def test_modern_layout_does_not_rewrite_historical_text_or_manifests(self):
        self.manifest(self.vault,{'UPGRADING.md':'Documentation: TaskNotes/Tasks -> Tasks\n'})
        self.put(self.vault,'Notes/History.md','We used TaskNotes/Tasks before migrating.\n')
        before={p.relative_to(self.vault):p.read_bytes() for p in self.vault.rglob('*') if p.is_file()}
        result=admin.migrate(self.vault,True,True)
        self.assertFalse(result['moves']);self.assertFalse(result['rewrites'])
        self.assertEqual({p.relative_to(self.vault):p.read_bytes() for p in self.vault.rglob('*') if p.is_file()},before)

    def test_legacy_migration_leaves_recovery_banks_backups_and_historical_proofs_unchanged(self):
        self.put(self.vault,'TaskNotes/Tasks/Old.md','[[TaskNotes/Tasks/Other]]')
        saved={name:self.put(self.vault,name,'TaskNotes/Tasks original saved content').read_bytes() for name in (
            '.fieldbook/modules/files/Dashboard.md','.fieldbook/modules/proofs/hash.json',
            '.fieldbook/config-backups/old/files/Notes/Before.md')}
        admin.migrate(self.vault,True,True)
        self.assertEqual((self.vault/'Tasks/Old.md').read_text(),'[[Tasks/Other]]')
        for name,data in saved.items():self.assertEqual((self.vault/name).read_bytes(),data)

    def test_untouched_prior_release_merge_candidate_can_refresh(self):
        self.manifest(self.vault,{'README.md':'previous canonical'},'0.7.5')
        self.put(self.vault,'README.md','My custom README')
        self.put(self.vault,'README.md.fieldbook-new','previous canonical')
        self.manifest(self.kit,{'README.md':'new canonical'},'0.7.6')
        preview=admin.update(self.vault,self.kit)
        self.assertIn('README.md.fieldbook-new',{p['path'] for p in preview['files']})
        self.assertEqual((self.vault/'README.md.fieldbook-new').read_text(),'previous canonical')
        admin.update(self.vault,self.kit,True,False,True)
        self.assertEqual((self.vault/'README.md').read_text(),'My custom README')
        self.assertEqual((self.vault/'README.md.fieldbook-new').read_text(),'new canonical')

    def test_edited_prior_release_merge_candidate_still_blocks_without_mutation(self):
        self.manifest(self.vault,{'README.md':'previous canonical'},'0.7.5')
        self.put(self.vault,'README.md','My custom README')
        self.put(self.vault,'README.md.fieldbook-new','previous canonical plus my pending edits')
        self.manifest(self.kit,{'README.md':'new canonical'},'0.7.6')
        with self.assertRaisesRegex(ValueError,'merge candidate'):admin.update(self.vault,self.kit,True,False,True)
        self.assertEqual((self.vault/'README.md').read_text(),'My custom README')
        self.assertEqual((self.vault/'README.md.fieldbook-new').read_text(),'previous canonical plus my pending edits')
    def test_migration_refuses_links(self):
        self.put(self.vault,'TaskNotes/Tasks/Old.md','legacy task')
        self.put(self.vault,'Notes/a.md','x')
        try:(self.vault/'linked').symlink_to(self.vault/'Notes',target_is_directory=True)
        except OSError:self.skipTest('Host cannot create links')
        with self.assertRaises(ValueError):admin.migrate(self.vault)
    def test_migration_preserves_bom_and_crlf(self):
        p=self.put(self.vault,'TaskNotes/Tasks/A.md','')
        p.write_bytes(b'\xef\xbb\xbf---\r\ntags: [task]\r\n---\r\n[[TaskNotes/Tasks/B]]\r\n')
        admin.migrate(self.vault,True,True)
        self.assertEqual((self.vault/'Tasks/A.md').read_bytes(),b'\xef\xbb\xbf---\r\ntags: [task]\r\n---\r\n[[Tasks/B]]\r\n')
    def test_configure_keeps_reviews_disabled_when_work_already_selected(self):
        self.config()
        admin.configure(self.vault,self.args(setups='work',reviews='off',apply=True))
        result=admin.configure(self.vault,self.args(setups='personal,work',work_focus='sales',apply=True))
        self.assertFalse(result['settings']['features']['reviews'])
    def test_apply_guard_refuses_dirty_or_parent_git_root_before_mutation(self):
        self.put(self.vault,'TaskNotes/Tasks/A.md','keep')
        for top,dirty in [(str(self.vault),' M Inbox.md\n'),(str(self.root),'')]:
            with self.subTest(top=top,dirty=dirty),patch.object(admin.subprocess,'run',side_effect=[argparse.Namespace(stdout=top),argparse.Namespace(stdout=dirty)]):
                with self.assertRaisesRegex(ValueError,'clean Git root'):admin.migrate(self.vault,True)
                self.assertTrue((self.vault/'TaskNotes/Tasks/A.md').exists())
                self.assertFalse((self.vault/'Tasks/A.md').exists())
    def test_update_preserves_user_edits_and_removed_files(self):
        old={'README.md':'old','SETUP.md':'setup','gone.md':'gone'};self.manifest(self.vault,old,'0.4.0')
        self.put(self.vault,'README.md','my edits');(self.vault/'gone.md').unlink()
        self.manifest(self.kit,{'README.md':'new','SETUP.md':'new setup','gone.md':'new gone','new.md':'new'})
        admin.update(self.vault,self.kit)
        self.assertFalse((self.vault/'new.md').exists())
        admin.update(self.vault,self.kit,True,False,True)
        self.assertEqual((self.vault/'README.md').read_text(),'my edits')
        self.assertEqual((self.vault/'README.md.fieldbook-new').read_text(),'new')
        self.assertEqual((self.vault/'SETUP.md').read_text(),'new setup')
        self.assertFalse((self.vault/'gone.md').exists())
    def test_update_bad_hash_and_protected_setting_fail_before_writes(self):
        self.manifest(self.kit,{'new.md':'new','bad.md':'expected'});self.put(self.kit,'bad.md','tampered')
        with self.assertRaises(ValueError):admin.update(self.vault,self.kit,True,False,True)
        self.assertFalse((self.vault/'new.md').exists())
        self.manifest(self.kit,{'opencode.json':'{}'})
        with self.assertRaises(ValueError):admin.update(self.vault,self.kit)
    def test_update_creates_missing_content_folders_and_refuses_file_collision(self):
        self.manifest(self.kit,{'README.md':'new'})
        self.put(self.vault,'Notes','user file')
        with self.assertRaisesRegex(ValueError,'collides'):admin.update(self.vault,self.kit,True,False,True)
        self.assertFalse((self.vault/'README.md').exists())
        (self.vault/'Notes').unlink()
        plan=admin.update(self.vault,self.kit)
        self.assertIn('Notes',plan['created_folders']);self.assertFalse((self.vault/'Notes').exists())
        admin.update(self.vault,self.kit,True,False,True)
        for name in ('Notes','Items','Lists','Attachments'):self.assertTrue((self.vault/name).is_dir())
    def test_deferred_backfill_preserves_body_and_is_idempotent(self):
        mig=json.dumps({'id':'0001','tag':'person','ops':[{'op':'addKey','key':'workerType','value':''}]})
        self.manifest(self.kit,{'fieldbook_core/migrations/0001.json':mig})
        self.put(self.vault,'People/Alex.md','---\ntags: [person]\n---\nOriginal body\n')
        admin.update(self.vault,self.kit,True,False,True)
        self.assertNotIn('workerType:',(self.vault/'People/Alex.md').read_text())
        admin.update(self.vault,self.kit,True,True,True)
        before=(self.vault/'People/Alex.md').read_text();self.assertIn('workerType:',before);self.assertTrue(before.endswith('Original body\n'))
        admin.update(self.vault,self.kit,True,True,True);self.assertEqual((self.vault/'People/Alex.md').read_text(),before)
    def test_labeled_list_conflict_remains_pending(self):
        mig=json.dumps({'id':'0001','tag':'person','ops':[{'op':'toLabeledList','from':'personalEmail','to':'otherEmails','label':'personal'}]})
        self.manifest(self.kit,{'fieldbook_core/migrations/0001.json':mig})
        self.put(self.vault,'People/Alex.md','---\ntags: [person]\npersonalEmail: alex@example.test\notherEmails: ["work: a@example.test"]\n---\nBody')
        result=admin.update(self.vault,self.kit,True,False,True)
        self.assertTrue(result['manual']);self.assertEqual(json.loads((self.vault/'fieldbook-applied.json').read_text())['migrations'],[])
    def test_labeled_list_keeps_quoted_value(self):
        text='---\ntags: [person]\npersonalEmail: "alex@example.test"\n---\nBody'
        mig={'tag':'person','ops':[{'op':'toLabeledList','from':'personalEmail','to':'otherEmails','label':'personal'}]}
        out,issues=admin.migrate_note(text,mig,False,False)
        self.assertFalse(issues);self.assertIn('["personal: alex@example.test"]',out);self.assertTrue(out.endswith('Body'))
    def test_unmodified_retired_script_removed_but_modified_preserved(self):
        self.manifest(self.vault,{'fieldbook_core/scripts/old.ps1':'old','tools/custom.ps1':'original'},'0.4.0')
        self.put(self.vault,'tools/custom.ps1','user edits');self.manifest(self.kit,{'README.md':'new'})
        admin.update(self.vault,self.kit,True,False,True)
        self.assertFalse((self.vault/'fieldbook_core/scripts/old.ps1').exists());self.assertEqual((self.vault/'tools/custom.ps1').read_text(),'user edits')
    def test_person_template_rename_retires_only_unmodified_template_and_is_idempotent(self):
        old={'Templates/Person.md':'old neutral', 'Templates/Work person.md':'old work template'}
        new={'Templates/Person.md':'new neutral','Templates/Person - Professional contact.md':'professional','Templates/Person - Direct report.md':'report'}
        self.manifest(self.vault,old,'0.6.0');self.manifest(self.kit,new,'0.6.1')
        note=self.put(self.vault,'People/Alex.md','---\ntags: [person]\nrelationship: peer\n---\nExisting goals and evidence\n')
        original=note.read_bytes()
        plan=admin.update(self.vault,self.kit)
        self.assertEqual(plan['retired_unmodified_templates'],['Templates/Work person.md'])
        self.assertTrue((self.vault/'Templates/Work person.md').exists())
        self.assertFalse((self.vault/'Templates/Person - Direct report.md').exists())
        admin.update(self.vault,self.kit,True,False,True)
        self.assertFalse((self.vault/'Templates/Work person.md').exists())
        for name,text in new.items():self.assertEqual((self.vault/name).read_text(),text)
        self.assertEqual(note.read_bytes(),original)
        again=admin.update(self.vault,self.kit,True,False,True)
        self.assertEqual(again['files'],[]);self.assertEqual(again['retired_unmodified_templates'],[])
        self.assertEqual(note.read_bytes(),original)
    def test_person_template_customizations_and_existing_new_name_are_preserved(self):
        self.manifest(self.vault,{'Templates/Person.md':'original person','Templates/Work person.md':'original work'},'0.6.0')
        self.put(self.vault,'Templates/Person.md','my person layout')
        self.put(self.vault,'Templates/Work person.md','my custom work layout')
        self.put(self.vault,'Templates/Person - Direct report.md','my existing report layout')
        self.manifest(self.kit,{'Templates/Person.md':'new person','Templates/Person - Direct report.md':'new report'},'0.6.1')
        plan=admin.update(self.vault,self.kit,True,False,True)
        self.assertEqual(plan['retired_unmodified_templates'],[])
        self.assertEqual(plan['preserved_modified_templates'],['Templates/Work person.md'])
        for name,text in [('Person','my person layout'),('Work person','my custom work layout'),('Person - Direct report','my existing report layout')]:
            self.assertEqual((self.vault/f'Templates/{name}.md').read_text(),text)
        self.assertEqual((self.vault/'Templates/Person.md.fieldbook-new').read_text(),'new person')
        self.assertEqual((self.vault/'Templates/Person - Direct report.md.fieldbook-new').read_text(),'new report')
    def test_archive_traversal_refused(self):
        archive=self.root/'bad.zip'
        with zipfile.ZipFile(archive,'w') as z:z.writestr('../outside.md','no')
        with self.assertRaises(ValueError):
            with admin.release(archive):pass
        self.assertFalse((self.root/'outside.md').exists())
    def test_capture_appends_and_does_not_clobber(self):
        self.put(self.vault,'Inbox.md','# Inbox\n\nExisting\n')
        admin.capture(self.vault,'buy milk');text=(self.vault/'Inbox.md').read_text()
        self.assertIn('Existing',text);self.assertIn('buy milk',text)
    def test_health_reports_invalid_setup(self):
        self.config();self.put(self.vault,'fieldbook.json','{}')
        self.assertTrue(admin.health(self.vault)['errors'])

if __name__=='__main__':unittest.main()
