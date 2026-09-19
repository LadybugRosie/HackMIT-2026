import { mkdirSync } from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

import { Server } from '@hocuspocus/server'
import { SQLite } from '@hocuspocus/extension-sqlite'

const PORT = Number.parseInt(process.env.PORT ?? '1235', 10)
const HOST = '0.0.0.0'
const BACKEND_URL = process.env.BACKEND_URL || 'http://localhost:8080'
const AUTH_TIMEOUT_MS = 10_000

// Document names look like "topic:<assignment_id>" (uuid-ish, hex + dashes).
const DOCUMENT_NAME_PATTERN = /^topic:[0-9a-f-]+$/

// Persist Yjs documents to SQLite in DATA_DIR (default: ./data next to this file).
const dataDir = process.env.DATA_DIR
  ? path.resolve(process.env.DATA_DIR)
  : path.join(path.dirname(fileURLToPath(import.meta.url)), 'data')
mkdirSync(dataDir, { recursive: true })
const databasePath = path.join(dataDir, 'collab.sqlite')

const server = new Server({
  port: PORT,
  address: HOST,
  // We register our own SIGINT/SIGTERM handlers below for logged, graceful shutdown.
  stopOnSignals: false,

  extensions: [
    new SQLite({ database: databasePath }),
  ],

  /**
   * Authenticate every connecting client against the Editorrah FastAPI backend.
   * The provider sends { token } which we forward as a Bearer token to
   * GET /api/research/collab-access/<assignment_id>.
   */
  async onAuthenticate({ token, documentName }) {
    if (!DOCUMENT_NAME_PATTERN.test(documentName)) {
      throw new Error(`Invalid document name: ${documentName}`)
    }
    if (!token) {
      throw new Error('Missing authentication token')
    }

    const assignmentId = documentName.slice('topic:'.length)

    let response
    try {
      response = await fetch(
        `${BACKEND_URL}/api/research/collab-access/${assignmentId}`,
        {
          headers: { Authorization: `Bearer ${token}` },
          signal: AbortSignal.timeout(AUTH_TIMEOUT_MS),
        },
      )
    } catch (error) {
      console.error(`[collab] auth request failed for ${documentName}: ${error.message}`)
      throw new Error('Authorization service unreachable')
    }

    if (!response.ok) {
      throw new Error(`Not authorized for ${documentName} (backend returned ${response.status})`)
    }

    let payload
    try {
      payload = await response.json()
    } catch {
      throw new Error('Invalid response from authorization service')
    }

    if (!payload?.allowed) {
      throw new Error(`Not authorized for ${documentName}`)
    }

    // Becomes available as `context` in subsequent hooks.
    return { user: payload.user }
  },

  async connected({ documentName, context }) {
    console.log(`[collab] connected: ${documentName} (user: ${context?.user?.name ?? 'unknown'})`)
  },

  async onDisconnect({ documentName, context, clientsCount }) {
    console.log(
      `[collab] disconnected: ${documentName} (user: ${context?.user?.name ?? 'unknown'}, remaining clients: ${clientsCount})`,
    )
  },
})

let shuttingDown = false
async function shutdown(signal) {
  if (shuttingDown) return
  shuttingDown = true
  console.log(`[collab] received ${signal}, shutting down gracefully...`)
  try {
    await server.destroy()
    console.log('[collab] shutdown complete')
    process.exit(0)
  } catch (error) {
    console.error(`[collab] error during shutdown: ${error.message}`)
    process.exit(1)
  }
}
process.on('SIGINT', () => shutdown('SIGINT'))
process.on('SIGTERM', () => shutdown('SIGTERM'))

await server.listen()
console.log(`[collab] Editorrah collab server listening on ws://${HOST}:${PORT}`)
console.log(`[collab] backend: ${BACKEND_URL}`)
console.log(`[collab] persistence: ${databasePath}`)
