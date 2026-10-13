#!/usr/bin/env python3
"""Preview/apply explicit local Project and Course integration bindings.

No network requests, credential lookups, note creation, body edits or generic
metadata writes. YAML token offsets retain unrelated frontmatter verbatim.
"""
import datetime as dt
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import tempfile
import types
import unicodedata
import uuid

CONTENT = {'Tasks', 'Projects', 'People', 'Notes', 'Meetings', 'Decisions', 'Reference', 'Research',
           'Reports', 'Transcripts', 'Accomplishments', 'Opportunities', 'Items', 'Lists'}
EXCLUDE = {'templates', 'examples', 'setups', 'dashboards', 'views', 'tools', 'tests', 'node_modules', '__pycache__'}
FIELDS = {'jira': ('jira_instance', 'jira_project_key'), 'agility': ('agility_instance', 'agility_scope_id'),
          'github': ('github_instance', 'github_repository'), 'azure': ('azure_instance', 'azure_project'),
          'canvas': ('canvas_instance', 'canvas_course_id'),
          'google': ('calendar_provider', 'calendar_instance', 'calendar_id', 'calendar_series_id'),
          'microsoft': ('calendar_provider', 'calendar_instance', 'calendar_id', 'calendar_series_id')}
MAX_FILE = 1024 * 1024


class LinkError(ValueError):pass


def _hash(raw):return hashlib.sha256(raw).hexdigest()


def _yaml():
    try:import yaml
    except ImportError:
        raise LinkError('Install fieldbook_core/requirements.txt in the vault Python environment to link Project or Course notes (PyYAML is required).') from None
    return yaml


def _path(root, relative, *, internal=False, missing=False):
    if not isinstance(relative, str) or not relative or len(relative) > 500:raise LinkError('Choose a vault-relative Markdown note path.')
    parts = relative.split('/')
    if any(not p or p in ('.', '..') or p.endswith((' ', '.')) or re.search(r'[\\:*?"<>|\x00-\x1f\x7f]', p)
           or re.match(r'^(con|prn|aux|nul|com[1-9¹²³]|lpt[1-9¹²³])(?:\.|$)', p, re.I) for p in parts):
        raise LinkError('Use a safe relative path with / separators; no traversal or device names.')
    if not internal and (len(parts) < 2 or parts[0] not in CONTENT or not relative.endswith('.md')
                         or any(p.startswith('.') or p.casefold() in EXCLUDE or p.casefold() in ('agents.md', 'agents.local.md') for p in parts)):
        raise LinkError('Choose a Markdown note in a content folder; templates, examples, settings and instructions are protected.')
    current = root
    for index, part in enumerate(parts):
        if current.exists():
            if any(p.name.casefold() == part.casefold() and p.name != part for p in current.iterdir()):raise LinkError('Use the existing path spelling and case.')
        current = current / part
        try:info = current.lstat()
        except FileNotFoundError:
            if missing:continue
            raise LinkError('The selected note no longer exists.') from None
        if stat.S_ISLNK(info.st_mode) or getattr(info, 'st_file_attributes', 0) & 0x400:raise LinkError('Linked paths and reparse points are not supported.')
        if index < len(parts) - 1 and not stat.S_ISDIR(info.st_mode):raise LinkError('A parent path is not a directory.')
        if index == len(parts) - 1 and (not stat.S_ISREG(info.st_mode) or info.st_nlink != 1):raise LinkError('Only regular files with one hard link may be linked.')
    if not current.resolve().is_relative_to(root):raise LinkError('The selected path is outside the vault.')
    return current


def _read(root, relative):
    path = _path(root, relative)
    fd = os.open(path, os.O_RDONLY | getattr(os, 'O_NOFOLLOW', 0) | getattr(os, 'O_NONBLOCK', 0) | getattr(os, 'O_BINARY', 0))
    with os.fdopen(fd, 'rb') as stream:
        info = os.fstat(stream.fileno())
        if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1 or info.st_size > MAX_FILE:raise LinkError('The note must be a regular UTF-8 file no larger than 1 MiB.')
        raw = stream.read(MAX_FILE + 1)
    if len(raw) > MAX_FILE or b'\0' in raw:raise LinkError('The note must be UTF-8 text no larger than 1 MiB.')
    try:raw.decode('utf-8-sig')
    except UnicodeError:raise LinkError('The note must contain valid UTF-8 text.') from None
    return path, raw, info


