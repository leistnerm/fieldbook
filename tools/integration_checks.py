#!/usr/bin/env python3
"""Bounded, read-only connection diagnostics. No response content is returned.

check_integration(root, provider, instance_id, *, env=None, transport=None,
                  credential_module=None)

The injectable transport accepts (method, url, headers, body), where body is
bytes or None, and returns {"status": int, "body": bytes}. It must not follow
redirects. The production implementation enforces HTTPS, TLS verification,
15-second request timeouts and a 45-second per-instance budget. Only this
module's fixed read routes are called; Agility query and Azure WIQL POSTs are
documented reads. Diagnostics never test writes or attest a read-only token.
"""
import base64
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import re
import socket
import ssl
import stat
import time
import types
import importlib.util

_spec = importlib.util.spec_from_file_location('diagnostic_coverage', Path(__file__).resolve().parent / 'integration_coverage.py')
coverage = importlib.util.module_from_spec(_spec);_spec.loader.exec_module(coverage)
from urllib.error import HTTPError, URLError
from urllib.parse import quote, unquote, urlencode, urlsplit
from urllib.request import HTTPRedirectHandler, HTTPSHandler, Request, build_opener

PROVIDERS = ('jira', 'agility', 'github', 'azure', 'canvas', 'google', 'microsoft')
MAX_BODY = 1024 * 1024
MAX_SCOPES = 10
MAX_SECONDS = 45
ID = re.compile(r'[A-Za-z0-9][A-Za-z0-9_-]{0,63}')
SECRET_KEYS = {'token', 'password', 'apikey', 'accesskey', 'accesstoken', 'refreshtoken', 'secret', 'clientsecret'}


class DiagnosticError(Exception):
    """Only fixed messages constructed here may enter the public result."""


def _json(raw):
    def unique(pairs):
        value = {}
        for key, item in pairs:
            if key in value:raise ValueError()
            value[key] = item
        return value
    return json.loads(raw.decode('utf-8-sig'), object_pairs_hook=unique,
                      parse_constant=lambda _: (_ for _ in ()).throw(ValueError()))


def _safe_file(root, name, limit):
    path = root
    for part in Path(name).parts:
        path = path / part
        info = path.lstat()
        if path.is_symlink() or getattr(info, 'st_file_attributes', 0) & 0x400:
            raise ValueError()
    if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1 or info.st_size > limit:raise ValueError()
    fd = os.open(path, os.O_RDONLY | getattr(os, 'O_NOFOLLOW', 0))
    with os.fdopen(fd, 'rb') as stream:
        info = os.fstat(stream.fileno())
        if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1 or info.st_size > limit:raise ValueError()
        raw = stream.read(limit + 1)
    if len(raw) > limit:raise ValueError()
    return raw


def _secret_fields(value):
    if isinstance(value, dict):
        return any(re.sub('[^a-z]', '', str(k).lower()) in SECRET_KEYS or _secret_fields(v) for k, v in value.items())
    return isinstance(value, list) and any(_secret_fields(v) for v in value)


def _text(value, maximum=4096):
    return isinstance(value, str) and len(value) <= maximum and not any(ord(c) < 32 or ord(c) == 127 for c in value)


