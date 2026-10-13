#!/usr/bin/env python3
"""Python maintenance for Fieldbook. Mutations preview unless --apply, except capture."""
import argparse
import ast
import contextlib
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import stat
import zipfile

ROOT = Path(__file__).resolve().parents[1]
PROTECTED = {'fieldbook.json','opencode.json','AGENTS.local.md','Types.md','fieldbook_core/jira.json',
             'fieldbook_core/agility.json','fieldbook_core/github.json','fieldbook_core/azure.json','fieldbook_core/canvas.json','fieldbook_core/google.json','fieldbook_core/microsoft.json','Templates/Review-format.md'}
TEMPLATE_RENAMES = {
    'Templates/Professional contact.md': 'Templates/Person - Professional contact.md',
    'Templates/Direct report.md': 'Templates/Person - Direct report.md',
    'Templates/Purchased item.md': 'Templates/Item - Purchased.md',
    'Templates/Course.md': 'Templates/Project - Course.md',
    'Templates/Assignment.md': 'Templates/Task - Assignment.md',
    'Templates/Study session.md': 'Templates/Task - Study session.md',
    'Templates/Experiment.md': 'Templates/Research - Experiment.md',
    'Templates/Work person.md': 'Templates/Person - Direct report.md',
}
SKIP = {'.git','.trash','.fieldbook','node_modules','.venv','__pycache__'}
CONTENT_FOLDERS = ('Tasks','Projects','People','Notes','Meetings','Decisions','Reference',
                   'Research','Reports','Transcripts','Accomplishments','Opportunities','Items','Lists','Attachments')

def safe(root, name):
    if not name or name.startswith('/') or '\\' in name or ':' in name or any(p in {'','.', '..'} for p in name.split('/')):
        raise ValueError(f'Unsafe relative path: {name}')
    path=root
    for part in name.split('/'):
        path=path/part
        if path.is_symlink() or path.exists() and getattr(path.lstat(),'st_file_attributes',0)&0x400:
            raise ValueError(f'Linked/reparse path: {name}')
        if path.is_file() and path.stat().st_nlink != 1:
            raise ValueError(f'Hard-linked file: {name}')
    if not path.resolve().is_relative_to(root.resolve()):
        raise ValueError('Path escapes vault')
    return path

def read(path):
    return path.read_bytes().decode('utf-8-sig')

def hash_text(path):
    return hashlib.sha256(read(path).replace('\r\n','\n').encode()).hexdigest()

def write(path, text):
    path.parent.mkdir(parents=True,exist_ok=True)
    fd,temp=tempfile.mkstemp(prefix='.fieldbook-',suffix='.tmp',dir=path.parent)
    try:
        with os.fdopen(fd,'w',encoding='utf-8',newline='') as stream:
            stream.write(text);stream.flush();os.fsync(stream.fileno())
        os.replace(temp,path)
    finally:
        if os.path.exists(temp):os.unlink(temp)

def dump(value):
    return json.dumps(value,indent=2,ensure_ascii=False)+'\n'

def remove_empty_directory(path):
    """Remove only an empty ordinary directory, handling Windows' read-only flag.

    Never change ACLs, recurse into content, or clear attributes on user files.
    Restore the directory mode if removing it still fails.
    """
    try:path.rmdir()
    except PermissionError:
        info=path.lstat()
        if (not stat.S_ISDIR(info.st_mode) or stat.S_ISLNK(info.st_mode)
                or getattr(info,'st_file_attributes',0)&0x400
                or not getattr(info,'st_file_attributes',0)&stat.FILE_ATTRIBUTE_READONLY):raise
        if any(path.iterdir()):raise
        original=stat.S_IMODE(info.st_mode)
        path.chmod(original|stat.S_IWRITE)
        try:path.rmdir()
        except BaseException:
            if path.exists():path.chmod(original)
            raise

