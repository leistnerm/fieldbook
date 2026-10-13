"""Setup switches exercise real resource gates, upgrade preservation and preflight."""
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import shutil
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]

def module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    value = importlib.util.module_from_spec(spec); spec.loader.exec_module(value)
    return value

admin = module('activation_admin', ROOT / 'tools/manage-vault.py')
modules = admin.setup_module()
deployer = module('activation_deploy', ROOT / 'tools/deploy-vault.py')


def config(setups=(), role='individual-contributor', reviews=False, **features):
    return {'schemaVersion': 1, 'setups': list(setups), 'workRole': role,
            'features': {'reviews': reviews, 'jira': False, 'agility': False, 'github': False, 'canvas': False, 'google': False, 'microsoft': False,
                         'azure': False, 'autoPeople': False, 'autoCommit': False, **features},
            'defaults': {'area': setups[0] if len(setups) == 1 else ''}}


class SetupActivationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.parent = Path(self.temp.name).resolve()
        self.kit = self.parent / 'kit'; self.kit.mkdir()
        self.vault = self.parent / 'vault'
        self.catalog = json.loads((ROOT / modules.CATALOG).read_text())
        seeds = {'fieldbook.json': json.dumps(config()), 'opencode.json': '{}',
                 'Templates/Review-format.md': '---\ntags: [review]\n---\n## Review\n'}
        self.put(self.kit, modules.CATALOG, json.dumps(self.catalog))
        self.put(self.kit, 'tools/starter-seeds.json', json.dumps(seeds))
        self.put(self.kit, 'tools/starter-settings.json', json.dumps({
            '.obsidian/plugins/tasknotes/data.json': {'userFields': [{'key':'area','defaultValue':''}]}}))
        self.put(self.kit, 'tools/starter-plugins.json', '{"plugins": []}')
        for entry in self.catalog['resources']:
            if not entry.get('seed'):self.put(self.kit, entry['path'], (ROOT / entry['path']).read_text())
        for name in ('Templates/Person.md','Templates/Person - Professional contact.md','Templates/Item - Purchased.md',
                     'Templates/Task - Study session.md','fieldbook_core/commands/resume.md','fieldbook_core/commands/sync.md',
                     'fieldbook_core/commands/1on1.md','Views/School.base','Views/Reviews.base','Views/Personal.base'):
            self.put(self.kit, name, (ROOT / name).read_text())
        self.put(self.kit, 'LICENSE', 'test license')
        self.manifest(self.kit)

    def put(self, root, name, text):
        path=root/name;path.parent.mkdir(parents=True,exist_ok=True);path.write_text(text);return path

    def manifest(self, root, version='test-new'):
        data={'version':version,'files':{p.relative_to(root).as_posix():admin.hash_text(p)
              for p in root.rglob('*') if p.is_file() and p.name!='fieldbook-manifest.json'
              and p.relative_to(root).as_posix() not in ('fieldbook.json','Templates/Review-format.md')}}
        self.put(root,'fieldbook-manifest.json',json.dumps(data));return data

    def args(self, **kwargs):
        args=dict(setups=None,work_role=None,work_focus=None,work_subrole=None,jira=None,agility=None,
                  github=None,azure=None,canvas=None,reviews=None,auto_people=None,auto_commit=None,apply=False)
        return argparse.Namespace(**{**args, **kwargs})

    def deploy(self, setups=(), role='individual-contributor'):
        return deployer.deploy(self.kit,self.vault,list(setups),role,True,False)

    def snapshot(self, root):
        return {p.relative_to(root).as_posix():p.read_bytes() for p in root.rglob('*') if p.is_file()}

    def test_fresh_matrix_only_discovers_enabled_resources_and_retains_shared_views(self):
        cases=[([], 'individual-contributor'), (['personal'],'individual-contributor'),
               (['school'],'individual-contributor'), (['work'],'individual-contributor'),
               (['work'],'people-manager'), (['personal','school'],'individual-contributor'),
               (['personal','work','school'],'people-manager')]
        for index,(setups,role) in enumerate(cases):
            with self.subTest(setups=setups,role=role):
                self.vault=self.parent/f'vault-{index}'; self.deploy(setups,role)
                settings=json.loads((self.vault/'fieldbook.json').read_text())
                for entry in self.catalog['resources']:
                    self.assertEqual((self.vault/entry['path']).exists(),bool(modules.enabled(entry,settings)),entry['path'])
                    self.assertTrue((self.vault/(modules.BANK+entry['path'])).is_file())
                for name in ('Templates/Person.md','Templates/Task - Study session.md','Templates/Item - Purchased.md',
                             'Templates/Person - Professional contact.md','fieldbook_core/commands/resume.md',
                             'fieldbook_core/commands/1on1.md','fieldbook_core/commands/sync.md',
                             'Views/Personal.base','Views/School.base','Views/Reviews.base'):
                    self.assertTrue((self.vault/name).exists(),name)
                dashboard=(self.vault/'Dashboard.md').read_text()
                for area in ('personal','school','work'):
                    self.assertEqual(f'[[Dashboards/{area.title()}|' in dashboard,area in setups)
                self.assertEqual('[[Views/Reviews.base|' in dashboard,'work' in setups)

    def test_switch_disable_restore_and_repeat_is_idempotent(self):
        self.deploy(['work'],'people-manager')
        note=self.put(self.vault,'Projects/School history.md','---\narea: school\n---\nKeep historical notes\n')
        before=note.read_bytes()
        admin.configure(self.vault,self.args(setups='personal,school',apply=True))
        self.assertFalse((self.vault/'Templates/Person - Direct report.md').exists())
        self.assertTrue((self.vault/'Templates/Project - Course.md').exists())
        self.assertFalse((self.vault/'fieldbook_core/skills/manager-coaching/SKILL.md').exists())
        admin.configure(self.vault,self.args(setups='work',work_role='people-manager',apply=True))
        self.assertTrue((self.vault/'Templates/Person - Direct report.md').exists())
        self.assertFalse((self.vault/'Templates/Project - Course.md').exists())
        snapshot=self.snapshot(self.vault)
        result=admin.configure(self.vault,self.args(apply=True))
        self.assertEqual(result['activation']['files'],[])
        self.assertEqual(self.snapshot(self.vault),snapshot)
        self.assertEqual(note.read_bytes(),before)

    def test_reviews_off_and_provider_features_control_discovery(self):
        self.deploy(['work'],'people-manager')
        admin.configure(self.vault,self.args(reviews='off',github='on',azure='on',apply=True))
        for name in ('Templates/Review-format.md','fieldbook_core/commands/review.md','fieldbook_core/commands/evidence.md',
                     'fieldbook_core/skills/review-evidence/SKILL.md','fieldbook_core/commands/jira-sync.md'):
            self.assertFalse((self.vault/name).exists(),name)
        for name in ('github-sync','azure-sync','coach'):
            self.assertTrue((self.vault/f'fieldbook_core/commands/{name}.md').exists())
        admin.configure(self.vault,self.args(setups='core',apply=True))
        self.assertTrue((self.vault/'fieldbook_core/commands/github-sync.md').exists())
        self.assertFalse((self.vault/'fieldbook_core/commands/coach.md').exists())

    def test_canvas_requires_school_and_disables_when_school_is_removed(self):
        self.deploy(['work']);before=self.snapshot(self.vault)
        with self.assertRaisesRegex(ValueError,'canvas requires school'):
            admin.configure(self.vault,self.args(canvas='on',apply=True))
        self.assertEqual(self.snapshot(self.vault),before)
        preview=admin.configure(self.vault,self.args(setups='school',canvas='on'))
        self.assertTrue(preview['settings']['features']['canvas'])
        self.assertEqual(self.snapshot(self.vault),before)
        admin.configure(self.vault,self.args(setups='school',canvas='on',apply=True))
        self.assertTrue(json.loads((self.vault/'fieldbook.json').read_text())['features']['canvas'])
        admin.configure(self.vault,self.args(setups='work',apply=True))
        self.assertFalse(json.loads((self.vault/'fieldbook.json').read_text())['features']['canvas'])

    def test_canvas_connection_is_seeded_once_and_preserved_on_upgrade(self):
        self.deploy(['school'])
        seeds=json.loads((self.kit/'tools/starter-seeds.json').read_text())
        seeds['fieldbook_core/canvas.json']='{"instances": []}\n'
        self.put(self.kit,'tools/starter-seeds.json',json.dumps(seeds));self.manifest(self.kit,'canvas-seed')
        admin.update(self.vault,self.kit,True,False,True)
        self.assertEqual((self.vault/'fieldbook_core/canvas.json').read_text(),seeds['fieldbook_core/canvas.json'])
        custom='{"instances": [{"id": "my-school", "baseUrl": "https://school.example", "tokenVar": "MY_CANVAS_TOKEN"}]}\n'
        self.put(self.vault,'fieldbook_core/canvas.json',custom)
        admin.update(self.vault,self.kit,True,False,True)
        self.assertEqual((self.vault/'fieldbook_core/canvas.json').read_text(),custom)

    def test_preview_is_mutation_free_and_reports_availability(self):
        self.deploy(['school']);before=self.snapshot(self.vault)
        preview=admin.configure(self.vault,self.args(setups='work',work_role='people-manager'))
        self.assertIn('Templates/Person - Direct report.md',preview['activation']['enabled'])
        self.assertIn('Templates/Project - Course.md',preview['activation']['inactive'])
        self.assertEqual(self.snapshot(self.vault),before)

    def test_customized_resources_remain_active_as_explicit_exceptions(self):
        self.deploy(['work','school'],'people-manager')
        paths=['Templates/Project - Course.md','Templates/Review-format.md','fieldbook_core/commands/coach.md',
               'Dashboards/Work.md','Dashboard.md']
        custom={name:self.put(self.vault,name,'My custom '+name+'\n').read_bytes() for name in paths}
        report=admin.configure(self.vault,self.args(setups='personal',apply=True))
        exceptions={item['path'] for item in report['activation']['preserved_customizations']}
        for name in paths:
            self.assertIn(name,exceptions);self.assertEqual((self.vault/name).read_bytes(),custom[name])
        self.assertTrue((self.vault/'Dashboard.md.fieldbook-new').exists())
        self.assertFalse((self.vault/'Templates/Review-format.md.fieldbook-new').exists())

    def test_user_removed_file_stays_removed_through_switch_and_upgrade(self):
        self.deploy(['school']);(self.vault/'Templates/Project - Course.md').unlink()
        admin.configure(self.vault,self.args(setups='work',apply=True))
        admin.configure(self.vault,self.args(setups='school',apply=True))
        report=admin.update(self.vault,self.kit,True,False,True)
        self.assertFalse((self.vault/'Templates/Project - Course.md').exists())
        self.assertIn('Templates/Project - Course.md',report['activation']['user_removed_preserved'])

    def test_disabled_upgrade_refreshes_hidden_bank_without_resurrection(self):
        self.deploy(['work'])
        changed=(self.kit/'Templates/Project - Course.md').read_text()+'\nNew release section\n'
        self.put(self.kit,'Templates/Project - Course.md',changed);self.manifest(self.kit,'future')
        preview=admin.update(self.vault,self.kit)
        self.assertFalse((self.vault/'Templates/Project - Course.md').exists())
        admin.update(self.vault,self.kit,True,False,True)
        self.assertFalse((self.vault/'Templates/Project - Course.md').exists())
        self.assertEqual((self.vault/(modules.BANK+'Templates/Project - Course.md')).read_text(),changed)
        admin.configure(self.vault,self.args(setups='school',apply=True))
        self.assertEqual((self.vault/'Templates/Project - Course.md').read_text(),changed)

    def without_resource(self, name, shared=False):
        data=json.loads((self.kit/modules.CATALOG).read_text())
        data['resources']=[entry for entry in data['resources'] if entry['path']!=name]
        self.put(self.kit,modules.CATALOG,json.dumps(data))
        if not shared:(self.kit/name).unlink()
        return self.manifest(self.kit,'future-retire')

    def restore_resource(self, name, text):
        data=json.loads((self.kit/modules.CATALOG).read_text())
        data['resources'].append(next(entry for entry in self.catalog['resources'] if entry['path']==name))
        self.put(self.kit,modules.CATALOG,json.dumps(data));self.put(self.kit,name,text)
        return self.manifest(self.kit,'future-restore')

    def test_retired_pristine_command_archived_with_proof_and_reintroduced(self):
        self.deploy(['school']);name='fieldbook_core/commands/course.md'
        original=(self.vault/name).read_text();self.without_resource(name)
        before=self.snapshot(self.vault);preview=admin.update(self.vault,self.kit)
        self.assertIn(name,preview['activation']['deactivated'])
        self.assertEqual(self.snapshot(self.vault),before)
        admin.update(self.vault,self.kit,True,False,True)
        self.assertFalse((self.vault/name).exists())
        self.assertEqual((self.vault/(modules.BANK+name)).read_text(),original)
        retired=json.loads((self.vault/modules.STATE).read_text())['resources'][name]
        self.assertTrue(retired['retired']);self.assertFalse(retired['removed'])
        self.assertEqual(modules.proven_hash(self.vault,name,retired['source'],admin.safe,admin.read),modules.digest(original))
        snapshot=self.snapshot(self.vault)
        admin.configure(self.vault,self.args(apply=True))
        self.assertEqual(self.snapshot(self.vault),snapshot)
        self.restore_resource(name,original+'\nNew release content\n')
        admin.update(self.vault,self.kit,True,False,True)
        self.assertEqual((self.vault/name).read_text(),original+'\nNew release content\n')
        self.assertNotIn('retired',json.loads((self.vault/modules.STATE).read_text())['resources'][name])

    def test_retired_custom_command_preserved_and_manual_removal_stays_removed(self):
        self.deploy(['school']);name='fieldbook_core/commands/course.md'
        original=(self.vault/name).read_text();self.put(self.vault,name,'My custom course command\n')
        self.without_resource(name)
        result=admin.update(self.vault,self.kit,True,False,True)
        self.assertEqual((self.vault/name).read_text(),'My custom course command\n')
        self.assertIn(name,{item['path'] for item in result['activation']['preserved_customizations']})
        self.restore_resource(name,original+'\nNew course\n')
        admin.update(self.vault,self.kit,True,False,True)
        self.assertEqual((self.vault/name).read_text(),'My custom course command\n')
        self.assertEqual((self.vault/(name+'.fieldbook-new')).read_text(),original+'\nNew course\n')
        (self.vault/name).unlink()
        self.without_resource(name);admin.update(self.vault,self.kit,True,False,True)
        self.restore_resource(name,original+'\nLater course\n')
        admin.update(self.vault,self.kit,True,False,True)
        self.assertFalse((self.vault/name).exists())

    def test_reintroduction_rejects_tampered_cache_even_with_matching_state_hash(self):
        self.deploy(['work']);name='Templates/Project - Course.md';original=(self.kit/name).read_text()
        self.without_resource(name);admin.update(self.vault,self.kit,True,False,True)
        self.put(self.vault,modules.BANK+name,'Unverified cache\n')
        state=json.loads((self.vault/modules.STATE).read_text())
        state['resources'][name]['bankHash']=modules.digest('Unverified cache\n')
        self.put(self.vault,modules.STATE,json.dumps(state))
        self.restore_resource(name,original+'\nNew canonical\n')
        before=self.snapshot(self.vault)
        with self.assertRaisesRegex(ValueError,'verified source'):
            admin.update(self.vault,self.kit,True,False,True)
        self.assertEqual(self.snapshot(self.vault),before)

    def test_retired_source_proof_cannot_be_replaced_or_escape_root(self):
        self.deploy(['work']);name='Templates/Project - Course.md'
        self.without_resource(name);admin.update(self.vault,self.kit,True,False,True)
        state=json.loads((self.vault/modules.STATE).read_text());proof=state['resources'][name]['source']['manifest']
        self.put(self.vault,proof,'{}\n');before=self.snapshot(self.vault)
        with self.assertRaisesRegex(ValueError,'source proof'):
            admin.configure(self.vault,self.args(apply=True))
        self.assertEqual(self.snapshot(self.vault),before)
        state['resources'][name]['source']['manifest']='../outside.json'
        self.put(self.vault,modules.STATE,json.dumps(state));before=self.snapshot(self.vault)
        with self.assertRaisesRegex(ValueError,'source proof'):
            admin.configure(self.vault,self.args(apply=True))
        self.assertEqual(self.snapshot(self.vault),before)

    def test_optional_shared_optional_transition_distinguishes_inactive_from_removed(self):
        self.deploy(['work']);name='Templates/Project - Course.md';original=(self.kit/name).read_text()
        self.without_resource(name,shared=True)
        admin.update(self.vault,self.kit,True,False,True)
        self.assertEqual((self.vault/name).read_text(),original)
        self.restore_resource(name,original+'\nBack to optional\n')
        admin.update(self.vault,self.kit,True,False,True)
        self.assertFalse((self.vault/name).exists())
        admin.configure(self.vault,self.args(setups='school',apply=True))
        self.assertEqual((self.vault/name).read_text(),original+'\nBack to optional\n')
        (self.vault/name).unlink()
        self.without_resource(name,shared=True)
        result=admin.update(self.vault,self.kit,True,False,True)
        self.assertFalse((self.vault/name).exists())
        self.assertIn(name,result['user_removed_preserved'])

    def test_shared_transition_rejects_unverified_inactive_cache_before_writing(self):
        self.deploy(['work']);name='Templates/Project - Course.md'
        self.without_resource(name,shared=True)
        self.put(self.vault,modules.BANK+name,'Changed cache')
        state=json.loads((self.vault/modules.STATE).read_text());state['resources'][name]['bankHash']=modules.digest('Changed cache')
        self.put(self.vault,modules.STATE,json.dumps(state));before=self.snapshot(self.vault)
        with self.assertRaisesRegex(ValueError,'verified source'):
            admin.update(self.vault,self.kit,True,False,True)
        self.assertEqual(self.snapshot(self.vault),before)

    def test_manual_removal_while_shared_survives_return_to_optional(self):
        self.deploy(['school']);name='Templates/Project - Course.md';original=(self.kit/name).read_text()
        self.without_resource(name,shared=True);admin.update(self.vault,self.kit,True,False,True)
        (self.vault/name).unlink()
        self.restore_resource(name,original+'\nOptional again\n')
        result=admin.update(self.vault,self.kit,True,False,True)
        self.assertFalse((self.vault/name).exists())
        self.assertIn(name,result['activation']['user_removed_preserved'])

    def test_retired_seed_keeps_historical_seed_proof(self):
        self.deploy(['work']);name='Templates/Review-format.md'
        data=json.loads((self.kit/modules.CATALOG).read_text())
        data['resources']=[entry for entry in data['resources'] if entry['path']!=name]
        self.put(self.kit,modules.CATALOG,json.dumps(data));self.manifest(self.kit,'future-seed-retire')
        admin.update(self.vault,self.kit,True,False,True)
        self.assertFalse((self.vault/name).exists())
        record=json.loads((self.vault/modules.STATE).read_text())['resources'][name]
        self.assertIn('seeds',record['source'])
        self.assertEqual(modules.proven_hash(self.vault,name,record['source'],admin.safe,admin.read),record['bankHash'])

    def test_old_vault_without_state_uses_manifest_proven_ownership(self):
        self.vault.mkdir()
        self.put(self.vault,'fieldbook.json',json.dumps(config(['work'],'people-manager',True)))
        old={'Templates/Project - Course.md':'old course','Templates/Person - Direct report.md':'old report',
             'Setups/Work.md':'old work dashboard','Setups/School.md':'old school dashboard'}
        for name,text in old.items():self.put(self.vault,name,text)
        self.manifest(self.vault,'0.3.0')
        self.put(self.vault,'Setups/School.md','Customized school dashboard')
        self.put(self.vault,'Templates/Person - Direct report.md','Customized report template')
        self.put(self.vault,'Templates/Review-format.md','Company review form')
        self.put(self.vault,'Notes/Real note.md','Important existing content')
        result=admin.update(self.vault,self.kit,True,False,True)
        self.assertFalse((self.vault/'Templates/Project - Course.md').exists())
        self.assertFalse((self.vault/'Setups/Work.md').exists())
        self.assertEqual((self.vault/'.fieldbook/modules/retired/Setups/Work.md').read_text(),old['Setups/Work.md'])
        self.assertEqual((self.vault/'Setups/School.md').read_text(),'Customized school dashboard')
        self.assertEqual((self.vault/'Templates/Person - Direct report.md').read_text(),'Customized report template')
        self.assertTrue((self.vault/'Templates/Person - Direct report.md.fieldbook-new').exists())
        self.assertEqual((self.vault/'Templates/Review-format.md').read_text(),'Company review form')
        self.assertEqual((self.vault/'Notes/Real note.md').read_text(),'Important existing content')
        self.assertTrue((self.vault/'Dashboards/People management.md').exists())

    def test_conflicting_candidate_or_recovery_copy_prevents_all_writes(self):
        self.deploy(['work'])
        self.put(self.vault,'Dashboard.md','Custom dashboard')
        candidate=self.put(self.vault,'Dashboard.md.fieldbook-new','Edited candidate')
        before=self.snapshot(self.vault)
        with self.assertRaisesRegex(ValueError,'merge candidate'):
            admin.configure(self.vault,self.args(setups='school',apply=True))
        self.assertEqual(self.snapshot(self.vault),before)
        candidate.unlink()
        self.put(self.vault,modules.BANK+'Templates/Project - Course.md','Edited recovery file')
        before=self.snapshot(self.vault)
        with self.assertRaisesRegex(ValueError,'recovery copy'):
            admin.update(self.vault,self.kit,True,False,True)
        self.assertEqual(self.snapshot(self.vault),before)

    def test_owned_upgrade_candidate_refreshes_after_setup_change_without_touching_custom_dashboard(self):
        self.deploy(['school']);custom='My personal dashboard layout\n'
        self.put(self.vault,'Dashboard.md',custom)
        admin.update(self.vault,self.kit,True,False,True)
        candidate=self.vault/'Dashboard.md.fieldbook-new'
        self.assertIn('[[Dashboards/School|',candidate.read_text())
        before=self.snapshot(self.vault)
        result=admin.configure(self.vault,self.args(setups='work',work_role='people-manager'))
        self.assertIn('Dashboard.md.fieldbook-new',{entry['path'] for entry in result['activation']['files']})
        self.assertEqual(self.snapshot(self.vault),before)
        admin.configure(self.vault,self.args(setups='work',work_role='people-manager',apply=True))
        self.assertNotIn('[[Dashboards/School|',candidate.read_text())
        self.assertIn('[[Dashboards/People management|',candidate.read_text())
        self.assertEqual((self.vault/'Dashboard.md').read_text(),custom)
        state=json.loads((self.vault/modules.STATE).read_text())['resources']['Dashboard.md']
        self.assertEqual(state['candidateHash'],modules.candidate_hash(self.vault,'Dashboard.md',state['candidateSource'],admin.safe,admin.read))
        before=self.snapshot(self.vault)
        repeated=admin.configure(self.vault,self.args(apply=True))
        self.assertEqual(repeated['activation']['files'],[])
        self.assertEqual(self.snapshot(self.vault),before)

    def test_edited_owned_candidate_refused_even_when_state_hash_is_changed(self):
        self.deploy(['school']);self.put(self.vault,'Dashboard.md','Custom dashboard\n')
        admin.update(self.vault,self.kit,True,False,True)
        self.put(self.vault,'Dashboard.md.fieldbook-new','My edited candidate\n')
        before=self.snapshot(self.vault)
        with self.assertRaisesRegex(ValueError,'merge candidate'):
            admin.configure(self.vault,self.args(setups='work',apply=True))
        self.assertEqual(self.snapshot(self.vault),before)
        state=json.loads((self.vault/modules.STATE).read_text())
        state['resources']['Dashboard.md']['candidateHash']=modules.digest('My edited candidate\n')
        self.put(self.vault,modules.STATE,json.dumps(state));before=self.snapshot(self.vault)
        with self.assertRaisesRegex(ValueError,'merge candidate'):
            admin.configure(self.vault,self.args(setups='work',apply=True))
        self.assertEqual(self.snapshot(self.vault),before)

    def test_owned_module_candidate_refreshes_across_verified_release_changes(self):
        self.deploy(['school']);name='Templates/Project - Course.md'
        self.put(self.vault,name,'My course template\n')
        admin.update(self.vault,self.kit,True,False,True)
        self.put(self.kit,name,(self.kit/name).read_text()+'\nFuture release section\n')
        self.manifest(self.kit,'future-candidate')
        admin.update(self.vault,self.kit,True,False,True)
        self.assertEqual((self.vault/name).read_text(),'My course template\n')
        self.assertEqual((self.vault/(name+'.fieldbook-new')).read_text(),(self.kit/name).read_text())

    def test_owned_candidate_source_proof_must_remain_verified(self):
        self.deploy(['school']);self.put(self.vault,'Dashboard.md','Custom dashboard\n')
        admin.update(self.vault,self.kit,True,False,True)
        state=json.loads((self.vault/modules.STATE).read_text())['resources']['Dashboard.md']
        self.put(self.vault,state['candidateSource']['content'],'{}\n');before=self.snapshot(self.vault)
        with self.assertRaisesRegex(ValueError,'source proof'):
            admin.configure(self.vault,self.args(setups='work',apply=True))
        self.assertEqual(self.snapshot(self.vault),before)

    def test_symlink_and_parent_file_preflight(self):
        self.deploy(['work']);bank=self.vault/(modules.BANK+'Templates/Project - Course.md')
        bank.unlink();bank.symlink_to(self.kit/'Templates/Project - Course.md')
        before=(self.vault/'fieldbook.json').read_bytes()
        with self.assertRaisesRegex(ValueError,'Linked'):
            admin.configure(self.vault,self.args(setups='school',apply=True))
        self.assertEqual((self.vault/'fieldbook.json').read_bytes(),before)
        bank.unlink();shutil.rmtree(self.vault/'.fieldbook')
        self.put(self.vault,'.fieldbook','user file')
        with self.assertRaisesRegex(ValueError,'parent collides'):
            admin.configure(self.vault,self.args(setups='school',apply=True))
        self.assertEqual((self.vault/'fieldbook.json').read_bytes(),before)

    def test_health_detects_config_edits_without_activating_anything(self):
        self.deploy(['work'])
        settings=json.loads((self.vault/'fieldbook.json').read_text())
        settings['setups']=['school'];settings['features']['reviews']=False
        self.put(self.vault,'fieldbook.json',json.dumps(settings))
        before=self.snapshot(self.vault)
        result=admin.health(self.vault)
        self.assertTrue(any('differs from fieldbook.json' in w for w in result['warnings']))
        self.assertEqual(self.snapshot(self.vault),before)

    def test_tasknotes_area_defaults_follow_owned_value_and_preserve_custom_value(self):
        self.deploy(['work'])
        path=self.vault/'.obsidian/plugins/tasknotes/data.json'
        admin.configure(self.vault,self.args(setups='personal,school',apply=True))
        self.assertEqual(json.loads(path.read_text())['userFields'][0]['defaultValue'],'')
        self.put(self.vault,'.obsidian/plugins/tasknotes/data.json','{"userFields":[{"key":"area","defaultValue":"my-custom-area"}]}')
        result=admin.configure(self.vault,self.args(setups='school',apply=True))
        self.assertIn('customized',result['tasknotes_area_default']['warning'])
        self.assertEqual(json.loads(path.read_text())['userFields'][0]['defaultValue'],'my-custom-area')


if __name__ == '__main__':unittest.main()