def _configuration(root, provider, identity):
    try:
        data = _json(_safe_file(root, 'fieldbook_core/' + provider + '.json', 65536))
        if not isinstance(data, dict) or not isinstance(data.get('instances'), list) or _secret_fields(data):raise ValueError()
        matches = [i for i in data['instances'] if isinstance(i, dict) and i.get('id') == identity]
        if len(matches) != 1:raise ValueError()
        item = matches[0]
    except Exception:
        raise DiagnosticError('Saved integration configuration is missing, invalid, linked, or contains literal credential fields.') from None
    raw = item.get('baseUrl')
    try:
        if not _text(raw, 2048) or not raw or any(c.isspace() for c in raw) or '\\' in raw:raise ValueError()
        base = urlsplit(raw)
        decoded = unquote(base.path)
        if (base.scheme != 'https' or not base.hostname or base.username or base.password or base.query or base.fragment
                or base.port == 0 or '\\' in decoded or not _text(decoded, 2048)
                or any(p in ('.', '..') for p in decoded.split('/'))):raise ValueError()
        if provider == 'canvas' and base.path not in ('', '/'):raise ValueError()
        if 'REPLACE' in raw.upper():
            raise DiagnosticError('Integration is not configured: replace the starter URL before testing.')
    except DiagnosticError:raise
    except Exception:
        raise DiagnosticError('Use a clean HTTPS integration URL without credentials, query, fragment, or relative path segments; Canvas requires an origin only.') from None
    token_var = item.get('tokenVar')
    if not isinstance(token_var, str) or not re.fullmatch(provider.upper() + r'_[A-Z0-9_]+', token_var):
        raise DiagnosticError('Configure a valid provider-prefixed token variable name.')
    if item.get('credentialStore', 'environment') not in ('environment', 'keyring'):
        raise DiagnosticError('Credential store must be environment or keyring.')
    for key in ('filter', 'project', 'memberId', 'email', 'apiVersion'):
        if key in item and not _text(item[key]):raise DiagnosticError('Integration scope and authentication settings must contain bounded single-line text.')
    if provider == 'jira':
        if item.get('flavor') not in ('cloud', 'server'):raise DiagnosticError('Jira flavor must be cloud or server.')
        if re.search(r'\border\s+by\b', item.get('filter', ''), re.I):raise DiagnosticError('Configure a JQL filter without ORDER BY.')
    if provider == 'agility':
        if not isinstance(item.get('where', {}), dict):raise DiagnosticError('Agility where must be an object.')
        if item.get('memberId') and not re.fullmatch(r'Member:\d+', item['memberId']):raise DiagnosticError('Configure Agility memberId in Member:123 form.')
    if provider == 'github':
        repos = item.get('repositories', [])
        if (not isinstance(repos, list) or any(not isinstance(r, str) or not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9-]*/[A-Za-z0-9_.-]+', r)
                or r.split('/')[1] in ('.', '..') for r in repos)):
            raise DiagnosticError('Configure repositories in owner/repository form.')
        if item.get('apiVersion') and not re.fullmatch(r'\d{4}-\d{2}-\d{2}', item['apiVersion']):raise DiagnosticError('GitHub API version must be a date.')
        if not isinstance(item.get('labels', []), list) or any(not _text(label, 256) for label in item.get('labels', [])):
            raise DiagnosticError('GitHub labels must be a list of bounded names.')
    if provider == 'azure':
        project = item.get('project', '')
        if re.search(r'[/\\]', project) or project in ('.', '..') or ('"' in project and "'" in project):
            raise DiagnosticError('Configure an Azure project name without slashes or mixed quotation marks.')
        if re.search(r'\b(select|from|order\s+by|asof)\b|;|--|/\*', item.get('filter', ''), re.I):raise DiagnosticError('Configure an Azure WIQL WHERE expression only.')
    if provider == 'canvas':
        ids = item.get('courseIds', [])
        if not isinstance(ids, list) or len(ids) > MAX_SCOPES or any(isinstance(v, bool) or not re.fullmatch(r'[1-9]\d*', str(v)) for v in ids):
            raise DiagnosticError('Configure at most 10 positive Canvas course IDs.')
    if provider in ('jira','agility','azure'):
        try:coverage.dates.date_fields(provider,item)
        except ValueError:raise DiagnosticError('Invalid dateFields mapping; use supported meanings and exact source field references.') from None
    return item, raw.rstrip('/')


