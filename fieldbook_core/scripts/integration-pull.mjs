// Fixed read-only adapters shared by every harness. No shell or caller-selected root.
import path from 'node:path'
import { fileURLToPath } from 'node:url'
import { pullTracker } from '../lib/tracker-service.js'
import { pullCanvas } from '../lib/canvas-service.js'
const root=path.resolve(path.dirname(fileURLToPath(import.meta.url)), '../..')
try {
 let input=''
 for await(const chunk of process.stdin){input+=chunk;if(Buffer.byteLength(input)>65536)throw Error('Request exceeds 64 KiB')}
 const {operation,...args}=JSON.parse(input)
 if(!['tracker_pull','canvas_pull'].includes(operation))throw Error('Unknown read operation')
 const result=await (operation==='tracker_pull'?pullTracker:pullCanvas)(args,root)
 const output=JSON.stringify(result)
 if(Buffer.byteLength(output)>2*1024*1024)throw Error('Response exceeds 2 MiB; narrow the request')
 console.log(output)
}catch(error){console.log(JSON.stringify({error:error.message}));process.exitCode=1}