def _frontmatter(raw):
    yaml = _yaml();text = raw.decode('utf-8')
    match = re.match(r'^(?:\ufeff)?---(\r?\n)(.*?)(\r?\n)---(?:\r?\n|$)', text, re.S)
    if not match or len(match[2]) > 32768:raise LinkError('The note needs bounded YAML frontmatter with closing --- delimiters.')
    source = match[2]
    try:
        if any(isinstance(t, (yaml.AliasToken, yaml.AnchorToken, yaml.TagToken)) for t in yaml.scan(source)):
            raise LinkError('YAML aliases, anchors and explicit tags are not supported for binding edits.')
        node = yaml.compose(source, Loader=yaml.BaseLoader)
        def convert(current):
            if isinstance(current, yaml.ScalarNode):return current.value
            if isinstance(current, yaml.SequenceNode):return [convert(v) for v in current.value]
            if isinstance(current, yaml.MappingNode):
                result = {}
                for key, value in current.value:
                    if not isinstance(key, yaml.ScalarNode) or key.value in result:raise LinkError('Frontmatter must use unique scalar keys; duplicate keys cannot be edited safely.')
                    result[key.value] = convert(value)
                return result
            raise LinkError('Unsupported YAML frontmatter.')
        if not isinstance(node, yaml.MappingNode):raise LinkError('Frontmatter must be a mapping.')
        metadata = convert(node)
    except LinkError:raise
    except Exception:raise LinkError('Invalid YAML frontmatter; repair it before linking this note.') from None
    return text, match, node, metadata


def _tags(metadata):
    tags = metadata.get('tags', [])
    if isinstance(tags, str):tags = [tags]
    return {v.lstrip('#').casefold() for v in tags if isinstance(v, str)} if isinstance(tags, list) else set()


def _eligible(metadata, provider=None):
    tags = _tags(metadata)
    if 'review' in tags and str(metadata.get('status', '')).casefold() == 'final':raise LinkError('Final review notes are protected.')
    if not tags.intersection(('course', 'project', 'series')):raise LinkError('The selected note must be tagged project, course or series.')
    if provider in ('google', 'microsoft'):
        if 'series' not in tags:raise LinkError('Calendar series bindings belong on a Meeting series note tagged series.')
        return 'series'
    if provider == 'canvas' and 'course' not in tags:raise LinkError('Canvas bindings belong on a Course note tagged course.')
    if provider and provider != 'canvas' and 'project' not in tags:raise LinkError('Tracker project bindings belong on a note tagged project.')
    return 'series' if 'series' in tags else 'course' if 'course' in tags else 'project'


def _bindings(metadata):
    return {p: {f: metadata.get(f, '') for f in fields} for p, fields in FIELDS.items()
            if any(metadata.get(f) for f in fields) and (p not in ('google', 'microsoft') or metadata.get('calendar_provider') == p)}


def list_records(root, kind=None):
    """List parseable existing content notes, bounded to 10,000 files/64 MiB.

    Malformed/ineligible/linked notes are omitted. Selecting a path explicitly in
    plan_link reports its error. kind=project includes Courses tagged project.
    """
    _yaml();root = Path(root).resolve(strict=True)
    if kind not in (None, 'project', 'course', 'series'):raise LinkError('Choose project, course or series records.')
    records = [];count = 0;size = 0
    for folder in sorted(CONTENT):
        base = root / folder
        if not base.is_dir() or base.is_symlink():continue
        for directory, dirs, names in os.walk(base, followlinks=False):
            dirs[:] = sorted(d for d in dirs if not d.startswith('.') and d.casefold() not in EXCLUDE and not (Path(directory) / d).is_symlink())
            for name in sorted(names):
                if not name.endswith('.md'):continue
                count += 1
                if count > 10000:raise LinkError('Record scan exceeds 10,000 Markdown files; narrow the vault before using the picker.')
                relative = (Path(directory) / name).relative_to(root).as_posix()
                try:
                    _, raw, _ = _read(root, relative);size += len(raw)
                    if size > 64 * MAX_FILE:raise LinkError('Record scan exceeds 64 MiB; narrow the vault before using the picker.')
                    _, _, _, metadata = _frontmatter(raw);record_kind = _eligible(metadata)
                    if kind and kind not in _tags(metadata):continue
                    title = metadata.get('title')
                    if not isinstance(title, str) or not title.strip():title = Path(relative).stem
                    title = ''.join(' ' if unicodedata.category(c).startswith('C') else c for c in title)[:200]
                    records.append({'path': relative, 'title': title, 'kind': record_kind, 'sha256': _hash(raw), 'expected': _hash(raw), 'bindings': _bindings(metadata)})
                except LinkError:
                    if size > 64 * MAX_FILE:raise
                    continue
    return records