def _credential(root, provider, instance, env, module):
    if instance.get('credentialStore') == 'keyring':
        try:
            if module is None:
                # Load the companion implementation, never a caller-selected script.
                home = Path(__file__).resolve().parents[1]
                raw = _safe_file(home, 'fieldbook_core/scripts/credentials.py', 65536)
                source = str(home / 'fieldbook_core/scripts/credentials.py')
                module = types.ModuleType('fieldbook_diagnostic_credentials');module.__file__ = source
                exec(compile(raw, source, 'exec'), module.__dict__)
            token = module.get(root, provider, instance)
        except Exception:
            raise DiagnosticError('OS credential lookup failed. Unlock the store, install the credential helper requirements, or save a key for this vault, instance and URL.') from None
    else:
        token = env.get(instance['tokenVar'])
    if (not isinstance(token, str) or not token or len(token) > 16384
            or any(c.isspace() or ord(c) < 32 or ord(c) == 127 for c in token)):
        raise DiagnosticError('API key is missing or malformed in the selected credential source; configure it and retry.')
    auth = 'Bearer ' + token
    if provider == 'azure':auth = 'Basic ' + base64.b64encode((':' + token).encode()).decode('ascii')
    if provider == 'jira' and instance['flavor'] == 'cloud':
        email = instance.get('email') or env.get('JIRA_EMAIL')
        if not _text(email, 320) or not email or ':' in email or any(c.isspace() for c in email):
            raise DiagnosticError('Jira Cloud needs an email in saved configuration or JIRA_EMAIL.')
        auth = 'Basic ' + base64.b64encode((email + ':' + token).encode()).decode('ascii')
    headers = {'Authorization': auth, 'Accept': 'application/json', 'Accept-Encoding': 'identity', 'User-Agent': 'Fieldbook-connection-check'}
    if provider == 'github':
        headers.update({'Accept': 'application/vnd.github+json', 'X-GitHub-Api-Version': instance.get('apiVersion') or '2026-03-10'})
    return headers


class _NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):return None


def _http_status(status):
    if 300 <= status < 400:return 'Redirect refused. Configure the final HTTPS API base URL; credentials were not forwarded.'
    return {
        400: 'HTTP 400: the service rejected the query or configuration.',
        401: 'HTTP 401: authentication or access was not accepted. Check the key, its server/account, expiry and required read access.',
        403: 'HTTP 403: this read was forbidden. Check read permissions, organization policy and token approval.',
        404: 'HTTP 404: the API route or scope was not found, or access to it is hidden. Check the URL, scope and permissions.',
        429: 'HTTP 429: rate limited. Wait before testing again.',
    }.get(status, 'The service returned an unsuccessful HTTP status; retry or check service availability.')


class _Transport:
    def __init__(self, deadline):
        self.deadline = deadline
        self.opener = build_opener(_NoRedirect(), HTTPSHandler(context=ssl.create_default_context()))

    def __call__(self, method, url, headers, body):
        if urlsplit(url).scheme != 'https':raise DiagnosticError('Only HTTPS requests are permitted.')
        remaining = self.deadline - time.monotonic()
        if remaining <= 0:raise DiagnosticError('Connection check time budget reached; remaining reads were not verified.')
        request = Request(url, headers=headers, data=body, method=method)
        try:
            with self.opener.open(request, timeout=min(15, remaining)) as response:
                status = response.status
                if status != 200:return {'status': status, 'body': b''}
                length = response.headers.get('Content-Length')
                if length and (not length.isdigit() or int(length) > MAX_BODY):raise DiagnosticError('Response exceeded the bounded JSON preview size.')
                # read1 limits each socket operation; budget is checked between chunks.
                pieces = [];size = 0
                while True:
                    if time.monotonic() >= self.deadline:raise DiagnosticError('Connection check time budget reached; response was not verified.')
                    block = response.read1(min(65536, MAX_BODY + 1 - size))
                    if not block:break
                    pieces.append(block);size += len(block)
                    if size > MAX_BODY:raise DiagnosticError('Response exceeded the bounded JSON preview size.')
                # Internal discovery only uses these to report an incomplete first
                # page. No header is displayed and no pagination URL is followed.
                paging = {}
                for name in ('link', 'x-ms-continuationtoken'):
                    value = response.headers.get(name, '')
                    paging[name] = value[:8192]
                    if len(value) > 8192:paging['truncated'] = True
                return {'status': status, 'body': b''.join(pieces), 'headers': paging}
        except HTTPError as exc:
            code = exc.code;exc.close()
            return {'status': code, 'body': b''}


