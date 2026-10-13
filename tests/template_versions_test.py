"""Provenance discovery stays advisory and read-only across real templates."""
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('versions_notebook',ROOT/'fieldbook_core/scripts/notebook.py')
nb=importlib.util.module_from_spec(spec);spec.loader.exec_module(nb)

class TemplateVersionTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name);self.vault=nb.Vault(self.root)
    def put(self,path,text):
        p=self.root/path;p.parent.mkdir(parents=True,exist_ok=True);p.write_text(text,encoding='utf-8')
    def test_statuses_pagination_filters_and_no_writes(self):
        self.put('Templates/Person.md','---\ntemplateName: Person\ntemplateVersion: 2\ntags: [person]\n---\n## Notes\n')
        for name,props in [('Old','templateName: Person\ntemplateVersion: 1'),('Current','templateName: Person\ntemplateVersion: 2'),('Future','templateName: Person\ntemplateVersion: 3'),('Legacy',''),('Other','templateName: Missing\ntemplateVersion: 1'),('Invalid','templateName: Person\ntemplateVersion: -1')]:
            self.put('People/'+name+'.md','---\ntags: [person]\n'+props+'\n---\nKeep [[Link#Heading]] ^anchor\n')
        self.put('Tasks/Task.md','---\ntags: [task]\n---\nKeep task\n')
        before={p.relative_to(self.root):p.read_bytes() for p in self.root.rglob('*') if p.is_file()}
        result=self.vault.run({'operation':'template_status','filters':{'kind':'person'},'limit':2})
        self.assertEqual(result['total'],6);self.assertEqual(result['next_offset'],2)
        self.assertEqual(result['counts'],{'current':1,'newer':1,'unknown':2,'older':1,'unavailable':1})
        self.assertFalse(result['changed']);self.assertFalse(result['warnings'])
        self.assertEqual(before,{p.relative_to(self.root):p.read_bytes() for p in self.root.rglob('*') if p.is_file()})
    def test_duplicate_identity_does_not_select_arbitrary_template(self):
        for name in ('One','Two'):
            self.put('Templates/'+name+'.md','---\ntemplateName: Person\ntemplateVersion: 2\n---\n')
        self.put('People/Sam.md','---\ntemplateName: Person\ntemplateVersion: 1\n---\n')
        result=self.vault.template_status({})
        self.assertEqual(result['results'][0]['status'],'unavailable');self.assertTrue(result['warnings'])
    def test_shipped_templates_have_unique_metadata_without_executing_templater(self):
        import re
        names=set()
        for p in (ROOT/'Templates').glob('*.md'):
            text=p.read_text()
            if p.stem=='Task body':
                self.assertRegex(text,r'template fragment: Task body; version: [1-9][0-9]*');continue
            clean=re.sub(r'^<%\*[\s\S]*?-?%>\s*','',text)
            fm=nb.frontmatter(clean)
            self.assertEqual(fm['templateName'],p.stem);self.assertRegex(fm['templateVersion'],r'^[1-9][0-9]*$')
            self.assertNotIn(fm['templateName'],names);names.add(fm['templateName'])
        seeds=json.loads((ROOT/'tools/starter-seeds.json').read_text())
        self.assertEqual(seeds['Templates/Review-format.md'],(ROOT/'Templates/Review-format.md').read_text())
    def test_setup_blocks_and_custom_unversioned_templates(self):
        self.put('Templates/Meeting.md','<%* DO NOT EXECUTE -%>\r\n---\r\ntemplateName: Meeting\r\ntemplateVersion: 2\r\n---\r\n')
        self.put('Templates/Custom.md','---\ntags: [note]\n---\n')
        self.put('Meetings/One.md','---\ntemplateName: Meeting\ntemplateVersion: 1\n---\n')
        result=self.vault.template_status({})
        self.assertEqual(result['results'][0]['status'],'older');self.assertFalse(result['warnings'])

if __name__=='__main__':unittest.main()
