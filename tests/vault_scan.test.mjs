import test from 'node:test'
import assert from 'node:assert/strict'
import { mkdtemp, mkdir, writeFile, rm } from 'node:fs/promises'
import os from 'node:os'
import path from 'node:path'
import { markdownFiles, frontmatter } from '../fieldbook_core/lib/vault.js'
test('shared scan excludes hidden backups, templates, examples and dashboards',async()=>{
  const root=await mkdtemp(path.join(os.tmpdir(),'fieldbook-scan-'))
  try {
    const included=['Projects/Active.md','Custom/Real.md']
    for(const name of [...included,'.fieldbook/config-backups/old/Projects/Old.md','Templates/T.md','Examples/E.md','Dashboards/D.md','Notes/.hidden.md']) {
      await mkdir(path.dirname(path.join(root,name)),{recursive:true});await writeFile(path.join(root,name),'---\njira: APP-1\n---\n')
    }
    assert.deepEqual((await markdownFiles(root)).map(p=>p.split(path.sep).join('/')).sort(),included.sort())
    await writeFile(path.join(root,'Projects/Huge.md'),'x'.repeat(1024*1024+1))
    await assert.rejects(markdownFiles(root),/Incomplete note scan/)
  } finally {await rm(root,{recursive:true,force:true})}
})
test('frontmatter has a bounded metadata budget',()=>assert.throws(()=>frontmatter('---\na: '+ 'x'.repeat(32769)+'\n---\n'),/32 KiB/))
