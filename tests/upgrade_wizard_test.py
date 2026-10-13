"""Upgrade real kit layouts through private staging, verified backups and failure recovery."""
import copy
import importlib.util
import io
import json
import os
from pathlib import Path
import shutil
import tempfile
import unittest
from unittest.mock import patch
import zipfile

ROOT=Path(__file__).resolve().parents[1]
def load(name,path):
    spec=importlib.util.spec_from_file_location(name,path)
    value=importlib.util.module_from_spec(spec);spec.loader.exec_module(value);return value
wizard=load('upgrade_test_wizard',ROOT/'tools/configure.py')
engine=load('upgrade_test_engine',ROOT/'tools/upgrade-vault.py')
admin=wizard.admin


class UpgradeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.shared=tempfile.TemporaryDirectory();cls.kit=Path(cls.shared.name)/'release';cls.kit.mkdir()
        names=set(json.loads((ROOT/'fieldbook-manifest.json').read_text())['files'])|{'tools/upgrade-vault.py','tests/upgrade_wizard_test.py'}
        for name in names:
            path=cls.kit/name;path.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(ROOT/name,path)
        for name,text in json.loads((ROOT/'tools/starter-seeds.json').read_text()).items():
            path=cls.kit/name;path.parent.mkdir(parents=True,exist_ok=True);path.write_text(text)
        cls.manifest={'version':(ROOT/'VERSION').read_text().strip(),'files':{n:admin.hash_text(cls.kit/n) for n in sorted(names)}}
        (cls.kit/'fieldbook-manifest.json').write_text(admin.dump(cls.manifest))

    @classmethod
    def tearDownClass(cls):cls.shared.cleanup()

    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.parent=Path(self.temp.name);self.root=self.parent/'Existing vault';shutil.copytree(self.kit,self.root)
        self.backups=self.parent/'Backups'
        self.put('VERSION','0.7.3\n');self.put('README.md','# Previous README\n')
        mf=copy.deepcopy(self.manifest);mf['version']='0.7.3'
        for n in ('VERSION','README.md'):mf['files'][n]=admin.hash_text(self.root/n)
        self.put('fieldbook-manifest.json',admin.dump(mf))
        config=json.loads((self.root/'fieldbook.json').read_text());config['setups']=['personal','school'];config['custom']={'keep':'my setting'}
        self.put('fieldbook.json',admin.dump(config));admin.configure(self.root,wizard.arguments(config,True))
        self.put('README.md','# Previous README\nMy custom section.\n')
        self.put('Notes/Keep.md',b'\xef\xbb\xbf---\r\ntags: [note]\r\n---\r\nOriginal notes.\r\n')
        self.put('Attachments/receipt.bin',b'\x00\xff\x01BINARY')
        self.put('.obsidian/app.json','{"customObsidianSetting": true}\n')
        self.put('.git/keep-hidden','git fixture\n')
        self.put('fieldbook_core/local-setting.json','{"custom":"keep"}\n')
        self.put('opencode.json','{"provider":{"my-provider":{"keep":true}},"permission":{"custom":"ask"}}\r\n')
        (self.root/'Empty folder').mkdir()

    def put(self,name,data):
        path=self.root/name;path.parent.mkdir(parents=True,exist_ok=True)
        path.write_bytes(data if isinstance(data,bytes) else data.encode());return path

    def upgrade(self):return engine.Upgrade(self.root,self.kit,self.backups,admin,say=lambda _:None)

    def manager(self,up):
        config=copy.deepcopy(up.config);config['setups']=['work'];config['workRole']='people-manager'
        config['features']['reviews']=True;config['features']['canvas']=False
        return config

    def test_preview_and_cancel_leave_all_target_bytes_unchanged(self):
        before=engine.snapshot(self.root)
        with self.upgrade() as up:
            preview=up.finalize(self.manager(up),wizard.arguments)
            self.assertIn('README.md.fieldbook-new',preview['mergeCandidates'])
            self.assertEqual(engine.snapshot(self.root),before)
        self.assertFalse(self.backups.exists());self.assertEqual(engine.snapshot(self.root),before)

    def test_manager_apply_preserves_notes_settings_and_complete_backup(self):
        before=engine.snapshot(self.root)
        with self.upgrade() as up:
            up.finalize(self.manager(up),wizard.arguments);result=up.apply()
        self.assertTrue(result['applied']);backup=Path(result['backup'])
        self.assertEqual(engine.snapshot(backup/'vault'),before)
        for name in ('Notes/Keep.md','Attachments/receipt.bin','opencode.json','.obsidian/app.json','fieldbook_core/jira.json','fieldbook_core/local-setting.json','.git/keep-hidden','README.md'):
            self.assertEqual(engine.entry(self.root/name),before[name],name)
        self.assertTrue((backup/'RESTORE.txt').is_file())
        self.assertEqual(json.loads((backup/'receipt.json').read_text())['status'],'upgrade-complete')
        c=json.loads((self.root/'fieldbook.json').read_text())
        self.assertEqual(c['custom'],{'keep':'my setting'});self.assertEqual(c['setups'],['work'])
        self.assertEqual(c['workRole'],'people-manager');self.assertTrue(c['features']['reviews'])
        self.assertTrue((self.root/'Templates/Person - Direct report.md').is_file())
        self.assertFalse((self.root/'Templates/Project - Course.md').exists())

    def test_keep_settings_preserves_exact_configuration_and_connections(self):
        self.put('fieldbook.json',(self.root/'fieldbook.json').read_bytes().replace(b'\n',b'\r\n'))
        before={n:(self.root/n).read_bytes() for n in ['fieldbook.json',*['fieldbook_core/'+p+'.json' for p in wizard.PROVIDERS]]}
        with self.upgrade() as up:up.finalize(up.config,wizard.arguments);up.apply()
        for name,data in before.items():self.assertEqual((self.root/name).read_bytes(),data)

    def test_custom_combination_focus_and_features_follow_activation(self):
        with self.upgrade() as up:
            c=copy.deepcopy(up.config);c['setups']=['work','school'];c['workRole']='individual-contributor'
            c['workFocus']=['information-technology'];c['workSubrole']='technical-lead';c['features']['reviews']=True
            up.finalize(c,wizard.arguments);up.apply()
        c=json.loads((self.root/'fieldbook.json').read_text())
        self.assertEqual(c['setups'],['work','school']);self.assertEqual(c['workSubrole'],'technical-lead')
        self.assertTrue((self.root/'Templates/Project - Course.md').is_file());self.assertFalse((self.root/'Templates/Person - Direct report.md').exists())

    def test_customized_disabled_template_is_preserved_and_reported(self):
        text=(self.root/'Templates/Project - Course.md').read_text()+'\nKeep my custom course layout.\n'
        self.put('Templates/Project - Course.md',text)
        with self.upgrade() as up:
            preview=up.finalize(self.manager(up),wizard.arguments);up.apply()
        self.assertEqual((self.root/'Templates/Project - Course.md').read_text(),text)
        self.assertIn('Templates/Project - Course.md',{r['path'] for r in preview['preservedCustomizations']})

    def test_repeating_upgrade_is_unchanged_without_another_backup(self):
        with self.upgrade() as up:up.finalize(self.manager(up),wizard.arguments);up.apply()
        before=engine.snapshot(self.root);backups=list(self.backups.iterdir())
        with self.upgrade() as up:up.finalize(up.config,wizard.arguments);result=up.apply()
        self.assertFalse(result['applied']);self.assertIsNone(result['backup'])
        self.assertEqual(engine.snapshot(self.root),before);self.assertEqual(list(self.backups.iterdir()),backups)

    def test_legacy_layout_and_missing_configuration_upgrade_without_manual_commands(self):
        shutil.rmtree(self.root/'.fieldbook');(self.root/'fieldbook.json').unlink()
        (self.root/'TaskNotes').mkdir();shutil.move(self.root/'Views',self.root/'TaskNotes/Views')
        (self.root/'TaskNotes/Tasks').mkdir();self.put('TaskNotes/Tasks/Old task.md','---\ntags: [task]\n---\nKeep old task.\n')
        manifest=json.loads((self.root/'fieldbook-manifest.json').read_text())
        manifest['files']={n.replace('Views/','TaskNotes/Views/',1) if n.startswith('Views/') else n:v for n,v in manifest['files'].items()}
        self.put('fieldbook-manifest.json',admin.dump(manifest));before=engine.snapshot(self.root)
        with self.upgrade() as up:
            self.assertTrue(up.migration['moves']);up.finalize(self.manager(up),wizard.arguments);result=up.apply()
        self.assertEqual((self.root/'Tasks/Old task.md').read_text(),'---\ntags: [task]\n---\nKeep old task.\n')
        self.assertFalse((self.root/'TaskNotes').exists())
        self.assertEqual(engine.snapshot(Path(result['backup'])/'vault'),before)

    def test_overlapping_release_and_backup_locations_are_refused(self):
        for source,backup in [(self.root,self.backups),(self.kit,self.root/'backup'),(self.kit,self.parent),(self.kit,self.kit/'backups')]:
            with self.subTest(source=source,backup=backup),self.assertRaises(ValueError):engine.Upgrade(self.root,source,backup,admin)

    def test_changed_target_after_preview_stops_before_backup_or_apply(self):
        with self.upgrade() as up:
            up.finalize(up.config,wizard.arguments);self.put('Notes/Keep.md','Concurrent edit')
            before=engine.snapshot(self.root)
            with self.assertRaisesRegex(ValueError,'changed after preview'):up.apply()
        self.assertEqual(engine.snapshot(self.root),before);self.assertFalse(self.backups.exists())

    def test_backup_failure_never_applies_changes(self):
        before=engine.snapshot(self.root)
        with self.upgrade() as up:
            up.finalize(self.manager(up),wizard.arguments)
            with patch.object(engine.shutil,'copytree',side_effect=OSError('disk full')):
                with self.assertRaisesRegex(ValueError,'no upgrade was applied'):up.apply()
        self.assertEqual(engine.snapshot(self.root),before)

    def test_corrupt_backup_is_detected_before_apply(self):
        before=engine.snapshot(self.root);real_copy=shutil.copytree
        with self.upgrade() as up:
            up.finalize(up.config,wizard.arguments)
            def corrupt(source,dest,*args,**kwargs):
                result=real_copy(source,dest,*args,**kwargs)
                if Path(dest)==up.backup/'vault':(Path(dest)/'Notes/Keep.md').write_text('corrupt')
                return result
            with patch.object(engine.shutil,'copytree',side_effect=corrupt):
                with self.assertRaisesRegex(ValueError,'could not be verified'):up.apply()
            self.assertEqual((up.backup/'vault/Notes/Keep.md').read_text(),'corrupt')
        self.assertEqual(engine.snapshot(self.root),before)

    def test_concurrent_change_during_backup_is_preserved_and_stops_apply(self):
        real_copy=shutil.copytree
        with self.upgrade() as up:
            up.finalize(up.config,wizard.arguments)
            def changed(source,dest,*args,**kwargs):
                result=real_copy(source,dest,*args,**kwargs)
                if Path(dest)==up.backup/'vault':self.put('Notes/Keep.md','Concurrent edit')
                return result
            with patch.object(engine.shutil,'copytree',side_effect=changed):
                with self.assertRaisesRegex(ValueError,'could not be verified'):up.apply()
        self.assertEqual((self.root/'Notes/Keep.md').read_text(),'Concurrent edit')
        self.assertEqual((self.root/'VERSION').read_text().strip(),'0.7.3')

    def test_partial_file_failure_rolls_back_exact_original_bytes(self):
        before=engine.snapshot(self.root);real_install=engine.install;calls=[]
        with self.upgrade() as up:
            up.finalize(self.manager(up),wizard.arguments)
            def failing(source,dest,expected):
                calls.append(str(dest))
                if len(calls)==3:raise OSError('simulated write failure')
                return real_install(source,dest,expected)
            with patch.object(engine,'install',side_effect=failing):
                with self.assertRaisesRegex(ValueError,'rolled back'):up.apply()
            self.assertEqual(json.loads((up.backup/'receipt.json').read_text())['status'],'rolled-back')
        self.assertEqual(engine.snapshot(self.root),before)

    def test_rollback_keeps_concurrent_changes_and_reports_manual_recovery(self):
        real_install=engine.install;changed=[]
        with self.upgrade() as up:
            up.finalize(self.manager(up),wizard.arguments)
            def failing(source,dest,expected):
                if changed:
                    changed[0].write_text('Concurrent user change');raise OSError('later failure')
                real_install(source,dest,expected);changed.append(dest)
            with patch.object(engine,'install',side_effect=failing):
                with self.assertRaisesRegex(ValueError,'manual review'):up.apply()
            self.assertEqual(changed[0].read_text(),'Concurrent user change')
            self.assertEqual(json.loads((up.backup/'receipt.json').read_text())['status'],'manual-recovery-needed')

    def test_modified_staging_copy_is_refused(self):
        before=engine.snapshot(self.root)
        with self.upgrade() as up:
            up.finalize(up.config,wizard.arguments);(up.stage/'Notes/Keep.md').write_text('changed')
            with self.assertRaisesRegex(ValueError,'Prepared upgrade changed'):up.apply()
        self.assertEqual(engine.snapshot(self.root),before);self.assertFalse(self.backups.exists())

    @unittest.skipIf(os.name=='nt','Creating symlinks needs platform privileges; junctions are refused separately')
    def test_full_backup_preserves_runtime_symlinks_without_following_them(self):
        outside=self.parent/'outside';outside.write_text('Do not copy this target')
        path=self.root/'fieldbook_core/.venv/bin/python';path.parent.mkdir(parents=True);path.symlink_to(outside)
        with self.upgrade() as up:up.finalize(up.config,wizard.arguments);result=up.apply()
        copy_path=Path(result['backup'])/'vault/fieldbook_core/.venv/bin/python'
        self.assertTrue(copy_path.is_symlink());self.assertEqual(os.readlink(copy_path),str(outside))
        self.assertFalse((Path(result['backup'])/'vault/outside').exists())

    def test_cli_direct_upgrade_cancels_before_writes_and_does_not_require_old_config(self):
        (self.root/'fieldbook.json').unlink();before=engine.snapshot(self.root)
        with patch('sys.stdin',io.StringIO(str(self.backups)+'\n0\n')),patch('sys.stdout',new_callable=io.StringIO) as out:
            result=wizard.main(['--upgrade','--vault',str(self.root),'--from',str(self.kit)])
        self.assertEqual(result,0);self.assertIn('Upgrade cancelled',out.getvalue());self.assertEqual(engine.snapshot(self.root),before)

    def test_cli_manager_shortcut_applies_only_after_final_confirmation(self):
        before=engine.snapshot(self.root);answers=iter([str(self.backups),'2','7','upgrade']);messages=[]
        result=wizard.upgrade_wizard(str(self.root),str(self.kit),lambda _:next(answers),messages.append)
        self.assertTrue(result['applied']);self.assertEqual(engine.snapshot(Path(result['backup'])/'vault'),before)
        self.assertEqual(json.loads((self.root/'fieldbook.json').read_text())['workRole'],'people-manager')
        self.assertIn('No services or OS credentials were accessed.','\n'.join(messages))

    def test_final_confirmation_cancel_keeps_original_settings(self):
        before=engine.snapshot(self.root);answers=iter([str(self.backups),'2','7',''])
        self.assertIsNone(wizard.upgrade_wizard(str(self.root),str(self.kit),lambda _:next(answers),lambda _:None))
        self.assertEqual(engine.snapshot(self.root),before);self.assertFalse(self.backups.exists())

    def test_main_menu_upgrade_reloads_the_selected_vault(self):
        answers=iter(['12','',str(self.kit),str(self.backups),'2','7','upgrade','0']);messages=[]
        ui=wizard.Wizard(wizard.Session(self.root),lambda _:next(answers),messages.append)
        self.assertTrue(ui.run());self.assertEqual(ui.session.config['workRole'],'people-manager')
        self.assertIn('configuration menu now targets','\n'.join(messages))

    def test_from_argument_requires_upgrade_mode(self):
        with patch('sys.stderr',new_callable=io.StringIO),self.assertRaises(SystemExit):wizard.main(['--from',str(self.kit)])

    def test_bad_release_hash_and_downgrade_are_refused_without_changes(self):
        kit=self.parent/'bad-kit';shutil.copytree(self.kit,kit);(kit/'README.md').write_text('Unverified change')
        before=engine.snapshot(self.root)
        with self.assertRaisesRegex(ValueError,'hash mismatch'):
            with engine.Upgrade(self.root,kit,self.backups,admin,lambda _:None):pass
        self.assertEqual(engine.snapshot(self.root),before)
        self.put('VERSION','99.0.0\n')
        with self.assertRaisesRegex(ValueError,'Downgrades'):
            with self.upgrade():pass

    def configured_source(self,name='starter',setups=('work',),role='people-manager'):
        source=self.parent/name;shutil.copytree(self.kit,source)
        config=json.loads((source/'fieldbook.json').read_text())
        config['setups']=list(setups);config['workRole']=role
        config['features']['reviews']='work' in setups
        admin.configure(source,wizard.arguments(config,True))
        self.assertFalse((source/'fieldbook_core/commands/agility-sync.md').exists())
        self.assertTrue((source/'.fieldbook/modules/files/fieldbook_core/commands/agility-sync.md').is_file())
        return source

    def test_starter_folder_and_zip_sources_upgrade_without_enabling_disabled_features(self):
        target_before=engine.snapshot(self.root)
        profiles=[('personal-school',('personal','school'),'individual-contributor'),
                  ('work',('work',),'individual-contributor'),('manager',('work',),'people-manager')]
        for label,setups,role in profiles:
            source=self.configured_source(label,setups,role);source_before=engine.snapshot(source)
            archive=self.parent/(label+'.zip')
            with zipfile.ZipFile(archive,'w') as zip:
                for file in source.rglob('*'):
                    if file.is_file():zip.write(file,label+'/'+file.relative_to(source).as_posix())
            for kind,release in [('folder',source),('zip',archive)]:
                with self.subTest(profile=label,kind=kind):
                    target=self.parent/(label+'-'+kind+'-target');shutil.copytree(self.root,target)
                    with engine.Upgrade(target,release,self.parent/(label+'-'+kind+'-backups'),admin,lambda _:None) as up:
                        up.finalize(self.manager(up),wizard.arguments);result=up.apply()
                    self.assertEqual(engine.snapshot(Path(result['backup'])/'vault'),target_before)
                    config=json.loads((target/'fieldbook.json').read_text())
                    self.assertEqual(config['setups'],['work']);self.assertEqual(config['workRole'],'people-manager')
                    self.assertFalse(config['features']['agility'])
                    self.assertFalse((target/'fieldbook_core/commands/agility-sync.md').exists())
                    self.assertTrue((target/'Templates/Person - Direct report.md').is_file())
                    self.assertFalse((target/'Templates/Project - Course.md').exists())
                    self.assertEqual((target/'Notes/Keep.md').read_bytes(),(self.root/'Notes/Keep.md').read_bytes())
                    self.assertEqual(engine.snapshot(source),source_before)

    def test_manual_updater_accepts_configured_source_and_preserves_target_settings(self):
        source=self.configured_source();before=engine.snapshot(source)
        config=(self.root/'fieldbook.json').read_bytes();note=(self.root/'Notes/Keep.md').read_bytes()
        admin.update(self.root,source,True,False,True)
        self.assertEqual((self.root/'fieldbook.json').read_bytes(),config)
        self.assertEqual((self.root/'Notes/Keep.md').read_bytes(),note)
        self.assertFalse((self.root/'fieldbook_core/commands/agility-sync.md').exists())
        self.assertEqual(engine.snapshot(source),before)

    def test_configured_source_uses_canonical_modules_without_importing_private_customizations(self):
        source=self.configured_source()
        (source/'Dashboard.md').write_text('PRIVATE customized dashboard')
        (source/'Templates/Person - Direct report.md').write_text('PRIVATE source template')
        (source/'Notes').mkdir(exist_ok=True);(source/'Notes/Private.md').write_text('PRIVATE note')
        (source/'fieldbook_core/agility.json').write_text('{"custom":"PRIVATE connection"}')
        before=engine.snapshot(source)
        with admin.verified_release(source) as prepared:
            for name,expected in self.manifest['files'].items():self.assertEqual(admin.hash_text(prepared/name),expected,name)
            self.assertFalse((prepared/'Notes/Private.md').exists())
            self.assertFalse((prepared/'fieldbook_core/agility.json').exists())
            self.assertFalse((prepared/'.fieldbook').exists())
        self.assertEqual(engine.snapshot(source),before)

    def test_missing_or_tampered_canonical_copy_refuses_before_target_changes(self):
        source=self.configured_source();name='fieldbook_core/commands/agility-sync.md'
        bank=source/('.fieldbook/modules/files/'+name);original=bank.read_bytes();before=engine.snapshot(self.root)
        for mode in ('missing','edited','linked'):
            with self.subTest(mode=mode):
                if bank.exists() or bank.is_symlink():bank.unlink()
                if mode=='edited':bank.write_text('unverified')
                if mode=='linked':
                    try:bank.symlink_to(self.kit/name)
                    except OSError:continue
                with self.assertRaises(ValueError):
                    with engine.Upgrade(self.root,source,self.backups,admin,lambda _:None):pass
                self.assertEqual(engine.snapshot(self.root),before);self.assertFalse(self.backups.exists())
        if bank.exists() or bank.is_symlink():bank.unlink()
        bank.write_bytes(original)

    def test_untracked_bank_does_not_repair_missing_nonmodule_file(self):
        source=self.configured_source();name='tools/configure.py'
        bank=source/('.fieldbook/modules/files/'+name);bank.parent.mkdir(parents=True)
        shutil.copy2(source/name,bank);(source/name).unlink()
        with self.assertRaisesRegex(ValueError,'Missing release file: tools/configure.py'):
            with admin.verified_release(source):pass

    def test_release_bank_is_verified_against_manifest_not_self_reported_state(self):
        source=self.configured_source();name='fieldbook_core/commands/agility-sync.md'
        bank=source/('.fieldbook/modules/files/'+name);bank.write_text('unverified')
        path=source/'.fieldbook/modules/state.json';state=json.loads(path.read_text())
        state['resources'][name]['bankHash']=admin.hash_text(bank);path.write_text(admin.dump(state))
        with self.assertRaisesRegex(ValueError,'recovery copy hash mismatch'):
            with admin.verified_release(source):pass

    def test_release_catalog_is_verified_before_authorizing_bank_fallback(self):
        source=self.configured_source();catalog=source/'tools/setup-catalog.json'
        catalog.write_text(catalog.read_text()+'\n')
        with self.assertRaisesRegex(ValueError,'hash mismatch: tools/setup-catalog.json'):
            with admin.verified_release(source):pass

    def test_untracked_migration_is_not_silently_filtered_from_prepared_source(self):
        source=self.configured_source();(source/'fieldbook_core/migrations/unverified.json').write_text('{}')
        with self.assertRaisesRegex(ValueError,'Migration must be included'):
            with admin.verified_release(source):pass

    def test_legacy_path_rewrites_do_not_preserve_outdated_pristine_kit_files(self):
        (self.root/'TaskNotes/Tasks').mkdir(parents=True)
        self.put('TaskNotes/Tasks/Real task.md','---\ntags: [task]\n---\n[[TaskNotes/Tasks/Other]]\n')
        previous={'AGENTS.md':'Old instructions: TaskNotes/Tasks\n',
                  'Templates/Person.md':'Old template: TaskNotes/Tasks\n',
                  'Dashboard.md':'Old dashboard: TaskNotes/Views\n'}
        manifest=json.loads((self.root/'fieldbook-manifest.json').read_text())
        for name,text in previous.items():
            self.put(name,text);manifest['files'][name]=admin.hash_text(self.root/name)
        self.put('fieldbook-manifest.json',admin.dump(manifest))
        # Emulate the pre-activation legacy kit, without newer module ownership state.
        shutil.rmtree(self.root/'.fieldbook')
        with self.upgrade() as up:
            preview=up.finalize(self.manager(up),wizard.arguments);up.apply()
        for name in previous:
            self.assertNotIn(name+'.fieldbook-new',preview['mergeCandidates'])
            if name!='Dashboard.md':self.assertEqual((self.root/name).read_bytes(),(self.kit/name).read_bytes())
        self.assertIn('[[Dashboards/People management|',(self.root/'Dashboard.md').read_text())
        self.assertIn('[[Tasks/Other]]',(self.root/'Tasks/Real task.md').read_text())

    def test_legacy_migration_still_preserves_custom_kit_content(self):
        (self.root/'TaskNotes/Tasks').mkdir(parents=True)
        self.put('AGENTS.md','Previous default rules for TaskNotes/Tasks.\n')
        manifest=json.loads((self.root/'fieldbook-manifest.json').read_text())
        manifest['files']['AGENTS.md']=admin.hash_text(self.root/'AGENTS.md')
        self.put('fieldbook-manifest.json',admin.dump(manifest))
        self.put('AGENTS.md','My custom rule references TaskNotes/Tasks.\n')
        with self.upgrade() as up:
            preview=up.finalize(self.manager(up),wizard.arguments);up.apply()
        self.assertEqual((self.root/'AGENTS.md').read_text(),'My custom rule references Tasks.\n')
        self.assertIn('AGENTS.md.fieldbook-new',preview['mergeCandidates'])

    def test_manager_preview_reports_preserved_removals_and_plugin_default(self):
        admin.configure(self.root,wizard.arguments({**json.loads((self.root/'fieldbook.json').read_text()),
            'setups':['work'],'workRole':'people-manager'},True))
        (self.root/'Templates/Person - Direct report.md').unlink()
        self.put('.obsidian/plugins/tasknotes/data.json',admin.dump({'userFields':[{'key':'area','defaultValue':'my-custom-area'}]}))
        self.put('Setups/Work.md','Custom old work page\n')
        historical='.fieldbook/config-backups/old/files/README.md.fieldbook-new'
        self.put(historical,'Historical backup content; not a pending merge')
        with self.upgrade() as up:
            preview=up.finalize(self.manager(up),wizard.arguments);up.apply()
        self.assertIn('Templates/Person - Direct report.md',preview['preservedRemovals'])
        self.assertIn('Setups/Work.md',{item['path'] for item in preview['preservedCustomizations']})
        self.assertNotIn(historical,preview['mergeCandidates'])
        # Work was already selected, so repeat configuration need not change the plugin.
        self.assertEqual(json.loads((self.root/'.obsidian/plugins/tasknotes/data.json').read_text())['userFields'][0]['defaultValue'],'my-custom-area')

    def test_changing_to_manager_reports_custom_tasknotes_area_default(self):
        self.put('.obsidian/plugins/tasknotes/data.json',admin.dump({'userFields':[{'key':'area','defaultValue':'my-custom-area'}]}))
        with self.upgrade() as up:
            preview=up.finalize(self.manager(up),wizard.arguments)
        self.assertTrue(preview['tasknotesAreaDefault']['warning'])
        self.assertIn(preview['tasknotesAreaDefault']['warning'],preview['healthWarnings'])

    def test_missing_yaml_dependency_refuses_before_staging_or_backup(self):
        real=__import__;before=engine.snapshot(self.root)
        def missing(name,*args,**kwargs):
            if name=='yaml':raise ModuleNotFoundError('yaml')
            return real(name,*args,**kwargs)
        with patch('builtins.__import__',side_effect=missing),self.assertRaisesRegex(ValueError,'Upgrade requires PyYAML'):
            with self.upgrade():pass
        self.assertEqual(engine.snapshot(self.root),before);self.assertFalse(self.backups.exists())

    def test_custom_temporary_folder_covers_all_preview_workspaces_and_cleans_up(self):
        parent=(self.parent/'Scratch').resolve();parent.mkdir();before=engine.snapshot(self.root)
        real=tempfile.TemporaryDirectory;created=[]
        def located(*args,**kwargs):
            self.assertEqual(Path(kwargs['dir']),parent)
            result=real(*args,**kwargs);created.append(Path(result.name));return result
        with patch.object(tempfile,'TemporaryDirectory',side_effect=located):
            with engine.Upgrade(self.root,self.kit,self.backups,admin,say=lambda _:None,temporary_parent=parent) as up:
                up.finalize(self.manager(up),wizard.arguments)
                self.assertTrue(up.stage.is_relative_to(parent))
                self.assertTrue(up.kit.is_relative_to(parent))
        self.assertGreaterEqual(len(created),5)
        self.assertFalse(any(p.exists() for p in created));self.assertEqual(engine.snapshot(self.root),before)

    def test_custom_temporary_folder_rejects_vault_release_backup_and_missing_paths(self):
        self.backups.mkdir()
        for parent in (self.root,self.kit,self.backups,self.parent,self.parent/'missing'):
            with self.subTest(parent=parent),self.assertRaises(ValueError):
                engine.Upgrade(self.root,self.kit,self.backups,admin,temporary_parent=parent)

    def test_denied_legacy_preview_names_phase_and_leaves_original_untouched(self):
        before=engine.snapshot(self.root)
        denied=PermissionError(13,'Access is denied',r'C:\Users\user\AppData\Local\Temp\fieldbook-upgrade-test\vault\TaskNotes\Tasks')
        with patch.object(admin,'migrate',side_effect=denied),self.assertRaisesRegex(ValueError,'migrate the legacy TaskNotes layout') as caught:
            with self.upgrade():pass
        self.assertIn('existing vault has not been changed',str(caught.exception))
        self.assertIn('--temp-dir',str(caught.exception));self.assertEqual(engine.snapshot(self.root),before)
        self.assertFalse(self.backups.exists())

    def test_windows_readonly_empty_legacy_directory_is_removed_without_touching_notes(self):
        import stat
        from types import SimpleNamespace
        (self.root/'TaskNotes/Tasks').mkdir(parents=True)
        self.put('TaskNotes/Tasks/Legacy.md','---\ntags: [task]\n---\nKeep this task.\n')
        target=self.root/'TaskNotes/Tasks';real_rmdir=Path.rmdir;real_stat=Path.lstat;attempts=[]
        def denied_once(path,*args,**kwargs):
            if path==target and not attempts:
                attempts.append(path);raise PermissionError(13,'Access is denied',str(path))
            return real_rmdir(path,*args,**kwargs)
        def attributes(path,*args,**kwargs):
            result=real_stat(path,*args,**kwargs)
            if path==target:return SimpleNamespace(st_mode=result.st_mode & ~stat.S_IWRITE,st_file_attributes=stat.FILE_ATTRIBUTE_READONLY)
            return result
        with patch.object(Path,'rmdir',denied_once),patch.object(Path,'lstat',attributes):
            admin.migrate(self.root,apply=True,skip=True)
        self.assertTrue(attempts);self.assertFalse((self.root/'TaskNotes').exists())
        self.assertIn('Keep this task.',(self.root/'Tasks/Legacy.md').read_text())

    def test_unrelated_denial_and_nonempty_directory_do_not_trigger_attribute_changes(self):
        import stat
        from types import SimpleNamespace
        target=self.root/'Empty folder'
        with patch.object(Path,'rmdir',side_effect=PermissionError('locked')),patch.object(Path,'chmod') as chmod:
            with self.assertRaises(PermissionError):admin.remove_empty_directory(target)
            chmod.assert_not_called()
        self.put('Empty folder/Keep.md','keep')
        with patch.object(Path,'rmdir',side_effect=PermissionError('denied')),patch.object(Path,'lstat',return_value=SimpleNamespace(st_mode=stat.S_IFDIR|0o555,st_file_attributes=stat.FILE_ATTRIBUTE_READONLY)),patch.object(Path,'chmod') as chmod:
            with self.assertRaises(PermissionError):admin.remove_empty_directory(target)
            chmod.assert_not_called()

    def test_failed_readonly_retry_restores_directory_mode(self):
        import stat
        from types import SimpleNamespace
        target=self.root/'Empty folder'
        with patch.object(Path,'rmdir',side_effect=PermissionError('locked')),patch.object(Path,'lstat',return_value=SimpleNamespace(st_mode=stat.S_IFDIR|0o555,st_file_attributes=stat.FILE_ATTRIBUTE_READONLY)),patch.object(Path,'chmod') as chmod:
            with self.assertRaises(PermissionError):admin.remove_empty_directory(target)
            self.assertEqual([c.args[0] for c in chmod.call_args_list],[0o755,0o555])


if __name__=='__main__':unittest.main()
