#!/usr/bin/env python3
"""Explicit calendar OAuth sign-in and private access-token refresh.

Only authorize() opens a browser or requests user input. access_token() is a
private transport helper: never register its return value as a model tool.
OAuth bundles stay in the OS credential store; no plaintext fallback exists.
Injected transport uses (method, url, headers, body)->{status, body: bytes}.
"""
import base64
import getpass
import hashlib
import hmac
from http.server import BaseHTTPRequestHandler, HTTPServer
import json
import os
from pathlib import Path
import re
import secrets
import ssl
import time
import types
from urllib.error import HTTPError
from urllib.parse import parse_qs, urlencode, urlsplit
from urllib.request import HTTPRedirectHandler, HTTPSHandler, Request, build_opener
import warnings
import webbrowser

ROOT = Path(__file__).resolve().parents[2]
BASES = {'google': 'https://www.googleapis.com/calendar/v3', 'microsoft': 'https://graph.microsoft.com/v1.0'}
SCOPES = {'google': ('https://www.googleapis.com/auth/calendar.events.readonly', 'https://www.googleapis.com/auth/calendar.calendarlist.readonly'),
          'microsoft': ('https://graph.microsoft.com/Calendars.Read', 'offline_access')}
MAX_RESPONSE = 65536
MAX_BUNDLE = 16384


class AuthError(ValueError):pass


def _module(name, path):
    module = types.ModuleType(name);module.__file__ = str(path)
    exec(compile(path.read_bytes(), str(path), 'exec'), module.__dict__)
    return module


def _config(root, provider, reference):
    if provider not in BASES:raise AuthError('Choose Google Calendar or Microsoft Outlook calendar.')
    identity = reference.get('id') if isinstance(reference, dict) else reference
    if not isinstance(identity, str) or not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_-]{0,63}', identity):raise AuthError('Choose a valid saved calendar instance ID.')
    try:
        checks = _module('calendar_auth_checks', ROOT / 'tools/integration_checks.py')
        data = checks._json(checks._safe_file(root, 'fieldbook_core/' + provider + '.json', 65536))
        if not isinstance(data, dict) or not isinstance(data.get('instances'), list) or checks._secret_fields(data):raise ValueError()
        matches = [v for v in data['instances'] if isinstance(v, dict) and v.get('id') == identity]
        if len(matches) != 1:raise ValueError()
        item = matches[0]
        if isinstance(reference, dict) and reference != item:raise ValueError()
        if item.get('baseUrl', '').rstrip('/') != BASES[provider]:raise ValueError()
        if not re.fullmatch(provider.upper() + r'_[A-Z0-9_]+', item.get('tokenVar', '')):raise ValueError()
        if item.get('authMode', 'oauth') not in ('oauth', 'access-token') or item.get('credentialStore', 'environment') not in ('keyring', 'environment'):raise ValueError()
    except Exception:raise AuthError('Save a valid calendar connection at the fixed provider API URL before signing in or reading.') from None
    if item.get('authMode', 'oauth') == 'oauth':
        if item.get('credentialStore') != 'keyring':raise AuthError('OAuth requires the OS credential store; plaintext and environment refresh-token storage are not supported.')
        client = item.get('clientId', '')
        if provider == 'google':valid = isinstance(client, str) and bool(re.fullmatch(r'[A-Za-z0-9._-]{1,220}\.apps\.googleusercontent\.com', client))
        else:valid = isinstance(client, str) and bool(re.fullmatch(r'[0-9a-fA-F]{8}(?:-[0-9a-fA-F]{4}){3}-[0-9a-fA-F]{12}', client))
        if not valid:raise AuthError('Configure the application client ID from the provider app registration before signing in.')
        tenant = item.get('tenant', 'common')
        if provider == 'microsoft' and (not isinstance(tenant, str) or not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9.-]{0,252}', tenant) or '..' in tenant or tenant.endswith('.')):
            raise AuthError('Microsoft tenant must be common, organizations, consumers, a tenant ID, or its domain.')
    return item