def files(root, notes=False):
    out=[]
    for parent,dirs,names in os.walk(root,followlinks=False):
        dirs[:]=[d for d in sorted(dirs) if d not in SKIP and not (notes and (d.startswith('.') or d in {'Templates','Examples','Setups','Dashboards','Views','tools','tests'}))]
        for name in [*dirs,*names]:
            safe(root,(Path(parent)/name).relative_to(root).as_posix())
        for name in sorted(names):
            p=Path(parent)/name
            if not notes or p.suffix=='.md':out.append(p)
    return out

def git_guard(root, skip):
    if skip:return
    try:
        top=subprocess.run(['git','-C',str(root),'rev-parse','--show-toplevel'],capture_output=True,text=True,check=True).stdout.strip()
        dirty=subprocess.run(['git','-C',str(root),'status','--porcelain'],capture_output=True,text=True,check=True).stdout
    except (OSError,subprocess.SubprocessError):
        raise ValueError('Use a clean Git vault root, or make a backup and pass --skip-git-check')
    if Path(top).resolve()!=root or dirty:
        raise ValueError('Vault must be a clean Git root; otherwise back up and use --skip-git-check')

def notebook_module():
    spec=importlib.util.spec_from_file_location('fieldbook_notebook',ROOT/'fieldbook_core/scripts/notebook.py')
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    return module

def setup_module():
    spec=importlib.util.spec_from_file_location('fieldbook_setup_modules',ROOT/'tools/setup-modules.py')
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    return module

def tasknotes_default_plan(root, previous, current):
    """Keep a customized plugin default; follow configuration only for an owned default."""
    name='.obsidian/plugins/tasknotes/data.json';path=safe(root,name)
    if not path.exists() or previous==current:return None,None
    data=json.loads(read(path))
    area=next((f for f in data.get('userFields',[]) if f.get('key')=='area'),None)
    if not area:return None,None
    if area.get('defaultValue','')!=previous:
        return None,'TaskNotes area default is customized; preserved. Adjust it manually if needed.'
    area['defaultValue']=current
    return (name,dump(data)),None

def configure(root, args):
    path=safe(root,'fieldbook.json'); c=json.loads(read(path)); previous_area=c.get('defaults',{}).get('area','');previous_setups=list(c.get('setups',[]))
    for provider in ('jira','agility','github','azure','canvas','google','microsoft'):c['features'].setdefault(provider,False)
    if args.setups is not None:
        choices=[] if args.setups=='core' else list(dict.fromkeys(args.setups.split(',')))
        if set(choices)-{'personal','work','school'}:raise ValueError('Use core alone or personal,work,school')
        newly_work='work' in choices and 'work' not in c['setups']
        c['setups']=choices
        if newly_work and args.reviews is None:c['features']['reviews']=True
    if args.work_role:c['workRole']=args.work_role
    if args.work_focus is not None:c['workFocus']=[] if args.work_focus=='none' else list(dict.fromkeys(args.work_focus.split(',')))
    if args.work_subrole is not None:c['workSubrole']='' if args.work_subrole=='none' else args.work_subrole
    for name,key in [('jira','jira'),('agility','agility'),('github','github'),('azure','azure'),('canvas','canvas'),('google','google'),('microsoft','microsoft'),('reviews','reviews'),('auto_people','autoPeople'),('auto_commit','autoCommit')]:
        value=getattr(args,name,None)
        if value is not None:c['features'][key]=value=='on'
    if 'work' not in c['setups']:
        for name in ('reviews',):
            if getattr(args,name,None)=='on':raise ValueError(f'{name} requires work')
            c['features'][name]=False
    if 'school' not in c['setups']:
        if getattr(args,'canvas',None)=='on':raise ValueError('canvas requires school')
        c['features']['canvas']=False
    original_defaults=dict(c.get('defaults',{}))
    supplied=getattr(args,'defaults',None)
    if supplied is not None:
        if not isinstance(supplied,dict):raise ValueError('defaults must be an object')
        for key in ('area','status','priority','type'):
            if key in supplied:c['defaults'][key]=supplied[key]
    elif args.setups is not None:
        c['defaults']['area']=c['setups'][0] if len(c['setups'])==1 else ''
    if args.setups is not None and c['setups']!=previous_setups and not getattr(args,'explicit_defaults',False):
        c['defaults']['area']=c['setups'][0] if len(c['setups'])==1 else ''
    def changed_default(key):return getattr(args,'explicit_defaults',False) or c['defaults'].get(key)!=original_defaults.get(key)
    if changed_default('area') and c['defaults'].get('area','') not in ('','personal','work','school'):raise ValueError('Invalid default area')
    if changed_default('status') and c['defaults'].get('status','backlog') not in ('backlog','active','blocked','done','dropped'):raise ValueError('Invalid default status')
    if changed_default('priority') and c['defaults'].get('priority','2-normal') not in ('1-high','2-normal','3-low'):raise ValueError('Invalid default priority')
    if changed_default('type') and (not isinstance(c['defaults'].get('type','task'),str) or not re.fullmatch(r'[a-z][a-z0-9_-]{0,63}',c['defaults'].get('type','task'))):raise ValueError('Default type must be a short lowercase label')
    activation=setup_module().plan(root,c,safe,read,write)
    plugin,warning=tasknotes_default_plan(root,previous_area,c['defaults']['area'])
    if args.apply:
        activation.apply()
        if plugin:write(safe(root,plugin[0]),plugin[1])
        if not path.exists() or json.loads(read(path))!=c:write(path,dump(c))
    return {'apply':args.apply,'settings':c,'activation':activation.summary(),
            'tasknotes_area_default':{'updated':bool(plugin),'warning':warning}}


