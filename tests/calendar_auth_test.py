#!/usr/bin/env python3
"""OAuth protocol tests: fake providers/store/browser, no live accounts."""
import base64
import getpass
import hashlib
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from urllib.parse import parse_qs, urlencode, urlsplit
import warnings

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('calendar_auth', ROOT / 'fieldbook_core/scripts/calendar_auth.py')
auth = importlib.util.module_from_spec(spec);spec.loader.exec_module(auth)
SECRET = 'never-display-this-secret'


def reply(data, status=200):return {'status': status, 'body': json.dumps(data).encode()}
def token(**kwargs):return {'access_token': 'access-secret', 'refresh_token': 'refresh-secret', 'token_type': 'Bearer', 'expires_in': 3600, **kwargs}


class Store:
    def __init__(self, raw=None):self.raw = raw;self.saved = [];self.reads = []
    def secure_backend(self):return object()
    def get(self, root, provider, instance):
        self.reads.append((root, provider, instance))
        if self.raw is None:raise ValueError('no credential')
        return self.raw
    def store(self, root, provider, instance, value):self.raw = value;self.saved.append((root, provider, instance, value))


class Transport:
    def __init__(self, *responses):self.responses = list(responses);self.calls = []
    def __call__(self, method, url, headers, body):
        self.calls.append((method, url, headers, parse_qs(body.decode())))
        response = self.responses.pop(0)
        if isinstance(response, Exception):raise response
        return response


class Listener:
    redirect_uri = 'http://127.0.0.1:12345/oauth2callback'
    def __init__(self, state):self.state = state
    def __enter__(self):return self
    def __exit__(self, *args):pass
    def wait(self):return 'authorization-code'


class CalendarAuthTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup);self.root = Path(self.temp.name).resolve()
        (self.root / 'fieldbook_core').mkdir()
        self.items = {}
        for provider in auth.BASES:
            self.items[provider] = {'id': 'test', 'baseUrl': auth.BASES[provider], 'tokenVar': provider.upper() + '_TOKEN', 'credentialStore': 'keyring', 'authMode': 'oauth',
                                   'clientId': '123456-example.apps.googleusercontent.com' if provider == 'google' else '12345678-1234-1234-1234-123456789abc'}
            if provider == 'microsoft':self.items[provider]['tenant'] = 'common'
            self.save(provider)

    def save(self, provider, **changes):
        self.items[provider].update(changes)
        (self.root / 'fieldbook_core' / (provider + '.json')).write_text(json.dumps({'instances': [self.items[provider]]}))

    def bundle(self, provider, **changes):
        value = auth._new_bundle(provider, self.items[provider], token(), now=lambda: 1000, client_secret='client-secret' if provider == 'google' else None)
        value.update(changes);return json.dumps(value, separators=(',', ':'))

    def google(self, transport=None, store=None, **kwargs):
        outputs = [];browser = []
        result = auth.authorize(self.root, 'google', 'test', say=outputs.append, password=lambda _: 'client-secret', browser=browser.append,
                                loopback_factory=Listener, transport=transport or Transport(reply(token())), credential_module=store or Store(), now=lambda: 1000, **kwargs)
        return result, outputs, browser

    def device(self, **changes):return {'device_code': 'device-secret', 'user_code': 'ABC-123', 'expires_in': 900, 'interval': 5, 'verification_uri': 'https://untrusted.example/' + SECRET, 'message': SECRET, **changes}

    def test_google_pkce_read_scopes_fixed_endpoints_and_os_bundle_only(self):
        store = Store();transport = Transport(reply(token()))
        result, outputs, browser = self.google(transport, store)
        self.assertTrue(result['authorized']);self.assertEqual(len(store.saved), 1)
        url = urlsplit(browser[0]);query = parse_qs(url.query)
        self.assertEqual(url.scheme + '://' + url.netloc + url.path, 'https://accounts.google.com/o/oauth2/v2/auth')
        self.assertEqual(set(query['scope'][0].split()), set(auth.SCOPES['google']))
        self.assertEqual(query['code_challenge_method'], ['S256']);self.assertEqual(query['prompt'], ['consent'])
        method, destination, headers, body = transport.calls[0]
        self.assertEqual((method, destination), ('POST', 'https://oauth2.googleapis.com/token'))
        self.assertEqual(body['client_secret'], ['client-secret']);self.assertEqual(body['code'], ['authorization-code'])
        expected = base64.urlsafe_b64encode(hashlib.sha256(body['code_verifier'][0].encode()).digest()).decode().rstrip('=')
        self.assertEqual(query['code_challenge'], [expected]);self.assertEqual(len(query['state'][0]), 43)
        for secret in ('client-secret', 'access-secret', 'refresh-secret', 'authorization-code'):
            self.assertNotIn(secret, json.dumps(result));self.assertNotIn(secret, '\n'.join(outputs))
        bundle = json.loads(store.raw);self.assertEqual(bundle['expires_at'], 4600);self.assertEqual(bundle['client_secret'], 'client-secret')
        self.assertEqual(set(self.root.rglob('*')), {self.root / 'fieldbook_core', self.root / 'fieldbook_core/google.json', self.root / 'fieldbook_core/microsoft.json'})

    def test_google_reuses_only_matching_stored_client_secret(self):
        store = Store(self.bundle('google'));outputs = []
        result = auth.authorize(self.root, 'google', 'test', credential_module=store, password=lambda _: '',
                                say=outputs.append, browser=lambda _: None, loopback_factory=Listener, transport=Transport(reply(token())))
        self.assertTrue(result['authorized'])

    def test_google_callback_state_code_and_error_validation(self):
        state = 'expected-random-state'
        self.assertEqual(auth._callback_values('/oauth2callback?' + urlencode({'state': state, 'code': 'private-code'}), state), 'private-code')
        bad = ['/oauth2callback?state=wrong&code=private-code', '/oauth2callback?state=%E2%98%83&code=x',
               '/oauth2callback?state=' + state + '&state=' + state + '&code=x', '/different?state=' + state + '&code=x',
               '/oauth2callback?state=' + state + '&error=access_denied&error_description=' + SECRET,
               '/oauth2callback?state=' + state, 'https://evil.example/oauth2callback?state=' + state + '&code=x']
        for path in bad:
            with self.subTest(path=path), self.assertRaises(auth.AuthError) as result:auth._callback_values(path, state)
            self.assertNotIn(SECRET, str(result.exception));self.assertNotIn('private-code', str(result.exception))

    def test_google_requires_loopback_and_never_stores_after_failed_callback(self):
        class BadListener(Listener):redirect_uri = 'http://0.0.0.0:12345/oauth2callback'
        store = Store();transport = Transport()
        with self.assertRaises(auth.AuthError):auth.authorize(self.root, 'google', 'test', password=lambda _: 'client-secret', say=lambda _: None,
             credential_module=store, transport=transport, loopback_factory=BadListener)
        self.assertEqual(store.saved, []);self.assertEqual(transport.calls, [])

    def test_google_hidden_input_cannot_fallback_to_echo(self):
        def password(_):warnings.warn('unsafe fallback', getpass.GetPassWarning);return SECRET
        with self.assertRaises(auth.AuthError):auth.authorize(self.root, 'google', 'test', credential_module=Store(), password=password, say=lambda _: None)

    def test_microsoft_device_flow_pending_slowdown_and_safe_instructions(self):
        transport = Transport(reply(self.device()), reply({'error': 'authorization_pending'}, 400), reply({'error': 'slow_down'}, 400), reply(token(scope='Calendars.Read')))
        store = Store();output = [];waits = []
        result = auth.authorize(self.root, 'microsoft', 'test', say=output.append, sleep=waits.append, credential_module=store, transport=transport, now=lambda: 1000)
        self.assertTrue(result['authorized']);self.assertEqual(waits, [5, 5, 10]);self.assertEqual(len(store.saved), 1)
        self.assertEqual(transport.calls[0][1], 'https://login.microsoftonline.com/common/oauth2/v2.0/devicecode')
        self.assertEqual(set(transport.calls[0][3]['scope'][0].split()), set(auth.SCOPES['microsoft']))
        self.assertTrue(all(call[1].startswith('https://login.microsoftonline.com/common/oauth2/v2.0/') for call in transport.calls))
        self.assertIn('https://microsoft.com/devicelogin', output[0]);self.assertIn('ABC-123', output[0])
        for secret in (SECRET, 'device-secret', 'access-secret', 'refresh-secret'):self.assertNotIn(secret, json.dumps(result) + '\n'.join(output))
        self.assertNotIn('client_secret', transport.calls[1][3])

    def test_microsoft_device_expiry_and_denial_never_save(self):
        for replies in [(reply(self.device(expires_in=6)), reply({'error': 'authorization_pending'}, 400)),
                        (reply(self.device()), reply({'error': 'authorization_declined', 'error_description': SECRET}, 400))]:
            store = Store()
            with self.assertRaises(auth.AuthError) as error:auth.authorize(self.root, 'microsoft', 'test', credential_module=store, transport=Transport(*replies), sleep=lambda _: None, say=lambda _: None)
            self.assertNotIn(SECRET, str(error.exception));self.assertEqual(store.saved, [])

    def test_invalid_device_fields_and_provider_supplied_urls_are_not_used(self):
        for change in ({'user_code': SECRET + '\nattack'}, {'expires_in': 9999999}, {'interval': 0}, {'device_code': ''}):
            with self.subTest(change=change), self.assertRaises(auth.AuthError):
                auth.authorize(self.root, 'microsoft', 'test', credential_module=Store(), transport=Transport(reply(self.device(**change))), sleep=lambda _: None, say=lambda _: None)

    def test_valid_access_token_read_does_not_refresh_or_login(self):
        for provider in auth.BASES:
            store = Store(self.bundle(provider));transport = Transport()
            result = auth.access_token(self.root, provider, self.items[provider], env={provider.upper() + '_TOKEN': 'wrong-env'}, credential_module=store, transport=transport, now=lambda: 1001)
            self.assertEqual(result, 'access-secret');self.assertEqual(store.saved, []);self.assertEqual(transport.calls, [])

    def test_expiry_refreshes_and_rotates_in_os_store(self):
        for provider in auth.BASES:
            with self.subTest(provider=provider):
                store = Store(self.bundle(provider, expires_at=999));transport = Transport(reply(token(access_token='new-access', refresh_token='new-refresh')))
                result = auth.access_token(self.root, provider, self.items[provider], credential_module=store, transport=transport, now=lambda: 1000)
                self.assertEqual(result, 'new-access');self.assertEqual(json.loads(store.raw)['refresh_token'], 'new-refresh')
                self.assertEqual(transport.calls[0][3]['grant_type'], ['refresh_token']);self.assertEqual(transport.calls[0][3]['refresh_token'], ['refresh-secret'])
                self.assertEqual('client_secret' in transport.calls[0][3], provider == 'google')

    def test_refresh_without_replacement_refresh_token_preserves_previous(self):
        store = Store(self.bundle('google', expires_at=999));data = token();data.pop('refresh_token')
        auth.access_token(self.root, 'google', self.items['google'], credential_module=store, transport=Transport(reply(data)), now=lambda: 1000)
        self.assertEqual(json.loads(store.raw)['refresh_token'], 'refresh-secret')

    def test_missing_or_mismatched_bundle_never_refreshes_or_falls_back_to_env(self):
        variants = [None, SECRET, self.bundle('google', clientId='different.apps.googleusercontent.com'), self.bundle('google', instance='another'),
                    self.bundle('google', baseUrl='https://evil.example'), self.bundle('google', scopes=['https://www.googleapis.com/auth/calendar'])]
        for raw in variants:
            with self.subTest(raw=raw):
                store = Store(raw);transport = Transport()
                with self.assertRaises(auth.AuthError) as error:auth.access_token(self.root, 'google', self.items['google'], env={'GOOGLE_TOKEN': SECRET}, credential_module=store, transport=transport)
                self.assertEqual(transport.calls, []);self.assertEqual(store.saved, []);self.assertNotIn(SECRET, str(error.exception))

    def test_tenant_binding_change_requires_new_signin(self):
        raw = self.bundle('microsoft');self.save('microsoft', tenant='organizations');transport = Transport()
        with self.assertRaises(auth.AuthError):auth.access_token(self.root, 'microsoft', self.items['microsoft'], credential_module=Store(raw), transport=transport)
        self.assertEqual(transport.calls, [])

    def test_read_write_or_unrelated_grants_are_rejected(self):
        for provider, scopes in [('google', 'https://www.googleapis.com/auth/calendar'), ('google', auth.SCOPES['google'][0]),
                                 ('microsoft', 'Calendars.ReadWrite offline_access'), ('microsoft', 'Calendars.Read Mail.Read')]:
            with self.subTest(provider=provider), self.assertRaises(auth.AuthError):
                auth._new_bundle(provider, self.items[provider], token(scope=scopes), now=lambda: 1000, client_secret='client-secret')

    def test_bad_tokens_types_and_missing_refresh_are_rejected(self):
        for change in ({'access_token': ''}, {'access_token': 'bad\ntoken'}, {'refresh_token': None}, {'token_type': 'DPoP'}, {'expires_in': True}, {'expires_in': 900000}, {'scope': [{}]}):
            with self.subTest(change=change), self.assertRaises(auth.AuthError):auth._new_bundle('google', self.items['google'], token(**change), now=lambda: 1000, client_secret='client-secret')

    def test_manual_access_token_mode_and_bundle_are_separate(self):
        self.save('google', authMode='access-token', credentialStore='environment', clientId='')
        self.assertEqual(auth.access_token(self.root, 'google', self.items['google'], env={'GOOGLE_TOKEN': SECRET}, credential_module=Store()), SECRET)
        self.save('google', credentialStore='keyring');store = Store('manual-key')
        self.assertEqual(auth.access_token(self.root, 'google', self.items['google'], env={'GOOGLE_TOKEN': 'wrong'}, credential_module=store), 'manual-key')
        store.raw = '{"refresh_token":"secret"}'
        with self.assertRaises(auth.AuthError):auth.access_token(self.root, 'google', self.items['google'], credential_module=store)
        with self.assertRaises(auth.AuthError):auth.authorize(self.root, 'google', 'test', credential_module=store)

    def test_invalid_config_store_client_and_tenant_are_rejected_before_requests(self):
        variants = [('google', {'baseUrl': 'https://evil.example'}), ('google', {'credentialStore': 'environment'}), ('google', {'clientId': ''}),
                    ('microsoft', {'tenant': '../../evil'}), ('microsoft', {'clientId': 'not-an-application-id'})]
        for provider, change in variants:
            with self.subTest(provider=provider, change=change):
                original = dict(self.items[provider]);self.save(provider, **change);transport = Transport()
                with self.assertRaises(auth.AuthError):auth.authorize(self.root, provider, 'test', transport=transport, credential_module=Store())
                self.assertEqual(transport.calls, []);self.items[provider] = original;self.save(provider)

    def test_config_change_during_signin_prevents_save(self):
        store = Store()
        def transport(*args):self.save('google', clientId='new.apps.googleusercontent.com');return reply(token())
        with self.assertRaises(auth.AuthError):self.google(transport=transport, store=store)
        self.assertEqual(store.saved, [])

    def test_store_unavailable_has_no_plaintext_fallback(self):
        class Broken(Store):
            def secure_backend(self):raise ValueError(SECRET)
        with self.assertRaises(auth.AuthError) as error:auth.authorize(self.root, 'google', 'test', credential_module=Broken())
        self.assertNotIn(SECRET, str(error.exception))
        class SaveBroken(Store):
            def store(self, *args):raise ValueError(SECRET)
        with self.assertRaises(auth.AuthError) as error:self.google(store=SaveBroken())
        self.assertNotIn(SECRET, str(error.exception))
        self.assertFalse((self.root / '.fieldbook').exists())

    def test_http_errors_redirects_and_exception_text_are_sanitized(self):
        responses = [reply({'error': 'invalid_client', 'error_description': SECRET}, 401), reply({'error': 'invalid_grant', 'error_description': SECRET}, 400),
                     {'status': 302, 'body': SECRET.encode()}, {'status': 429, 'body': SECRET.encode()},
                     {'status': 200, 'body': b'not JSON ' + SECRET.encode()}, {'status': 200, 'body': b' ' * (auth.MAX_RESPONSE + 1)}, RuntimeError(SECRET)]
        for response in responses:
            with self.subTest(response=str(response)[:20]), self.assertRaises(auth.AuthError) as error:
                auth._post('https://oauth2.googleapis.com/token', {'refresh_token': SECRET}, Transport(response))
            self.assertNotIn(SECRET, str(error.exception))

    def test_transport_only_allows_fixed_provider_post_routes(self):
        for method, url in [('GET', 'https://oauth2.googleapis.com/token'), ('POST', 'http://oauth2.googleapis.com/token'),
                            ('POST', 'https://evil.example/token'), ('POST', 'https://login.microsoftonline.com/common/oauth2/v2.0/logout')]:
            with self.subTest(url=url), self.assertRaises(auth.AuthError):auth._transport(method, url, {}, b'')
        self.assertIsNone(auth._NoRedirect().redirect_request(None, None, 302, SECRET, {}, 'https://evil.example'))

    def test_google_secret_can_rotate_without_changing_client_id(self):
        store = Store(self.bundle('google'));transport = Transport(reply(token()))
        auth.authorize(self.root, 'google', 'test', credential_module=store, password=lambda _: 'rotated-secret', say=lambda _: None,
                       browser=lambda _: None, loopback_factory=Listener, transport=transport)
        self.assertEqual(transport.calls[0][3]['client_secret'], ['rotated-secret']);self.assertEqual(json.loads(store.raw)['client_secret'], 'rotated-secret')

    def test_password_exception_is_sanitized(self):
        def password(_):raise RuntimeError(SECRET)
        with self.assertRaises(auth.AuthError) as error:auth.authorize(self.root, 'google', 'test', credential_module=Store(), password=password, say=lambda _: None)
        self.assertNotIn(SECRET, str(error.exception))

    def test_loopback_socket_timeout_and_closure_without_real_socket(self):
        class Socket:
            def settimeout(self, value):self.timeout = value
        socket = Socket();closed = []
        def initialize(server, address, handler):
            self.assertEqual(address, ('127.0.0.1', 0));server.server_port = 54321;server.RequestHandlerClass = handler
        with patch.object(auth.HTTPServer, '__init__', initialize), patch.object(auth.HTTPServer, 'get_request', return_value=(socket, ('127.0.0.1', 1))), patch.object(auth.HTTPServer, 'server_close', side_effect=lambda: closed.append(True)):
            with auth._Loopback('state') as listener:
                self.assertEqual(listener.redirect_uri, 'http://127.0.0.1:54321/oauth2callback')
                self.assertEqual(listener.server.get_request()[0], socket);self.assertEqual(socket.timeout, 2)
                self.assertEqual(listener.server.timeout, .5)
            self.assertEqual(closed, [True])


if __name__ == '__main__':unittest.main()
