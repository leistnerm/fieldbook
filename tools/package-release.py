#!/usr/bin/env python3
"""Build a clean source ZIP and optional plugin-free starter ZIPs, entirely offline."""
import argparse
import importlib.util
import json
from pathlib import Path
import shutil
import zipfile

ROOT=Path(__file__).resolve().parents[1]
def load(name,path):
    spec=importlib.util.spec_from_file_location(name,path);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m

def package(source,destination,starters=False,plugin_cache=None):
    source=Path(source).resolve(strict=True);destination=Path(destination).resolve()
    if destination==source or destination.is_relative_to(source) or source.is_relative_to(destination):raise ValueError('Output must be separate from source')
    deploy=load('package_deploy',source/'tools/deploy-vault.py');manifest=deploy.checked_release(source)
    version=manifest['version'];destination.mkdir(parents=True,exist_ok=True)
    target=destination/('fieldbook-'+version)
    if target.exists():raise ValueError('Choose a fresh output folder')
    target.mkdir()
    for name in [*manifest['files'],'fieldbook-manifest.json','.github/workflows/check.yml']:
        p=target/name;p.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(source/name,p)
    for name,content in json.loads((source/'tools/starter-seeds.json').read_text()).items():
        p=target/name;p.parent.mkdir(parents=True,exist_ok=True);p.write_text(content,encoding='utf-8',newline='')
    for folder in (*deploy.FOLDERS,'Reports/Reviews'):
        p=target/folder;p.mkdir(parents=True,exist_ok=True);(p/'.gitkeep').touch()
    folders=[target]
    if starters:
        download=deploy.cached_download(source,plugin_cache) if plugin_cache else None
        for name,setups,role in [('personal-college',['personal','school'],'individual-contributor'),('work',['work'],'individual-contributor'),('work-people-manager',['work'],'people-manager')]:
            p=destination/f'fieldbook-{name}-{version}'
            kwargs={'download':download} if download else {}
            deploy.deploy(target,p,setups,role,apply=True,plugins=bool(plugin_cache),**kwargs);folders.append(p)
    archives=[]
    for folder in folders:
        archive=destination/(folder.name+'.zip')
        with zipfile.ZipFile(archive,'x',zipfile.ZIP_DEFLATED) as z:
            for p in sorted(folder.rglob('*')):
                name=(Path(folder.name)/p.relative_to(folder)).as_posix()
                if p.is_dir():z.writestr(name+'/',b'')
                elif p.is_file():z.write(p,name)
        with zipfile.ZipFile(archive) as z:
            if z.testzip() is not None:raise ValueError('Corrupt ZIP')
        archives.append(str(archive))
    return {'archives':archives,'folders':[str(p) for p in folders],'plugins_bundled':bool(plugin_cache)}

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('output',type=Path);parser.add_argument('--starters',action='store_true');parser.add_argument('--plugin-cache',type=Path)
    args=parser.parse_args();print(json.dumps(package(ROOT,args.output,args.starters,args.plugin_cache),indent=2))
