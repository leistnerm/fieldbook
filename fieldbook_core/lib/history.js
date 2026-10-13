import { execFile } from 'node:child_process'
import { promisify } from 'node:util'
import { realpath } from 'node:fs/promises'
const execute = promisify(execFile)
export async function snapshot(directory, prefix, run = execute, resolve = realpath) {
  const git = async (...args) => (await run('git', ['-C', directory, ...args], { windowsHide: true })).stdout
  let top
  try { top = (await git('rev-parse', '--show-toplevel')).trim() } catch { return null }
  if (await resolve(top) !== await resolve(directory)) throw new Error('Vault must be the Git repository root; parent repository was not changed')
  await git('add', '-A', '--', '.')
  const files = (await git('diff', '--cached', '--name-only', '-z')).split('\0').filter(Boolean)
  if (!files.length) return null
  const label = `${prefix}: ${files.slice(0, 3).map(f => f.split('/').pop()).join(', ')}${files.length > 3 ? ` +${files.length - 3} more` : ''}`
  await git('commit', '-q', '-m', label)
  return label
}
