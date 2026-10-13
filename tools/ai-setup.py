#!/usr/bin/env python3
"""Configure project-local AI instructions and optional harness-launched MCP."""
import argparse
import datetime as dt
import hashlib
import importlib.util
import json
from pathlib import Path
import shutil
import subprocess
import sys

ROOT=Path(__file__).resolve().parents[1]
HARNESSES={'opencode':'OpenCode','claude':'Claude Code','codex':'Codex','cursor':'Cursor',
           'copilot':'GitHub Copilot (VS Code)','gemini':'Gemini CLI','generic':'Other / shared instructions'}
STATE='.fieldbook/ai.json'
GUIDANCE='Read AGENTS.md and AGENTS.local.md before working with this notebook. Use tools/notebook.py for notebook operations as described in Using AI assistants.md. Workflow names are portable requests, not guaranteed slash commands. No AI plugins or MCP are required.\n'

def safe(root,name):
    path=root
    if Path(name).is_absolute() or '..' in Path(name).parts:raise ValueError('Unsafe configuration path')
    for part in Path(name).parts:
        path=path/part
        if path.is_symlink() or path.exists() and (getattr(path.lstat(),'st_file_attributes',0)&0x400 or path.is_file() and path.stat().st_nlink!=1):
            raise ValueError('Linked configuration path refused: '+name)
    return path

def digest(text):return hashlib.sha256(text.encode()).hexdigest()
def text(root,name):
    p=safe(root,name)
    if not p.exists():return None
    if not p.is_file() or p.stat().st_size>1024*1024:raise ValueError('Configuration must be a regular file smaller than 1 MiB: '+name)
    return p.read_text('utf-8-sig')
def state(root):
    raw=text(root,STATE)
    return json.loads(raw) if raw else {'harnesses':[],'mcp':False,'writes':False,'remote':False,'files':{}}

def connection(root,writes=False,remote=False):
    python=root/'fieldbook_core/.venv'/('Scripts/python.exe' if sys.platform=='win32' else 'bin/python')
    if not python.is_file():python=Path(sys.executable).absolute()
    args=['-B',str(root/'tools/mcp-server.py')]
    if writes:args+=['--allow-writes']
    if remote:args+=['--allow-remote']
    return {'command':str(python),'args':args}

def plan(root,harnesses,mcp=False,writes=False,remote=False):
    root=Path(root).resolve(strict=True)
    if not (root/'fieldbook.json').is_file():raise ValueError('Choose a Fieldbook vault root')
    if set(harnesses)-set(HARNESSES):raise ValueError('Unknown harness')
    if (writes or remote) and not mcp:raise ValueError('MCP access flags require MCP enabled')
    old=state(root);desired={};conflicts=[]
    wrappers={'claude':('CLAUDE.md','@AGENTS.md\n\n'),
              'cursor':('.cursor/rules/fieldbook.mdc','---\ndescription: Fieldbook notebook workflows\nalwaysApply: true\n---\n'+GUIDANCE),
              'copilot':('.github/copilot-instructions.md',GUIDANCE),
              'gemini':('GEMINI.md','@./AGENTS.md\n\n')}
    for h in harnesses:
        if h in wrappers:desired[wrappers[h][0]]=wrappers[h][1]
    # Remove only exact previously generated instruction files on deselection.
    for name,proof in old.get('files',{}).items():
        if name not in desired and name in [v[0] for v in wrappers.values()] and digest(text(root,name) or '')==proof:desired[name]=None
    conn=connection(root,writes,remote)
    paths={'opencode':('opencode.json','mcp'),'claude':('.mcp.json','mcpServers'),
           'cursor':('.cursor/mcp.json','mcpServers'),'gemini':('.gemini/settings.json','mcpServers'),
           'copilot':('.vscode/mcp.json','servers'),'generic':('.fieldbook/mcp-connection.json','mcpServers')}
    entries={}
    for h in set(harnesses)|set(old.get('harnesses',[])):
        if h=='codex':continue
        name,key=paths[h];raw=text(root,name);data=json.loads(raw) if raw else {}
        if not isinstance(data,dict) or not isinstance(data.get(key,{}),dict):raise ValueError('Invalid MCP configuration: '+name)
        previous=data.get(key,{}).get('fieldbook')
        wanted=mcp and h in harnesses
        value=({'type':'local','command':[conn['command'],*conn['args']],'enabled':True} if h=='opencode' else
               {**conn,**({'type':'stdio'} if h in ('claude','copilot') else {})}) if wanted else None
        if previous is not None and previous!=old.get('entries',{}).get(h) and previous!=value:
            conflicts.append(name+': existing fieldbook MCP entry is customized; preserved');continue
        if wanted:data.setdefault(key,{})['fieldbook']=value;entries[h]=value
        elif previous is not None:data[key].pop('fieldbook')
        else:continue
        desired[name]=json.dumps(data,indent=2,ensure_ascii=False)+'\n'
    name='.codex/config.toml';raw=text(root,name) or ''
    start='# BEGIN FIELDBOOK MCP\n';end='# END FIELDBOOK MCP\n'
    if 'codex' in harnesses or 'codex' in old.get('harnesses',[]):
        block=old.get('codexBlock','');remaining=raw
        if block and block in raw:remaining=raw.replace(block,'',1)
        elif start in raw:conflicts.append(name+': customized Fieldbook block preserved')
        if '[mcp_servers.fieldbook' in remaining or start in remaining:
            if not any(name in c for c in conflicts):conflicts.append(name+': existing Fieldbook MCP entry preserved')
        else:
            block=''
            if mcp and 'codex' in harnesses:
                block=start+'[mcp_servers.fieldbook]\ncommand = '+json.dumps(conn['command'])+'\nargs = '+json.dumps(conn['args'])+'\nenabled = true\n'+end
                remaining=remaining.rstrip()+'\n\n' if remaining.strip() else ''
            if raw or block:desired[name]=remaining+block
    else:block=old.get('codexBlock','')
    changes={};proofs={}
    for name,new in desired.items():
        current=text(root,name)
        if name in [v[0] for v in wrappers.values()] and current is not None and current!=new and digest(current)!=old.get('files',{}).get(name):
            conflicts.append(name+': customized instructions preserved; add the shared AGENTS.md reference manually');continue
        if new is not None:proofs[name]=digest(new)
        if current!=new:changes[name]={'before':current,'after':new}
    result={'harnesses':sorted(set(harnesses)),'mcp':mcp,'writes':writes,'remote':remote,
            'files':proofs,'entries':entries,'codexBlock':block}
    serialized=json.dumps(result,indent=2,sort_keys=True)+'\n'
    if text(root,STATE)!=serialized:changes[STATE]={'before':text(root,STATE),'after':serialized}
    return {'changes':changes,'conflicts':conflicts,'settings':result}