def _credentials(module):return module if module is not None else _module('calendar_os_credentials', Path(__file__).with_name('credentials.py'))


def _secret(value):
    if not isinstance(value, str) or not value or len(value) > 8192 or value.startswith('{') or any(c.isspace() or not 33 <= ord(c) <= 126 for c in value):
        raise AuthError('The provider returned an invalid credential; sign in again.')
    return value


def _binding(provider, item):
    return {'version': 1, 'kind': 'fieldbook-calendar-oauth', 'provider': provider, 'instance': item['id'],
            'baseUrl': BASES[provider], 'clientId': item['clientId'], 'tenant': item.get('tenant', 'common') if provider == 'microsoft' else ''}


def _scopes(provider, value):
    if not isinstance(value, (str, list)):raise AuthError('The granted calendar scopes could not be verified; sign in again.')
    if isinstance(value, list) and any(not isinstance(v, str) for v in value):raise AuthError('The granted calendar scopes could not be verified; sign in again.')
    actual = set(value.split() if isinstance(value, str) else value)
    if provider == 'google':
        required = set(SCOPES[provider]);allowed = required
    else:
        actual = {v.removeprefix('https://graph.microsoft.com/').casefold() for v in actual if isinstance(v, str)}
        required = {'calendars.read'};allowed = required | {'offline_access'}
    if not required <= actual or actual - allowed:raise AuthError('The grant did not contain exactly the supported calendar read scopes. Use a dedicated app registration and sign in again.')
    return list(SCOPES[provider])


def _bundle(raw, provider, item):
    try:
        if not isinstance(raw, str) or len(raw.encode()) > MAX_BUNDLE:raise ValueError()
        value = json.loads(raw)
        if not isinstance(value, dict) or any(value.get(k) != v for k, v in _binding(provider, item).items()):raise ValueError()
        _secret(value.get('access_token'));_secret(value.get('refresh_token'))
        _scopes(provider, value.get('scopes'))
        if provider == 'google':_secret(value.get('client_secret'))
        if type(value.get('expires_at')) not in (int, float) or not 0 < value['expires_at'] < 10**12:raise ValueError()
        return value
    except Exception:raise AuthError('Saved OAuth credentials do not match this application, tenant or connection, or are invalid. Use calendar sign-in again.') from None


class _NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):return None


def _transport(method, url, headers, body):
    if method != 'POST' or not (url == 'https://oauth2.googleapis.com/token' or re.fullmatch(r'https://login\.microsoftonline\.com/[A-Za-z0-9.-]+/oauth2/v2\.0/(token|devicecode)', url)):
        raise AuthError('Only fixed provider OAuth endpoints are permitted.')
    opener = build_opener(_NoRedirect(), HTTPSHandler(context=ssl.create_default_context()))
    deadline = time.monotonic() + 30
    try:
        try:response = opener.open(Request(url, data=body, headers=headers, method='POST'), timeout=15)
        except HTTPError as exc:response = exc
        with response:
            status = response.status
            if 300 <= status < 400:return {'status': status, 'body': b''}
            pieces = [];size = 0
            while True:
                if time.monotonic() >= deadline:raise AuthError('OAuth request timed out.')
                block = response.read1(min(16384, MAX_RESPONSE + 1 - size))
                if not block:break
                pieces.append(block);size += len(block)
                if size > MAX_RESPONSE:raise AuthError('OAuth response exceeded the size limit.')
            raw = b''.join(pieces)
            return {'status': status, 'body': raw}
    except AuthError:raise
    except Exception:raise AuthError('OAuth connection failed. Check network access, trusted TLS certificates and provider availability.') from None