def health(root):
    errors=[];warnings=[]
    for name in ('fieldbook.json','opencode.json','fieldbook_core/package.json','fieldbook_core/jira.json','fieldbook_core/agility.json','fieldbook_core/github.json','fieldbook_core/azure.json','fieldbook_core/canvas.json','fieldbook_core/google.json','fieldbook_core/microsoft.json'):
        try:json.loads(read(safe(root,name)))
        except (ValueError,OSError) as e:errors.append(f'{name}: {e}')
    for name in ('Tasks','Views','Projects','People','Notes','Templates'):
        if not (root/name).is_dir():errors.append(f'Missing {name}/')
    if (root/'TaskNotes').exists():errors.append('Legacy TaskNotes folder remains; run migrate')
    try:
        c=json.loads(read(safe(root,'fieldbook.json')))
        if set(c['setups'])-{'personal','work','school'}:errors.append('Unknown setup')
        if c['workRole'] not in {'individual-contributor','people-manager'}:errors.append('Invalid workRole')
        for f in ('jira','agility','github','azure','canvas','google','microsoft','reviews','autoPeople','autoCommit'):
            if type(c['features'].get(f,False)) is not bool:errors.append(f'{f} must be true or false')
        if 'work' not in c['setups'] and c['features'].get('reviews'):errors.append('Review features require work')
        if 'school' not in c['setups'] and c['features'].get('canvas'):errors.append('Canvas requires school')
        modules=setup_module();resources=modules.catalog(root,safe,read)
        state_path=safe(root,modules.STATE)
        if resources and not state_path.exists():
            warnings.append('Setup activation has not run; preview configure, then configure --apply for this vault.')
        elif resources:
            activation=json.loads(read(state_path)).get('resources',{})
            for entry in resources:
                name=entry['path'];status=activation.get(name,{})
                if status.get('enabled')!=bool(modules.enabled(entry,c)):
                    warnings.append('Setup activation differs from fieldbook.json: '+name+'; run configure --apply.')
                active=safe(root,name)
                if status.get('preserved'):
                    warnings.append('Customized resource preserved: '+name)
                elif status.get('enabled') and not active.exists() and not status.get('removed'):
                    warnings.append('Active resource was removed: '+name+'; configure preserves deliberate removals.')
                elif not status.get('enabled') and active.exists():
                    warnings.append('Inactive resource remains installed: '+name+'; run configure --apply.')
                bank=safe(root,modules.BANK+name)
                if not bank.exists() or hash_text(bank)!=status.get('bankHash'):
                    warnings.append('Missing or edited optional-resource recovery copy: '+name)
    except (ValueError,KeyError,TypeError,OSError) as e:errors.append(str(e))
    for folder in ('tools','fieldbook_core/scripts'):
        for p in (root/folder).glob('*.py'):
            try:ast.parse(read(safe(root,p.relative_to(root).as_posix())))
            except (ValueError,SyntaxError,OSError) as e:errors.append(str(e))
    try:
        import yaml
    except ImportError:warnings.append('Install fieldbook_core/requirements.txt in the Python used by notebook tools')
    if not (root/'fieldbook_core/node_modules/yaml/package.json').exists():warnings.append('Optional tracker/Canvas readers need Node.js 22+ and npm install --omit=dev --ignore-scripts --no-save (run from fieldbook_core)')
    return {'errors':errors,'warnings':warnings,'note':'Live Obsidian/AI harness and tracker checks remain manual'}

