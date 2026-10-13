#!/usr/bin/env python3
"""Guided Fieldbook configuration; --check is offline, --test explicitly checks saved remote connections."""
import argparse
import copy
from datetime import datetime, timezone
import getpass
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import sys
import unicodedata
import uuid
import warnings
import webbrowser
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parents[1]
RECORD_PROVIDERS = ('jira', 'agility', 'github', 'azure', 'canvas')
CALENDAR_PROVIDERS = ('google', 'microsoft')
PROVIDERS = (*RECORD_PROVIDERS, *CALENDAR_PROVIDERS)
CALENDAR_URLS = {'google':'https://www.googleapis.com/calendar/v3', 'microsoft':'https://graph.microsoft.com/v1.0'}
FEATURES = (*PROVIDERS, 'reviews', 'autoPeople', 'autoCommit')
STATUSES = {'backlog', 'active', 'blocked', 'done', 'dropped'}
SECRET_KEYS = {'token', 'password', 'apikey', 'accesskey', 'accesstoken', 'refreshtoken', 'secret', 'clientsecret'}
FIELDS = {
    'jira': [('flavor', 'Cloud or server', 'text'), ('email', 'Jira Cloud email (or use JIRA_EMAIL)', 'text'),
             ('filter', 'Optional JQL filter without ORDER BY', 'text'), ('statusMap', 'Status map JSON object (optional)', 'object')],
    'agility': [('memberId', 'Your member ID, e.g. Member:123 (optional)', 'text'),
                ('where', 'Scope filter JSON object (optional)', 'object'), ('statusMap', 'Status map JSON object (optional)', 'object')],
    'github': [('repositories', 'Repositories, comma-separated owner/repository', 'list'),
               ('login', 'Your exact login (optional)', 'text'), ('labels', 'Labels, comma-separated (optional)', 'list'),
               ('apiVersion', 'GitHub API version', 'text'), ('statusMap', 'Status map JSON object (optional)', 'object'),
               ('resolutionMap', 'Resolution map JSON object (optional)', 'object')],
    'azure': [('project', 'Project name (needed for mine/team/all)', 'text'),
              ('filter', 'Optional WIQL WHERE expression', 'text'), ('dueField', 'Due-date field reference (optional)', 'text'),
              ('completionField', 'Completion-date field reference (optional)', 'text'), ('statusMap', 'Status map JSON object (optional)', 'object')],
    'canvas': [('courseIds', 'Selected course IDs, comma-separated (optional; maximum 10)', 'list')],
    'google': [('authMode','Authentication: oauth or access-token','text'),
               ('clientId','Google Desktop OAuth client ID (needed for oauth)','text'),
               ('calendarIds','Selected calendar IDs (optional; choose calendars with menu 7)','list')],
    'microsoft': [('authMode','Authentication: oauth or access-token','text'),
                  ('clientId','Microsoft public-client application ID (needed for oauth)','text'),
                  ('tenant','Microsoft tenant: common, organizations, consumers, tenant ID or domain','text'),
                  ('calendarIds','Selected calendar IDs (optional; choose calendars with menu 7)','list')],
}


def module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    value = importlib.util.module_from_spec(spec); spec.loader.exec_module(value)
    return value


admin = module('wizard_admin', ROOT / 'tools/manage-vault.py')
dates = module('wizard_dates', ROOT / 'tools/tracker_dates.py')
for provider in ('jira', 'agility', 'azure'):
    FIELDS[provider].append(('dateFields', 'Date mappings JSON: due/completed/start/target/review/available_from/closes_at to exact fields; empty string disables a mapping', 'object'))


def contains_secret(value):
    if isinstance(value, dict):
        return any(re.sub(r'[^a-z]', '', str(key).lower()) in SECRET_KEYS or contains_secret(item)
                   for key, item in value.items())
    return isinstance(value, list) and any(contains_secret(item) for item in value)


def clean_url(value, provider):
    if not isinstance(value, str) or not value or '\\' in value or any(c.isspace() or ord(c) < 32 or ord(c) == 127 for c in value):
        raise ValueError('Use a clean HTTPS URL without credentials, query or fragment')
    try:
        parts = urlsplit(value)
        if (parts.scheme != 'https' or not parts.hostname or parts.username or parts.password
                or parts.query or parts.fragment or parts.port == 0):
            raise ValueError()
    except ValueError:
        raise ValueError('Use a clean HTTPS URL without credentials, query or fragment') from None
    if provider == 'canvas' and parts.path not in ('', '/'):
        raise ValueError('Canvas requires the institution HTTPS origin without a path')
    return value.rstrip('/')


def check_instance(provider, item, allow_missing_client=False):
    """Validate shapes and adapter constraints; never include supplied values in errors."""
    if not isinstance(item, dict):raise ValueError('Each instance must be an object')
    if contains_secret(item):raise ValueError('Remove literal credential fields; use tokenVar or the OS credential store')
    if not isinstance(item.get('id'), str) or not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_-]{0,63}', item['id']):
        raise ValueError('Instance ID must be 1..64 letters, digits, underscores or hyphens, starting with a letter or digit')
    clean_url(item.get('baseUrl'), provider)
    if not isinstance(item.get('tokenVar'), str) or not re.fullmatch(provider.upper() + r'_[A-Z0-9_]+', item['tokenVar']):
        raise ValueError('Token variable must start with ' + provider.upper() + '_ and contain only uppercase letters, digits and underscores')
    if item.get('credentialStore', 'environment') not in ('environment', 'keyring'):
        raise ValueError('Credential store must be environment or keyring')
    for key, _, kind in FIELDS[provider]:
        if key not in item:continue
        value = item[key]
        if kind == 'text' and (not isinstance(value, str) or any(ord(c) < 32 for c in value)):
            raise ValueError(key + ' must be single-line text')
        if kind == 'list' and (not isinstance(value, list) or any(not isinstance(x, (str, int)) or isinstance(x, bool) for x in value)):
            raise ValueError(key + ' must be a list of names or IDs')
        if kind == 'object' and not isinstance(value, dict):raise ValueError(key + ' must be a JSON object')
    for name in ('statusMap', 'resolutionMap'):
        if name in item and any(not isinstance(v, str) or v not in STATUSES for v in item[name].values()):
            raise ValueError(name + ' values must be backlog, active, blocked, done or dropped')
    if provider in ('jira', 'agility', 'azure'):dates.date_fields(provider, item)
    if provider == 'jira':
        if item.get('flavor') not in ('cloud', 'server'):raise ValueError('Jira flavor must be cloud or server')
        if re.search(r'\border\s+by\b', item.get('filter', ''), re.I):raise ValueError('JQL filter must omit ORDER BY')
    if provider == 'agility' and item.get('memberId') and not re.fullmatch(r'Member:\d+', item['memberId']):
        raise ValueError('Agility memberId must use Member:123 form')
    if provider == 'github':
        if any(not isinstance(v, str) or not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9-]*/[A-Za-z0-9_.-]+', v)
               or v.split('/')[1] in ('.', '..') for v in item.get('repositories', [])):
            raise ValueError('Repositories must use owner/repository form')
        if item.get('login') and not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9-]*', item['login']):raise ValueError('GitHub login must be an exact account name')
        if any(not isinstance(x, str) for x in item.get('labels', [])):raise ValueError('GitHub labels must be text')
    if provider == 'azure':
        if re.search(r'[/\\\x00-\x1f]', item.get('project', '')) or item.get('project') in ('.', '..'):
            raise ValueError('Azure project must be a project name without slashes')
        if re.search(r'\b(select|from|order\s+by|asof)\b|;|--|/\*', item.get('filter', ''), re.I):
            raise ValueError('Azure filter must be a WHERE expression only')
        for key in ('dueField', 'completionField'):
            if item.get(key) and not re.fullmatch(r'[A-Za-z][A-Za-z0-9_.]*', item[key]):raise ValueError(key + ' must be a field reference name')
    if provider == 'canvas':
        ids = item.get('courseIds', [])
        if len(ids) > 10 or any(not re.fullmatch(r'[1-9]\d*', str(v)) for v in ids):raise ValueError('Canvas courseIds must contain at most 10 positive IDs')
    if provider in CALENDAR_PROVIDERS:
        if item['baseUrl'].rstrip('/') != CALENDAR_URLS[provider]:raise ValueError('Calendar API URL must use the fixed Google Calendar or Microsoft Graph endpoint')
        mode = item.get('authMode','oauth')
        if mode not in ('oauth','access-token'):raise ValueError('Calendar authMode must be oauth or access-token')
        client = item.get('clientId','')
        if mode == 'oauth':
            if item.get('credentialStore') != 'keyring':raise ValueError('Calendar OAuth requires OS credential storage (keyring)')
            if not client and not allow_missing_client:raise ValueError('Configure an OAuth client ID before signing in')
        if client:
            pattern = r'[A-Za-z0-9_-]+\.apps\.googleusercontent\.com' if provider == 'google' else r'[0-9a-fA-F]{8}(?:-[0-9a-fA-F]{4}){3}-[0-9a-fA-F]{12}'
            if not re.fullmatch(pattern,client):raise ValueError('Use the provider-issued Google Desktop client ID or Microsoft application GUID')
        if provider == 'microsoft':
            tenant = item.get('tenant','common')
            if not isinstance(tenant,str) or not (tenant in ('common','organizations','consumers')
                    or re.fullmatch(r'[0-9a-fA-F]{8}(?:-[0-9a-fA-F]{4}){3}-[0-9a-fA-F]{12}',tenant)
                    or re.fullmatch(r'[A-Za-z0-9](?:[A-Za-z0-9-]*[A-Za-z0-9])?(?:\.[A-Za-z0-9](?:[A-Za-z0-9-]*[A-Za-z0-9])?)+',tenant)):
                raise ValueError('Use a valid Microsoft tenant ID/domain, common, organizations or consumers')
        calendars = item.get('calendarIds',[])
        if len(calendars)>10 or any(not isinstance(v,str) or not v or v in ('.','..') or len(v)>1024 or any(unicodedata.category(c).startswith('C') for c in v) for v in calendars):
            raise ValueError('Choose at most 10 non-empty calendar IDs without control characters')
        if provider == 'google' and 'primary' in calendars:raise ValueError('Use the exact Google calendar ID from the picker; primary is not a stable record identity')


