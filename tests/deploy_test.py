import hashlib
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

spec = importlib.util.spec_from_file_location('deploy', Path(__file__).resolve().parents[1] / 'tools/deploy-vault.py')
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class DeploymentTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.parent = Path(self.temp.name).resolve()
        self.root = self.parent / 'release'
        self.root.mkdir()
        self.target = self.parent / 'new vault'
        self.assets = {'manifest.json': b'{"id":"demo","version":"1.0"}', 'main.js': b'// demo', 'styles.css': b'/* demo */'}
        lock = {'plugins': [{'id':'demo','repo':'example/demo','version':'1.0','release':'https://github.com/example/demo/releases/tag/1.0',
                            'assets':[{'name':k,'url':'https://github.com/example/demo/releases/download/1.0/'+k,'sha256':hashlib.sha256(v).hexdigest()} for k,v in self.assets.items()]}]}
        config = {'setups':[], 'workRole':'individual-contributor','features':{'reviews':False},'defaults':{'area':''}}
        seeds = {'fieldbook.json':json.dumps(config),'Inbox.md':'# Empty inbox\n','opencode.json':'{"share":"disabled"}'}
        profile = {'.obsidian/community-plugins.json':['demo'],'.obsidian/plugins/tasknotes/data.json':{'userFields':[{'key':'area'}]}}
        files = {'tools/starter-plugins.json': json.dumps(lock),'tools/starter-seeds.json':json.dumps(seeds),
                 'tools/starter-settings.json':json.dumps(profile), 'README.md':'Public kit', 'LICENSE':'Public license'}
        for name,text in files.items():
            p=self.root/name;p.parent.mkdir(parents=True,exist_ok=True);p.write_text(text)
        manifest = {'version':'1.0.0','files':{name:hashlib.sha256(text.encode()).hexdigest() for name,text in files.items()}}
        (self.root/'fieldbook-manifest.json').write_text(json.dumps(manifest))
        (self.root/'Inbox.md').write_text('PRIVATE PERSONAL CONTENT')
        (self.root/'opencode.json').write_text('{"token":"private"}')

    def download(self, url):
        return self.assets[url.rsplit('/',1)[-1]]

    def test_preview_does_not_write_or_download(self):
        def fail(url):
            self.fail('Preview must not download')
        result=module.deploy(self.root,self.target,['personal','school'],download=fail)
        self.assertFalse(result['apply'])
        self.assertFalse(self.target.exists())

    def test_new_vault_uses_clean_seeds_and_selected_setup(self):
        module.deploy(self.root,self.target,['work'],'people-manager',True,True,self.download)
        self.assertEqual((self.target/'Inbox.md').read_text(),'# Empty inbox\n')
        self.assertNotIn('private',(self.target/'opencode.json').read_text())
        config=json.loads((self.target/'fieldbook.json').read_text())
        self.assertEqual(config['workRole'],'people-manager')
        self.assertTrue(config['features']['reviews'])
        self.assertEqual(config['defaults']['area'],'work')
        self.assertTrue((self.target/'.obsidian/plugins/demo/main.js').is_file())

    def test_checksum_failure_leaves_no_target_or_stage(self):
        with self.assertRaisesRegex(ValueError,'checksum'):
            module.deploy(self.root,self.target,[],apply=True,download=lambda url:b'corrupted')
        self.assertFalse(self.target.exists())
        self.assertFalse(list(self.parent.glob('.fieldbook-deploy-*')))

    def test_existing_destination_is_never_changed(self):
        self.target.mkdir(); keep=self.target/'keep.md'; keep.write_text('keep')
        with self.assertRaisesRegex(ValueError,'already exists'):
            module.deploy(self.root,self.target,[],apply=True,download=self.download)
        self.assertEqual(keep.read_text(),'keep')

    def test_modified_release_is_refused(self):
        (self.root/'README.md').write_text('changed')
        with self.assertRaisesRegex(ValueError,'damaged release'):
            module.deploy(self.root,self.target,[])

    def test_offline_profile_does_not_mark_absent_plugins_enabled(self):
        module.deploy(self.root,self.target,[],apply=True,plugins=False)
        self.assertEqual(json.loads((self.target/'.obsidian/community-plugins.json').read_text()),[])

    def test_nested_vaults_refused(self):
        with self.assertRaisesRegex(ValueError,'inside'):
            module.deploy(self.root,self.root/'nested',[])

    def test_offline_cache_uses_locked_paths_and_refuses_missing_assets(self):
        cache=self.parent/'cache'; folder=cache/'demo/1.0'; folder.mkdir(parents=True)
        for name,data in self.assets.items():
            (folder/name).write_bytes(data)
        read=module.cached_download(self.root,cache)
        module.deploy(self.root,self.target,[],apply=True,download=read)
        with self.assertRaises(ValueError):
            read('https://example.test/unlisted')
        (folder/'main.js').unlink()
        with self.assertRaises(OSError):
            read('https://github.com/example/demo/releases/download/1.0/main.js')


if __name__ == '__main__':
    unittest.main()
