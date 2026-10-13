#!/usr/bin/env python3
"""Explicit standalone snapshots and previewed retention; uses the restore receipt format."""
from datetime import datetime, timezone
import importlib.util
import json
from pathlib import Path
import shutil
import uuid


def load(name):
    spec=importlib.util.spec_from_file_location('backup_'+name,Path(__file__).with_name(name+'.py'))
    mod=importlib.util.module_from_spec(spec);spec.loader.exec_module(mod);return mod

engine=load('upgrade-vault')
restore=load('restore-vault')


def ordinary(value):
    p=Path(value).expanduser().absolute()
    if p.resolve()!=p or any(x.is_symlink() for x in (p,*p.parents)):
        raise ValueError('Choose an ordinary folder without linked ancestors')
    for x in (p,*p.parents):
        if x.exists() and getattr(x.lstat(),'st_file_attributes',0)&0x400:raise ValueError('Reparse folders are not supported')
    return p


def plan(root,directory=None):
    root=ordinary(root)
    if not root.is_dir() or not (root/'fieldbook-manifest.json').is_file():raise ValueError('Select a Fieldbook vault')
    directory=ordinary(directory or root.parent/(root.name+'-fieldbook-backups'))
    if engine.overlap(root,directory):raise ValueError('Backups must be outside the vault')
    entries=engine.snapshot(root)
    return {'vault':str(root),'directory':str(directory),'entries':entries,
            'files':sum(v['kind']=='file' for v in entries.values()),
            'bytes':sum(v.get('bytes',0) for v in entries.values()),'version':restore.shown_version(root)}


def create(preview,admin):
    root=ordinary(preview['vault']);directory=ordinary(preview['directory'])
    if engine.overlap(root,directory) or engine.snapshot(root)!=preview['entries']:raise ValueError('Vault changed after preview; start again')
    directory.mkdir(parents=True,exist_ok=True,mode=0o700)
    ordinary(directory)
    folder=directory/(datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ-')+uuid.uuid4().hex[:8])
    folder.mkdir(mode=0o700)
    receipt={'status':'backup-incomplete','kind':'standalone','vault':str(root),'from':preview['version'],
             'to':preview['version'],'createdUtc':datetime.now(timezone.utc).isoformat(),'entries':preview['entries']}
    admin.write(folder/'receipt.json',admin.dump(receipt))
    try:
        shutil.copytree(root,folder/'vault',symlinks=True)
        if engine.snapshot(folder/'vault')!=preview['entries'] or engine.snapshot(root)!=preview['entries']:
            raise ValueError('Changed while copying')
        admin.write(folder/'RESTORE.txt','Close Obsidian/OpenCode and pause sync. Run a separate source kit: python tools/configure.py --restore\nSelect original vault: '+str(root)+'\nSelect this dated backup. The current vault is preserved before restore.\nOS credential-store entries are not included. Do not merge folders manually.\n')
        receipt['status']='backup-verified';admin.write(folder/'receipt.json',admin.dump(receipt))
        if restore.read_receipt(folder)!=receipt:raise ValueError('Receipt verification failed')
    except BaseException:
        receipt['status']='backup-incomplete'
        try:admin.write(folder/'receipt.json',admin.dump(receipt))
        except OSError:pass
        raise ValueError('Backup was not verified; vault unchanged. Keep incomplete folder for inspection: '+str(folder)) from None
    return {'backup':str(folder),'verified':True,'files':preview['files'],'bytes':preview['bytes']}


def retention(root,directory,keep):
    root=ordinary(root);directory=ordinary(directory)
    if type(keep) is not int or keep<1:raise ValueError('Retain at least one verified backup')
    if engine.overlap(root,directory):raise ValueError('Backup folder overlaps vault')
    found=restore.list_backups(directory,root)
    if found['truncated']:raise ValueError('More than 200 backup folders; review retention manually')
    verified=[];skipped=[]
    for row in found['backups']:
        folder=ordinary(row['folder'])
        try:
            receipt=restore.read_receipt(folder)
            if folder.parent!=directory or not row['selectable'] or engine.snapshot(folder/'vault')!=receipt['entries']:
                raise ValueError('Unverified')
            verified.append({'folder':str(folder),'receipt':receipt})
        except (ValueError,OSError):skipped.append(str(folder))
    return {'vault':str(root),'directory':str(directory),'keep':verified[:keep],'remove':verified[keep:],
            'skipped':skipped,'ignored':found['ignored']}


def prune(preview):
    if not preview['keep']:raise ValueError('No verified recovery copy would remain')
    root=ordinary(preview['vault']);directory=ordinary(preview['directory'])
    if engine.overlap(root,directory):raise ValueError('Backup folder overlaps vault')
    all_rows=preview['keep']+preview['remove']
    if len({r['folder'] for r in all_rows})!=len(all_rows):raise ValueError('Duplicate retention entry')
    # Revalidate every survivor and removal immediately before any deletion.
    for row in all_rows:
        p=ordinary(row['folder'])
        if p.parent!=directory or restore.read_receipt(p)!=row['receipt'] or Path(row['receipt']['vault'])!=root:
            raise ValueError('Backup changed since preview')
        if row['receipt']['status'] not in restore.READY or engine.snapshot(p/'vault')!=row['receipt']['entries']:
            raise ValueError('Backup changed since preview')
    removed=[]
    for row in preview['remove']:
        for survivor in preview['keep']:
            kept=ordinary(survivor['folder'])
            if restore.read_receipt(kept)!=survivor['receipt'] or engine.snapshot(kept/'vault')!=survivor['receipt']['entries']:
                raise ValueError('Retained recovery copy changed; retention stopped')
        p=ordinary(row['folder'])
        if restore.read_receipt(p)!=row['receipt'] or engine.snapshot(p/'vault')!=row['receipt']['entries']:
            raise ValueError('Backup changed during retention')
        shutil.rmtree(p);removed.append(str(p))
    return {'removed':removed,'retained':[r['folder'] for r in preview['keep']]}