def _post(url, values, transport, *, polling=False):
    try:
        result = (transport or _transport)('POST', url, {'Content-Type': 'application/x-www-form-urlencoded', 'Accept': 'application/json', 'Accept-Encoding': 'identity'}, urlencode(values).encode())
        status = result.get('status');raw = result.get('body')
        if type(status) is not int:raise ValueError()
        if 300 <= status < 400:raise AuthError('OAuth redirect refused; use the standard provider endpoints.')
        if status == 429:raise AuthError('OAuth service rate limited this request. Wait before signing in or reading again.')
        if not isinstance(raw, bytes) or len(raw) > MAX_RESPONSE:raise ValueError()
        data = json.loads(raw)
        if not isinstance(data, dict):raise ValueError()
        if status == 200 and 'error' not in data:return data
        error = data.get('error')
        if polling and error in ('authorization_pending', 'slow_down'):return {'error': error}
        if error in ('authorization_declined', 'access_denied'):raise AuthError('Calendar authorization was declined. No credential was saved.')
        if error in ('invalid_client', 'unauthorized_client'):raise AuthError('The provider rejected the app registration. Check its client ID, client type, tenant and allowed sign-in flow.')
        if error in ('invalid_grant', 'expired_token', 'bad_verification_code', 'interaction_required'):
            raise AuthError('Calendar authorization expired, was revoked, or needs consent. Use calendar sign-in again.')
        raise AuthError('The provider rejected the OAuth request. Check app registration, organization policy and calendar consent, then retry.')
    except AuthError:raise
    except Exception:raise AuthError('OAuth returned an invalid response or the connection failed; no credential was saved.') from None


def _token_endpoint(provider, item):
    return 'https://oauth2.googleapis.com/token' if provider == 'google' else 'https://login.microsoftonline.com/' + item.get('tenant', 'common') + '/oauth2/v2.0/token'


def _new_bundle(provider, item, response, *, now, previous=None, client_secret=None):
    if str(response.get('token_type', '')).casefold() != 'bearer':raise AuthError('The provider did not return a supported bearer token.')
    expiry = response.get('expires_in')
    if type(expiry) is not int or not 0 < expiry <= 86400:raise AuthError('The provider returned an invalid access-token expiry.')
    value = {**_binding(provider, item), 'access_token': _secret(response.get('access_token')),
             'refresh_token': _secret(response.get('refresh_token') or (previous or {}).get('refresh_token')),
             'expires_at': now() + expiry, 'scopes': _scopes(provider, response.get('scope', list(SCOPES[provider])))}
    if provider == 'google':value['client_secret'] = _secret(client_secret or (previous or {}).get('client_secret'))
    if len(json.dumps(value, separators=(',', ':')).encode()) > MAX_BUNDLE:raise AuthError('OAuth credential bundle exceeds the supported OS-store size.')
    return value


def _store(root, provider, item, bundle, credentials):
    _config(root, provider, item)  # Do not save after destination/app changes.
    try:credentials.store(root, provider, item, json.dumps(bundle, separators=(',', ':')))
    except Exception:raise AuthError('Could not save calendar credentials in the OS store. No plaintext fallback was used; unlock the store and sign in again.') from None


def _callback_values(path, state):
    if not isinstance(path, str) or len(path) > 8192:raise AuthError('Invalid OAuth callback.')
    parsed = urlsplit(path)
    if parsed.path != '/oauth2callback' or parsed.scheme or parsed.netloc or parsed.fragment:raise AuthError('Invalid OAuth callback path.')
    try:query = parse_qs(parsed.query, keep_blank_values=True, strict_parsing=True, max_num_fields=12)
    except Exception:raise AuthError('Invalid OAuth callback parameters.') from None
    if any(len(v) != 1 for v in query.values()) or not hmac.compare_digest(query.get('state', [''])[0].encode(), state.encode()):raise AuthError('OAuth state did not match this sign-in attempt.')
    if query.get('error'):raise AuthError('Calendar authorization was declined or failed. No credential was saved.')
    return _secret(query.get('code', [''])[0])