def _connection(root, provider, instance):
    if provider not in FIELDS or not isinstance(instance, str) or not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_-]{0,63}', instance):
        raise LinkError('Choose a supported provider and saved instance ID.')
    # Fixed companion code; no dependency on configure.py and no .pyc writes.
    source = Path(__file__).with_name('integration_checks.py')
    checks = types.ModuleType('fieldbook_link_checks');checks.__file__ = str(source)
    exec(compile(source.read_bytes(), str(source), 'exec'), checks.__dict__)
    try:
        raw = checks._safe_file(root, 'fieldbook_core/' + provider + '.json', 65536)
        if provider in ('google', 'microsoft'):
            data = checks._json(raw)
            matches = [i for i in data.get('instances', []) if isinstance(i, dict) and i.get('id') == instance]
            if len(matches) != 1 or checks._secret_fields(data):raise ValueError()
            item = matches[0]
            base = 'https://www.googleapis.com/calendar/v3' if provider == 'google' else 'https://graph.microsoft.com/v1.0'
            if item.get('baseUrl', '').rstrip('/') != base or not re.fullmatch(provider.upper() + r'_[A-Z0-9_]+', item.get('tokenVar', '')):raise ValueError()
            if item.get('authMode', 'access-token') not in ('oauth', 'access-token'):raise ValueError()
            if item.get('credentialStore', 'environment') not in ('environment', 'keyring'):raise ValueError()
        else:checks._configuration(root, provider, instance)
    except Exception:raise LinkError('Save a valid integration connection with this instance ID and HTTPS URL before linking a note.') from None
    return _hash(raw)


def _scope(provider, choice):
    if not isinstance(choice, dict) or not isinstance(choice.get('id'), (str, int)) or isinstance(choice['id'], bool):raise LinkError('Choose a validated remote project or course scope.')
    identity = str(choice['id'])
    if provider in ('google', 'microsoft'):
        settings = choice.get('settings')
        if not isinstance(settings, dict):raise LinkError('Choose a calendar series with its calendar and saved connection identity.')
        values = {f: settings.get(f) for f in FIELDS[provider]}
        if values['calendar_provider'] != provider or values['calendar_series_id'] != identity:raise LinkError('The series choice does not match the selected provider or series ID.')
        if any(not isinstance(v, str) or not v or len(v) > 1024 or v in ('.', '..') or any(unicodedata.category(c).startswith('C') for c in v) for v in values.values()):raise LinkError('Calendar series identity fields must be bounded text.')
        if provider == 'google' and values['calendar_id'].casefold() == 'primary':raise LinkError('Choose the real Google calendar ID from calendar discovery; the primary alias is not a stable binding.')
        return values, {'id': identity, 'settings': values}
    if provider == 'jira' and re.fullmatch(r'[A-Za-z][A-Za-z0-9_]{0,127}', identity):return identity, {'id': identity}
    if provider == 'agility' and re.fullmatch(r'Scope:[1-9]\d{0,19}', identity):return identity, {'id': identity}
    if provider == 'github' and re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9-]{0,38}/[A-Za-z0-9_.-]{1,100}', identity) and identity.split('/')[1] not in ('.', '..'):return identity, {'id': identity}
    if provider == 'canvas' and re.fullmatch(r'[1-9]\d{0,19}', identity):return identity, {'id': identity}
    if provider == 'azure':
        settings = choice.get('settings', {})
        value = settings.get('project', identity) if isinstance(settings, dict) else None
        if (isinstance(value, str) and 0 < len(value) <= 256 and value == value.strip() and value not in ('.', '..')
                and not re.search(r'[/\\\x00-\x1f\x7f]', value) and not ('"' in value and "'" in value)):
            return value, {'id': value, 'settings': {'project': value}}
    raise LinkError('Invalid remote scope: use a Jira key, Agility Scope:123, GitHub owner/repository, Azure project name, or Canvas course ID.')


def _has_item(metadata, provider):
    fields = [provider, provider + '_id', provider + '_key', provider + '_number', provider + '_issue', provider + '_issue_id']
    if provider == 'canvas':fields += ['canvas_assignment_id', 'canvas_event_id', 'canvas_quiz_id', 'canvas_discussion_id', 'canvas_identity', 'canvas_aliases', 'canvas_checkpoint_tag']
    return any(metadata.get(f) not in (None, '', 'none', 'null', '~') for f in fields)


