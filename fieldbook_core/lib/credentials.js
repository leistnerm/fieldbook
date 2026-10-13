import { spawn } from 'node:child_process'
import { existsSync } from 'node:fs'
import path from 'node:path'

const providers = ['jira', 'agility', 'github', 'azure', 'canvas']
function reference(provider, instance) {
  if (!providers.includes(provider) || !instance || typeof instance.id !== 'string' || !/^[A-Za-z0-9][A-Za-z0-9_-]{0,63}$/.test(instance.id)) throw Error('Invalid credential reference')
  if (typeof instance.baseUrl !== 'string' || /[\s\x00-\x1f\x7f\\]/.test(instance.baseUrl)) throw Error('Invalid credential destination')
  let url
  try { url = new URL(instance.baseUrl) } catch { throw Error('Invalid credential destination') }
  if (url.protocol !== 'https:' || !url.hostname || url.username || url.password || url.search || url.hash || url.port === '0') throw Error('Invalid credential destination')
  if (typeof instance.tokenVar !== 'string' || !new RegExp('^' + provider.toUpperCase() + '_[A-Z0-9_]+$').test(instance.tokenVar)) throw Error('Invalid credential reference')
  return { id: instance.id, baseUrl: instance.baseUrl, tokenVar: instance.tokenVar }
}
// This helper is private to the HTTP adapters. It is never registered as an AI tool.
export async function credentialEnvironment(root, provider, instance, env = process.env, signal, lookup = lookupCredential) {
  if (!providers.includes(provider) || !instance || !/^[A-Z][A-Z0-9_]+$/.test(instance.tokenVar || '') || !instance.tokenVar.startsWith(provider.toUpperCase() + '_')) throw Error('Invalid credential reference')
  const mode = instance.credentialStore || 'environment'
  if (mode === 'environment') return env
  if (mode !== 'keyring') throw Error('credentialStore must be environment or keyring')
  const expected = reference(provider, instance)
  const token = await lookup(root, provider, expected, env, signal)
  if (typeof token !== 'string' || !token || token.length > 16384 || /[\x00-\x1f\x7f]/.test(token)) throw Error('OS credential lookup returned an invalid key')
  return { ...env, [instance.tokenVar]: token }
}

export function lookupCredential(root, provider, instance, env = process.env, signal) {
  const expected = reference(provider, instance)
  const venv = path.join(root, 'fieldbook_core/.venv', process.platform === 'win32' ? 'Scripts/python.exe' : 'bin/python')
  if (env.FIELDBOOK_PYTHON && !path.isAbsolute(env.FIELDBOOK_PYTHON)) throw Error('FIELDBOOK_PYTHON must be an absolute executable path')
  const executable = env.FIELDBOOK_PYTHON || (existsSync(venv) ? venv : process.platform === 'win32' ? 'python' : 'python3')
  return new Promise((resolve, reject) => {
    const child = spawn(executable, ['-I', '-B', path.join(root, 'fieldbook_core/scripts/credentials.py')], {cwd:root, shell:false, windowsHide:true, signal, env:{...env, PYTHONDONTWRITEBYTECODE:'1'}})
    let output = '', failed = false
    const error = () => new Error('OS credential lookup failed. Check tools/configure.py and the vault Python credential dependency.')
    const timer = setTimeout(() => { failed = true; child.kill() }, 30_000)
    child.stdout.setEncoding('utf8')
    child.stdout.on('data', part => { output += part; if (Buffer.byteLength(output) > 32768) { failed = true; child.kill() } })
    child.stderr.resume() // Backend errors may contain sensitive details; never forward them.
    child.stdin.on('error', () => {})
    child.on('error', () => { clearTimeout(timer); reject(error()) })
    child.on('close', code => {
      clearTimeout(timer)
      if (failed || code !== 0) return reject(error())
      try { const value = JSON.parse(output); if (typeof value.token !== 'string') throw error(); resolve(value.token) }
      catch { reject(error()) }
    })
    child.stdin.end(JSON.stringify({provider,instance:expected}))
  })
}