def apply(root,report):
    root=Path(root).resolve(strict=True)
    if report['conflicts']:raise ValueError('Resolve the listed conflicts before saving; no files changed')
    for name,change in report['changes'].items():
        if text(root,name)!=change['before']:raise ValueError('Configuration changed after preview: '+name)
    if not report['changes']:return None
    stamp=dt.datetime.now(dt.timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
    backup=safe(root,'.fieldbook/ai-backups/'+stamp);backup.mkdir(parents=True)
    (backup/'changes.json').write_text(json.dumps(report['changes'],indent=2)+'\n')
    written=[]
    try:
        for name,change in report['changes'].items():
            path=safe(root,name)
            if text(root,name)!=change['before']:raise ValueError('Configuration changed during save: '+name)
            if change['after'] is None:path.unlink()
            else:path.parent.mkdir(parents=True,exist_ok=True);path.write_text(change['after'],encoding='utf-8')
            written.append(name)
    except Exception:
        for name in reversed(written):
            change=report['changes'][name];path=safe(root,name)
            if text(root,name)!=change['after']:continue
            if change['before'] is None:path.unlink(missing_ok=True)
            else:path.write_text(change['before'],encoding='utf-8')
        raise
    return str(backup)

def check(root):
    root=Path(root).resolve(strict=True);conn=connection(root)
    requests=[{'jsonrpc':'2.0','id':1,'method':'initialize','params':{'protocolVersion':'2025-06-18','capabilities':{},'clientInfo':{'name':'fieldbook-check','version':'1'}}},
              {'jsonrpc':'2.0','method':'notifications/initialized'},
              {'jsonrpc':'2.0','id':2,'method':'tools/list'},
              {'jsonrpc':'2.0','id':3,'method':'tools/call','params':{'name':'read','arguments':{'path':'Inbox.md'}}}]
    r=subprocess.run([conn['command'],*conn['args']],input=''.join(json.dumps(x)+'\n' for x in requests),capture_output=True,text=True,timeout=30)
    replies=[json.loads(line) for line in r.stdout.splitlines()]
    if r.returncode or len(replies)!=3 or any('error' in x for x in replies) or replies[-1]['result'].get('isError'):raise ValueError('MCP self-test failed; check core Python requirements')
    return {'stdio_handshake':'pass','tool_discovery':'pass','local_read':'pass','writes_exposed':False,'remote_exposed':False,
            'note':'Protocol test only; verify discovery and permissions inside your selected harness.'}

def menu(root,ask=input,say=print):
    root=Path(root).resolve(strict=True)
    while True:
        value=ask('\nAI assistants: 1 Configure assistants  2 Check optional MCP server  3 Show manual launch command  0 Back\nChoose: ').strip()
        if value in ('','0'):return
        try:
            if value=='2':say(json.dumps(check(root),indent=2));continue
            if value=='3':say(json.dumps(connection(root),indent=2));say('The MCP client launches and stops stdio with its session. No background service or login autostart is installed.');continue
            if value!='1':continue
            say('Choose any: '+', '.join(HARNESSES)+'. Enter none to remove managed adapters. Default is Python scripts and shared instructions; no plugins.')
            selected=ask('Comma-separated harness IDs (Enter cancels): ').strip()
            if not selected:continue
            selected=[] if selected=='none' else [v.strip() for v in selected.split(',')]
            mcp=bool(selected) and ask('Enable optional harness-launched MCP? y/N: ').strip().lower()=='y'
            writes=mcp and ask('Expose local MCP writes? Configure approval in the harness. y/N: ').strip().lower()=='y'
            remote=mcp and ask('Expose remote read-only integration tools over MCP? y/N: ').strip().lower()=='y'
            report=plan(root,selected,mcp,writes,remote)
            say('Files: '+', '.join(report['changes']));say('MCP starts with the selected harness after its trust approval.' if mcp else 'Python scripts + shared instructions. No MCP or plugins.')
            if report['conflicts']:say('\n'.join(report['conflicts']));continue
            if ask('Type save to apply these local files with a configuration backup: ').strip()=='save':say('Saved. Backup: '+str(apply(root,report)))
        except (ValueError,OSError,subprocess.SubprocessError) as error:say('AI setup: '+str(error))

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--vault',type=Path,default=ROOT);p.add_argument('--check',action='store_true')
    a=p.parse_args()
    if a.check:print(json.dumps(check(a.vault),indent=2))
    else:menu(a.vault)
