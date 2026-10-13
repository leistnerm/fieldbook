#!/usr/bin/env python3
"""Generate the release's text-file SHA-256 manifest. Packaging utility."""
import hashlib
import json
from pathlib import Path
import sys

PATTERNS = [
 'Everyday workflow.md','Sync previews.md','fieldbook.py','AGENTS.md','README.md','VERSION','Features.md','Cheat Sheet.md','Using AI assistants.md','MCP setup.md','SETUP.md',
 'Setups.md','Skills.md','Obsidian additions.md','Note types.md','Notebook tools.md','START HERE.md',
 'INTEGRATIONS.md','Integration coverage.md','Vault tools.md','Selected intake.md','Calendar meetings.md','Canvas LMS.md','Calendar connections.md','Configuration CLI.md','Optional functionality.md','UPGRADING.md','VALIDATION.md','CHANGELOG.md','Dashboard.md','.gitattributes','.gitignore','LICENSE','NOTICE',
 'Templates/**/*.md','Dashboards/*.md','Setups/*.md','Examples/*.md','Views/*.base','fieldbook_core/scripts/*',
 'fieldbook_core/lib/*','fieldbook_core/commands/*','fieldbook_core/skills/**/*',
 'fieldbook_core/migrations/*','fieldbook_core/package.json','fieldbook_core/requirements*.txt',
 'tools/*','tools/licenses/*','tests/*','package.json',
]
root=Path(sys.argv[1] if len(sys.argv)>1 else Path(__file__).resolve().parents[1]).resolve()
files=sorted({p for pattern in PATTERNS for p in root.glob(pattern) if p.is_file() and not p.is_symlink()
              and p.name!='Review-format.md' and not p.name.endswith(('-default.base','.pyc'))})
version=(root/'VERSION').read_text().strip()
manifest={'version':version,'files':{p.relative_to(root).as_posix():hashlib.sha256(p.read_bytes().decode('utf-8-sig').replace('\r\n','\n').encode()).hexdigest() for p in files}}
(root/'fieldbook-manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
print(f"fieldbook-manifest.json: version {version}, {len(files)} files")
