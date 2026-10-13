"""Fixture tests for the read-only, saved-connection scope picker."""
import base64
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from urllib.parse import parse_qs, urlsplit

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('scope_picker', ROOT / 'tools/integration_projects.py')
picker = importlib.util.module_from_spec(spec);spec.loader.exec_module(picker)


class ScopePickerTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        (self.root / 'fieldbook_core').mkdir()
        self.calls = []

    def configure(self, provider, **extra):
        item = {'id': 'office', 'baseUrl': 'https://example.test' + ('' if provider == 'canvas' else '/base'),
                'tokenVar': provider.upper() + '_TOKEN', **extra}
        if provider == 'jira':item = {'flavor': 'cloud', 'email': 'person@example.test', **item}
        (self.root / 'fieldbook_core' / (provider + '.json')).write_text(json.dumps({'instances': [item]}))
        return item

    def run_discovery(self, provider, payload, *, status=200, headers=None, **kwargs):
        before = {str(p.relative_to(self.root)): p.read_bytes() for p in self.root.rglob('*') if p.is_file()}
        def transport(method, url, request_headers, body):
            self.calls.append((method, url, request_headers, body))
            return {'status': status, 'body': json.dumps(payload).encode(), 'headers': headers or {}}
        result = picker.discover_projects(self.root, provider, 'office', env={provider.upper() + '_TOKEN': 'secret-fixture'}, transport=transport, **kwargs)
        after = {str(p.relative_to(self.root)): p.read_bytes() for p in self.root.rglob('*') if p.is_file()}
        self.assertEqual(before, after)
        self.assertEqual(len(self.calls), 1)
        self.assertNotIn('secret-fixture', json.dumps(result))
        return result

    def test_jira_cloud_project_key_becomes_safe_jql(self):
        self.configure('jira', filter='status = Open')
        result = self.run_discovery('jira', {'values': [{'id': '10', 'key': 'TEAM', 'name': 'Team Project', 'extra': 'ignored'}], 'isLast': True})
        self.assertEqual(result['choices'], [{'id': 'TEAM', 'label': 'Team Project [TEAM]', 'settings': {'filter': 'project = "TEAM"'}}])
        method, url, headers, body = self.calls[0]
        self.assertEqual(method, 'GET');self.assertIsNone(body)
        self.assertEqual(urlsplit(url).path, '/base/rest/api/3/project/search')
        self.assertEqual(parse_qs(urlsplit(url).query), {'startAt': ['0'], 'maxResults': ['50']})
        self.assertEqual(headers['Authorization'], 'Basic ' + base64.b64encode(b'person@example.test:secret-fixture').decode())
        self.assertFalse(result['truncated'])

    def test_jira_server_uses_read_list_and_retains_base_context(self):
        self.configure('jira', flavor='server')
        result = self.run_discovery('jira', [{'key': 'OPS', 'name': 'Operations'}])
        self.assertEqual(self.calls[0][1], 'https://example.test/base/rest/api/2/project')
        self.assertEqual(self.calls[0][2]['Authorization'], 'Bearer secret-fixture')
        self.assertEqual(result['choices'][0]['id'], 'OPS')

    def test_agility_query_is_scope_read_and_uses_oid(self):
        self.configure('agility')
        result = self.run_discovery('agility', [[{'_oid': 'Scope:123', 'Name': 'Delivery', 'ID': {'_oid': 'Scope:123'}}]])
        method, url, _, body = self.calls[0]
        self.assertEqual(method, 'POST');self.assertTrue(url.endswith('/query.v1'))
        self.assertEqual(json.loads(body), {'from': 'Scope', 'select': ['Name', 'ID'], 'page': {'start': 0, 'size': 50}})
        self.assertEqual(result['choices'][0]['settings'], {'where': {'Scope': 'Scope:123'}})

    def test_azure_preserves_exact_project_name(self):
        self.configure('azure')
        identity = 'eb6e4656-77fc-42a1-9181-4c6d8e9da5d1'
        result = self.run_discovery('azure', {'value': [{'id': identity, 'name': "Mark's Team"}]})
        self.assertEqual(result['choices'][0]['settings'], {'project': "Mark's Team"})
        self.assertEqual(urlsplit(self.calls[0][1]).path, '/base/_apis/projects')
        self.assertEqual(parse_qs(urlsplit(self.calls[0][1]).query), {'api-version': ['7.1'], '$top': ['50']})
        self.assertEqual(self.calls[0][2]['Authorization'], 'Basic ' + base64.b64encode(b':secret-fixture').decode())

    def test_github_only_issues_enabled_and_valid_full_names(self):
        self.configure('github')
        rows = [{'full_name': 'owner/repo', 'has_issues': True}, {'full_name': 'owner/off', 'has_issues': False},
                {'full_name': 'owner/../escape', 'has_issues': True}, {'full_name': 'owner/.', 'has_issues': True},
                {'full_name': 'OWNER/REPO', 'has_issues': True}]
        result = self.run_discovery('github', rows)
        self.assertEqual(result['choices'], [{'id': 'owner/repo', 'label': 'owner/repo', 'settings': {'repositories': ['owner/repo']}}])
        self.assertIn('omitted', result['notice'])
        self.assertEqual(urlsplit(self.calls[0][1]).path, '/base/user/repos')

    def test_canvas_active_enrollment_list_and_string_ids(self):
        self.configure('canvas')
        result = self.run_discovery('canvas', [{'id': 123, 'name': 'Biology'}, {'id': True}, {'id': '2/3'}, {'id': 4.1}])
        self.assertEqual(result['choices'][0]['settings'], {'courseIds': ['123']})
        self.assertEqual(len(result['choices']), 1)
        self.assertEqual(urlsplit(self.calls[0][1]).path, '/api/v1/courses')
        self.assertEqual(parse_qs(urlsplit(self.calls[0][1]).query), {'enrollment_state': ['active'], 'per_page': ['50']})

    def test_page_limit_and_remote_next_link_never_followed(self):
        self.configure('canvas')
        result = self.run_discovery('canvas', [{'id': n, 'name': str(n)} for n in range(1, 60)],
                                    headers={'Link': '<https://hostile.test/leak>; rel="next"'})
        self.assertEqual(len(result['choices']), 50);self.assertTrue(result['truncated'])
        self.assertNotIn('hostile', json.dumps(result))

    def test_short_page_with_continuation_is_incomplete(self):
        self.configure('azure')
        result = self.run_discovery('azure', {'value': []}, headers={'X-MS-ContinuationToken': 'secret-cursor'})
        self.assertTrue(result['truncated']);self.assertNotIn('secret-cursor', json.dumps(result))

    def test_short_page_with_next_link_or_truncated_headers_is_incomplete(self):
        self.configure('canvas')
        for headers in [{'link': '<https://untrusted.test/next>; rel="next"'}, {'truncated': True}]:
            with self.subTest(headers=headers):
                self.calls = []
                result = self.run_discovery('canvas', [{'id': 1}], headers=headers)
                self.assertTrue(result['truncated'])
                self.assertNotIn('untrusted', json.dumps(result))

    def test_full_page_without_metadata_is_conservatively_incomplete(self):
        self.configure('canvas')
        result = self.run_discovery('canvas', [{'id': n} for n in range(1, 51)])
        self.assertTrue(result['truncated']);self.assertIn('may be incomplete', result['notice'])

    def test_untrusted_labels_are_plain_and_bounded(self):
        self.configure('jira')
        result = self.run_discovery('jira', {'values': [{'key': 'SAFE', 'name': '<b>Name</b>\x1b\n\u202e ' + 'x' * 300},
                                                      {'key': 'X" OR 1=1', 'name': 'bad'}]})
        label = result['choices'][0]['label']
        self.assertNotRegex(label, '[<>\x00-\x1f\u202e]');self.assertLessEqual(len(label), 147)
        self.assertEqual(len(result['choices']), 1)

    def test_os_credentials_use_selected_instance_binding(self):
        saved = self.configure('canvas', credentialStore='keyring')
        class Credentials:
            @staticmethod
            def get(root, provider, instance):
                self.assertEqual((root, provider, instance), (self.root.resolve(), 'canvas', saved))
                return 'os-secret'
        result = self.run_discovery('canvas', [], credential_module=Credentials)
        self.assertEqual(self.calls[0][2]['Authorization'], 'Bearer os-secret')
        self.assertNotIn('os-secret', json.dumps(result))

    def test_empty_list_is_not_connection_verification(self):
        self.configure('canvas')
        result = self.run_discovery('canvas', [])
        self.assertEqual(result['choices'], []);self.assertIn('not a connection', result['notice'])
        self.assertIn('No selectable', result['notice'])

    def test_http_error_ignores_response_body(self):
        self.configure('github')
        with self.assertRaisesRegex(picker.DiscoveryError, 'HTTP 403') as error:
            self.run_discovery('github', {'error': 'secret-fixture private server details'}, status=403)
        self.assertNotIn('secret-fixture', str(error.exception))

    def test_redirect_is_not_retried(self):
        self.configure('canvas')
        with self.assertRaisesRegex(picker.DiscoveryError, 'Redirect refused'):
            self.run_discovery('canvas', [], status=302)
        self.assertEqual(len(self.calls), 1)

    def test_invalid_configuration_is_rejected_before_network(self):
        self.configure('canvas', baseUrl='http://example.test')
        with self.assertRaisesRegex(picker.DiscoveryError, 'HTTPS'):
            picker.discover_projects(self.root, 'canvas', 'office', transport=lambda *args: self.fail('unexpected network'))

    def test_missing_key_does_not_contact_remote(self):
        self.configure('github')
        with self.assertRaisesRegex(picker.DiscoveryError, 'key is missing'):
            picker.discover_projects(self.root, 'github', 'office', env={}, transport=lambda *args: self.fail('unexpected network'))

    def test_transport_exception_details_are_not_returned(self):
        self.configure('github')
        def transport(*args):raise OSError('secret-fixture https://private.example/sensitive')
        with self.assertRaises(picker.DiscoveryError) as error:
            picker.discover_projects(self.root, 'github', 'office', env={'GITHUB_TOKEN': 'secret-fixture'}, transport=transport)
        self.assertNotIn('secret-fixture', str(error.exception))
        self.assertNotIn('private.example', str(error.exception))

    def test_invalid_json_wrong_shape_duplicate_keys_and_size_are_sanitized(self):
        self.configure('canvas')
        for raw in [b'<html>secret-fixture</html>', b'{"secret":"secret-fixture"}', b'{"x":1,"x":2}', b'x' * (picker.checks.MAX_BODY + 1)]:
            with self.subTest(size=len(raw)):
                with self.assertRaises(picker.DiscoveryError) as error:
                    picker.discover_projects(self.root, 'canvas', 'office', env={'CANVAS_TOKEN': 'secret-fixture'},
                                             transport=lambda *args: {'status': 200, 'body': raw})
                self.assertNotIn('secret-fixture', str(error.exception))

    def test_linked_config_is_refused(self):
        self.configure('canvas')
        config = self.root / 'fieldbook_core/canvas.json'
        original = self.root / 'original.json';config.rename(original);config.symlink_to(original)
        with self.assertRaisesRegex(picker.DiscoveryError, 'linked'):
            picker.discover_projects(self.root, 'canvas', 'office', transport=lambda *args: self.fail('unexpected network'))

    def test_disabled_workflows_do_not_prevent_human_discovery(self):
        self.configure('canvas')
        (self.root / 'fieldbook_core/fieldbook.json').write_text(json.dumps({'setups': ['work'], 'features': {'canvas': False}}))
        result = self.run_discovery('canvas', [{'id': 1, 'name': 'One'}])
        self.assertEqual(len(result['choices']), 1)


if __name__ == '__main__':unittest.main()
