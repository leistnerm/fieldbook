#!/usr/bin/env python3
"""Restore verified local Fieldbook snapshots, retaining the current vault in full."""
from datetime import datetime, timezone
import importlib.util
import json
import os
from pathlib import Path
import re
import shutil
import tempfile
import uuid

spec=importlib.util.spec_from_file_location('restore_snapshot_tools',Path(__file__).with_name('upgrade-vault.py'))
backup_tools=importlib.util.module_from_spec(spec);spec.loader.exec_module(backup_tools)
READY={'backup-verified','upgrade-complete','rolled-back','manual-recovery-needed','restore-complete'}
STATUSES=READY|{'backup-incomplete'}


def absolute(value):
    path=Path(value).expanduser().absolute()
    if path.is_symlink():raise ValueError('Select an ordinary folder, not a linked vault or backup root')
    return path.resolve()


def plain(value,limit=100):
    return isinstance(value,str) and len(value)<=limit and not any(ord(c)<32 or ord(c)==127 for c in value)


def read_receipt(folder):
    """Read both original upgrade receipts and new pre-restore receipts; never execute backup code."""
    path=folder/'receipt.json'
    if path.is_symlink() or not path.is_file() or path.stat().st_size>64*1024*1024:
        raise ValueError('Backup receipt is missing, linked or too large')
    def pairs(values):
        result={}
        for key,value in values:
            if key in result:raise ValueError('Duplicate receipt field')
            result[key]=value
        return result
    try:
        data=json.loads(path.read_bytes(),object_pairs_hook=pairs)
        if data.get('status') not in STATUSES:raise ValueError()
        if not plain(data.get('vault'),32768) or not Path(data['vault']).is_absolute():raise ValueError()
        if not plain(data.get('from')) or not plain(data.get('to')) or not plain(data.get('createdUtc')):raise ValueError()
        if datetime.fromisoformat(data['createdUtc']).tzinfo is None:raise ValueError()
        entries=data['entries']
        if not isinstance(entries,dict) or len(entries)>500000:raise ValueError()
        for name,item in entries.items():
            if not isinstance(name,str) or not name or '\\' in name or ':' in name or '\0' in name or any(p in ('','.', '..') for p in name.split('/')):raise ValueError()
            if not isinstance(item,dict):raise ValueError()
            kind=item.get('kind')
            if kind=='directory':
                if set(item)!={'kind'}:raise ValueError()
            elif kind=='link':
                if set(item)!={'kind','target'} or not isinstance(item['target'],str) or not item['target'] or '\0' in item['target'] or len(item['target'])>32768:raise ValueError()
            elif kind=='file':
                if set(item)!={'kind','bytes','sha256','mode'}:raise ValueError()
                if type(item['bytes']) is not int or item['bytes']<0 or type(item['mode']) is not int or not 0<=item['mode']<=0o7777:raise ValueError()
                if not isinstance(item['sha256'],str) or not re.fullmatch('[0-9a-f]{64}',item['sha256']):raise ValueError()
            else:raise ValueError()
        return data
    except (ValueError,KeyError,TypeError,AttributeError):
        raise ValueError('Backup receipt is invalid or unsupported') from None


def list_backups(directory,root):
    directory=absolute(directory);root=absolute(root)
    if not directory.is_dir():return {'backups':[],'ignored':0,'truncated':False}
    folders=[directory] if (directory/'receipt.json').exists() else sorted(
        [p for p in directory.iterdir() if p.is_dir() and not p.is_symlink()],key=lambda p:p.name,reverse=True)
    found=[];ignored=0
    for folder in folders[:200]:
        try:
            data=read_receipt(folder)
            if Path(data['vault']).resolve()!=root:continue
            valid=data['status'] in READY and (folder/'vault').is_dir() and not (folder/'vault').is_symlink()
            found.append({'folder':str(folder),'createdUtc':data['createdUtc'],'version':data['from'],
                          'kind':data.get('kind') if data.get('kind') in ('pre-restore','standalone') else 'upgrade',
                          'status':data['status'],'selectable':valid})
        except (OSError,ValueError):ignored+=1
    found.sort(key=lambda row:row['createdUtc'],reverse=True)
    return {'backups':found,'ignored':ignored,'truncated':len(folders)>200}


