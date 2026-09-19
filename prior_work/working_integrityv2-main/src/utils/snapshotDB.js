/**
 * snapshotDB.js — IndexedDB wrapper for session playback snapshots
 *
 * Stores periodic document snapshots during editing sessions.
 * Used by SessionRecorder.vue to capture and by SessionPlayback.vue to replay.
 */

const DB_NAME = 'editorrah_session_playback'
const DB_VERSION = 3
const STORE_NAME = 'snapshots'
const EVENTS_STORE = 'events'
const SYNC_META_STORE = 'sync_meta'
const MAX_SNAPSHOTS = 5000  // ~16 min at 5 snapshots/sec
// Discrete edit events are tiny (~40-100 bytes); 60k covers hours of typing.
const MAX_EVENTS = 60000
const EVENTS_EVICT_BATCH = 5000

let dbInstance = null
const IDB_AVAILABLE = typeof indexedDB !== 'undefined'

function openDB() {
  if (!IDB_AVAILABLE) return Promise.reject(new Error('IndexedDB not available'))
  if (dbInstance) return Promise.resolve(dbInstance)

  return new Promise((resolve, reject) => {
    const request = indexedDB.open(DB_NAME, DB_VERSION)

    request.onupgradeneeded = (e) => {
      const db = e.target.result
      const oldVersion = e.oldVersion

      if (oldVersion < 1) {
        const store = db.createObjectStore(STORE_NAME, { keyPath: 'id', autoIncrement: true })
        store.createIndex('assignmentId', 'assignmentId', { unique: false })
        store.createIndex('timestamp', 'timestamp', { unique: false })
      }

      if (oldVersion < 2) {
        const store = e.target.transaction.objectStore(STORE_NAME)
        store.createIndex('userAssignment', ['userId', 'assignmentId'], { unique: false })
      }

      if (oldVersion < 3) {
        // Discrete edit-event stream (char-by-char fidelity). Events are
        // deltas — order matters, so the autoincrement id doubles as a
        // per-client sequence number.
        const evStore = db.createObjectStore(EVENTS_STORE, { keyPath: 'id', autoIncrement: true })
        evStore.createIndex('userAssignment', ['userId', 'assignmentId'], { unique: false })
        // Tracks the last event id synced to the server per (user, assignment)
        // so SessionRecorder and the submit flow never double-send.
        db.createObjectStore(SYNC_META_STORE, { keyPath: 'key' })
      }
    }

    request.onsuccess = (e) => {
      dbInstance = e.target.result
      // Reset cached instance if browser closes the connection externally
      dbInstance.onclose = () => { dbInstance = null }
      dbInstance.onversionchange = () => { dbInstance.close(); dbInstance = null }
      resolve(dbInstance)
    }

    request.onerror = (e) => {
      console.error('[SnapshotDB] Failed to open:', e.target.error)
      reject(e.target.error)
    }
  })
}

/**
 * Save a snapshot for an assignment editing session.
 * Enforces MAX_SNAPSHOTS by THINNING: instead of always dropping the oldest
 * snapshot (which erases the beginning of long sessions), it scans the oldest
 * records and removes the first non-keyframe one, preserving the session
 * start and _full keyframes.
 * All operations in a SINGLE readwrite transaction to prevent race conditions.
 */