def configuration_errors(config):
    if not isinstance(config, dict):return ['fieldbook.json must be an object']
    errors = []
    setups = config.get('setups')
    if not isinstance(setups, list) or any(v not in ('personal', 'work', 'school') for v in setups) or len(set(setups)) != len(setups):
        errors.append('Choose unique personal, work and/or school setups, or core only')
    if config.get('workRole') not in ('individual-contributor', 'people-manager'):errors.append('Choose an individual contributor or people manager work role')
    features = config.get('features')
    if not isinstance(features, dict):errors.append('features must be an object')
    else:
        for key in FEATURES:
            if type(features.get(key, False)) is not bool:errors.append(key + ' must be true or false')
        if isinstance(setups, list):
            if features.get('reviews') and 'work' not in setups:errors.append('Reviews require work')
            if features.get('canvas') and 'school' not in setups:errors.append('Canvas requires school')
    if not isinstance(config.get('defaults'), dict):errors.append('defaults must be an object')
    if not isinstance(config.get('workFocus', []), list) or any(not isinstance(v, str) for v in config.get('workFocus', [])):
        errors.append('workFocus must be a list of labels')
    if not isinstance(config.get('workSubrole', ''), str):errors.append('workSubrole must be text')
    if contains_secret(config):errors.append('Remove literal credential fields from fieldbook.json before using this editor')
    return errors


def arguments(config, apply=False, explicit_defaults=False):
    flags = {key: ('on' if config['features'].get(key, False) else 'off') for key in FEATURES}
    flags['auto_people'] = flags.pop('autoPeople');flags['auto_commit'] = flags.pop('autoCommit')
    return argparse.Namespace(setups=','.join(config['setups']) or 'core', work_role=config['workRole'],
                              work_focus=','.join(config.get('workFocus', [])) or 'none',
                              work_subrole=config.get('workSubrole', '') or 'none', defaults=copy.deepcopy(config.get('defaults',{})), explicit_defaults=explicit_defaults, apply=apply, **flags)


def test_connections(root, provider='all', instance=None, checker=None, progress=None):
    """Explicit diagnostics use saved provider files, even before feature activation."""
    if provider not in ('all', *PROVIDERS):raise ValueError('Choose all or a supported provider')
    if instance is not None and (provider == 'all' or not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_-]{0,63}', instance)):
        raise ValueError('--instance requires a named provider and a valid instance ID')
    root = Path(root).resolve(strict=True)
    results = []
    def issue(p, identity, stage, status, message, skipped=False):
        results.append({'provider':p, 'instance':identity, 'ok':False, 'skipped':skipped,
                        'checks':[{'stage':stage, 'status':status, 'message':message}]})
    for p in PROVIDERS if provider == 'all' else (provider,):
        try:
            path = admin.safe(root, 'fieldbook_core/' + p + '.json')
            if not path.exists():data = {'instances':[]}
            else:
                if not path.is_file() or path.stat().st_size > 65536:raise ValueError()
                data = json.loads(admin.read(path))
            if not isinstance(data, dict) or not isinstance(data.get('instances'), list) or contains_secret(data):raise ValueError()
        except (ValueError, OSError, TypeError):
            issue(p, None, 'configuration', 'fail', 'Repair the saved provider JSON; it must contain an instances list and no literal API keys.')
            continue
        selected = data['instances'] if instance is None else [i for i in data['instances'] if isinstance(i, dict) and i.get('id') == instance]
        if not selected:
            skipped = provider == 'all'
            issue(p, instance, 'configuration', 'skip' if skipped else 'unknown', 'No matching saved connection is configured.', skipped)
            continue
        seen = set()
        for item in selected:
            try:
                check_instance(p, item, allow_missing_client=True)
                if item['id'] in seen:raise ValueError()
                seen.add(item['id'])
            except (ValueError, TypeError):
                issue(p, None, 'configuration', 'fail', 'Repair this saved instance: check its unique ID, HTTPS URL, variable name and provider fields.')
                continue
            # Reject duplicates before consulting credentials for either copy.
            if sum(1 for i in data['instances'] if isinstance(i,dict) and i.get('id') == item['id']) != 1:
                issue(p, item['id'], 'configuration', 'fail', 'Instance ID is duplicated; make each saved ID unique.')
                continue
            if 'REPLACE' in item['baseUrl'].upper():
                skipped = provider == 'all'
                issue(p, item['id'], 'url', 'skip' if skipped else 'unknown', 'Starter URL is not configured; save the real service URL first.', skipped)
                continue
            if p in CALENDAR_PROVIDERS and item.get('authMode','oauth') == 'oauth' and not item.get('clientId'):
                skipped = provider == 'all'
                issue(p,item['id'],'configuration','skip' if skipped else 'unknown','Calendar OAuth is not configured; save a client ID and sign in first.',skipped)
                continue
            if (provider == 'all' and p == 'github' and item['id'] == 'personal'
                    and item['baseUrl'].rstrip('/') == 'https://api.github.com' and item['tokenVar'] == 'GITHUB_TOKEN'
                    and item.get('credentialStore','environment') == 'environment'
                    and not any(item.get(k) for k in ('repositories','login','labels','statusMap','resolutionMap'))):
                issue(p, item['id'], 'scope', 'skip', 'Default GitHub connection has no selected repositories. Configure a scope, or test github explicitly to check authentication.', True)
                continue
            try:
                if progress:progress(p, item['id'])
                check = checker or module('fieldbook_integration_checks', ROOT / 'tools/integration_checks.py').check_integration
                result = check(root, p, item['id'])
                if not isinstance(result, dict) or type(result.get('ok')) is not bool or not isinstance(result.get('checks'), list) or not result['checks']:
                    raise ValueError()
                checks = []
                for entry in result['checks']:
                    if (not isinstance(entry, dict) or entry.get('status') not in ('pass','fail','skip','unknown')
                            or not isinstance(entry.get('stage'), str) or not isinstance(entry.get('message'), str)):
                        raise ValueError()
                    checks.append({key:entry[key] for key in ('stage','status','message')})
                # The helper distinguishes required access checks from optional identity
                # discovery. A protected Azure/Agility query can verify access without
                # additional profile permissions; missing required scope keeps ok false.
                verified = result['ok'] and not any(c['status'] == 'fail' for c in checks)
                results.append({'provider':p,'instance':item['id'],'ok':verified,'skipped':False,'checks':checks})
            except Exception:
                issue(p, item['id'], 'connection', 'fail', 'Connection test could not finish. Check the local diagnostic tool, saved configuration, credentials and network; no remote response details were printed.')
    failed = sum(any(c['status']=='fail' for c in r['checks']) for r in results)
    verified = sum(r['ok'] for r in results)
    skipped = sum(r['skipped'] for r in results)
    not_verified = len(results) - failed - verified - skipped
    return {'readOnly':True, 'savedConfiguration':True, 'ok':bool(verified) and not failed and not not_verified,
            'status':'failed' if failed else 'not_verified' if not_verified or not verified else 'passed',
            'verified':verified,'failed':failed,'notVerified':not_verified,'skipped':skipped,
            'exitCode':1 if failed else 2 if not_verified or not verified else 0, 'results':results,
            'notice':'Explicit tests read saved connections without enabling features or changing notes. Skipped or unknown checks do not verify access. Agility/Azure may use read-only POST queries.'}


