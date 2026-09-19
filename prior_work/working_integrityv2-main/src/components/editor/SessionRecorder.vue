<template>
  <!-- Invisible component — captures document snapshots for session playback -->
</template>

<script setup>
/**
 * SessionRecorder.vue — High-frequency document snapshot capture for session playback.
 *
 * Captures a snapshot on EVERY text change (throttled to 200ms) so that playback
 * can show character-by-character typing, instant pastes, and deletions.
 *
 * Snapshots are stored locally in IndexedDB AND synced to MongoDB every 30 seconds
 * for cross-browser persistence. On submission, remaining snapshots are uploaded.
 *
 * SAFETY: Read-only. Never mutates editor or window globals.
 */

import { onMounted, onBeforeUnmount, watch } from 'vue'
import { useStore } from '@/composables/store'
import { saveSnapshot, getSnapshots, getSnapshotCount, clearSnapshots, saveEvent } from '@/utils/snapshotDB'
import { syncEvents } from '@/utils/eventSync'
import { isRemoteTransaction } from '@/extensions/authorship'
import axios from 'axios'
import { getApiUrl } from '@/utils/api-url'

const props = defineProps({
  assignmentId: { type: String, required: true },
  userId: { type: String, default: null }
})

const { editor } = useStore()
const API = getApiUrl()

/**
 * Resolve the user id for snapshot scoping: prefer the prop (parent wiring
 * happens elsewhere); if absent, fall back to the locally stored user id
 * (same key documentService.js reads). Returns null when neither exists.
 */
function resolveUserId() {
  if (props.userId) return props.userId
  try {
    const stored = localStorage.getItem('user_id')
    if (stored) return stored
  } catch { /* localStorage unavailable */ }
  return null
}

let lastPlaintext = ''
let lastSnapshotTime = 0
let throttleTimer = null
let fullSnapshotTimer = null
let serverSyncTimer = null
let lastSyncTimestamp = 0  // Track by timestamp, not count (fixes ring buffer wrap bug)

const THROTTLE_MS = 200        // Capture at most every 200ms (5 snapshots/sec)
const FULL_SNAPSHOT_MS = 15000  // Full snapshot with HTML + timeline every 15s
const SERVER_SYNC_MS = 30000    // Sync to MongoDB every 30 seconds

function countWords(text) {
  if (!text) return 0
  return text.trim().split(/\s+/).filter(Boolean).length
}

function payloadBytes(str) {
  try {
    return new TextEncoder().encode(str).length
  } catch {
    return str.length
  }
}

/**
 * Lightweight snapshot — just plaintext + counts.
 * Called on every keystroke (throttled). ~200 bytes each.
 */
function captureLightSnapshot() {
  const ed = editor.value
  if (!ed || ed.isDestroyed) return

  const plaintext = ed.getText() || ''
  if (plaintext === lastPlaintext) return

  const now = Date.now()
  saveSnapshot(props.assignmentId, {
    timestamp: now,
    plaintext,
    wordCount: countWords(plaintext),
    cursorPos: ed.state?.selection?.from || 0,
    typedCount: window.TYPED_DB?.totalTypedCount || 0,
    pasteCount: window.EXTERNAL_DB?.pastes?.length || 0,
  }, resolveUserId())

  lastPlaintext = plaintext
  lastSnapshotTime = now
}

/**
 * Full snapshot — includes HTML content + timeline segments.
 * Called every 15s for rich data. ~5-20KB each.
 */
function captureFullSnapshot() {
  const ed = editor.value
  if (!ed || ed.isDestroyed) return

  const plaintext = ed.getText() || ''
  const now = Date.now()
  saveSnapshot(props.assignmentId, {
    timestamp: now,
    plaintext,
    content: ed.getHTML(),
    wordCount: countWords(plaintext),
    cursorPos: ed.state?.selection?.from || 0,
    timelineSegments: Array.isArray(window.TIMELINE_DB?.segments)
      ? window.TIMELINE_DB.segments.map(s => ({
          text: s.text, timestamp: s.timestamp,
          duration: s.duration, wpm: s.wpm, type: s.type
        }))
      : [],
    typedCount: window.TYPED_DB?.totalTypedCount || 0,
    pasteCount: window.EXTERNAL_DB?.pastes?.length || 0,
    _full: true,
  }, resolveUserId())

  lastPlaintext = plaintext
  lastSnapshotTime = now
}

/**
 * Sync new snapshots to MongoDB for cross-browser persistence.
 * Uses timestamp-based tracking (not index-based) so it works correctly
 * even after the ring buffer wraps and old snapshots are evicted.
 */
