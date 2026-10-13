"""Validate explicit remote date mappings; shared by configuration and diagnostics."""
import re
from datetime import date

DATE_TYPES = ('due', 'completed', 'start', 'target', 'review', 'available_from', 'closes_at')

def valid_date(value):
    if not isinstance(value,str) or not re.fullmatch(r'\d{4}-\d{2}-\d{2}(?:T\d{2}:\d{2}:\d{2}(?:\.\d{1,9})?(?:Z|[+-]\d{2}:?\d{2})?)?',value):return False
    try:date.fromisoformat(value[:10])
    except ValueError:return False
    if len(value) == 10:return True
    m = re.search(r'T(\d{2}):(\d{2}):(\d{2})(?:\.\d+)?(?:Z|([+-])(\d{2}):?(\d{2}))?$',value)
    return bool(m and int(m[1]) < 24 and int(m[2]) < 60 and int(m[3]) < 60 and (not m[4] or (int(m[5]) < 24 and int(m[6]) < 60)))

def date_fields(provider, instance):
    configured = instance.get('dateFields', {})
    if not isinstance(configured, dict):raise ValueError('dateFields must be a JSON object')
    defaults = ({'due':'duedate', 'completed':'resolutiondate'} if provider == 'jira' else
                {'due':instance.get('dueField', ''), 'completed':instance.get('completionField', '')} if provider == 'azure' else {})
    mapping = {**defaults, **configured}
    pattern = r'[A-Za-z][A-Za-z0-9_]{0,127}' if provider == 'jira' else r'[A-Za-z][A-Za-z0-9_]*(?:\.[A-Za-z][A-Za-z0-9_]*)*'
    for kind, field in mapping.items():
        if kind not in DATE_TYPES or not isinstance(field, str) or len(field) > 128 or (field and not re.fullmatch(pattern, field)):
            raise ValueError('Use supported date meanings and exact field references in dateFields')
    result = {k:v for k,v in mapping.items() if v}
    if len(set(result.values())) != len(result):raise ValueError('Map a source date field to only one meaning')
    return result