def _network_error(exc):
    reason = exc.reason if isinstance(exc, URLError) else exc
    if isinstance(reason, (ssl.SSLError, ssl.CertificateError)):return 'TLS verification failed. Check the certificate and trusted HTTPS endpoint.'
    if isinstance(reason, (TimeoutError, socket.timeout)):return 'Request timed out; no read result was verified.'
    return 'Connection failed. Check network access, DNS and the configured HTTPS server; no read result was verified.'


def _plans(provider, item):
    """All routes, methods and selected fields are owned by this module."""
    identity = None;reads = [];missing = ''
    if provider == 'jira':
        version = '3' if item['flavor'] == 'cloud' else '2'
        identity = ('/rest/api/' + version + '/myself', {}, None, 'jira_identity')
        if item.get('filter', '').strip():
            endpoint = '/rest/api/3/search/jql' if version == '3' else '/rest/api/2/search'
            reads.append((endpoint, {'jql': '(' + item['filter'] + ') ORDER BY key ASC', 'maxResults': 1, 'fields': ','.join(['summary',*coverage.dates.date_fields(provider,item).values()])}, None, 'jira'))
        else:missing = 'No JQL filter is configured; project/filter read access was not tested.'
    if provider == 'github':
        identity = ('/user', {}, None, 'github_identity')
        for repo in dict.fromkeys(item.get('repositories', [])):
            query = {'state': 'all', 'per_page': 1}
            if item.get('labels'):query['labels'] = ','.join(item['labels'])
            reads.append(('/repos/' + repo + '/issues', query, None, 'list'))
        if not reads:missing = 'No repositories are configured; repository Issues read access was not tested.'
    if provider == 'canvas':
        identity = ('/api/v1/users/self/profile', {}, None, 'canvas_identity')
        today = datetime.now(timezone.utc).date().isoformat()
        for course in dict.fromkeys(str(v) for v in item.get('courseIds', [])):
            reads.append(('/api/v1/courses/' + course + '/assignments', {'override_assignment_dates': 'true', 'include[]': 'checkpoints', 'per_page': 1}, None, 'list'))
            for endpoint in ('quizzes', 'discussion_topics'):
                reads.append(('/api/v1/courses/' + course + '/' + endpoint, {'per_page': 1}, None, 'list'))
            window = {'context_codes[]': 'course_' + course, 'start_date': today, 'end_date': today, 'per_page': 1}
            reads.append(('/api/v1/planner/items', window, None, 'canvas_planner'))
            reads.append(('/api/v1/calendar_events', {**window, 'type': 'event', 'excludes[]': ['child_events', 'assignment']}, None, 'list'))
            reads.append(('/api/v1/announcements', {**window, 'active_only': 'true'}, None, 'list'))
        if not reads:missing = 'No course IDs are configured; assignment, quiz, discussion, planner, calendar and announcement reads were not tested.'
    if provider == 'agility':
        where = dict(item.get('where', {}))
        if item.get('memberId'):where['Owners'] = item['memberId']
        if where:
            reads.append(('/query.v1', {}, {'from': 'Workitem', 'select': ['Number', *coverage.dates.date_fields(provider,item).values()], 'where': where, 'page': {'start': 0, 'size': 1}}, 'agility'))
        else:missing = 'No Agility where filter or member ID is configured; work item read access was not tested.'
    if provider == 'azure':
        project = item.get('project', '')
        if project:
            delimiter = '"' if "'" in project else "'"
            query = 'SELECT [System.Id] FROM WorkItems WHERE [System.TeamProject] = ' + delimiter + project + delimiter
            if item.get('filter', '').strip():query += ' AND (' + item['filter'] + ')'
            query += ' ORDER BY [System.Id] ASC'
            reads.append(('/' + quote(project, safe='') + '/_apis/wit/wiql', {'api-version': '7.1', '$top': 1}, {'query': query}, 'azure'))
        else:missing = 'No Azure project is configured; project Work Items read access was not tested.'
    return identity, reads, missing


