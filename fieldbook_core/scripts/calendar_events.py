#!/usr/bin/env python3
"""Bounded, read-only iCalendar event previews. No file, network or write access.

Supported RFC 5545 subset: VCALENDAR/VEVENT, UTF-8 folding, escaped TEXT,
quoted parameters, DATE and DATE-TIME (UTC, floating, IANA TZID), duration,
recurrence metadata and detached occurrences. No recurrence expansion, custom
VTIMEZONE execution, alarms, attachments, or embedded content processing.
"""
import datetime as dt
import hashlib
import json
import re
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

MAX_BYTES = 1024 * 1024
MAX_EVENTS = 100
MAX_ATTENDEES = 20


class CalendarError(ValueError):
    pass


def split_quoted(text, separator):
    result=[];start=0;quoted=False
    for index,char in enumerate(text):
        if char=='"':quoted=not quoted
        elif char==separator and not quoted:
            result.append(text[start:index]);start=index+1
    if quoted:raise CalendarError('Unclosed quoted iCalendar parameter')
    result.append(text[start:]);return result


def property_line(line):
    quoted=False;separator=None
    for index,char in enumerate(line):
        if char=='"':quoted=not quoted
        elif char==':' and not quoted:separator=index;break
    if separator is None:raise CalendarError('iCalendar property has no value separator')
    header,body=line[:separator],line[separator+1:]
    head=split_quoted(header,';');name=head[0].upper()
    if not re.fullmatch(r'[A-Z0-9-]+',name):raise CalendarError('Invalid iCalendar property name')
    params={}
    for field in head[1:]:
        if '=' not in field:raise CalendarError('Malformed iCalendar parameter')
        key,value=field.split('=',1);key=key.upper()
        if key in params:raise CalendarError('Duplicate iCalendar parameter: '+key)
        if not re.fullmatch(r'[A-Z0-9-]+',key):raise CalendarError('Invalid iCalendar parameter name')
        if value.startswith('"'):
            if not value.endswith('"'):raise CalendarError('Unclosed quoted parameter')
            value=value[1:-1]
        elif '"' in value:raise CalendarError('Invalid quoted parameter')
        # RFC 6868 parameter encoding; this is metadata, never executable text.
        value=re.sub(r'\^([nN^\'])',lambda m:'\n' if m[1].lower()=='n' else '"' if m[1]=="'" else '^',value)
        params[key]=value
    return name,params,body


def text_value(value):
    def escaped(match):
        char=match[1]
        if char in ('n','N'):return '\n'
        if char in ('\\',';',','):return char
        raise CalendarError('Unsupported iCalendar TEXT escape: \\'+char)
    if value.endswith('\\') and len(re.search(r'\\+$',value)[0])%2:raise CalendarError('Incomplete TEXT escape')
    return re.sub(r'\\(.)',escaped,value)


def temporal(params, value, label):
    kind=params.get('VALUE','DATE-TIME').upper();zone=params.get('TZID')
    if kind=='DATE':
        if zone or not re.fullmatch(r'\d{8}',value):raise CalendarError(label+' DATE must be YYYYMMDD without TZID')
        try:return dt.datetime.strptime(value,'%Y%m%d').date(),'date'
        except ValueError as error:raise CalendarError('Invalid '+label+' date') from error
    if kind!='DATE-TIME':raise CalendarError('Unsupported '+label+' value type: '+kind)
    if not re.fullmatch(r'\d{8}T\d{6}Z?',value):raise CalendarError(label+' must use YYYYMMDDTHHMMSS with optional Z')
    try:moment=dt.datetime.strptime(value.removesuffix('Z'),'%Y%m%dT%H%M%S')
    except ValueError as error:raise CalendarError('Invalid '+label+' date/time (leap seconds unsupported)') from error
    if value.endswith('Z'):
        if zone:raise CalendarError(label+' cannot combine UTC Z and TZID')
        return moment.replace(tzinfo=dt.timezone.utc),'UTC'
    if not zone:return moment,'floating'
    if zone.startswith('/') or '..' in zone.split('/') or '\\' in zone:
        raise CalendarError('Unsupported timezone identifier: '+zone)
    try:tz=ZoneInfo(zone)
    except (ZoneInfoNotFoundError,ValueError) as error:
        raise CalendarError('Unsupported or unavailable timezone '+zone+'; export this event in UTC or with an installed IANA timezone') from error
    first=moment.replace(tzinfo=tz,fold=0);second=moment.replace(tzinfo=tz,fold=1)
    valid=[v for v in (first,second) if v.astimezone(dt.timezone.utc).astimezone(tz).replace(tzinfo=None)==moment]
    if not valid:raise CalendarError(label+' falls in a nonexistent local DST time; export the occurrence in UTC')
    if len(valid)==2 and first.utcoffset()!=second.utcoffset():
        raise CalendarError(label+' is ambiguous at a DST transition; export the occurrence in UTC')
    return valid[0],zone