def migrate(root, apply=False, skip=False):
    if not (root/'TaskNotes').exists():
        return {'apply':apply,'moves':[],'rewrites':[],'note':'Root Tasks/Views layout already in use; no migration needed'}
    all_files=files(root);moves=[];changes=[]
    for folder in ('Tasks','Views'):
        old=root/'TaskNotes'/folder
        for p in all_files:
            if p.is_relative_to(old):
                dest=safe(root,(Path(folder)/p.relative_to(old)).as_posix())
                if dest.exists():raise ValueError(f'Collision: {dest}; nothing changed')
                moves.append((p,dest))
    replacements=[(a,b) for a,b in [('TaskNotes/Tasks','Tasks'),('TaskNotes/Views','Views'),('TaskNotes\\\\Tasks','Tasks'),('TaskNotes\\\\Views','Views'),('TaskNotes\\Tasks','Tasks'),('TaskNotes\\Views','Views')]]
    for p in all_files:
        if p.name=='fieldbook-manifest.json' or p.suffix not in {'.md','.base','.json'}:continue
        text=p.read_bytes().decode('utf-8');new=text
        for before,after in replacements:new=new.replace(before,after)
        if new!=text:changes.append((p,new))
    manifest=safe(root,'fieldbook-manifest.json')
    manifest_new=None
    if manifest.exists():
        mf=json.loads(read(manifest));renamed={}
        for name,h in mf['files'].items():
            new=name.replace('TaskNotes/Tasks','Tasks').replace('TaskNotes/Views','Views')
            if new in renamed:raise ValueError('Manifest path collision')
            renamed[new]=h
        mf['files']=renamed;manifest_new=dump(mf)
    if apply:
        git_guard(root,skip)
        for p,text in changes:write(p,text)
        for source,dest in moves:
            dest.parent.mkdir(parents=True,exist_ok=True)
            # Exclusive destination creation before removing the old file.
            with dest.open('xb') as stream:stream.write(source.read_bytes())
            source.unlink()
        if manifest_new is not None:write(manifest,manifest_new)
        old=root/'TaskNotes'
        if old.exists():
            for parent,dirs,names in os.walk(old,topdown=False):
                if not any(Path(parent).iterdir()):remove_empty_directory(Path(parent))
    return {'apply':apply,'moves':[{'from':str(a.relative_to(root)),'to':str(b.relative_to(root))} for a,b in moves],
            'rewrites':[p.relative_to(root).as_posix() for p,_ in changes], 'note':'Close both apps and back up before apply; the batch is not transactional'}

@contextlib.contextmanager
def release(location, temporary_parent=None):
    path=Path(location).resolve(strict=True)
    with tempfile.TemporaryDirectory(prefix='fieldbook-release-', dir=temporary_parent) as temp:
        if path.is_file():
            stage=Path(temp)
            with zipfile.ZipFile(path) as z:
                if len(z.infolist())>10000 or sum(i.file_size for i in z.infolist())>200*1024*1024:raise ValueError('Release archive is too large')
                for info in z.infolist():
                    name=info.filename.rstrip('/')
                    target=safe(stage,name)
                    if (info.external_attr>>16)&0o170000==0o120000:raise ValueError('Archive symlink refused')
                    if info.is_dir():target.mkdir(parents=True,exist_ok=True)
                    else:
                        target.parent.mkdir(parents=True,exist_ok=True)
                        with target.open('xb') as stream:stream.write(z.read(info))
            path=stage
        candidates=[path/'fieldbook-manifest.json',*path.glob('*/fieldbook-manifest.json')]
        matches=[p for p in candidates if p.is_file()]
        if len(matches)!=1:raise ValueError('Choose a release with exactly one manifest at its root or one folder below')
        yield matches[0].parent

