"""Coverage and mapped-field diagnostics use disposable configs and fake transports."""
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
def load(name,file):
    spec=importlib.util.spec_from_file_location(name,ROOT/file);module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module);return module
checks=load('coverage_checks','tools/integration_checks.py')
coverage=load('coverage_summary','tools/integration_coverage.py')
wizard=load('coverage_wizard','tools/configure.py')

class CoverageTests(unittest.TestCase):
    def setUp(self):
        temp=tempfile.TemporaryDirectory();self.addCleanup(temp.cleanup);self.root=Path(temp.name)
        (self.root/'fieldbook_core').mkdir()
        (self.root/'fieldbook.json').write_text(json.dumps({'features':{'jira':True}}))

    def config(self,provider,**kw):
        item={'id':'test','baseUrl':'https://service.example','tokenVar':provider.upper()+'_TOKEN',**kw}
        (self.root/'fieldbook_core'/f'{provider}.json').write_text(json.dumps({'instances':[item]}));return item

    def run_check(self,provider,*replies):
        pending=list(replies);calls=[]
        def transport(method,url,headers,body):
            calls.append((method,url,json.loads(body) if body else None))
            status,data=pending.pop(0)
            return {'status':status,'body':json.dumps(data).encode()}
        result=checks.check_integration(self.root,provider,'test',env={provider.upper()+'_TOKEN':'HIDDEN-TOKEN'},transport=transport)
        self.assertFalse(pending);self.assertNotIn('HIDDEN-TOKEN',json.dumps(result));return result,calls

    def test_every_provider_has_coverage_and_offline_summary_reads_no_keys_or_network(self):
        self.assertEqual(set(coverage.CATALOG),set(wizard.PROVIDERS)|{'ics'})
        self.config('jira',flavor='cloud',filter='project = ABC',email='me@example.test',dateFields={'target':'customfield_1'})
        with patch.object(wizard.getpass,'getpass',side_effect=AssertionError('credential read')):
            result=coverage.offline(self.root,wizard)
        item=result['integrations'][0]['connections'][0]
        self.assertIsNone(item['read_at']);self.assertEqual(item['date_fields']['target'],'customfield_1')
        self.assertNotIn('email',json.dumps(result));self.assertEqual(result['mode'],'offline_configuration')

    def test_invalid_or_secret_configuration_is_not_printed_in_coverage(self):
        self.config('jira',flavor='cloud',token='DO-NOT-PRINT',dateFields={'due':'bad expression'})
        result=coverage.offline(self.root,wizard)
        self.assertIn('error',result['integrations'][0]);self.assertNotIn('DO-NOT-PRINT',json.dumps(result))

    def test_mapping_validation_and_invalid_dates(self):
        for mapping in (None,[],{'unknown':'Field'},{'due':'Field; other'},{'due':'F','target':'F'}):
            with self.assertRaises(ValueError):coverage.dates.date_fields('azure',{'dateFields':mapping})
        for date in ('2026-02-30','2026-01-01T25:00:00Z',{},'tomorrow'):
            self.assertFalse(coverage.dates.valid_date(date))
        self.assertTrue(coverage.dates.valid_date('2024-02-29T12:30:00.000-0400'))

    def test_azure_tests_mapped_fields_and_detects_detail_access_failure(self):
        self.config('azure',project='Team',dateFields={'due':'Custom.Due','target':'Custom.Target'})
        result,calls=self.run_check('azure',(200,{'workItems':[{'id':7}]}),(403,{'error':'PRIVATE RESPONSE'}))
        self.assertFalse(result['ok']);self.assertEqual(calls[1][2]['ids'],[7])
        self.assertIn('Custom.Target',calls[1][2]['fields']);self.assertEqual(calls[1][0],'POST')
        self.assertNotIn('PRIVATE RESPONSE',json.dumps(result));self.assertIn('checked_at',result['coverage'])

    def test_azure_rejects_wrong_sample_and_empty_query_does_not_claim_fields_verified(self):
        self.config('azure',project='Team',dateFields={'due':'Custom.Due'})
        result,_=self.run_check('azure',(200,{'workItems':[{'id':7}]}),(200,{'value':[{'id':8,'fields':{'System.Title':'T','System.State':'New'}}]}))
        self.assertFalse(result['ok'])
        result,calls=self.run_check('azure',(200,{'workItems':[]}))
        self.assertEqual(len(calls),1)
        self.assertEqual(next(c for c in result['checks'] if c['stage']=='work_item_details')['status'],'skip')
        self.assertIn('not_returned',next(c for c in result['checks'] if c['stage']=='date_fields')['message'])

    def test_mapped_field_samples_do_not_expose_values_or_count_invalid_dates_as_present(self):
        for provider in ('jira','agility'):
            with self.subTest(provider=provider):
                kw={'flavor':'cloud','filter':'project = A','email':'me@example.test'} if provider=='jira' else {'where':{'Scope':'Scope:1'}}
                self.config(provider,**kw,dateFields={'target':'CustomDate'})
                row={'id':'1','fields':{'CustomDate':'2026-02-30'}} if provider=='jira' else {'Number':'S-1','CustomDate':'2026-02-30'}
                replies=[(200,{'accountId':'private-user'}),(200,{'issues':[row]})] if provider=='jira' else [(200,[[row]])]
                result,calls=self.run_check(provider,*replies)
                message=next(c for c in result['checks'] if c['stage']=='date_fields')['message']
                self.assertIn('invalid_date',message);self.assertNotIn('2026-02-30',json.dumps(result))
                if provider=='agility':self.assertIn('CustomDate',calls[0][2]['select'])

if __name__ == '__main__':unittest.main()
