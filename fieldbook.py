#!/usr/bin/env python3
"""Prepare Fieldbook's private Python environment, then open configuration."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import venv

ROOT=Path(__file__).resolve().parent
GROUPS={'core':'requirements.txt','calendar':'requirements-credentials.txt','credentials':'requirements-credentials.txt','intake':'requirements-intake.txt'}

def main(argv=None):
    argv=list(sys.argv[1:] if argv is None else argv)
    if argv[:1]==['tool']:
        python=ROOT/'fieldbook_core/.venv'/('Scripts/python.exe' if os.name=='nt' else 'bin/python')
        if not python.is_file():
            print('Run python fieldbook.py once to prepare the Python environment. Tool calls never install packages.',file=sys.stderr)
            return 1
        return subprocess.call([str(python),'-B',str(ROOT/'tools/notebook.py'),*argv[1:]])
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--install',nargs='+',choices=GROUPS,help='Install selected dependency groups; core is always included')
    parser.add_argument('--check',action='store_true',help='Report environment readiness without creating or installing anything')
    parser.add_argument('cli',nargs=argparse.REMAINDER,help='Arguments after -- are passed to configure.py')
    args=parser.parse_args(argv)
    if sys.version_info<(3,10):parser.error('Python 3.10 or newer is required')
    env=ROOT/'fieldbook_core/.venv';python=env/('Scripts/python.exe' if os.name=='nt' else 'bin/python')
    receipt=env/'fieldbook-dependencies.json'
    state=json.loads(receipt.read_text()) if receipt.is_file() else {}
    groups=set(args.install or ['core'])|{'core'}
    # Receipts pin exact selected requirement bytes; dependency checks catch deleted packages.
    fingerprints={g:hashlib.sha256((ROOT/'fieldbook_core'/GROUPS[g]).read_bytes()).hexdigest() for g in groups}
    pending=[g for g in groups if state.get(g)!=fingerprints[g]]
    if python.is_file():
        for group in sorted(groups-set(pending)):
            requirements=[line.strip().split('==',1) for line in (ROOT/'fieldbook_core'/GROUPS[group]).read_text().splitlines() if line.strip() and not line.lstrip().startswith('#')]
            probe="import importlib.metadata as m,json,sys; pairs=json.loads(sys.argv[1]); sys.exit(any(m.version(n)!=v for n,v in pairs))"
            check=subprocess.run([str(python),'-c',probe,json.dumps(requirements)],capture_output=True)
            if check.returncode:pending.append(group)
    if args.check:
        print(json.dumps({'python':str(python),'exists':python.is_file(),'pending':sorted(pending)},indent=2))
        return int(not python.is_file() or bool(pending))
    if not python.is_file():
        print('Creating fieldbook_core/.venv (a folder containing Fieldbook’s Python environment).')
        venv.EnvBuilder(with_pip=True).create(env)
    if pending:
        print('Installing selected dependencies: '+', '.join(sorted(pending))+'. This downloads packages from your configured pip index.')
        command=[str(python),'-m','pip','install']
        for group in sorted(pending):command+=['-r',str(ROOT/'fieldbook_core'/GROUPS[group])]
        subprocess.run(command,check=True)
        state.update(fingerprints);receipt.write_text(json.dumps(state,indent=2)+'\n')
    check=subprocess.run([str(python),'-m','pip','check'])
    if check.returncode:return check.returncode
    extra=args.cli[1:] if args.cli[:1]==['--'] else args.cli
    return subprocess.call([str(python),'-B',str(ROOT/'tools/configure.py'),*(extra or ['--menu'])])

if __name__=='__main__':
    try:raise SystemExit(main())
    except (OSError,ValueError,subprocess.CalledProcessError) as error:
        print('Fieldbook setup: '+str(error),file=sys.stderr);raise SystemExit(1)