def _shape(data, shape):
    if shape == 'azure_detail':return isinstance(data,dict) and isinstance(data.get('value'),list) and len(data['value']) == 1 and isinstance(data['value'][0],dict) and type(data['value'][0].get('id')) is int and isinstance(data['value'][0].get('fields'),dict) and isinstance(data['value'][0]['fields'].get('System.Title'),str) and isinstance(data['value'][0]['fields'].get('System.State'),str)
    if shape == 'jira_identity':return isinstance(data, dict) and bool(data.get('accountId') or data.get('name'))
    if shape == 'github_identity':return isinstance(data, dict) and type(data.get('id')) is int and data['id'] > 0 and isinstance(data.get('login'), str) and bool(data['login'])
    if shape == 'canvas_identity':return isinstance(data, dict) and type(data.get('id')) is int and data['id'] > 0
    if shape == 'canvas_planner':return isinstance(data, list) and all(isinstance(item, dict) and item.get('plannable_id') and isinstance(item.get('plannable_type'), str) and isinstance(item.get('plannable'), dict) for item in data)
    if shape == 'list':return isinstance(data, list) and all(isinstance(item, dict) and item.get('id') for item in data)
    if shape == 'jira':return isinstance(data, dict) and isinstance(data.get('issues'), list) and all(isinstance(item, dict) and item.get('id') for item in data['issues'])
    if shape == 'agility':return isinstance(data, list) and len(data) == 1 and isinstance(data[0], list) and all(isinstance(item, dict) and item.get('Number') for item in data[0])
    if shape == 'azure':return isinstance(data, dict) and isinstance(data.get('workItems'), list) and all(isinstance(item, dict) and type(item.get('id')) is int and item['id'] > 0 for item in data['workItems'])
    return False


