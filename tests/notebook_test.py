import importlib.util
import json
import os
from pathlib import Path
import tempfile
import unittest

SCRIPT = Path(__file__).resolve().parents[1] / 'fieldbook_core/scripts/notebook.py'
spec = importlib.util.spec_from_file_location('notebook', SCRIPT)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class NotebookTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.vault = module.Vault(self.root)

    def put(self, name, text):
        p = self.root / name
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text, encoding='utf-8')
        return p

    def task(self, name='Tasks/Migration.md', extra=''):
        return self.put(name, '---\ntags: [task]\ntitle: Search migration\narea: work\nstatus: done\ntype: delivery\n'
                        'projects: ["[[Search]]"]\nassignee: ["[[Doe, Alex]]"]\ncompletedDate: 2026-09-12\n'
                        + extra + '---\nReduced search latency from 100 ms to 50 ms.\n')

    def test_relative_paths_protect_configuration_and_code(self):
        for p in ['/tmp/a.md', '../a.md', 'Tasks/../../a.md', 'C:/a.md', r'Tasks\a.md',
                  'Tasks/a.md:stream', 'Tasks/CON.md', 'Tasks/a.md.', '.git/config',
                  'fieldbook_core/scripts/x.py', 'Tasks/.secret.md', 'Tasks//a.md']:
            with self.subTest(p=p), self.assertRaises(ValueError):
                self.vault.path(p)
        for p in ['AGENTS.md', 'fieldbook.json', 'Templates/Task.md', 'Tasks/AGENTS.md']:
            with self.subTest(p=p), self.assertRaises(ValueError):
                self.vault.path(p, write=True)

    def test_tracker_configs_are_readable_but_not_writable_and_relationship_filter_is_exact(self):
        for provider in ('github','azure'):
            name=f'fieldbook_core/{provider}.json'
            self.put(name,'{"instances": []}')
            self.assertEqual(self.vault.read({'path':name})['text'],'{"instances": []}')
            with self.assertRaises(ValueError):self.vault.path(name,write=True)
        self.put('People/Me.md','---\ntags: [person]\nrelationship: self\n---\n')
        self.put('People/Alex.md','---\ntags: [person]\nrelationship: report\n---\n')
        self.put('People/Peer.md','---\ntags: [person]\nrelationship: peer\nmanager: "[[Me]]"\n---\n')
        result=self.vault.query({'filters':{'kind':'person','relationship':'report'}})
        self.assertEqual([r['path'] for r in result['results']],['People/Alex.md'])
    def test_symlinks_and_hardlinks_are_refused(self):
        source = self.put('Notes/source.md', 'source')
        os.link(source, self.root / 'Notes/other.md')
        with self.assertRaises(ValueError):
            self.vault.raw('Notes/source.md')
        try:
            (self.root / 'Tasks').symlink_to(self.root / 'Notes', target_is_directory=True)
        except OSError:
            self.skipTest('Host cannot create symlinks')
        with self.assertRaises(ValueError):
            self.vault.path('Tasks/new.md', write=True)

    def test_case_collisions(self):
        self.put('Tasks/Existing.md', 'x')
        with self.assertRaises(ValueError):
            self.vault.path('Tasks/existing.md', write=True)

    def test_write_creation_no_clobber_and_stale_hash(self):
        args = {'path': 'Tasks/New.md', 'text': 'new\n', 'expected': 'missing'}
        self.assertTrue(self.vault.write(args)['created'])
        with self.assertRaises(ValueError):
            self.vault.write(args)
        read = self.vault.read({'path': args['path']})
        self.put(args['path'], 'external change\n')
        with self.assertRaises(ValueError):
            self.vault.write({**args, 'expected': read['sha256']})
        self.assertEqual((self.root / args['path']).read_text(), 'external change\n')

    def test_read_paging_hash_and_write_preserve_bom_newlines(self):
        p = self.put('Notes/Unicode.md', '')
        p.write_bytes(b'\xef\xbb\xbfOne\r\nTwo\r\n')
        read = self.vault.read({'path': 'Notes/Unicode.md', 'limit': 1})
        self.assertTrue(read['truncated'])
        self.assertEqual(read['text'], 'One\r\n')
        args = {'path': 'Notes/Unicode.md', 'text': 'One\nThree\n', 'expected': read['sha256']}
        self.assertIn('+Three', self.vault.preview(args)['diff'])
        self.assertEqual(p.read_bytes(), b'\xef\xbb\xbfOne\r\nTwo\r\n')
        self.vault.write(args)
        self.assertEqual(p.read_bytes(), b'\xef\xbb\xbfOne\r\nThree\r\n')
        self.assertFalse(list(p.parent.glob('.fieldbook-*.tmp')))

    def test_final_review_and_invalid_yaml_cannot_be_overwritten(self):
        self.put('Reports/Final.md', '---\ntags: [review]\nstatus: final\n---\nApproved')
        read = self.vault.read({'path': 'Reports/Final.md'})
        with self.assertRaises(ValueError):
            self.vault.write({'path': read['path'], 'expected': read['sha256'], 'text': 'Replacement'})
        with self.assertRaises(ValueError):
            self.vault.write({'path': 'Tasks/Bad.md', 'expected': 'missing', 'text': '---\nstatus: a\nstatus: b\n---\n'})

    def test_tag_type_project_person_and_date_query(self):
        self.task()
        self.put('Notes/Meeting.md', '---\ntags: [meeting]\narea: work\n---\n')
        filters = {'kind': 'task', 'type': 'delivery', 'area': 'work', 'status': 'done',
                   'project': 'Search', 'person': 'Doe, Alex', 'completed_from': '2026-09-01', 'completed_to': '2026-09-30'}
        result = self.vault.query({'filters': filters})
        self.assertEqual([r['path'] for r in result['results']], ['Tasks/Migration.md'])
        self.assertEqual(self.vault.query({'filters': {'kind': 'meeting'}})['total'], 1)
        self.assertEqual(self.vault.query({'filters': {'completed_to': '2026-08-31'}})['total'], 0)

    def test_invalid_metadata_is_reported_and_searchable(self):
        self.put('Tasks/Broken.md', '---\ntags: [task\n---\nfind me')
        result = self.vault.query({})
        self.assertEqual(result['total'], 0)
        self.assertEqual(len(result['warnings']), 1)
        self.assertEqual(self.vault.search({'query': 'find me'})['total'], 1)
        for text in ['---\na: &x abc\nb: *x\n---\n', '---\na: !!python/object x\n---\n']:
            with self.assertRaises(ValueError):
                module.frontmatter(text)

    def test_search_modes_and_excluded_examples(self):
        self.task()
        self.put('Templates/Task.md', 'search latency')
        self.put('Examples/Demo.md', 'search latency')
        self.put('Notes/Garden.md', 'Tomatoes and gardening')
        self.assertEqual(self.vault.search({'query': 'LATENCY'})['total'], 1)
        self.assertEqual(self.vault.search({'query': r'\d+ ms', 'mode': 'regex'})['total'], 1)
        self.assertEqual(self.vault.search({'query': 'Serch migraton', 'mode': 'fuzzy'})['results'][0]['path'], 'Tasks/Migration.md')
        self.assertEqual(self.vault.search({'query': 'search latency', 'mode': 'similar'})['results'][0]['path'], 'Tasks/Migration.md')
        self.assertEqual(self.vault.search({'query': 'latency', 'filters': {'area': 'school'}})['total'], 0)
        self.assertEqual(self.vault.search({'query': 'latency', 'scope': 'guides'})['total'], 2)

    def test_regex_timeout_and_invalid_pattern(self):
        self.put('Notes/Long.md', 'a' * 20000 + '!')
        with self.assertRaisesRegex(ValueError, 'two-second'):
            self.vault.search({'query': '(a+)+$', 'mode': 'regex'})
        with self.assertRaisesRegex(ValueError, 'regular expression'):
            self.vault.search({'query': '[', 'mode': 'regex'})

    def test_paging(self):
        for n in range(3):
            self.put(f'Notes/{n}.md', 'test')
        result = self.vault.search({'query': 'test', 'limit': 2})
        self.assertEqual(result['next_offset'], 2)
        self.assertEqual(self.vault.search({'query': 'test', 'limit': 2, 'offset': 2})['results'][0]['path'], 'Notes/2.md')

    def test_links_aliases_backlinks_and_ambiguity(self):
        self.put('People/Alex.md', '---\ntags: [person]\naliases: [Al]\n---\n')
        self.put('Notes/Source.md', '[[Al]] [[Missing]] [[Alex]]')
        self.assertEqual(self.vault.links({})['results'][0]['target'], 'Missing')
        self.assertEqual(self.vault.links({'target': 'Alex'})['total'], 2)
        self.put('Notes/Alex.md', 'Another Alex')
        self.assertTrue(any(r['status'] == 'ambiguous' for r in self.vault.links({})['results']))

    def test_transcript_is_read_only(self):
        p = self.put('Transcripts/Meeting.vtt', 'WEBVTT\n\n1\n00:00:00.000 --> 00:00:02.000\n<v Alex>Hello &amp; welcome</v>\n')
        before = p.read_bytes()
        result = self.vault.transcript({'path': 'Transcripts/Meeting.vtt'})
        self.assertEqual(result['text'], 'Alex: Hello & welcome')
        self.assertEqual(p.read_bytes(), before)
        self.assertEqual(self.vault.files('transcripts'), ['Transcripts/Meeting.vtt'])

    def test_overview_recurring_and_closed_tasks(self):
        self.task('Tasks/Done.md', 'due: 2000-01-01\n')
        self.put('Tasks/Open.md', '---\ntags: [task]\nstatus: active\ndue: 2000-01-01\n---\n')
        self.put('Tasks/Repeat.md', '---\ntags: [task]\nstatus: active\ndue: 2000-01-01\nrecurrence: weekly\n---\n')
        result = self.vault.overview({})
        self.assertEqual(result['tasks'], 3)
        self.assertEqual(result['overdue_total'], 1)

    def test_help_uses_installed_metadata(self):
        self.put('fieldbook_core/commands/people.md', '---\ndescription: Find contacts\n---\n')
        self.put('fieldbook_core/skills/resume/SKILL.md', '---\nname: resume\ndescription: Craft a resume\n---\n')
        self.assertEqual(self.vault.help({'topic': '/people'})['entries'][0]['name'], 'people')
        self.assertEqual(len(self.vault.help({})['entries']), 2)


if __name__ == '__main__':
    unittest.main()