class _Loopback:
    def __init__(self, state):
        self.code = None;self.error = None;self.state = state
        outer = self
        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *args):pass  # Never log callback query/code.
            def do_GET(self):
                if self.client_address[0] != '127.0.0.1':self.send_error(403);return
                try:code = _callback_values(self.path, outer.state)
                except AuthError:
                    # A wrong nonce must not cancel a real sign-in still in flight.
                    try:q = parse_qs(urlsplit(self.path).query)
                    except Exception:q = {}
                    if q.get('state') == [outer.state] and q.get('error'):outer.error = AuthError('Calendar authorization was declined or failed. No credential was saved.')
                    self.send_response(400);body = b'Authorization not accepted. Return to Fieldbook.'
                else:
                    outer.code = code;self.send_response(200);body = b'Authorization received. Return to Fieldbook to finish.'
                self.send_header('Content-Type', 'text/plain; charset=utf-8');self.send_header('Cache-Control', 'no-store');self.send_header('Content-Length', str(len(body)));self.end_headers();self.wfile.write(body)
        class LocalServer(HTTPServer):
            def get_request(self):
                connection, address = super().get_request();connection.settimeout(2);return connection, address
            def handle_error(self, request, address):pass
        self.server = LocalServer(('127.0.0.1', 0), Handler);self.server.timeout = .5
        self.redirect_uri = 'http://127.0.0.1:' + str(self.server.server_port) + '/oauth2callback'
    def __enter__(self):return self
    def __exit__(self, *args):self.server.server_close()
    def wait(self):
        deadline = time.monotonic() + 180
        while self.code is None and self.error is None and time.monotonic() < deadline:self.server.handle_request()
        if self.error:raise self.error
        if self.code is None:raise AuthError('Browser sign-in timed out. Run calendar sign-in again.')
        return self.code