async function syncToServer() {
  try {
    const allSnapshots = await getSnapshots(props.assignmentId, resolveUserId())
    if (allSnapshots.length === 0) return

    // Find snapshots newer than the last sync timestamp
    const newSnapshots = allSnapshots
      .filter(s => s.timestamp > lastSyncTimestamp)
      .map(s => {
        const { id, assignmentId: _aid, userId: _uid, ...data } = s
        return data
      })

    if (newSnapshots.length === 0) return

    await axios.post(
      `${API}/api/session-playback/assignment/${props.assignmentId}/sync`,
      { snapshots: newSnapshots }
    )

    // Update sync timestamp to the latest snapshot we sent
    lastSyncTimestamp = newSnapshots[newSnapshots.length - 1].timestamp
  } catch (err) {
    // Non-critical — local IndexedDB still has the data
    console.warn('[SessionRecorder] Server sync failed (non-critical):', err.message)
  }
}

/**
 * Restore snapshots from server on mount (cross-browser support).
 * If this is a new browser, seed IndexedDB from server data.
 */
async function restoreFromServer() {
  try {
    const localCount = await getSnapshotCount(props.assignmentId, resolveUserId())
    if (localCount > 0) {
      // Already have local data — set sync timestamp to now so we only sync future snapshots
      const localSnapshots = await getSnapshots(props.assignmentId, resolveUserId())
      if (localSnapshots.length > 0) {
        lastSyncTimestamp = localSnapshots[localSnapshots.length - 1].timestamp
      }
      return
    }

    // No local data — try to fetch from server
    const res = await axios.get(`${API}/api/session-playback/assignment/${props.assignmentId}`)
    if (res.data.found && res.data.snapshots?.length > 0) {
      // Seed IndexedDB from server
      for (const snap of res.data.snapshots) {
        await saveSnapshot(props.assignmentId, snap, resolveUserId())
      }
      lastSyncTimestamp = res.data.snapshots[res.data.snapshots.length - 1].timestamp || Date.now()
      console.log(`[SessionRecorder] Restored ${res.data.snapshots.length} snapshots from server`)
    }
  } catch (err) {
    console.warn('[SessionRecorder] Server restore failed (non-critical):', err.message)
  }
}

/**
 * Throttled handler for editor updates — fires on every keystroke.
 */
function onEditorUpdate() {
  if (throttleTimer) return
  throttleTimer = setTimeout(() => {
    throttleTimer = null
    captureLightSnapshot()
  }, THROTTLE_MS)
}

// ════════════════════════════════════════════════════════════════
// Discrete edit-event stream (true char-by-char fidelity).
//
// Every LOCAL editor transaction that changes the text becomes one event
// { t, p, d, i, k }: at time t, at plaintext offset p, d chars were deleted
// and text i was inserted (k = 'type' | 'paste' | 'ckpt'). Remote (Yjs)
// transactions are skipped — each collab participant records only their own
// edits, so the server-side merge attributes every event to its real author.
//
// 'ckpt' events carry the full plaintext so replay can always resync from
// ground truth (session start, browser switches, collab merge seams).
// ════════════════════════════════════════════════════════════════

const CKPT_EVERY_EVENTS = 300
const CKPT_EVERY_MS = 120000

let lastEventText = null       // null until the editor is attached
let eventsSinceCkpt = 0
let lastCkptTime = 0

/**
 * Single-region diff via common prefix/suffix trimming. Editor transactions
 * are (near-)contiguous changes, so this is exact for typing/paste/delete
 * and always converges to the true text even for multi-region transactions.
 */
function diffOnce(oldStr, newStr) {
  let start = 0
  const minLen = Math.min(oldStr.length, newStr.length)
  while (start < minLen && oldStr.charCodeAt(start) === newStr.charCodeAt(start)) start++
  let endOld = oldStr.length
  let endNew = newStr.length
  while (endOld > start && endNew > start &&
         oldStr.charCodeAt(endOld - 1) === newStr.charCodeAt(endNew - 1)) {
    endOld--
    endNew--
  }
  return { pos: start, del: endOld - start, ins: newStr.slice(start, endNew) }
}

function recordCheckpoint(text) {
  saveEvent(props.assignmentId, {
    t: Date.now(), p: 0, d: 0, i: text, k: 'ckpt',
  }, resolveUserId())
  eventsSinceCkpt = 0
  lastCkptTime = Date.now()
}

