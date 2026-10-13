#!/usr/bin/env python3
"""Local, staged upgrades with verified full-folder backups; invoked by configure.py."""
from contextlib import ExitStack
from datetime import datetime, timezone
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import shutil
import stat
import tempfile
import uuid


def entry(path):
    try:info = path.lstat()
    except FileNotFoundError:return None
    if stat.S_ISLNK(info.st_mode):return {'kind':'link','target':os.readlink(path)}
    if getattr(info,'st_file_attributes',0) & 0x400:
        raise ValueError('A junction/reparse point cannot be backed up safely: ' + str(path))
    if stat.S_ISDIR(info.st_mode):return {'kind':'directory'}
    if not stat.S_ISREG(info.st_mode):raise ValueError('A special file cannot be backed up: ' + str(path))
    digest=hashlib.sha256()
    with path.open('rb') as stream:
        for chunk in iter(lambda:stream.read(1024*1024),b''):digest.update(chunk)
    return {'kind':'file','bytes':info.st_size,'sha256':digest.hexdigest(),'mode':stat.S_IMODE(info.st_mode)}


def snapshot(root):
    """Include hidden files, binaries and links, but never follow a linked directory."""
    result={}
    def failed(error):raise error
    for parent,dirs,names in os.walk(root,followlinks=False,onerror=failed):
        for name in sorted([*dirs,*names]):
            path=Path(parent)/name;value=entry(path)
            if value is None:raise ValueError('Vault changed while it was being inspected; close both apps and retry')
            result[path.relative_to(root).as_posix()]=value
    return result


def version(value):
    match=re.fullmatch(r'(\d+)\.(\d+)\.(\d+)',value.strip())
    if not match:raise ValueError('Use a numbered Fieldbook release, such as 1.0.0')
    return tuple(map(int,match.groups()))


def overlap(a,b):return a==b or a.is_relative_to(b) or b.is_relative_to(a)


def install(source, destination, expected):
    """Copy exact bytes/metadata, checking the destination again before replacement."""
    fd,temporary=tempfile.mkstemp(prefix='.fieldbook-upgrade-',dir=destination.parent)
    os.close(fd)
    try:
        shutil.copy2(source,temporary)
        if entry(destination)!=expected:raise ValueError('A file changed during upgrade: ' + str(destination))
        if expected is None:
            os.link(temporary,destination)  # Exclusive creation; never overwrite a new user file.
        else:os.replace(temporary,destination)
    finally:
        if os.path.exists(temporary):os.unlink(temporary)


def preflight(root, backup_parent, temporary_parent=None):
    """Exercise only a disposable temp directory; inspect real vault without edits."""
    parent=Path(temporary_parent or tempfile.gettempdir()).resolve(strict=True)
    phase='create temporary folder'
    try:
        with tempfile.TemporaryDirectory(prefix='fieldbook-preflight-',dir=parent) as value:
            folder=Path(value);a=folder/'write-test';b=folder/'rename-test'
            phase='write temporary file';a.write_bytes(b'Fieldbook preflight')
            phase='rename temporary file';a.rename(b)
            phase='delete temporary file';b.unlink()
            phase='create and remove temporary directory';(folder/'directory').mkdir();(folder/'directory').rmdir()
    except OSError as error:
        raise ValueError('Upgrade preflight could not '+phase+': '+str(error)+'. Choose an existing writable --temp-dir outside the vault, release and backups.') from error
    before=snapshot(root);size=sum(v.get('bytes',0) for v in before.values())
    backup=Path(backup_parent)
    while not backup.exists():backup=backup.parent
    # Reserve staging plus verified backup on a shared volume, with working headroom.
    volumes={}
    for path,required in ((parent,size*2+64*1024*1024),(backup,size+64*1024*1024)):
        device=path.stat().st_dev
        item=volumes.setdefault(device,{'path':path,'required':0});item['required']+=required
    for item in volumes.values():
        if shutil.disk_usage(item['path']).free<item['required']:
            raise ValueError('Upgrade preflight: insufficient free space for preview and backup at '+str(item['path'])+'; need approximately '+str(item['required'])+' bytes')
    readonly=[name for name,value in before.items() if value['kind']=='file' and not value.get('mode',0)&stat.S_IWUSR]
    return {'temporary_folder':str(parent),'vault_bytes':size,'read_only_files':readonly,
            'notice':'Temporary create/write/rename/delete passed. Read-only files may need manual attention if changed by upgrade; no original permissions were changed.'}