def _render(raw, values):
    yaml = _yaml();text, match, node, metadata = _frontmatter(raw);source = match[2];edits = [];missing = []
    nodes = {key.value: value for key, value in node.value}
    for field, value in values.items():
        if metadata.get(field, '') == value:continue
        rendered = json.dumps(value, ensure_ascii=False)
        if field not in nodes:
            missing.append(field + ': ' + rendered);continue
        current = nodes[field]
        if not isinstance(current, yaml.ScalarNode):raise LinkError('Existing binding fields must be scalar text; repair complex values manually before linking.')
        start, end = current.start_mark.index, current.end_mark.index
        if start == end and start and source[start - 1] == ':':rendered = ' ' + rendered
        if source[start:end].endswith('\n'):rendered += '\r\n' if source[start:end].endswith('\r\n') else '\n'
        edits.append((start, end, rendered))
    if missing:
        if node.flow_style:
            position = node.end_mark.index - 1
            if source[position:position + 1] != '}':raise LinkError('Cannot safely append binding fields to this frontmatter style.')
            edits.append((position, position, ', ' + ', '.join(missing)))
        else:
            newline = match[1];indent = ' ' * node.start_mark.column
            edits.append((len(source), len(source), newline + newline.join(indent + item for item in missing)))
    for start, end, value in sorted(edits, reverse=True):source = source[:start] + value + source[end:]
    result = (text[:match.start(2)] + source + text[match.end(2):]).encode('utf-8')
    if len(result) > MAX_FILE:raise LinkError('The edited note would exceed 1 MiB.')
    _, _, _, after = _frontmatter(result)
    expected = dict(metadata);expected.update(values)
    # Missing empty bindings need no key inserted, but are equivalent to unset.
    expected = {k: v for k, v in expected.items() if k in metadata or v != ''}
    if after != expected:raise LinkError('This YAML layout cannot be edited while preserving unrelated metadata; adjust the binding fields manually.')
    return result


def plan_link(root, path, provider, instanceID, remotechoice, *, expected=None):
    root = Path(root).resolve(strict=True);configuration_hash = _connection(root, provider, instanceID)
    _, raw, _ = _read(root, path);before_hash = _hash(raw)
    if expected is not None and expected != before_hash:raise LinkError('The note changed after selection. Read it again and review a fresh plan.')
    _, _, _, metadata = _frontmatter(raw);kind = _eligible(metadata, provider)
    if provider in ('google', 'microsoft'):
        if any(f in metadata and not isinstance(metadata[f], str) for f in FIELDS[provider]):raise LinkError('Existing calendar binding fields must be scalar text.')
        if remotechoice is None:
            if metadata.get('calendar_provider') not in ('', None, provider) or metadata.get('calendar_instance') not in ('', None, instanceID):raise LinkError('Select the currently bound calendar provider and instance before clearing the series.')
            values = {f: '' for f in FIELDS[provider]};choice = None
        else:
            values, choice = _scope(provider, remotechoice)
            if values['calendar_instance'] != instanceID:raise LinkError('The series choice belongs to a different saved connection.')
        if any(metadata.get(f) for f in ('calendar_uid', 'calendar_event_id', 'calendar_recurrence_id')) and any(metadata.get(f, '') != value for f, value in values.items()):
            raise LinkError('Existing meeting event metadata would change identity; resolve the event link manually before changing its series binding.')
        return _make_plan(root, path, provider, instanceID, choice, configuration_hash, raw, metadata, kind, values)
    instance_field, scope_field = FIELDS[provider]
    for field in (instance_field, scope_field):
        if field in metadata and not isinstance(metadata[field], str):raise LinkError('Existing binding fields must be scalar text.')
    old_instance = metadata.get(instance_field, '');old_scope = metadata.get(scope_field, '')
    linked_item = _has_item(metadata, provider)
    if remotechoice is None:
        if old_instance and old_instance != instanceID:raise LinkError('Select the currently bound instance before clearing its project/course binding.')
        if provider == 'canvas' and linked_item:raise LinkError('Canvas assignment/event metadata depends on this course identity; clear or repair the item links manually first.')
        values = {scope_field: '', instance_field: old_instance if linked_item else ''};choice = None
    else:
        value, choice = _scope(provider, remotechoice)
        if linked_item and old_instance != instanceID:raise LinkError('Existing ticket/item metadata would change identity. Resolve its instance explicitly before rebinding this project or course.')
        if provider == 'canvas' and linked_item and old_scope != value:raise LinkError('Existing Canvas assignment/event metadata would change course identity; resolve it manually first.')
        values = {instance_field: instanceID, scope_field: value}
    return _make_plan(root, path, provider, instanceID, choice, configuration_hash, raw, metadata, kind, values)


