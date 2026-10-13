#!/usr/bin/env python3
"""Plan setup activation without touching notes or overwriting customized resources."""
import hashlib
import json
from pathlib import Path
import re

CATALOG = 'tools/setup-catalog.json'
STATE = '.fieldbook/modules/state.json'
BANK = '.fieldbook/modules/files/'
PROOFS = '.fieldbook/modules/proofs/'
START = '<!-- fieldbook:setup-navigation:start -->'
END = '<!-- fieldbook:setup-navigation:end -->'


def digest(text):
    return hashlib.sha256(text.lstrip('\ufeff').replace('\r\n', '\n').encode()).hexdigest()


def resource_name(name):
    return isinstance(name, str) and re.fullmatch(
        r'(?:Dashboard\.md|(?:Templates|Setups|Dashboards)/.+\.md|(?:fieldbook_core|\.opencode)/(?:commands/.+\.md|skills/.+/SKILL\.md))', name)


def proof_text(root, name, safe, read):
    if not isinstance(name, str) or not re.fullmatch(re.escape(PROOFS) + r'[0-9a-f]{64}\.json', name):
        raise ValueError('Invalid retired module source proof')
    text = read(safe(root, name))
    if digest(text) != name[len(PROOFS):-5]:
        raise ValueError('Edited retired module source proof: ' + name)
    return text


def proven_hash(root, name, source, safe, read):
    """A retired cache remains anchored to its historical manifest, not state alone."""
    if not isinstance(source, dict) or set(source) - {'manifest', 'seeds'} or 'manifest' not in source:
        raise ValueError('Invalid retired module source: ' + name)
    manifest = json.loads(proof_text(root, source['manifest'], safe, read))
    expected = manifest.get('files', {}).get(name)
    if 'seeds' in source:
        if name != 'Templates/Review-format.md':
            raise ValueError('Unexpected retired module seed: ' + name)
        text = proof_text(root, source['seeds'], safe, read)
        if digest(text) != manifest.get('files', {}).get('tools/starter-seeds.json'):
            raise ValueError('Retired module seed differs from its historical manifest')
        value = json.loads(text).get(name)
        if not isinstance(value, str):
            raise ValueError('Missing retired module seed: ' + name)
        expected = digest(value)
    if not isinstance(expected, str) or not re.fullmatch(r'[0-9a-f]{64}', expected):
        raise ValueError('Missing retired module source hash: ' + name)
    return expected


def candidate_hash(root, name, source, safe, read):
    """Reconstruct an owned candidate from a verified canonical and render inputs."""
    if not isinstance(source, dict) or set(source) != {'manifest', 'content', 'navigation', 'config'}:
        raise ValueError('Invalid merge candidate source: ' + name)
    expected = proven_hash(root, name, {'manifest': source['manifest']}, safe, read)
    content = json.loads(proof_text(root, source['content'], safe, read))
    if not isinstance(content, dict) or content.get('path') != name or not isinstance(content.get('text'), str) or digest(content['text']) != expected:
        raise ValueError('Merge candidate canonical differs from its verified source: ' + name)
    config = source['config']
    if (source['navigation'] not in (None, 'dashboard', 'work') or not isinstance(config, dict)
            or not isinstance(config.get('setups'), list) or any(s not in ('personal','work','school') for s in config['setups'])
            or config.get('workRole') not in ('individual-contributor','people-manager')
            or not isinstance(config.get('features'), dict) or type(config['features'].get('reviews')) is not bool):
        raise ValueError('Invalid merge candidate render inputs: ' + name)
    return digest(navigation(content['text'], source['navigation'], config))


def enabled(resource, config):
    return (not resource.get('setup') or resource['setup'] in config.get('setups', [])) and (
        not resource.get('workRole') or resource['workRole'] == config.get('workRole')) and (
        not resource.get('feature') or config.get('features', {}).get(resource['feature']) is True)


