import { once } from 'node:events'
import { spawn } from 'node:child_process'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

const __filename = fileURLToPath(import.meta.url)
const __dirname = path.dirname(__filename)
const frontendRoot = path.resolve(__dirname, '..')
const backendRoot = path.resolve(frontendRoot, '..', 'backend')
const schemaUrl = 'http://localhost:8000/openapi.json'
const backendPython = path.join(backendRoot, '.venv', 'bin', 'python')

async function canReachSchema() {
  try {
    const response = await fetch(schemaUrl, { signal: AbortSignal.timeout(1_000) })
    return response.ok
  } catch {
    return false
  }
}

async function waitForSchema(timeoutMs = 20_000) {
  const deadline = Date.now() + timeoutMs
  while (Date.now() < deadline) {
    if (await canReachSchema()) {
      return
    }
    await new Promise((resolve) => setTimeout(resolve, 400))
  }

  throw new Error(`OpenAPI schema not reachable at ${schemaUrl} within ${timeoutMs} ms`)
}

function runCommand(command, args, options = {}) {
  return new Promise((resolve, reject) => {
    const child = spawn(command, args, {
      stdio: 'inherit',
      ...options,
    })

    child.on('error', reject)
    child.on('exit', (code, signal) => {
      if (code === 0) {
        resolve()
        return
      }
      reject(
        new Error(`${command} exited with code ${code ?? 'null'} and signal ${signal ?? 'null'}`),
      )
    })
  })
}

async function stopServer(child) {
  if (child.exitCode !== null || child.killed) {
    return
  }

  child.kill('SIGTERM')
  const settled = Promise.race([
    once(child, 'exit'),
    new Promise((resolve) => setTimeout(resolve, 5_000)),
  ])
  await settled

  if (child.exitCode === null && !child.killed) {
    child.kill('SIGKILL')
    await once(child, 'exit')
  }
}

async function main() {
  let backendProcess = null
  let startedBackend = false

  try {
    if (await canReachSchema()) {
      console.log('Using existing backend at http://localhost:8000')
    } else {
      console.log('Starting temporary backend for OpenAPI generation...')
      backendProcess = spawn(
        backendPython,
        ['-m', 'uvicorn', 'cimiento.api.main:app', '--app-dir', 'src', '--host', '127.0.0.1', '--port', '8000'],
        {
          cwd: backendRoot,
          env: {
            ...process.env,
            DATABASE_URL: 'sqlite+aiosqlite:///:memory:',
          },
          stdio: 'inherit',
        },
      )
      startedBackend = true
      await waitForSchema()
    }

    await runCommand('npm', ['run', 'gen:types'], { cwd: frontendRoot })
    console.log('Generated src/types/api.generated.ts')
  } finally {
    if (startedBackend && backendProcess) {
      console.log('Stopping temporary backend...')
      await stopServer(backendProcess)
    }
  }
}

main().catch((error) => {
  console.error(error instanceof Error ? error.message : error)
  process.exitCode = 1
})