@contextlib.contextmanager
def verified_release(location, temporary_parent=None):
    """Build canonical update input without activating or modifying a starter/source vault.

    Optional resources can be absent or rendered/customized at their visible paths.
    Only catalogued resources may fall back to the hidden canonical bank, and the
    release manifest (never activation state alone) must prove their contents.
    """
    with release(location, temporary_parent) as source, tempfile.TemporaryDirectory(prefix='fieldbook-verified-release-', dir=temporary_parent) as temp:
        kit=Path(temp)
        manifest=json.loads(read(safe(source,'fieldbook-manifest.json')))
        declared=manifest.get('files')
        if not isinstance(declared,dict):raise ValueError('Invalid release manifest')
        modules=setup_module();catalog_path=safe(source,modules.CATALOG)
        if catalog_path.exists():
            if modules.CATALOG not in declared:raise ValueError('Setup catalog must be included in the verified manifest')
            if hash_text(catalog_path)!=declared[modules.CATALOG]:raise ValueError('Release hash mismatch: '+modules.CATALOG)
        elif modules.CATALOG in declared:
            raise ValueError('Missing release file: '+modules.CATALOG+'; extract a fresh source ZIP')
        managed={entry['path'] for entry in modules.catalog(source,safe,read) if not entry.get('seed')}
        # Do not hide untracked migration programs when assembling the clean input.
        for migration in (source/'fieldbook_core/migrations').glob('*.json'):
            if migration.relative_to(source).as_posix() not in declared:
                raise ValueError('Migration must be included in the verified manifest')
        for name,expected in declared.items():
            if name in PROTECTED or name.startswith(('.obsidian/','.git/')):
                raise ValueError('Release tries to replace user settings: '+name)
            active=safe(source,name)
            if active.exists() and not active.is_file():raise ValueError('Release file collides with a directory: '+name)
            text=read(active) if active.is_file() else None
            if text is None or modules.digest(text)!=expected:
                if name in managed:
                    bank=safe(source,modules.BANK+name)
                    if bank.is_file():
                        canonical=read(bank)
                        if modules.digest(canonical)!=expected:
                            raise ValueError('Release recovery copy hash mismatch: '+name+'; extract a fresh source ZIP')
                        text=canonical
                if text is None:
                    raise ValueError('Missing release file: '+name+' (no verified recovery copy); extract a fresh source ZIP')
                if modules.digest(text)!=expected:
                    raise ValueError('Release hash mismatch: '+name+'; extract a fresh source ZIP')
            write(safe(kit,name),text)
        write(kit/'fieldbook-manifest.json',dump(manifest))
        yield kit

def migrate_note(text, migration, backfill, was_applied):
    module=notebook_module();fm=module.frontmatter(text)
    if migration['tag'] not in module.values(fm.get('tags')):return text,[]
    match=re.match(r'^(\ufeff?---\r?\n)(.*?)(\r?\n---(?:\r?\n|$))',text,re.S)
    if not match:return text,[]
    newline='\r\n' if '\r\n' in text else '\n';lines=match[2].splitlines();manual=[]
    def index(key):return next((i for i,l in enumerate(lines) if l.startswith(key+':')),None)
    for op in migration['ops']:
        if op['op']=='addKey':
            if backfill and index(op['key']) is None:lines.append(op['key']+': '+str(op.get('value','')))
        elif was_applied:continue
        elif op['op']=='toLabeledList':
            source=op['from'];dest=op['to'];idx=index(source)
            if idx is None:continue
            value=fm.get(source)
            if not isinstance(value,str) or (idx+1<len(lines) and lines[idx+1].startswith((' ','\t'))):
                manual.append(source+' needs manual conversion');continue
            other=index(dest)
            if other is not None and fm.get(dest) not in (None,'',[]):
                manual.append(dest+' already contains data');continue
            converted=dest+': ['+json.dumps(op['label']+': '+value,ensure_ascii=False)+']' if value else dest+': []'
            if other is not None:lines[other]=converted;lines.pop(idx)
            else:lines[idx]=converted
        else:manual.append('Unsupported migration operation: '+str(op['op']))
    result=match[1]+newline.join(lines)+match[3]+text[match.end():]
    module.frontmatter(result)
    return result,manual