export async function saveSnapshot(assignmentId, snapshot, userId = null) {
  if (!IDB_AVAILABLE) return
  try {
    const db = await openDB()
    const tx = db.transaction(STORE_NAME, 'readwrite')
    const store = tx.objectStore(STORE_NAME)

    // Use user-scoped index when userId available, otherwise fall back to assignmentId-only
    let countReq, cursorKeyRange
    if (userId) {
      const uaIndex = store.index('userAssignment')
      cursorKeyRange = IDBKeyRange.only([userId, assignmentId])
      countReq = uaIndex.count(cursorKeyRange)
    } else {
      const index = store.index('assignmentId')
      cursorKeyRange = IDBKeyRange.only(assignmentId)
      countReq = index.count(cursorKeyRange)
    }

    const count = await new Promise((resolve, reject) => {
      countReq.onsuccess = () => resolve(countReq.result)
      countReq.onerror = () => reject(countReq.error)
    })

    // If at max, THIN instead of deleting the oldest (same transaction):
    // scan the oldest 50 records and delete the first one that is neither a
    // _full keyframe nor the very first record of the session. If every
    // scanned record is protected, fall back to deleting the oldest.
    if (count >= MAX_SNAPSHOTS) {
      const indexForCursor = userId
        ? store.index('userAssignment')
        : store.index('assignmentId')
      const cursorReq = indexForCursor.openCursor(cursorKeyRange)
      await new Promise((resolve, reject) => {
        let scanned = 0
        let isFirstRecord = true
        let oldestPrimaryKey = null

        const deleteOldest = () => {
          if (oldestPrimaryKey === null) { resolve(); return }
          const delReq = store.delete(oldestPrimaryKey)
          delReq.onsuccess = () => resolve()
          delReq.onerror = () => reject(delReq.error)
        }

        cursorReq.onsuccess = (e) => {
          const cursor = e.target.result
          if (!cursor) {
            // Exhausted before finding an evictable record
            deleteOldest()
            return
          }
          if (oldestPrimaryKey === null) oldestPrimaryKey = cursor.primaryKey
          const isProtected = cursor.value?._full === true || isFirstRecord
          isFirstRecord = false
          scanned++
          if (!isProtected) {
            cursor.delete()
            resolve()
            return
          }
          if (scanned >= 50) {
            deleteOldest()
            return
          }
          cursor.continue()
        }
        cursorReq.onerror = () => reject(cursorReq.error)
      })
    }

    // Add the new snapshot (same transaction)
    const { assignmentId: _dropped, id: _dropped2, userId: _dropped3, ...safeSnapshot } = snapshot
    const record = { ...safeSnapshot, assignmentId, userId }
    store.add(record)

    // Wait for the single transaction to complete
    await new Promise((resolve, reject) => {
      tx.oncomplete = resolve
      tx.onerror = () => reject(tx.error)
    })
  } catch (err) {
    console.error('[SnapshotDB] saveSnapshot failed:', err)
  }
}

/**
 * Get all snapshots for an assignment, sorted by timestamp ascending.
 */
export async function getSnapshots(assignmentId, userId = null) {
  if (!IDB_AVAILABLE) return []
  try {
    const db = await openDB()
    const tx = db.transaction(STORE_NAME, 'readonly')
    const store = tx.objectStore(STORE_NAME)

    let request
    if (userId) {
      const uaIndex = store.index('userAssignment')
      request = uaIndex.getAll(IDBKeyRange.only([userId, assignmentId]))
    } else {
      const index = store.index('assignmentId')
      request = index.getAll(IDBKeyRange.only(assignmentId))
    }

    const results = await new Promise((resolve, reject) => {
      request.onsuccess = () => resolve(request.result)
      request.onerror = () => reject(request.error)
    })

    return results.sort((a, b) => a.timestamp - b.timestamp)
  } catch (err) {
    console.error('[SnapshotDB] getSnapshots failed:', err)
    return []
  }
}

/**
 * Get count of snapshots for an assignment (cheaper than getAll).
 */
export async function getSnapshotCount(assignmentId, userId = null) {
  if (!IDB_AVAILABLE) return 0
  try {
    const db = await openDB()
    const tx = db.transaction(STORE_NAME, 'readonly')
    const store = tx.objectStore(STORE_NAME)

    let countReq
    if (userId) {
      countReq = store.index('userAssignment').count(IDBKeyRange.only([userId, assignmentId]))
    } else {
      countReq = store.index('assignmentId').count(IDBKeyRange.only(assignmentId))
    }

    return await new Promise((resolve, reject) => {
      countReq.onsuccess = () => resolve(countReq.result)
      countReq.onerror = () => reject(countReq.error)
    })
  } catch {
    return 0
  }
}

/**
 * Clear all snapshots for an assignment (call after successful submission upload).
 */
export async function clearSnapshots(assignmentId, userId = null) {
  if (!IDB_AVAILABLE) return
  try {
    const db = await openDB()
    const tx = db.transaction(STORE_NAME, 'readwrite')
    const store = tx.objectStore(STORE_NAME)

    let cursorReq
    if (userId) {
      const uaIndex = store.index('userAssignment')
      cursorReq = uaIndex.openCursor(IDBKeyRange.only([userId, assignmentId]))
    } else {
      const index = store.index('assignmentId')
      cursorReq = index.openCursor(IDBKeyRange.only(assignmentId))
    }

    await new Promise((resolve, reject) => {
      cursorReq.onsuccess = (e) => {
        const cursor = e.target.result
        if (cursor) {
          cursor.delete()
          cursor.continue()
        } else {
          resolve()
        }
      }
      cursorReq.onerror = () => reject(cursorReq.error)
    })
  } catch (err) {
    console.error('[SnapshotDB] clearSnapshots failed:', err)
  }
}

