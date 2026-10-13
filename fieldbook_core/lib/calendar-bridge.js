import { existsSync } from 'node:fs'
import path from 'node:path'
import { processJSON, root } from './notebook-bridge.js'

export function calendarPython(args, signal) {
  const venv = path.join(root, 'fieldbook_core', '.venv', process.platform === 'win32' ? 'Scripts/python.exe' : 'bin/python')
  const configured = process.env.FIELDBOOK_PYTHON
  if (configured && !path.isAbsolute(configured)) throw new Error('FIELDBOOK_PYTHON must be an absolute executable path')
  const executable = configured || (existsSync(venv) ? venv : process.platform === 'win32' ? 'python' : 'python3')
  return processJSON(executable, ['-I', '-B', path.join(root, 'fieldbook_core/scripts/calendar_service.py')], args, signal)
}

export async function calendar(args, context, run = calendarPython) {
  if (typeof context.ask !== 'function') throw new Error('Update OpenCode for custom-tool permission support')
  const pattern = `${args.provider}:${args.instance}:${args.mode || 'events'}`
  await context.ask({ permission: 'calendar_pull', patterns: [pattern], always: [pattern], metadata: {
    provider: args.provider, instance: args.instance, mode: args.mode || 'events',
    calendars: args.calendarIds || 'configured', start: args.start, end: args.end,
  } })
  return JSON.stringify(await run(args, context.abort))
}