def update(root, source, apply=False, backfill=False, skip=False, temporary_parent=None):
    with release(source, temporary_parent) as original, verified_release(original, temporary_parent) as kit:
        if original.resolve()==root:raise ValueError('Release cannot be the target vault itself')
        if (root/'.opencode').exists():raise ValueError('Use the guided upgrade to archive the previous AI runtime and preserve provider settings')
        if (root/'TaskNotes').exists():raise ValueError('Run migrate first; TaskNotes/ still exists')
        new=json.loads(read(safe(kit,'fieldbook-manifest.json')))
        old_path=safe(root,'fieldbook-manifest.json');old=json.loads(read(old_path)) if old_path.exists() else {'files':{}}
        modules=setup_module()
        resources=modules.catalog(kit,safe,read)
        if resources and modules.CATALOG not in new['files']:
            raise ValueError('Setup catalog must be included in the verified manifest')
        managed={entry['path'] for entry in resources}
        module_state_path=safe(root,modules.STATE)
        module_state=json.loads(read(module_state_path)) if module_state_path.exists() else {'schemaVersion':1,'resources':{}}
        if module_state.get('schemaVersion')!=1 or not isinstance(module_state.get('resources'),dict):
            raise ValueError('Unsupported setup activation state')
        plan=[];same=[];removed=[];retired=[];retired_templates=[];kept_templates=[];folders=[]
        for name in CONTENT_FOLDERS:
            folder=safe(root,name)
            if folder.exists() and not folder.is_dir():raise ValueError('Content folder collides with a file: '+name)
            if not folder.exists():folders.append(name)
        for name,expected in new['files'].items():
            if name in PROTECTED or name.startswith(('.obsidian/','.git/')):raise ValueError('Release tries to replace user settings: '+name)
            src=safe(kit,name);dest=safe(root,name)
            if hash_text(src)!=expected:raise ValueError('Release hash mismatch: '+name)
            if name in managed:continue
            before=old['files'].get(name)
            if not dest.exists():
                prior=module_state['resources'].get(name,{})
                inactive=prior.get('enabled') is False and prior.get('removed') is False and not prior.get('retired')
                deliberate=prior.get('removed') is True
                if inactive or deliberate:
                    # Inactive optional files are absent by design, unlike a
                    # user's deletion. Establish prior ownership before making
                    # a newly shared resource active or preserving a removal.
                    expected=modules.proven_hash(root,name,prior.get('source'),safe,read) if prior.get('retired') else before
                    bank=safe(root,modules.BANK+name)
                    if not expected or not bank.is_file() or hash_text(bank)!=expected or prior.get('bankHash')!=expected:
                        raise ValueError('Module recovery copy differs from its verified source: '+name)
                if deliberate or (before and not inactive):removed.append(name)
                else:plan.append((name,read(src),'add'))
            elif hash_text(dest)==expected or before==expected:same.append(name)
            elif hash_text(dest)==before:plan.append((name,read(src),'replace'))
            else:
                conflict=name+'.fieldbook-new';safe(root,conflict)
                if (root/conflict).exists() and hash_text(root/conflict) not in {expected,before}:
                    raise ValueError('Existing merge candidate would be overwritten: '+conflict)
                plan.append((conflict,read(src),'conflict'))
        for name,h in old['files'].items():
            dest=safe(root,name)
            if name not in new['files'] and dest.exists():
                # Only named obsolete kit files are retired, never a user's notes.
                if (name.endswith('.ps1') or name=='tools/make-manifest.rb') and hash_text(dest)==h:retired.append(name)
                if name in TEMPLATE_RENAMES and TEMPLATE_RENAMES[name] in new['files'] and name not in module_state['resources']:
                    if hash_text(dest)==h:retired_templates.append(name)
                    else:kept_templates.append(name)
        seeds=safe(kit,'tools/starter-seeds.json')
        if seeds.exists():
            seed_data=json.loads(read(seeds))
            for name in ('fieldbook.json','fieldbook_core/jira.json','fieldbook_core/agility.json','fieldbook_core/github.json','fieldbook_core/azure.json','fieldbook_core/canvas.json','fieldbook_core/google.json','fieldbook_core/microsoft.json'):
                if not safe(root,name).exists() and name in seed_data:plan.append((name,seed_data[name],'seed'))
        configuration=safe(root,'fieldbook.json')
        if configuration.exists():configuration_data=json.loads(read(configuration))
        else:
            seeded=next((text for name,text,_ in plan if name=='fieldbook.json'), '{}')
            configuration_data=json.loads(seeded)
        # The unused 0.3.0 placeholder predates named instances and is not editable
        # by the current menu. Recognize only that exact default, never an account.
        jira=safe(root,'fieldbook_core/jira.json')
        legacy_jira={'instances':[{'baseUrl':'REPLACE-JIRA-URL','flavor':'server','tokenVar':'JIRA_TOKEN','email':''}]}
        jira_data=json.loads(read(jira)) if jira.is_file() else None
        if (jira.is_file() and not configuration_data.get('features',{}).get('jira',False)
                and jira_data==legacy_jira):
            legacy_jira['instances'][0].update(id='office',baseUrl='https://REPLACE-JIRA-HOST')
            plan.append(('fieldbook_core/jira.json',dump(legacy_jira),'modernize-unused-jira-placeholder'))
        elif isinstance(jira_data,dict) and isinstance(jira_data.get('instances'),list) and len(jira_data['instances'])==1:
            account=jira_data['instances'][0]
            if (isinstance(account,dict) and 'id' not in account and isinstance(account.get('baseUrl'),str)
                    and account['baseUrl'].startswith('https://') and 'REPLACE' not in account['baseUrl'].upper()):
                # The single-account legacy adapter had an implicit default. Give
                # it the default name used by newer kits without altering details.
                account['id']='office'
                plan.append(('fieldbook_core/jira.json',dump(jira_data),'name-legacy-jira-instance'))
        activation=modules.plan(root,configuration_data,safe,read,write,kit,new,old)
        if resources:
            catalog_data=json.loads(read(safe(kit,modules.CATALOG)))
            for name in catalog_data.get('retiredPaths',[]):
                # Former kit dashboard pages only, never arbitrary user notes.
                if name not in {'Setups/Personal.md','Setups/Work.md','Setups/School.md',
                                'Setups/Work - Individual contributor.md','Setups/Work - People manager.md'}:
                    raise ValueError('Unknown retired setup dashboard: '+name)
                previous=safe(root,name)
                if not previous.exists():continue
                if hash_text(previous)==old['files'].get(name):
                    archived='.fieldbook/modules/retired/'+name;destination=safe(root,archived)
                    if destination.exists() and hash_text(destination)!=hash_text(previous):
                        raise ValueError('Existing retired dashboard recovery copy would be overwritten: '+archived)
                    activation.put(archived,read(previous),'archive-old-dashboard')
                    activation.deletes.append(name)
                else:activation.preserved.append({'path':name,'reason':'Customized old setup dashboard preserved; update any links manually.'})
        applied_path=safe(root,'fieldbook-applied.json');state=json.loads(read(applied_path)) if applied_path.exists() else {'migrations':[]}
        applied=set(state.get('migrations',[]));manual=[];note_edits={};finished=[]
        migrations=sorted((kit/'fieldbook_core/migrations').glob('*.json'))
        for mpath in migrations:
            relative=mpath.relative_to(kit).as_posix()
            if relative not in new['files']:raise ValueError('Migration must be included in the verified manifest')
            m=json.loads(read(mpath));pending=False
            if m['id'] in applied and not backfill:continue
            for path in files(root,notes=True):
                original=note_edits.get(path,path.read_bytes().decode('utf-8'))
                try:changed,issues=migrate_note(original,m,backfill,m['id'] in applied)
                except (ValueError,ImportError) as e:changed=original;issues=[str(e)]
                if issues:pending=True;manual.append({'path':str(path.relative_to(root)),'migration':m['id'],'issues':issues})
                if changed!=original:note_edits[path]=changed
            if not pending:finished.append(m['id'])
        if apply:
            git_guard(root,skip)
            # All names, hashes, merge candidates and migration edits were preflighted above.
            for name in folders:safe(root,name).mkdir(parents=True,exist_ok=True)
            for name,text,action in plan:write(safe(root,name),text)
            for path,text in note_edits.items():write(path,text)
            for name in retired+retired_templates:safe(root,name).unlink()
            activation.apply()
            write(old_path,dump(new));write(safe(root,'VERSION'),new['version']+'\n')
            write(applied_path,dump({'version':new['version'],'migrations':sorted(applied|set(finished))}))
        return {'apply':apply,'version':new['version'],'files':[{'path':n,'action':a} for n,_,a in plan],
                'unchanged':len(same),'user_removed_preserved':removed,'retired_unmodified_powershell':retired,
                'retired_unmodified_templates':retired_templates,'preserved_modified_templates':kept_templates,
                'created_folders':folders,'activation':activation.summary(),
                'note_edits':[str(p.relative_to(root)) for p in note_edits],'manual':manual,
                'note':'Close both apps and back up. Batch is not transactional; user settings and modified old scripts are preserved.'}