def iso(value):
    return value.isoformat().replace('+00:00','Z') if value is not None else None


def recurrence_rule(value, start):
    parts={}
    for token in value.split(';'):
        if '=' not in token:raise CalendarError('Malformed RRULE')
        key,item=token.split('=',1);key=key.upper();item=item.upper()
        if key in parts or not item:raise CalendarError('Duplicate or empty RRULE part')
        parts[key]=item
    if parts.get('FREQ') not in {'SECONDLY','MINUTELY','HOURLY','DAILY','WEEKLY','MONTHLY','YEARLY'}:
        raise CalendarError('RRULE requires a supported FREQ')
    allowed={'FREQ','UNTIL','COUNT','INTERVAL','BYSECOND','BYMINUTE','BYHOUR','BYDAY','BYMONTHDAY','BYYEARDAY','BYWEEKNO','BYMONTH','BYSETPOS','WKST'}
    if set(parts)-allowed:raise CalendarError('Unsupported RRULE parts: '+', '.join(sorted(set(parts)-allowed)))
    if 'UNTIL' in parts and 'COUNT' in parts:raise CalendarError('RRULE cannot contain both UNTIL and COUNT')
    for key in ('COUNT','INTERVAL'):
        if key in parts and (not parts[key].isdigit() or len(parts[key])>10 or not 1<=int(parts[key])<=2147483647):raise CalendarError('Invalid RRULE '+key)
    if 'UNTIL' in parts:
        value=parts['UNTIL'];kind='DATE' if re.fullmatch(r'\d{8}',value) else 'DATE-TIME'
        until,_=temporal({'VALUE':kind},value,'RRULE UNTIL')
        if isinstance(start,dt.datetime) != isinstance(until,dt.datetime):raise CalendarError('RRULE UNTIL type must match DTSTART')
        if isinstance(start,dt.datetime) and bool(start.tzinfo)!=bool(until.tzinfo):raise CalendarError('Zoned DTSTART requires UTC RRULE UNTIL; floating DTSTART requires floating UNTIL')
    ranges={'BYSECOND':(0,59),'BYMINUTE':(0,59),'BYHOUR':(0,23),'BYMONTH':(1,12),
            'BYMONTHDAY':(-31,31),'BYYEARDAY':(-366,366),'BYWEEKNO':(-53,53),'BYSETPOS':(-366,366)}
    for key,(minimum,maximum) in ranges.items():
        if key not in parts:continue
        for item in parts[key].split(','):
            if not re.fullmatch(r'[+-]?\d{1,4}',item) or not minimum<=int(item)<=maximum or (minimum<0 and int(item)==0):
                raise CalendarError('Invalid RRULE '+key)
    days={'MO','TU','WE','TH','FR','SA','SU'}
    if 'WKST' in parts and parts['WKST'] not in days:raise CalendarError('Invalid RRULE WKST')
    if 'BYDAY' in parts:
        for day in parts['BYDAY'].split(','):
            match=re.fullmatch(r'([+-]?\d{1,2})?(MO|TU|WE|TH|FR|SA|SU)',day)
            if not match or match[1] and (int(match[1])==0 or abs(int(match[1]))>53):raise CalendarError('Invalid RRULE BYDAY')
            if match[1] and parts['FREQ'] not in ('MONTHLY','YEARLY'):raise CalendarError('Ordinal BYDAY is only supported for monthly/yearly rules')
    if 'BYWEEKNO' in parts and parts['FREQ']!='YEARLY':raise CalendarError('BYWEEKNO requires YEARLY frequency')
    if 'BYYEARDAY' in parts and parts['FREQ'] in ('DAILY','WEEKLY','MONTHLY'):raise CalendarError('Unsupported BYYEARDAY frequency combination')
    if 'BYMONTHDAY' in parts and parts['FREQ']=='WEEKLY':raise CalendarError('BYMONTHDAY cannot be used with WEEKLY frequency')
    if 'BYSETPOS' in parts and not any(key.startswith('BY') and key!='BYSETPOS' for key in parts):raise CalendarError('BYSETPOS requires another BY rule part')
    return ';'.join(key+'='+item for key,item in parts.items())


