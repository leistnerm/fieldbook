"""Full-vault restore, interrupted directory swaps, and human-operated CLI recovery."""
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

ROOT=Path(__file__).resolve().parents[1]
def load(name,path):
    spec=importlib.util.spec_from_file_location(name,path)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module);return module
wizard=load('restore_test_wizard',ROOT/'tools/configure.py')
engine=load('restore_test_engine',ROOT/'tools/restore-vault.py')
admin=wizard.admin


class RestoreTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.parent=Path(self.temp.name).resolve();self.root=self.parent/'Existing vault';self.root.mkdir()
        self.backups=self.parent/'Existing vault-fieldbook-backups';self.folder=self.backups/'20261001T120000Z-old'
        self.put('VERSION','0.3.0\n')
        self.put('Notes/Original.md',b'\xef\xbb\xbf---\r\ntags: [note]\r\n---\r\nOld notes.\r\n')
        self.put('Attachments/photo.bin',b'\x00\xff\xfeBINARY')
        self.put('.obsidian/app.json','{"oldSetting":true}\r\n')
        self.put('.git/objects/fixture','history')
        self.put('fieldbook_core/runtime/keep','runtime fixture')
        self.put('File becomes folder','previous file')
        self.put('Folder becomes file/child.md','previous child')
        (self.root/'Empty folder').mkdir()
        self.expected=engine.snapshot(self.root)
        self.make_backup(self.folder)
        self.put('VERSION','0.7.4\n');self.put('Notes/New after upgrade.md','Keep this newer note!')
        self.put('Notes/Original.md','Recent edits');self.put('.obsidian/app.json','{"newSetting":true}')
        (self.root/'File becomes folder').unlink();self.put('File becomes folder/child','new content')
        shutil.rmtree(self.root/'Folder becomes file');self.put('Folder becomes file','new file')
        self.before=engine.snapshot(self.root);self.source_before=engine.snapshot(self.folder)

    def put(self,name,value):
        path=self.root/name;path.parent.mkdir(parents=True,exist_ok=True)
        path.write_bytes(value if isinstance(value,bytes) else value.encode());return path

    def make_backup(self,folder,status='upgrade-complete',root=None,date='2026-10-01T12:00:00+00:00'):
        folder.mkdir(parents=True);shutil.copytree(self.root,folder/'vault',symlinks=True)
        # Original 0.7.4 shape, deliberately without a schema version or kind.
        data={'status':status,'vault':str(root or self.root),'from':'0.3.0','to':'0.7.4',
              'createdUtc':date,'entries':engine.snapshot(folder/'vault')}
        (folder/'receipt.json').write_text(json.dumps(data));return folder

    def restore(self,folder=None):return engine.Restore(self.root,folder or self.folder,admin,say=lambda _:None)

    def run_restore(self,folder=None):
        with self.restore(folder) as restore:restore.preview();return restore.apply()

    def edit_receipt(self,edit):
        data=json.loads((self.folder/'receipt.json').read_text());edit(data)
        (self.folder/'receipt.json').write_text(json.dumps(data))

    def test_preview_cancel_is_read_only_for_vault_and_selected_backup(self):
        with self.restore() as restore:
            preview=restore.preview()
            self.assertEqual(preview['restoreVersion'],'0.3.0');self.assertGreater(preview['changedPaths'],0)
            self.assertIn('Notes/New after upgrade.md',{v['path'] for v in preview['preview']})
        self.assertEqual(engine.snapshot(self.root),self.before)
        self.assertEqual(engine.snapshot(self.folder),self.source_before)
        self.assertEqual(list(self.backups.iterdir()),[self.folder])
        self.assertFalse(list(self.parent.glob('.fieldbook-restore-*')))

    def test_full_restore_keeps_newer_notes_settings_and_entire_previous_vault(self):
        result=self.run_restore();safety=Path(result['safetyBackup'])
        self.assertTrue(result['restored']);self.assertEqual(result['version'],'0.3.0')
        self.assertEqual(engine.snapshot(self.root),self.expected)
        self.assertEqual(engine.snapshot(safety/'vault'),self.before)
        self.assertEqual(engine.read_receipt(safety)['entries'],self.before)
        self.assertEqual(engine.read_receipt(safety)['status'],'restore-complete')
        self.assertEqual(engine.snapshot(self.folder),self.source_before)
        self.assertIn('--restore',(safety/'RESTORE.txt').read_text())

    def test_pre_restore_backup_can_undo_restore_without_discarding_either_snapshot(self):
        first=self.run_restore();safety=Path(first['safetyBackup']);first_state=engine.snapshot(safety)
        second=self.run_restore(safety)
        self.assertEqual(engine.snapshot(self.root),self.before)
        self.assertEqual(engine.snapshot(Path(second['safetyBackup'])/'vault'),self.expected)
        self.assertEqual(engine.snapshot(safety),first_state)
        listed=engine.list_backups(self.backups,self.root)['backups']
        self.assertEqual(sum(v['kind']=='pre-restore' and v['selectable'] for v in listed),2)

    def test_restore_missing_vault_needs_no_current_backup(self):
        shutil.rmtree(self.root);result=self.run_restore()
        self.assertTrue(result['restored']);self.assertIsNone(result['safetyBackup'])
        self.assertEqual(engine.snapshot(self.root),self.expected)

    def test_restore_does_not_need_valid_vault_configuration(self):
        self.put('fieldbook.json','{broken JSON');result=self.run_restore()
        self.assertTrue(result['restored']);self.assertFalse((self.root/'fieldbook.json').exists())
        self.assertEqual((Path(result['safetyBackup'])/'vault/fieldbook.json').read_text(),'{broken JSON')

    def test_noop_creates_no_additional_backup(self):
        self.run_restore();before=list(self.backups.iterdir());result=self.run_restore()
        self.assertFalse(result['restored']);self.assertIsNone(result['safetyBackup'])
        self.assertEqual(list(self.backups.iterdir()),before)

    def test_runtime_links_are_preserved_without_copying_external_targets(self):
        outside=self.parent/'External runtime';outside.mkdir();(outside/'secret').write_text('outside')
        try:(self.root/'fieldbook_core/runtime/python').symlink_to(outside,target_is_directory=True)
        except OSError:self.skipTest('Symlink creation requires platform privileges')
        link_backup=self.make_backup(self.backups/'links');expected=engine.snapshot(self.root)
        (self.root/'fieldbook_core/runtime/python').unlink()
        self.run_restore(link_backup)
        self.assertEqual(engine.snapshot(self.root),expected)
        self.assertTrue((self.root/'fieldbook_core/runtime/python').is_symlink())
        self.assertEqual((outside/'secret').read_text(),'outside')

    def test_list_is_newest_first_filters_vault_and_marks_incomplete(self):
        new=self.make_backup(self.backups/'new',date='2026-10-03T12:00:00+00:00')
        self.make_backup(self.backups/'other',root=self.parent/'another vault')
        self.make_backup(self.backups/'incomplete',status='backup-incomplete',date='2026-10-02T12:00:00+00:00')
        (self.backups/'invalid').mkdir();(self.backups/'invalid/receipt.json').write_text('{}')
        result=engine.list_backups(self.backups,self.root);rows=result['backups']
        self.assertEqual(len(rows),3);self.assertEqual(rows[0]['folder'],str(new))
        self.assertFalse(rows[1]['selectable']);self.assertTrue(rows[2]['selectable']);self.assertEqual(result['ignored'],1)
        self.assertEqual(len(engine.list_backups(self.folder,self.root)['backups']),1)

    def test_missing_backup_directory_lists_empty(self):
        self.assertEqual(engine.list_backups(self.parent/'missing',self.root)['backups'],[])

    def test_malformed_receipts_are_rejected_before_target_changes(self):
        original=(self.folder/'receipt.json').read_bytes()
        bad=[lambda d:d.update(status='unknown'),lambda d:d.update(entries={'../escape':{'kind':'directory'}}),
             lambda d:d.update(entries={'/absolute':{'kind':'directory'}}),lambda d:d.update(entries=[]),
             lambda d:d.update(vault='relative'),lambda d:d.update(createdUtc='bad date'),
             lambda d:d.update(createdUtc='2026-10-01T12:00:00'),
             lambda d:d['entries']['VERSION'].update(sha256='no'),lambda d:d['entries']['VERSION'].update(bytes=True)]
        for edit in bad:
            with self.subTest(edit=edit):
                (self.folder/'receipt.json').write_bytes(original);self.edit_receipt(edit)
                with self.assertRaises(ValueError):self.restore()
                self.assertEqual(engine.snapshot(self.root),self.before)

    def test_duplicate_json_receipt_fields_rejected(self):
        data=(self.folder/'receipt.json').read_text()
        (self.folder/'receipt.json').write_text(data[:-1]+',"status":"upgrade-complete"}')
        with self.assertRaisesRegex(ValueError,'invalid'):self.restore()

    def test_incomplete_backup_never_restored(self):
        self.edit_receipt(lambda d:d.update(status='backup-incomplete'))
        with self.assertRaisesRegex(ValueError,'never verified'):self.restore()

    def test_different_vault_receipt_never_restored(self):
        self.edit_receipt(lambda d:d.update(vault=str(self.parent/'Another vault')))
        with self.assertRaisesRegex(ValueError,'different vault'):self.restore()

    def test_backup_corruption_extra_and_missing_files_rejected(self):
        path=self.folder/'vault/Notes/Original.md';original=path.read_bytes()
        for mode in ('change','missing','extra'):
            with self.subTest(mode=mode):
                path.write_bytes(original)
                if mode=='change':path.write_text('corrupt')
                elif mode=='missing':path.unlink()
                else:(self.folder/'vault/extra').write_text('unexpected')
                with self.assertRaisesRegex(ValueError,'do not match'):
                    with self.restore():pass
                self.assertEqual(engine.snapshot(self.root),self.before)

    def test_linked_root_or_backup_rejected(self):
        link=self.parent/'Linked'
        try:link.symlink_to(self.root,target_is_directory=True)
        except OSError:self.skipTest('Symlink creation requires platform privileges')
        with self.assertRaises(ValueError):engine.Restore(link,self.folder,admin)
        link.unlink();link.symlink_to(self.folder,target_is_directory=True)
        with self.assertRaises(ValueError):self.restore(link)
        link.unlink();shutil.rmtree(self.folder/'vault');(self.folder/'vault').symlink_to(self.root,target_is_directory=True)
        with self.assertRaisesRegex(ValueError,'linked'):self.restore()

    def test_overlapping_backup_rejected(self):
        with self.assertRaisesRegex(ValueError,'outside'):self.restore(self.root/'backup')

    def test_changed_target_after_preview_refuses_application(self):
        with self.restore() as restore:
            restore.preview();self.put('Notes/Concurrent.md','another app');current=engine.snapshot(self.root)
            with self.assertRaisesRegex(ValueError,'changed after'):restore.apply()
        self.assertEqual(engine.snapshot(self.root),current);self.assertEqual(list(self.backups.iterdir()),[self.folder])

    def test_changed_backup_receipt_after_preview_refuses_application(self):
        with self.restore() as restore:
            restore.preview();self.edit_receipt(lambda d:d.update(to='0.8.0'))
            with self.assertRaisesRegex(ValueError,'Selected backup changed'):restore.apply()
        self.assertEqual(engine.snapshot(self.root),self.before)

    def test_changed_backup_file_after_preview_refuses_application(self):
        with self.restore() as restore:
            restore.preview();(self.folder/'vault/VERSION').write_text('0.0.0')
            with self.assertRaisesRegex(ValueError,'Selected backup changed'):restore.apply()
        self.assertEqual(engine.snapshot(self.root),self.before)

    def test_changed_stage_refuses_application(self):
        with self.restore() as restore:
            (restore.stage/'VERSION').write_text('changed')
            with self.assertRaisesRegex(ValueError,'restore copy changed'):restore.apply()
        self.assertEqual(engine.snapshot(self.root),self.before)

    def test_copy_failure_keeps_original_and_source(self):
        with patch.object(engine.shutil,'copytree',side_effect=OSError('disk full')):
            with self.assertRaises(OSError):
                with self.restore():pass
        self.assertEqual(engine.snapshot(self.root),self.before)
        self.assertEqual(engine.snapshot(self.folder),self.source_before)
        self.assertFalse(list(self.parent.glob('.fieldbook-restore-*')))

    def test_corrupt_stage_copy_keeps_original(self):
        real=shutil.copytree
        def corrupt(src,dst,*args,**kwargs):
            value=real(src,dst,*args,**kwargs)
            if Path(src)==self.folder/'vault':(Path(dst)/'VERSION').write_text('bad')
            return value
        with patch.object(engine.shutil,'copytree',side_effect=corrupt):
            with self.assertRaisesRegex(ValueError,'copy failed verification'):
                with self.restore():pass
        self.assertEqual(engine.snapshot(self.root),self.before)

    def test_safety_receipt_failure_keeps_original(self):
        with self.restore() as restore,patch.object(admin,'write',side_effect=OSError('disk full')):
            with self.assertRaises(OSError):restore.apply()
        self.assertEqual(engine.snapshot(self.root),self.before)

    def test_rename_failures_and_interruptions_return_original(self):
        real=os.rename
        for failing_call in (1,2):
            for after_move in (False,True):
                calls=[]
                def fail(src,dst):
                    calls.append((src,dst))
                    if len(calls)==failing_call:
                        if after_move:real(src,dst)
                        raise KeyboardInterrupt() if after_move else OSError('rename denied')
                    return real(src,dst)
                with self.subTest(failing_call=failing_call,after_move=after_move):
                    with self.restore() as restore,patch.object(engine.os,'rename',side_effect=fail):
                        with self.assertRaisesRegex(ValueError,'previous vault was returned'):restore.apply()
                    self.assertEqual(engine.snapshot(self.root),self.before)
                    self.assertEqual(engine.snapshot(self.folder),self.source_before)

    def test_final_receipt_failure_rolls_back_completed_swap(self):
        real=admin.write
        def fail(path,text):
            if path.name=='receipt.json' and '"status": "restore-complete"' in text:raise OSError('disk full')
            return real(path,text)
        with self.restore() as restore,patch.object(admin,'write',side_effect=fail):
            with self.assertRaisesRegex(ValueError,'previous vault was returned'):restore.apply()
        self.assertEqual(engine.snapshot(self.root),self.before)

    def test_concurrent_restored_note_is_retained_and_previous_vault_stays_in_safety(self):
        real=os.rename
        with self.restore() as restore:
            def change(src,dst):
                value=real(src,dst)
                if Path(src)==restore.stage:self.put('Notes/Concurrent after swap.md','Keep concurrent edit')
                return value
            with patch.object(engine.os,'rename',side_effect=change):
                with self.assertRaisesRegex(ValueError,'review recovery manually'):restore.apply()
            safety=restore.safety
        self.assertEqual((self.root/'Notes/Concurrent after swap.md').read_text(),'Keep concurrent edit')
        self.assertEqual(engine.snapshot(safety/'vault'),self.before)
        self.assertEqual(engine.read_receipt(safety)['status'],'manual-recovery-needed')

    def test_new_target_directory_during_swap_is_not_overwritten(self):
        real=os.rename
        with self.restore() as restore:
            def change(src,dst):
                value=real(src,dst)
                if Path(src)==self.root:self.root.mkdir();self.put('Concurrent.md','Keep this')
                return value
            with patch.object(engine.os,'rename',side_effect=change):
                with self.assertRaisesRegex(ValueError,'review recovery manually'):restore.apply()
            safety=restore.safety
        self.assertEqual((self.root/'Concurrent.md').read_text(),'Keep this')
        self.assertEqual(engine.snapshot(safety/'vault'),self.before)

    def test_interrupted_move_with_new_target_file_keeps_selectable_original_backup(self):
        real=os.rename
        with self.restore() as restore:
            def interrupt(src,dst):
                value=real(src,dst)
                if Path(src)==self.root:
                    self.root.write_text('Keep concurrent replacement')
                    raise KeyboardInterrupt()
                return value
            with patch.object(engine.os,'rename',side_effect=interrupt):
                with self.assertRaisesRegex(ValueError,'review recovery manually'):restore.apply()
            safety=restore.safety
        self.assertEqual(self.root.read_text(),'Keep concurrent replacement')
        self.assertEqual(engine.snapshot(safety/'vault'),self.before)
        self.assertEqual(engine.read_receipt(safety)['status'],'manual-recovery-needed')

    def test_walk_permission_error_cannot_silently_omit_files(self):
        def failed_walk(root,**kwargs):
            kwargs['onerror'](PermissionError('unreadable directory'));return iter(())
        with patch.object(engine.backup_tools.os,'walk',side_effect=failed_walk):
            with self.assertRaises(PermissionError):engine.snapshot(self.root)

    def test_cli_picker_lists_backup_previews_and_restores_old_missing_config(self):
        answers=iter(['','1','list','restore']);output=[]
        result=wizard.restore_wizard(str(self.root),ask=lambda _:next(answers),say=output.append)
        self.assertTrue(result['restored']);self.assertEqual(engine.snapshot(self.root),self.expected)
        self.assertIn('contents will be verified','\n'.join(output));self.assertIn('CLI is exiting','\n'.join(output))

    def test_cli_cancel_at_target_picker_and_final_preview(self):
        for target,answers in [(None,['']),(str(self.root),['','0']),(str(self.root),['','1',''])]:
            sequence=iter(answers)
            self.assertIsNone(wizard.restore_wizard(target,ask=lambda _:next(sequence),say=lambda _:None))
        self.assertEqual(engine.snapshot(self.root),self.before);self.assertEqual(list(self.backups.iterdir()),[self.folder])

    def test_direct_cli_handles_restore_before_reading_invalid_session(self):
        with patch.object(wizard,'Session',side_effect=AssertionError('must not read broken config')), \
             patch('sys.stdin',io.StringIO('restore\n')),patch('sys.stdout',io.StringIO()):
            code=wizard.main(['--restore','--vault',str(self.root),'--backup',str(self.folder)])
        self.assertEqual(code,0);self.assertEqual(engine.snapshot(self.root),self.expected)

    def test_main_menu_exits_after_restore_without_reloading_legacy_configuration(self):
        class MinimalSession:
            root=self.root
            config=json.loads((ROOT/'fieldbook.json').read_text())
            original_config=copy.deepcopy(config)
            connections={};original_connections={};credential_attempted=False;save_attempted=False
            key_updates={}
            def unchanged(self):pass
        answers=iter(['13','','','1','restore']);output=[]
        ui=wizard.Wizard(MinimalSession(),ask=lambda _:next(answers),say=output.append)
        with patch.object(wizard,'Session',side_effect=AssertionError('must exit without reopening legacy config')):
            self.assertTrue(ui.run())
        self.assertEqual(engine.snapshot(self.root),self.expected)

    def test_bad_restore_arguments_are_rejected(self):
        for args in (['--backup',str(self.folder)],['--restore','--upgrade'],['--restore','--from','release.zip']):
            with self.subTest(args=args),patch('sys.stderr',io.StringIO()),self.assertRaises(SystemExit) as error:
                wizard.main(args)
            self.assertEqual(error.exception.code,2)


if __name__=='__main__':unittest.main()
