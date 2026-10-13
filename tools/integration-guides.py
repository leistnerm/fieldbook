"""Offline, source-maintained credential instructions; never creates credentials."""
import json
from pathlib import Path
import unicodedata
from urllib.parse import urlsplit

GUIDES = Path(__file__).with_name('integration-guides.json')
LINK_HOSTS = {
    'support.atlassian.com', 'id.atlassian.com', 'developer.atlassian.com', 'confluence.atlassian.com',
    'docs.digital.ai', 'docs.github.com', 'github.com', 'learn.microsoft.com', 'entra.microsoft.com',
    'developerdocs.instructure.com', 'community.instructure.com', 'developers.google.com', 'console.cloud.google.com',
}


def plain(value, limit=3000):
    return isinstance(value,str) and 0 < len(value) <= limit and not any(unicodedata.category(c).startswith('C') for c in value)


def safe_link(value):
    if not plain(value,2048) or '\\' in value or any(c.isspace() for c in value):return False
    try:
        parts=urlsplit(value)
        return (parts.scheme == 'https' and parts.hostname in LINK_HOSTS and parts.netloc == parts.hostname
                and not parts.username and not parts.password)
    except ValueError:return False


def load(providers, path=GUIDES):
    """Fail closed if a registered provider lacks a maintained guide or links drift."""
    try:
        raw=Path(path).read_bytes()
        if len(raw)>200000:raise ValueError()
        def pairs(values):
            result={}
            for key,value in values:
                if key in result:raise ValueError()
                result[key]=value
            return result
        data=json.loads(raw,object_pairs_hook=pairs)
        if data.get('schemaVersion') != 1 or not plain(data.get('checked'),32):raise ValueError()
        guides=data['providers']
        if set(guides)!=set(providers):raise ValueError()
        for provider,guide in guides.items():
            if not plain(guide.get('title'),180) or not isinstance(guide.get('variants'),list) or not 1<=len(guide['variants'])<=5:raise ValueError()
            for variant in guide['variants']:
                if not plain(variant.get('title'),180) or not isinstance(variant.get('steps'),list) or not 2<=len(variant['steps'])<=12:raise ValueError()
                for step in variant['steps']:
                    if not plain(step.get('title'),180) or not plain(step.get('text')):raise ValueError()
                    links=step.get('links',[])
                    if not isinstance(links,list) or len(links)>5:raise ValueError()
                    for link in links:
                        if not plain(link.get('label'),180) or not safe_link(link.get('url')):raise ValueError()
        return data
    except (OSError,ValueError,KeyError,TypeError,AttributeError):
        raise ValueError('Credential guides are missing or invalid. Restore the verified kit guides before continuing; no link was opened.') from None