def contact(params, value):
    if not value.lower().startswith('mailto:'):return {'email':'','name':params.get('CN','')[:512],'address':value[:512]}
    address=value[7:]
    if any(char in address for char in '\r\n,;') or len(address)>512:raise CalendarError('Invalid calendar attendee address')
    return {'email':address,'name':params.get('CN','')[:512],
            'role':params.get('ROLE',''), 'participation':params.get('PARTSTAT',''),
            'type':params.get('CUTYPE','INDIVIDUAL')}


def event_preview(properties, method):
    data={}
    for name,params,value in properties:data.setdefault(name,[]).append((params,value))
    def one(name, default=None):
        items=data.get(name,[])
        if len(items)>1:raise CalendarError('Duplicate VEVENT '+name)
        return items[0] if items else default
    uid_item=one('UID')
    if not uid_item or not uid_item[1].strip():raise CalendarError('VEVENT requires UID for stable identity')
    uid=text_value(uid_item[1])
    if len(uid)>4096:raise CalendarError('Calendar UID is too long')
    status=one('STATUS',({},''))[1].upper()
    if status not in ('','TENTATIVE','CONFIRMED','CANCELLED'):raise CalendarError('Unsupported VEVENT STATUS: '+status)
    cancelled=status=='CANCELLED' or method=='CANCEL'
    start_item=one('DTSTART');start=None;zone=None
    warnings=[]
    if start_item:start,zone=temporal(*start_item,'DTSTART')
    elif not cancelled:raise CalendarError('VEVENT requires DTSTART; provide a concrete event date/time')
    else:warnings.append('Cancellation has no start time; match its stored identity before updating a note.')
    end_item=one('DTEND');duration_item=one('DURATION');end=None
    if end_item and duration_item:raise CalendarError('VEVENT cannot contain both DTEND and DURATION')
    if end_item:
        end,end_zone=temporal(*end_item,'DTEND')
        if start is None:raise CalendarError('DTEND requires DTSTART')
        if isinstance(start,dt.datetime)!=isinstance(end,dt.datetime):raise CalendarError('DTEND must match DTSTART date/time type')
        if isinstance(start,dt.datetime) and bool(start.tzinfo)!=bool(end.tzinfo):raise CalendarError('DTEND and DTSTART must both be zoned or floating')
        if end<=start:raise CalendarError('DTEND must be after DTSTART')
    elif duration_item:
        if start is None:raise CalendarError('DURATION requires DTSTART')
        duration=duration_item[1]
        match=re.fullmatch(r'\+?P(?:(\d+)W|(?:(\d+)D)?(?:T(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?)?)',duration)
        if not match or not any(match.groups()):raise CalendarError('Unsupported or malformed DURATION')
        if any(x and len(x)>9 for x in match.groups()):raise CalendarError('DURATION is out of range')
        weeks,days,hours,minutes,seconds=(int(x or 0) for x in match.groups())
        if not isinstance(start,dt.datetime) and (hours or minutes or seconds):raise CalendarError('All-day DURATION must use whole days or weeks')
        try:
            delta=dt.timedelta(weeks=weeks,days=days,hours=hours,minutes=minutes,seconds=seconds)
            if delta<=dt.timedelta(0):raise CalendarError('DURATION must be positive')
            if isinstance(start,dt.datetime) and start.tzinfo and (weeks or days) and start.utcoffset()!=(start+delta).utcoffset():
                raise CalendarError('Day/week DURATION across a DST change is unsupported; export an explicit DTEND')
            # Hour/minute/second durations use absolute time across DST boundaries.
            end=(start.astimezone(dt.timezone.utc)+delta).astimezone(start.tzinfo) if isinstance(start,dt.datetime) and start.tzinfo else start+delta
        except OverflowError as error:raise CalendarError('DURATION is out of range') from error
    elif start is not None:
        try:end=start if isinstance(start,dt.datetime) else start+dt.timedelta(days=1)
        except OverflowError as error:raise CalendarError('All-day end date is out of range') from error
    rid_item=one('RECURRENCE-ID');rid='';rid_original='';rid_zone=None
    if rid_item:
        if 'RANGE' in rid_item[0]:raise CalendarError('RECURRENCE-ID RANGE is unsupported; export a single concrete occurrence')
        occurrence,rid_zone=temporal(*rid_item,'RECURRENCE-ID');rid_original=iso(occurrence)
        if start is not None and isinstance(start,dt.datetime)!=isinstance(occurrence,dt.datetime):raise CalendarError('RECURRENCE-ID type must match DTSTART')
        if isinstance(start,dt.datetime) and isinstance(occurrence,dt.datetime) and bool(start.tzinfo)!=bool(occurrence.tzinfo):raise CalendarError('RECURRENCE-ID and DTSTART must both be zoned or floating')
        if isinstance(occurrence,dt.datetime) and occurrence.tzinfo:occurrence=occurrence.astimezone(dt.timezone.utc)
        rid=iso(occurrence)
    rule_item=one('RRULE');rule=recurrence_rule(rule_item[1],start) if rule_item else ''
    if 'EXRULE' in data:raise CalendarError('EXRULE is unsupported; export a single concrete occurrence')
    for key in ('RDATE','EXDATE'):
        for params,value in data.get(key,[]):
            if params.get('VALUE')=='PERIOD':raise CalendarError(key+' PERIOD is unsupported; export a single occurrence')
            for item in value.split(','):
                occurrence,_=temporal(params,item,key)
                if start is not None and isinstance(start,dt.datetime)!=isinstance(occurrence,dt.datetime):raise CalendarError(key+' type must match DTSTART')
                if isinstance(start,dt.datetime) and bool(start.tzinfo)!=bool(occurrence.tzinfo):raise CalendarError(key+' and DTSTART must both be zoned or floating')
    recurring=bool(rule or rid or 'RDATE' in data or 'EXDATE' in data)
    needs_occurrence=recurring and not bool(rid)
    if recurring:warnings.append('Recurrence metadata is not expanded or evaluated; select/export one concrete occurrence.')
    if zone=='floating':warnings.append('Floating local time has no timezone; confirm the intended timezone before saving.')
    if needs_occurrence:warnings.append('Recurring master: confirm a concrete occurrence and original occurrence start before creating a meeting note.')
    attendees=data.get('ATTENDEE',[])
    description=text_value(one('DESCRIPTION',({},''))[1])
    url=one('URL',({},''))[1]
    if len(url)>2048:raise CalendarError('Event URL exceeds preview limit')
    title=text_value(one('SUMMARY',({},''))[1]);location=text_value(one('LOCATION',({},''))[1])
    if len(title)>2048 or len(location)>2048:raise CalendarError('Event title/location exceeds preview limit')
    organizer=one('ORGANIZER')
    return {'uid':uid,'recurrence_id':rid,'identity':hashlib.sha256(json.dumps([uid,rid],ensure_ascii=False,separators=(',',':')).encode()).hexdigest(),
            'start':iso(start),'end':iso(end),'time_zone':zone,'all_day':start is not None and not isinstance(start,dt.datetime),
            'title':title,'location':location,'description':description[:4096],'description_truncated':len(description)>4096,'url':url,
            'recurrence_original':rid_original,'recurrence_time_zone':rid_zone,'organizer':contact(*organizer) if organizer else None,
            'attendees':[contact(*item) for item in attendees[:MAX_ATTENDEES]],
            'attendee_total':len(attendees),'attendees_truncated':len(attendees)>MAX_ATTENDEES,
            'status':'cancelled' if cancelled else status.lower() or 'unspecified','cancelled':cancelled,
            'recurring':recurring,'requires_occurrence':needs_occurrence,'recurrence_rule':rule,'warnings':warnings}