/**
 * Export snapshots as a compressed array for upload to backend.
 * First snapshot is full, subsequent snapshots store only plaintext diffs
 * and changed metadata to reduce payload size ~80%.
 * A full keyframe (plaintext + content) is re-emitted at least every
 * EXPORT_KEYFRAME_EVERY snapshots even when unchanged, so delta
 * reconstruction chains can't break if intermediate records are lost.
 */
const EXPORT_KEYFRAME_EVERY = 200

export async function exportSnapshots(assignmentId, userId = null) {
  const snapshots = await getSnapshots(assignmentId, userId)
  if (snapshots.length === 0) return null

  const exported = []
  let prevPlaintext = ''

  for (let i = 0; i < snapshots.length; i++) {
    const snap = snapshots[i]
    // Strip IndexedDB internal fields
    const { id, assignmentId: _aid, userId: _uid, ...data } = snap

    if (i === 0) {
      // First snapshot: full content
      exported.push({ ...data, _full: true })
    } else {
      // Subsequent: only include plaintext if changed (or on a forced keyframe)
      const delta = {}
      delta.timestamp = data.timestamp
      delta.wordCount = data.wordCount
      delta.cursorPos = data.cursorPos
      delta.typedCount = data.typedCount
      delta.pasteCount = data.pasteCount

      const forceKeyframe = i % EXPORT_KEYFRAME_EVERY === 0
      if (forceKeyframe || data.plaintext !== prevPlaintext) {
        delta.plaintext = data.plaintext !== undefined ? data.plaintext : prevPlaintext
        delta.content = data.content
        if (forceKeyframe) delta._full = true
      }

      // Include timeline segments only if count changed
      if (data.timelineSegments?.length !== snapshots[i - 1].timelineSegments?.length) {
        delta.timelineSegments = data.timelineSegments
      }

      exported.push(delta)
    }
    prevPlaintext = data.plaintext || prevPlaintext
  }

  return {
    version: 1,
    assignmentId,
    snapshotCount: exported.length,
    totalDurationMs: snapshots.length > 1
      ? snapshots[snapshots.length - 1].timestamp - snapshots[0].timestamp
      : 0,
    snapshots: exported
  }
}

// ════════════════════════════════════════════════════════════════
// Discrete edit-event stream (session playback v2 — char-by-char)
//
// Each event is a plaintext-space delta:
//   { t, p, d, i, k, a }
//   t = epoch ms, p = plaintext offset, d = deleted char count,
//   i = inserted text ('' for pure delete), k = 'type'|'paste'|'ckpt',
//   a = author user id (attribution survives collab merges)
// 'ckpt' events carry the FULL plaintext in `i` so replay can always
// resync from ground truth (start of session, resumes, cap evictions).
// ════════════════════════════════════════════════════════════════

let _saveCounter = 0

/**
 * Append one edit event. The autoincrement id is the per-client sequence
 * number. Every 500 saves, enforce MAX_EVENTS by evicting the oldest batch
 * (they are deltas, so eviction is only safe because sync has already
 * shipped them and replay restarts from the next 'ckpt' event).
 */
export async function saveEvent(assignmentId, event, userId = null) {
  if (!IDB_AVAILABLE) return
  try {
    const db = await openDB()
    const tx = db.transaction(EVENTS_STORE, 'readwrite')
    const store = tx.objectStore(EVENTS_STORE)
    store.add({ ...event, assignmentId, userId })
    await new Promise((resolve, reject) => {
      tx.oncomplete = resolve
      tx.onerror = () => reject(tx.error)
    })

    _saveCounter++
    if (_saveCounter % 500 === 0) {
      const count = await countEvents(assignmentId, userId)
      if (count > MAX_EVENTS) await _evictOldestEvents(assignmentId, userId, EVENTS_EVICT_BATCH)
    }
  } catch (err) {
    console.error('[SnapshotDB] saveEvent failed:', err)
  }
}