def authorize(root, provider, instanceID, *, say=print, password=getpass.getpass, browser=webbrowser.open,
              transport=None, credential_module=None, loopback_factory=None, sleep=time.sleep, now=time.time):
    """Human-invoked sign-in. Returns sanitized receipt, never tokens or codes."""
    root = Path(root).resolve(strict=True);item = _config(root, provider, instanceID)
    if item.get('authMode', 'oauth') != 'oauth':raise AuthError('This connection uses a manually supplied access token; select OAuth before browser sign-in.')
    credentials = _credentials(credential_module)
    try:
        if hasattr(credentials, 'secure_backend'):credentials.secure_backend()
    except Exception:raise AuthError('OS credential store unavailable. Install fieldbook_core/requirements-credentials.txt in the vault Python environment and unlock the OS store.') from None
    if provider == 'google':
        client_secret = None
        try:client_secret = _bundle(credentials.get(root, provider, item), provider, item).get('client_secret')
        except Exception:pass
        try:
            with warnings.catch_warnings():
                warnings.simplefilter('error', getpass.GetPassWarning)
                prompt = 'Google Desktop app client secret (hidden; Enter keeps the saved secret): ' if client_secret else 'Google Desktop app client secret (hidden; stored only in the OS credential store): '
                entered = password(prompt)
                client_secret = _secret(client_secret if entered == '' and client_secret else entered)
        except getpass.GetPassWarning:raise AuthError('Hidden client-secret input requires an interactive terminal; no echoed-input fallback is allowed.') from None
        except AuthError:raise
        except Exception:raise AuthError('Could not read the hidden client secret; reopen calendar sign-in in an interactive terminal.') from None
        verifier = secrets.token_urlsafe(64);state = secrets.token_urlsafe(32)
        challenge = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode('ascii')).digest()).decode().rstrip('=')
        try:
            with (loopback_factory or _Loopback)(state) as listener:
                redirect = listener.redirect_uri
                if not re.fullmatch(r'http://127\.0\.0\.1:[1-9]\d{0,4}/oauth2callback', redirect):raise AuthError('Only a random local loopback redirect is permitted.')
                url = 'https://accounts.google.com/o/oauth2/v2/auth?' + urlencode({'client_id': item['clientId'], 'redirect_uri': redirect, 'response_type': 'code',
                      'scope': ' '.join(SCOPES[provider]), 'state': state, 'code_challenge': challenge, 'code_challenge_method': 'S256', 'access_type': 'offline', 'prompt': 'consent'})
                say('Sign in to Google and approve calendar read access in your browser. If it does not open, use this URL: ' + url)
                try:browser(url)
                except Exception:pass
                code = _secret(listener.wait())
        except AuthError:raise
        except Exception:raise AuthError('Could not complete the local browser sign-in. Check loopback access and try again.') from None
        response = _post(_token_endpoint(provider, item), {'client_id': item['clientId'], 'client_secret': client_secret, 'code': code,
                         'code_verifier': verifier, 'redirect_uri': redirect, 'grant_type': 'authorization_code'}, transport)
        bundle = _new_bundle(provider, item, response, now=now, client_secret=client_secret)
    else:
        endpoint = 'https://login.microsoftonline.com/' + item.get('tenant', 'common') + '/oauth2/v2.0/devicecode'
        device = _post(endpoint, {'client_id': item['clientId'], 'scope': ' '.join(SCOPES[provider])}, transport)
        device_code = _secret(device.get('device_code'));user_code = device.get('user_code')
        expiry = device.get('expires_in');interval = device.get('interval', 5)
        if (not isinstance(user_code, str) or not re.fullmatch(r'[A-Za-z0-9-]{4,32}', user_code)
                or type(expiry) is not int or not 1 <= expiry <= 900 or type(interval) is not int or not 1 <= interval <= 60):raise AuthError('The provider returned an invalid device sign-in response.')
        say('Open https://microsoft.com/devicelogin and enter code ' + user_code + '. Sign in and approve calendar read access.')
        # Use fixed trusted instructions; ignore provider-supplied URLs/message.
        elapsed = 0;response = None;deadline = time.monotonic() + expiry
        while elapsed + interval < expiry and time.monotonic() < deadline:
            sleep(interval);elapsed += interval
            response = _post(_token_endpoint(provider, item), {'grant_type': 'urn:ietf:params:oauth:grant-type:device_code', 'client_id': item['clientId'], 'device_code': device_code}, transport, polling=True)
            if response.get('error') == 'authorization_pending':continue
            if response.get('error') == 'slow_down':interval += 5;continue
            break
        if response is None or 'error' in response:raise AuthError('Device sign-in expired. Run calendar sign-in again.')
        bundle = _new_bundle(provider, item, response, now=now)
    _store(root, provider, item, bundle, credentials)
    return {'provider': provider, 'instance': item['id'], 'authorized': True, 'storage': 'keyring', 'message': 'Calendar read authorization saved in the OS credential store. No calendar events were changed.'}


def access_token(root, provider, instance, *, env=None, transport=None, credential_module=None, now=time.time):
    """Private read-time credential resolution; never starts interactive sign-in."""
    root = Path(root).resolve(strict=True);item = _config(root, provider, instance)
    credentials = _credentials(credential_module)
    if item.get('authMode', 'oauth') == 'access-token':
        try:raw = credentials.get(root, provider, item) if item.get('credentialStore') == 'keyring' else (os.environ if env is None else env).get(item['tokenVar'])
        except Exception:raise AuthError('Calendar access token is unavailable from the selected credential source.') from None
        return _secret(raw)
    try:raw = credentials.get(root, provider, item)
    except Exception:raise AuthError('No usable OAuth credential exists for this vault and connection. Use calendar sign-in first.') from None
    previous = _bundle(raw, provider, item)
    if previous['expires_at'] > now() + 60:return previous['access_token']
    values = {'grant_type': 'refresh_token', 'client_id': item['clientId'], 'refresh_token': previous['refresh_token']}
    if provider == 'google':values['client_secret'] = previous['client_secret']
    else:values['scope'] = ' '.join(SCOPES[provider])
    response = _post(_token_endpoint(provider, item), values, transport)
    bundle = _new_bundle(provider, item, response, now=now, previous=previous)
    _store(root, provider, item, bundle, credentials)
    return bundle['access_token']