class Session:
    def __init__(self, root):
        self.root = Path(root).resolve(strict=True)
        self.config = self.load('fieldbook.json')
        self.connections = {p: self.load('fieldbook_core/' + p + '.json', {'instances': []}) for p in PROVIDERS}
        self.original_config = copy.deepcopy(self.config)
        self.original_connections = copy.deepcopy(self.connections)
        self.key_updates = set()
        self.credential_attempted = False
        self.credentials_updated = 0
        self.save_attempted = False
        self.baseline = self.snapshot()

    def load(self, name, missing=None):
        path = admin.safe(self.root, name)
        if missing is not None and not path.exists():return copy.deepcopy(missing)
        if not path.is_file() or path.stat().st_size > 65536:raise ValueError(name + ' must be a regular JSON file no larger than 64 KiB')
        try:return json.loads(admin.read(path))
        except (ValueError, UnicodeError):raise ValueError('Invalid JSON in ' + name) from None

    def snapshot(self):
        names = {'fieldbook.json', 'fieldbook-manifest.json', 'tools/setup-catalog.json', 'tools/starter-seeds.json',
                 '.fieldbook/modules/state.json', '.obsidian/plugins/tasknotes/data.json',
                 *('fieldbook_core/' + p + '.json' for p in PROVIDERS)}
        for entry in admin.setup_module().catalog(self.root, admin.safe, admin.read):
            names.update((entry['path'], entry['path'] + '.fieldbook-new', '.fieldbook/modules/files/' + entry['path']))
        bank = admin.safe(self.root, '.fieldbook/modules')
        if bank.exists():
            for path in admin.files(bank):names.add(path.relative_to(self.root).as_posix())
        return {name: admin.safe(self.root, name).read_bytes() if admin.safe(self.root, name).is_file() else None for name in names}

    def unchanged(self):
        if self.snapshot() != self.baseline:raise ValueError('Vault configuration or managed resources changed during editing; cancel and reopen the wizard')

    def validate(self):
        errors = configuration_errors(self.config);warnings = []
        for provider, data in self.connections.items():
            if not isinstance(data, dict) or not isinstance(data.get('instances'), list):
                errors.append(provider + ': config must contain an instances list');continue
            if contains_secret(data):errors.append(provider + ': remove literal credential fields before editing');continue
            seen = set()
            enabled = isinstance(self.config, dict) and isinstance(self.config.get('features'), dict) and self.config['features'].get(provider) is True
            if enabled and not data['instances']:errors.append(provider + ': add an instance before enabling')
            for index, item in enumerate(data['instances']):
                label = provider + ' instance ' + str(index + 1)
                try:
                    check_instance(provider, item, allow_missing_client=not enabled)
                    if item['id'] in seen:raise ValueError('Duplicate instance ID')
                    seen.add(item['id'])
                    if provider in CALENDAR_PROVIDERS and item.get('authMode','oauth') == 'oauth' and not item.get('clientId'):
                        warnings.append(label + ': save an OAuth client ID and sign in before enabling')
                    if 'REPLACE' in item['baseUrl'].upper():
                        (errors if enabled else warnings).append(label + ': replace the starter URL before enabling')
                    if enabled:
                        if provider == 'jira' and item['flavor'] == 'cloud' and not item.get('email'):
                            warnings.append(label + ': Jira Cloud needs email here or JIRA_EMAIL at runtime')
                        if provider in ('github','azure') and not item.get('repositories' if provider == 'github' else 'project'):
                            warnings.append(label + ': linked records work; configure repository/project scope for mine, team or all')
                        if provider == 'canvas' and not item.get('courseIds'):
                            warnings.append(label + ': discover courses first, then choose course IDs when importing')
                except (ValueError, TypeError):errors.append(label + ': ' + str(sys.exc_info()[1]))
        return {'errors': errors, 'warnings': warnings}

    def preview(self):
        self.unchanged()
        result = self.validate()
        if result['errors']:return result
        configured = admin.configure(self.root, arguments(self.config,explicit_defaults=getattr(self,'explicit_defaults',False)))
        changed = ['fieldbook.json'] if configured['settings'] != self.original_config else []
        changed += ['fieldbook_core/' + p + '.json' for p in PROVIDERS if self.connections[p] != self.original_connections[p]]
        return {**result, 'changed': changed, 'settings': configured['settings'], 'activation': configured['activation'],
                'tasknotes': configured['tasknotes_area_default']}

    def commit(self, password=getpass.getpass, credential_module=None):
        result = self.preview()
        if result['errors']:raise ValueError('Fix validation errors before saving')
        settings = result['settings']
        activation = admin.setup_module().plan(self.root, settings, admin.safe, admin.read, admin.write)
        writes = dict(activation.writes)
        writes['fieldbook.json'] = admin.dump(settings)
        plugin, _ = admin.tasknotes_default_plan(self.root, self.original_config.get('defaults', {}).get('area', ''), settings['defaults']['area'])
        if plugin:writes[plugin[0]] = plugin[1]
        for p in PROVIDERS:
            if self.connections[p] != self.original_connections[p]:writes['fieldbook_core/' + p + '.json'] = admin.dump(self.connections[p])
        # Prompt only after Save confirmation, without writes until all prompts succeed.
        secrets = []
        for provider, identity in sorted(self.key_updates):
            instance = next((i for i in self.connections[provider]['instances'] if i['id'] == identity), None)
            if (instance is None or instance.get('credentialStore') != 'keyring'
                    or provider in CALENDAR_PROVIDERS and instance.get('authMode','oauth') == 'oauth'):continue
            try:
                with warnings.catch_warnings():
                    # getpass otherwise falls back to echoed stdin when no terminal is
                    # available. A redirected session must never expose the API key.
                    warnings.simplefilter('error', getpass.GetPassWarning)
                    token = password('API key for ' + provider + '/' + identity + ' (hidden; Ctrl+C cancels): ')
            except getpass.GetPassWarning:
                raise ValueError('Hidden API-key input requires an interactive terminal; choose environment variables or reopen the wizard in a terminal') from None
            helper = credential_module or module('wizard_credentials', ROOT / 'fieldbook_core/scripts/credentials.py')
            helper.token_value(token)
            secrets.append((provider, instance, token))
        self.unchanged()
        # Store failures leave every vault file unchanged. Keys from an earlier successful
        # store in this batch may remain in the OS store; no plaintext fallback exists.
        stored = 0
        for provider, instance, token in secrets:
            self.credential_attempted = True
            try:helper.store(self.root, provider, instance, token)
            except Exception:
                raise ValueError('OS credential store unavailable or save failed; vault files are unchanged. '
                                 'OS credentials from earlier store attempts may already have changed.') from None
            self.credentials_updated += 1;stored += 1
            self.key_updates.discard((provider, instance['id']))
        secrets.clear()
        self.unchanged()
        affected = sorted(set(writes) | set(activation.deletes))
        before = {name: admin.safe(self.root, name).read_bytes() if admin.safe(self.root, name).is_file() else None for name in affected}
        changed = [name for name in affected if name in activation.deletes or before[name] != writes[name].encode()]
        if not changed:return {'saved': bool(stored), 'backup': None, 'credentialsUpdated': stored,
                               'message': 'Updated ' + str(stored) + ' OS credential(s); configuration files were unchanged' if stored else 'No configuration changes'}
        folder = '.fieldbook/config-backups/' + datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ-') + uuid.uuid4().hex[:8]
        backup = admin.safe(self.root, folder);backup.mkdir(parents=True, mode=0o700)
        manifest = {'createdUtc': datetime.now(timezone.utc).isoformat(), 'files': {}}
        for name in changed:
            data = before[name]
            manifest['files'][name] = None if data is None else hashlib.sha256(data).hexdigest()
            if data is not None:
                dest = admin.safe(self.root, folder + '/files/' + name);dest.parent.mkdir(parents=True,exist_ok=True)
                with dest.open('xb') as stream:stream.write(data)
                os.chmod(dest, 0o600)
        admin.write(backup/'restore.json', admin.dump(manifest))
        self.save_attempted = True
        try:
            admin.configure(self.root, arguments(self.config, apply=True,explicit_defaults=getattr(self,'explicit_defaults',False)))
            for p in PROVIDERS:
                name = 'fieldbook_core/' + p + '.json'
                if name in writes:admin.write(admin.safe(self.root, name), writes[name])
        except BaseException:
            conflicts = []
            for name in changed:
                path = admin.safe(self.root, name);current = path.read_bytes() if path.is_file() else None
                expected = writes[name].encode() if name in writes else None
                if current not in (before[name], expected):conflicts.append(name);continue
                if before[name] is None:
                    if path.exists():path.unlink()
                else:
                    # Restore exact original bytes, including BOM and newline conventions.
                    temp = path.with_name('.fieldbook-restore-' + uuid.uuid4().hex)
                    temp.write_bytes(before[name]);os.replace(temp, path)
            raise ValueError('Save failed; original configuration was restored where unchanged. Backup: ' + folder
                             + ('; concurrent edits need manual review' if conflicts else '')
                             + ('. OS credentials already saved remain in the OS store.' if self.credential_attempted else '')) from None
        return {'saved': True, 'backup': folder, 'credentialsUpdated': stored,
                'message': 'Saved locally; remote services were not contacted' + ('; updated ' + str(stored) + ' OS credential(s)' if stored else '')}