def capture(root,text):
    if not text.strip():raise ValueError('Capture text is empty')
    if len(text)>20000:raise ValueError('Capture is limited to 20,000 characters')
    module=notebook_module();v=module.Vault(root)
    try:
        data=v.raw('Inbox.md');before=data.decode('utf-8-sig');expected=module.digest(data)
    except FileNotFoundError:before='# Inbox\n';expected='missing'
    date=module.dt.date.today().isoformat()
    return v.write({'path':'Inbox.md','text':before.rstrip()+'\n\n- '+date+' '+text.strip()+'\n','expected':expected})

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--vault',default=str(ROOT),help='Target vault; defaults to this kit')
    commands=parser.add_subparsers(dest='command',required=True)
    p=commands.add_parser('configure');p.add_argument('--setups');p.add_argument('--work-role',choices=['individual-contributor','people-manager']);p.add_argument('--work-focus');p.add_argument('--work-subrole')
    for name in ('jira','agility','github','azure','canvas','google','microsoft','reviews','auto-people','auto-commit'):p.add_argument('--'+name,choices=['on','off'])
    p.add_argument('--apply',action='store_true')
    commands.add_parser('health')
    p=commands.add_parser('migrate');p.add_argument('--apply',action='store_true');p.add_argument('--skip-git-check',action='store_true')
    p=commands.add_parser('update');p.add_argument('--from',dest='source',required=True);p.add_argument('--apply',action='store_true');p.add_argument('--backfill',action='store_true');p.add_argument('--skip-git-check',action='store_true')
    p=commands.add_parser('capture');p.add_argument('--text',required=True)
    p=commands.add_parser('links');p.add_argument('--target',default='')
    args=parser.parse_args()
    try:
        root=Path(args.vault).resolve(strict=True)
        if args.command=='configure':result=configure(root,args)
        elif args.command=='health':result=health(root)
        elif args.command=='migrate':result=migrate(root,args.apply,args.skip_git_check)
        elif args.command=='update':result=update(root,args.source,args.apply,args.backfill,args.skip_git_check)
        elif args.command=='capture':result=capture(root,args.text)
        else:result=notebook_module().Vault(root).links({'target':args.target})
        print(dump(result))
        if args.command=='health' and result['errors']:sys.exit(1)
    except (OSError,ValueError,KeyError,TypeError,zipfile.BadZipFile) as error:parser.exit(1,'Fieldbook: '+str(error)+'\n')

if __name__=='__main__':main()
