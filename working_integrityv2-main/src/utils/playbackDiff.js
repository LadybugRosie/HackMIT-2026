/**
 * playbackDiff.js — Text diff engine for session playback visualization.
 *
 * Uses diff-match-patch for efficient Myers diff computation.
 * Provides utilities to compute, render, and classify changes between snapshots.
 */

import DiffMatchPatch from 'diff-match-patch'

const dmp = new DiffMatchPatch()

// Diff types matching diff-match-patch constants
const DIFF_DELETE = -1
const DIFF_INSERT = 1
const DIFF_EQUAL = 0

/**
 * Compute a diff between two plaintext strings.
 * @returns {Array<{type: 'add'|'remove'|'same', text: string}>}
 */
export function computeDiff(oldText, newText) {
  if (!oldText && !newText) return []
  if (!oldText) return [{ type: 'add', text: newText }]
  if (!newText) return [{ type: 'remove', text: oldText }]

  const diffs = dmp.diff_main(oldText, newText)
  dmp.diff_cleanupSemantic(diffs)

  return diffs.map(([op, text]) => ({
    type: op === DIFF_INSERT ? 'add' : op === DIFF_DELETE ? 'remove' : 'same',
    text
  }))
}

/**
 * Classify the type of change between two snapshots.
 * @param {Object} prevSnap - Previous snapshot
 * @param {Object} nextSnap - Next snapshot
 * @returns {'typing'|'paste'|'delete'|'idle'|'mixed'}
 */
export function classifyChange(prevSnap, nextSnap) {
  if (!prevSnap || !nextSnap) return 'typing'

  const prevText = prevSnap.plaintext || ''
  const nextText = nextSnap.plaintext || ''
  const lengthDelta = nextText.length - prevText.length

  // Check if paste count increased
  const prevPastes = prevSnap.pasteCount || 0
  const nextPastes = nextSnap.pasteCount || 0
  if (nextPastes > prevPastes) return 'paste'

  // Check if content got shorter (deletion)
  if (lengthDelta < -20) return 'delete'

  // Check if content is unchanged (idle)
  if (prevText === nextText) return 'idle'

  // Otherwise it's typing
  return 'typing'
}

/**
 * Compute stats for a range of snapshots.
 */
export function computeRangeStats(snapshots, startIdx, endIdx) {
  if (!snapshots || snapshots.length === 0) return null

  const start = snapshots[Math.max(0, startIdx)]
  const end = snapshots[Math.min(snapshots.length - 1, endIdx)]

  const durationMs = (end.timestamp || 0) - (start.timestamp || 0)
  const wordDelta = (end.wordCount || 0) - (start.wordCount || 0)
  const charDelta = (end.plaintext || '').length - (start.plaintext || '').length

  return {
    durationMs,
    wordDelta,
    charDelta,
    wordsPerMinute: durationMs > 0 ? Math.round(wordDelta / (durationMs / 60000)) : 0,
    startTime: start.timestamp,
    endTime: end.timestamp,
  }
}

/**
 * Build a timeline of activity segments from snapshots for visualization.
 * Groups consecutive snapshots of the same change type into segments.
 * @returns {Array<{type: string, startTime: number, endTime: number, startIdx: number, endIdx: number}>}
 */
export function buildActivityTimeline(snapshots) {
  if (!snapshots || snapshots.length < 2) return []

  const segments = []
  let currentType = null
  let segStart = 0

  for (let i = 1; i < snapshots.length; i++) {
    const changeType = classifyChange(snapshots[i - 1], snapshots[i])

    if (changeType !== currentType) {
      if (currentType !== null) {
        segments.push({
          type: currentType,
          startTime: snapshots[segStart].timestamp,
          endTime: snapshots[i - 1].timestamp,
          startIdx: segStart,
          endIdx: i - 1,
        })
      }
      currentType = changeType
      segStart = i - 1
    }
  }

  // Push final segment
  if (currentType !== null) {
    segments.push({
      type: currentType,
      startTime: snapshots[segStart].timestamp,
      endTime: snapshots[snapshots.length - 1].timestamp,
      startIdx: segStart,
      endIdx: snapshots.length - 1,
    })
  }

  return segments
}

/**
 * Reconstruct full plaintext at a given snapshot index from delta-compressed export.
 * Handles the delta compression format from snapshotDB.exportSnapshots().
 */
export function reconstructAtIndex(exportedSnapshots, index) {
  if (!exportedSnapshots || index < 0 || index >= exportedSnapshots.length) return ''

  let lastFullText = ''

  for (let i = 0; i <= index; i++) {
    const snap = exportedSnapshots[i]
    if (snap._full || snap.plaintext !== undefined) {
      lastFullText = snap.plaintext || ''
    }
  }

  return lastFullText
}
