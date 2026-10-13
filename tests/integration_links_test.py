#!/usr/bin/env python3
import importlib.util
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('integration_links', ROOT / 'tools/integration_links.py')
links = importlib.util.module_from_spec(spec);spec.loader.exec_module(links)


class LinksTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup);self.root = Path(self.temp.name).resolve()
        (self.root / 'fieldbook_core').mkdir();(self.root / 'Projects').mkdir()
        for provider in links.FIELDS:
            base = 'https://service.example'
            if provider == 'google':base = 'https://www.googleapis.com/calendar/v3'
            if provider == 'microsoft':base = 'https://graph.microsoft.com/v1.0'
            item = {'id': 'one', 'baseUrl': base, 'tokenVar': provider.upper() + '_TOKEN'}
            if provider == 'jira':item['flavor'] = 'server'
            (self.root / 'fieldbook_core' / (provider + '.json')).write_text(json.dumps({'instances': [item, {**item, 'id': 'two'}]}))

    def note(self, text='---\ntags: [project]\n---\nBody.\n', path='Projects/Test.md'):
        target = self.root / path;target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(text.encode() if isinstance(text, str) else text);return path

    def plan(self, path=None, provider='jira', instance='one', choice=None):
        return links.plan_link(self.root, path or 'Projects/Test.md', provider, instance, {'id': 'ABC'} if choice is None else choice)

    def test_plan_is_mutation_free_apply_adds_only_bindings_and_backup(self):
        path = self.note();before = (self.root / path).read_bytes()
        plan = self.plan();self.assertEqual((self.root / path).read_bytes(), before)
        self.assertFalse((self.root / '.fieldbook').exists());self.assertEqual(len(plan['changes']), 2)
        receipt = links.apply_link(self.root, plan)
        self.assertEqual((self.root / receipt['backup']).read_bytes(), before)
        after = (self.root / path).read_bytes();self.assertTrue(after.endswith(b'---\nBody.\n'))
        self.assertIn(b'jira_instance: "one"\njira_project_key: "ABC"', after)
        self.assertNotIn('token', after.decode())

    def test_bom_crlf_unrelated_styles_and_body_preserved_exactly(self):
        original = b'\xef\xbb\xbf---\r\n# Comment\r\ntags: [project]\r\ncustom: \'Keep it\' # inline\r\nlist:\r\n  - yes\r\njira_instance: old # keep this\r\njira_project_key: XYZ\r\n---\r\n\r\nBody \t unchanged\nMixed newline.\r\n'
        path = self.note(original);plan = self.plan();links.apply_link(self.root, plan)
        expected = original.replace(b'jira_instance: old', b'jira_instance: "one"').replace(b'jira_project_key: XYZ', b'jira_project_key: "ABC"')
        self.assertEqual((self.root / path).read_bytes(), expected)

    def test_flow_frontmatter_preserves_unrelated_fields_and_comments(self):
        original = '---\n{tags: [project], custom: \'yes\'} # comment\n---\nBODY'
        path = self.note(original);links.apply_link(self.root, self.plan())
        self.assertEqual((self.root / path).read_text(), original.replace("custom: 'yes'}", 'custom: \'yes\', jira_instance: "one", jira_project_key: "ABC"}'))

    def test_blank_and_block_scalar_binding_values_are_safely_replaced(self):
        path = self.note('---\ntags: [project]\njira_instance: # keep\njira_project_key: >-\n  OLD\n# keep block comment\nother: true\n---\nBODY')
        links.apply_link(self.root, self.plan())
        self.assertEqual((self.root / path).read_text(), '---\ntags: [project]\njira_instance: "one" # keep\njira_project_key: "ABC"\n# keep block comment\nother: true\n---\nBODY')

    def test_all_tracker_and_course_scope_forms(self):
        self.note('---\ntags: [project, course]\n---\nBody')
        cases = [('agility', {'id': 'Scope:12'}, 'agility_scope_id', 'Scope:12'), ('github', {'id': 'owner/repo'}, 'github_repository', 'owner/repo'),
                 ('azure', {'id': 'uuid', 'settings': {'project': "Team's Project"}}, 'azure_project', "Team's Project"),
                 ('canvas', {'id': 42}, 'canvas_course_id', '42')]
        for provider, choice, field, value in cases:
            with self.subTest(provider=provider):
                plan = self.plan(provider=provider, choice=choice);links.apply_link(self.root, plan)
                self.assertIn({'field': field, 'before': '', 'after': value}, plan['changes'])
        text = (self.root / 'Projects/Test.md').read_text()
        for _, _, field, _ in cases:self.assertIn(field, text)

    def test_two_schools_can_use_the_same_course_id(self):
        a = self.note('---\ntags: [course, project]\n---\nA', 'Projects/School A.md')
        b = self.note('---\ntags: [course, project]\n---\nB', 'Projects/School B.md')
        links.apply_link(self.root, self.plan(a, 'canvas', 'one', {'id': '42'}))
        links.apply_link(self.root, self.plan(b, 'canvas', 'two', {'id': '42'}))
        records = links.list_records(self.root, 'course')
        self.assertEqual(len(records), 2)
        self.assertEqual({r['bindings']['canvas']['canvas_instance'] for r in records}, {'one', 'two'})

    def test_lists_notes_by_tags_anywhere_in_content_folders_and_excludes_seeds(self):
        self.note();self.note('---\ntags: [project, course]\n---\n', 'Notes/Course.md')
        self.note('---\ntags: series\n---\n', 'Meetings/Weekly.md')
        self.note(path='Templates/Project.md');self.note(path='Examples/Project.md');self.note(path='Projects/.hidden/Project.md')
        self.note(path='Projects/Examples/Project.md');self.note('---\ntags: task\n---\n', 'Tasks/Task.md')
        all_records = links.list_records(self.root)
        self.assertEqual({r['path'] for r in all_records}, {'Projects/Test.md', 'Notes/Course.md', 'Meetings/Weekly.md'})
        self.assertEqual(len(links.list_records(self.root, 'project')), 2)
        self.assertEqual(len(links.list_records(self.root, 'series')), 1)

    def test_wrong_types_and_protected_paths_are_rejected(self):
        self.note()
        with self.assertRaises(links.LinkError):self.plan(provider='canvas', choice={'id': '1'})
        for path in ('../else.md', '/tmp/note.md', 'Templates/Project.md', 'Projects/AGENTS.md', 'Projects/.hidden.md', 'README.md', 'Projects/../Test.md'):
            with self.subTest(path=path), self.assertRaises(links.LinkError):self.plan(path)

    def test_duplicate_keys_aliases_anchors_explicit_tags_and_invalid_yaml_rejected(self):
        for fields in ('tags: [project]\nx: 1\nx: 2', 'tags: [project]\nx: &x value', 'tags: [project]\nx: *other',
                       'tags: [project]\nx: !!str value', 'tags: [project]\nx: [', 'tags: [project]\nx: {a: 1, a: 2}'):
            self.note('---\n' + fields + '\n---\n')
            with self.assertRaises(links.LinkError):self.plan()

    def test_non_scalar_binding_requires_manual_repair(self):
        self.note('---\ntags: [project]\njira_instance: [one]\n---\n')
        with self.assertRaises(links.LinkError):self.plan()

    def test_ticket_identity_prevents_rebinding_instance_including_legacy_missing_instance(self):
        for instance in ('jira_instance: one\n', ''):
            self.note('---\ntags: [project]\njira: ABC-12\n' + instance + '---\n')
            with self.assertRaises(links.LinkError):self.plan(instance='two')
        self.note('---\ntags: [project]\njira: ABC-12\njira_instance: one\n---\n')
        self.assertFalse(self.plan()['unchanged'])

    def test_clear_binding_retains_ticket_instance_and_comments(self):
        path = self.note('---\ntags: [project]\njira: ABC-12\njira_instance: one # account\njira_project_key: ABC # scope\n---\nBody')
        plan = links.plan_link(self.root, path, 'jira', 'one', None)
        self.assertEqual(plan['changes'], [{'field': 'jira_project_key', 'before': 'ABC', 'after': ''}])
        links.apply_link(self.root, plan)
        text = (self.root / path).read_text();self.assertIn('jira_instance: one # account', text);self.assertIn('jira_project_key: "" # scope', text)

    def test_clear_unneeded_instance_and_idempotent_apply(self):
        path = self.note();links.apply_link(self.root, self.plan())
        plan = links.plan_link(self.root, path, 'jira', 'one', None);links.apply_link(self.root, plan)
        next_plan = links.plan_link(self.root, path, 'jira', 'one', None)
        self.assertTrue(next_plan['unchanged']);self.assertIsNone(links.apply_link(self.root, next_plan)['backup'])

    def test_canvas_planner_quiz_and_checkpoint_bindings_prevent_course_rebind(self):
        for field, value in [('canvas_identity', 'canvas:one:course:12:wiki_page:9'), ('canvas_aliases', '["canvas:one:course:12:quiz:9"]'), ('canvas_quiz_id', '9'), ('canvas_discussion_id', '9'), ('canvas_checkpoint_tag', 'reply_to_topic')]:
            path = self.note('---\ntags: [project, course]\ncanvas_instance: one\ncanvas_course_id: "12"\n' + field + ': ' + value + '\n---\n')
            with self.subTest(field=field):
                with self.assertRaises(links.LinkError):links.plan_link(self.root, path, 'canvas', 'one', {'id': '13'})

    def test_canvas_item_course_identity_cannot_be_rebound_or_cleared(self):
        path = self.note('---\ntags: [project, course]\ncanvas_instance: one\ncanvas_course_id: "12"\ncanvas_assignment_id: "99"\n---\n')
        for choice in ({'id': '13'}, None):
            with self.assertRaises(links.LinkError):links.plan_link(self.root, path, 'canvas', 'one', choice)
        self.assertTrue(self.plan(provider='canvas', choice={'id': '12'})['unchanged'])

    def test_race_and_config_changes_refuse_before_note_write(self):
        path = self.note();plan = self.plan();(self.root / path).write_text('---\ntags: [project]\n---\nNew body')
        with self.assertRaises(links.LinkError):links.apply_link(self.root, plan)
        self.assertFalse((self.root / '.fieldbook').exists())
        plan = self.plan();config = self.root / 'fieldbook_core/jira.json';config.write_text(config.read_text() + ' ')
        with self.assertRaises(links.LinkError):links.apply_link(self.root, plan)
        self.assertFalse((self.root / '.fieldbook').exists())

    def test_plan_tampering_and_cross_vault_apply_refused(self):
        self.note();plan = self.plan();plan['changes'][0]['field'] = 'title'
        with self.assertRaises(links.LinkError):links.apply_link(self.root, plan)
        plan = self.plan();plan['vault'] = 'different'
        with self.assertRaises(links.LinkError):links.apply_link(self.root, plan)

    def test_symlink_hardlink_and_linked_backup_directory_refused(self):
        path = self.note();original = self.root / path;other = self.root / 'other.md';original.rename(other);original.symlink_to(other)
        with self.assertRaises(links.LinkError):self.plan()
        original.unlink();os.link(other, original)
        with self.assertRaises(links.LinkError):self.plan()
        original.unlink();other.rename(original);plan = self.plan()
        (self.root / '.fieldbook').symlink_to(self.root / 'Projects', target_is_directory=True)
        with self.assertRaises(links.LinkError):links.apply_link(self.root, plan)
        self.assertNotIn('jira_instance', original.read_text())

    def test_real_time_race_after_backup_is_detected(self):
        path = self.note();plan = self.plan();original_mkstemp = links.tempfile.mkstemp
        def changed(*args, **kwargs):
            result = original_mkstemp(*args, **kwargs)
            (self.root / path).write_text('---\ntags: [project]\n---\nConcurrent edit')
            return result
        with patch.object(links.tempfile, 'mkstemp', side_effect=changed), self.assertRaises(links.LinkError):links.apply_link(self.root, plan)
        self.assertTrue((self.root / path).read_text().endswith('Concurrent edit'))
        self.assertFalse(list((self.root / 'Projects').glob('.fieldbook-link-*')))

    def test_calendar_series_binding_and_clearing(self):
        path = self.note('---\ntags: series\ncustom: yes # keep\n---\nBody', 'Meetings/Weekly.md')
        for provider, instance in [('google', 'one'), ('microsoft', 'two')]:
            choice = {'id': 'series-ID/abc=', 'settings': {'calendar_provider': provider, 'calendar_instance': instance, 'calendar_id': 'calendar-ID/abc=', 'calendar_series_id': 'series-ID/abc='}}
            plan = links.plan_link(self.root, path, provider, instance, choice);links.apply_link(self.root, plan)
        records = links.list_records(self.root, 'series');self.assertEqual(records[0]['bindings']['microsoft']['calendar_instance'], 'two')
        plan = links.plan_link(self.root, path, 'microsoft', 'two', None);links.apply_link(self.root, plan)
        self.assertIn('custom: yes # keep', (self.root / path).read_text());self.assertTrue((self.root / path).read_text().endswith('Body'))

    def test_series_choice_mismatches_and_event_identity_refused(self):
        path = self.note('---\ntags: series\ncalendar_uid: existing\n---\n', 'Meetings/Weekly.md')
        choice = {'id': 'series', 'settings': {'calendar_provider': 'google', 'calendar_instance': 'one', 'calendar_id': 'calendar', 'calendar_series_id': 'series'}}
        with self.assertRaises(links.LinkError):links.plan_link(self.root, path, 'google', 'one', choice)
        choice['settings']['calendar_instance'] = 'one';choice['settings']['calendar_id'] = 'primary'
        with self.assertRaises(links.LinkError):links.plan_link(self.root, path, 'google', 'one', choice)
        self.note('---\ntags: series\n---\n', path);choice['settings']['calendar_instance'] = 'two'
        with self.assertRaises(links.LinkError):links.plan_link(self.root, path, 'google', 'one', choice)


if __name__ == '__main__':unittest.main()
