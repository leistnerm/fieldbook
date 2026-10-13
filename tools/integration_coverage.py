"""Non-secret coverage metadata. Offline summaries do not load keys or call APIs."""
import json
from datetime import datetime, timezone
from pathlib import Path
import importlib.util

ROOT = Path(__file__).resolve().parents[1]
CATALOG = json.loads((ROOT / 'tools/integration-coverage.json').read_text())['providers']
spec = importlib.util.spec_from_file_location('coverage_dates', ROOT / 'tools/tracker_dates.py')
dates = importlib.util.module_from_spec(spec);spec.loader.exec_module(dates)

def selection(provider, item):
    keys = {'jira':('filter',), 'agility':('where','memberId'), 'github':('repositories','labels'),
            'azure':('project','filter'), 'canvas':('courseIds',), 'google':('calendarIds',), 'microsoft':('calendarIds',)}
    return {k:item[k] for k in keys.get(provider, ()) if item.get(k)}

def summary(provider, item, *, scope=None, result=None, limits=None):
    capability = CATALOG[provider]
    mapping = dates.date_fields(provider, item) if provider in ('jira','agility','azure') else {}
    report = {'schema_version':1, 'provider':provider, 'read_only':True, 'read_at':None,
              'scope':selection(provider,item) if scope is None else scope,
              'supported':capability['objects'], 'date_types':list(mapping) if provider in ('jira','agility','azure') else capability['date_types'],
              'date_fields':mapping, 'excluded':capability['excluded'], 'limits':limits or {},
              'freshness':'Configuration only; no read has been performed.', 'completeness':'Untested; use Test saved connections for a bounded sample.'}
    if result is not None:
        report.update(read_at=datetime.now(timezone.utc).isoformat(), returned=len(result.get('items',[])), truncated=bool(result.get('truncated')),
                      freshness='Snapshot at read_at; no background refresh.',
                      completeness='Partial: narrow the window or selection.' if result.get('truncated') else 'Selected scope/window only; absence is not deletion or completion evidence.')
    return report

def offline(root, validator):
    root = Path(root)
    config = json.loads(validator.admin.read(validator.admin.safe(root,'fieldbook.json')))
    results = []
    for provider in validator.PROVIDERS:
        entry = {'provider':provider, 'enabled':config.get('features',{}).get(provider,False), 'connections':[]}
        try:
            path = validator.admin.safe(root,'fieldbook_core/'+provider+'.json')
            if not path.is_file() or path.stat().st_size > 65536:raise ValueError()
            data = json.loads(validator.admin.read(path))
            if not isinstance(data,dict) or not isinstance(data.get('instances'),list):raise ValueError()
            seen = set()
            for item in data['instances']:
                validator.check_instance(provider,item,allow_missing_client=True)
                if item['id'] in seen:raise ValueError()
                seen.add(item['id'])
                entry['connections'].append({'instance':item['id'], 'configured': 'REPLACE' not in item['baseUrl'].upper(), **summary(provider,item)})
        except (ValueError, OSError, TypeError, KeyError):
            entry['connections'] = []
            entry['error'] = 'Configuration needs attention; run --check. No keys or remote data were read.'
        results.append(entry)
    return {'schema_version':1, 'mode':'offline_configuration', 'read_only':True, 'integrations':results,
            'local_ics':summary('ics',{}), 'notice':'Lists adapter capabilities and saved selections, not successful reads. No account details, keys or remote content are cached.'}
