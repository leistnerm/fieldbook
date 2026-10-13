#!/usr/bin/env python3
"""Connection diagnostics use mocks only; never contact an account or server."""
import base64
import importlib.util
import io
import json
import os
from pathlib import Path
import ssl
import tempfile
import unittest
from unittest.mock import patch
from urllib.error import HTTPError, URLError
from urllib.parse import parse_qs, urlsplit

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('integration_checks', ROOT / 'tools/integration_checks.py')
checks = importlib.util.module_from_spec(spec);spec.loader.exec_module(checks)
SECRET = 'very-private-key-do-not-display'


def response(data, status=200):return {'status': status, 'body': json.dumps(data).encode()}


class Transport:
    def __init__(self, *replies):self.replies = list(replies);self.calls = []
    def __call__(self, method, url, headers, body):
        self.calls.append((method, url, headers, body))
        reply = self.replies.pop(0)
        if isinstance(reply, Exception):raise reply
        return reply


class ConnectionChecksTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name);(self.root / 'fieldbook_core').mkdir()

    def save(self, provider, **fields):
        item = {'id': 'test', 'baseUrl': 'https://service.example', 'tokenVar': provider.upper() + '_TOKEN'}
        item.update({'jira': {'flavor': 'cloud', 'email': 'user@example.test', 'filter': 'project = ABC'},
                     'agility': {'where': {'Scope': 'Scope:123'}},
                     'github': {'repositories': ['owner/repo']},
                     'azure': {'project': 'Example'}, 'canvas': {'courseIds': ['12']}}[provider])
        item.update(fields)
        (self.root / 'fieldbook_core' / (provider + '.json')).write_text(json.dumps({'instances': [item]}))
        return item

    def run_check(self, provider, transport, **kwargs):
        return checks.check_integration(self.root, provider, 'test', env={provider.upper() + '_TOKEN': SECRET}, transport=transport, **kwargs)

    def stage(self, result, stage):return next(c for c in result['checks'] if c['stage'] == stage)

    def test_jira_cloud_tests_identity_and_configured_filter_with_basic_auth(self):
        self.save('jira', baseUrl='https://service.example/prefix/')
        transport = Transport(response({'accountId': 'private-account'}), response({'issues': [{'id': '1'}]}))
        result = self.run_check('jira', transport)
        self.assertTrue(result['ok']);self.assertEqual(len(transport.calls), 2)
        self.assertTrue(transport.calls[0][1].endswith('/prefix/rest/api/3/myself'))
        query = parse_qs(urlsplit(transport.calls[1][1]).query)
        self.assertEqual(query['jql'], ['(project = ABC) ORDER BY key ASC']);self.assertEqual(query['maxResults'], ['1'])
        self.assertEqual(transport.calls[0][2]['Authorization'], 'Basic ' + base64.b64encode(('user@example.test:' + SECRET).encode()).decode())
        self.assertNotIn('private-account', json.dumps(result));self.assertNotIn(SECRET, json.dumps(result))

    def test_jira_server_uses_bearer_v2_and_email_environment_supported_for_cloud(self):
        self.save('jira', flavor='server', email='')
        transport = Transport(response({'name': 'account'}), response({'issues': []}))
        result = self.run_check('jira', transport)
        self.assertTrue(result['ok']);self.assertIn('/rest/api/2/search?', transport.calls[1][1])
        self.assertEqual(transport.calls[0][2]['Authorization'], 'Bearer ' + SECRET)
        self.save('jira', email='')
        transport = Transport(response({'accountId': 'account'}), response({'issues': []}))
        result = checks.check_integration(self.root, 'jira', 'test', env={'JIRA_TOKEN': SECRET, 'JIRA_EMAIL': 'me@example.test'}, transport=transport)
        self.assertTrue(result['ok'])

    def test_github_auth_plus_each_repository_with_no_response_content(self):
        self.save('github', repositories=['one/repo', 'two/repo'], labels=['selected label'], apiVersion='2026-03-10')
        transport = Transport(response({'id': 1, 'login': 'hidden-account'}), response([]), response([{'id': 2, 'title': SECRET}]))
        result = self.run_check('github', transport)
        self.assertTrue(result['ok']);self.assertEqual(len(transport.calls), 3)
        self.assertTrue(all(c[0] == 'GET' and c[3] is None for c in transport.calls))
        self.assertEqual(transport.calls[0][2]['X-GitHub-Api-Version'], '2026-03-10')
        self.assertEqual(parse_qs(urlsplit(transport.calls[1][1]).query)['labels'], ['selected label'])
        self.assertNotIn(SECRET, json.dumps(result));self.assertNotIn('hidden-account', json.dumps(result))
        self.assertIn('no records', self.stage(result, 'scope_1')['message'])

    def test_github_public_success_does_not_prove_authentication(self):
        self.save('github')
        transport = Transport(response({'error': SECRET}, 401), response([{'id': 1}]))
        result = self.run_check('github', transport)
        self.assertFalse(result['ok']);self.assertEqual(self.stage(result, 'identity')['status'], 'fail')
        self.assertEqual(self.stage(result, 'scope_1')['status'], 'pass')
        self.assertEqual(self.stage(result, 'authentication')['status'], 'fail')

    def test_identity_forbidden_does_not_stop_jira_or_canvas_scope_checks(self):
        for provider, scope in [('jira', {'issues': []}), ('canvas', [])]:
            with self.subTest(provider=provider):
                self.save(provider);transport = Transport(response({'error': SECRET}, 403), *[response(scope) for _ in range(6 if provider == 'canvas' else 1)])
                result = self.run_check(provider, transport)
                self.assertFalse(result['ok']);self.assertEqual(len(transport.calls), 7 if provider == 'canvas' else 2)
                self.assertEqual(self.stage(result, 'scope_1')['status'], 'pass')
                self.assertNotIn('invalid key', json.dumps(result));self.assertNotIn(SECRET, json.dumps(result))

    def test_canvas_uses_self_only_and_selected_courses_without_roster(self):
        self.save('canvas', courseIds=[2, '7'])
        transport = Transport(response({'id': 1, 'calendar': {'ics': SECRET}}), *[response([]) for _ in range(12)])
        result = self.run_check('canvas', transport)
        self.assertTrue(result['ok'])
        self.assertEqual(urlsplit(transport.calls[0][1]).path, '/api/v1/users/self/profile')
        self.assertEqual([urlsplit(c[1]).path for c in transport.calls[1:]], [path for course in ('2', '7') for path in (f'/api/v1/courses/{course}/assignments', f'/api/v1/courses/{course}/quizzes', f'/api/v1/courses/{course}/discussion_topics', '/api/v1/planner/items', '/api/v1/calendar_events', '/api/v1/announcements')])
        self.assertTrue(all(c[0] == 'GET' and c[3] is None for c in transport.calls))
        self.assertEqual(parse_qs(urlsplit(transport.calls[1][1]).query)['include[]'], ['checkpoints'])
        self.assertEqual(parse_qs(urlsplit(transport.calls[5][1]).query)['excludes[]'], ['child_events', 'assignment'])
        self.assertIn('course_7', self.stage(result, 'scope_12')['message'])
        self.assertNotIn(SECRET, json.dumps(result))

    def test_canvas_planner_shape_and_each_new_route_failure_are_reported(self):
        self.save('canvas')
        planner = [{'course_id': 12, 'plannable_type': 'wiki_page', 'plannable_id': 99, 'plannable': {'title': SECRET}}]
        replies = [response([]), response([]), response([]), response(planner), response([]), response([])]
        result = self.run_check('canvas', Transport(response({'id': 1}), *replies))
        self.assertTrue(result['ok']);self.assertNotIn(SECRET, json.dumps(result))
        for index in range(6):
            failed = list(replies);failed[index] = response({'error': SECRET}, 403)
            result = self.run_check('canvas', Transport(response({'id': 1}), *failed))
            self.assertFalse(result['ok']);self.assertEqual(self.stage(result, 'scope_' + str(index + 1))['status'], 'fail')
            self.assertNotIn(SECRET, json.dumps(result))
        replies[3] = response([{'id': 99}])
        self.assertFalse(self.run_check('canvas', Transport(response({'id': 1}), *replies))['ok'])

    def test_canvas_all_ten_courses_are_checked_without_silently_hitting_other_provider_cap(self):
        self.save('canvas', courseIds=list(range(1, 11)))
        transport = Transport(response({'id': 1}), *[response([]) for _ in range(60)])
        result = self.run_check('canvas', transport)
        self.assertTrue(result['ok']);self.assertEqual(len(transport.calls), 61)
        self.assertIn('course_10', self.stage(result, 'scope_60')['message'])

    def test_agility_protected_query_is_read_only_and_bounded(self):
        self.save('agility', baseUrl='https://service.example/agility', memberId='Member:7')
        transport = Transport(response([[{'Number': 'S-1'}]]));result = self.run_check('agility', transport)
        self.assertTrue(result['ok']);self.assertEqual(len(transport.calls), 1)
        method, url, headers, body = transport.calls[0]
        self.assertEqual(method, 'POST');self.assertEqual(url, 'https://service.example/agility/query.v1')
        query = json.loads(body);self.assertEqual(query['page'], {'start': 0, 'size': 1})
        self.assertEqual(query['where'], {'Scope': 'Scope:123', 'Owners': 'Member:7'});self.assertEqual(query['select'], ['Number'])
        self.assertEqual(self.stage(result, 'identity')['status'], 'unknown')
        self.assertEqual(self.stage(result, 'authentication')['status'], 'pass')

    def test_azure_uses_documented_wiql_and_batch_detail_reads(self):
        self.save('azure', baseUrl='https://dev.azure.com/organization', project="Team's Board", filter='[System.State] <> \'Closed\'')
        transport = Transport(response({'workItems': [{'id': 1}]}),response({'value':[{'id':1,'fields':{'System.Title':'Sample','System.State':'New'}}]}));result = self.run_check('azure', transport)
        self.assertTrue(result['ok']);self.assertEqual(len(transport.calls), 2)
        self.assertTrue(transport.calls[1][1].startswith('https://dev.azure.com/organization/_apis/wit/workitemsbatch'))
        method, url, headers, body = transport.calls[0]
        self.assertEqual(method, 'POST');self.assertEqual(parse_qs(urlsplit(url).query)['$top'], ['1'])
        self.assertIn('/Team%27s%20Board/_apis/wit/wiql', url)
        self.assertIn('[System.TeamProject] = "Team\'s Board"', json.loads(body)['query'])
        self.assertIn("AND ([System.State] <> 'Closed')", json.loads(body)['query'])
        self.assertEqual(headers['Authorization'], 'Basic ' + base64.b64encode((':' + SECRET).encode()).decode())

    def test_empty_scope_is_incomplete_without_scanning_all_accounts(self):
        for provider, settings in [('jira', {'filter': ''}), ('github', {'repositories': []}), ('canvas', {'courseIds': []}), ('agility', {'where': {}, 'memberId': ''}), ('azure', {'project': ''})]:
            with self.subTest(provider=provider):
                self.save(provider, **settings)
                transport = Transport(response({'id': 1, 'login': 'user', 'accountId': 'a'}))
                result = self.run_check(provider, transport)
                self.assertFalse(result['ok']);self.assertEqual(self.stage(result, 'scope')['status'], 'skip')
                self.assertLessEqual(len(transport.calls), 1)

    def test_disabled_features_do_not_block_explicit_saved_connection_check(self):
        self.save('canvas');(self.root / 'fieldbook.json').write_text('{"setups":[],"features":{"canvas":false}}')
        self.assertTrue(self.run_check('canvas', Transport(response({'id': 1}), *[response([]) for _ in range(6)]))['ok'])

    def test_scope_cap_is_truthfully_incomplete(self):
        self.save('github', repositories=['owner/repo' + str(i) for i in range(15)])
        transport = Transport(response({'id': 1, 'login': 'user'}), *[response([]) for _ in range(10)])
        result = self.run_check('github', transport)
        self.assertFalse(result['ok']);self.assertEqual(len(transport.calls), 11)
        self.assertEqual(self.stage(result, 'scope_remaining')['status'], 'skip')

    def test_missing_malformed_and_literal_secret_configuration_fail_before_credentials(self):
        transport = Transport()
        self.assertFalse(self.run_check('github', transport)['ok'])
        path = self.root / 'fieldbook_core/github.json'
        for raw in ('[]', '{bad', '{"instances":[]}', '{"instances":[],"token":"' + SECRET + '"}', '{"instances":[],"instances":[]}'):
            path.write_text(raw);result = self.run_check('github', transport)
            self.assertEqual(self.stage(result, 'configuration')['status'], 'fail');self.assertNotIn(SECRET, json.dumps(result))
        self.assertEqual(transport.calls, [])

    def test_url_validation_and_placeholder_fail_without_request(self):
        urls = ['http://service.example', 'https://user:secret@service.example', 'https://service.example/?secret=x',
                'https://service.example/#fragment', 'https://service.example/../api', 'https://service.example/%2e%2e/api',
                'https://service.example\\evil', 'https://service.example:99999', 'https://REPLACE-HOST', 'https://service.example/\n']
        for url in urls:
            with self.subTest(url=url):
                self.save('github', baseUrl=url);transport = Transport();result = self.run_check('github', transport)
                self.assertFalse(result['ok']);self.assertEqual(transport.calls, [])
                self.assertNotIn(url, json.dumps(result))
        self.save('canvas', baseUrl='https://service.example/path')
        self.assertFalse(self.run_check('canvas', Transport())['ok'])

    def test_invalid_scope_cannot_add_routes_or_writes(self):
        cases = [('github', {'repositories': ['owner/../anything']}), ('jira', {'filter': 'project=ABC ORDER BY key'}),
                 ('azure', {'project': '../other'}), ('azure', {'filter': 'x; DROP WorkItems'}), ('canvas', {'courseIds': ['1/roster']})]
        for provider, settings in cases:
            with self.subTest(provider=provider, settings=settings):
                self.save(provider, **settings);transport = Transport()
                result = self.run_check(provider, transport)
                self.assertFalse(result['ok']);self.assertEqual(transport.calls, [])

    def test_missing_and_bad_tokens_do_not_reach_network(self):
        self.save('github')
        for key in (None, '', 'with\nheader', ' ', 'x' * 16385):
            transport = Transport();result = checks.check_integration(self.root, 'github', 'test', env={'GITHUB_TOKEN': key}, transport=transport)
            self.assertFalse(result['ok']);self.assertEqual(self.stage(result, 'credential')['status'], 'fail');self.assertEqual(transport.calls, [])

    def test_keyring_mode_ignores_environment_and_uses_bound_instance(self):
        saved = self.save('github', credentialStore='keyring')
        class Store:
            calls = []
            def get(self, root, provider, item):self.calls.append((root, provider, item));return 'keyring-secret'
        store = Store();transport = Transport(response({'id': 1, 'login': 'me'}), response([]))
        result = self.run_check('github', transport, credential_module=store)
        self.assertTrue(result['ok']);self.assertEqual(store.calls, [(self.root.resolve(), 'github', saved)])
        self.assertEqual(transport.calls[0][2]['Authorization'], 'Bearer keyring-secret')
        self.assertNotIn('keyring-secret', json.dumps(result))
        class Broken:
            def get(self, *args):raise RuntimeError(SECRET)
        transport = Transport();result = self.run_check('github', transport, credential_module=Broken())
        self.assertFalse(result['ok']);self.assertEqual(transport.calls, []);self.assertNotIn(SECRET, json.dumps(result))

    def test_environment_mode_never_opens_keyring(self):
        self.save('github')
        class Forbidden:
            def get(self, *args):raise AssertionError('must not use keyring')
        result = self.run_check('github', Transport(response({'id': 1, 'login': 'me'}), response([])), credential_module=Forbidden())
        self.assertTrue(result['ok'])

    def test_http_failures_and_redirect_never_expose_body_headers_or_urls(self):
        self.save('github')
        for status in (301, 302, 307, 308, 400, 401, 403, 404, 429, 500):
            with self.subTest(status=status):
                transport = Transport(response({'id': 1, 'login': 'me'}), {'status': status, 'body': SECRET.encode(), 'headers': {'Location': 'https://' + SECRET}})
                result = self.run_check('github', transport)
                self.assertFalse(result['ok']);self.assertEqual(self.stage(result, 'scope_1')['status'], 'fail')
                self.assertNotIn(SECRET, json.dumps(result));self.assertEqual(len(transport.calls), 2)
                if status == 404:self.assertIn('hidden', self.stage(result, 'scope_1')['message'])

    def test_tls_timeout_and_exception_text_are_sanitized(self):
        self.save('github')
        for exc, expected in [(ssl.SSLCertVerificationError(SECRET), 'TLS'), (URLError(ssl.SSLError(SECRET)), 'TLS'),
                              (TimeoutError(SECRET), 'timed out'), (URLError(TimeoutError(SECRET)), 'timed out'),
                              (OSError(SECRET), 'Connection failed')]:
            with self.subTest(expected=expected):
                result = self.run_check('github', Transport(response({'id': 1, 'login': 'me'}), exc))
                self.assertFalse(result['ok']);self.assertIn(expected, self.stage(result, 'scope_1')['message']);self.assertNotIn(SECRET, json.dumps(result))

    def test_invalid_or_oversized_json_is_not_reported_as_working(self):
        self.save('github')
        for body in (b'<html>login</html>', b'[' + b' ' * checks.MAX_BODY + b']', b'{"x":NaN}', b'{"x":1,"x":2}', b'["wrong-shape"]'):
            result = self.run_check('github', Transport(response({'id': 1, 'login': 'me'}), {'status': 200, 'body': body}))
            self.assertFalse(result['ok']);self.assertEqual(self.stage(result, 'scope_1')['status'], 'fail')

    def test_linked_configuration_is_rejected(self):
        self.save('github');path = self.root / 'fieldbook_core/github.json';other = self.root / 'elsewhere.json'
        path.rename(other);path.symlink_to(other)
        self.assertFalse(self.run_check('github', Transport())['ok'])
        path.unlink();os.link(other, path)
        self.assertFalse(self.run_check('github', Transport())['ok'])

    def test_check_has_no_local_write_side_effects(self):
        self.save('github')
        before = {p.relative_to(self.root): p.read_bytes() for p in self.root.rglob('*') if p.is_file()}
        result = self.run_check('github', Transport(response({'id': 1, 'login': 'me'}), response([])))
        after = {p.relative_to(self.root): p.read_bytes() for p in self.root.rglob('*') if p.is_file()}
        self.assertTrue(result['ok']);self.assertEqual(before, after)
        self.assertEqual(self.stage(result, 'write_permissions')['status'], 'unknown')

    def test_transport_refuses_redirects_without_reading_error_body(self):
        self.assertIsNone(checks._NoRedirect().redirect_request(None, None, 302, SECRET, {}, 'https://elsewhere.example'))
        error = HTTPError('https://service.example', 302, SECRET, {'Location': 'https://elsewhere.example'}, io.BytesIO(SECRET.encode()))
        class Opener:
            def open(self, request, timeout):raise error
        with patch.object(checks, 'build_opener', return_value=Opener()):
            transport = checks._Transport(checks.time.monotonic() + 45)
            self.assertEqual(transport('GET', 'https://service.example/user', {}, None), {'status': 302, 'body': b''})

    def test_transport_bounds_response_and_uses_timeout(self):
        calls = []
        class Reply:
            status = 200;headers = {'Content-Length': str(checks.MAX_BODY + 1)}
            def __enter__(self):return self
            def __exit__(self, *args):pass
            def read1(self, size):raise AssertionError('oversized response must not be read')
        class Opener:
            def open(self, request, timeout):calls.append((request, timeout));return Reply()
        with patch.object(checks, 'build_opener', return_value=Opener()):
            transport = checks._Transport(checks.time.monotonic() + 45)
            with self.assertRaises(checks.DiagnosticError):transport('GET', 'https://service.example/user', {}, None)
            self.assertGreater(calls[0][1], 0);self.assertLessEqual(calls[0][1], 15)
            with self.assertRaises(checks.DiagnosticError):transport('GET', 'http://service.example/user', {}, None)
        self.assertEqual(len(calls), 1)

    def test_instance_deadline_prevents_further_scope_requests(self):
        self.save('github');transport = Transport()
        with patch.object(checks.time, 'monotonic', side_effect=[0, 100, 100]):
            result = self.run_check('github', transport)
        self.assertFalse(result['ok']);self.assertEqual(transport.calls, [])
        self.assertIn('budget', json.dumps(result))

    def test_url_reachability_is_separate_from_auth_and_routes(self):
        self.save('github')
        result = self.run_check('github', Transport(response({}, 404), response({}, 404)))
        self.assertEqual(self.stage(result, 'url')['status'], 'pass');self.assertFalse(result['ok'])
        self.assertIn('reachability', self.stage(result, 'url')['message'])
        self.save('github', repositories=[])
        result = self.run_check('github', Transport(TimeoutError(SECRET)))
        self.assertEqual(self.stage(result, 'url')['status'], 'fail');self.assertFalse(result['ok'])
        result = self.run_check('github', Transport(response({}, 401)))
        self.assertEqual(self.stage(result, 'authentication')['status'], 'fail')
        self.assertEqual(self.stage(result, 'url')['status'], 'pass')
        self.save('agility', where={})
        result = self.run_check('agility', Transport())
        self.assertEqual(self.stage(result, 'url')['status'], 'skip')


if __name__ == '__main__':unittest.main()
