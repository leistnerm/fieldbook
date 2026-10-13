#!/usr/bin/env python3
"""One-page, read-only scope picker for the human-operated configuration CLI.

Uses saved connections and the diagnostics engine's bounded HTTPS transport.
Only labels, stable IDs and validated configuration patches leave this module;
it never saves settings, follows pagination links, or enables a workflow.
"""
import html
import importlib.util
import json
import os
from pathlib import Path
import re
import time
import unicodedata
from urllib.parse import urlencode

_spec = importlib.util.spec_from_file_location('fieldbook_scope_checks', Path(__file__).with_name('integration_checks.py'))
checks = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(checks)
MAX_CHOICES = 50


class DiscoveryError(ValueError):
    """A sanitized error suitable for the interactive CLI."""


def _plain(value, maximum=256):
    return (isinstance(value, str) and 0 < len(value) <= maximum
            and not any(unicodedata.category(c).startswith('C') for c in value))


def _label(value, identity):
    text = html.unescape(re.sub(r'<[^>]*>', '', value if isinstance(value, str) else ''))
    text = ''.join(' ' if unicodedata.category(c).startswith('C') else c for c in text)
    text = ' '.join(text.split())[:140]
    return (text + ' [' + identity + ']') if text and text != identity else identity


def _plan(provider, item):
    if provider == 'jira':
        if item['flavor'] == 'cloud':
            return '/rest/api/3/project/search', {'startAt': 0, 'maxResults': MAX_CHOICES}, None
        # Data Center's list endpoint is not paginated. The byte limit still
        # applies, and only its first MAX_CHOICES records are offered.
        return '/rest/api/2/project', {}, None
    if provider == 'agility':
        return '/query.v1', {}, {'from': 'Scope', 'select': ['Name', 'ID'], 'page': {'start': 0, 'size': MAX_CHOICES}}
    if provider == 'github':
        return '/user/repos', {'per_page': MAX_CHOICES, 'page': 1, 'sort': 'full_name', 'direction': 'asc'}, None
    if provider == 'azure':
        return '/_apis/projects', {'api-version': '7.1', '$top': MAX_CHOICES}, None
    return '/api/v1/courses', {'enrollment_state': 'active', 'per_page': MAX_CHOICES}, None


def _rows(provider, item, data):
    if provider == 'jira' and item['flavor'] == 'cloud':
        rows = data.get('values') if isinstance(data, dict) else None
    elif provider == 'azure':
        rows = data.get('value') if isinstance(data, dict) else None
    elif provider == 'agility':
        rows = data[0] if isinstance(data, list) and len(data) == 1 else None
    else:
        rows = data
    if not isinstance(rows, list) or any(not isinstance(row, dict) for row in rows):
        raise DiscoveryError('The service did not return the expected project list. Check the API URL and list permissions, or enter the scope manually.')
    return rows


def _choice(provider, row):
    if provider == 'jira':
        identity = row.get('key')
        if not isinstance(identity, str) or not re.fullmatch(r'[A-Za-z][A-Za-z0-9_]{0,127}', identity):return None
        return {'id': identity, 'label': _label(row.get('name'), identity), 'settings': {'filter': 'project = "' + identity + '"'}}
    if provider == 'agility':
        # query.v1 always returns _oid. ID itself may be a relationship object.
        identity = row.get('_oid')
        if not isinstance(identity, str) or not re.fullmatch(r'Scope:[1-9]\d{0,19}', identity):return None
        return {'id': identity, 'label': _label(row.get('Name'), identity), 'settings': {'where': {'Scope': identity}}}
    if provider == 'github':
        identity = row.get('full_name')
        if (row.get('has_issues') is not True or not isinstance(identity, str)
                or not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9-]{0,38}/[A-Za-z0-9_.-]{1,100}', identity)
                or identity.split('/')[1] in ('.', '..')):return None
        return {'id': identity, 'label': identity, 'settings': {'repositories': [identity]}}
    if provider == 'azure':
        identity, name = row.get('id'), row.get('name')
        if (not isinstance(identity, str) or not re.fullmatch(r'[0-9a-fA-F]{8}(?:-[0-9a-fA-F]{4}){3}-[0-9a-fA-F]{12}', identity)
                or not _plain(name) or name != name.strip() or re.search(r'[/\\]', name)
                or name in ('.', '..') or ('"' in name and "'" in name)):return None
        return {'id': identity, 'label': _label(name, identity), 'settings': {'project': name}}
    value = row.get('id')
    if isinstance(value, bool) or not isinstance(value, (int, str)):return None
    identity = str(value)
    if not re.fullmatch(r'[1-9]\d{0,19}', identity):return None
    return {'id': identity, 'label': _label(row.get('name') or row.get('course_code'), identity), 'settings': {'courseIds': [identity]}}