class Wizard:
    def __init__(self, session, ask=input, say=print, password=getpass.getpass, credential_module=None, connection_checker=None, project_discoverer=None, link_helper=None, calendar_authorizer=None, series_discoverer=None, link_opener=None):
        self.session, self.ask, self.say = session, ask, say
        self.password, self.credentials = password, credential_module
        self.connection_checker = connection_checker
        self.project_discoverer = project_discoverer
        self.link_helper = link_helper
        self.calendar_authorizer = calendar_authorizer
        self.series_discoverer = series_discoverer
        self.link_opener = link_opener or webbrowser.open
        self.saved_any = False
        self.record_links_saved = False

    def provider_choice(self, purpose, include_all=False, allowed=None):
        labels = dict(zip((*PROVIDERS,'all'), ('Jira','Digital.ai Agility','GitHub Issues','Azure Boards','Canvas LMS','Google Calendar','Outlook / Microsoft 365 Calendar','All providers')))
        choices = tuple(p for p in PROVIDERS if allowed is None or p in allowed)
        if include_all:choices = (*choices, 'all')
        for n, name in enumerate(choices):
            self.say(str(n+1) + ' ' + labels[name])
        self.say('0 Back')
        value = self.ask(purpose + ' — provider number or name (Enter goes back): ').strip().lower()
        if value in ('','0'):return ''
        if value.isdigit() and 1 <= int(value) <= len(choices):return choices[int(value)-1]
        if value not in choices:raise ValueError('Choose a listed provider')
        return value

    def saved_instance_choice(self, provider):
        data = self.session.connections[provider]
        if not isinstance(data, dict) or not isinstance(data.get('instances'), list) or not data['instances']:
            raise ValueError('Add and save a connection before choosing a scope')
        instances = data['instances'];seen = set()
        for n, item in enumerate(instances):
            check_instance(provider, item, allow_missing_client=True)
            if item['id'] in seen:raise ValueError('Make each instance ID unique before choosing a scope')
            seen.add(item['id']);self.say(str(n+1) + ' ' + item['id'] + ': ' + item['baseUrl']
                + (' (needs OAuth client ID)' if provider in CALENDAR_PROVIDERS and item.get('authMode','oauth') == 'oauth' and not item.get('clientId') else ''))
        selected = self.ask('Saved instance number or ID (Enter cancels): ').strip()
        if not selected:return None
        matches = [i for i in instances if i['id'] == selected]
        item = instances[int(selected)-1] if selected.isdigit() and 1 <= int(selected) <= len(instances) else matches[0] if matches else None
        if item is None:raise ValueError('Choose a listed instance')
        check_instance(provider,item)
        if 'REPLACE' in item['baseUrl'].upper():raise ValueError('Save the real service URL and credential choice before choosing a scope')
        return item

    def field(self, label, old='', kind='text'):
        display = json.dumps(old, ensure_ascii=True) if kind == 'object' else ','.join(map(str, old)) if kind == 'list' else str(old)
        while True:
            text = self.ask(label + ' [' + display + '] (Enter keeps; - clears): ').strip()
            if not text:return old
            if text == '-':return {} if kind == 'object' else [] if kind == 'list' else ''
            if kind == 'list':return list(dict.fromkeys(v.strip() for v in text.split(',') if v.strip()))
            if kind == 'object':
                try:
                    value = json.loads(text)
                    if not isinstance(value, dict) or contains_secret(value):raise ValueError()
                    return value
                except ValueError:self.say('Enter a JSON object without literal credential fields.');continue
            return text

    def setups(self):
        c = self.session.config
        value = self.field('Setups: core or any of personal,work,school', ','.join(c['setups']) or 'core')
        setups = [] if value == 'core' else list(dict.fromkeys(v.strip() for v in value.split(',') if v.strip()))
        if any(v not in ('personal', 'work', 'school') for v in setups):raise ValueError('Choose core or personal,work,school')
        if 'work' in setups and 'work' not in c['setups']:c['features']['reviews'] = True
        if c['setups']!=setups:c['defaults']['area']=setups[0] if len(setups)==1 else ''
        c['setups'] = setups
        if 'work' not in setups:c['features']['reviews'] = False
        if 'school' not in setups:c['features']['canvas'] = False
        if 'work' in setups:
            role = self.field('Work role: individual-contributor or people-manager', c['workRole'])
            if role not in ('individual-contributor','people-manager'):raise ValueError('Choose individual-contributor or people-manager')
            c['workRole'] = role
            c['workFocus'] = self.field('Optional work focus labels', c.get('workFocus', []), 'list')
            c['workSubrole'] = self.field('Optional work subrole label', c.get('workSubrole', ''))

    def features(self):
        c = self.session.config
        self.say('\n'.join(str(n + 1) + ' ' + name + ': ' + ('on' if c['features'].get(name) else 'off') for n, name in enumerate((*PROVIDERS, 'reviews'))))
        choice = self.ask('Toggle feature number/name (Enter goes back): ').strip()
        if not choice:return
        name = (*PROVIDERS, 'reviews')[int(choice)-1] if choice.isdigit() and 1 <= int(choice) <= len((*PROVIDERS, 'reviews')) else choice
        if name not in (*PROVIDERS, 'reviews'):raise ValueError('Choose a listed feature')
        enabled = not c['features'].get(name, False)
        if enabled and (name == 'canvas' and 'school' not in c['setups'] or name == 'reviews' and 'work' not in c['setups']):
            raise ValueError(name + ' requires its school/work setup first')
        c['features'][name] = enabled

    def integrations(self, provider=None):
        provider = provider or self.provider_choice('Edit connections')
        if not provider:return
        if provider not in PROVIDERS:raise ValueError('Choose a listed provider')
        data = self.session.connections[provider]
        if not isinstance(data, dict) or not isinstance(data.get('instances'), list):raise ValueError('Repair the provider instances list before editing')
        for item in data['instances']:
            # Only display validated, credential-free identity fields.
            try:
                check_instance(provider, item)
                self.say(item['id'] + ': ' + item['baseUrl'] + ' (' + item.get('credentialStore', 'environment') + ')')
            except (ValueError, TypeError):self.say('An existing instance needs configuration repair; --check gives its index.')
        action = self.ask('add, edit INSTANCE_ID, remove INSTANCE_ID (Enter goes back): ').strip().split()
        if not action:return
        if action[0] == 'add' and len(action) == 1:
            identity = self.ask('New instance ID: ').strip()
            if any(i.get('id') == identity for i in data['instances'] if isinstance(i, dict)):raise ValueError('Instance ID already exists')
            item = {'id': identity, 'baseUrl': 'https://api.github.com' if provider == 'github' else '',
                    'tokenVar': provider.upper() + '_' + re.sub(r'[^A-Z0-9_]', '_', identity.upper()) + '_TOKEN', 'credentialStore': 'environment'}
            if provider == 'jira':item['flavor'] = 'cloud'
            if provider == 'github':item['apiVersion'] = '2026-03-10'
            if provider in CALENDAR_PROVIDERS:
                item.update(baseUrl=CALENDAR_URLS[provider],authMode='oauth',credentialStore='keyring',clientId='',calendarIds=[])
                if provider == 'microsoft':item['tenant']='common'
            original = None
        elif len(action) == 2 and action[0] in ('edit', 'remove'):
            matches = [i for i in data['instances'] if isinstance(i, dict) and i.get('id') == action[1]]
            if len(matches) != 1:raise ValueError('Choose one unique existing instance ID')
            original = matches[0];item = copy.deepcopy(original)
            if action[0] == 'remove':
                if self.ask('Remove this connection from local config? Type remove: ').strip() == 'remove':
                    data['instances'].remove(original);self.session.key_updates.discard((provider,item['id']))
                    self.say('Staged removal. Notes and any saved OS credential remain intact.')
                return
        else:raise ValueError('Choose add, edit INSTANCE_ID or remove INSTANCE_ID')
        # Refuse to echo/back up old literal credentials; never print arbitrary fields.
        if contains_secret(item):raise ValueError('Remove literal credential fields manually before using this editor')
        current_url = item.get('baseUrl', '')
        if current_url:
            try:clean_url(current_url, provider)
            except ValueError:current_url = ''
        if provider in CALENDAR_PROVIDERS:
            item['baseUrl'] = CALENDAR_URLS[provider]
            self.say('Fixed calendar API URL: ' + item['baseUrl'])
        else:item['baseUrl'] = clean_url(self.field('HTTPS service URL (no API key)', current_url), provider)
        item['tokenVar'] = self.field('Environment variable NAME (never the key itself)', item.get('tokenVar', provider.upper() + '_TOKEN'))
        for key, label, kind in FIELDS[provider]:
            item[key] = self.field(label, item.get(key, {} if kind == 'object' else [] if kind == 'list' else ''), kind)
        oauth = provider in CALENDAR_PROVIDERS and item.get('authMode','oauth') == 'oauth'
        if oauth:
            mode = 'keyring';self.say('OAuth uses OS credential storage. Save this connection, then use menu 9 to sign in.')
        else:mode = self.field('Credential source: environment or keyring', item.get('credentialStore', 'environment'))
        if mode not in ('environment', 'keyring'):raise ValueError('Choose environment or keyring')
        item['credentialStore'] = mode
        check_instance(provider, item)
        identity_changed = original is None or original.get('baseUrl', '').rstrip('/') != item['baseUrl'] or original.get('credentialStore', 'environment') != 'keyring'
        update_key = not oauth and mode == 'keyring' and (identity_changed or self.ask('Replace its saved API key after Save? [y/N]: ').strip().lower() == 'y')
        if original is None:data['instances'].append(item)
        else:data['instances'][data['instances'].index(original)] = item
        if update_key:self.session.key_updates.add((provider,item['id']))
        else:self.session.key_updates.discard((provider,item['id']))
        self.say('Connection staged. Enable its feature separately; all remote access stays read only.')
        if mode == 'environment':self.say('Set ' + item['tokenVar'] + ' in the environment that launches OpenCode; the wizard does not store its value.')
        else:self.say('OS storage needs fieldbook_core/requirements-credentials.txt installed in the vault Python environment. Moving/copying a vault requires ' + ('signing in again.' if oauth else 'a new saved key.'))

    def preview(self):
        result = self.session.preview()
        for error in result['errors']:self.say('Error: ' + error)
        for warning in result['warnings']:self.say('Note: ' + warning)
        if result['errors']:return result
        c = result['settings']
        self.say('Setups: ' + (', '.join(c['setups']) or 'core') + '; work role: ' + c['workRole'])
        self.say('CLI/OpenCode record defaults: '+json.dumps(c['defaults'],ensure_ascii=True))
        self.say('Enabled features: ' + (', '.join(k for k in FEATURES if c['features'].get(k)) or 'none'))
        self.say('Changed config files: ' + (', '.join(result['changed']) or 'none'))
        for provider in PROVIDERS:
            if self.session.connections[provider] == self.session.original_connections[provider]:continue
            for item in self.session.connections[provider]['instances']:
                self.say(provider + '/' + item['id'] + ': ' + item['baseUrl'] + '; ' + item.get('credentialStore','environment') + '; variable ' + item['tokenVar'])
                for key, _, _ in FIELDS[provider]:
                    if key in item:self.say('  ' + key + ': ' + json.dumps(item[key], ensure_ascii=True))
        self.say('Other custom keys are preserved. Credentials are never shown or written to JSON.')
        a = result['activation']
        self.say('Managed files to write: ' + str(len(a['files'])) + '; deactivate: ' + str(len(a['deactivated'])))
        for item in a['preserved_customizations']:self.say('Preserved customization: ' + item['path'])
        for name in a['user_removed_preserved']:self.say('Preserved manual removal: ' + name)
        if result['tasknotes']['warning']:self.say(result['tasknotes']['warning'])
        if self.session.key_updates:self.say('API keys to request after Save: ' + ', '.join(p + '/' + i for p,i in sorted(self.session.key_updates)))
        return result

    def require_saved(self, action):
        self.session.unchanged()
        if (self.session.config != self.session.original_config or self.session.connections != self.session.original_connections
                or self.session.key_updates):
            raise ValueError('Save or cancel pending edits before ' + action + '; remote operations use saved configuration only')

    def test_saved(self, provider=None):
        self.require_saved('testing')
        provider = provider or self.provider_choice('Test saved connections', include_all=True)
        if not provider:return None
        if provider not in ('all', *PROVIDERS):raise ValueError('Choose all or a supported provider')
        instance = self.ask('Instance ID (Enter tests all saved instances for this provider): ').strip() if provider != 'all' else ''
        self.say('Testing saved connections with read-only requests. OS credential access may prompt; no feature is enabled and no note is written.')
        result = test_connections(self.session.root, provider, instance or None, self.connection_checker,
                                  lambda p,i:self.say('Testing ' + p + '/' + i + '...'))
        self.last_test = {'result':copy.deepcopy(result),'checked_at':datetime.now(timezone.utc).isoformat()}
        for item in result['results']:
            self.say(item['provider'] + ('/' + item['instance'] if item['instance'] else '') + ':')
            for entry in item['checks']:self.say('  ' + entry['stage'] + ' — ' + entry['status'] + ': ' + entry['message'])
        self.say('Connection tests: ' + result['status'] + '; verified ' + str(result['verified']) + ', failed '
                 + str(result['failed']) + ', not verified ' + str(result['notVerified']) + ', skipped ' + str(result['skipped']))
        return result

    def choose_project(self, provider=None):
        self.require_saved('listing projects')
        provider = provider or self.provider_choice('Choose project/repository/course')
        if not provider:return
        if provider not in PROVIDERS:raise ValueError('Choose a supported provider')
        item = self.saved_instance_choice(provider)
        if item is None:return
        instances = self.session.connections[provider]['instances']
        self.say('Listing available scope for ' + provider + '/' + item['id'] + ' with read-only requests...')
        try:
            discover = self.project_discoverer or module('fieldbook_integration_projects', ROOT / 'tools/integration_projects.py').discover_projects
            result = discover(self.session.root, provider, item['id'])
        except Exception:
            raise ValueError('Could not list projects. Check the saved connection and read permissions, or enter the scope manually under Integrations.') from None
        if not isinstance(result, dict) or not isinstance(result.get('choices'), list) or len(result['choices']) > 50:
            raise ValueError('Project discovery returned an invalid result; use manual scope entry')
        scope_key = {'jira':'filter','agility':'where','github':'repositories','azure':'project','canvas':'courseIds','google':'calendarIds','microsoft':'calendarIds'}[provider]
        choices = result['choices']
        for n, choice in enumerate(choices):
            if (not isinstance(choice, dict) or not isinstance(choice.get('id'), str) or not isinstance(choice.get('label'), str)
                    or not isinstance(choice.get('settings'), dict) or set(choice['settings']) != {scope_key}):
                raise ValueError('Project discovery returned an unsupported scope; use manual entry')
            check_instance(provider, {**item, **choice['settings']})
            label = ''.join(c if ord(c) >= 32 and ord(c) != 127 else ' ' for c in choice['label'])[:180]
            self.say(str(n+1) + ' ' + label)
        if result.get('truncated'):self.say('Only the first bounded page is shown. Enter an exact scope manually if yours is absent.')
        if isinstance(result.get('notice'), str):
            self.say(''.join(c if ord(c) >= 32 and ord(c) != 127 else ' ' for c in result['notice'])[:500])
        if not choices:
            self.say('No selectable scopes were returned. Existing settings were kept; enter an exact scope manually under Integrations.');return
        many = provider in ('github','canvas',*CALENDAR_PROVIDERS)
        answer = self.ask('Choose ' + ('numbers separated by commas' if many else 'one number') + ' (Enter cancels): ').strip()
        if not answer:return
        indexes = list(dict.fromkeys(v.strip() for v in answer.split(',')))
        if (not many and len(indexes) != 1) or any(not i.isdigit() or not 1 <= int(i) <= len(choices) for i in indexes):
            raise ValueError('Choose only displayed scope numbers')
        chosen = [choices[int(i)-1]['settings'][scope_key] for i in indexes]
        patch_value = chosen[0]
        if many:
            patch_value = list(dict.fromkeys(v for values in chosen for v in values))
            mode = self.ask('Replace or add to the existing selection? [replace/add; Enter replaces]: ').strip().lower()
            if mode not in ('','replace','add'):raise ValueError('Choose replace or add')
            if mode == 'add':patch_value = list(dict.fromkeys([*item.get(scope_key,[]), *patch_value]))
        proposed = {**item, scope_key:patch_value}
        check_instance(provider, proposed)
        self.say('Current ' + scope_key + ': ' + json.dumps(item.get(scope_key), ensure_ascii=True))
        self.say('Proposed ' + scope_key + ': ' + json.dumps(patch_value, ensure_ascii=True))
        if self.ask('Stage this scope for the next Save? Type use (Enter keeps the current scope): ').strip() != 'use':
            self.say('Existing scope kept.');return
        self.session.unchanged()
        instances[instances.index(item)] = proposed
        self.say('Scope staged. Choose 4 to preview, then 5 to save and optionally test. Feature activation is unchanged.')

    def calendar_signin(self, provider=None):
        self.require_saved('signing in to a calendar')
        provider = provider or self.provider_choice('Sign in to calendar', allowed=CALENDAR_PROVIDERS)
        if not provider:return
        if provider not in CALENDAR_PROVIDERS:raise ValueError('Choose Google or Microsoft calendar')
        instance = self.saved_instance_choice(provider)
        if instance is None:return
        if instance.get('authMode','oauth') != 'oauth':raise ValueError('This connection uses an access token. Choose OAuth in Integrations and save before browser sign-in.')
        self.say('Sign-in uses the saved OAuth client and stores credentials in the OS credential store. It does not enable the feature or change notes.')
        if self.ask('Start calendar sign-in now? Type signin (Enter cancels): ').strip() != 'signin':return
        self.session.unchanged();self.session.credential_attempted = True
        try:
            authorize = self.calendar_authorizer or module('fieldbook_calendar_auth', ROOT / 'fieldbook_core/scripts/calendar_auth.py').authorize
            receipt = authorize(self.session.root, provider, instance['id'], say=self.say, password=self.password)
        except (EOFError, KeyboardInterrupt):
            self.say('Calendar sign-in cancelled. Existing OS credentials were not removed.');return
        except Exception:
            raise ValueError('Calendar sign-in did not finish. Check the OAuth client settings, tenant and OS credential-store dependency, then retry. Existing credentials were not removed.') from None
        if not isinstance(receipt,dict) or receipt.get('authorized') is not True:
            raise ValueError('Calendar sign-in was not confirmed; no token or response details were printed')
        self.saved_any = True
        self.say('Calendar sign-in complete. Use 7 to choose default calendars, 8 to link a Meeting Series, or 6 to test reads. Feature activation is unchanged.')

    def choose_one_remote(self, result, label):
        choices = result.get('choices') if isinstance(result,dict) else None
        if not isinstance(choices,list) or len(choices)>50:raise ValueError('Remote listing is invalid')
        for n, choice in enumerate(choices):
            if not isinstance(choice,dict) or not isinstance(choice.get('id'),str) or not isinstance(choice.get('label'),str):
                raise ValueError('Remote listing is invalid')
            title = ''.join(c if ord(c)>=32 and ord(c)!=127 else ' ' for c in choice['label'])[:180]
            self.say(str(n+1) + ' ' + title)
        if result.get('truncated'):self.say('Only the first bounded page is shown; use a known ID if the intended item is absent.')
        if not choices:
            self.say('No selectable entries were returned.');return None
        value = self.ask(label + ' number (Enter cancels): ').strip()
        if not value:return None
        if not value.isdigit() or not 1 <= int(value) <= len(choices):raise ValueError('Choose a displayed number')
        return choices[int(value)-1]

    def series_choice(self, provider, instance):
        calendar_id = None
        while calendar_id is None:
            mode = self.ask('1 List calendars\n2 Enter a known calendar ID\n0 Cancel\nChoose: ').strip()
            if mode in ('','0'):return None
            if mode == '2':calendar_id = self.ask('Exact calendar ID (Enter cancels): ').strip()
            elif mode == '1':
                self.say('Listing calendars for ' + provider + '/' + instance['id'] + '...')
                try:
                    discover = self.project_discoverer or module('fieldbook_integration_projects', ROOT / 'tools/integration_projects.py').discover_projects
                    result = discover(self.session.root, provider, instance['id'])
                except Exception:
                    self.say('Calendars could not be listed. Check sign-in or choose 2 to enter a known ID.');continue
                choice = self.choose_one_remote(result,'Calendar')
                if choice is None:return None
                calendar_id = choice['id']
            else:self.say('Choose 1, 2 or 0.');continue
            if not calendar_id:return None
        check_instance(provider,{**instance,'calendarIds':[calendar_id]})
        while True:
            mode = self.ask('1 Find recurring series in a UTC date window\n2 Enter a known series ID\n0 Cancel\nChoose: ').strip()
            if mode in ('','0'):return None
            if mode == '2':
                identity = self.ask('Exact recurring series ID (Enter cancels): ').strip()
                if not identity:return None
                return {'id':identity,'settings':{'calendar_provider':provider,'calendar_instance':instance['id'],
                                                 'calendar_id':calendar_id,'calendar_series_id':identity}}
            if mode != '1':self.say('Choose 1, 2 or 0.');continue
            start = self.ask('Window start, UTC date YYYY-MM-DD: ').strip()
            end = self.ask('Window end, UTC date YYYY-MM-DD (inclusive; at most 93 days): ').strip()
            try:
                if not re.fullmatch(r'\d{4}-\d{2}-\d{2}',start) or not re.fullmatch(r'\d{4}-\d{2}-\d{2}',end):raise ValueError()
                first,last = datetime.strptime(start,'%Y-%m-%d'),datetime.strptime(end,'%Y-%m-%d')
                if not 0 <= (last-first).days <= 92:raise ValueError()
            except ValueError:raise ValueError('Choose valid YYYY-MM-DD UTC dates in order, spanning at most 93 inclusive days') from None
            self.say('Finding recurring series in the selected calendar and UTC window...')
            try:
                discover = self.series_discoverer or module('fieldbook_calendar_service', ROOT / 'fieldbook_core/scripts/calendar_service.py').discover_series
                result = discover(self.session.root, provider, instance['id'], calendar_id, start, end)
            except Exception:
                self.say('Series could not be listed. Check the selected window and read access, or choose 2 for a known series ID.');continue
            return self.choose_one_remote(result,'Recurring series')

    def link_record(self, provider=None, kind=None):
        self.require_saved('linking a Project, Course or Meeting Series')
        try:
            helper = self.link_helper or module('fieldbook_integration_links', ROOT / 'tools/integration_links.py')
        except ImportError:
            raise ValueError('Record linking needs the notebook Python environment; install fieldbook_core/requirements.txt there') from None
        records = helper.list_records(self.session.root)
        if not isinstance(records, list):raise ValueError('Could not list local Project, Course and Meeting Series records')
        if kind is not None:records = [record for record in records if isinstance(record,dict) and record.get('kind') == kind]
        elif provider is not None:
            kinds = ('series',) if provider in CALENDAR_PROVIDERS else ('course',) if provider == 'canvas' else ('project','course')
            records = [record for record in records if isinstance(record,dict) and record.get('kind') in kinds]
        if not records:
            self.say('No eligible records found. Create a Meeting Series note using Templates/Series.md, then return to link it.' if kind == 'series'
                     else 'No eligible records found. Create a Project, Course or Meeting Series note first, then use this option to link it.');return
        for n, record in enumerate(records):
            if not isinstance(record, dict) or record.get('kind') not in ('project','course','series') or not isinstance(record.get('path'),str):
                raise ValueError('Record listing is invalid')
            title = str(record.get('title') or record['path'])
            title = ''.join(c if ord(c) >= 32 and ord(c) != 127 else ' ' for c in title)[:180]
            self.say(str(n+1) + ' ' + title + ' (' + record['kind'] + ') — ' + json.dumps(record['path'],ensure_ascii=True))
        selected = self.ask('Local record number or exact relative path (Enter cancels): ').strip()
        if not selected:return
        matches = [r for r in records if r['path'] == selected]
        record = records[int(selected)-1] if selected.isdigit() and 1 <= int(selected) <= len(records) else matches[0] if matches else None
        if record is None:raise ValueError('Choose a listed local record')
        allowed = CALENDAR_PROVIDERS if record['kind'] == 'series' else RECORD_PROVIDERS if record['kind'] == 'course' else tuple(p for p in RECORD_PROVIDERS if p != 'canvas')
        provider = provider or self.provider_choice('Link this ' + record['kind'], allowed=allowed)
        if not provider:return
        if provider not in allowed:raise ValueError('Choose a provider supported by this record kind')
        instance = self.saved_instance_choice(provider)
        if instance is None:return
        self.say('This links only the selected record. Connection default scopes and other records stay unchanged.')
        remote = None
        if record['kind'] == 'series':
            remote = self.series_choice(provider,instance)
            if remote is None:return
        manual_labels = {'jira':'Jira project key (e.g. APP)', 'agility':'Agility scope ID (e.g. Scope:123)',
                         'github':'GitHub owner/repository', 'azure':'Exact Azure project name', 'canvas':'Canvas course ID'}
        while remote is None:
            mode = self.ask('1 List remote scopes\n2 Enter a known scope manually\n0 Cancel\nChoose: ').strip()
            if mode in ('','0'):return
            if mode == '2':
                value = self.ask(manual_labels[provider] + ' (Enter cancels): ').strip()
                if not value:return
                remote = {'id':value, **({'settings':{'project':value}} if provider == 'azure' else {})}
                break
            if mode != '1':self.say('Choose 1, 2 or 0.');continue
            self.say('Listing remote scopes for ' + provider + '/' + instance['id'] + ' with read-only requests...')
            try:
                discover = self.project_discoverer or module('fieldbook_integration_projects', ROOT / 'tools/integration_projects.py').discover_projects
                result = discover(self.session.root, provider, instance['id'])
            except Exception:
                self.say('Remote scopes could not be listed. Check the saved connection, or choose 2 to enter a known scope manually.');continue
            choices = result.get('choices') if isinstance(result,dict) else None
            if not isinstance(choices,list) or len(choices)>50:raise ValueError('Remote scope listing is invalid')
            for n, choice in enumerate(choices):
                if not isinstance(choice,dict) or not isinstance(choice.get('label'),str):raise ValueError('Remote scope listing is invalid')
                label = ''.join(c if ord(c) >= 32 and ord(c) != 127 else ' ' for c in choice['label'])[:180]
                self.say(str(n+1) + ' ' + label)
            if result.get('truncated'):self.say('Only the first bounded page is shown; enter an unlisted scope manually.')
            if not choices:
                self.say('No selectable scopes were returned. Choose 2 for a known scope, or 0 to cancel.');continue
            chosen = self.ask('Remote scope number, m for manual entry, or Enter to cancel: ').strip().lower()
            if not chosen:return
            if chosen == 'm':
                value = self.ask(manual_labels[provider] + ' (Enter cancels): ').strip()
                if not value:return
                remote = {'id':value, **({'settings':{'project':value}} if provider == 'azure' else {})}
                break
            if not chosen.isdigit() or not 1 <= int(chosen) <= len(choices):raise ValueError('Choose a displayed remote scope number')
            remote = choices[int(chosen)-1]
        self.session.unchanged()
        expected = record.get('sha256',record.get('expected'))
        if not isinstance(expected,str):raise ValueError('Record listing did not include a content hash; reopen the wizard')
        plan = helper.plan_link(self.session.root, record['path'], provider, instance['id'], remote, expected=expected)
        self.say('Record: ' + json.dumps(record['path'],ensure_ascii=True))
        for change in plan['changes']:
            self.say('  ' + change['field'] + ': ' + json.dumps(change.get('before'),ensure_ascii=True)
                     + ' → ' + json.dumps(change.get('after'),ensure_ascii=True))
        if plan.get('unchanged'):
            self.say('This record already has the selected link. No file was changed.');return
        if self.ask('Apply this metadata link to this record now, with a backup? Type apply (Enter cancels): ').strip() != 'apply':
            self.say('Record unchanged.');return
        self.session.unchanged()
        saved = helper.apply_link(self.session.root, plan)
        self.record_links_saved = not saved.get('unchanged',False) or self.record_links_saved
        self.say('Record link saved locally. Its body and the connection default scopes were preserved.')
        if saved.get('backup'):self.say('Record backup: ' + str(saved['backup']))

    def save_settings(self, provider=None):
        result = self.preview()
        if result['errors']:return
        if self.ask('Save this preview and make a local backup? Type save (Enter cancels): ').strip() != 'save':return
        outcome = self.session.commit(self.password, self.credentials)
        self.say(outcome['message'])
        if outcome['backup']:self.say('Backup: ' + outcome['backup'] + '/restore.json')
        if outcome['saved']:
            self.saved_any = True
            self.session = Session(self.session.root)
            try:answer = self.ask('Test saved connections now with read-only remote requests? [y/N]: ').strip().lower()
            except (EOFError, KeyboardInterrupt):answer = ''
            if answer == 'y':
                try:self.test_saved(provider)
                except (EOFError, KeyboardInterrupt):self.say('Settings were saved; the optional connection test was cancelled.')
                except (ValueError, OSError) as error:self.say('Settings were saved; connection test: ' + str(error))
            self.say('Saved. Back at the current menu; connection tests and feature activation are separate choices.')

    def calendar_requirements(self, provider):
        self.say('Prerequisites only: no browser, credential store or service is accessed by this screen.')
        if provider == 'microsoft':
            self.say('Microsoft 365 / Outlook.com: use the cloud account behind Outlook, including when you normally use the desktop client.')
            self.say('Register an Entra public-client app, choose its permitted account types, enable Allow public client flows, and use delegated Calendars.Read plus offline_access. No client secret is needed.')
            self.say('https://learn.microsoft.com/en-us/entra/identity-platform/scenario-desktop-app-configuration')
            self.say('Enter the application client ID and tenant under Configure connection. Company consent policies may require administrator approval.')
        else:
            self.say('Google Calendar: use the Google account behind Gmail or Workspace, including a Google calendar displayed in Outlook. This connection does not read Gmail messages.')
            self.say('Enable the Google Calendar API, configure the consent audience/test users, and create a Desktop app OAuth client.')
            self.say('https://developers.google.com/workspace/guides/create-credentials#desktop-app')
            self.say('Enter only the client ID under Configure connection. The Desktop client secret is requested in a hidden terminal prompt during Sign in; never paste it into chat or a vault file.')
        self.say('Use the notebook Python environment with fieldbook_core/requirements.txt and fieldbook_core/requirements-credentials.txt installed. Read Calendar connections.md for platform commands and registration steps.')
        self.say('Order: configure connection -> save -> sign in -> choose calendars -> save -> test read access -> link a recurring Meeting Series.')
        self.say('Need help registering the app? Choose 9 in this guided menu, or run --credential-guide ' + provider + ' for steps and official links.')
        self.say('Sign-in and read access are unverified until their explicit actions succeed. Tests do not prove a token lacks write permissions; Fieldbook only calls calendar read routes.')

    def calendar_setup(self):
        self.say('Choose where the calendar is stored, regardless of which app displays it.')
        self.say('1 Microsoft 365 / Outlook.com (also displayed in Outlook desktop)\n2 Google Calendar (Gmail / Workspace)\n3 Outlook local-only / on-premises / another provider\n0 Back')
        choice = self.ask('Calendar source: ').strip().lower()
        if choice in ('','0'):return
        if choice == '3':
            self.say('Fieldbook does not directly read the Outlook application, PST-only calendars or on-premises Exchange. Export the selected event/series to an .ics file in Attachments/, then use /meeting with that file. No live sign-in or read-permission test applies to an exported file.')
            self.say('If Outlook displays Microsoft cloud or Google calendars, choose that provider instead. See Calendar meetings.md for local ICS and occurrence selection.');return
        provider = {'1':'microsoft','2':'google','microsoft':'microsoft','google':'google'}.get(choice)
        if provider is None:raise ValueError('Choose a listed calendar source')
        self.connection_setup(provider)

    def integration_requirements(self, provider):
        if provider in CALENDAR_PROVIDERS:
            self.calendar_requirements(provider);return
        self.say('Prerequisites only: no credential store or service is accessed by this screen.')
        guidance = {
            'jira':'Jira: site URL, Cloud email/API token or supported server credential, and a project/JQL scope.',
            'agility':'Digital.ai Agility: service URL and read-capable token; select a project Scope and optional member/filter.',
            'github':'GitHub Issues: API URL and token with access to the selected repositories/issues. Repository listing may need additional read access.',
            'azure':'Azure Boards: organization URL and token with work-item read access; select a project. Project listing requires its own read permission.',
            'canvas':'Canvas LMS: institution HTTPS origin and API token; select course IDs. Create a separate connection for each institution/account. The AI feature requires the school setup; diagnostics can run before enabling it.',
        }
        self.say(guidance.get(provider,'Configure the provider URL, credential reference and smallest useful read scope. See its integration guide.'))
        self.say('Keep keys out of chat and vault files. Configure an environment-variable NAME or choose OS credential storage; Save requests an OS-stored key in a hidden terminal prompt.')
        self.say('OS credential storage requires fieldbook_core/requirements-credentials.txt in the notebook Python environment; environment references do not.')
        self.say('Order: configure connection -> save -> choose default scopes -> save -> test read access -> link a local record.')
        self.say('Need help getting a key? Choose 9 in this guided menu, or run --credential-guide ' + provider + ' for steps and official links.')
        self.say('A URL response alone does not prove authentication or selected-scope read access. Missing scope is unverified; reads do not prove a token lacks write permissions.')
        self.say('Guide: ' + ('Canvas LMS.md' if provider == 'canvas' else 'INTEGRATIONS.md') + '. Use the main menu option 6 or --test all to test every saved connection.')

    def integration_setup(self, provider=None):
        provider = provider or self.provider_choice('Guided integration setup/test')
        if not provider:return
        if provider not in PROVIDERS:raise ValueError('Choose a listed provider')
        self.connection_setup(provider)

    def credential_guide(self, provider=None):
        provider = provider or self.provider_choice('Get an API key or register an app')
        if not provider:return
        if provider not in PROVIDERS:raise ValueError('Choose a listed provider')
        helper = module('fieldbook_integration_guides', ROOT / 'tools/integration-guides.py')
        catalog = helper.load(PROVIDERS)
        guide = catalog['providers'][provider]
        self.say(guide['title'] + ' — instructions checked ' + catalog['checked'])
        self.say('This guide never requests a secret. It creates no credentials, registrations or vault changes. Only an explicit open command launches a browser; do the provider steps there yourself.')
        variants = guide['variants']
        if len(variants) > 1:
            for n,variant in enumerate(variants):self.say(str(n+1) + ' ' + variant['title'])
            value = self.ask('Credential type number (Enter cancels): ').strip()
            if not value:return
            if not value.isdigit() or not 1<=int(value)<=len(variants):raise ValueError('Choose a listed credential type')
            variant = variants[int(value)-1]
        else:variant = variants[0]
        index = 0
        while index < len(variant['steps']):
            step = variant['steps'][index]
            self.say('\nStep ' + str(index+1) + '/' + str(len(variant['steps'])) + ': ' + step['title'])
            self.say(step['text'])
            links = step.get('links',[])
            for n,link in enumerate(links):self.say('  Link ' + str(n+1) + ' — ' + link['label'] + ': ' + link['url'])
            answer = self.ask('Enter = next; b = back; open NUMBER = open that link; q = return. Do not enter a key: ').strip().lower()
            if answer in ('q','0'):return
            if answer in ('','n','next'):index += 1;continue
            if answer == 'b':index = max(0,index-1);continue
            parts = answer.split()
            if len(parts)==2 and parts[0]=='open' and parts[1].isdigit() and 1<=int(parts[1])<=len(links):
                url = links[int(parts[1])-1]['url']
                if not helper.safe_link(url):raise ValueError('This guide link is not permitted')
                try:opened = self.link_opener(url)
                except Exception:opened = False
                self.say('Opened the selected link. Return here when ready for the next step.' if opened
                         else 'Could not open a browser. Copy the displayed HTTPS link into your browser.')
            else:self.say('Choose next, back, open plus a displayed link number, or q. Nothing was submitted.')
        self.say('Instructions finished; credential creation and read access have not been verified by this guide. Return to guided setup to configure, save and test your connection.')

    def connection_setup(self, provider):
        self.integration_requirements(provider)
        calendar = provider in CALENDAR_PROVIDERS
        while True:
            self.say('\nIntegration setup/test: ' + provider + '. Each network action and local save is selected explicitly.')
            pending = (self.session.connections != self.session.original_connections or self.session.config != self.session.original_config or bool(self.session.key_updates))
            self.say('Settings: ' + ('staged changes need Save' if pending else 'saved; sign-in/read access not checked by this screen')
                     + '. AI integration feature: ' + ('on' if self.session.config['features'].get(provider) else 'off'))
            option = self.ask('1 Setup requirements\n2 Configure connection\n3 Preview and save settings\n4 '
                              + ('Sign in' if calendar else 'Credential setup instructions') + '\n5 '
                              + ('Choose default calendars' if calendar else 'Choose default project/repository/course scopes') + '\n6 Test saved read access\n7 '
                              + ('Link a recurring Meeting Series' if calendar else 'Link a local Project or Course')
                              + '\n8 Toggle this integration feature (staged)\n9 Get an API key / register an app (step-by-step)\n0 Back\nChoose: ').strip().lower()
            if option in ('','0','q'):return
            try:
                if option == '1':self.integration_requirements(provider)
                elif option == '2':self.integrations(provider)
                elif option == '3':self.save_settings(provider)
                elif option == '4':
                    if calendar:self.calendar_signin(provider)
                    else:self.credential_guide(provider)
                elif option == '5':self.choose_project(provider)
                elif option == '6':self.test_saved(provider)
                elif option == '7':self.link_record(provider, kind='series' if calendar else None)
                elif option == '8':
                    enabled = not self.session.config['features'].get(provider,False)
                    if enabled and provider == 'canvas' and 'school' not in self.session.config['setups']:
                        raise ValueError('Canvas requires the school setup first; read-access tests remain available without enabling it')
                    self.session.config['features'][provider] = enabled
                    self.say('Feature choice staged. Use 3 to preview and save; existing records are preserved.')
                elif option == '9':self.credential_guide(provider)
                else:self.say('Choose a listed option.')
            except (ValueError, OSError) as error:self.say('Error: ' + str(error))

    def finish(self):
        if self.record_links_saved:
            self.say('Exited. Earlier saved settings and record links remain; any later staged settings were discarded.')
        elif self.saved_any:
            self.say('Exited. Earlier saved settings and credentials remain; any later staged edits were discarded.')
        elif self.session.credential_attempted or self.session.save_attempted:
            self.say('Cancelled remaining staged edits. Earlier save attempts may have changed OS credentials; keep any reported backup for recovery.')
        else:self.say('Exited; vault files and credentials were not changed.')
        return self.saved_any or self.record_links_saved

    def upgrade(self):
        self.require_saved('upgrading a vault')
        target = self.field('Existing vault path', str(self.session.root))
        if not target:return
        result = upgrade_wizard(target, ask=self.ask, say=self.say)
        if result:
            self.session = Session(result['vault'])
            self.saved_any = self.saved_any or result['applied']
            self.say('The configuration menu now targets the upgraded vault: ' + result['vault'])

    def restore(self):
        self.require_saved('restoring a vault')
        target = self.field('Vault path to restore', str(self.session.root))
        if not target:return None
        return restore_wizard(target, ask=self.ask, say=self.say)

    def onboard(self):
        self.say('Guided onboarding: choose context, preview/save settings, optionally identify yourself and capture one task. Each save is separate; you can skip optional steps or rerun later. Keep work/school vaults separate if their privacy or account policies differ.')
        self.setups()
        self.say('These task defaults apply to CLI/AI capture. Manual templates and customized TaskNotes defaults are preserved; their values may differ.')
        self.session.explicit_defaults=True
        defaults=self.session.config['defaults']
        for key,value in {'status':'backlog','priority':'2-normal','type':'task'}.items():defaults.setdefault(key,value)
        value=self.ask('Default area personal/work/school, none for blank (Enter keeps '+(defaults.get('area') or 'blank')+'): ').strip()
        if value:
            value='' if value=='none' else value
            if value not in ('','personal','work','school'):raise ValueError('Choose a valid default area')
            defaults['area']=value
        for key,allowed in [('status',('backlog','active','blocked')),('priority',('1-high','2-normal','3-low'))]:
            value=self.field('Default task '+key+' ('+'/'.join(allowed)+')',defaults[key])
            if value not in allowed:raise ValueError('Choose a listed '+key)
            defaults[key]=value
        value=self.field('Default task type (lowercase label; task is neutral)',defaults['type'])
        if not re.fullmatch(r'[a-z][a-z0-9_-]{0,63}',value):raise ValueError('Choose a short lowercase task type')
        defaults['type']=value
        result=self.preview()
        if result['errors']:raise ValueError('Resolve the displayed errors before saving onboarding')
        if self.ask('Type save to apply this setup with a local configuration backup (Enter cancels onboarding): ').strip()!='save':
            self.say('Onboarding not saved. Selections remain staged in this menu; exit to discard or resume setup.');return
        outcome=self.session.commit(self.password,self.credentials);self.say(outcome['message']);self.saved_any|=outcome['saved']
        if outcome['backup']:self.say('Configuration backup: '+outcome['backup'])
        self.session=Session(self.session.root)
        vt=module('fieldbook_vault_tools',ROOT/'tools/vault-tools.py')
        vt.journeys().finish_onboarding(vt.api(),self.session.root,self.ask,self.say)

    def menu(self):
        self.say('First time here? Setup > Guided onboarding. For everyday use, choose Daily use > Daily or Weekly review.')
        groups=json.loads((ROOT/'tools/menu-catalog.json').read_text())
        while True:
            try:
                value=self.ask('\n1 Setup\n2 Daily use\n3 Integrations\n4 Maintenance\n5 Help\n6 Advanced numbered menu\n0 Exit\nChoose: ').strip()
                if value in ('','0'):return self.finish()
                if value=='6':return self.run()
                if value=='5':
                    self.say('Start with Setup, preview, then save. Integrations are optional and remote read-only. Daily-use writes have separate previews. Maintenance backs up before upgrade/restore. See Configuration CLI.md and Vault tools.md.');continue
                if value not in groups:self.say('Choose a listed option.');continue
                title,items=groups[value]
                self.say(title+'\n'+'\n'.join(str(i+1)+' '+label for i,(_,label) in enumerate(items)))
                value=self.ask('Number (Enter goes back): ').strip()
                if not value:continue
                if not value.isdigit() or not 1<=int(value)<=len(items):raise ValueError('Choose a listed number')
                action=items[int(value)-1][0]
                callbacks={'1':self.setups,'2':self.features,'4':self.preview,'5':self.save_settings,'6':self.test_saved,'7':self.choose_project,'8':self.link_record,'9':self.calendar_signin,'10':self.integration_setup,'11':self.credential_guide,'12':self.upgrade,'13':self.restore}
                if action=='ai':
                    self.require_saved('configuring AI assistants')
                    module('fieldbook_ai_setup',ROOT/'tools/ai-setup.py').menu(self.session.root,ask=self.ask,say=self.say)
                elif action=='onboard':self.onboard()
                elif action in callbacks:
                    result=callbacks[action]()
                    if action=='13' and result and result.get('restored'):return True
                elif action=='14':
                    self.require_saved('viewing coverage')
                    report=module('coverage_report',ROOT/'tools/integration_coverage.py').offline(self.session.root,type('ConfigurationAPI',(),dict(PROVIDERS=PROVIDERS,admin=admin,check_instance=staticmethod(check_instance))))
                    module('fieldbook_vault_tools',ROOT/'tools/vault-tools.py').show_summary(report,self.ask,self.say)
                else:
                    self.require_saved('using vault tools');self.vault_tools_entered=True
                    module('fieldbook_vault_tools',ROOT/'tools/vault-tools.py').run(self.session.root,action,ask=self.ask,say=self.say,last_test=getattr(self,'last_test',None),human=True)
            except (ValueError,OSError) as error:self.say('Error: '+str(error))
            except (EOFError,KeyboardInterrupt):return self.finish()

    def run(self):
        self.say('Fieldbook setup. Settings are staged until Save. Record links have a separate Apply preview. Listing remote scopes, testing connections and calendar sign-in use the network only when selected.')
        initial = configuration_errors(self.session.config)
        if initial:raise ValueError('; '.join(initial))
        while True:
            menu = '\n1 Setups/work role\n2 Features\n3 Integrations\n4 Preview\n5 Save\n6 Test saved connections\n7 Choose default project/repository/course/calendar scopes\n8 Link a local Project, Course or Meeting Series\n9 Sign in to Google or Microsoft calendar\n10 Guided integration setup/test\n11 Get an API key / register an app\n12 Upgrade an existing vault (backup + preview)\n13 Restore a vault from backup\n14 Integration coverage (saved configuration, offline)\n15 Vault tools: backup, checks, compare, create, activity, intake, follow-ups\n0 Exit\nChoose: '
            try:choice = self.ask(menu).strip().lower()
            except (EOFError, KeyboardInterrupt):return self.finish()
            try:
                if choice in ('0','cancel','q'):return self.finish()
                if choice == '1':self.setups()
                elif choice == '2':self.features()
                elif choice == '3':self.integrations()
                elif choice == '4':self.preview()
                elif choice == '6':self.test_saved()
                elif choice == '7':self.choose_project()
                elif choice == '8':self.link_record()
                elif choice == '9':self.calendar_signin()
                elif choice == '10':self.integration_setup()
                elif choice == '11':self.credential_guide()
                elif choice == '12':self.upgrade()
                elif choice == '15':
                    self.require_saved('using vault tools')
                    self.vault_tools_entered = True
                    module('fieldbook_vault_tools', ROOT / 'tools/vault-tools.py').run(self.session.root, ask=self.ask, say=self.say, last_test=getattr(self,'last_test',None))
                elif choice == '14':
                    report = module('coverage_report', ROOT / 'tools/integration_coverage.py').offline(self.session.root, type('ConfigurationAPI', (), dict(PROVIDERS=PROVIDERS, admin=admin, check_instance=staticmethod(check_instance))))
                    self.say(json.dumps(report, indent=2, ensure_ascii=True))
                elif choice == '13':
                    result = self.restore()
                    if result and result['restored']:return True  # Restored releases may not have this CLI/config format.
                elif choice == '5':self.save_settings()
                else:self.say('Choose a listed option.')
            except (ValueError, OSError) as error:
                if choice == '13':raise
                self.say('Error: ' + str(error))
            except (EOFError, KeyboardInterrupt):
                if choice == '13':
                    self.say('Restore interrupted. Check the vault and any reported backup/recovery folders before continuing.');return False
                return self.finish()


