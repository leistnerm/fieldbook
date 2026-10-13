#!/usr/bin/env python3
"""Private credential-store bridge. No OpenCode tool exposes this module's output."""
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import sys
from urllib.parse import urlsplit

PROVIDERS = {'jira', 'agility', 'github', 'azure', 'canvas', 'google', 'microsoft'}
ROOT = Path(__file__).resolve().parents[2]


class CredentialError(ValueError):
    pass


def location(root, provider, instance):
    if provider not in PROVIDERS or not isinstance(instance, dict):
        raise CredentialError('Invalid credential reference')
    identity = instance.get('id', '')
    if not isinstance(identity, str) or not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_-]{0,63}', identity):
        raise CredentialError('Invalid instance ID')
    url = instance.get('baseUrl', '')
    if not isinstance(url, str):
        raise CredentialError('Invalid integration URL')
    try:
        parts = urlsplit(url)
        if parts.port == 0:raise ValueError()
    except ValueError:
        raise CredentialError('Credentials require a clean HTTPS integration URL') from None
    if (parts.scheme != 'https' or not parts.hostname or parts.username or parts.password
            or parts.query or parts.fragment or '\\' in url or any(c.isspace() or ord(c) < 32 or ord(c) == 127 for c in url)):
        raise CredentialError('Credentials require a clean HTTPS integration URL')
    # Reconfiguring the destination or moving/copying a vault requires a fresh key.
    # Never send an old credential to a newly selected server implicitly.
    canonical = parts.geturl().rstrip('/')
    key = '\n'.join((str(Path(root).resolve()), provider, identity, canonical))
    return 'Fieldbook:' + hashlib.sha256(key.encode()).hexdigest(), provider + ':' + identity


def secure_backend():
    try:
        if sys.platform == 'darwin':
            from keyring.backends.macOS import Keyring
        elif sys.platform == 'win32':
            from keyring.backends.Windows import WinVaultKeyring as Keyring
        elif sys.platform.startswith('linux'):
            from keyring.backends.SecretService import Keyring
        else:
            raise CredentialError('Use environment variables on this platform')
        backend = Keyring()
        if backend.priority <= 0:
            raise CredentialError('OS credential store is unavailable')
        return backend
    except CredentialError:
        raise
    except Exception:
        raise CredentialError('OS credential store unavailable. Install fieldbook_core/requirements-credentials.txt in the vault Python environment, unlock the store, or choose environment variables.') from None


def token_value(token):
    if not isinstance(token, str) or not token or len(token) > 16384 or any(ord(c) < 32 or ord(c) == 127 for c in token):
        raise CredentialError('Enter a non-empty API key without control characters (maximum 16 KiB)')
    return token


def store(root, provider, instance, token, backend=None):
    service, account = location(root, provider, instance)
    token_value(token)
    selected = backend if backend is not None else secure_backend()
    try:
        selected.set_password(service, account, token)
    except Exception:
        raise CredentialError('Could not save the credential in the OS store; no plaintext fallback was used') from None


def get(root, provider, instance, backend=None):
    service, account = location(root, provider, instance)
    selected = backend if backend is not None else secure_backend()
    try:
        token = selected.get_password(service, account)
    except Exception:
        raise CredentialError('Could not read the OS credential store; unlock it or configure an environment variable') from None
    if token is None:
        raise CredentialError('No saved credential for this vault, instance and URL. Run tools/configure.py to save one.')
    return token_value(token)


def status(root, provider, instance, backend=None):
    """Return presence only; never expose the key to status/preview output."""
    try:
        get(root, provider, instance, backend)
        return {'available': True, 'source': 'keyring'}
    except CredentialError:
        return {'available': False, 'source': 'keyring'}


def configured_instance(root, provider, reference):
    """Match the caller's destination before consulting the OS credential store."""
    if not isinstance(reference, dict) or set(reference) != {'id', 'baseUrl', 'tokenVar'}:
        raise CredentialError('Invalid credential reference')
    location(root, provider, reference)
    if not isinstance(reference['tokenVar'], str) or not re.fullmatch(provider.upper() + r'_[A-Z0-9_]+', reference['tokenVar']):
        raise CredentialError('Invalid token variable reference')
    folder = root / 'fieldbook_core';file = folder / (provider + '.json')
    for path in (folder, file):
        info = path.lstat()
        if path.is_symlink() or getattr(info, 'st_file_attributes', 0) & 0x400 or path.is_file() and info.st_nlink != 1:
            raise CredentialError('Linked integration configuration is not supported')
        if path == file and not stat.S_ISREG(info.st_mode):raise CredentialError('Invalid integration configuration')
    fd = os.open(file, os.O_RDONLY | getattr(os, 'O_NOFOLLOW', 0))
    with os.fdopen(fd, 'rb') as stream:
        info = os.fstat(stream.fileno())
        if not stat.S_ISREG(info.st_mode) or info.st_size > 65536 or info.st_nlink != 1:raise CredentialError('Invalid integration configuration')
        raw = stream.read(65537)
    if len(raw) > 65536:raise CredentialError('Invalid integration configuration')
    data = json.loads(raw.decode('utf-8-sig'))
    instances = [i for i in data.get('instances', []) if isinstance(i, dict) and i.get('id') == reference['id']]
    if (len(instances) != 1 or instances[0].get('credentialStore') != 'keyring'
            or any(instances[0].get(key) != value for key, value in reference.items())):
        raise CredentialError('Integration configuration changed; retry the read before consulting saved credentials')
    return instances[0]


def main():
    try:
        request = json.loads(sys.stdin.read(8193))
        if not isinstance(request, dict) or set(request) != {'provider', 'instance'} or request['provider'] not in PROVIDERS:
            raise CredentialError('Invalid credential request')
        provider = request['provider']
        instance = configured_instance(ROOT, provider, request['instance'])
        # Only the private JS transport consumes this response; not a model tool.
        sys.stdout.write(json.dumps({'token': get(ROOT, provider, instance)}))
    except Exception:
        sys.stdout.write(json.dumps({'error': 'Credential lookup failed. Run tools/configure.py with the vault Python environment and check its credential-store setup.'}))
        raise SystemExit(1)


if __name__ == '__main__':
    main()
