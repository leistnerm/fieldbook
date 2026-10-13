"""Credential references never contain keys or silently fall back to plaintext."""
import importlib.util
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('fieldbook_credentials',ROOT/'fieldbook_core/scripts/credentials.py')
credentials=importlib.util.module_from_spec(spec);spec.loader.exec_module(credentials)

class MemoryStore:
    def __init__(self):self.items={}
    def set_password(self,service,account,value):self.items[(service,account)]=value
    def get_password(self,service,account):return self.items.get((service,account))

class CredentialTests(unittest.TestCase):
    def setUp(self):
        self.backend=MemoryStore();self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name);self.instance={'id':'school','baseUrl':'https://school.example.test','tokenVar':'CANVAS_TOKEN'}
    def test_store_get_status_do_not_write_vault(self):
        credentials.store(self.root,'canvas',self.instance,'fixture-key',self.backend)
        self.assertEqual(credentials.get(self.root,'canvas',self.instance,self.backend),'fixture-key')
        self.assertEqual(credentials.status(self.root,'canvas',self.instance,self.backend),{'available':True,'source':'keyring'})
        self.assertEqual(list(self.root.iterdir()),[])
        self.assertNotIn('fixture-key',str(list(self.backend.items)))
    def test_key_is_bound_to_vault_provider_instance_and_destination(self):
        credentials.store(self.root,'canvas',self.instance,'fixture-key',self.backend)
        for root,provider,instance in [(self.root/'copied','canvas',self.instance),(self.root,'jira',self.instance),
             (self.root,'canvas',{**self.instance,'id':'other'}),(self.root,'canvas',{**self.instance,'baseUrl':'https://another.example.test'})]:
            with self.subTest(instance=instance),self.assertRaises(credentials.CredentialError):
                credentials.get(root,provider,instance,self.backend)
    def test_rejects_unsafe_reference_or_key(self):
        for field,value in [('id','../school'),('baseUrl','http://school.test'),('baseUrl','https://user:key@school.test'),('baseUrl','https://school.test?token=x')]:
            with self.assertRaises(credentials.CredentialError):credentials.store(self.root,'canvas',{**self.instance,field:value},'key',self.backend)
        for token in ['', 'key\nsecret', 'x'*16385]:
            with self.assertRaises(credentials.CredentialError):credentials.store(self.root,'canvas',self.instance,token,self.backend)
        self.assertEqual(self.backend.items,{})
    def test_backend_error_cannot_echo_a_key(self):
        class Broken:
            def set_password(self,*args):raise RuntimeError('sensitive-fixture-key')
            def get_password(self,*args):raise RuntimeError('sensitive-fixture-key')
        for fn in [lambda:credentials.store(self.root,'canvas',self.instance,'secret',Broken()),lambda:credentials.get(self.root,'canvas',self.instance,Broken())]:
            with self.assertRaises(credentials.CredentialError) as caught:fn()
            self.assertNotIn('sensitive-fixture-key',str(caught.exception))
    def test_unavailable_store_fails_without_file_fallback(self):
        with patch.object(credentials,'secure_backend',side_effect=credentials.CredentialError('Unavailable')):
            with self.assertRaises(credentials.CredentialError):credentials.store(self.root,'canvas',self.instance,'key')
        self.assertEqual(list(self.root.iterdir()),[])
    def test_bridge_matches_the_callers_destination_before_any_credential_access(self):
        folder=self.root/'fieldbook_core';folder.mkdir()
        original={**self.instance,'credentialStore':'keyring'}
        file=folder/'canvas.json';file.write_text(json.dumps({'instances':[original]}))
        reference={key:original[key] for key in ('id','baseUrl','tokenVar')}
        self.assertEqual(credentials.configured_instance(self.root,'canvas',reference),original)
        for key,value in [('baseUrl','https://another.example.test'),('tokenVar','CANVAS_OTHER_TOKEN'),('credentialStore','environment')]:
            file.write_text(json.dumps({'instances':[{**original,key:value}]}))
            with patch.object(credentials,'ROOT',self.root),patch.object(credentials.sys,'stdin',io.StringIO(json.dumps({'provider':'canvas','instance':reference}))),patch.object(credentials.sys,'stdout',io.StringIO()) as output,patch.object(credentials,'get',side_effect=AssertionError('must not consult keychain')):
                with self.assertRaises(SystemExit):credentials.main()
            self.assertIn('Credential lookup failed',output.getvalue())
            self.assertNotIn('another.example',output.getvalue())
    def test_bridge_refuses_linked_configuration(self):
        folder=self.root/'fieldbook_core';folder.mkdir()
        original={**self.instance,'credentialStore':'keyring'}
        source=self.root/'external.json';source.write_text(json.dumps({'instances':[original]}))
        (folder/'canvas.json').symlink_to(source)
        reference={key:original[key] for key in ('id','baseUrl','tokenVar')}
        with self.assertRaisesRegex(credentials.CredentialError,'Linked'):
            credentials.configured_instance(self.root,'canvas',reference)
    def test_location_rejects_invalid_ports_and_hidden_url_controls(self):
        for url in ('https://school.example.test:invalid','https://school.example.test:0','https://school.example.test/\x1bpath'):
            with self.assertRaises(credentials.CredentialError):
                credentials.location(self.root,'canvas',{**self.instance,'baseUrl':url})

if __name__=='__main__':unittest.main()