class Upgrade:
    def __init__(self, root, source, backup_parent, admin, say=print, temporary_parent=None):
        self.admin,self.say=admin,say
        self.root=Path(root).expanduser().resolve(strict=True)
        self.source=Path(source).expanduser().resolve(strict=True)
        self.backup_parent=Path(backup_parent).expanduser().resolve()
        if not self.root.is_dir() or not (self.root/'fieldbook-manifest.json').is_file():
            raise ValueError('Select an existing Fieldbook vault with fieldbook-manifest.json')
        if overlap(self.root,self.source):raise ValueError('Keep the release outside the existing vault')
        if overlap(self.root,self.backup_parent) or overlap(self.source,self.backup_parent):
            raise ValueError('Choose a backup folder separate from the vault and release')
        self.temporary_parent=None
        if temporary_parent is not None:
            parent=Path(temporary_parent).expanduser().absolute()
            if not parent.is_dir() or parent.resolve()!=parent or any(p.is_symlink() or (p.exists() and getattr(p.lstat(),'st_file_attributes',0)&0x400) for p in (parent,*parent.parents)):
                raise ValueError('Choose an existing ordinary --temp-dir folder without linked ancestors')
            if any(overlap(parent,p) for p in (self.root,self.source,self.backup_parent)):
                raise ValueError('--temp-dir must be separate from the vault, release and backup folders')
            self.temporary_parent=parent
        self.stack=ExitStack();self.backup=None;self.after=None

    def __enter__(self):
        phase='preflight'
        try:
            self.preflight=preflight(self.root,self.backup_parent,self.temporary_parent)
            self.say('Upgrade preflight passed: '+str(self.preflight['vault_bytes'])+' vault bytes; '+str(len(self.preflight['read_only_files']))+' read-only files.')
            phase='verify release'
            self.kit=self.stack.enter_context(self.admin.verified_release(self.source,self.temporary_parent))
            manifest=json.loads(self.admin.read(self.admin.safe(self.kit,'fieldbook-manifest.json')))
            self.new_version=manifest['version']
            if version(self.new_version)>version((self.admin.ROOT/'VERSION').read_text()):
                raise ValueError('This release is newer than the running upgrader. Extract it and run its tools/configure.py --upgrade')
            if (self.kit/'VERSION').read_text().strip()!=self.new_version:
                raise ValueError('Release VERSION does not match its manifest')
            old=self.root/'VERSION'
            self.old_version=old.read_text().strip() if old.is_file() else 'unknown'
            if self.old_version!='unknown' and version(self.new_version)<version(self.old_version):
                raise ValueError('Downgrades are not supported by the guided upgrade')
            # Verify the whole kit before copying or applying any migration, including modules.
            for name,expected in manifest['files'].items():
                if self.admin.hash_text(self.admin.safe(self.kit,name))!=expected:
                    raise ValueError('Release hash mismatch: ' + name)
            try:__import__('yaml')
            except ImportError:
                raise ValueError('Upgrade requires PyYAML in the Python environment running this command. '
                                 'Install this release\'s fieldbook_core/requirements.txt in that environment, then retry. '
                                 'The vault has not been changed.') from None
            self.before=snapshot(self.root)
            phase='copy vault for preview'
            temp=Path(self.stack.enter_context(tempfile.TemporaryDirectory(prefix='fieldbook-upgrade-',dir=self.temporary_parent)))
            if temp.is_relative_to(self.root):raise ValueError('Temporary workspace must be outside the vault')
            self.stage=temp/'vault'
            self.say('Preparing an upgrade preview in a temporary copy. The existing vault is unchanged.')
            shutil.copytree(self.root,self.stage,symlinks=True)
            if snapshot(self.stage)!=self.before or snapshot(self.root)!=self.before:
                raise ValueError('Vault changed while preparing the preview; close both apps and retry')
            # A path migration is our edit, not a user's customization. Retain the
            # original bytes of pristine kit files that the new release will own;
            # the updater must see that original baseline to replace them normally.
            pristine={}
            if (self.stage/'TaskNotes').exists():
                prior=json.loads(self.admin.read(self.admin.safe(self.stage,'fieldbook-manifest.json')))
                for name,expected in prior['files'].items():
                    destination=name.replace('TaskNotes/Tasks','Tasks').replace('TaskNotes/Views','Views')
                    if destination not in manifest['files'] or destination in self.admin.PROTECTED:continue
                    path=self.admin.safe(self.stage,name)
                    if path.is_file() and self.admin.hash_text(path)==expected:pristine[name]=(destination,path.read_bytes())
            phase='migrate the legacy TaskNotes layout in the preview'
            self.migration=self.admin.migrate(self.stage,apply=True,skip=True)
            for name in self.migration['rewrites']:
                if name in pristine:
                    destination,data=pristine[name]
                    self.admin.safe(self.stage,destination).write_bytes(data)
            phase='prepare portable AI layout in the preview'
            spec=importlib.util.spec_from_file_location('portable_ai_migration',self.admin.ROOT/'tools/migrate-ai-layout.py')
            migration=importlib.util.module_from_spec(spec);spec.loader.exec_module(migration)
            self.ai_layout=migration.prepare(self.stage,self.admin)
            phase='update kit files in the preview'
            self.update=self.admin.update(self.stage,self.kit,apply=True,skip=True,temporary_parent=self.temporary_parent)
            self.config=json.loads(self.admin.read(self.stage/'fieldbook.json'))
            return self
        except BaseException as error:
            # Cleanup errors must not obscure the file/operation that blocked preview.
            try:self.stack.close()
            except OSError as cleanup_error:self.say('Temporary cleanup could not finish: '+str(cleanup_error))
            if isinstance(error,PermissionError):
                raise ValueError('Could not '+phase+': access denied to '+str(error.filename or 'a required file')+
                                 '. The existing vault has not been changed. Close apps using the vault; '
                                 'if the denied path is in your temporary folder, retry with --temp-dir pointing '
                                 'to an existing writable folder outside the vault, release and backups. '
                                 'Original error: '+str(error)) from error
            raise

    def __exit__(self,*args):return self.stack.__exit__(*args)

    def finalize(self, config, arguments):
        selection = self.admin.configure(self.stage,arguments(config,apply=True)) if config!=self.config else None
        self.after=snapshot(self.stage)
        names=sorted(set(self.before)|set(self.after))
        self.changed=[name for name in names if self.before.get(name)!=self.after.get(name)]
        for name in self.changed:
            kinds={v['kind'] for v in (self.before.get(name),self.after.get(name)) if v}
            if 'link' in kinds or len(kinds)>1:raise ValueError('Upgrade would replace a linked path or change a path type: ' + name)
        check=self.admin.health(self.stage)
        if check['errors']:raise ValueError('Staged upgrade did not pass health checks: ' + '; '.join(check['errors']))
        activations=[self.update['activation']]+([selection['activation']] if selection else [])
        preserved={item['path']:item for activation in activations for item in activation.get('preserved_customizations',[])}
        for name in self.update.get('preserved_modified_templates',[]):
            preserved.setdefault(name,{'path':name,'reason':'Customized legacy template preserved.'})
        removals=set(self.update.get('user_removed_preserved',[]))
        for activation in activations:removals.update(activation.get('user_removed_preserved',[]))
        plugin=selection.get('tasknotes_area_default') if selection else None
        if plugin and plugin.get('warning'):check['warnings'].append(plugin['warning'])
        declared=json.loads(self.admin.read(self.stage/'fieldbook-manifest.json'))['files']
        return {'preflight':self.preflight,'from':self.old_version,'to':self.new_version,'files':[
            {'path':name,'action':'add' if name not in self.before else 'remove' if name not in self.after else 'update'}
            for name in self.changed if (self.after.get(name) or self.before[name])['kind']=='file'],
            'healthWarnings':check['warnings'],'manual':self.update['manual'],
            'settings':{key:config.get(key) for key in ('setups','workRole','features','workFocus','workSubrole')},
            'preservedCustomizations':list(preserved.values()),'preservedRemovals':sorted(removals),
            'tasknotesAreaDefault':plugin,
            'mergeCandidates':[name for name in self.after if name.endswith('.fieldbook-new') and name[:-len('.fieldbook-new')] in declared],
            'backupParent':str(self.backup_parent)}

    def receipt(self,status,**extra):
        self.admin.write(self.backup/'receipt.json',self.admin.dump({
            'status':status,'vault':str(self.root),'from':self.old_version,'to':self.new_version,
            'createdUtc':datetime.now(timezone.utc).isoformat(),'entries':self.before,**extra}))

    def make_backup(self):
        if snapshot(self.root)!=self.before:raise ValueError('Vault changed after preview; no upgrade was applied. Reopen the upgrade.')
        self.backup_parent.mkdir(parents=True,exist_ok=True,mode=0o700)
        if self.backup_parent.resolve()!=self.backup_parent or overlap(self.root,self.backup_parent):
            raise ValueError('Backup destination changed; no upgrade was applied')
        self.backup=self.backup_parent/(datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ-')+uuid.uuid4().hex[:8])
        self.backup.mkdir(mode=0o700)
        self.receipt('backup-incomplete')
        try:
            self.say('Copying the entire vault, including hidden folders and attachments, to ' + str(self.backup))
            shutil.copytree(self.root,self.backup/'vault',symlinks=True)
            if snapshot(self.backup/'vault')!=self.before or snapshot(self.root)!=self.before:
                raise ValueError('Backup verification or unchanged-vault check failed')
            self.admin.write(self.backup/'RESTORE.txt',
                'Close Obsidian and OpenCode. From the latest extracted source kit, run: python tools/configure.py --restore\n'
                'Choose the original vault and this dated backup folder. The CLI preserves the current vault before restoring.\n'
                'For manual recovery, keep the current vault by renaming/moving it outside its original path.\n'
                'Copy this backup\'s entire vault folder (including hidden files) to the original location:\n'+str(self.root)+'\n'
                'Do not merge the backup into a partially upgraded folder. Verify your notes before deleting either copy.\n'
                'OS credential-store entries are outside this backup. Keeping the original path preserves their binding.\n'
                'Python environments are machine-specific; reinstall them if restoring on another computer.\n')
            self.receipt('backup-verified')
        except BaseException:
            raise ValueError('Backup could not be verified; no upgrade was applied. Incomplete backup: ' + str(self.backup)) from None
        self.say('Full backup verified. Applying only the reviewed changes.')

    def apply(self):
        if self.after is None:raise ValueError('Preview the final settings before applying')
        if snapshot(self.stage)!=self.after:raise ValueError('Prepared upgrade changed; restart the upgrade')
        if not self.changed:return {'applied':False,'vault':str(self.root),'backup':None,'version':self.new_version}
        self.make_backup()
        if snapshot(self.root)!=self.before:raise ValueError('Vault changed after backup; no upgrade applied. Backup: ' + str(self.backup))
        attempted=[];created=[];removed=[]
        try:
            for name in sorted(self.changed,key=lambda n:(n.count('/'),n)):
                after=self.after.get(name)
                if after and after['kind']=='directory':
                    path=self.admin.safe(self.root,name)
                    if entry(path)!=self.before.get(name):raise ValueError('Directory changed during upgrade')
                    path.mkdir();created.append(name)
                    shutil.copystat(self.stage/name,path)
            for name in self.changed:
                before,after=self.before.get(name),self.after.get(name)
                if (after or before)['kind']!='file':continue
                path=self.admin.safe(self.root,name)
                if entry(path)!=before:raise ValueError('File changed during upgrade: ' + name)
                attempted.append(name)
                if after:install(self.stage/name,path,before)
                else:path.unlink()
            for name in sorted(self.changed,key=lambda n:(-n.count('/'),n)):
                if name not in self.after and self.before[name]['kind']=='directory':
                    self.admin.remove_empty_directory(self.admin.safe(self.root,name));removed.append(name)
            if snapshot(self.root)!=self.after:raise ValueError('Vault changed during the final verification')
            self.receipt('upgrade-complete')
        except BaseException:
            conflicts=[]
            for name in sorted(removed,key=lambda n:n.count('/')):
                try:
                    path=self.admin.safe(self.root,name);path.mkdir()
                    shutil.copystat(self.backup/'vault'/name,path)
                except (OSError,ValueError):conflicts.append(name)
            for name in reversed(attempted):
                try:
                    path=self.admin.safe(self.root,name);current=entry(path)
                    before,after=self.before.get(name),self.after.get(name)
                    if current==before:continue
                    if current!=after:conflicts.append(name);continue
                    if before:install(self.backup/'vault'/name,path,after)
                    else:path.unlink()
                except (OSError,ValueError):conflicts.append(name)
            for name in reversed(created):
                try:self.admin.safe(self.root,name).rmdir()
                except (OSError,ValueError):pass  # Never remove another process's new file.
            try:self.receipt('manual-recovery-needed' if conflicts else 'rolled-back',conflicts=conflicts)
            except OSError:pass
            raise ValueError('Upgrade failed; reviewed file changes were rolled back where unchanged. '
                             + ('Concurrent edits or restore failures need manual review. ' if conflicts else '')
                             + 'Keep the full backup and follow RESTORE.txt if needed: ' + str(self.backup)) from None
        return {'applied':True,'vault':str(self.root),'backup':str(self.backup),'version':self.new_version,
                'mergeCandidates':[n for n in self.changed if n.endswith('.fieldbook-new')]}