function onEditorTransaction({ transaction }) {
  try {
    if (!transaction || !transaction.docChanged) return
    const ed = editor.value
    if (!ed || ed.isDestroyed) return

    const newText = ed.getText() || ''

    // Remote co-author edits shift our local base text but are NOT ours to
    // record — the co-author's own recorder captures them as local events.
    if (isRemoteTransaction(transaction)) {
      lastEventText = newText
      return
    }

    // Mark-only / metadata transactions don't change the text — skip.
    if (lastEventText === null) { lastEventText = newText; return }
    if (newText === lastEventText) return

    const { pos, del, ins } = diffOnce(lastEventText, newText)
    const uiEvent = transaction.getMeta('uiEvent')
    const kind = (uiEvent === 'paste' || uiEvent === 'drop') ? 'paste' : 'type'

    // Programmatic whole-document loads (draft restore, setContent) are
    // local transactions but NOT user work — record them as a checkpoint so
    // replay starts from the restored text instead of showing a giant
    // "paste". Real pastes carry the uiEvent meta and never hit this branch.
    const wholeDocReplace = pos === 0 && del === lastEventText.length && ins === newText
    if (kind !== 'paste' && wholeDocReplace && ins.length > 200) {
      lastEventText = newText
      recordCheckpoint(newText)
      return
    }

    saveEvent(props.assignmentId, {
      t: Date.now(), p: pos, d: del, i: ins, k: kind,
    }, resolveUserId())
    lastEventText = newText

    eventsSinceCkpt++
    if (eventsSinceCkpt >= CKPT_EVERY_EVENTS ||
        (eventsSinceCkpt > 0 && Date.now() - lastCkptTime > CKPT_EVERY_MS)) {
      recordCheckpoint(newText)
    }
  } catch (err) {
    // The recorder must never break editing.
    console.warn('[SessionRecorder] event capture failed:', err?.message || err)
  }
}

/** Attach event capture to a ready editor: ground-truth checkpoint first. */
function attachEventStream(ed) {
  lastEventText = ed.getText() || ''
  recordCheckpoint(lastEventText)
  ed.on('transaction', onEditorTransaction)
}

onMounted(async () => {
  // Restore from server first (cross-browser support)
  await restoreFromServer()

  // Full snapshots on a timer
  fullSnapshotTimer = setInterval(captureFullSnapshot, FULL_SNAPSHOT_MS)

  // Periodic server sync — snapshots and the discrete event stream
  serverSyncTimer = setInterval(() => {
    syncToServer()
    syncEvents(props.assignmentId, resolveUserId())
  }, SERVER_SYNC_MS)

  if (editor.value && !editor.value.isDestroyed) {
    captureFullSnapshot()
    editor.value.on('update', onEditorUpdate)
    attachEventStream(editor.value)
    return
  }

  // Wait for editor
  let editorReady = false
  const unwatch = watch(
    () => editor.value,
    (ed) => {
      if (ed && !ed.isDestroyed && !editorReady) {
        editorReady = true
        captureFullSnapshot()
        ed.on('update', onEditorUpdate)
        attachEventStream(ed)
        queueMicrotask(() => unwatch())
      }
    },
    { immediate: true }
  )
})

onBeforeUnmount(() => {
  if (throttleTimer) { clearTimeout(throttleTimer); throttleTimer = null }
  if (fullSnapshotTimer) { clearInterval(fullSnapshotTimer); fullSnapshotTimer = null }
  if (serverSyncTimer) { clearInterval(serverSyncTimer); serverSyncTimer = null }

  captureFullSnapshot()

  // Final sync via fetch keepalive — survives page navigation AND (unlike
  // sendBeacon) can carry the Authorization header the backend requires.
  // sendBeacon cannot set headers, so the backend 401'd and the final
  // snapshot was silently lost.
  try {
    const token = localStorage.getItem('auth_token')
    if (token && lastPlaintext) {
      const ed = editor.value
      const snap = {
        timestamp: Date.now(),
        plaintext: lastPlaintext,
        content: ed && !ed.isDestroyed ? ed.getHTML() : undefined,
        wordCount: countWords(lastPlaintext),
        typedCount: window.TYPED_DB?.totalTypedCount || 0,
        pasteCount: window.EXTERNAL_DB?.pastes?.length || 0,
        _full: true,
      }
      let payload = JSON.stringify({ snapshots: [snap] })
      // keepalive request bodies are capped at ~64KB — if we're over the
      // limit, drop the HTML content field and send plaintext-only.
      if (payloadBytes(payload) > 60000) {
        delete snap.content
        payload = JSON.stringify({ snapshots: [snap] })
      }
      const url = `${API}/api/session-playback/assignment/${props.assignmentId}/sync`
      fetch(url, {
        method: 'POST',
        keepalive: true,
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${token}`,
        },
        body: payload,
      }).catch(() => {})
    }
  } catch { /* best effort */ }

  // Final event-stream flush — keepalive so it survives SPA navigation.
  syncEvents(props.assignmentId, resolveUserId(), { keepalive: true })

  const ed = editor.value
  if (ed && !ed.isDestroyed) {
    ed.off('update', onEditorUpdate)
    ed.off('transaction', onEditorTransaction)
  }
})
</script>

<style scoped>/* Invisible */</style>
