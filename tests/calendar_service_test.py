"""Live calendar runtime uses bounded read-only routes; fixtures never contact accounts."""
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('calendar_service_tests',ROOT/'fieldbook_core/scripts/calendar_service.py')
service=importlib.util.module_from_spec(spec);spec.loader.exec_module(service)


class CalendarServiceTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.root=Path(self.tmp.name)
        (self.root/'fieldbook_core').mkdir()
        (self.root/'fieldbook.json').write_text(json.dumps({'features':{'google':True,'microsoft':True}}))
        for provider in service.BASES:
            self.save(provider,{'id':'a','baseUrl':service.BASES[provider],'tokenVar':provider.upper()+'_TOKEN','authMode':'access-token','credentialStore':'environment','calendarIds':['cal@example.test']})
        self.requests=[]
        self.env={'GOOGLE_TOKEN':'PRIVATE_FIXTURE_KEY','MICROSOFT_TOKEN':'PRIVATE_FIXTURE_KEY'}
    def save(self,p,item):
        (self.root/f'fieldbook_core/{p}.json').write_text(json.dumps({'instances':[item]}))
    def transport(self,responses):
        queue=iter(responses)
        def run(method,url,headers,body):
            self.requests.append((method,url,body));self.assertEqual(method,'GET');self.assertIsNone(body)
            self.assertEqual(headers['Authorization'],'Bearer PRIVATE_FIXTURE_KEY')
            value=next(queue)
            if isinstance(value,Exception):raise value
            return value if 'status' in value else {'status':200,'body':json.dumps(value).encode()}
        return run
    def read(self,p,rows,**args):
        return service.pull_calendar(self.root,{'provider':p,'instance':'a','mode':'events','start':'2026-10-01','end':'2026-10-07',**args},env=self.env,transport=self.transport(rows))
    def g(self,**extra):
        return {'id':'event1','summary':'Meeting','start':{'dateTime':'2026-10-02T10:00:00-04:00'},'end':{'dateTime':'2026-10-02T11:00:00-04:00'},**extra}
    def m(self,**extra):
        return {'id':'immutable1','subject':'Meeting','type':'singleInstance','start':{'dateTime':'2026-10-02T14:00:00','timeZone':'UTC'},'end':{'dateTime':'2026-10-02T15:00:00','timeZone':'UTC'},**extra}
    def test_google_events_and_window_are_read_only_and_no_disk_changes(self):
        before={p:p.read_bytes() for p in self.root.rglob('*') if p.is_file()}
        result=self.read('google',[{'items':[self.g()]}])
        self.assertEqual(result['items'][0]['title'],'Meeting');self.assertTrue(result['read_only'])
        self.assertEqual(result['coverage']['scope']['calendars'],['cal@example.test'])
        self.assertEqual(result['coverage']['scope']['start'],'2026-10-01')
        self.assertEqual(result['coverage']['returned'],1)
        self.assertEqual(result['read_at'],result['coverage']['read_at'])
        self.assertFalse(result['coverage']['truncated'])
        self.assertIn('cal%40example.test/events',self.requests[0][1]);self.assertIn('singleEvents=true',self.requests[0][1])
        self.assertIn('2026-10-08T00%3A00%3A00Z',self.requests[0][1])
        self.assertEqual(before,{p:p.read_bytes() for p in self.root.rglob('*') if p.is_file()})
        self.assertNotIn('PRIVATE_FIXTURE_KEY',json.dumps(result))
    def test_provider_gate_and_invalid_window_precede_any_credentials(self):
        for args in [{'provider':'google','instance':'a','mode':'events','start':'2026-10-07','end':'2026-10-01'},
                     {'provider':'google','instance':'a','mode':'events','start':'2026-01-01','end':'2026-12-31'}]:
            with self.assertRaises(service.CalendarError):service.pull_calendar(self.root,args,token_loader=lambda *x:self.fail('must not read key'))
        (self.root/'fieldbook.json').write_text('{"features":{}}')
        with self.assertRaisesRegex(service.CalendarError,'Enable'):service.pull_calendar(self.root,{'provider':'google','instance':'a'},token_loader=lambda *x:self.fail('must not read key'))
    def test_primary_alias_and_invalid_series_window_precede_credentials(self):
        denied=lambda *x:self.fail('must not read key')
        with self.assertRaisesRegex(service.CalendarError,'exact calendar ID'):
            service.pull_calendar(self.root,{'provider':'google','instance':'a','calendarIds':['primary'],'start':'2026-10-01','end':'2026-10-07'},token_loader=denied)
        with self.assertRaisesRegex(service.CalendarError,'UTC date window'):
            service.discover_series(self.root,'google','a','cal@example.test','not a date','2026-10-07',token_loader=denied)
        item=json.loads((self.root/'fieldbook_core/google.json').read_text())['instances'][0]
        item['calendarIds']=['primary'];self.save('google',item)
        with self.assertRaisesRegex(service.CalendarError,'exact Google calendar ID'):
            service.Client(self.root,'google','a',token_loader=denied)
    def test_oauth_bundle_cannot_be_sent_after_switch_to_manual_token_mode(self):
        item=json.loads((self.root/'fieldbook_core/google.json').read_text())['instances'][0]
        item['credentialStore']='keyring';self.save('google',item)
        class OldStore:
            @staticmethod
            def get(*args):return '{"access_token":"PRIVATE_ACCESS","refresh_token":"PRIVATE_REFRESH","client_secret":"PRIVATE_SECRET"}'
        with self.assertRaises(service.CalendarError) as caught:
            service.pull_calendar(self.root,{'provider':'google','instance':'a','mode':'calendars'},credential_module=OldStore,
                                  transport=lambda *x:self.fail('must not send an OAuth bundle'))
        self.assertNotIn('PRIVATE',str(caught.exception))
    def test_google_moved_occurrence_has_stable_identity_and_date_only_preserved(self):
        original={'dateTime':'2026-10-02T14:00:00Z'}
        a=self.g(recurringEventId='series',originalStartTime=original)
        b=self.g(id='newEventID',recurringEventId='series',originalStartTime={'dateTime':'2026-10-02T10:00:00-04:00'},start={'dateTime':'2026-10-03T10:00:00-04:00'})
        x=service.event('google','a','c',a);y=service.event('google','a','c',b)
        self.assertEqual(x['identity'],y['identity']);self.assertEqual(y['series_id'],'series')
        all_day=service.event('google','a','c',self.g(start={'date':'2026-10-01'},end={'date':'2026-10-02'}),'America/New_York')
        self.assertTrue(all_day['all_day']);self.assertEqual(all_day['start'],{'date':'2026-10-01'})
    def test_original_named_timezone_and_offset_have_same_occurrence_identity(self):
        named=self.g(recurringEventId='series',originalStartTime={'dateTime':'2026-10-02T10:00:00','timeZone':'America/New_York'})
        utc=self.g(id='moved-id',recurringEventId='series',originalStartTime={'dateTime':'2026-10-02T14:00:00Z'})
        self.assertEqual(service.event('google','a','c',named)['identity'],service.event('google','a','c',utc)['identity'])
    def test_original_time_missing_invalid_or_dst_ambiguous_is_refused(self):
        for original in [{}, {'date':'2026-02-30'}, {'dateTime':'invalid'}, {'dateTime':'2026-10-02T10:00:00'},
                         {'dateTime':'2026-11-01T01:30:00','timeZone':'America/New_York'},
                         {'dateTime':'2026-03-08T02:30:00','timeZone':'America/New_York'}]:
            with self.subTest(original=original),self.assertRaises(service.CalendarError):
                service.event('google','a','c',self.g(recurringEventId='series',originalStartTime=original))
        with self.assertRaises(service.CalendarError):service.event('microsoft','a','c',self.m(seriesMasterId='series'))
    def test_same_ids_in_different_accounts_or_calendars_are_distinct(self):
        items=[service.event('google',i,c,self.g())['identity'] for i,c in [('a','x'),('b','x'),('a','y')]]
        self.assertEqual(len(set(items)),3)
    def test_graph_occurrence_keeps_source_timezones_immutable_identity_and_preview_warning(self):
        output=self.read('microsoft',[{'value':[self.m(seriesMasterId='master',originalStart='2026-10-02T14:00:00Z',originalStartTimeZone='Eastern Standard Time',bodyPreview='Preview')]}])
        item=output['items'][0];self.assertEqual(item['series_id'],'master');self.assertEqual(item['start']['timeZone'],'UTC')
        self.assertEqual(item['time_zone'],'Eastern Standard Time');self.assertTrue(item['description_truncated'])
    def test_hidden_or_omitted_attendees_never_claim_full_count(self):
        attendees=[{'email':'p'+str(i)+'@example.test'} for i in range(500)]
        row=service.event('google','a','c',self.g(attendees=attendees,attendeesOmitted=True,description='x'*6000))
        self.assertEqual(len(row['attendees']),20);self.assertIsNone(row['attendee_total']);self.assertTrue(row['description_truncated'])
        graph=service.event('microsoft','a','c',self.m(hideAttendees=True,attendees=[]))
        self.assertIsNone(graph['attendee_total'])
    def test_series_mode_groups_only_occurrences_in_window(self):
        result=self.read('google',[{'items':[self.g(recurringEventId='series',originalStartTime={'date':'2026-10-02'}),self.g(id='event2',recurringEventId='series',originalStartTime={'date':'2026-10-03'}),self.g(id='single')]}],mode='series')
        self.assertEqual(len(result['items']),1);self.assertEqual(result['items'][0]['occurrences_in_preview'],2)
    def test_series_discovery_does_not_need_feature_activation(self):
        (self.root/'fieldbook.json').write_text('{"features":{}}')
        result=service.discover_series(self.root,'google','a','cal@example.test','2026-10-01','2026-10-07',env=self.env,transport=self.transport([{'items':[self.g(recurringEventId='master',originalStartTime={'dateTime':'2026-10-02T14:00:00Z'})]}]))
        self.assertEqual(result['choices'][0]['settings']['calendar_series_id'],'master')
    def test_recurring_masters_are_refused(self):
        for p,row in [('google',self.g(recurrence=['RRULE:FREQ=WEEKLY'])),('microsoft',self.m(type='seriesMaster'))]:
            with self.assertRaisesRegex(service.CalendarError,'master'):service.event(p,'a','c',row)
    def test_google_pagination_continues_through_empty_page(self):
        result=self.read('google',[{'items':[],'nextPageToken':'safe-token'},{'items':[self.g()]}])
        self.assertEqual(len(result['items']),1);self.assertIn('pageToken=safe-token',self.requests[1][1])
    def test_bad_page_discards_prior_results_and_sanitizes_remote_errors(self):
        with self.assertRaises(service.CalendarError) as caught:
            self.read('google',[{'items':[self.g()],'nextPageToken':'next'},{'status':403,'body':b'SECRET_REMOTE_BODY'}])
        self.assertNotIn('SECRET',str(caught.exception))
    def test_pagination_duplicate_occurrence_is_not_silent(self):
        with self.assertRaisesRegex(service.CalendarError,'Duplicate'):
            self.read('google',[{'items':[self.g()],'nextPageToken':'next'},{'items':[self.g()]}])
    def test_graph_cross_origin_and_changed_scope_next_links_are_refused(self):
        for link in ['https://evil.test/calendarView?$skiptoken=x','https://graph.microsoft.com/v1.0/me/calendars/cal%40example.test/calendarView?$skiptoken=x']:
            with self.assertRaisesRegex(service.CalendarError,'pagination'):
                self.read('microsoft',[{'value':[self.m()],'@odata.nextLink':link}])
    def test_graph_safe_pagination_retains_filters_and_never_uses_arbitrary_link(self):
        def transport(method,url,headers,body):
            self.assertIn('ImmutableId',headers['Prefer']);self.requests.append(url)
            data={'value':[self.m()] if len(self.requests)==1 else [self.m(id='immutable2')]}
            if len(self.requests)==1:data['@odata.nextLink']=url+'&%24skiptoken=opaque'
            return {'status':200,'body':json.dumps(data).encode()}
        result=service.pull_calendar(self.root,{'provider':'microsoft','instance':'a','mode':'events','start':'2026-10-01','end':'2026-10-02'},env=self.env,transport=transport)
        self.assertEqual(len(result['items']),2)
    def test_limit_marks_remaining_scope_as_partial(self):
        result=self.read('google',[{'items':[self.g()], 'nextPageToken':'next'}],limit=1)
        self.assertTrue(result['truncated']);self.assertEqual(len(self.requests),1)
    def test_calendar_picker_first_page_is_explicit_and_safe(self):
        result=service.discover_projects(self.root,'google','a',env=self.env,transport=self.transport([{'items':[{'id':'a@x','summary':'\x1bUnsafe'}],'nextPageToken':'next'}]))
        self.assertTrue(result['truncated']);self.assertEqual(result['choices'][0]['settings'],{'calendarIds':['a@x']})
        self.assertNotIn('\x1b',result['choices'][0]['label'])
    def test_connections_fixed_url_and_linked_config_refused(self):
        item=json.loads((self.root/'fieldbook_core/google.json').read_text())['instances'][0]
        item['baseUrl']='https://other.example';self.save('google',item)
        with self.assertRaises(service.CalendarError):service.Client(self.root,'google','a',env=self.env)
        path=self.root/'fieldbook_core/microsoft.json';other=self.root/'outside.json';path.rename(other);path.symlink_to(other)
        with self.assertRaises(service.checks.DiagnosticError):service.Client(self.root,'microsoft','a',env=self.env)
    def test_diagnostics_print_no_calendar_event_or_credential_data(self):
        result=service.check_integration(self.root,'google','a',env=self.env,transport=self.transport([{'items':[{'id':'privatecal','summary':'PRIVATE_CAL_NAME'}]},{'items':[self.g(summary='PRIVATE_TITLE')]}]))
        self.assertTrue(result['ok']);self.assertNotIn('PRIVATE',json.dumps(result))
    def test_missing_scope_diagnostics_incomplete(self):
        item=json.loads((self.root/'fieldbook_core/google.json').read_text())['instances'][0];item['calendarIds']=[];self.save('google',item)
        result=service.check_integration(self.root,'google','a',env=self.env,transport=self.transport([{'items':[]}]))
        self.assertFalse(result['ok']);self.assertTrue(any(c['status']=='skip' for c in result['checks']))
    def test_oversized_or_malformed_response_is_sanitized(self):
        for value in [{'status':302,'body':b'PRIVATE_REDIRECT'}, {'status':200,'body':b'x'*(service.checks.MAX_BODY+1)}, {'status':200,'body':b'{"items":[],"items":[]}'}]:
            with self.assertRaises(service.CalendarError) as caught:self.read('google',[value])
            self.assertNotIn('PRIVATE',str(caught.exception))


if __name__=='__main__':unittest.main()