def upgrade_wizard(target=None, source=None, ask=input, say=print, temporary_parent=None):
    """Use the running release's engine; old targets need not have the new CLI/config."""
    say('Guided upgrade. Close Obsidian and OpenCode for the target vault. A temporary copy is used for planning; a verified full backup is required before apply.')
    target = target or ask('Existing vault path (Enter cancels): ').strip()
    if not target:return None
    root = Path(target).expanduser().resolve(strict=True)
    if source is None:
        default = str(ROOT) if root != ROOT else ''
        source = ask('Release folder or ZIP' + (' [' + default + ']' if default else ' (Enter cancels)') + ': ').strip() or default
    if not source:return None
    default_backup = str(root.parent / (root.name + '-fieldbook-backups'))
    backup = ask('Full-backup folder [' + default_backup + '] (Enter keeps): ').strip() or default_backup
    engine = module('fieldbook_upgrade', ROOT / 'tools/upgrade-vault.py')
    with engine.Upgrade(root, source, backup, admin, say, temporary_parent=temporary_parent) as upgrade:
        session = Session(upgrade.stage)
        editor = Wizard(session, ask=ask, say=say)
        original = copy.deepcopy(session.config)
        say('Release: ' + upgrade.old_version + ' -> ' + upgrade.new_version)
        say('Existing notes, connections and custom settings are kept. Choose only the setup/feature changes you want; connection editing remains available after upgrading.')
        while True:
            c = session.config
            say('Selected setups: ' + (', '.join(c['setups']) or 'core') + '; work role: ' + c['workRole']
                + '; reviews: ' + ('on' if c['features'].get('reviews') else 'off'))
            choice = ask('1 Keep existing settings (reset selections)\n2 Work + people manager + reviews\n3 Work + individual contributor + reviews\n4 Choose any setups, role and work focus\n5 Toggle features\n6 Preview upgrade summary\n7 Review, back up and apply\n0 Cancel\nChoose: ').strip().lower()
            if choice in ('','0','q'):
                say('Upgrade cancelled. The existing vault is unchanged; no full backup was created.');return None
            try:
                if choice == '1':session.config = copy.deepcopy(original)
                elif choice in ('2','3'):
                    c['setups'] = ['work'];c['workRole'] = 'people-manager' if choice == '2' else 'individual-contributor'
                    c['features']['reviews'] = True;c['features']['canvas'] = False;c['defaults']['area']='work'
                elif choice == '4':editor.setups()
                elif choice == '5':editor.features()
                elif choice == '6':
                    say('Legacy layout moves: ' + str(len(upgrade.migration['moves']))
                        + '; kit-file changes: ' + str(len(upgrade.update['files']))
                        + '; note metadata migrations: ' + str(len(upgrade.update['note_edits'])))
                    say('The final preview includes setup activation, preserved customizations and merge candidates. Full backup destination: ' + backup)
                elif choice == '7':
                    errors = configuration_errors(session.config)
                    if errors:raise ValueError('; '.join(errors))
                    preview = upgrade.finalize(session.config, arguments)
                    say(json.dumps(preview, indent=2, ensure_ascii=True))
                    if ask('With both apps closed, type upgrade to create the verified backup and apply this preview (Enter cancels): ').strip() != 'upgrade':
                        say('Upgrade cancelled. The existing vault is unchanged; no full backup was created.');return None
                    result = upgrade.apply()
                    if result['applied']:
                        say('Upgraded to ' + result['version'] + '. Verified full backup: ' + result['backup'])
                        say('Keep the backup until you check your notes. RESTORE.txt explains recovery. Review .fieldbook-new candidates and merge new OpenCode permissions while retaining your provider/settings.')
                        say('Refresh the vault Python dependencies from fieldbook_core/requirements.txt, then restart both apps. No services or OS credentials were accessed. Use the normal configuration menu for connection changes.')
                    else:say('No upgrade changes are needed; no backup or vault files were written.')
                    return result
                else:say('Choose a listed option.')
            except (ValueError, OSError):
                # Final preparation or apply can have changed the temporary state;
                # leave it instead of reusing a partially prepared plan.
                if choice == '7':raise
                say('Invalid selection. Check the setup/feature values and try again.')