def catalog(root, safe, read):
    path = safe(root, CATALOG)
    if not path.exists():
        return []
    data = json.loads(read(path))
    if data.get('schemaVersion') != 1 or not isinstance(data.get('resources'), list):
        raise ValueError('Unsupported setup catalog')
    seen = set()
    for entry in data['resources']:
        name = entry['path']
        safe(root, name)
        if name in seen or not resource_name(name):
            raise ValueError('Invalid or duplicate setup resource: ' + name)
        if entry.get('setup') not in (None, 'personal', 'work', 'school') or entry.get('workRole') not in (None, 'individual-contributor', 'people-manager') or entry.get('feature') not in (None, 'reviews', 'jira', 'agility', 'github', 'azure', 'canvas', 'google', 'microsoft') or entry.get('navigation') not in (None, 'dashboard', 'work'):
            raise ValueError('Invalid setup gate: ' + name)
        seen.add(name)
    return data['resources']


def navigation(text, kind, config):
    if not kind:
        return text
    # The distribution stays readable with every link. Only this marked section varies.
    if text.count(START) != 1 or text.count(END) != 1:
        raise ValueError('Setup navigation needs exactly one marker pair')
    setups = config.get('setups', [])
    links = []
    if kind == 'dashboard':
        for setup in ('personal', 'work', 'school'):
            if setup in setups:
                title = setup.title()
                links.append(f'[[Dashboards/{title}|{title} dashboard]]')
    if 'work' in setups:
        role = 'People manager' if config.get('workRole') == 'people-manager' else 'Individual contributor'
        page = 'People management' if role == 'People manager' else 'Work - Individual contributor'
        links.append(f'[[Dashboards/{page}|{role}]]')
        if config.get('features', {}).get('reviews'):
            links.append('[[Views/Reviews.base|Formal reviews]]')
        if kind == 'work':
            links.append('[[Setups/Work specializations|Domain ideas]]')
    content = '\n' + (' · '.join(links) if links else 'Shared Dashboard is ready. Enable optional setups in [[Setups]].') + '\n'
    return re.sub(re.escape(START) + r'.*?' + re.escape(END), lambda _: START + content + END, text, flags=re.S)


class Plan:
    def __init__(self, root, safe, read, write):
        self.root, self.safe, self.read, self.write = root, safe, read, write
        self.writes, self.deletes, self.actions = {}, [], []
        self.preserved, self.removed = [], []
        self.enabled, self.inactive = [], []

    def put(self, name, text, action):
        path = self.safe(self.root, name)
        for ancestor in path.parents:
            if ancestor == self.root:break
            if ancestor.exists() and not ancestor.is_dir():
                raise ValueError('Resource parent collides with a file: ' + str(ancestor.relative_to(self.root)))
        if path.exists() and not path.is_file():
            raise ValueError('Resource collides with a directory: ' + name)
        if not path.exists() or self.read(path) != text:
            self.writes[name] = text
            self.actions.append({'path': name, 'action': action})

    def candidate(self, name, text, prior, canonical, entry, config, manifest):
        target = name + '.fieldbook-new'
        path = self.safe(self.root, target)
        if path.exists() and (not path.is_file() or digest(self.read(path)) != digest(text)):
            if (not path.is_file() or digest(self.read(path)) != prior.get('candidateHash')
                    or candidate_hash(self.root, name, prior.get('candidateSource'), self.safe, self.read) != prior.get('candidateHash')):
                raise ValueError('Existing merge candidate would be overwritten: ' + target)
        if digest(canonical) != manifest.get('files', {}).get(name):
            raise ValueError('Merge candidate canonical differs from its verified source: ' + name)
        source = {'manifest': self.proof(json.dumps(manifest, indent=2) + '\n'),
                  'content': self.proof(json.dumps({'path': name, 'text': canonical}, indent=2) + '\n'),
                  'navigation': entry.get('navigation'),
                  'config': {'setups': config.get('setups', []), 'workRole': config.get('workRole', 'individual-contributor'),
                             'features': {'reviews': config.get('features', {}).get('reviews') is True}}}
        self.put(target, text, 'conflict')
        return {'candidateHash': digest(text), 'candidateSource': source}

    def proof(self, text):
        name = PROOFS + digest(text) + '.json'
        path = self.safe(self.root, name)
        if path.exists() and (not path.is_file() or digest(self.read(path)) != digest(text)):
            raise ValueError('Edited retired module source proof: ' + name)
        self.put(name, text, 'cache-source-proof')
        return name

    def apply(self):
        # Every destination and destructive action was validated while planning.
        for name, text in self.writes.items():
            if name != STATE:
                self.write(self.safe(self.root, name), text)
        for name in self.deletes:
            self.safe(self.root, name).unlink()
        if STATE in self.writes:
            self.write(self.safe(self.root, STATE), self.writes[STATE])

    def summary(self):
        return {'enabled': self.enabled, 'inactive': self.inactive, 'files': self.actions, 'deactivated': self.deletes,
                'preserved_customizations': self.preserved, 'user_removed_preserved': self.removed,
                'note': 'Customized active resources remain visible as explicit preservation exceptions. Hidden module copies restore optional resources when enabled.'}


