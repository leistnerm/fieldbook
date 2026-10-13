#!/usr/bin/env python3
"""Create a new vault from a verified Fieldbook release. Preview unless --apply."""
import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path, PurePosixPath
import shutil
import stat
import tempfile
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
FOLDERS = ('Tasks', 'Projects', 'People', 'Notes', 'Meetings', 'Decisions', 'Reference',
           'Research', 'Reports', 'Transcripts', 'Accomplishments', 'Opportunities', 'Items', 'Lists', 'Attachments')
MAX_ASSET = 20 * 1024 * 1024


def relative(root, name):
    parts = PurePosixPath(name).parts
    if not parts or name.startswith('/') or '\\' in name or ':' in name or any(p in {'.', '..'} for p in name.split('/')):
        raise ValueError(f'Unsafe release path: {name}')
    current = root
    for part in parts:
        current = current / part
        if current.is_symlink() or current.exists() and getattr(current.lstat(), 'st_file_attributes', 0) & 0x400:
            raise ValueError(f'Linked paths are not supported: {name}')
    if not current.resolve().is_relative_to(root.resolve()):
        raise ValueError(f'Path escapes release: {name}')
    return current


def checked_release(root):
    manifest = json.loads((root / 'fieldbook-manifest.json').read_text('utf-8-sig'))
    for name, expected in manifest['files'].items():
        file = relative(root, name)
        if not file.is_file():
            raise ValueError(f'Missing release file: {name}')
        text = file.read_text('utf-8-sig').replace('\r\n', '\n')
        if hashlib.sha256(text.encode()).hexdigest() != expected:
            raise ValueError(f'Edited or damaged release file: {name}; deploy from a clean release')
    for required in ('tools/starter-seeds.json', 'tools/starter-settings.json', 'tools/starter-plugins.json'):
        if required not in manifest['files']:
            raise ValueError(f'Release does not cover {required}')
    return manifest


def fetch(url):
    # Release URLs are fixed in the hash-verified lock, never chosen by a model tool.
    if not url.startswith(('https://github.com/', 'https://codeload.github.com/')):
        raise ValueError('Plugin downloads must start at an HTTPS GitHub release URL')
    req = urllib.request.Request(url, headers={'User-Agent': 'Fieldbook-starter'})
    with urllib.request.urlopen(req, timeout=30) as response:
        if not response.url.startswith('https://'):
            raise ValueError('Insecure download redirect')
        data = response.read(MAX_ASSET + 1)
    if len(data) > MAX_ASSET:
        raise ValueError('Plugin asset exceeds 20 MiB')
    return data


def cached_download(root, cache):
    """An explicit offline cache never falls back to the network."""
    cache = Path(cache).resolve(strict=True)
    lock = json.loads((root / 'tools/starter-plugins.json').read_text())
    paths = {}
    for plugin in lock['plugins']:
        prefix = f"{plugin['id']}/{plugin['version']}/"
        for asset in plugin['assets']:
            paths[asset['url']] = prefix + asset['name']
        if plugin.get('source'):
            paths[plugin['source']['url']] = prefix + 'source.tar.gz'
    def read(url):
        if url not in paths:
            raise ValueError('URL is absent from the locked cache map')
        file = relative(cache, paths[url])
        if file.stat().st_size > MAX_ASSET:
            raise ValueError('Cached asset exceeds 20 MiB')
        return file.read_bytes()
    return read