def parse_calendar(data, source=''):
    if isinstance(data,str):data=data.encode('utf-8')
    if not isinstance(data,bytes) or len(data)>MAX_BYTES or b'\x00' in data:raise CalendarError('Calendar must be UTF-8 text of at most 1 MiB')
    if not isinstance(source,str) or len(source)>2048:raise CalendarError('Invalid calendar source label')
    # Unfold bytes before decoding, since UTF-8 sequences may themselves be folded.
    unfolded=re.sub(br'\r?\n[ \t]',b'',data)
    try:text=unfolded.decode('utf-8-sig')
    except UnicodeDecodeError as error:raise CalendarError('Calendar must be UTF-8') from error
    if '\r' in text.replace('\r\n',''):raise CalendarError('Malformed calendar line endings')
    stack=[];events=[];current=None;calendar={};warnings=[];closed=False
    for line in text.splitlines():
        if not line:continue
        if len(line)>65536:raise CalendarError('Unfolded calendar line exceeds 64 KiB')
        name,params,value=property_line(line)
        if name in ('BEGIN','END') and (params or not re.fullmatch(r'[A-Za-z0-9-]+',value)):
            raise CalendarError('Malformed iCalendar component declaration')
        if name=='BEGIN':
            value=value.upper()
            if not stack:
                if value!='VCALENDAR' or closed:raise CalendarError('Exactly one VCALENDAR is required')
            elif value=='VCALENDAR':raise CalendarError('Nested VCALENDAR is unsupported')
            elif value=='VEVENT':
                if stack!=['VCALENDAR']:raise CalendarError('VEVENT must be inside VCALENDAR')
                if len(events)>=MAX_EVENTS:raise CalendarError('Calendar exceeds 100 events; export a smaller range')
                current=[]
            elif value=='VTIMEZONE':warnings.append('VTIMEZONE definitions are not interpreted; installed IANA timezone data is used.')
            elif len(stack)==1:warnings.append('Ignored component: '+value)
            stack.append(value)
            if len(stack)>8:raise CalendarError('Calendar component nesting is too deep')
        elif name=='END':
            if not stack or stack[-1]!=value.upper():raise CalendarError('Mismatched iCalendar component ending')
            if stack[-1]=='VEVENT':events.append(current);current=None
            stack.pop()
            if not stack:closed=True
        elif not stack:raise CalendarError('Calendar property outside VCALENDAR')
        elif stack==['VCALENDAR']:
            if name in ('VERSION','METHOD'):
                if name in calendar:raise CalendarError('Duplicate calendar '+name)
                calendar[name]=value.upper()
        elif stack==['VCALENDAR','VEVENT']:current.append((name,params,value))
    if stack or not closed or calendar.get('VERSION')!='2.0':raise CalendarError('A complete VERSION:2.0 VCALENDAR is required')
    previews=[event_preview(event,calendar.get('METHOD','')) for event in events]
    identities=[event['identity'] for event in previews]
    if len(identities)!=len(set(identities)):warnings.append('Duplicate UID/occurrence identities in export; choose the intended revision before saving.')
    return {'source':source,'events':previews,'total_events':len(previews),'warnings':sorted(set(warnings)), 'read_only':True}
