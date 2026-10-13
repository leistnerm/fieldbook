"""Interactive configuration preserves data and keeps credential input off disk."""
import copy
import importlib.util
import io
import json
from pathlib import Path
import tempfile
import unittest
import warnings
from unittest.mock import patch
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('configure_wizard', ROOT/'tools/configure.py')
wizard = importlib.util.module_from_spec(spec);spec.loader.exec_module(wizard)
admin = wizard.admin


class FakeCredentials:
    def __init__(self, fail=False):self.calls=[];self.fail=fail
    def token_value(self, token):
        if not token:raise ValueError('Empty API key')
        return token
    def store(self, root, provider, instance, token):
        if self.fail:raise ValueError('OS credential store unavailable')
        self.calls.append((root, provider, copy.deepcopy(instance), token))


class FakeLinks:
    def __init__(self,kind='course'):
        self.kind=kind;self.planned=[];self.applied=[]
    def list_records(self,root):
        return [{'path':'Projects/History.md','title':'History','kind':self.kind,'sha256':'a'*64,'bindings':{}}]
    def plan_link(self,root,path,provider,instance,remote,*,expected=None):
        self.planned.append((root,path,provider,instance,remote,expected))
        return {'path':path,'provider':provider,'instance':instance,'kind':self.kind,'unchanged':False,
                'changes':[{'field':'canvas_instance','before':None,'after':instance},
                           {'field':'canvas_course_id','before':None,'after':remote['id']}]}
    def apply_link(self,root,plan):
        self.applied.append(copy.deepcopy(plan));return {'path':plan['path'],'sha256':'b'*64,'backup':'.fieldbook/record-backups/test','unchanged':False}


class WizardTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name).resolve()
        self.config={'schemaVersion':1,'setups':['work'],'workRole':'individual-contributor',
                     'features':{name:False for name in wizard.FEATURES},'defaults':{'area':'work'},
                     'workFocus':[],'workSubrole':'','custom':{'keep':'local setting'}}
        self.put('fieldbook.json',admin.dump(self.config))
        for p in wizard.PROVIDERS:self.put('fieldbook_core/'+p+'.json','{"instances": []}\n')
        catalog={'schemaVersion':1,'resources':[
            {'path':'Dashboard.md','navigation':'dashboard'},
            {'path':'Templates/Project - Course.md','setup':'school'},
            {'path':'Templates/Person - Direct report.md','setup':'work','workRole':'people-manager'}]}
        self.put('tools/setup-catalog.json',admin.dump(catalog))
        self.put('Dashboard.md','# Dashboard\n<!-- fieldbook:setup-navigation:start -->\nlinks\n<!-- fieldbook:setup-navigation:end -->\n')
        self.put('Templates/Project - Course.md','# Course\n')
        self.put('Templates/Person - Direct report.md','# Direct report\n')
        self.put('.obsidian/plugins/tasknotes/data.json','{"userFields": [{"key":"area","defaultValue":"work"}]}')
        self.put('Notes/Keep.md','My note\n')
        self.put('fieldbook-manifest.json',admin.dump({'version':'test','files':{
            name:admin.hash_text(self.root/name) for name in ('tools/setup-catalog.json','Dashboard.md','Templates/Project - Course.md','Templates/Person - Direct report.md')}}))
        admin.configure(self.root,wizard.arguments(self.config,True))

    def put(self,name,text):
        path=self.root/name;path.parent.mkdir(parents=True,exist_ok=True);path.write_text(text);return path

    def snapshot(self):return {p.relative_to(self.root).as_posix():p.read_bytes() for p in self.root.rglob('*') if p.is_file()}

    def instance(self,**kwargs):
        return {'id':'my-school','baseUrl':'https://school.example','tokenVar':'CANVAS_TOKEN',
                'credentialStore':'environment','courseIds':['123'],**kwargs}

    def canvas(self,session,**kwargs):
        session.config['setups']=['school'];session.config['features']['canvas']=True
        session.connections['canvas']['instances']=[self.instance(**kwargs)]

    def test_check_has_no_mutations_prompts_credentials_or_network(self):
        before=self.snapshot()
        with patch('builtins.input',side_effect=AssertionError('prompt')),patch.object(wizard.getpass,'getpass',side_effect=AssertionError('secret')),patch('sys.stdout',new_callable=io.StringIO) as out:
            self.assertEqual(wizard.main(['--vault',str(self.root),'--check']),0)
        self.assertIn('passed',out.getvalue());self.assertEqual(self.snapshot(),before)

    def test_preview_switches_are_staged_and_cancel_writes_nothing(self):
        before=self.snapshot();answers=iter(['1','school','4','0']);messages=[]
        self.assertFalse(wizard.Wizard(wizard.Session(self.root),lambda _:next(answers),messages.append).run())
        self.assertEqual(self.snapshot(),before)
        self.assertIn('Setups: school','\n'.join(messages))

    def test_save_preserves_unknowns_notes_customization_and_backs_up_exact_bytes(self):
        self.put('Dashboard.md','My customized dashboard\r\n')
        before=self.snapshot();session=wizard.Session(self.root);self.canvas(session)
        session.connections['canvas']['customMetadata']={'keep':17}
        session.connections['canvas']['instances'][0]['customInstanceOption']='keep'
        preview=session.preview();self.assertFalse(preview['errors']);self.assertEqual(self.snapshot(),before)
        saved=session.commit();self.assertTrue(saved['saved'])
        self.assertEqual((self.root/'Dashboard.md').read_bytes(),before['Dashboard.md'])
        self.assertEqual((self.root/'Notes/Keep.md').read_bytes(),before['Notes/Keep.md'])
        self.assertTrue((self.root/'Templates/Project - Course.md').exists())
        self.assertFalse((self.root/'Templates/Person - Direct report.md').exists())
        config=json.loads((self.root/'fieldbook.json').read_text());self.assertEqual(config['custom'],self.config['custom'])
        self.assertTrue(config['features']['canvas']);self.assertEqual(config['defaults']['area'],'school')
        connections=json.loads((self.root/'fieldbook_core/canvas.json').read_text())
        self.assertEqual(connections['customMetadata'],{'keep':17});self.assertEqual(connections['instances'][0]['customInstanceOption'],'keep')
        backup=self.root/saved['backup'];manifest=json.loads((backup/'restore.json').read_text())
        for name,sha in manifest['files'].items():
            if sha is not None:self.assertEqual((backup/'files'/name).read_bytes(),before[name])
        self.assertIn('Templates/Project - Course.md',manifest['files'])

    def test_save_requires_explicit_confirmation_and_then_masked_key(self):
        session=wizard.Session(self.root);self.canvas(session,credentialStore='keyring')
        session.key_updates.add(('canvas','my-school'));before=self.snapshot();events=[];messages=[]
        answers=iter(['5','save','','0'])
        def ask(prompt):
            answer=next(answers);events.append(answer);return answer
        def secret(prompt):
            self.assertEqual(events,['5','save']);self.assertEqual(self.snapshot(),before)
            events.append('masked');return 'FAKE_TEST_CREDENTIAL'
        credentials=FakeCredentials()
        self.assertTrue(wizard.Wizard(session,ask,messages.append,secret,credentials).run())
        self.assertEqual(len(credentials.calls),1)
        self.assertEqual(credentials.calls[0][0],self.root)
        self.assertEqual(credentials.calls[0][2]['baseUrl'],'https://school.example')
        self.assertNotIn('FAKE_TEST_CREDENTIAL','\n'.join(messages))
        self.assertNotIn(b'FAKE_TEST_CREDENTIAL',b''.join(self.snapshot().values()))

    def test_cancel_at_confirmation_does_not_prompt_or_store_key(self):
        session=wizard.Session(self.root);self.canvas(session,credentialStore='keyring');session.key_updates.add(('canvas','my-school'))
        before=self.snapshot();answers=iter(['5','','0']);credentials=FakeCredentials()
        def secret(_):raise AssertionError('secret input before approval')
        wizard.Wizard(session,lambda _:next(answers),lambda _:None,secret,credentials).run()
        self.assertFalse(credentials.calls);self.assertEqual(self.snapshot(),before)

    def test_store_failure_leaves_all_files_unchanged(self):
        session=wizard.Session(self.root);self.canvas(session,credentialStore='keyring');session.key_updates.add(('canvas','my-school'))
        before=self.snapshot()
        with self.assertRaisesRegex(ValueError,'credential store unavailable'):
            session.commit(lambda _:'FAKE_TEST_CREDENTIAL',FakeCredentials(fail=True))
        self.assertEqual(self.snapshot(),before)

    def test_cancel_during_secret_input_leaves_all_files_unchanged(self):
        session=wizard.Session(self.root);self.canvas(session,credentialStore='keyring');session.key_updates.add(('canvas','my-school'))
        before=self.snapshot()
        def cancel(_):raise KeyboardInterrupt()
        with self.assertRaises(KeyboardInterrupt):session.commit(cancel,FakeCredentials())
        self.assertEqual(self.snapshot(),before)

    def test_getpass_echo_fallback_refused_before_key_read_or_writes(self):
        session=wizard.Session(self.root);self.canvas(session,credentialStore='keyring');session.key_updates.add(('canvas','my-school'))
        before=self.snapshot();credentials=FakeCredentials()
        def insecure_prompt(_):
            warnings.warn('Password may be echoed',wizard.getpass.GetPassWarning)
            self.fail('must stop before fallback reads plaintext')
        with self.assertRaisesRegex(ValueError,'interactive terminal'):session.commit(insecure_prompt,credentials)
        self.assertFalse(credentials.calls);self.assertEqual(self.snapshot(),before)

    def test_credential_only_rotation_reports_success_without_config_backup(self):
        session=wizard.Session(self.root);self.canvas(session,credentialStore='keyring');session.commit()
        session=wizard.Session(self.root);session.key_updates.add(('canvas','my-school'));before=self.snapshot()
        credentials=FakeCredentials();result=session.commit(lambda _:'FAKE_ROTATED_KEY',credentials)
        self.assertTrue(result['saved']);self.assertIsNone(result['backup']);self.assertEqual(result['credentialsUpdated'],1)
        self.assertIn('Updated 1 OS credential',result['message']);self.assertEqual(self.snapshot(),before)

    def test_partial_key_store_failure_and_later_cancel_report_prior_side_effects(self):
        session=wizard.Session(self.root);self.canvas(session,credentialStore='keyring')
        session.connections['canvas']['instances'].append(self.instance(id='other-school',credentialStore='keyring'))
        session.key_updates.update([('canvas','my-school'),('canvas','other-school')])
        credentials=FakeCredentials();real_store=credentials.store
        def store(root,provider,instance,token):
            if credentials.calls:raise ValueError('failed')
            real_store(root,provider,instance,token)
        credentials.store=store;before=self.snapshot();answers=iter(['5','save','0']);messages=[]
        wizard.Wizard(session,lambda _:next(answers),messages.append,lambda _:'FAKE_TEST_CREDENTIAL',credentials).run()
        self.assertEqual(len(credentials.calls),1);self.assertEqual(self.snapshot(),before)
        self.assertIn('may already have changed','\n'.join(messages))
        self.assertNotIn('vault files and credentials were not changed','\n'.join(messages))
        self.assertEqual(session.key_updates,{('canvas','other-school')})

    def test_activation_partial_failure_rolls_back_original_bytes(self):
        session=wizard.Session(self.root);session.config['setups']=['school'];before=self.snapshot()
        original=admin.configure
        def failing(root,args):
            if args.apply:
                original(root,args)
                raise OSError('simulated interrupted save')
            return original(root,args)
        with patch.object(admin,'configure',side_effect=failing):
            with self.assertRaisesRegex(ValueError,'original configuration was restored'):session.commit()
        after=self.snapshot();after={k:v for k,v in after.items() if not k.startswith('.fieldbook/config-backups/')}
        self.assertEqual(after,before)

    def test_conflicting_external_change_refuses_before_credentials_and_writes(self):
        session=wizard.Session(self.root);self.canvas(session,credentialStore='keyring');session.key_updates.add(('canvas','my-school'))
        self.put('fieldbook.json',admin.dump({**self.config,'external':'changed'}));before=self.snapshot()
        with self.assertRaisesRegex(ValueError,'changed during editing'):session.commit(lambda _:self.fail('should not prompt'))
        self.assertEqual(self.snapshot(),before)

    def test_edited_module_during_session_refuses_and_preserves_edit(self):
        session=wizard.Session(self.root);session.config['setups']=['school']
        self.put('Dashboard.md','Concurrent custom content');before=self.snapshot()
        with self.assertRaisesRegex(ValueError,'changed during editing'):session.commit()
        self.assertEqual(self.snapshot(),before)

    def test_canvas_gate_invalid_url_duplicate_ids_and_mapping_fail_without_writes(self):
        cases=[('outside school',lambda s:s.config['features'].update(canvas=True)),
               ('url',lambda s:s.connections['canvas']['instances'][0].update(baseUrl='https://school.example/path')),
               ('literal token',lambda s:s.connections['canvas']['instances'][0].update(token='FAKE_TEST_SECRET')),
               ('duplicate',lambda s:s.connections['canvas']['instances'].append(self.instance())),
               ('map',lambda s:s.connections['canvas']['instances'][0].update(tokenVar='not a variable'))]
        for label,change in cases:
            with self.subTest(case=label):
                session=wizard.Session(self.root)
                if label!='outside school':self.canvas(session)
                change(session);before=self.snapshot()
                self.assertTrue(session.preview()['errors'])
                with self.assertRaisesRegex(ValueError,'validation'):session.commit()
                self.assertEqual(self.snapshot(),before)

    def test_remove_school_disables_canvas_and_keeps_connection(self):
        session=wizard.Session(self.root);self.canvas(session);session.commit()
        session=wizard.Session(self.root);answers=iter(['work','people-manager','',''])
        wizard.Wizard(session,lambda _:next(answers),lambda _:None).setups()
        self.assertFalse(session.config['features']['canvas']);self.assertTrue(session.config['features']['reviews'])
        session.commit();self.assertTrue((self.root/'Templates/Person - Direct report.md').exists())
        self.assertEqual(json.loads((self.root/'fieldbook_core/canvas.json').read_text())['instances'][0]['id'],'my-school')

    def test_interactive_add_edit_remove_preserves_other_provider_and_unknown_keys(self):
        session=wizard.Session(self.root)
        answers=iter(['canvas','add','my-school','https://school.example','','123,456','environment'])
        wizard.Wizard(session,lambda _:next(answers),lambda _:None).integrations()
        self.assertEqual(session.connections['canvas']['instances'][0]['courseIds'],['123','456'])
        session.connections['canvas']['instances'][0]['custom']='keep'
        answers=iter(['canvas','edit my-school','https://new.example','','456','environment'])
        wizard.Wizard(session,lambda _:next(answers),lambda _:None).integrations()
        self.assertEqual(session.connections['canvas']['instances'][0]['custom'],'keep')
        answers=iter(['canvas','remove my-school','remove'])
        wizard.Wizard(session,lambda _:next(answers),lambda _:None).integrations()
        self.assertEqual(session.connections['canvas']['instances'],[])
        self.assertEqual(session.connections['jira'],session.original_connections['jira'])

    def test_keyring_endpoint_change_requires_new_key_not_implicit_old_key(self):
        self.put('fieldbook_core/canvas.json',admin.dump({'instances':[self.instance(credentialStore='keyring')]}))
        session=wizard.Session(self.root)
        answers=iter(['canvas','edit my-school','https://other.example','','',''])
        wizard.Wizard(session,lambda _:next(answers),lambda _:None).integrations()
        self.assertEqual(session.key_updates,{('canvas','my-school')})
        self.assertEqual(session.connections['canvas']['instances'][0]['baseUrl'],'https://other.example')

    def test_unknown_fields_not_printed_and_plaintext_secrets_refused(self):
        session=wizard.Session(self.root);self.canvas(session)
        session.connections['canvas']['instances'][0]['customPrivateDetail']='PRIVATE_VALUE_NOT_FOR_PREVIEW'
        messages=[];wizard.Wizard(session,say=messages.append).preview()
        self.assertNotIn('PRIVATE_VALUE_NOT_FOR_PREVIEW','\n'.join(messages))
        session.connections['canvas']['instances'][0]['apiKey']='FAKE_TEST_SECRET';messages=[]
        wizard.Wizard(session,say=messages.append).preview()
        self.assertNotIn('FAKE_TEST_SECRET','\n'.join(messages));self.assertTrue(session.validate()['errors'])

    def test_unsafe_urls_do_not_echo_credentials(self):
        for value in ('http://school.example','https://user:FAKE_TEST_SECRET@school.example','https://school.example?token=FAKE_TEST_SECRET','https://school.example/#FAKE_TEST_SECRET'):
            with self.subTest(url=value):
                with self.assertRaises(ValueError) as error:wizard.clean_url(value,'canvas')
                self.assertNotIn('FAKE_TEST_SECRET',str(error.exception))

    def test_linked_configuration_refused(self):
        external=self.root/'outside.json';external.write_text('{"instances": []}')
        target=self.root/'fieldbook_core/canvas.json';target.unlink();target.symlink_to(external)
        with self.assertRaisesRegex(ValueError,'Linked'):wizard.Session(self.root)

    def diagnostic(self,ok=True,status='pass'):
        return {'provider':'canvas','instance':'my-school','ok':ok,'checks':[
            {'stage':'url','status':'pass','message':'Configured HTTPS origin accepted.'},
            {'stage':'authentication','status':'pass','message':'Authenticated request succeeded.'},
            {'stage':'scope','status':status,'message':'Configured course read succeeded.' if status=='pass' else 'Select a course to verify read scope.'}]}

    def save_connection(self,provider='canvas',**kwargs):
        self.put('fieldbook_core/'+provider+'.json',admin.dump({'instances':[self.instance(**kwargs)]}))

    def test_explicit_connection_checks_saved_config_even_while_feature_disabled(self):
        self.save_connection();before=self.snapshot();calls=[]
        def check(root,provider,identity):
            calls.append((root,provider,identity));return self.diagnostic()
        result=wizard.test_connections(self.root,'canvas','my-school',check)
        self.assertEqual(calls,[(self.root,'canvas','my-school')]);self.assertEqual(result['status'],'passed')
        self.assertTrue(result['ok']);self.assertEqual(result['exitCode'],0)
        self.assertFalse(json.loads((self.root/'fieldbook.json').read_text())['features']['canvas'])
        self.assertEqual(self.snapshot(),before)

    def test_all_skips_empty_and_placeholder_connections_without_accessing_credentials(self):
        self.save_connection(baseUrl='https://REPLACE-CANVAS-HOST');before=self.snapshot()
        result=wizard.test_connections(self.root,'all',checker=lambda *_:self.fail('no remote test for placeholders'))
        self.assertEqual(result['verified'],0);self.assertEqual(result['skipped'],len(wizard.PROVIDERS))
        self.assertEqual(result['status'],'not_verified');self.assertFalse(result['ok']);self.assertEqual(result['exitCode'],2)
        self.assertEqual(self.snapshot(),before)

    def test_explicit_unconfigured_test_returns_not_verified_and_nonzero(self):
        for configured in (False,True):
            if configured:self.save_connection(baseUrl='https://REPLACE-CANVAS-HOST')
            result=wizard.test_connections(self.root,'canvas',checker=lambda *_:self.fail('not configured'))
            self.assertEqual(result['notVerified'],1);self.assertEqual(result['exitCode'],2);self.assertFalse(result['ok'])

    def test_missing_scope_and_failures_are_distinct_and_no_extra_payload_printed(self):
        self.save_connection()
        unknown=wizard.test_connections(self.root,'canvas',checker=lambda *_:self.diagnostic(False,'skip'))
        self.assertEqual(unknown['notVerified'],1);self.assertEqual(unknown['exitCode'],2)
        response={**self.diagnostic(False,'fail'),'token':'FAKE_PRIVATE_TOKEN','remoteResponse':'FAKE_RESPONSE_BODY'}
        failure=wizard.test_connections(self.root,'canvas',checker=lambda *_:response)
        self.assertEqual(failure['failed'],1);self.assertEqual(failure['exitCode'],1)
        self.assertNotIn('FAKE_PRIVATE_TOKEN',json.dumps(failure));self.assertNotIn('FAKE_RESPONSE_BODY',json.dumps(failure))

    def test_optional_identity_unknown_does_not_override_verified_protected_read(self):
        self.save_connection('agility',id='office',tokenVar='AGILITY_TOKEN',baseUrl='https://agility.example/instance')
        response=self.diagnostic();response['checks'].append({'stage':'identity','status':'unknown','message':'Protected scope read verified access; no additional identity permission requested.'})
        result=wizard.test_connections(self.root,'agility',checker=lambda *_:response)
        self.assertTrue(result['ok']);self.assertEqual(result['verified'],1);self.assertEqual(result['exitCode'],0)

    def test_all_skips_default_github_but_explicit_test_can_check_authentication(self):
        self.put('fieldbook_core/github.json',(ROOT/'fieldbook_core/github.json').read_text())
        result=wizard.test_connections(self.root,'all',checker=lambda *_:self.fail('default GitHub connection is unconfigured'))
        self.assertEqual(result['skipped'],len(wizard.PROVIDERS));self.assertEqual(result['exitCode'],2)
        calls=[]
        def check(*args):calls.append(args);return self.diagnostic(False,'skip')
        result=wizard.test_connections(self.root,'github',checker=check)
        self.assertEqual(len(calls),1);self.assertEqual(result['notVerified'],1)

    def test_diagnostic_exceptions_never_echo_api_keys_or_response_body(self):
        self.save_connection()
        def broken(*_):raise RuntimeError('Authorization: Bearer FAKE_PRIVATE_TOKEN server private response')
        result=wizard.test_connections(self.root,'canvas',checker=broken)
        self.assertEqual(result['exitCode'],1);self.assertNotIn('FAKE_PRIVATE_TOKEN',json.dumps(result))
        self.assertNotIn('private response',json.dumps(result))

    def test_duplicate_connections_refused_before_any_remote_check(self):
        self.put('fieldbook_core/canvas.json',admin.dump({'instances':[self.instance(),self.instance()]}))
        result=wizard.test_connections(self.root,'canvas',checker=lambda *_:self.fail('ambiguous identity'))
        self.assertGreater(result['failed'],0);self.assertEqual(result['exitCode'],1)

    def test_menu_checks_refuse_pending_edits_and_use_saved_config_only(self):
        self.save_connection();session=wizard.Session(self.root);self.canvas(session)
        session.connections['canvas']['instances'][0]['baseUrl']='https://unsaved.example'
        before=self.snapshot();ui=wizard.Wizard(session,ask=lambda _:self.fail('must not ask which remote endpoint'),connection_checker=lambda *_:self.fail('must not test staged values'))
        with self.assertRaisesRegex(ValueError,'Save or cancel'):ui.test_saved()
        self.assertEqual(self.snapshot(),before)

    def test_menu_six_prints_stages_and_does_not_write_configuration(self):
        self.save_connection();before=self.snapshot();answers=iter(['6','canvas','my-school','0']);messages=[];calls=[]
        def check(*args):calls.append(args);return self.diagnostic()
        wizard.Wizard(wizard.Session(self.root),lambda _:next(answers),messages.append,connection_checker=check).run()
        self.assertEqual(len(calls),1);self.assertIn('authentication — pass','\n'.join(messages))
        self.assertIn('scope — pass','\n'.join(messages));self.assertEqual(self.snapshot(),before)

    def test_post_save_connection_test_defaults_no(self):
        session=wizard.Session(self.root);self.canvas(session);answers=iter(['5','save','','0'])
        wizard.Wizard(session,lambda _:next(answers),lambda _:None,connection_checker=lambda *_:self.fail('test must be opt in')).run()
        self.assertTrue(json.loads((self.root/'fieldbook.json').read_text())['features']['canvas'])

    def test_post_save_connection_test_uses_new_saved_url(self):
        session=wizard.Session(self.root);self.canvas(session);answers=iter(['5','save','y','canvas','my-school','0']);calls=[]
        def check(root,provider,identity):
            data=json.loads((root/'fieldbook_core/canvas.json').read_text())
            calls.append((provider,identity,data['instances'][0]['baseUrl']));return self.diagnostic()
        self.assertTrue(wizard.Wizard(session,lambda _:next(answers),lambda _:None,connection_checker=check).run())
        self.assertEqual(calls,[('canvas','my-school','https://school.example')])

    def test_cancel_post_save_test_preserves_success_and_does_not_claim_cancelled_save(self):
        session=wizard.Session(self.root);self.canvas(session);answers=iter(['5','save','y']);messages=[]
        def ask(_):
            try:return next(answers)
            except StopIteration:raise KeyboardInterrupt()
        self.assertTrue(wizard.Wizard(session,ask,messages.append).run())
        self.assertIn('Settings were saved; the optional connection test was cancelled.','\n'.join(messages))
        self.assertTrue(json.loads((self.root/'fieldbook.json').read_text())['features']['canvas'])

    def test_cli_test_interrupt_is_not_described_as_cancelled_configuration_save(self):
        with patch.object(wizard,'test_connections',side_effect=KeyboardInterrupt()),patch('sys.stdout',new_callable=io.StringIO) as out:
            self.assertEqual(wizard.main(['--vault',str(self.root),'--test','all']),1)
        self.assertIn('Connection testing cancelled',out.getvalue());self.assertNotIn('before save',out.getvalue())

    def test_cli_test_outputs_structured_results_with_exit_status_and_check_stays_offline(self):
        self.save_connection();before=self.snapshot()
        with patch.object(wizard,'test_connections',return_value={'status':'not_verified','exitCode':2,'results':[]}) as check,patch('sys.stdout',new_callable=io.StringIO) as out:
            self.assertEqual(wizard.main(['--vault',str(self.root),'--test','canvas','--instance','my-school']),2)
        self.assertEqual(json.loads(out.getvalue())['status'],'not_verified')
        check.assert_called_once_with(str(self.root),'canvas','my-school')
        with patch.object(wizard,'test_connections',side_effect=AssertionError('check must remain offline')),patch('sys.stdout',new_callable=io.StringIO):
            self.assertEqual(wizard.main(['--vault',str(self.root),'--check']),0)
        self.assertEqual(self.snapshot(),before)

    def test_cli_rejects_check_test_combination_and_instance_without_named_provider(self):
        for arguments in (['--check','--test','all'],['--instance','my-school'],['--test','all','--instance','my-school']):
            with patch('sys.stderr',new_callable=io.StringIO):
                with self.assertRaises(SystemExit) as error:wizard.main(arguments)
            self.assertEqual(error.exception.code,2)

    def projects(self):
        return {'readOnly':True,'choices':[
            {'id':'12','label':'History — Spring','settings':{'courseIds':['12']}},
            {'id':'34','label':'Calculus — Spring','settings':{'courseIds':['34']}}],
            'truncated':False,'notice':'First bounded page only.'}

    def test_choose_scope_stages_selection_until_save_and_does_not_enable_feature(self):
        self.save_connection();session=wizard.Session(self.root);before=self.snapshot();answers=iter(['canvas','1','2','replace','use']);calls=[]
        def discover(root,provider,identity):calls.append((root,provider,identity));return self.projects()
        wizard.Wizard(session,lambda _:next(answers),lambda _:None,project_discoverer=discover).choose_project()
        self.assertEqual(calls,[(self.root,'canvas','my-school')])
        self.assertEqual(session.connections['canvas']['instances'][0]['courseIds'],['34'])
        self.assertEqual(self.snapshot(),before);self.assertFalse(session.config['features']['canvas'])
        session.commit()
        self.assertEqual(json.loads((self.root/'fieldbook_core/canvas.json').read_text())['instances'][0]['courseIds'],['34'])
        self.assertFalse(json.loads((self.root/'fieldbook.json').read_text())['features']['canvas'])

    def test_numbered_provider_and_instance_choices_work_without_typing_ids(self):
        self.save_connection();session=wizard.Session(self.root);answers=iter(['5','1','1','','use']);messages=[]
        wizard.Wizard(session,lambda _:next(answers),messages.append,project_discoverer=lambda *_:self.projects()).choose_project()
        self.assertIn('5 Canvas LMS',messages);self.assertIn('1 my-school: https://school.example',messages)
        self.assertEqual(session.connections['canvas']['instances'][0]['courseIds'],['12'])
        ui=wizard.Wizard(wizard.Session(self.root),lambda _:str(len(wizard.PROVIDERS)+1),lambda _:None)
        self.assertEqual(ui.provider_choice('Test',include_all=True),'all')

    def test_choose_scope_decline_keeps_existing_scope_and_shows_replacement(self):
        self.save_connection();session=wizard.Session(self.root);before=copy.deepcopy(session.connections);messages=[]
        answers=iter(['canvas','my-school','1','replace',''])
        wizard.Wizard(session,lambda _:next(answers),messages.append,project_discoverer=lambda *_:self.projects()).choose_project()
        self.assertEqual(session.connections,before)
        self.assertIn('Current courseIds: ["123"]','\n'.join(messages));self.assertIn('Proposed courseIds: ["12"]','\n'.join(messages))

    def test_choose_scopes_can_add_and_deduplicate_selected_courses(self):
        self.save_connection(courseIds=['12']);session=wizard.Session(self.root);answers=iter(['canvas','1','1,2,1','add','use'])
        wizard.Wizard(session,lambda _:next(answers),lambda _:None,project_discoverer=lambda *_:self.projects()).choose_project()
        self.assertEqual(session.connections['canvas']['instances'][0]['courseIds'],['12','34'])

    def test_scope_picker_rejects_unsaved_connections_before_discovery(self):
        session=wizard.Session(self.root);self.canvas(session)
        ui=wizard.Wizard(session,ask=lambda _:self.fail('must require save'),project_discoverer=lambda *_:self.fail('must not discover staged endpoint'))
        with self.assertRaisesRegex(ValueError,'Save or cancel'):ui.choose_project()

    def test_scope_picker_cannot_modify_credentials_or_other_settings(self):
        self.save_connection();session=wizard.Session(self.root);before=copy.deepcopy(session.connections);answers=iter(['canvas','1'])
        result=self.projects();result['choices'][0]['settings']['tokenVar']='CANVAS_OTHER_TOKEN'
        with self.assertRaisesRegex(ValueError,'unsupported scope'):
            wizard.Wizard(session,lambda _:next(answers),lambda _:None,project_discoverer=lambda *_:result).choose_project()
        self.assertEqual(session.connections,before)

    def test_empty_truncated_scope_listing_keeps_manual_settings(self):
        self.save_connection();session=wizard.Session(self.root);before=copy.deepcopy(session.connections);answers=iter(['canvas','1']);messages=[]
        result={'choices':[],'truncated':True,'notice':'no project metadata'}
        wizard.Wizard(session,lambda _:next(answers),messages.append,project_discoverer=lambda *_:result).choose_project()
        self.assertEqual(session.connections,before)
        self.assertIn('Existing settings were kept','\n'.join(messages));self.assertIn('first bounded page','\n'.join(messages))

    def test_discovery_errors_do_not_echo_api_keys(self):
        self.save_connection();session=wizard.Session(self.root);answers=iter(['canvas','1'])
        def fail(*_):raise ValueError('Server echoed FAKE_PRIVATE_KEY')
        with self.assertRaises(ValueError) as error:
            wizard.Wizard(session,lambda _:next(answers),lambda _:None,project_discoverer=fail).choose_project()
        self.assertNotIn('FAKE_PRIVATE_KEY',str(error.exception))

    def test_save_stays_in_menu_for_scope_selection_and_optional_testing(self):
        session=wizard.Session(self.root);self.canvas(session);calls=[];messages=[]
        answers=iter(['5','save','','7','canvas','1','2','replace','use','5','save','y','canvas','my-school','0'])
        def discover(root,provider,identity):
            self.assertTrue((root/'fieldbook_core/canvas.json').exists());return self.projects()
        def check(root,provider,identity):
            calls.append(json.loads((root/'fieldbook_core/canvas.json').read_text())['instances'][0]['courseIds']);return self.diagnostic()
        self.assertTrue(wizard.Wizard(session,lambda _:next(answers),messages.append,connection_checker=check,project_discoverer=discover).run())
        self.assertEqual(calls,[['34']]);self.assertIn('Earlier saved settings','\n'.join(messages))
        self.assertEqual(json.loads((self.root/'fieldbook_core/canvas.json').read_text())['instances'][0]['courseIds'],['34'])

    def test_interactive_connection_tests_show_progress_before_request(self):
        self.save_connection();answers=iter(['canvas','my-school']);messages=[]
        def check(*_):
            self.assertEqual(messages[-1],'Testing canvas/my-school...');return self.diagnostic()
        wizard.Wizard(wizard.Session(self.root),lambda _:next(answers),messages.append,connection_checker=check).test_saved()

    def test_eof_after_save_exits_truthfully_and_preserves_saved_settings(self):
        session=wizard.Session(self.root);self.canvas(session);answers=iter(['5','save','']);messages=[]
        def ask(_):
            try:return next(answers)
            except StopIteration:raise EOFError()
        self.assertTrue(wizard.Wizard(session,ask,messages.append).run())
        self.assertIn('Earlier saved settings','\n'.join(messages));self.assertNotIn('vault files and credentials were not changed','\n'.join(messages))

    def test_real_engines_complete_add_save_discover_save_test_menu_with_fake_transport(self):
        diagnostics=wizard.module('wizard_e2e_diagnostics',ROOT/'tools/integration_checks.py')
        projects=wizard.module('wizard_e2e_projects',ROOT/'tools/integration_projects.py')
        paths=[];messages=[];original_note=(self.root/'Notes/Keep.md').read_bytes()
        def transport(method,url,headers,body):
            self.assertEqual(method,'GET');self.assertIsNone(body)
            self.assertEqual(headers['Authorization'],'Bearer FAKE_TEST_TOKEN')
            parsed=urlsplit(url);self.assertEqual(parsed.hostname,'canvas.example.test');paths.append(parsed.path)
            if parsed.path=='/api/v1/courses':data=[{'id':12,'name':'History'},{'id':34,'name':'Calculus'}]
            elif parsed.path=='/api/v1/users/self/profile':data={'id':7,'name':'PRIVATE_PROFILE_NOT_FOR_OUTPUT'}
            elif parsed.path=='/api/v1/courses/34/assignments':data=[{'id':101,'name':'PRIVATE_ASSIGNMENT_NOT_FOR_OUTPUT'}]
            elif parsed.path in ('/api/v1/courses/34/quizzes','/api/v1/courses/34/discussion_topics','/api/v1/planner/items','/api/v1/calendar_events','/api/v1/announcements'):data=[]
            else:self.fail('unexpected route')
            return {'status':200,'body':json.dumps(data).encode()}
        environment={'CANVAS_TEST_TOKEN':'FAKE_TEST_TOKEN'}
        def discover(root,provider,identity):
            return projects.discover_projects(root,provider,identity,env=environment,transport=transport)
        def check(root,provider,identity):
            return diagnostics.check_integration(root,provider,identity,env=environment,transport=transport)
        answers=iter(['3','5','add','school','https://canvas.example.test','CANVAS_TEST_TOKEN','-','',
                      '5','save','','7','5','1','2','','use','5','save','y','5','school','0'])
        self.assertTrue(wizard.Wizard(wizard.Session(self.root),lambda _:next(answers),messages.append,
                                     connection_checker=check,project_discoverer=discover).run())
        self.assertEqual(paths,['/api/v1/courses','/api/v1/users/self/profile','/api/v1/courses/34/assignments','/api/v1/courses/34/quizzes','/api/v1/courses/34/discussion_topics','/api/v1/planner/items','/api/v1/calendar_events','/api/v1/announcements'])
        saved=json.loads((self.root/'fieldbook_core/canvas.json').read_text())['instances'][0]
        self.assertEqual(saved['courseIds'],['34']);self.assertEqual(saved['baseUrl'],'https://canvas.example.test')
        self.assertFalse(json.loads((self.root/'fieldbook.json').read_text())['features']['canvas'])
        self.assertEqual((self.root/'Notes/Keep.md').read_bytes(),original_note)
        self.assertIn('Connection tests: passed','\n'.join(messages))
        for secret in ('FAKE_TEST_TOKEN','PRIVATE_PROFILE_NOT_FOR_OUTPUT','PRIVATE_ASSIGNMENT_NOT_FOR_OUTPUT'):
            self.assertNotIn(secret,'\n'.join(messages));self.assertNotIn(secret.encode(),b''.join(self.snapshot().values()))

    def test_local_course_manual_binding_requires_preview_apply_and_keeps_defaults(self):
        self.save_connection();session=wizard.Session(self.root);before=self.snapshot();links=FakeLinks();messages=[]
        answers=iter(['1','5','1','2','123','apply'])
        ui=wizard.Wizard(session,lambda _:next(answers),messages.append,link_helper=links,
                         project_discoverer=lambda *_:self.fail('manual binding must not contact provider'))
        ui.link_record()
        self.assertEqual(links.planned[0][2:],('canvas','my-school',{'id':'123'},'a'*64))
        self.assertEqual(len(links.applied),1);self.assertTrue(ui.record_links_saved)
        self.assertIn('canvas_course_id: null → "123"','\n'.join(messages))
        self.assertEqual(self.snapshot(),before);self.assertFalse(session.config['features']['canvas'])

    def test_local_binding_decline_does_not_apply(self):
        self.save_connection();links=FakeLinks();answers=iter(['1','canvas','my-school','2','456',''])
        ui=wizard.Wizard(wizard.Session(self.root),lambda _:next(answers),lambda _:None,link_helper=links)
        ui.link_record();self.assertEqual(len(links.planned),1);self.assertFalse(links.applied);self.assertFalse(ui.record_links_saved)

    def test_local_project_cannot_select_canvas(self):
        self.save_connection();links=FakeLinks(kind='project');answers=iter(['1','canvas'])
        with self.assertRaisesRegex(ValueError,'listed provider'):
            wizard.Wizard(wizard.Session(self.root),lambda _:next(answers),lambda _:None,link_helper=links).link_record()
        self.assertFalse(links.planned)

    def test_local_binding_remote_discovery_can_fall_back_to_manual(self):
        self.save_connection();links=FakeLinks();answers=iter(['1','5','1','1','2','789','apply']);messages=[]
        def failure(*_):raise RuntimeError('FAKE_PRIVATE_SECRET')
        wizard.Wizard(wizard.Session(self.root),lambda _:next(answers),messages.append,link_helper=links,project_discoverer=failure).link_record()
        self.assertEqual(links.planned[0][4],{'id':'789'});self.assertEqual(len(links.applied),1)
        self.assertNotIn('FAKE_PRIVATE_SECRET','\n'.join(messages))

    def test_menu_eight_remote_choice_binds_record_without_changing_default_scope(self):
        self.save_connection();session=wizard.Session(self.root);links=FakeLinks();messages=[];before=self.snapshot()
        answers=iter(['8','1','5','1','1','2','apply','0'])
        self.assertTrue(wizard.Wizard(session,lambda _:next(answers),messages.append,link_helper=links,project_discoverer=lambda *_:self.projects()).run())
        self.assertEqual(links.planned[0][4]['id'],'34');self.assertEqual(self.snapshot(),before)
        self.assertIn('Earlier saved settings and record links remain','\n'.join(messages))

    def test_local_binding_refuses_unsaved_configuration_before_note_listing(self):
        session=wizard.Session(self.root);self.canvas(session);links=FakeLinks()
        with self.assertRaisesRegex(ValueError,'Save or cancel'):
            wizard.Wizard(session,ask=lambda _:self.fail('must save first'),link_helper=links).link_record()
        self.assertFalse(links.planned)

    def calendar(self,provider='google',**values):
        item={'id':'office','baseUrl':wizard.CALENDAR_URLS[provider],'tokenVar':provider.upper()+'_TOKEN',
              'credentialStore':'keyring','authMode':'oauth','calendarIds':['default-calendar'],
              'clientId':'123-example.apps.googleusercontent.com' if provider=='google' else '12345678-1234-1234-1234-123456789abc'}
        if provider=='microsoft':item['tenant']='common'
        return {**item,**values}

    def save_calendar(self,provider='google',**values):
        self.put('fieldbook_core/'+provider+'.json',admin.dump({'instances':[self.calendar(provider,**values)]}))

    def test_calendar_placeholders_are_offline_valid_until_enabled_and_never_read_keys(self):
        for provider in wizard.CALENDAR_PROVIDERS:
            self.put('fieldbook_core/'+provider+'.json',(ROOT/'fieldbook_core'/f'{provider}.json').read_text())
        before=self.snapshot();session=wizard.Session(self.root)
        self.assertFalse(session.validate()['errors']);self.assertTrue(session.validate()['warnings'])
        result=wizard.test_connections(self.root,'all',checker=lambda *_:self.fail('seed calendars must not read keys'))
        self.assertEqual(result['skipped'],len(wizard.PROVIDERS));self.assertEqual(self.snapshot(),before)
        for provider in wizard.CALENDAR_PROVIDERS:
            with self.subTest(provider=provider):
                result=wizard.test_connections(self.root,provider,checker=lambda *_:self.fail('missing client ID'))
                self.assertEqual(result['exitCode'],2)
                session.config['features'][provider]=True;self.assertTrue(session.validate()['errors'])
                session.config['features'][provider]=False

    def test_add_oauth_calendar_save_never_prompts_for_api_key(self):
        answers=iter(['3','google','add','office','','','123-example.apps.googleusercontent.com','-',
                      '5','save','','0']);messages=[];credentials=FakeCredentials()
        ui=wizard.Wizard(wizard.Session(self.root),lambda _:next(answers),messages.append,
                         lambda _:self.fail('OAuth must use menu 9, never paste an API key on save'),credentials)
        self.assertTrue(ui.run());self.assertFalse(credentials.calls)
        saved=json.loads((self.root/'fieldbook_core/google.json').read_text())['instances'][0]
        self.assertEqual(saved['baseUrl'],wizard.CALENDAR_URLS['google']);self.assertEqual(saved['authMode'],'oauth')
        self.assertEqual(saved['credentialStore'],'keyring');self.assertEqual(saved['calendarIds'],[])
        self.assertFalse(json.loads((self.root/'fieldbook.json').read_text())['features']['google'])
        self.assertIn('menu 9 to sign in','\n'.join(messages))

    def test_manual_calendar_access_token_uses_explicit_environment_or_keyring_mode(self):
        for mode in ('environment','keyring'):
            with self.subTest(mode=mode):
                session=wizard.Session(self.root)
                answers=iter(['microsoft','add','office','','access-token','-','','-',mode])
                wizard.Wizard(session,lambda _:next(answers),lambda _:None).integrations()
                item=session.connections['microsoft']['instances'][0]
                self.assertEqual(item['credentialStore'],mode);self.assertEqual(item['authMode'],'access-token')
                self.assertEqual(session.key_updates,{('microsoft','office')} if mode=='keyring' else set())

    def test_calendar_validation_rejects_wrong_endpoint_oauth_store_client_tenant_or_scope(self):
        changes=[('google',{'baseUrl':'https://other.example'}),('google',{'clientId':'not-a-client'}),
                 ('google',{'credentialStore':'environment'}),('microsoft',{'clientId':'not-a-guid'}),
                 ('microsoft',{'tenant':'../other'}),('google',{'calendarIds':['.']}),
                 ('google',{'calendarIds':['bad\nvalue']}),('google',{'calendarIds':['bad\u202evalue']}),
                 ('google',{'calendarIds':['primary']}),('google',{'calendarIds':['id']*11})]
        for provider,change in changes:
            with self.subTest(provider=provider,change=change):
                with self.assertRaises(ValueError):wizard.check_instance(provider,self.calendar(provider,**change))
        wizard.check_instance('google',self.calendar(calendarIds=['caseSensitive/calendar@example.com']))

    def test_calendar_signin_requires_explicit_action_and_keeps_config_and_notes(self):
        self.save_calendar();before=self.snapshot();calls=[];messages=[]
        def authorize(root,provider,identity,**kwargs):
            calls.append((root,provider,identity));return {'authorized':True,'token':'FAKE_TOKEN_MUST_NOT_PRINT'}
        answers=iter(['9','1','1','signin','0'])
        self.assertTrue(wizard.Wizard(wizard.Session(self.root),lambda _:next(answers),messages.append,
                                     calendar_authorizer=authorize).run())
        self.assertEqual(calls,[(self.root,'google','office')]);self.assertEqual(self.snapshot(),before)
        self.assertIn('Calendar sign-in complete','\n'.join(messages));self.assertNotIn('FAKE_TOKEN_MUST_NOT_PRINT','\n'.join(messages))
        answers=iter(['1','1','']);calls.clear()
        wizard.Wizard(wizard.Session(self.root),lambda _:next(answers),lambda _:None,calendar_authorizer=authorize).calendar_signin()
        self.assertFalse(calls)

    def test_calendar_signin_refuses_staged_settings_and_access_token_mode(self):
        self.save_calendar();session=wizard.Session(self.root);session.config['features']['google']=True
        with self.assertRaisesRegex(ValueError,'Save or cancel'):
            wizard.Wizard(session,ask=lambda _:self.fail('must save first')).calendar_signin()
        self.save_calendar(authMode='access-token',credentialStore='environment');answers=iter(['google','1'])
        with self.assertRaisesRegex(ValueError,'access token'):
            wizard.Wizard(wizard.Session(self.root),lambda _:next(answers),lambda _:None,
                          calendar_authorizer=lambda *_:self.fail('must not authorize')).calendar_signin()

    def test_calendar_signin_cancel_and_failure_never_echo_tokens(self):
        self.save_calendar();before=self.snapshot();messages=[]
        for error in (KeyboardInterrupt(),ValueError('FAKE_PRIVATE_CREDENTIAL')):
            answers=iter(['9','google','1','signin','0'])
            def authorize(*args,**kwargs):raise error
            wizard.Wizard(wizard.Session(self.root),lambda _:next(answers),messages.append,calendar_authorizer=authorize).run()
        self.assertEqual(self.snapshot(),before);self.assertNotIn('FAKE_PRIVATE_CREDENTIAL','\n'.join(messages))

    def test_calendar_default_scope_picker_stages_multiselect_only(self):
        self.save_calendar();session=wizard.Session(self.root);before=self.snapshot();answers=iter(['google','1','1,2','replace','use'])
        result={'choices':[{'id':v,'label':v,'settings':{'calendarIds':[v]}} for v in ('Cal/A','Cal/B')],'truncated':False}
        wizard.Wizard(session,lambda _:next(answers),lambda _:None,project_discoverer=lambda *_:result).choose_project()
        self.assertEqual(session.connections['google']['instances'][0]['calendarIds'],['Cal/A','Cal/B'])
        self.assertEqual(self.snapshot(),before);self.assertFalse(session.config['features']['google'])

    def test_series_manual_binding_limits_providers_and_preserves_default_calendars(self):
        self.save_calendar();links=FakeLinks(kind='series');before=self.snapshot();answers=iter(['1','1','1','2','Cal/A','2','Series/A','apply'])
        ui=wizard.Wizard(wizard.Session(self.root),lambda _:next(answers),lambda _:None,link_helper=links,
                         project_discoverer=lambda *_:self.fail('manual IDs must stay offline'))
        ui.link_record();self.assertTrue(ui.record_links_saved);self.assertEqual(self.snapshot(),before)
        self.assertEqual(links.planned[0][2:5],('google','office',{'id':'Series/A','settings':{
            'calendar_provider':'google','calendar_instance':'office','calendar_id':'Cal/A','calendar_series_id':'Series/A'}}))
        answers=iter(['1','canvas'])
        with self.assertRaisesRegex(ValueError,'listed provider'):
            wizard.Wizard(wizard.Session(self.root),lambda _:next(answers),lambda _:None,link_helper=links).link_record()

    def test_series_discovery_uses_selected_calendar_and_bounded_utc_window(self):
        self.save_calendar();calls=[];links=FakeLinks(kind='series')
        calendars={'choices':[{'id':'Cal/A','label':'Office calendar','settings':{'calendarIds':['Cal/A']}}]}
        remote={'id':'Series/A','label':'Weekly meeting','settings':{'calendar_provider':'google','calendar_instance':'office','calendar_id':'Cal/A','calendar_series_id':'Series/A'}}
        def discover(*args):calls.append(args);return {'choices':[remote],'truncated':False}
        answers=iter(['1','google','1','1','1','1','2026-10-01','2027-01-01','1','apply'])
        wizard.Wizard(wizard.Session(self.root),lambda _:next(answers),lambda _:None,link_helper=links,
                      project_discoverer=lambda *_:calendars,series_discoverer=discover).link_record()
        self.assertEqual(calls,[(self.root,'google','office','Cal/A','2026-10-01','2027-01-01')])
        self.assertEqual(links.planned[0][4],remote)
        for start,end in [('2026-10-01','2027-01-02'),('2026-11-01','2026-10-01'),('2026-02-30','2026-03-01')]:
            answers=iter(['2','Cal/A','1',start,end])
            with self.assertRaisesRegex(ValueError,'93 inclusive days'):
                wizard.Wizard(wizard.Session(self.root),lambda _:next(answers),lambda _:None,
                              series_discoverer=lambda *_:self.fail('invalid window must not fetch')).series_choice('google',self.calendar())

    def test_real_binder_two_schools_same_remote_course_keep_separate_local_identity(self):
        links=wizard.module('wizard_real_links',ROOT/'tools/integration_links.py')
        self.put('fieldbook_core/canvas.json',admin.dump({'instances':[self.instance(id='school-a'),self.instance(id='school-b',baseUrl='https://other.example')]}))
        notes={'Projects/History A.md':'---\ntags: [project, course]\ncustom: keep\n---\nStudy checklist A\n',
               'Projects/History B.md':'---\ntags: [project, course]\ncustom: keep\n---\nStudy checklist B\n'}
        for path,body in notes.items():self.put(path,body)
        before=(self.root/'fieldbook_core/canvas.json').read_bytes();messages=[]
        for path,identity in zip(notes,('school-a','school-b')):
            answers=iter([path,'canvas',identity,'2','123','apply'])
            wizard.Wizard(wizard.Session(self.root),lambda _:next(answers),messages.append,link_helper=links).link_record()
            updated=(self.root/path).read_text();self.assertIn('canvas_instance: "'+identity+'"',updated)
            self.assertIn('canvas_course_id: "123"',updated);self.assertTrue(updated.endswith(notes[path].split('---\n')[-1]))
            self.assertIn('custom: keep',updated)
        self.assertEqual((self.root/'fieldbook_core/canvas.json').read_bytes(),before)
        backups=list((self.root/'.fieldbook/config-backups').glob('*-link-*'))
        self.assertEqual(len(backups),2)
        for path,body in notes.items():
            copies=[backup/path for backup in backups if (backup/path).exists()]
            self.assertEqual(len(copies),1);self.assertEqual(copies[0].read_text(),body)

    def test_real_binder_series_manual_link_changes_only_metadata_with_backup(self):
        links=wizard.module('wizard_real_series_links',ROOT/'tools/integration_links.py');self.save_calendar()
        original='---\ntags: [series]\ncustom: keep\n---\n# Planning series\nExisting recurring agenda\n'
        self.put('Meetings/Planning.md',original);before=(self.root/'fieldbook_core/google.json').read_bytes()
        answers=iter(['1','google','1','2','Calendar/A','2','Series/A','apply'])
        wizard.Wizard(wizard.Session(self.root),lambda _:next(answers),lambda _:None,link_helper=links).link_record()
        updated=(self.root/'Meetings/Planning.md').read_text()
        for key,value in {'calendar_provider':'google','calendar_instance':'office','calendar_id':'Calendar/A','calendar_series_id':'Series/A'}.items():
            self.assertIn(key+': "'+value+'"',updated)
        self.assertTrue(updated.endswith(original.split('---\n')[-1]));self.assertIn('custom: keep',updated)
        self.assertEqual((self.root/'fieldbook_core/google.json').read_bytes(),before)
        self.assertFalse(json.loads((self.root/'fieldbook.json').read_text())['features']['google'])

    def test_real_calendar_engines_add_save_pick_link_and_test_through_main_menu(self):
        service=wizard.module('wizard_live_calendar_e2e',ROOT/'fieldbook_core/scripts/calendar_service.py')
        projects=wizard.module('wizard_calendar_projects_e2e',ROOT/'tools/integration_projects.py')
        diagnostics=wizard.module('wizard_calendar_diagnostics_e2e',ROOT/'tools/integration_checks.py')
        links=wizard.module('wizard_calendar_links_e2e',ROOT/'tools/integration_links.py')
        original='---\ntags: [series]\ncustom: keep\n---\nExisting recurring agenda and checklist\n'
        self.put('Meetings/Planning.md',original);unrelated=(self.root/'Notes/Keep.md').read_bytes()
        messages=[];requests=[];environment={'GOOGLE_OFFICE_TOKEN':'FAKE_CALENDAR_TOKEN'}
        def transport(method,url,headers,body):
            self.assertEqual(method,'GET');self.assertIsNone(body)
            self.assertEqual(headers['Authorization'],'Bearer FAKE_CALENDAR_TOKEN')
            parsed=urlsplit(url);self.assertEqual(parsed.hostname,'www.googleapis.com');requests.append(parsed.path)
            if parsed.path=='/calendar/v3/users/me/calendarList':
                result={'items':[{'id':'office@example.test','summary':'Office calendar'}]}
            elif parsed.path=='/calendar/v3/calendars/office%40example.test/events':
                result={'items':[{'id':'meeting-occurrence','summary':'Planning session','recurringEventId':'series-123',
                                 'originalStartTime':{'dateTime':'2026-10-02T13:00:00Z'},
                                 'start':{'dateTime':'2026-10-02T13:00:00Z'},'end':{'dateTime':'2026-10-02T14:00:00Z'},
                                 'description':'PRIVATE_EVENT_BODY_NOT_FOR_DIAGNOSTICS','attendees':[{'email':'private-attendee@example.test'}]}]}
            else:self.fail('unexpected calendar route')
            return {'status':200,'body':json.dumps(result).encode()}
        def discover(root,provider,identity):return projects.discover_projects(root,provider,identity,env=environment,transport=transport)
        def series(*args):return service.discover_series(*args,env=environment,transport=transport)
        def check(root,provider,identity):return diagnostics.check_integration(root,provider,identity,env=environment,transport=transport)
        answers=iter(['3','google','add','office','','access-token','-','-','environment',
                      '5','save','','7','google','1','1','','use','5','save','',
                      '8','1','google','1','1','1','1','2026-10-01','2026-10-31','1','apply',
                      '6','google','office','0'])
        self.assertTrue(wizard.Wizard(wizard.Session(self.root),lambda _:next(answers),messages.append,
                                     connection_checker=check,project_discoverer=discover,series_discoverer=series,link_helper=links).run())
        self.assertEqual(requests,['/calendar/v3/users/me/calendarList']*2+['/calendar/v3/calendars/office%40example.test/events',
                                 '/calendar/v3/users/me/calendarList','/calendar/v3/calendars/office%40example.test/events'])
        saved=json.loads((self.root/'fieldbook_core/google.json').read_text())['instances'][0]
        self.assertEqual(saved['calendarIds'],['office@example.test']);self.assertEqual(saved['credentialStore'],'environment')
        self.assertFalse(json.loads((self.root/'fieldbook.json').read_text())['features']['google'])
        updated=(self.root/'Meetings/Planning.md').read_text()
        self.assertIn('calendar_series_id: "series-123"',updated);self.assertIn('calendar_instance: "office"',updated)
        self.assertTrue(updated.endswith(original.split('---\n')[-1]));self.assertEqual((self.root/'Notes/Keep.md').read_bytes(),unrelated)
        self.assertEqual(list((self.root/'Meetings').glob('*.md')),[self.root/'Meetings/Planning.md'])
        self.assertIn('Connection tests: passed','\n'.join(messages))
        for secret in ('FAKE_CALENDAR_TOKEN','PRIVATE_EVENT_BODY_NOT_FOR_DIAGNOSTICS','private-attendee@example.test'):
            self.assertNotIn(secret,'\n'.join(messages));self.assertNotIn(secret.encode(),b''.join(self.snapshot().values()))

    def test_calendar_signin_loads_shared_auth_module_without_a_tools_wrapper(self):
        self.save_calendar();answers=iter(['google','1','signin']);calls=[]
        class Auth:
            @staticmethod
            def authorize(*args,**kwargs):return {'authorized':True}
        def load(name,path):calls.append(path);return Auth
        with patch.object(wizard,'module',side_effect=load):
            wizard.Wizard(wizard.Session(self.root),lambda _:next(answers),lambda _:None).calendar_signin()
        self.assertEqual(calls,[ROOT/'fieldbook_core/scripts/calendar_auth.py'])

    def test_guided_requirements_for_every_provider_are_offline_and_do_not_change_files(self):
        before=self.snapshot()
        for provider in wizard.PROVIDERS:
            answers=iter(['1','0']);messages=[]
            fail=lambda *a,**k:self.fail('requirements must stay offline')
            wizard.Wizard(wizard.Session(self.root),lambda _:next(answers),messages.append,
                          calendar_authorizer=fail,connection_checker=fail,project_discoverer=fail).integration_setup(provider)
            self.assertIn('not checked by this screen','\n'.join(messages));self.assertEqual(self.snapshot(),before)
        answers=iter(['3']);messages=[]
        wizard.Wizard(wizard.Session(self.root),lambda _:next(answers),messages.append).calendar_setup()
        self.assertIn('PST-only','\n'.join(messages));self.assertIn('.ics','\n'.join(messages));self.assertEqual(self.snapshot(),before)

    def test_guided_cli_entry_points_and_modes(self):
        before=self.snapshot()
        for flags,answers in [(['--integration-setup','canvas'],'0\n'),(['--integration-setup'],'0\n'),(['--calendar-setup'],'3\n')]:
            with patch('sys.stdin',io.StringIO(answers)),patch('sys.stdout',new_callable=io.StringIO):
                self.assertEqual(wizard.main(['--vault',str(self.root),*flags]),0)
        with patch('sys.stderr',new_callable=io.StringIO),self.assertRaises(SystemExit) as caught:
            wizard.main(['--check','--integration-setup','canvas'])
        self.assertEqual(caught.exception.code,2);self.assertEqual(self.snapshot(),before)

    def test_guided_read_test_dispatches_every_provider_without_enabling_or_writing(self):
        for provider in wizard.PROVIDERS:
            with self.subTest(provider=provider):
                item=self.calendar(provider) if provider in wizard.CALENDAR_PROVIDERS else json.loads((ROOT/'fieldbook_core'/f'{provider}.json').read_text())['instances'][0]
                item=copy.deepcopy(item);item['baseUrl']=item['baseUrl'].replace('REPLACE','example')
                self.put('fieldbook_core/'+provider+'.json',admin.dump({'instances':[item]}))
                before=self.snapshot();answers=iter(['6',item['id'],'0']);calls=[];messages=[]
                def check(root,p,identity):
                    calls.append((p,identity));return {'provider':p,'instance':identity,'ok':True,'checks':[{'stage':'scope','status':'pass','message':'Selected read passed'}]}
                wizard.Wizard(wizard.Session(self.root),lambda _:next(answers),messages.append,connection_checker=check).integration_setup(provider)
                self.assertEqual(calls,[(provider,item['id'])]);self.assertIn('Connection tests: passed','\n'.join(messages))
                self.assertEqual(self.snapshot(),before);self.assertFalse(json.loads((self.root/'fieldbook.json').read_text())['features'][provider])

    def test_guided_pending_changes_block_remote_reads_and_canvas_toggle_requires_school(self):
        before=self.snapshot();answers=iter(['8','6','0']);messages=[]
        wizard.Wizard(wizard.Session(self.root),lambda _:next(answers),messages.append,
                      connection_checker=lambda *a:self.fail('must save first')).integration_setup('google')
        self.assertIn('Save or cancel pending edits','\n'.join(messages));self.assertEqual(self.snapshot(),before)
        answers=iter(['8','0']);messages=[];session=wizard.Session(self.root)
        wizard.Wizard(session,lambda _:next(answers),messages.append).integration_setup('canvas')
        self.assertIn('requires the school setup','\n'.join(messages));self.assertFalse(session.config['features']['canvas'])

    def test_unconfigured_calendar_seed_does_not_block_a_separate_ready_account(self):
        for provider in wizard.CALENDAR_PROVIDERS:
            seeds=json.loads((ROOT/'fieldbook_core'/f'{provider}.json').read_text())['instances']
            self.put('fieldbook_core/'+provider+'.json',admin.dump({'instances':[*seeds,self.calendar(provider)]}))
            answers=iter(['office']);messages=[]
            selected=wizard.Wizard(wizard.Session(self.root),lambda _:next(answers),messages.append).saved_instance_choice(provider)
            self.assertEqual(selected['id'],'office');self.assertIn('needs OAuth client ID','\n'.join(messages))
            answers=iter(['1'])
            with self.assertRaisesRegex(ValueError,'OAuth client ID'):
                wizard.Wizard(wizard.Session(self.root),lambda _:next(answers),lambda _:None).saved_instance_choice(provider)

    def test_guided_failed_or_incomplete_read_check_never_reports_pass(self):
        self.save_calendar();before=self.snapshot()
        for status in ('fail','skip'):
            answers=iter(['6','office','0']);messages=[]
            def check(root,p,identity):return {'provider':p,'instance':identity,'ok':False,'checks':[{'stage':'scope','status':status,'message':'Not verified'}]}
            wizard.Wizard(wizard.Session(self.root),lambda _:next(answers),messages.append,connection_checker=check).integration_setup('google')
            self.assertNotIn('Connection tests: passed','\n'.join(messages));self.assertEqual(self.snapshot(),before)

    def test_guided_calendar_signin_read_and_series_link_use_real_engines_for_both_providers(self):
        auth=wizard.module('guided_auth',ROOT/'fieldbook_core/scripts/calendar_auth.py')
        service=wizard.module('guided_service',ROOT/'fieldbook_core/scripts/calendar_service.py')
        links=wizard.module('guided_links',ROOT/'tools/integration_links.py')
        class Store:
            raw=None
            def secure_backend(self):return object()
            def store(self,*args):self.raw=args[-1]
            def get(self,*args):
                if self.raw is None:raise ValueError('No credential')
                return self.raw
        class Listener:
            redirect_uri='http://127.0.0.1:12345/oauth2callback'
            def __init__(self,state):pass
            def __enter__(self):return self
            def __exit__(self,*a):pass
            def wait(self):return 'FAKE_AUTH_CODE'
        for provider in wizard.CALENDAR_PROVIDERS:
            with self.subTest(provider=provider):
                self.save_calendar(provider);store=Store();calls=[];messages=[]
                path='Meetings/Series/CLI test.md';body='---\ntags: [series]\ncustom: keep\n---\nExisting agenda\n'
                self.put(path,body);self.put('Projects/Unrelated.md','---\ntags: [project]\n---\nKeep\n')
                unchanged=(self.root/'Notes/Keep.md').read_bytes()
                def transport(method,url,headers,payload):
                    calls.append((method,url));host=urlsplit(url).hostname
                    if host in ('login.microsoftonline.com','oauth2.googleapis.com'):
                        self.assertEqual(method,'POST')
                        result=({'device_code':'FAKE_DEVICE_SECRET','user_code':'TEST-123','expires_in':900,'interval':1}
                                if url.endswith('/devicecode') else {'access_token':'FAKE_ACCESS_SECRET','refresh_token':'FAKE_REFRESH_SECRET','token_type':'Bearer','expires_in':3600})
                    else:
                        self.assertEqual(method,'GET');self.assertIsNone(payload);self.assertEqual(headers['Authorization'],'Bearer FAKE_ACCESS_SECRET')
                        is_list=urlsplit(url).path.endswith(('/calendarList','/calendars'))
                        if provider=='google':
                            result={'items':[{'id':'cal@example.test','summary':'Calendar'}] if is_list else [{'id':'event-1','summary':'Planning','recurringEventId':'series-1','originalStartTime':{'dateTime':'2026-10-20T14:00:00Z'},'start':{'dateTime':'2026-10-20T14:00:00Z'},'end':{'dateTime':'2026-10-20T15:00:00Z'}}]}
                        else:
                            result={'value':[{'id':'CalABC','name':'Calendar'}] if is_list else [{'id':'event-1','subject':'Planning','seriesMasterId':'series-1','originalStart':'2026-10-20T14:00:00Z','type':'occurrence','start':{'dateTime':'2026-10-20T14:00:00','timeZone':'UTC'},'end':{'dateTime':'2026-10-20T15:00:00','timeZone':'UTC'}}]}
                    return {'status':200,'body':json.dumps(result).encode()}
                def authorize(root,p,identity,**kwargs):
                    return auth.authorize(root,p,identity,**kwargs,browser=lambda *a:None,transport=transport,credential_module=store,loopback_factory=Listener,sleep=lambda *a:None)
                options={'transport':transport,'token_loader':lambda root,p,item:auth.access_token(root,p,item,credential_module=store)}
                answers=iter(['4','1','signin','5','1','1','','use','3','save','',
                              '6','office','7','1','1','1','1','1','2026-10-01','2026-10-31','1','apply','0'])
                ui=wizard.Wizard(wizard.Session(self.root),lambda _:next(answers),messages.append,password=lambda *a:'FAKE_CLIENT_SECRET',
                                 calendar_authorizer=authorize,connection_checker=lambda *a:service.check_integration(*a,**options),
                                 project_discoverer=lambda *a:service.discover_projects(*a,**options),series_discoverer=lambda *a:service.discover_series(*a,**options),link_helper=links)
                ui.integration_setup(provider)
                self.assertTrue(ui.saved_any);self.assertTrue(ui.record_links_saved)
                self.assertIn('Calendar sign-in complete','\n'.join(messages));self.assertIn('Connection tests: passed','\n'.join(messages))
                updated=(self.root/path).read_text();self.assertIn('calendar_provider: "'+provider+'"',updated);self.assertIn('calendar_series_id: "series-1"',updated)
                self.assertTrue(updated.endswith('Existing agenda\n'));self.assertEqual((self.root/'Notes/Keep.md').read_bytes(),unchanged)
                self.assertFalse(json.loads((self.root/'fieldbook.json').read_text())['features'][provider])
                self.assertTrue(any(method=='GET' for method,url in calls));self.assertTrue(any(method=='POST' for method,url in calls))
                for secret in ('FAKE_ACCESS_SECRET','FAKE_REFRESH_SECRET','FAKE_CLIENT_SECRET','FAKE_AUTH_CODE','FAKE_DEVICE_SECRET'):
                    self.assertNotIn(secret,'\n'.join(messages));self.assertNotIn(secret.encode(),b''.join(self.snapshot().values()))

    def test_every_credential_guide_variant_completes_without_credentials_browser_or_writes(self):
        helper=wizard.module('guide_test_catalog',ROOT/'tools/integration-guides.py');catalog=helper.load(wizard.PROVIDERS)
        before=self.snapshot()
        for provider,guide in catalog['providers'].items():
            for n,variant in enumerate(guide['variants']):
                with self.subTest(provider=provider,variant=n):
                    answers=iter(([str(n+1)] if len(guide['variants'])>1 else [])+['']*len(variant['steps']));messages=[]
                    fail=lambda *a,**k:self.fail('walkthrough must stay offline')
                    wizard.Wizard(wizard.Session(self.root),lambda _:next(answers),messages.append,password=fail,
                                  link_opener=fail,connection_checker=fail,calendar_authorizer=fail).credential_guide(provider)
                    self.assertIn('have not been verified','\n'.join(messages));self.assertEqual(self.snapshot(),before)

    def test_credential_links_open_only_by_explicit_selection_and_navigation_is_reversible(self):
        before=self.snapshot();messages=[];opened=[]
        answers=iter(['','b','open 1','open 99','open https://untrusted.example','q'])
        ui=wizard.Wizard(wizard.Session(self.root),lambda _:next(answers),messages.append,link_opener=lambda url:opened.append(url) or True)
        ui.credential_guide('github')
        self.assertEqual(opened,['https://github.com/settings/personal-access-tokens/new'])
        self.assertGreaterEqual('\n'.join(messages).count('Step 1/'),2);self.assertEqual(self.snapshot(),before)

    def test_credential_guide_browser_failure_is_sanitized_and_invalid_input_is_not_echoed(self):
        answers=iter(['open 1','FAKE_SECRET_DO_NOT_ECHO','q']);messages=[]
        def fail(url):raise ValueError('PRIVATE_BROWSER_ERROR')
        wizard.Wizard(wizard.Session(self.root),lambda _:next(answers),messages.append,link_opener=fail).credential_guide('microsoft')
        output='\n'.join(messages)
        self.assertIn('Copy the displayed HTTPS link',output);self.assertNotIn('PRIVATE_BROWSER_ERROR',output);self.assertNotIn('FAKE_SECRET_DO_NOT_ECHO',output)

    def test_credential_guide_registry_missing_provider_or_unsafe_link_fails_before_open(self):
        helper=wizard.module('guide_test_validation',ROOT/'tools/integration-guides.py')
        original=json.loads((ROOT/'tools/integration-guides.json').read_text());bad=copy.deepcopy(original)
        del bad['providers']['canvas']
        path=self.root/'bad-guides.json';path.write_text(json.dumps(bad))
        with self.assertRaisesRegex(ValueError,'missing or invalid'):helper.load(wizard.PROVIDERS,path)
        for url in ['http://github.com/settings','https://github.com.evil.test/','https://secret@github.com/','file:///tmp/key','https://github.com:443/settings','https://github.com/\x1bsettings']:
            bad=copy.deepcopy(original);bad['providers']['github']['variants'][0]['steps'][0]['links'][0]['url']=url
            path.write_text(json.dumps(bad))
            with self.subTest(url=url),self.assertRaises(ValueError):helper.load(wizard.PROVIDERS,path)

    def test_credential_guide_direct_entry_and_nested_menu_keep_pending_settings(self):
        before=self.snapshot()
        with patch('sys.stdin',io.StringIO('q\n')),patch('sys.stdout',new_callable=io.StringIO) as out:
            self.assertEqual(wizard.main(['--vault',str(self.root),'--credential-guide','canvas']),0)
        self.assertIn('Canvas LMS access token',out.getvalue());self.assertEqual(self.snapshot(),before)
        answers=iter(['8','9','q','0']);session=wizard.Session(self.root)
        wizard.Wizard(session,lambda _:next(answers),lambda _:None).integration_setup('github')
        self.assertTrue(session.config['features']['github']);self.assertEqual(self.snapshot(),before)
        answers=iter(['11','google','q','0']);messages=[]
        wizard.Wizard(wizard.Session(self.root),lambda _:next(answers),messages.append).run()
        self.assertIn('Google Calendar app registration','\n'.join(messages));self.assertEqual(self.snapshot(),before)

    def test_credential_guides_distinguish_nonsecret_ids_token_permissions_and_supported_auth(self):
        data=json.loads((ROOT/'tools/integration-guides.json').read_text())['providers']
        text=lambda p:' '.join(s['text'] for v in data[p]['variants'] for s in v['steps'])
        self.assertIn('https://api.atlassian.com/ex/jira/YOUR_CLOUD_ID',text('jira'))
        self.assertIn('Issues to Read-only',text('github'));self.assertIn('vso.work',text('azure'));self.assertIn('vso.project',text('azure'))
        self.assertIn('does not implement Canvas OAuth',text('canvas'));self.assertIn('not an OAuth2 JSON',text('agility'))
        self.assertIn('Desktop app',text('google'));self.assertIn('calendar.events.readonly',text('google'));self.assertIn('calendar.calendarlist.readonly',text('google'))
        self.assertIn('not Object ID',text('microsoft'));self.assertIn('delegated Calendars.Read',text('microsoft'));self.assertIn('offline_access',text('microsoft'))


if __name__=='__main__':unittest.main()
