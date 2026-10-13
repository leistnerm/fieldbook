"""Exercise setup-aware help without making hidden module copies readable."""
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('help_notebook', ROOT/'fieldbook_core/scripts/notebook.py')
notebook = importlib.util.module_from_spec(spec)
spec.loader.exec_module(notebook)


class HelpTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.vault = notebook.Vault(self.root)
        self.put('fieldbook.json', json.dumps({'setups': ['work'], 'workRole': 'people-manager', 'features': {'reviews': False}}))
        self.resources = [
            {'path': 'fieldbook_core/commands/course.md', 'setup': 'school', 'description': 'Create a formal course'},
            {'path': 'fieldbook_core/commands/coach.md', 'setup': 'work', 'workRole': 'people-manager', 'description': 'Prepare coaching'},
            {'path': 'fieldbook_core/commands/review.md', 'setup': 'work', 'feature': 'reviews', 'description': 'Prepare an evaluation'},
            {'path': 'fieldbook_core/skills/personal-admin/SKILL.md', 'setup': 'personal', 'description': 'Household planning'},
        ]
        self.put('tools/setup-catalog.json', json.dumps({'schemaVersion': 1, 'resources': self.resources}))
        self.put('fieldbook_core/commands/task.md', '---\ndescription: Capture an action\n---\n')
        self.put('fieldbook_core/commands/coach.md', '---\ndescription: Prepare coaching\n---\n')

    def put(self, name, text):
        path = self.root/name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text)
        return path

    def test_normal_help_lists_only_installed_workflows(self):
        entries = self.vault.help({})['entries']
        self.assertEqual({e['name'] for e in entries}, {'task', 'coach'})
        self.assertTrue(all(e['status'] == 'active' and e['installed'] for e in entries))
        self.assertEqual(next(e for e in entries if e['name'] == 'coach')['requirements'],
                         {'setup': 'work', 'workRole': 'people-manager'})

    def test_explicit_help_can_discover_disabled_features_and_setup_requirements(self):
        for topic, name, requirements in [('/course', 'course', {'setup': 'school'}),
                                         ('evaluation', 'review', {'setup': 'work', 'feature': 'reviews'}),
                                         ('household', 'personal-admin', {'setup': 'personal'})]:
            with self.subTest(topic=topic):
                entry = self.vault.help({'topic': topic})['entries'][0]
                self.assertEqual(entry['name'], name)
                self.assertEqual(entry['status'], 'inactive')
                self.assertFalse(entry['installed'])
                self.assertFalse(entry['enabled'])
                self.assertIsNone(entry['path'])
                self.assertEqual(entry['requirements'], requirements)

    def test_custom_disabled_command_remains_visible_with_honest_status(self):
        self.put('fieldbook_core/commands/course.md', '---\ndescription: My custom course workflow\n---\n')
        self.put('.fieldbook/modules/state.json', json.dumps({'schemaVersion': 1, 'resources': {
            'fieldbook_core/commands/course.md': {'enabled': False, 'preserved': True}}}))
        entry = next(e for e in self.vault.help({})['entries'] if e['name'] == 'course')
        self.assertEqual(entry['description'], 'My custom course workflow')
        self.assertEqual(entry['status'], 'custom-preserved')
        self.assertFalse(entry['enabled'])
        self.assertTrue(entry['installed'])
        self.assertEqual(len(self.vault.help({'topic': 'course'})['entries']), 1)

    def test_removed_enabled_workflow_is_not_recommended_as_installed(self):
        (self.root/'fieldbook_core/commands/coach.md').unlink()
        self.put('.fieldbook/modules/state.json', json.dumps({'schemaVersion': 1, 'resources': {
            'fieldbook_core/commands/coach.md': {'enabled': True, 'removed': True}}}))
        self.assertEqual([e['name'] for e in self.vault.help({})['entries']], ['task'])
        self.assertEqual(self.vault.help({'topic': '/coach'})['entries'][0]['status'], 'user-removed')

    def test_bank_and_metadata_are_not_readable_by_notebook_read(self):
        self.put('.fieldbook/modules/files/fieldbook_core/commands/course.md', 'hidden template body')
        for name in ('tools/setup-catalog.json', '.fieldbook/modules/state.json',
                     '.fieldbook/modules/files/fieldbook_core/commands/course.md'):
            with self.subTest(path=name), self.assertRaises(ValueError):
                self.vault.read({'path': name})
        self.assertNotIn('hidden template body', json.dumps(self.vault.help({'topic': 'course'})))

    def test_linked_metadata_is_reported_without_following_it(self):
        catalog = self.root/'tools/setup-catalog.json'
        catalog.unlink()
        target = self.put('Notes/secret.json', '{"private": "Do not return me"}')
        try:
            catalog.symlink_to(target)
        except OSError:
            self.skipTest('Host cannot create symlinks')
        result = self.vault.help({'topic': 'course'})
        self.assertTrue(result['warnings'])
        self.assertNotIn('Do not return me', json.dumps(result))

    def test_dashboards_and_optional_guide_are_read_only_guides_not_records(self):
        self.put('Dashboards/Work.md', '---\ntags: [task]\n---\nDashboard test phrase')
        self.put('Optional functionality.md', 'Dashboard test phrase')
        self.assertEqual(self.vault.query({})['total'], 0)
        self.assertEqual(self.vault.search({'query': 'Dashboard test phrase'})['total'], 0)
        self.assertEqual(self.vault.search({'query': 'Dashboard test phrase', 'scope': 'guides'})['total'], 2)
        self.assertIn('Dashboards/Work.md', self.vault.files('guides'))
        self.assertIn('Dashboard test phrase', self.vault.read({'path': 'Dashboards/Work.md'})['text'])
        for name in ('Dashboards/Work.md', 'Optional functionality.md'):
            with self.subTest(path=name), self.assertRaises(ValueError):
                self.vault.path(name, write=True)


if __name__ == '__main__':
    unittest.main()