def restore_wizard(target=None, backup=None, ask=input, say=print):
    say('Restore a full vault snapshot. Close Obsidian and OpenCode. The current vault will be kept separately before replacement; newer notes are not merged into the selected backup.')
    target = target or ask('Original vault path to restore (Enter cancels): ').strip()
    if not target:return None
    helper = module('fieldbook_restore', ROOT / 'tools/restore-vault.py')
    root = helper.absolute(target)
    if backup is None:
        default = str(root.parent / (root.name + '-fieldbook-backups'))
        directory = ask('Backup folder [' + default + '] (Enter keeps): ').strip() or default
        found = helper.list_backups(directory, root)
        if found['ignored']:say('Ignored ' + str(found['ignored']) + ' folders with invalid or missing receipts.')
        if found['truncated']:say('Only the first 200 folders are listed; enter a specific dated backup folder to reach an older one.')
        for n,item in enumerate(found['backups']):
            say(str(n+1) + ' ' + json.dumps({key:item[key] for key in ('createdUtc','version','kind','status')},ensure_ascii=True)
                + (' — contents will be verified after selection' if item['selectable'] else ' — incomplete/unavailable; cannot restore'))
        if not found['backups']:
            say('No Fieldbook backups for this vault were found in that folder. Select the dated backup folder or use --backup with its path.');return None
        selected = ask('Backup number (Enter or 0 cancels): ').strip()
        if selected in ('','0'):return None
        if not selected.isdigit() or not 1<=int(selected)<=len(found['backups']):raise ValueError('Choose a listed backup number')
        item = found['backups'][int(selected)-1]
        if not item['selectable']:raise ValueError('Choose a completed backup; incomplete backups cannot be restored automatically')
        backup = item['folder']
    with helper.Restore(root, backup, admin, say) as restore:
        say(json.dumps(restore.preview(),indent=2,ensure_ascii=True))
        while True:
            answer = ask('Type list for every changed path, or restore to keep the current vault and restore this snapshot (Enter cancels): ').strip()
            if answer == 'list':say(json.dumps(restore.changes,indent=2,ensure_ascii=True));continue
            if answer != 'restore':
                say('Restore cancelled. The current vault and selected backup are unchanged.');return None
            result = restore.apply();break
        if result['restored']:
            say('Restored Fieldbook ' + result['version'] + ' at ' + result['vault'])
            if result['safetyBackup']:say('The complete pre-restore vault is kept at ' + result['safetyBackup'] + '. Select that backup to undo this restore or recover newer notes.')
            say('The selected backup is unchanged. This CLI is exiting; reopen the restored vault after checking your notes. OS credentials and remote services were not changed.')
        else:say('The vault already matches this backup. No restore or pre-restore backup was needed.')
        return result


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    mode_menu=parser.add_mutually_exclusive_group()
    mode_menu.add_argument('--menu',action='store_true',help='Grouped Setup, Daily use, Integrations and Maintenance menu')
    mode_menu.add_argument('--advanced',action='store_true',help='Original numbered menu (also the configure.py default)')
    parser.add_argument('--vault', help='Vault path; --upgrade/--restore prompt when omitted')
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument('--onboard',action='store_true',help='Guided setups, defaults, optional self record and first task')
    mode.add_argument('--coverage', action='store_true', help='Show saved integration selections and capabilities offline; no keys, remote requests or writes')
    mode.add_argument('--check', action='store_true', help='Validate settings and activation without writing, prompting, reading keys or contacting services')
    mode.add_argument('--test', choices=('all', *PROVIDERS), help='Explicitly test saved connections with read-only remote requests; never enables features')
    mode.add_argument('--calendar-setup', action='store_true', help='Guided calendar setup/test menu; prerequisites stay offline, sign-in and reads run only when selected')
    mode.add_argument('--integration-setup', nargs='?', const='choose', choices=('choose', *PROVIDERS), help='Guided setup/test for any provider; optionally name it to skip the provider picker')
    mode.add_argument('--credential-guide', nargs='?', const='choose', choices=('choose', *PROVIDERS), help='Offline step-by-step API key/app registration instructions; optionally open a selected official link')
    mode.add_argument('--ai-setup',action='store_true',help='Configure AI harnesses and optional MCP; no plugins required')
    mode.add_argument('--upgrade', action='store_true', help='Preview an existing-vault upgrade with setup choices and a verified full backup before apply')
    mode.add_argument('--restore', action='store_true', help='Choose and verify a full backup, preserve the current vault, then restore its snapshot')
    mode.add_argument('--vault-tools', choices=('backup','doctor','compare','create','activity','intake','followups','calendar','cadence','export','daily','weekly','sync-preview'), help='Human-operated local vault tools; changes have their own previews')
    parser.add_argument('--backup', help='Dated backup folder containing receipt.json and vault/; requires --restore')
    parser.add_argument('--temp-dir', help='Existing writable folder for all upgrade preview/release copies; requires --upgrade and must be separate from vault, release and backups')
    parser.add_argument('--from', dest='release', help='Release folder or ZIP for --upgrade; otherwise prompted')
    parser.add_argument('--instance', help='Test one saved instance; requires --test with a named provider')
    args = parser.parse_args(argv)
    if args.instance is not None and (args.test is None or args.test == 'all'):
        parser.error('--instance requires --test with a named provider')
    if args.release is not None and not args.upgrade:parser.error('--from requires --upgrade')
    if args.backup is not None and not args.restore:parser.error('--backup requires --restore')
    if args.temp_dir is not None and not args.upgrade:parser.error('--temp-dir requires --upgrade')
    try:
        if args.restore:
            restore_wizard(args.vault, args.backup)
            return 0
        if args.upgrade:
            upgrade_wizard(args.vault, args.release, temporary_parent=args.temp_dir)
            return 0
        args.vault = args.vault or str(ROOT)
        if args.ai_setup:
            module('fieldbook_ai_setup',ROOT/'tools/ai-setup.py').menu(Path(args.vault))
            return 0
        if args.vault_tools:
            module('fieldbook_vault_tools', ROOT / 'tools/vault-tools.py').run(Path(args.vault),args.vault_tools)
            return 0
        if args.coverage:
            print(json.dumps(module('coverage_report', ROOT / 'tools/integration_coverage.py').offline(args.vault, type('ConfigurationAPI', (), dict(PROVIDERS=PROVIDERS, admin=admin, check_instance=staticmethod(check_instance)))), indent=2, ensure_ascii=True));return 0
        if args.test:
            result = test_connections(args.vault, args.test, args.instance)
            print(json.dumps(result, indent=2, ensure_ascii=True));return result['exitCode']
        session = Session(args.vault)
        if args.check:
            result = session.preview()
            for kind in ('errors','warnings'):
                for message in result[kind]:print(kind[:-1].capitalize() + ': ' + message)
            print('Configuration check: ' + ('failed' if result['errors'] else 'passed') + '. No credentials or remote services were accessed.')
            return 1 if result['errors'] else 0
        ui = Wizard(session)
        if args.onboard:
            ui.onboard();ui.finish()
        elif args.calendar_setup:
            ui.calendar_setup();ui.finish()
        elif args.integration_setup:
            ui.integration_setup(None if args.integration_setup == 'choose' else args.integration_setup);ui.finish()
        elif args.credential_guide:
            ui.credential_guide(None if args.credential_guide == 'choose' else args.credential_guide);ui.finish()
        elif args.menu:ui.menu()
        else:ui.run()
        return 0
    except (KeyboardInterrupt, EOFError):
        if args.restore:
            print('\nRestore interrupted. Check the vault and any reported backup/recovery folders before continuing.')
        elif args.vault_tools or ('ui' in locals() and getattr(ui, 'vault_tools_entered', False)):
            print('\nVault tools interrupted. Earlier confirmed actions may have completed; inspect the reported notes or backup folders before retrying.')
        elif args.test:
            print('\nConnection testing cancelled; no configuration or notes were changed.')
        elif 'session' in locals() and session.save_attempted:
            print('\nSettings were saved; remaining optional prompts were cancelled. Keep any reported backup for recovery.')
        elif 'session' in locals() and session.credential_attempted:
            print('\nCancelled. OS credentials from earlier store attempts may already have changed; remaining staged settings were not saved.')
        else:print('\nCancelled before save; staged settings were not written.')
        return 1
    except (OSError, ValueError, KeyError, TypeError) as error:
        print('Fieldbook configuration: ' + str(error), file=sys.stderr);return 1


if __name__ == '__main__':
    raise SystemExit(main())