def discover_projects(root, provider, instanceID, *, env=None, transport=None, credential_module=None):
    """Return one bounded page of selectable saved-provider scopes.

    ``transport`` follows integration_checks' injection contract. An optional
    response ``headers`` dict supplies pagination indicators; links are never
    followed or returned. A full page also sets truncated conservatively, since
    some installations omit their pagination metadata.
    """
    if provider in ('google', 'microsoft'):
        path = Path(__file__).resolve().parents[1] / 'fieldbook_core/scripts/calendar_service.py'
        namespace = {'__file__': str(path), '__name__': 'calendar_discovery_service'}
        exec(compile(path.read_bytes(), str(path), 'exec'), namespace)
        return namespace['discover_projects'](root, provider, instanceID, env=env, transport=transport, credential_module=credential_module)
    if provider not in checks.PROVIDERS or not isinstance(instanceID, str) or not checks.ID.fullmatch(instanceID):
        raise DiscoveryError('Choose a supported provider and a valid saved instance ID.')
    try:
        root = Path(root).resolve(strict=True)
        item, base = checks._configuration(root, provider, instanceID)
        headers = checks._credential(root, provider, item, os.environ if env is None else env, credential_module)
        headers['User-Agent'] = 'Fieldbook-scope-picker'
        endpoint, query, body = _plan(provider, item)
        if body is not None:headers['Content-Type'] = 'application/json'
        send = transport if transport is not None else checks._Transport(time.monotonic() + checks.MAX_SECONDS)
        response = send('POST' if body is not None else 'GET', base + endpoint + ('?' + urlencode(query) if query else ''),
                        headers, json.dumps(body).encode() if body is not None else None)
        status = response.get('status') if isinstance(response, dict) else None
        if type(status) is not int or not 100 <= status <= 599:raise DiscoveryError('The HTTP response could not be verified.')
        if status != 200:raise DiscoveryError(checks._http_status(status))
        raw = response.get('body')
        if not isinstance(raw, bytes) or len(raw) > checks.MAX_BODY:
            raise DiscoveryError('The project list exceeded the bounded JSON preview size. Enter the scope manually.')
        try:data = checks._json(raw)
        except Exception:raise DiscoveryError('The service did not return valid bounded JSON. Check the API URL or enter the scope manually.') from None
        rows = _rows(provider, item, data)
    except (checks.DiagnosticError, DiscoveryError) as exc:
        raise DiscoveryError(str(exc)) from None
    except Exception as exc:
        raise DiscoveryError(checks._network_error(exc)) from None
    choices = [];seen = set();omitted = 0
    for row in rows[:MAX_CHOICES]:
        choice = _choice(provider, row)
        if choice is None or choice['id'].casefold() in seen:
            omitted += 1;continue
        seen.add(choice['id'].casefold());choices.append(choice)
    response_headers = response.get('headers', {})
    if not isinstance(response_headers, dict):response_headers = {}
    paging = {str(k).lower(): v for k, v in response_headers.items()}
    link = paging.get('link', '')
    more = isinstance(link, str) and bool(re.search(r'\brel\s*=\s*["\']?next\b', link, re.I))
    more |= bool(paging.get('x-ms-continuationtoken')) or paging.get('truncated') is True
    if provider == 'jira' and item['flavor'] == 'cloud':
        more |= data.get('isLast') is False or (type(data.get('total')) is int and data['total'] > len(rows))
    truncated = bool(more or len(rows) >= MAX_CHOICES)
    notice = 'Only the first response is inspected; this is a scope picker, not a connection or item-access test.'
    if truncated:notice += ' The list may be incomplete; enter an unlisted scope manually.'
    if omitted:notice += ' Entries that cannot be selected safely, duplicates, or repositories without Issues were omitted.'
    if not choices:notice += ' No selectable entries were returned; check list permissions or enter the scope manually.'
    if provider == 'canvas':notice += ' Only your active course enrollments are listed.'
    if provider == 'github':notice += ' Only accessible repositories with Issues enabled are listed.'
    return {'provider': provider, 'instance': instanceID, 'choices': choices, 'truncated': truncated, 'notice': notice}
