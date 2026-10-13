import { spawn } from 'node:child_process'
import { existsSync } from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'
import { pullTracker } from './tracker-service.js'

export const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '../..')

// Fixed executables and scripts; no shell interpolation, command text, or model-selected root.
export function processJSON(executable, argv, input, signal) {
  return new Promise((resolve, reject) => {
    const child = spawn(executable, argv, { cwd: root, shell: false, windowsHide: true, signal,
      env: { ...process.env, PYTHONDONTWRITEBYTECODE: '1' } })
    let output = '', error = '', bytes = 0, failure
    child.stdout.setEncoding('utf8')
    child.stderr.setEncoding('utf8')
    const timeout = setTimeout(() => { failure = new Error('Tool exceeded 45 seconds; narrow the request'); child.kill() }, 45_000)
    child.stdout.on('data', data => {
      bytes += Buffer.byteLength(data, 'utf8')
      if (bytes > 2 * 1024 * 1024) { failure = new Error('Tool output exceeds 2 MiB; use a smaller limit'); child.kill() }
      else output += data
    })
    child.stderr.on('data', data => { error = (error + data.toString('utf8')).slice(0, 4000) })
    child.on('error', e => { clearTimeout(timeout); reject(e) })
    child.stdin.on('error', () => {}) // Early process exit is handled by close.
    child.on('close', code => {
      clearTimeout(timeout)
      if (failure) return reject(failure)
      try {
        const result = output ? JSON.parse(output) : undefined
        if (code !== 0 || result?.error) throw new Error(result?.error || error || `Tool exited ${code}`)
        resolve(result)
      } catch (e) { reject(new Error(e.message || error)) }
    })
    child.stdin.end(input === undefined ? '' : JSON.stringify(input))
  })
}

export function python(args, signal) {
  const venv = path.join(root, 'fieldbook_core', '.venv', process.platform === 'win32' ? 'Scripts/python.exe' : 'bin/python')
  const configured = process.env.FIELDBOOK_PYTHON
  if (configured && !path.isAbsolute(configured)) throw new Error('FIELDBOOK_PYTHON must be an absolute executable path, without arguments')
  const executable = configured || (existsSync(venv) ? venv : process.platform === 'win32' ? 'python' : 'python3')
  return processJSON(executable, ['-I', '-B', path.join(root, 'fieldbook_core/scripts/notebook.py')], args, signal)
}

export async function notebook(operation, args, context, run = python) {
  if (typeof context.ask !== 'function') throw new Error('This OpenCode version lacks custom-tool permission support; update OpenCode')
  if (operation === 'write') {
    const preview = await run({ ...args, operation: 'preview' }, context.abort)
    await context.ask({ permission: 'notebook_write', patterns: [args.path], always: [args.path], metadata: preview })
    return JSON.stringify(await run({ ...args, operation: 'write' }, context.abort))
  }
  await context.ask({ permission: `notebook_${operation}`, patterns: [args.path || args.topic || '*'], always: ['*'], metadata: {} })
  return JSON.stringify(await run({ ...args, operation }, context.abort))
}

export async function tracker(args, context, run = pullTracker) {
  await context.ask({ permission: 'tracker_pull', patterns: [`${args.provider}:${args.instance}:${args.scope}`],
    always: [`${args.provider}:${args.instance}:${args.scope}`], metadata: { provider: args.provider, instance: args.instance, scope: args.scope } })
  // Executes within OpenCode's JavaScript runtime; no separate Node installation or shell.
  return JSON.stringify(await run(args, root, context.abort))
}