def plan(root, config, safe, read, write, release=None, manifest=None, old_manifest=None):
    """Preflight all writes/deletions. A release is authoritative; configure uses its bank."""
    source = release or root
    resources = catalog(source, safe, read)
    result = Plan(root, safe, read, write)
    if not resources and not safe(root, STATE).exists():
        return result
    if manifest is None:
        path = safe(root, 'fieldbook-manifest.json')
        manifest = json.loads(read(path)) if path.exists() else {'files': {}}
    old_manifest = old_manifest or manifest
    seeds_path = safe(source, 'tools/starter-seeds.json')
    seeds = json.loads(read(seeds_path)) if seeds_path.exists() else {}
    state_path = safe(root, STATE)
    state = json.loads(read(state_path)) if state_path.exists() else {'schemaVersion': 1, 'resources': {}}
    if state.get('schemaVersion') != 1 or not isinstance(state.get('resources'), dict):
        raise ValueError('Unsupported setup activation state')
    next_state = {'schemaVersion': 1, 'resources': {}}
    names = {entry['path'] for entry in resources}
    # A removed optional resource may return in a future release. Keep its source
    # proof and ownership instead of abandoning an untracked hidden cache.
    for name, prior in state['resources'].items():
        if name in names:
            continue
        if not resource_name(name) or not isinstance(prior, dict):
            raise ValueError('Invalid retired setup resource: ' + str(name))
        active = safe(root, name); bank_name = BANK + name; bank = safe(root, bank_name)
        if active.exists() and not active.is_file():
            raise ValueError('Resource collides with a directory: ' + name)
        bank_text = read(bank)
        if prior.get('retired'):
            source_proof = prior.get('source')
            expected = proven_hash(root, name, source_proof, safe, read)
        else:
            source_proof = {'manifest': result.proof(json.dumps(old_manifest, indent=2) + '\n')}
            expected = old_manifest.get('files', {}).get(name)
            if expected is None and name == 'Templates/Review-format.md':
                old_seeds_text = read(safe(root, 'tools/starter-seeds.json'))
                if digest(old_seeds_text) != old_manifest.get('files', {}).get('tools/starter-seeds.json'):
                    raise ValueError('Module seed differs from its historical manifest: ' + name)
                old_seed = json.loads(old_seeds_text).get(name)
                if not isinstance(old_seed, str):
                    raise ValueError('Missing historical module seed: ' + name)
                source_proof['seeds'] = result.proof(old_seeds_text)
                expected = digest(old_seed)
        if not expected or digest(bank_text) != expected or prior.get('bankHash') != expected:
            raise ValueError('Retired module recovery copy differs from its verified source: ' + bank_name)
        current = read(active) if active.exists() else None
        pristine = current is not None and digest(current) in {expected, prior.get('activeHash')}
        was_shared = prior.get('retired') is True and name in old_manifest.get('files', {})
        removed = bool(prior.get('removed')) or (current is None and (prior.get('enabled') is True or was_shared))
        # A catalog exit that leaves the path in the manifest makes it shared;
        # the general updater owns its active copy from then on.
        shared = name in manifest.get('files', {})
        preserved = current is not None and not pristine
        if not shared and current is not None:
            if pristine:
                result.deletes.append(name)
            else:
                result.preserved.append({'path': name, 'reason': 'Retired customized resource remains available; its historical source is preserved.'})
        result.inactive.append(name)
        next_state['resources'][name] = {**{key: prior[key] for key in ('candidateHash','candidateSource') if key in prior},
            'retired': True, 'enabled': False, 'removed': removed,
            'activeHash': prior.get('activeHash'), 'bankHash': expected, 'preserved': preserved, 'source': source_proof}
    for entry in resources:
        name = entry['path']; active = safe(root, name); bank_name = BANK + name; bank = safe(root, bank_name)
        prior = state['resources'].get(name, {})
        current = read(active) if active.exists() and active.is_file() else None
        if active.exists() and not active.is_file():
            raise ValueError('Resource collides with a directory: ' + name)
        known = {h for h in (prior.get('activeHash'), old_manifest['files'].get(name)) if h}
        if entry.get('seed'):
            if name not in seeds:
                raise ValueError('Missing setup seed: ' + name)
            known.add(digest(seeds[name]))
        old_bank = read(bank) if bank.exists() and bank.is_file() else None
        if bank.exists() and not bank.is_file():
            raise ValueError('Module recovery path collides with a directory: ' + bank_name)
        if old_bank is not None and digest(old_bank) != prior.get('bankHash'):
            raise ValueError('Customized or untracked module recovery copy; preserve it elsewhere before retrying: ' + bank_name)
        if prior.get('retired'):
            expected = proven_hash(root, name, prior.get('source'), safe, read)
            if old_bank is None or digest(old_bank) != expected:
                raise ValueError('Retired module recovery copy differs from its verified source: ' + bank_name)
        if release:
            canonical = seeds[name] if entry.get('seed') else read(safe(source, name))
            if not entry.get('seed') and digest(canonical) != manifest['files'].get(name):
                raise ValueError('Module release hash mismatch: ' + name)
        elif old_bank is not None:
            canonical = old_bank
        elif entry.get('seed'):
            canonical = seeds[name]
        elif current is not None and digest(current) in known:
            canonical = current
        else:
            # Cannot reconstruct an edited or removed distribution file on configure.
            result.preserved.append({'path': name, 'reason': 'No verified canonical copy; update from a clean release to install optional resources.'})
            continue
        result.put(bank_name, canonical, 'cache-module')
        wanted = bool(enabled(entry, config))
        (result.enabled if wanted else result.inactive).append(name)
        rendered = navigation(canonical, entry.get('navigation'), config) if wanted else canonical
        known.add(digest(canonical))
        pristine = current is not None and digest(current) in known
        removed = bool(prior.get('removed'))
        if current is not None:
            removed = False
        elif prior.get('enabled') is True or (prior.get('retired') is True and name in old_manifest['files']) or (not prior and name in old_manifest['files']):
            removed = True
        installed_hash = prior.get('activeHash')
        candidate = {key: prior[key] for key in ('candidateHash','candidateSource') if key in prior}
        if wanted:
            if current is None and removed:
                result.removed.append(name)
            elif current is None or pristine:
                result.put(name, rendered, 'activate' if current is None else 'refresh-module')
                installed_hash = digest(rendered)
            elif digest(current) == digest(rendered):
                installed_hash = digest(rendered)
            else:
                result.preserved.append({'path': name, 'reason': 'Customized active resource preserved.'})
                if not entry.get('seed'):
                    candidate = result.candidate(name, rendered, prior, canonical, entry, config, manifest)
        elif current is not None:
            if pristine:
                result.deletes.append(name)
            else:
                result.preserved.append({'path': name, 'reason': 'Setup disabled; customized active resource remains available. Move it manually to hide it.'})
                # Canonical replacement is in the hidden bank, never overwrite user content.
        next_state['resources'][name] = {**candidate, 'enabled': wanted, 'removed': removed,
                                         'activeHash': installed_hash, 'bankHash': digest(canonical),
                                         'preserved': current is not None and not pristine and digest(current) != digest(rendered)}
    result.put(STATE, json.dumps(next_state, indent=2) + '\n', 'activation-state')
    return result