def identity(path):
    if path.is_symlink():raise ValueError('Vault path must be an ordinary folder or a missing original vault')
    if not path.exists():return None
    if not path.is_dir():raise ValueError('Vault path must be an ordinary folder or a missing original vault')
    info=path.stat();return (info.st_dev,info.st_ino)


def snapshot(path):
    if identity(path) is None:return None
    return backup_tools.snapshot(path)


def shown_version(root):
    try:
        path=root/'VERSION'
        if path.is_symlink() or path.stat().st_size>100:return 'unknown'
        value=path.read_text().strip()
        return value if plain(value) else 'unknown'
    except (OSError,ValueError):return 'unknown'


class Restore:
    def __init__(self,root,folder,admin,say=print):
        self.root=absolute(root);self.folder=absolute(folder);self.admin,self.say=admin,say
        if self.root==self.root.parent or not self.root.parent.is_dir():raise ValueError('The original vault parent folder must exist')
        if backup_tools.overlap(self.root,self.folder):raise ValueError('The selected backup must be outside the vault')
        self.data=read_receipt(self.folder)
        if Path(self.data['vault']).resolve()!=self.root:raise ValueError('This backup belongs to a different vault; select its original vault path')
        if self.data['status'] not in READY:raise ValueError('This backup was never verified; it cannot be restored automatically')
        self.saved=self.folder/'vault'
        if self.saved.is_symlink() or not self.saved.is_dir():raise ValueError('Backup vault folder is missing or linked')
        self.expected=self.data['entries'];self.current_id=identity(self.root)
        self.before=snapshot(self.root);self.temp=None;self.safety=None
        self.safety_parent=self.root.parent/(self.root.name+'-fieldbook-backups')
        if self.safety_parent.resolve()!=self.safety_parent or self.safety_parent==self.folder or self.safety_parent.is_relative_to(self.folder):
            raise ValueError('The pre-restore backup folder must be a separate ordinary folder beside the vault')

    def __enter__(self):
        try:
            if backup_tools.snapshot(self.saved)!=self.expected:raise ValueError('Backup contents do not match its receipt; nothing was restored')
            self.say('Verifying the selected backup and preparing a separate restore copy. The current vault is unchanged.')
            # The replacement and parked current vault must stay on the vault filesystem.
            self.temp=tempfile.TemporaryDirectory(prefix='.fieldbook-restore-',dir=self.root.parent)
            self.stage=Path(self.temp.name)/'vault'
            shutil.copytree(self.saved,self.stage,symlinks=True)
            if backup_tools.snapshot(self.stage)!=self.expected:raise ValueError('Prepared restore copy failed verification')
            self.unchanged()
            self.stage_id=identity(self.stage)
            return self
        except BaseException:
            self.__exit__(None,None,None);raise

    def __exit__(self,*args):
        if self.temp:self.temp.cleanup()

    def unchanged(self):
        if identity(self.root)!=self.current_id or snapshot(self.root)!=self.before:
            raise ValueError('Vault changed after the restore preview; close both apps and start again')
        if read_receipt(self.folder)!=self.data or backup_tools.snapshot(self.saved)!=self.expected:
            raise ValueError('Selected backup changed; start the restore again')

    def preview(self):
        before=self.before or {};names=sorted(set(before)|set(self.expected))
        changes=[{'path':name,'action':'add' if name not in before else 'remove from restored vault' if name not in self.expected else 'replace'}
                 for name in names if before.get(name)!=self.expected.get(name)]
        self.changes=changes
        return {'vault':str(self.root),'backup':str(self.folder),'backupDateUtc':self.data['createdUtc'],
                'restoreVersion':self.data['from'],'currentVersion':shown_version(self.root),
                'changedPaths':len(changes),'preview':changes[:50],'morePaths':max(0,len(changes)-50),
                'currentVaultWillBeKeptIn':str(self.safety_parent) if self.before is not None else None,
                'notice':'Restore replaces the whole vault snapshot, including settings and Fieldbook version. Newer notes and edits remain in the separate pre-restore backup; they are not merged.'}

    def receipt(self,status):
        if self.safety:
            self.admin.write(self.safety/'receipt.json',self.admin.dump({
                'status':status,'kind':'pre-restore','vault':str(self.root),'from':self.previous_version,
                'to':self.data['from'],'createdUtc':self.created,'entries':self.before}))

    def prepare_safety(self):
        if self.before is None:return
        self.safety_parent.mkdir(parents=True,exist_ok=True,mode=0o700)
        if self.safety_parent.resolve()!=self.safety_parent or self.safety_parent.stat().st_dev!=self.root.parent.stat().st_dev:
            raise ValueError('Pre-restore backups must be beside the vault on the same filesystem')
        self.safety=self.safety_parent/(datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ-')+uuid.uuid4().hex[:8])
        self.safety.mkdir(mode=0o700);self.created=datetime.now(timezone.utc).isoformat()
        self.previous_version=shown_version(self.root)
        self.receipt('backup-incomplete')
        self.admin.write(self.safety/'RESTORE.txt',
            'This folder retains the entire vault as it was immediately before a restore.\n'
            'To undo that restore, run the latest extracted source kit: python tools/configure.py --restore\n'
            'Select the original vault path and this dated backup folder. Keep both apps closed.\n'
            'For manual recovery, move the current vault aside and copy vault/ to the original path, including hidden files:\n'+str(self.root)+'\n'
            'Do not merge folders. OS credential-store entries are not part of this backup.\n')

    def apply(self):
        self.unchanged()
        if backup_tools.snapshot(self.stage)!=self.expected:raise ValueError('Prepared restore copy changed; nothing was restored')
        if self.before==self.expected:return {'restored':False,'vault':str(self.root),'safetyBackup':None,'version':self.data['from']}
        self.prepare_safety();self.unchanged()
        parked=False
        try:
            if self.before is not None:
                self.say('Keeping the current vault in ' + str(self.safety))
                os.rename(self.root,self.safety/'vault');parked=True
                if identity(self.safety/'vault')!=self.current_id or snapshot(self.safety/'vault')!=self.before:
                    raise ValueError('Current vault changed during preservation')
                self.receipt('backup-verified')
            if self.root.exists() or self.root.is_symlink():raise ValueError('A new path appeared at the original vault location')
            os.rename(self.stage,self.root)
            if identity(self.root)!=self.stage_id or snapshot(self.root)!=self.expected:raise ValueError('Restored vault verification failed')
            if parked and snapshot(self.safety/'vault')!=self.before:raise ValueError('Pre-restore vault changed during restoration')
            self.receipt('restore-complete')
        except BaseException:
            recovered=False
            # Locate the preserved original even when another process replaced the
            # target with a file/link immediately after the first move.
            try:parked=bool(self.safety and identity(self.safety/'vault')==self.current_id and self.current_id is not None)
            except (OSError,ValueError):pass
            try:
                # Infer moves from directory identities, including interruption immediately
                # after a rename but before Python recorded its success.
                if identity(self.root)==self.stage_id and snapshot(self.root)==self.expected:
                    os.rename(self.root,self.stage)
                if parked and not self.root.exists() and not self.root.is_symlink():
                    os.rename(self.safety/'vault',self.root);parked=False
                recovered=identity(self.root)==self.current_id
            except (OSError,ValueError):pass
            try:self.receipt('manual-recovery-needed' if parked else 'backup-incomplete')
            except OSError:pass
            raise ValueError('Restore failed. ' + ('The previous vault was returned to its original location. ' if recovered and self.before is not None
                else 'The original vault path remains missing. ' if recovered else 'Keep the current vault and review recovery manually. ')
                + ('Pre-restore folder: '+str(self.safety)+'. ' if self.safety else '')
                + 'The selected backup is unchanged: '+str(self.folder)) from None
        return {'restored':True,'vault':str(self.root),'safetyBackup':str(self.safety) if self.safety else None,'version':self.data['from']}