def _make_plan(root, path, provider, instanceID, choice, configuration_hash, raw, metadata, kind, values):
    after = _render(raw, values);before_hash = _hash(raw)
    changes = [{'field': f, 'before': metadata.get(f, ''), 'after': v} for f, v in values.items() if metadata.get(f, '') != v]
    return {'version': 1, 'vault': _hash(str(root).encode()), 'path': path, 'kind': kind, 'provider': provider, 'instance': instanceID,
            'remotechoice': choice, 'before_hash': before_hash, 'after_hash': _hash(after), 'configuration_hash': configuration_hash,
            'changes': changes, 'diff': '\n'.join(c['field'] + ': ' + json.dumps(c['before'], ensure_ascii=False) + ' -> ' + json.dumps(c['after'], ensure_ascii=False) for c in changes),
            'unchanged': raw == after}


def _mkdir(root, relative):
    current = root
    for part in relative.split('/'):
        current = current / part
        try:current.mkdir()
        except FileExistsError:pass
        info = current.lstat()
        if not stat.S_ISDIR(info.st_mode) or stat.S_ISLNK(info.st_mode) or getattr(info, 'st_file_attributes', 0) & 0x400:
            raise LinkError('Backup or note directory is linked or invalid.')


def apply_link(root, plan):
    """Revalidate an explicit plan, back up exact bytes, then atomically replace."""
    if not isinstance(plan, dict):raise LinkError('Provide a reviewed binding plan.')
    root = Path(root).resolve(strict=True)
    try:
        fresh = plan_link(root, plan['path'], plan['provider'], plan['instance'], plan['remotechoice'], expected=plan['before_hash'])
    except (KeyError, TypeError):raise LinkError('Provide a complete reviewed binding plan.') from None
    if fresh != plan:raise LinkError('The plan, connection or note changed; review a fresh plan before applying.')
    path, raw, info = _read(root, plan['path'])
    if _hash(raw) != plan['before_hash']:raise LinkError('The note changed; no binding was applied.')
    if plan['unchanged']:return {'path': plan['path'], 'sha256': plan['after_hash'], 'backup': None, 'unchanged': True}
    after = _render(raw, {c['field']: c['after'] for c in plan['changes']})
    if _hash(after) != plan['after_hash']:raise LinkError('The reviewed result no longer matches; no binding was applied.')
    stamp = dt.datetime.now(dt.timezone.utc).strftime('%Y%m%dT%H%M%SZ')
    backup = '.fieldbook/config-backups/' + stamp + '-link-' + uuid.uuid4().hex + '/' + plan['path']
    _path(root, backup, internal=True, missing=True)  # Preflight before mkdir/write.
    _mkdir(root, str(Path(backup).parent).replace(os.sep, '/'))
    backup_path = _path(root, backup, internal=True, missing=True)
    fd = os.open(backup_path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, 'O_NOFOLLOW', 0), 0o600)
    with os.fdopen(fd, 'wb') as stream:stream.write(raw);stream.flush();os.fsync(stream.fileno())
    temporary = None
    try:
        fd, temporary = tempfile.mkstemp(prefix='.fieldbook-link-', dir=path.parent)
        with os.fdopen(fd, 'wb') as stream:
            stream.write(after);stream.flush();os.fsync(stream.fileno())
            if hasattr(os, 'fchmod'):os.fchmod(stream.fileno(), stat.S_IMODE(info.st_mode))
            else:os.chmod(temporary, stat.S_IMODE(info.st_mode))
        current_path, current, current_info = _read(root, plan['path'])
        if (_hash(current) != plan['before_hash'] or (current_info.st_dev, current_info.st_ino) != (info.st_dev, info.st_ino)
                or _connection(root, plan['provider'], plan['instance']) != plan['configuration_hash']):
            raise LinkError('The note or saved connection changed while applying; no binding was applied. The original-byte backup remains available.')
        _path(root, plan['path'])
        os.replace(temporary, current_path);temporary = None
    finally:
        if temporary is not None:
            try:os.unlink(temporary)
            except FileNotFoundError:pass
    return {'path': plan['path'], 'sha256': plan['after_hash'], 'backup': backup, 'unchanged': False}
