"""Read-only calendar previews: identities, bounded rosters and unsupported cases."""
import importlib.util
from pathlib import Path
import unittest

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('calendar_events',ROOT/'fieldbook_core/scripts/calendar_events.py')
calendar=importlib.util.module_from_spec(spec);spec.loader.exec_module(calendar)


def event(lines, uid='event-1'):
    return 'BEGIN:VEVENT\r\nUID:'+uid+'\r\n'+lines+'\r\nEND:VEVENT\r\n'


def export(events, extra=''):
    return 'BEGIN:VCALENDAR\r\nVERSION:2.0\r\n'+extra+events+'END:VCALENDAR\r\n'


class CalendarTests(unittest.TestCase):
    def parse(self, lines):
        return calendar.parse_calendar(export(event(lines)),'Attachments/event.ics')['events'][0]

    def test_utc_event_quoted_parameters_and_plain_text_escaping(self):
        result=self.parse('DTSTART:20261020T140000Z\r\nDTEND:20261020T143000Z\r\n'
            'SUMMARY:Review\\, planning\\; say "hello\r\nLOCATION:Room\\, 1\r\n'
            'DESCRIPTION:Agenda\\nTwo items\\; literal \\\\ slash\r\nURL:https://example.test/join?a=b:c\r\n'
            'ORGANIZER;CN="Smith, Alex":mailto:alex@example.test\r\n'
            'ATTENDEE;CN="Doe; Jo: Team";PARTSTAT=ACCEPTED:mailto:jo@example.test')
        self.assertEqual(result['title'],'Review, planning; say "hello')
        self.assertEqual(result['description'],'Agenda\nTwo items; literal \\ slash')
        self.assertEqual(result['start'],'2026-10-20T14:00:00Z')
        self.assertEqual(result['time_zone'],'UTC')
        self.assertEqual(result['organizer']['name'],'Smith, Alex')
        self.assertEqual(result['attendees'][0]['name'],'Doe; Jo: Team')
        self.assertEqual(result['url'],'https://example.test/join?a=b:c')
        self.assertFalse(result['recurring'])

    def test_utf8_octet_folding_and_parameter_caret_encoding(self):
        content=export(event('DTSTART:20261020T140000Z\r\nSUMMARY:Café\r\nATTENDEE;CN="Alex^n^\'QA^\'":mailto:a@example.test'))
        data=content.encode().replace('é'.encode(),b'\xc3\r\n \xa9')
        result=calendar.parse_calendar(data)['events'][0]
        self.assertEqual(result['title'],'Café')
        self.assertEqual(result['attendees'][0]['name'],'Alex\n"QA"')

    def test_all_day_dates_have_exclusive_end_and_no_timezone(self):
        result=self.parse('DTSTART;VALUE=DATE:20261020\r\nSUMMARY:Away')
        self.assertTrue(result['all_day']);self.assertEqual(result['end'],'2026-10-21')
        self.assertEqual(result['time_zone'],'date')
        explicit=self.parse('DTSTART;VALUE=DATE:20261020\r\nDTEND;VALUE=DATE:20261023')
        self.assertEqual(explicit['end'],'2026-10-23')

    def test_iana_timezone_and_duration(self):
        result=self.parse('DTSTART;TZID="America/New_York":20261020T100000\r\nDURATION:PT1H30M')
        self.assertEqual(result['start'],'2026-10-20T10:00:00-04:00')
        self.assertEqual(result['end'],'2026-10-20T11:30:00-04:00')
        self.assertEqual(result['time_zone'],'America/New_York')
        floating=self.parse('DTSTART:20261020T100000')
        self.assertEqual(floating['time_zone'],'floating');self.assertTrue(floating['warnings'])

    def test_master_and_detached_occurrence_are_not_expanded_and_have_distinct_ids(self):
        master=self.parse('DTSTART;TZID=America/New_York:20261020T100000\r\nRRULE:FREQ=WEEKLY;COUNT=5;BYDAY=TU')
        self.assertTrue(master['requires_occurrence']);self.assertEqual(master['recurrence_id'],'')
        moved=self.parse('DTSTART;TZID=America/New_York:20261028T110000\r\nRECURRENCE-ID;TZID=America/New_York:20261027T100000')
        utc=self.parse('DTSTART:20261028T150000Z\r\nRECURRENCE-ID:20261027T140000Z')
        self.assertEqual(moved['recurrence_id'],'2026-10-27T14:00:00Z')
        self.assertEqual(moved['recurrence_original'],'2026-10-27T10:00:00-04:00')
        self.assertEqual(moved['identity'],utc['identity'])
        self.assertNotEqual(master['identity'],moved['identity'])
        self.assertFalse(moved['requires_occurrence'])

    def test_cancellation_with_no_start_retains_occurrence_identity(self):
        result=calendar.parse_calendar(export(event('RECURRENCE-ID:20261027T140000Z'), 'METHOD:CANCEL\r\n'))['events'][0]
        self.assertTrue(result['cancelled']);self.assertEqual(result['status'],'cancelled')
        self.assertIsNone(result['start']);self.assertTrue(result['warnings'])
        all_day=self.parse('DTSTART;VALUE=DATE:20261020\r\nRECURRENCE-ID;VALUE=DATE:20261020\r\nSTATUS:CANCELLED')
        self.assertEqual(all_day['recurrence_id'],'2026-10-20')

    def test_large_all_hands_is_bounded_and_does_not_generate_people(self):
        attendees='\r\n'.join(f'ATTENDEE;CN=Person {n}:mailto:person{n}@example.test' for n in range(2500))
        result=self.parse('DTSTART:20261020T140000Z\r\nSUMMARY:All hands\r\n'+attendees)
        self.assertEqual(result['attendee_total'],2500)
        self.assertEqual(len(result['attendees']),20)
        self.assertTrue(result['attendees_truncated'])
        self.assertNotIn('people',result)

    def test_large_description_is_truncated_with_disclosure(self):
        result=self.parse('DTSTART:20261020T140000Z\r\nDESCRIPTION:'+'a'*5000)
        self.assertEqual(len(result['description']),4096)
        self.assertTrue(result['description_truncated'])

    def test_event_count_size_and_line_bounds(self):
        with self.assertRaisesRegex(calendar.CalendarError,'100 events'):
            calendar.parse_calendar(export(''.join(event('DTSTART:20261020T140000Z',str(n)) for n in range(101))))
        with self.assertRaisesRegex(calendar.CalendarError,'1 MiB'):
            calendar.parse_calendar(b'x'*(calendar.MAX_BYTES+1))
        with self.assertRaisesRegex(calendar.CalendarError,'64 KiB'):
            self.parse('DTSTART:20261020T140000Z\r\nDESCRIPTION:'+'a'*65537)

    def test_invalid_or_unsupported_times_are_explicit_errors(self):
        cases=[('DTSTART;TZID=Eastern Standard Time:20261020T100000','timezone'),
               ('DTSTART;TZID=America/New_York:20261101T013000','ambiguous'),
               ('DTSTART;TZID=America/New_York:20260308T023000','nonexistent'),
               ('DTSTART:20260230T100000Z','Invalid'),
               ('DTSTART;TZID=America/New_York:20261020T100000Z','combine UTC'),
               ('DTSTART;VALUE=DATE;TZID=America/New_York:20261020','without TZID'),
               ('DTSTART:20261020T100000Z\r\nDTEND;VALUE=DATE:20261021','type'),
               ('DTSTART:20261020T100000Z\r\nDTEND:20261020T090000Z','after'),
               ('DTSTART;TZID=America/New_York:20261031T100000\r\nDURATION:P1D','DST')]
        for lines,message in cases:
            with self.subTest(lines=lines),self.assertRaisesRegex(calendar.CalendarError,message):self.parse(lines)

    def test_malformed_or_unsupported_recurrence_is_an_explicit_error(self):
        cases=['RRULE:FREQ=NOPE','RRULE:FREQ=WEEKLY;COUNT=3;UNTIL=20261031T120000Z',
               'RRULE:FREQ=MONTHLY;BYDAY=0MO','RRULE:FREQ=WEEKLY;BYDAY=2TU',
               'RRULE:FREQ=DAILY;INTERVAL=0','RRULE:FREQ=DAILY;X-SURPRISE=1',
               'RECURRENCE-ID;RANGE=THISANDFUTURE:20261020T140000Z',
               'EXRULE:FREQ=WEEKLY','RDATE;VALUE=PERIOD:20261020T140000Z/20261020T150000Z']
        for line in cases:
            with self.subTest(line=line),self.assertRaises(calendar.CalendarError):self.parse('DTSTART:20261020T140000Z\r\n'+line)

    def test_extreme_numbers_and_recurrence_type_mismatches_are_bounded_errors(self):
        cases=['RRULE:FREQ=DAILY;COUNT='+'1'*5000,
               'RRULE:FREQ=DAILY;BYSECOND='+'1'*5000,
               'DURATION:PT'+'1'*5000+'H',
               'EXDATE;VALUE=DATE:20261021',
               'RDATE:20261021T100000',
               'RECURRENCE-ID:20261020T140000']
        for line in cases:
            with self.subTest(line=line[:80]),self.assertRaises(calendar.CalendarError):
                self.parse('DTSTART:20261020T140000Z\r\n'+line)
        with self.assertRaisesRegex(calendar.CalendarError,'out of range'):
            self.parse('DTSTART;VALUE=DATE:99991231')

    def test_structure_duplicates_and_invalid_text_fail_without_partial_results(self):
        cases=['garbage', 'BEGIN:VCALENDAR\r\nVERSION:2.0\r\n',export(event('DTSTART:20261020T140000Z\r\nUID:duplicate')),
               export(event('DTSTART:20261020T140000Z\r\nDTSTART:20261021T140000Z')),
               export(event('DTSTART:20261020T140000Z\r\nSUMMARY:bad\\q'))]
        for content in cases:
            with self.subTest(content=content),self.assertRaises(calendar.CalendarError):calendar.parse_calendar(content)
        with self.assertRaisesRegex(calendar.CalendarError,'UTF-8'):calendar.parse_calendar(b'\xff')

    def test_export_rename_title_change_and_move_do_not_change_identity(self):
        a=calendar.parse_calendar(export(event('DTSTART:20261020T140000Z\r\nSUMMARY:Old')), 'Attachments/old.ics')
        b=calendar.parse_calendar(export(event('DTSTART:20261021T140000Z\r\nSUMMARY:New')), 'Attachments/new.ics')
        self.assertEqual(a['events'][0]['identity'],b['events'][0]['identity'])
        self.assertNotEqual(a['source'],b['source'])
        duplicate=calendar.parse_calendar(export(event('DTSTART:20261020T140000Z')*2))
        self.assertTrue(any('Duplicate UID' in value for value in duplicate['warnings']))
        self.assertTrue(a['read_only'])

    def test_alarms_timezone_components_and_embedded_content_are_not_executed(self):
        data=export('BEGIN:VTIMEZONE\r\nTZID:America/New_York\r\nEND:VTIMEZONE\r\n'+event(
            'DTSTART;TZID=America/New_York:20261020T100000\r\n'
            'ATTACH:https://example.test/private\r\nBEGIN:VALARM\r\nACTION:EMAIL\r\nDESCRIPTION:Send this\r\nEND:VALARM'))
        result=calendar.parse_calendar(data)
        self.assertEqual(len(result['events']),1)
        self.assertNotIn('attachments',result['events'][0]);self.assertNotIn('alarms',result['events'][0])
        self.assertTrue(any('VTIMEZONE' in value for value in result['warnings']))


if __name__=='__main__':unittest.main()
