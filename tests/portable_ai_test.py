import importlib.util
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
def load(name,file):
    spec=importlib.util.spec_from_file_location(name,file);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m

class PortableAI(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name)/'Vault with spaces';self.root.mkdir()
        for name in ('fieldbook.json','Inbox.md','AGENTS.md'):shutil.copyfile(ROOT/name,self.root/name)
        (self.root/'Notes').mkdir();(self.root/'tools').mkdir()
        for name in ('notebook.py','mcp-server.py'):shutil.copyfile(ROOT/'tools'/name,self.root/'tools'/name)
        shutil.copytree(ROOT/'fieldbook_core/scripts',self.root/'fieldbook_core/scripts',ignore=shutil.ignore_patterns('__pycache__'))
        self.setup=load('portable_setup_test',ROOT/'tools/ai-setup.py')
        self.api=load('portable_api_test',self.root/'tools/notebook.py')

    def test_default_setup_all_harnesses_has_no_mcp_or_plugins(self):
        p=self.setup.plan(self.root,list(self.setup.HARNESSES));self.setup.apply(self.root,p)
        self.assertFalse((self.root/'.opencode').exists());self.assertFalse((self.root/'.mcp.json').exists())
        self.assertFalse((self.root/'.codex/config.toml').exists())
        self.assertEqual((self.root/'CLAUDE.md').read_text(),'@AGENTS.md\n\n')
        self.assertFalse(self.setup.state(self.root)['mcp'])
        self.assertFalse(self.setup.plan(self.root,list(self.setup.HARNESSES))['changes'])

    def test_mcp_merge_disable_preserves_other_settings(self):
        (self.root/'opencode.json').write_text(json.dumps({'model':'chosen/model','mcp':{'other':{'type':'remote','url':'https://example.com'}}}))
        (self.root/'.codex').mkdir();(self.root/'.codex/config.toml').write_text('model = "chosen"\n')
        harnesses=list(self.setup.HARNESSES)
        p=self.setup.plan(self.root,harnesses,True,True,True);self.setup.apply(self.root,p)
        config=json.loads((self.root/'opencode.json').read_text())
        self.assertEqual(config['model'],'chosen/model');self.assertIn('--allow-writes',config['mcp']['fieldbook']['command'])
        self.assertFalse(self.setup.plan(self.root,harnesses,True,True,True)['changes'])
        self.setup.apply(self.root,self.setup.plan(self.root,harnesses,False))
        config=json.loads((self.root/'opencode.json').read_text());self.assertEqual(set(config['mcp']),{'other'})
        self.assertNotIn('[mcp_servers.fieldbook]',(self.root/'.codex/config.toml').read_text())
        self.assertIn('model = "chosen"',(self.root/'.codex/config.toml').read_text())

    def test_custom_instructions_and_mcp_fail_without_overwrite(self):
        (self.root/'CLAUDE.md').write_text('My existing instructions')
        p=self.setup.plan(self.root,['claude']);self.assertTrue(p['conflicts'])
        with self.assertRaises(ValueError):self.setup.apply(self.root,p)
        self.assertEqual((self.root/'CLAUDE.md').read_text(),'My existing instructions')
        self.assertFalse((self.root/self.setup.STATE).exists())

    def test_stale_setup_preview(self):
        p=self.setup.plan(self.root,['claude']);(self.root/'CLAUDE.md').write_text('Concurrent edit')
        with self.assertRaisesRegex(ValueError,'changed after preview'):self.setup.apply(self.root,p)
        self.assertFalse((self.root/self.setup.STATE).exists())

    def test_links_are_refused(self):
        try:(self.root/'CLAUDE.md').symlink_to(self.root/'Inbox.md')
        except OSError:self.skipTest('Symlinks unavailable')
        with self.assertRaisesRegex(ValueError,'Linked'):self.setup.plan(self.root,['claude'])

    def test_write_requires_explicit_apply_and_current_hash(self):
        request={'operation':'write','path':'Notes/Example.md','text':'A note','expected':'missing'}
        with self.assertRaisesRegex(ValueError,'--apply'):self.api.execute(request)
        self.api.execute({**request,'operation':'preview'})
        self.api.execute(request,apply=True)
        with self.assertRaises(ValueError):self.api.execute(request,apply=True)
        self.assertEqual((self.root/'Notes/Example.md').read_text(),'A note')

    def test_script_rejects_outside_and_settings(self):
        for name in ('../outside.md','fieldbook.json','AGENTS.md','fieldbook_core/scripts/notebook.py'):
            with self.assertRaises(ValueError):self.api.execute({'operation':'write','path':name,'text':'x','expected':'missing'},apply=True)

    def test_json_stdin_and_cli_read(self):
        command=[sys.executable,str(self.root/'tools/notebook.py')]
        result=subprocess.run(command+['read','--path','Inbox.md'],capture_output=True,text=True)
        self.assertEqual(result.returncode,0,result.stdout);self.assertIn('sha256',json.loads(result.stdout))
        result=subprocess.run(command,input=json.dumps({'operation':'today'}),capture_output=True,text=True)
        self.assertIn('date',json.loads(result.stdout))

    def test_launcher_tool_never_installs_and_uses_prepared_python(self):
        launcher=load('portable_launcher_test',ROOT/'fieldbook.py');launcher.ROOT=self.root
        self.assertEqual(launcher.main(['tool','today']),1)
        self.assertFalse((self.root/'fieldbook_core/.venv').exists())
        python=self.root/'fieldbook_core/.venv'/('Scripts/python.exe' if sys.platform=='win32' else 'bin/python')
        python.parent.mkdir(parents=True);python.touch()
        with patch.object(launcher.subprocess,'call',return_value=0) as call:
            self.assertEqual(launcher.main(['tool','read','--path','Inbox.md']),0)
        self.assertEqual(call.call_args.args[0],[str(python),'-B',str(self.root/'tools/notebook.py'),'read','--path','Inbox.md'])

    def test_mcp_wire_default_denies_writes_remote_and_accepts_reads(self):
        requests=[{'jsonrpc':'2.0','id':1,'method':'initialize','params':{'protocolVersion':'2025-06-18'}},
                  {'jsonrpc':'2.0','method':'notifications/initialized'},
                  {'jsonrpc':'2.0','id':2,'method':'tools/list'},
                  {'jsonrpc':'2.0','id':3,'method':'tools/call','params':{'name':'write','arguments':{'path':'Notes/X.md','expected':'missing','text':'x'}}},
                  {'jsonrpc':'2.0','id':4,'method':'tools/call','params':{'name':'read','arguments':{'path':'Inbox.md'}}}]
        p=subprocess.run([sys.executable,str(self.root/'tools/mcp-server.py')],input=''.join(json.dumps(x)+'\n' for x in requests),capture_output=True,text=True)
        replies=[json.loads(x) for x in p.stdout.splitlines()];self.assertEqual(len(replies),4)
        self.assertEqual(replies[0]['result']['protocolVersion'],'2025-06-18')
        names={x['name'] for x in replies[1]['result']['tools']};self.assertNotIn('write',names);self.assertNotIn('tracker_pull',names)
        self.assertTrue(replies[2]['result']['isError']);self.assertFalse(replies[3]['result']['isError']);self.assertFalse((self.root/'Notes/X.md').exists())

    def test_mcp_argument_cannot_override_operation(self):
        server=load('portable_mcp_test',self.root/'tools/mcp-server.py')
        reply=server.dispatch({'method':'tools/call','params':{'name':'read','arguments':{'operation':'write','path':'Inbox.md','text':'x','expected':'missing'}}})
        self.assertTrue(reply['isError'])

    def test_menu_cancel_does_not_create_configuration(self):
        replies=iter(['1','codex,claude','n','','0'])
        self.setup.menu(self.root,ask=lambda _:next(replies),say=lambda _:None)
        self.assertFalse((self.root/'CLAUDE.md').exists());self.assertFalse((self.root/self.setup.STATE).exists())

    def test_old_runtime_archived_and_connections_preserved(self):
        migration=load('portable_migrate_test',ROOT/'tools/migrate-ai-layout.py')
        admin=load('portable_admin_test',ROOT/'tools/manage-vault.py')
        (self.root/'.opencode/plugins').mkdir(parents=True)
        (self.root/'.opencode/plugins/custom.js').write_text('custom plugin')
        raw=json.dumps({'instances':[{'id':'custom','baseUrl':'https://example.com'}]})
        (self.root/'.opencode/jira.json').write_text(raw)
        migration.prepare(self.root,admin)
        self.assertFalse((self.root/'.opencode').exists())
        self.assertEqual((self.root/'fieldbook_core/jira.json').read_text(),raw)
        self.assertEqual((self.root/'.fieldbook/legacy-ai-runtime/plugins/custom.js').read_text(),'custom plugin')

if __name__=='__main__':unittest.main()
