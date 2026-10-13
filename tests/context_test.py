"""Exercise shipped template records through the actual scoped notebook tools."""
import importlib.util
import json
from pathlib import Path
import re
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('context_notebook', ROOT/'fieldbook_core/scripts/notebook.py')
notebook = importlib.util.module_from_spec(spec)
spec.loader.exec_module(notebook)

def template(name):
    text = (ROOT/f'Templates/{name}.md').read_text()
    text = re.sub(r'<%\*[\s\S]*?-?%>\n?', '', text)
    text = text.replace('<% JSON.stringify(tp.file.title) %>', '"Sample record"')
    text = text.replace('<% tp.date.now("YYYY-MM-DD") %>', '2026-10-10')
    return text

class ContextTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.vault = notebook.Vault(self.root)

    def write(self, path, text):
        self.vault.write({'path':path,'text':text,'expected':'missing'})

    def test_shared_records_can_be_saved_queried_and_linked_in_each_area(self):
        cases = [('core',[],''),('personal',['personal'],'personal'),('work',['work'],'work'),
                 ('school',['school'],'school'),('combined',['personal','work','school'],'')]
        for label,setups,area in cases:
            with self.subTest(setup=label):
                (self.root/'fieldbook.json').write_text(json.dumps({'setups':setups,'workRole':'people-manager',
                    'features':{'reviews':False},'defaults':{'area':area}}))
                project=f'Project {label}'
                self.write(f'Projects/{project}.md',template('Project').replace('area:\n',f'area: {area}\n'))
                for name,folder,kind in [('Item','Items','item'),('Item - Purchased','Items','item'),
                                        ('Reference','Reference','reference'),('Research','Research','research'),
                                        ('Research - Experiment','Research','research'),('Task - Study session','Tasks','task')]:
                    path=f'{folder}/{label} {name}.md'
                    text=template(name).replace('area:\n',f'area: {area}\n').replace('projects: []',f'projects: ["[[{project}]]"]')
                    self.write(path,text)
                    result=self.vault.query({'filters':{'kind':kind,'project':project}})
                    self.assertIn(path,[r['path'] for r in result['results']])
                    if area:
                        scoped=self.vault.query({'filters':{'kind':kind,'project':project,'area':area}})
                        self.assertIn(path,[r['path'] for r in scoped['results']])
                    self.assertEqual(self.vault.read({'path':path})['text'],text)
                self.assertEqual(self.vault.links({'target':project})['total'],6)

    def test_unfiltered_planning_tools_include_blank_missing_and_disabled_areas(self):
        for area in ('personal','work','school','',None):
            area_line='' if area is None else f'area: {area}\n'
            self.write(f'Tasks/{area or "blank"}{"missing" if area is None else ""}.md',
                       f'---\ntags: [task]\nstatus: active\n{area_line}---\n')
        for setups in ([],['personal'],['work'],['school'],['personal','school'],['personal','work','school']):
            with self.subTest(setups=setups):
                (self.root/'fieldbook.json').write_text(json.dumps({'setups':setups}))
                self.assertEqual(self.vault.query({'filters':{'kind':'task'}})['total'],5)
                self.assertEqual(self.vault.overview({})['by_area'],{'personal':1,'work':1,'school':1,'unset':2})
                self.assertEqual(self.vault.query({'filters':{'kind':'task','area':'school'}})['total'],1)

    def test_existing_specialized_fields_and_history_survive_a_local_edit(self):
        for path,text in [('Items/Drill.md','---\ntags: [item]\narea: personal\nstatus: lent\nwarranty_end: 2028-01-01\nreceipt: "[[receipt.pdf]]"\n---\n## Maintenance and repair history\n- 2026-09-10: Replaced bit.\n'),
                          ('Reference/Runbook.md','---\ntags: [reference]\nkind: how-to\nsystems: [Lab]\nverified: 2026-09-10\n---\nOriginal commands and source.\n'),
                          ('Research/Trial.md','---\ntags: [research]\nkind: experiment\n---\n## Hypothesis\nOriginal prediction.\n## Method\nOriginal method.\n')]:
            self.write(path,text)
            read=self.vault.read({'path':path})
            self.vault.write({'path':path,'text':read['text']+'\nRequested follow-up.\n','expected':read['sha256']})
            self.assertEqual(self.vault.read({'path':path})['text'],text+'\nRequested follow-up.\n')

if __name__=='__main__': unittest.main()
