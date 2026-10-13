#!/usr/bin/env python3
"""Offline end-to-end human CLI checks against packaged source and starter profiles."""
import importlib.util
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

ROOT=Path(__file__).resolve().parents[1]
def load(name,path):
    spec=importlib.util.spec_from_file_location(name,path);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m

def main():
    builder=load('usage_package',ROOT/'tools/package-release.py');results=[]
    with tempfile.TemporaryDirectory(prefix='fieldbook-usage-') as temp:
        parent=Path(temp).resolve();packages=builder.package(ROOT,parent/'release',True)
        for index,source in enumerate(packages['folders']):
            root=parent/('Working vault '+str(index));shutil.copytree(source,root)
            vt=load('usage_vt',Path(source)/'tools/vault-tools.py');config=json.loads((root/'fieldbook.json').read_text())
            permissions=(root/'opencode.json').read_bytes()
            def run(args,answers):
                result=subprocess.run([sys.executable,'-B',str(Path(source)/'tools/configure.py'),'--vault',str(root),*args],input='\n'.join(answers)+'\n',capture_output=True,text=True,timeout=90)
                if result.returncode or 'Error:' in result.stdout:raise AssertionError(result.stderr+'\n'+result.stdout[-3000:])
                return result.stdout
            context=['']+(['','',''] if 'work' in config['setups'] else [])
            run(['--onboard'],context+['','active','1-high','task','save','2','Vault owner','create','y','First task','create'])
            task=root/'Tasks/First task.md';assert task.is_file()
            assert vt.nb.frontmatter(task.read_text('utf-8'))['status']=='active'
            selves=[r for r in vt.records(root)[0] if vt.tagged(r,'person') and r['fm'].get('relationship')=='self'];assert len(selves)==1
            before=vt.backup.engine.snapshot(root)
            run(['--onboard'],context+['','','','','save',''])
            assert vt.backup.engine.snapshot(root)==before
            run(['--vault-tools','daily'],['','','Tasks/First task.md','','y','create'])
            reports=list((root/'Reports').glob('Daily review*.md'));assert len(reports)==1
            assert '[[Tasks/First task]]' in reports[0].read_text('utf-8')
            before=vt.backup.engine.snapshot(root)
            run(['--vault-tools','weekly'],['','','',''])
            assert vt.backup.engine.snapshot(root)==before
            source_id={'provider':'jira','instance':'office','id':'APP-1'}
            sync=load('usage_sync',Path(source)/'fieldbook_core/scripts/sync_preview.py')
            key=sync.source_key('jira','office','APP-1')
            task.write_text(vt.workflows().metadata(task.read_text('utf-8'),{'jira':'APP-1','jira_instance':'office','status':'blocked','sync_baselines':{key:{'source':source_id,'fields':{'status':'backlog'}}}}),encoding='utf-8')
            proposal={'path':'Tasks/First task.md','expected':vt.sha(task.read_bytes()),'sync':{'source':source_id,'proposed':{'status':'active'},'coverage':{'warning':'Mock proposal; no remote read'}}}
            (root/'Attachments/proposal.json').write_text(json.dumps(proposal),encoding='utf-8')
            before=vt.backup.engine.snapshot(root)
            text=run(['--vault-tools','sync-preview'],['Attachments/proposal.json']);assert '"conflict"' in text
            assert vt.backup.engine.snapshot(root)==before
            assert (root/'opencode.json').read_bytes()==permissions
            results.append({'profile':Path(source).name,'onboarding':'pass','resume_noop':'pass','daily_snapshot':'pass','weekly_cancel':'pass','sync_conflict_read_only':'pass','permissions_unchanged':True})
    print(json.dumps({'results':results,'network':False,'real_vaults_changed':False},indent=2))
if __name__=='__main__':main()