def _check_integration(root, provider, instance, *, env=None, transport=None, credential_module=None):
    """Test a saved instance, even if its workflow feature is currently disabled.

    ok requires all configured bounded scope reads and authentication evidence.
    No scope, excess scopes, or unverified public-read authentication is incomplete.
    Identity can remain unknown for Agility/Azure's documented protected queries.
    """
    if provider in ('google', 'microsoft'):
        path = Path(__file__).resolve().parents[1] / 'fieldbook_core/scripts/calendar_service.py'
        namespace = {'__file__': str(path), '__name__': 'calendar_diagnostic_service'}
        exec(compile(path.read_bytes(), str(path), 'exec'), namespace)
        return namespace['check_integration'](root, provider, instance, env=env, transport=transport, credential_module=credential_module)
    valid_provider = isinstance(provider, str) and provider in PROVIDERS
    valid_identity = isinstance(instance, str) and bool(ID.fullmatch(instance))
    result = {'provider': provider if valid_provider else 'unknown', 'instance': instance if valid_identity else 'invalid', 'ok': False, 'checks': []}
    def record(stage, status, message):result['checks'].append({'stage': stage, 'status': status, 'message': message})
    if not valid_provider or not valid_identity:
        record('configuration', 'fail', 'Choose a supported provider and a valid saved instance ID.');return result
    try:
        root = Path(root).resolve(strict=True)
        item, base = _configuration(root, provider, instance)
        identity, reads, missing = _plans(provider, item)
        record('configuration', 'pass', 'Saved instance and HTTPS destination passed local validation.')
    except Exception as exc:
        record('configuration', 'fail', str(exc) if isinstance(exc, DiagnosticError) else 'Could not safely load the saved integration configuration.')
        record('url', 'skip', 'Server was not contacted because saved configuration needs attention.')
        return result
    try:
        headers = _credential(root, provider, item, os.environ if env is None else env, credential_module)
        record('credential', 'pass', 'A key was loaded from the selected credential source; remote authentication is checked separately.')
    except Exception as exc:
        record('credential', 'fail', str(exc) if isinstance(exc, DiagnosticError) else 'Could not load a key from the selected credential source.')
        record('url', 'skip', 'Server was not contacted because credentials need attention.')
        return result
    deadline = time.monotonic() + MAX_SECONDS
    try:send = transport if transport is not None else _Transport(deadline)
    except Exception as exc:
        record('connection', 'fail', _network_error(exc));return result
    attempted = False;http_seen = False;network_message = '';last_data = None
    def probe(plan):
        nonlocal attempted, http_seen, network_message, last_data
        last_data = None
        endpoint, query, body, shape = plan
        status = None
        try:
            if time.monotonic() >= deadline:raise DiagnosticError('Connection check time budget reached; remaining reads were not verified.')
            url = base + endpoint + ('?' + urlencode(query, doseq=True) if query else '')
            req_headers = dict(headers)
            if body is not None:req_headers['Content-Type'] = 'application/json'
            attempted = True
            response = send('POST' if body is not None else 'GET', url, req_headers, json.dumps(body).encode() if body is not None else None)
            status = response.get('status') if isinstance(response, dict) else None
            if type(status) is not int or not 100 <= status <= 599:raise DiagnosticError('The HTTP response could not be verified.')
            http_seen = True
            if status != 200:raise DiagnosticError(_http_status(status))
            raw = response.get('body')
            if not isinstance(raw, bytes) or len(raw) > MAX_BODY:raise DiagnosticError('Response exceeded the bounded JSON preview size or was not valid bytes.')
            try:data = _json(raw)
            except Exception:raise DiagnosticError('The service did not return a valid bounded JSON response.') from None
            if not _shape(data, shape):raise DiagnosticError('The service response did not match the expected read API; check the API base URL and access.')
            last_data = data
            empty = (not data if shape in ('list', 'canvas_planner') else not data['issues'] if shape == 'jira' else not data[0] if shape == 'agility' else not data['workItems'] if shape == 'azure' else False)
            return True, empty, '', status
        except DiagnosticError as exc:
            if type(status) is not int or not 100 <= status <= 599:network_message = str(exc)
            return False, False, str(exc), status
        except Exception as exc:
            network_message = _network_error(exc)
            return False, False, network_message, status
    authenticated = False
    identity_status = None
    if identity:
        passed, _, message, identity_status = probe(identity)
        authenticated = passed
        record('identity', 'pass' if passed else 'fail' if identity_status == 401 else 'unknown', 'The current-user endpoint confirmed an authenticated account; account details are not displayed.' if passed else message + ' Current-user identity is unverified; scope reads will still be attempted.')
    else:
        record('identity', 'unknown', 'No independent current-user probe is used for this provider; its documented protected query is tested instead.')
    successful = True
    if missing:record('scope', 'skip', missing)
    max_reads = MAX_SCOPES * 6 if provider == 'canvas' else MAX_SCOPES
    for index, plan in enumerate(reads[:max_reads], 1):
        passed, empty, message, _ = probe(plan)
        successful &= passed
        label = (plan[0] + ' [' + (plan[1].get('context_codes[]') or 'course_' + plan[0].split('/')[4]) + ']: ') if provider == 'canvas' else ''
        record('scope_' + str(index), 'pass' if passed else 'fail', label +
               (('Configured scope read succeeded. The query returned no records; access to any expected item remains unverified.' if empty else 'Configured scope read succeeded. This bounded sample does not verify every item or permission.') if passed else message))
        if passed and provider in ('agility', 'azure'):authenticated = True
        sample = last_data if passed else None
        if passed and provider == 'azure':
            ids = [value['id'] for value in sample['workItems']]
            if ids:
                requested = ids[0]
                detail = ('/_apis/wit/workitemsbatch', {'api-version':'7.1'}, {'ids':[requested], 'fields':['System.Id','System.Title','System.State',*coverage.dates.date_fields(provider,item).values()], 'errorPolicy':'Fail'}, 'azure_detail')
                detail_ok, _, detail_error, _ = probe(detail)
                detail_ok = detail_ok and last_data['value'][0]['id'] == requested
                successful &= detail_ok
                record('work_item_details','pass' if detail_ok else 'fail','Selected work item and requested fields were read through the documented batch read.' if detail_ok else detail_error or 'The batch did not return the selected work item.')
                sample = last_data['value'][0]['fields'] if detail_ok else None
            else:
                record('work_item_details','skip','No sample work item was returned; detail and configured date field access remain unverified.')
                sample = None
        elif passed and provider == 'jira':sample = sample['issues'][0].get('fields',{}) if sample['issues'] else None
        elif passed and provider == 'agility':sample = sample[0][0] if sample[0] else None
        if provider in ('jira','agility','azure'):
            mapping = coverage.dates.date_fields(provider,item)
            statuses = {kind:('not_returned' if sample is None or field not in sample else 'unset' if sample[field] in (None,'') else 'present' if coverage.dates.valid_date(sample[field]) else 'invalid_date') for kind,field in mapping.items()}
            record('date_fields','unknown' if any(value in ('not_returned','invalid_date') for value in statuses.values()) else 'pass',
                   'Date field sample: ' + json.dumps(statuses,sort_keys=True) + '. Missing/unset fields do not authorize clearing local dates; present values still need meaning/timezone review.' if mapping else 'No date fields are mapped; dates are not inferred from timeboxes or iterations.')
    if len(reads) > max_reads:
        record('scope_remaining', 'skip', 'Only the first 10 configured scopes were tested. Additional scopes remain unverified; reduce the configured selection to test them.')
    record('url', 'pass' if http_seen else 'fail' if attempted or network_message else 'skip',
           'The HTTPS server responded. This confirms reachability; the individual checks determine API-route and access validity.' if http_seen else network_message or 'No appropriate read scope is configured, so the server was not contacted.')
    record('authentication', 'pass' if authenticated else 'fail' if identity_status == 401 else 'unknown',
           ('The service accepted an authenticated read request; the account identity was not independently checked.' if identity is None else 'The current-user read confirmed authentication.') if authenticated else
           'The current-user authentication check returned HTTP 401. Check the key, its server/account, expiry and required read access.' if identity_status == 401 else
           'Authentication remains unverified; a successful public or scope read alone is insufficient evidence.')
    record('write_permissions', 'unknown', 'Only read operations were tested. This does not prove the key lacks write permissions.')
    result['ok'] = bool(reads) and len(reads) <= max_reads and successful and authenticated
    return result


def check_integration(root, provider, instance, **kwargs):
    result = _check_integration(root,provider,instance,**kwargs)
    if isinstance(provider,str) and provider in coverage.CATALOG:
        try:item,_ = _configuration(Path(root).resolve(strict=True),provider,instance)
        except Exception:item = {}
        report = coverage.summary(provider,item)
        report.update(checked_at=datetime.now(timezone.utc).isoformat(), checks=result['checks'],
                      freshness='Connection diagnostic at checked_at; no sync result is cached.',
                      completeness='Bounded samples only; read each check for unverified or failed coverage. Token write privileges are never tested.')
        result['coverage'] = report
    return result