def deploy(root, destination, setups, work_role='individual-contributor', apply=False,
           plugins=True, download=fetch):
    root = Path(root).resolve(strict=True)
    # Check lexical components before resolving, so symlink parents cannot hide.
    destination = Path(os.path.abspath(os.path.expanduser(str(destination))))
    if any(p.is_symlink() or p.exists() and getattr(p.lstat(), 'st_file_attributes', 0) & 0x400
           for p in [destination, *destination.parents]):
        raise ValueError('Destination and its parents must not be links/reparse points')
    if destination.exists():
        raise ValueError('Destination already exists; choose a new folder. Use UPGRADING for a live vault.')
    if not destination.parent.is_dir():
        raise ValueError('Create the destination parent folder first')
    if destination.is_relative_to(root) or root.is_relative_to(destination):
        raise ValueError('Do not deploy inside or around the source vault')
    if set(setups) - {'personal', 'work', 'school'} or len(setups) != len(set(setups)):
        raise ValueError('Choose core alone or unique personal,work,school setups')
    if work_role not in {'individual-contributor', 'people-manager'}:
        raise ValueError('Invalid work role')
    manifest = checked_release(root)
    lock = json.loads((root / 'tools/starter-plugins.json').read_text())
    summary = {'destination': str(destination), 'version': manifest['version'], 'setups': setups,
               'workRole': work_role, 'plugins': [{k: p[k] for k in ('id','version','release')} for p in lock['plugins']] if plugins else [],
               'apply': apply, 'notice': 'A new vault only. Obsidian trust and an optional AI provider are configured by you.'}
    spec = importlib.util.spec_from_file_location('fieldbook_deploy_admin', ROOT / 'tools/manage-vault.py')
    admin = importlib.util.module_from_spec(spec); spec.loader.exec_module(admin)
    modules = admin.setup_module()
    seeds = json.loads((root / 'tools/starter-seeds.json').read_text())
    config = json.loads(seeds['fieldbook.json'])
    config['setups'] = setups
    config['workRole'] = work_role
    config['features']['reviews'] = 'work' in setups
    config['defaults']['area'] = setups[0] if len(setups) == 1 else ''
    resources = modules.catalog(root, admin.safe, admin.read)
    summary['availability'] = {
        'enabled': [r['path'] for r in resources if modules.enabled(r, config)],
        'inactive': [r['path'] for r in resources if not modules.enabled(r, config)]}
    if not apply:
        return summary
    # Stage beside the destination, never in the user's existing notebook.
    stage = Path(tempfile.mkdtemp(prefix='.fieldbook-deploy-', dir=destination.parent))
    try:
        for name in manifest['files']:
            out = relative(stage, name)
            out.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(relative(root, name), out)
        for name in ('fieldbook-manifest.json', 'LICENSE'):
            shutil.copyfile(relative(root, name), stage / name)
        seeds = json.loads((root / 'tools/starter-seeds.json').read_text())
        for name, content in seeds.items():
            out = relative(stage, name)
            out.parent.mkdir(parents=True, exist_ok=True)
            out.write_text(content, encoding='utf-8', newline='')
        config = json.loads((stage / 'fieldbook.json').read_text())
        config['setups'] = setups
        config['workRole'] = work_role
        config['features']['reviews'] = 'work' in setups
        config['defaults']['area'] = setups[0] if len(setups) == 1 else ''
        (stage / 'fieldbook.json').write_text(json.dumps(config, indent=2) + '\n')
        profile = json.loads((root / 'tools/starter-settings.json').read_text())
        # A sole area can be prefilled in the TaskNotes form too.
        if config['defaults']['area']:
            for field in profile['.obsidian/plugins/tasknotes/data.json']['userFields']:
                if field['key'] == 'area':
                    field['defaultValue'] = config['defaults']['area']
        if not plugins:
            profile['.obsidian/community-plugins.json'] = []
        for name, content in profile.items():
            out = relative(stage, name)
            out.parent.mkdir(parents=True, exist_ok=True)
            out.write_text(json.dumps(content, indent=2) + '\n')
        for folder in FOLDERS:
            (stage / folder).mkdir(parents=True, exist_ok=True)
        if plugins:
            for plugin in lock['plugins']:
                folder = relative(stage, '.obsidian/plugins/' + plugin['id'])
                folder.mkdir(parents=True, exist_ok=True)
                prefix = f"https://github.com/{plugin['repo']}/releases/download/{plugin['version']}/"
                for asset in plugin['assets']:
                    if asset['name'] not in {'manifest.json', 'main.js', 'styles.css'} or asset['url'] != prefix + asset['name']:
                        raise ValueError('Invalid locked plugin asset')
                    data = download(asset['url'])
                    if hashlib.sha256(data).hexdigest() != asset['sha256']:
                        raise ValueError(f"Plugin checksum mismatch: {plugin['id']}/{asset['name']}")
                    (folder / asset['name']).write_bytes(data)
                installed = json.loads((folder / 'manifest.json').read_text())
                if installed['id'] != plugin['id'] or installed['version'] != plugin['version']:
                    raise ValueError('Plugin identity/version differs from lock')
                source = plugin.get('source')
                if source:
                    expected_url = f"https://codeload.github.com/{plugin['repo']}/tar.gz/refs/tags/{plugin['version']}"
                    if source['url'] != expected_url:
                        raise ValueError('Unexpected plugin source URL')
                    data = download(source['url'])
                    if hashlib.sha256(data).hexdigest() != source['sha256']:
                        raise ValueError('Plugin source checksum mismatch')
                    (folder / 'source.tar.gz').write_bytes(data)
        # Reuse the same preflighted activation rules as configure/update.
        activation = modules.plan(stage, config, admin.safe, admin.read, admin.write)
        activation.apply()
        summary['activation'] = activation.summary()
        receipt = {**summary, 'status': 'deployed', 'source': 'verified release manifest and pristine starter seeds'}
        portable_receipt = {key: value for key, value in receipt.items() if key != 'destination'}
        (stage / '.fieldbook-starter.json').write_text(json.dumps(portable_receipt, indent=2) + '\n')
        # mkdir reserves the final name exclusively; never replace an existing directory.
        destination.mkdir()
        try:
            for child in stage.iterdir():
                shutil.move(str(child), destination / child.name)
        except Exception:
            shutil.rmtree(destination)  # Only the destination this invocation just created.
            raise
        return receipt
    finally:
        shutil.rmtree(stage, ignore_errors=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--destination', required=True)
    parser.add_argument('--setups', default='core', help='core or a comma-separated personal,work,school list')
    parser.add_argument('--work-role', default='individual-contributor', choices=['individual-contributor', 'people-manager'])
    parser.add_argument('--apply', action='store_true')
    parser.add_argument('--without-plugins', action='store_true')
    parser.add_argument('--plugin-cache', help='Offline cache: <folder>/<plugin-id>/<version>/<asset>; hashes still checked')
    args = parser.parse_args()
    setups = [] if args.setups == 'core' else args.setups.split(',')
    try:
        download = cached_download(ROOT, args.plugin_cache) if args.plugin_cache else fetch
        print(json.dumps(deploy(ROOT, args.destination, setups, args.work_role, args.apply, not args.without_plugins, download), indent=2))
    except (ValueError, OSError, KeyError) as error:
        parser.exit(1, f'Deployment stopped: {error}\n')


if __name__ == '__main__':
    main()
