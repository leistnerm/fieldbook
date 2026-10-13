#!/usr/bin/env python3
"""Portable Fieldbook tools. One JSON request on stdin, or an operation and --json."""
import argparse
import importlib.util
import json
from pathlib import Path
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
LOCAL = ('read','list','search','query','links','overview','today','help','transcript','calendar','preview','write','template_status')
REMOTE = ('tracker_pull','canvas_pull','calendar_pull')
MAX_INPUT = 8 * 1024 * 1024

def module(name, filename):
    spec=importlib.util.spec_from_file_location(name,ROOT/'fieldbook_core/scripts'/filename)
    result=importlib.util.module_from_spec(spec);spec.loader.exec_module(result);return result

def execute(request, *, apply=False):
    if not isinstance(request,dict):raise ValueError('Expected a JSON object')
    operation=request.get('operation')
    if operation=='write' and not apply:
        raise ValueError('Writes require --apply after the user approves the preview. This flag records intent; it is not a security boundary.')
    if operation in LOCAL:
        return module('portable_notebook','notebook.py').Vault(ROOT).run(request)
    if operation=='calendar_pull':
        return module('portable_calendar','calendar_service.py').pull_calendar(ROOT,{k:v for k,v in request.items() if k!='operation'})
    if operation in ('tracker_pull','canvas_pull'):
        node=shutil.which('node')
        if not node:raise ValueError('Tracker and Canvas readers need Node.js 22+ and npm install --omit=dev --ignore-scripts --no-save (run from fieldbook_core). Local notebook tools and calendars use Python.')
        result=subprocess.run([node,str(ROOT/'fieldbook_core/scripts/integration-pull.mjs')],
            input=json.dumps(request),text=True,encoding='utf-8',capture_output=True,timeout=60,cwd=ROOT)
        if len(result.stdout.encode())>2*1024*1024:raise ValueError('Integration response exceeds 2 MiB; narrow the request')
        try:payload=json.loads(result.stdout)
        except ValueError:raise ValueError('Integration reader failed. Check Node.js and fieldbook_core dependencies; no partial results returned.') from None
        if result.returncode or 'error' in payload:raise ValueError(payload.get('error','Integration read failed'))
        return payload
    raise ValueError('Unknown operation')

def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('operation',nargs='?',choices=LOCAL+REMOTE)
    parser.add_argument('--json',dest='payload',help='JSON arguments; alternatively send the request on stdin')
    parser.add_argument('--path',help='Vault-relative note path')
    parser.add_argument('--apply',action='store_true',help='Apply a write already previewed and approved by the user')
    args=parser.parse_args(argv)
    try:
        raw=args.payload if args.payload is not None else (None if args.operation else sys.stdin.buffer.read(MAX_INPUT+1))
        if raw is not None and len(raw)>MAX_INPUT:raise ValueError('Request exceeds 8 MiB')
        request=json.loads(raw) if raw is not None else {}
        if not isinstance(request,dict):raise ValueError('Expected a JSON object')
        if args.operation:request['operation']=args.operation
        if args.path is not None:request['path']=args.path
        print(json.dumps(execute(request,apply=args.apply),ensure_ascii=True));return 0
    except (ValueError,OSError,KeyError,TypeError,subprocess.SubprocessError) as error:
        print(json.dumps({'error':str(error)[:500]}));return 1

if __name__=='__main__':raise SystemExit(main())
