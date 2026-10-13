"""Prepare a disposable upgrade stage for the portable runtime layout."""
import json
from pathlib import Path
import shutil

def prepare(root,admin):
    root=Path(root);old=admin.safe(root,'.opencode')
    if not old.exists():return []
    archive=admin.safe(root,'.fieldbook/legacy-ai-runtime')
    if archive.exists():raise ValueError('Legacy AI archive already exists; preserve it separately before upgrading')
    # The guided upgrader already validates/copies the whole tree and backs up the
    # real vault before applying. Never execute archived code or copy its runtime.
    copied=[]
    for provider in ('jira','agility','github','azure','canvas','google','microsoft'):
        source=admin.safe(root,'.opencode/'+provider+'.json')
        dest=admin.safe(root,'fieldbook_core/'+provider+'.json')
        if source.is_file():
            value=admin.read(source);json.loads(value)
            if dest.exists() and admin.read(dest)!=value:raise ValueError('Conflicting old/new integration settings: '+provider)
            if not dest.exists():admin.write(dest,value);copied.append(dest.relative_to(root).as_posix())
    archive.parent.mkdir(parents=True,exist_ok=True)
    shutil.move(str(old),str(archive))
    return copied+['.fieldbook/legacy-ai-runtime']
