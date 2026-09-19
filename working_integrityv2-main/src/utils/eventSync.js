/**
 * eventSync.js — Ships the discrete edit-event stream to the server.
 *
 * Shared by SessionRecorder.vue (periodic + unmount flush) and EditorPage.vue
 * (final flush right before submit) so both paths advance the SAME
 * lastSyncedEventId marker in IndexedDB and never double-send a batch.
 *
 * Events are append-only on the server (one chunk document per batch), so a
 * retried batch after a failed marker write would at worst duplicate a chunk —
 * the playback merge sorts by (t, seq) and tolerates that.
 */
import { getEvents, getLastSyncedEventId, setLastSyncedEventId } from './snapshotDB'
import { getApiUrl } from './api-url'

const MAX_BATCH = 4000

function _stripLocal(ev) {
  // Local IndexedDB id doubles as the per-client sequence number.
  const { id, assignmentId: _aid, userId: _uid, ...data } = ev
  return { ...data, seq: id }
}

/**
 * Sync all unsynced events for (user, assignment) to the server.
 * @param {object} opts
 *   keepalive: use fetch keepalive (survives SPA navigation / page hide)
 * @returns number of events synced (0 when nothing new or on failure)
 */
export async function syncEvents(assignmentId, userId, opts = {}) {
  try {
    const API = getApiUrl()
    const token = localStorage.getItem('auth_token')
    if (!token || !assignmentId) return 0

    const lastId = await getLastSyncedEventId(assignmentId, userId)
    const pending = await getEvents(assignmentId, userId, lastId)
    if (pending.length === 0) return 0

    const url = `${API}/api/session-playback/assignment/${assignmentId}/events/sync`
    const headers = {
      'Content-Type': 'application/json',
      'Authorization': `Bearer ${token}`,
    }

    let synced = 0
    let off = 0
    while (off < pending.length) {
      let size = Math.min(MAX_BATCH, pending.length - off)
      let batch = pending.slice(off, off + size)
      let body = JSON.stringify({ events: batch.map(_stripLocal) })
      let useKeepalive = !!opts.keepalive

      if (useKeepalive) {
        // keepalive request bodies are capped at ~64KB — shrink the batch
        // until it fits; a single oversized event (a full-text checkpoint)
        // falls back to a normal fetch, which has no body cap.
        while (size > 1 && new TextEncoder().encode(body).length > 60000) {
          size = Math.ceil(size / 2)
          batch = pending.slice(off, off + size)
          body = JSON.stringify({ events: batch.map(_stripLocal) })
        }
        if (size === 1 && new TextEncoder().encode(body).length > 60000) {
          useKeepalive = false
        }
      }

      const res = await fetch(url, { method: 'POST', keepalive: useKeepalive, headers, body })
      if (!res.ok) break
      // Advance the marker after every accepted batch so a mid-run failure
      // never re-sends what the server already stored.
      await setLastSyncedEventId(assignmentId, userId, batch[batch.length - 1].id)
      synced += batch.length
      off += size
    }
    return synced
  } catch (err) {
    console.warn('[eventSync] sync failed (non-critical):', err?.message || err)
    return 0
  }
}
