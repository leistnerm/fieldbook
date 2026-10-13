#!/usr/bin/env python3
"""Native offline acceptance: actual packaged source/starters, legacy upgrade and restore."""
import importlib.util
import json
import os
from pathlib import Path
import shutil
import stat
import tempfile
import zipfile

ROOT=Path(__file__).resolve().parents[1]
def load(name,path):
    spec=importlib.util.spec_from_file_location(name,path);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m

def main():
    package=load('accept_package',ROOT/'tools/package-release.py')
    with tempfile.TemporaryDirectory(prefix='fieldbook-acceptance-') as temp:
        parent=Path(temp).resolve();result=package.package(ROOT,parent/'release',starters=True)
        extracted=parent/'extracted';extracted.mkdir()
        for archive in result['archives']:
            with zipfile.ZipFile(archive) as z:z.extractall(extracted)
        result['folders']=[str(extracted/Path(folder).name) for folder in result['folders']]
        for folder in result['folders']:
            for required in ('Tasks','Notes','People','Attachments'):
                assert (Path(folder)/required).is_dir(), 'Archive omitted an empty content folder'
        kit=Path(result['folders'][0]);wizard=load('accept_wizard',kit/'tools/configure.py');admin=wizard.admin
        engine=load('accept_upgrade',kit/'tools/upgrade-vault.py');backup=load('accept_backup',kit/'tools/backup-vault.py');restore=load('accept_restore',kit/'tools/restore-vault.py')
        results=[]
        for source in result['folders']:
            name=Path(source).name;root=parent/('Vault spaces é '+name);shutil.copytree(source,root)
            # Emulate the former AI runtime layout, including optional-resource
            # ownership. Its code is archived, never executed during upgrade.
            (root/'fieldbook_core').rename(root/'.opencode')
            mf=json.loads((root/'fieldbook-manifest.json').read_text())
            mf['files']={n.replace('fieldbook_core/','.opencode/',1) if n.startswith('fieldbook_core/') else n:v for n,v in mf['files'].items()}
            (root/'fieldbook-manifest.json').write_text(json.dumps(mf))
            bank=root/'.fieldbook/modules/files/fieldbook_core'
            if bank.exists():bank.rename(bank.with_name('.opencode'))
            state=root/'.fieldbook/modules/state.json'
            if state.exists():
                data=json.loads(state.read_text())
                data['resources']={n.replace('fieldbook_core/','.opencode/',1) if n.startswith('fieldbook_core/') else n:v for n,v in data['resources'].items()}
                state.write_text(json.dumps(data))
            previous_connection=(root/'.opencode/jira.json').read_bytes()
            # Real legacy path migration plus user-owned read-only file.
            legacy=root/'TaskNotes/Tasks';legacy.mkdir(parents=True)
            (legacy/'Legacy.md').write_bytes(b'---\ntags: [task]\n---\nKeep legacy task.\n')
            views=root/'TaskNotes/Views';shutil.move(root/'Views',views)
            mf=json.loads((root/'fieldbook-manifest.json').read_text())
            mf['files']={n.replace('Views/','TaskNotes/Views/',1) if n.startswith('Views/') else n:v for n,v in mf['files'].items()}
            (root/'fieldbook-manifest.json').write_text(json.dumps(mf))
            kept=root/'Notes/Keep é.md';kept.write_bytes(b'\xef\xbb\xbfMy notes\r\n');kept.chmod(stat.S_IREAD)
            if os.name=='nt':legacy.chmod(stat.S_IREAD)
            original=engine.snapshot(root)
            try:
                scratch=parent/('scratch '+name);scratch.mkdir()
                with engine.Upgrade(root,Path(result['archives'][0]),parent/('backups '+name),admin,say=lambda _:None,temporary_parent=scratch) as upgrade:
                    cfg=dict(upgrade.config);cfg['setups']=['work'];cfg['workRole']='people-manager'
                    cfg['features']={**cfg['features'],'reviews':True}
                    upgrade.finalize(cfg,wizard.arguments);assert engine.snapshot(root)==original
                    receipt=upgrade.apply()
                assert kept.read_bytes()==b'\xef\xbb\xbfMy notes\r\n'
                assert not (root/'.opencode').exists()
                assert (root/'.fieldbook/legacy-ai-runtime').is_dir()
                assert (root/'fieldbook_core/jira.json').read_bytes()==previous_connection
                assert (root/'Tasks/Legacy.md').is_file() and not (root/'TaskNotes').exists()
                assert (root/'Templates/Person - Direct report.md').is_file()
                assert not (root/'Templates/Project - Course.md').exists()
                snap=backup.create(backup.plan(root,parent/('standalone '+name)),admin)
                (root/'Notes/After.md').write_text('Keep in safety snapshot')
                with restore.Restore(root,Path(snap['backup']),admin,say=lambda _:None) as action:
                    action.preview();restored=action.apply()
                assert not (root/'Notes/After.md').exists()
                assert (Path(restored['safetyBackup'])/'vault/Notes/After.md').is_file()
                results.append({'source':name,'legacy_upgrade':'pass','readonly_preserved':'pass','standalone_backup_restore':'pass'})
            finally:
                # CI cleanup must remove the deliberate read-only fixture on Windows too.
                for p in parent.rglob('*'):
                    try:
                        if p.is_file() or os.name=='nt':p.chmod(stat.S_IWRITE|stat.S_IREAD)
                    except OSError:pass
        print(json.dumps({'platform':os.name,'cases':results,'network':False,'plugins':'offline plugin-free fixture'},indent=2))
if __name__=='__main__':main()
