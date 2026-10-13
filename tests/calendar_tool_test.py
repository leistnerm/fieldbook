"""Exercise the actual scoped calendar operation, including its read boundary."""
import importlib.util
import os
from pathlib import Path
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('calendar_notebook', ROOT/'fieldbook_core/scripts/notebook.py')
notebook = importlib.util.module_from_spec(spec)
spec.loader.exec_module(notebook)
ICS = '''BEGIN:VCALENDAR\r
VERSION:2.0\r
PRODID:-//Fieldbook//Calendar test//EN\r
BEGIN:VEVENT\r
UID:demo-event@example.test\r
DTSTAMP:20261011T120000Z\r
DTSTART:20261012T150000Z\r
DTEND:20261012T153000Z\r
SUMMARY:Project planning\r
ATTENDEE;CN=Alex:mailto:alex@example.test\r
END:VEVENT\r
END:VCALENDAR\r
'''


class CalendarToolTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        (self.root/'Attachments').mkdir()
        (self.root/'Attachments/invite.ics').write_text(ICS, newline='')
        self.vault = notebook.Vault(self.root)

    def test_preview_reads_one_local_event_without_creating_people_or_meetings(self):
        before = {p.relative_to(self.root): p.read_bytes() for p in self.root.rglob('*') if p.is_file()}
        result = self.vault.run({'operation':'calendar', 'path':'Attachments/invite.ics'})
        self.assertTrue(result['read_only'])
        self.assertEqual(result['total_events'], 1)
        self.assertEqual(result['events'][0]['uid'], 'demo-event@example.test')
        self.assertEqual(result['events'][0]['attendee_total'], 1)
        self.assertEqual(before, {p.relative_to(self.root): p.read_bytes() for p in self.root.rglob('*') if p.is_file()})

    def test_raw_calendar_cannot_bypass_the_bounded_parser_via_normal_read(self):
        with self.assertRaises(notebook.NotebookError):
            self.vault.read({'path':'Attachments/invite.ics'})

    def test_calendar_rejects_other_folders_urls_and_traversal(self):
        for name in ('invite.ics', 'Notes/invite.ics', '../invite.ics', 'Attachments/../invite.ics',
                     'https://example.test/calendar.ics', 'Attachments/.hidden/invite.ics', 'Attachments/invite.md'):
            with self.subTest(path=name), self.assertRaises(notebook.NotebookError):
                self.vault.run({'operation':'calendar','path':name})

    def test_calendar_rejects_links_and_never_writes_invites(self):
        link = self.root/'Attachments/linked.ics'
        link.symlink_to(self.root/'Attachments/invite.ics')
        with self.assertRaises(notebook.NotebookError):
            self.vault.calendar({'path':'Attachments/linked.ics'})
        with self.assertRaises(notebook.NotebookError):
            self.vault.write({'path':'Attachments/invite.ics','text':'changed','expected':'missing'})

    def test_calendar_rejects_hardlinks(self):
        os.link(self.root/'Attachments/invite.ics', self.root/'Attachments/copy.ics')
        with self.assertRaises(notebook.NotebookError):
            self.vault.calendar({'path':'Attachments/copy.ics'})


if __name__ == '__main__':
    unittest.main()