async function _evictOldestEvents(assignmentId, userId, howMany) {
  try {
    const db = await openDB()
    const tx = db.transaction(EVENTS_STORE, 'readwrite')
    const index = tx.objectStore(EVENTS_STORE).index('userAssignment')
    const cursorReq = index.openCursor(IDBKeyRange.only([userId, assignmentId]))
    let removed = 0
    await new Promise((resolve, reject) => {
      cursorReq.onsuccess = (e) => {
        const cursor = e.target.result
        if (!cursor || removed >= howMany) { resolve(); return }
        cursor.delete()
        removed++
        cursor.continue()
      }
      cursorReq.onerror = () => reject(cursorReq.error)
    })
  } catch (err) {
    console.error('[SnapshotDB] event eviction failed:', err)
  }
}

/**
 * Get events for (user, assignment) with id > afterId, ordered by id
 * (insertion order == chronological order for a single client).
 */
export async function getEvents(assignmentId, userId = null, afterId = 0) {
  if (!IDB_AVAILABLE) return []
  try {
    const db = await openDB()
    const tx = db.transaction(EVENTS_STORE, 'readonly')
    const index = tx.objectStore(EVENTS_STORE).index('userAssignment')
    const request = index.getAll(IDBKeyRange.only([userId, assignmentId]))
    const results = await new Promise((resolve, reject) => {
      request.onsuccess = () => resolve(request.result || [])
      request.onerror = () => reject(request.error)
    })
    return results
      .filter(r => r.id > afterId)
      .sort((a, b) => a.id - b.id)
  } catch (err) {
    console.error('[SnapshotDB] getEvents failed:', err)
    return []
  }
}

export async function countEvents(assignmentId, userId = null) {
  if (!IDB_AVAILABLE) return 0
  try {
    const db = await openDB()
    const tx = db.transaction(EVENTS_STORE, 'readonly')
    const countReq = tx.objectStore(EVENTS_STORE)
      .index('userAssignment').count(IDBKeyRange.only([userId, assignmentId]))
    return await new Promise((resolve, reject) => {
      countReq.onsuccess = () => resolve(countReq.result)
      countReq.onerror = () => reject(countReq.error)
    })
  } catch {
    return 0
  }
}

export async function clearEvents(assignmentId, userId = null) {
  if (!IDB_AVAILABLE) return
  try {
    const db = await openDB()
    const tx = db.transaction([EVENTS_STORE, SYNC_META_STORE], 'readwrite')
    const index = tx.objectStore(EVENTS_STORE).index('userAssignment')
    const cursorReq = index.openCursor(IDBKeyRange.only([userId, assignmentId]))
    await new Promise((resolve, reject) => {
      cursorReq.onsuccess = (e) => {
        const cursor = e.target.result
        if (cursor) { cursor.delete(); cursor.continue() } else resolve()
      }
      cursorReq.onerror = () => reject(cursorReq.error)
    })
    tx.objectStore(SYNC_META_STORE).delete(_syncMetaKey(assignmentId, userId))
  } catch (err) {
    console.error('[SnapshotDB] clearEvents failed:', err)
  }
}

function _syncMetaKey(assignmentId, userId) {
  return `${userId || 'anon'}::${assignmentId}`
}

/** Last event id already synced to the server for (user, assignment). */
export async function getLastSyncedEventId(assignmentId, userId = null) {
  if (!IDB_AVAILABLE) return 0
  try {
    const db = await openDB()
    const tx = db.transaction(SYNC_META_STORE, 'readonly')
    const req = tx.objectStore(SYNC_META_STORE).get(_syncMetaKey(assignmentId, userId))
    const rec = await new Promise((resolve, reject) => {
      req.onsuccess = () => resolve(req.result)
      req.onerror = () => reject(req.error)
    })
    return rec?.lastSyncedEventId || 0
  } catch {
    return 0
  }
}

export async function setLastSyncedEventId(assignmentId, userId = null, eventId = 0) {
  if (!IDB_AVAILABLE) return
  try {
    const db = await openDB()
    const tx = db.transaction(SYNC_META_STORE, 'readwrite')
    tx.objectStore(SYNC_META_STORE).put({
      key: _syncMetaKey(assignmentId, userId),
      lastSyncedEventId: eventId,
    })
    await new Promise((resolve, reject) => {
      tx.oncomplete = resolve
      tx.onerror = () => reject(tx.error)
    })
  } catch (err) {
    console.error('[SnapshotDB] setLastSyncedEventId failed:', err)
  }
}
