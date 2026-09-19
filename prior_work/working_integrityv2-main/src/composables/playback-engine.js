/**
 * playback-engine.js — Pure playback state machine for session replay.
 *
 * Extracted from pages/teacher/SessionPlayback.vue so the same engine can
 * drive the teacher playback page, the researcher results page and the
 * public share page.
 *
 * Usage:
 *   const engine = createPlaybackEngine()
 *   engine.load(rawSnapshots)   // raw, possibly delta-compressed
 *   engine.play() / engine.stop() / engine.seekToIndex(i) / ...
 *   engine.destroy()            // on unmount
 *
 * Reactive state: { snapshots, currentIdx, isPlaying, speed, charTags,
 *                   liveTypedCount, livePasteCount, liveWordCount, eventBanner }
 */

import { reactive } from 'vue'
import DiffMatchPatch from 'diff-match-patch'

const dmp = new DiffMatchPatch()

// Cache a charTags keyframe every N snapshots (plus paste boundaries)
const KEYFRAME_INTERVAL = 100
// Per-character reveal delay at 1x speed (~16 chars/sec → ~50 WPM feel)
const TYPE_CHAR_BASE_MS = 60
// A burst of >= this many characters appearing in a single transition is
// treated as a paste/insert rather than typing — no human types this much at
// once between two ~200ms snapshots.
const PASTE_MIN_CHARS = 40
// Maximum plausible sustained human typing speed (chars/sec). A burst faster
// than this across a snapshot gap is a paste even when the integrity tracker
// missed the event (e.g. collaborative sessions, or a noisy paste counter).
const MAX_HUMAN_CPS = 25

/**
 * Materialize delta-compressed snapshots:
 *  - carry plaintext forward when a snapshot omits it
 *  - defensively drop snapshots with non-finite timestamps
 */
export function materializeSnapshots(raw) {
  const built = []
  let prev = ''
  for (const s of Array.isArray(raw) ? raw : []) {
    if (!s || typeof s !== 'object') continue
    const pt = s.plaintext !== undefined ? s.plaintext : prev
    prev = pt // keep the carry-forward chain intact even if this one is dropped
    const ts = Number(s.timestamp)
    if (!Number.isFinite(ts)) continue
    built.push({ ...s, timestamp: ts, plaintext: pt })
  }
  return built
}

/**
 * Classify the transition between two snapshots.
 * @returns {'typing'|'paste'|'delete'|'idle'}
 */
export function detectSnapshotEvent(prevSnap, currSnap) {
  const currText = currSnap?.plaintext || ''
  if (!prevSnap) {
    // The first snapshot that already carries a block of text represents
    // pre-existing / pasted content, not live typing.
    return currText.length >= PASTE_MIN_CHARS ? 'paste' : 'typing'
  }
  const prevText = prevSnap.plaintext || ''
  const prevPastes = prevSnap.pasteCount || 0
  const currPastes = currSnap.pasteCount || 0
  const added = currText.length - prevText.length

  // Explicit paste signal from the integrity tracker.
  if (currPastes > prevPastes && added > 0) return 'paste'

  // Content-based fallback: a burst too large/fast to be hand-typed. Keeps
  // paste detection working when the tracker globals are unavailable or the
  // paste counter is noisy.
  if (added >= PASTE_MIN_CHARS) {
    const gapMs = (Number(currSnap.timestamp) || 0) - (Number(prevSnap.timestamp) || 0)
    const cps = gapMs > 0 ? added / (gapMs / 1000) : Infinity
    if (cps > MAX_HUMAN_CPS) return 'paste'
  }

  if (currText.length < prevText.length - 2) return 'delete'
  if (prevText === currText) return 'idle'
  return 'typing'
}

/**
 * Pure version of the charTags diff application.
 * Diffs from the text represented by `oldTags` to `newText`, preserving
 * existing origin tags (pasted chars stay tagged as pasted forever).
 * Returns a NEW tags array; never mutates `oldTags`.
 */
export function applyDiffToTags(oldTags, newText, origin) {
  const currentText = oldTags.map(c => c.ch).join('')
  const diffs = dmp.diff_main(currentText, newText || '')
  dmp.diff_cleanupSemantic(diffs)

  const newTags = []
  let oldIdx = 0

  for (const [op, text] of diffs) {
    if (op === 0) {
      // Unchanged — preserve existing tags (keeps pasted origin)
      for (let i = 0; i < text.length; i++) {
        const existing = oldTags[oldIdx]
        newTags.push(existing
          ? { ch: text[i], origin: existing.origin, justAdded: false }
          : { ch: text[i], origin: 'typed', justAdded: false })
        oldIdx++
      }
    } else if (op === 1) {
      // Added — tag with the given origin
      for (let i = 0; i < text.length; i++) {
        newTags.push({ ch: text[i], origin, justAdded: true })
      }
    } else {
      // Deleted — skip these chars from old
      oldIdx += text.length
    }
  }

  return newTags
}

export function formatDuration(ms) {
  if (!ms || ms <= 0) return '0:00'
  const s = Math.floor(ms / 1000), m = Math.floor(s / 60)
  if (m >= 60) return `${Math.floor(m / 60)}h ${m % 60}m`
  return `${m}:${(s % 60).toString().padStart(2, '0')}`
}

function countWords(text) {
  if (!text) return 0
  return text.trim().split(/\s+/).filter(Boolean).length
}

// ════════════════════════════════════════════════════════════════
// EVENT MODE (playback v2) — discrete edit events { t, p, d, i, k, a }
//
// The document is a compact RUN list [{ text, origin, author }] instead of
// one object per character: run ops are O(runs), rendering is O(runs), and
// per-character provenance (typed/pasted) + per-author attribution survive
// every edit. 'ckpt' events carry full text and reconcile the run list back
// to ground truth, so replay self-heals across browser switches and collab
// merge seams.
// ════════════════════════════════════════════════════════════════

export function runsText(runs) {
  let out = ''
  for (const r of runs) out += r.text
  return out
}

export function runsLength(runs) {
  let n = 0
  for (const r of runs) n += r.text.length
  return n
}

function _sameStyle(a, borigin, bauthor) {
  return a.origin === borigin && a.author === bauthor
}

/** Insert `text` at plaintext offset `pos`, merging with same-style runs. */
export function runsInsert(runs, pos, text, origin, author = null) {
  if (!text) return
  let off = 0
  let idx = 0
  while (idx < runs.length && off + runs[idx].text.length < pos) {
    off += runs[idx].text.length
    idx++
  }
  if (idx === runs.length) {
    const last = runs[runs.length - 1]
    if (last && _sameStyle(last, origin, author)) last.text += text
    else runs.push({ text, origin, author })
    return
  }
  const r = runs[idx]
  const local = Math.max(0, pos - off)
  if (_sameStyle(r, origin, author)) {
    r.text = r.text.slice(0, local) + text + r.text.slice(local)
    return
  }
  if (local === 0) {
    const prev = runs[idx - 1]
    if (prev && _sameStyle(prev, origin, author)) { prev.text += text; return }
    runs.splice(idx, 0, { text, origin, author })
    return
  }
  if (local === r.text.length) {
    const next = runs[idx + 1]
    if (next && _sameStyle(next, origin, author)) { next.text = text + next.text; return }
    runs.splice(idx + 1, 0, { text, origin, author })
    return
  }
  runs.splice(idx, 1,
    { text: r.text.slice(0, local), origin: r.origin, author: r.author },
    { text, origin, author },
    { text: r.text.slice(local), origin: r.origin, author: r.author })
}

/** Delete `count` chars starting at plaintext offset `pos`. */
export function runsDelete(runs, pos, count) {
  let remaining = Math.max(0, count)
  if (remaining === 0) return
  let off = 0
  let idx = 0
  while (idx < runs.length && remaining > 0) {
    const r = runs[idx]
    const len = r.text.length
    const end = off + len
    if (end <= pos) { off = end; idx++; continue }
    // After earlier partial trims, the not-yet-deleted range always starts
    // back at `pos` in current coordinates, spanning `remaining` chars.
    const delStart = Math.max(pos, off) - off
    const delEnd = Math.min(end, pos + remaining) - off
    const removed = Math.min(delEnd, len) - delStart
    if (removed <= 0) break
    r.text = r.text.slice(0, delStart) + r.text.slice(delStart + removed)
    remaining -= removed
    if (r.text.length === 0) {
      runs.splice(idx, 1)
      // idx stays: the next run slides into this slot; off unchanged
    } else {
      off += r.text.length
      idx++
    }
  }
  // Merge adjacent same-style runs left behind by the deletion
  for (let i = runs.length - 1; i > 0; i--) {
    if (_sameStyle(runs[i - 1], runs[i].origin, runs[i].author)) {
      runs[i - 1].text += runs[i].text
      runs.splice(i, 1)
    }
  }
}

/** Display kind of one event (large un-flagged inserts read as paste). */
export function eventDisplayKind(ev) {
  if (ev.k === 'ckpt') return 'ckpt'
  if (ev.k === 'paste') return 'paste'
  if (ev.i && ev.i.length >= PASTE_MIN_CHARS) return 'paste'
  if (ev.d > 0 && !ev.i) return 'delete'
  return 'typing'
}

/**
 * Group a normalized event stream into human-readable activity segments for
 * the timeline/event-list UI. Pastes are always their own segment (with a
 * text preview); consecutive typing/deleting by the same author groups while
 * gaps stay short; long silences become explicit idle segments.
 */
export function buildEventSegments(events, authors = {}) {
  const IDLE_MS = 30000
  const GROUP_GAP_MS = 2500
  const segs = []
  let cur = null
  let lastT = null

  for (let idx = 0; idx < (events?.length || 0); idx++) {
    const ev = events[idx]
    if (ev.k === 'ckpt') continue
    const kind = eventDisplayKind(ev)
    const author = ev.a || null

    if (lastT != null && ev.t - lastT >= IDLE_MS) {
      segs.push({ kind: 'idle', startIdx: idx, endIdx: idx, startT: lastT, endT: ev.t, author: null, authorName: null, chars: 0, durMs: ev.t - lastT })
      cur = null
    }
    lastT = ev.t

    if (kind === 'paste') {
      cur = {
        kind, startIdx: idx, endIdx: idx, startT: ev.t, endT: ev.t,
        author, authorName: authors[author] || null,
        chars: ev.i.length, preview: ev.i.slice(0, 300),
      }
      segs.push(cur)
      continue
    }

    const chars = kind === 'delete' ? ev.d : (ev.i?.length || 0)
    if (cur && cur.kind === kind && cur.author === author && ev.t - cur.endT < GROUP_GAP_MS) {
      cur.endIdx = idx
      cur.endT = ev.t
      cur.chars += chars
    } else {
      cur = {
        kind, startIdx: idx, endIdx: idx, startT: ev.t, endT: ev.t,
        author, authorName: authors[author] || null, chars,
      }
      segs.push(cur)
    }
  }
  return segs
}

/**
 * Snapshot-mode fallback of buildEventSegments — derives segments from
 * snapshot transitions (legacy sessions with no event stream). Paste
 * previews come from a one-off diff of the two snapshots around the paste.
 */
export function buildSnapshotSegments(snapshots) {
  const IDLE_MS = 30000
  const GROUP_GAP_MS = 5000
  const segs = []
  let cur = null
  let lastActiveT = null

  for (let i = 1; i < (snapshots?.length || 0); i++) {
    const prev = snapshots[i - 1]
    const curr = snapshots[i]
    const event = detectSnapshotEvent(prev, curr)
    if (event === 'idle') continue
    const t = Number(curr.timestamp) || 0
    const prevText = prev.plaintext || ''
    const currText = curr.plaintext || ''

    if (lastActiveT != null && t - lastActiveT >= IDLE_MS) {
      segs.push({ kind: 'idle', startIdx: i, endIdx: i, startT: lastActiveT, endT: t, author: null, authorName: null, chars: 0, durMs: t - lastActiveT })
      cur = null
    }
    lastActiveT = t

    if (event === 'paste') {
      // Largest inserted chunk = the pasted text (preview only)
      let preview = ''
      try {
        const diffs = dmp.diff_main(prevText, currText)
        dmp.diff_cleanupSemantic(diffs)
        for (const [op, text] of diffs) {
          if (op === 1 && text.length > preview.length) preview = text
        }
      } catch { /* preview is optional */ }
      segs.push({
        kind: 'paste', startIdx: i, endIdx: i, startT: t, endT: t,
        author: null, authorName: null,
        chars: Math.max(0, currText.length - prevText.length),
        preview: preview.slice(0, 300),
      })
      cur = segs[segs.length - 1]
      continue
    }

    const kind = event === 'delete' ? 'delete' : 'typing'
    const chars = kind === 'delete'
      ? Math.max(0, prevText.length - currText.length)
      : Math.max(0, currText.length - prevText.length)
    if (cur && cur.kind === kind && t - cur.endT < GROUP_GAP_MS) {
      cur.endIdx = i
      cur.endT = t
      cur.chars += chars
    } else {
      cur = { kind, startIdx: i, endIdx: i, startT: t, endT: t, author: null, authorName: null, chars }
      segs.push(cur)
    }
  }
  return segs
}

export function formatClockTime(ts) {
  if (!ts || !Number.isFinite(Number(ts))) return '--:--'
  return new Date(Number(ts)).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' })
}

export function createPlaybackEngine() {
  const state = reactive({
    snapshots: [],
    currentIdx: 0,
    isPlaying: false,
    speed: 1,
    // Each entry: { ch: 'a', origin: 'typed'|'pasted', justAdded: bool }
    charTags: [],
    // Metrics from IntegrityTracker snapshots (authoritative)
    liveTypedCount: 0,
    livePasteCount: 0,
    liveWordCount: 0,
    eventBanner: null,

    // ─── Event mode (playback v2) ───
    mode: 'snapshots',        // 'snapshots' | 'events'
    events: [],               // normalized { t, p, d, i, k, seq, a }
    currentEventIdx: -1,      // index of the LAST applied event
    runs: [],                 // [{ text, origin: 'typed'|'pasted', author }]
    caretPos: null,           // plaintext offset of the live caret
    activeAuthor: null,       // uid of whoever performed the last event
    activeKind: null,         // 'typing' | 'paste' | 'delete' | null
    authors: {},              // { uid: displayName }
    trueSpeed: false,         // honor real gaps (capped) instead of compressing
  })

  let destroyed = false

  // ─── Timer hygiene (bug h) ───────────────────────────────────
  // Exactly ONE pending playback step timer at any time; tracked here so
  // stop()/destroy() always clear it and setSpeed() can reschedule it.
  let pendingStep = null // { handle, fn, baseMs }
  let bannerTimer = null
  let justAddedTimer = null

  // ─── Keyframe cache (bug a) ──────────────────────────────────
  // idx -> plain copy of the charTags state AFTER snapshot idx is applied.
  const keyframeCache = new Map()
  let keyframeIndices = new Set()

  function _scheduleStep(fn, baseMs) {
    _cancelStep()
    // Read speed from state at scheduling time — no stale closures (bug b)
    const delay = Math.max(0, baseMs / (state.speed || 1))
    const handle = setTimeout(() => {
      pendingStep = null
      if (destroyed || !state.isPlaying) return // never run a stale step (bug g)
      fn()
    }, delay)
    pendingStep = { handle, fn, baseMs }
  }

  function _cancelStep() {
    if (pendingStep) {
      clearTimeout(pendingStep.handle)
      pendingStep = null
    }
  }

  function _showBanner(type, label, detail, ms) {
    if (bannerTimer) { clearTimeout(bannerTimer); bannerTimer = null }
    const icons = { paste: '📋', delete: '⌫', start: '▶️', end: '✅', idle: '⏸️' }
    state.eventBanner = { type, label, detail, icon: icons[type] || '📝' }
    bannerTimer = setTimeout(() => {
      bannerTimer = null
      state.eventBanner = null
    }, ms)
  }

  function _clearJustAddedSoon() {
    if (justAddedTimer) clearTimeout(justAddedTimer)
    justAddedTimer = setTimeout(() => {
      justAddedTimer = null
      for (const c of state.charTags) {
        if (c.justAdded) c.justAdded = false
      }
    }, 300)
  }

  function _updateMetrics(snap) {
    if (!snap) return
    state.liveTypedCount = snap.typedCount || 0
    state.livePasteCount = snap.pasteCount || 0
    state.liveWordCount = snap.wordCount || 0
  }

  function _resetDocState() {
    state.charTags = []
    state.liveTypedCount = 0
    state.livePasteCount = 0
    state.liveWordCount = 0
  }

  function _renderStatic(idx) {
    const snap = state.snapshots[idx]
    if (!snap) return
    state.charTags = Array.from(snap.plaintext || '')
      .map(ch => ({ ch, origin: 'typed', justAdded: false }))
    _updateMetrics(snap)
  }

  function _cacheKeyframe(idx, tags) {
    if (!keyframeIndices.has(idx) || keyframeCache.has(idx)) return
    const source = tags || state.charTags
    keyframeCache.set(idx, source.map(c => ({ ch: c.ch, origin: c.origin })))
  }

  // ─── Load ────────────────────────────────────────────────────
  function load(rawSnapshots) {
    if (destroyed) return
    stop()
    keyframeCache.clear()

    state.mode = 'snapshots'
    state.events = []
    state.currentEventIdx = -1
    state.runs = []
    state.caretPos = null
    state.activeAuthor = null
    state.activeKind = null

    state.snapshots = materializeSnapshots(rawSnapshots)
    state.currentIdx = 0
    state.eventBanner = null
    _resetDocState()

    // Precompute keyframe indices: every KEYFRAME_INTERVAL snapshots,
    // plus before/after each paste event (bug a)
    keyframeIndices = new Set()
    const snaps = state.snapshots
    for (let i = 0; i < snaps.length; i += KEYFRAME_INTERVAL) keyframeIndices.add(i)
    for (let i = 1; i < snaps.length; i++) {
      if (detectSnapshotEvent(snaps[i - 1], snaps[i]) === 'paste') {
        keyframeIndices.add(i - 1)
        keyframeIndices.add(i)
      }
    }

    // Single-snapshot session: show the document statically with its
    // metrics instead of an empty doc (bug e)
    if (snaps.length === 1) _renderStatic(0)
  }

  // ─── Event mode: load ────────────────────────────────────────
  // Prefix sums (static after load) so paste/delete counters are O(1)
  // at any playback position, including after seeks.
  let _pastePrefix = [0]
  let _deletePrefix = [0]
  // Content of every paste event, so checkpoint recovery can keep the
  // "pasted" attribution instead of laundering recovered pastes as typed.
  let _pasteTexts = []

  /**
   * Load a discrete event stream (returns false when the stream is too
   * thin to replay — caller should fall back to snapshot mode).
   */
  function loadEvents(rawEvents, authorsMap = {}) {
    if (destroyed) return false

    const evs = (Array.isArray(rawEvents) ? rawEvents : [])
      .filter(e => e && typeof e === 'object' && Number.isFinite(Number(e.t)))
      .map(e => ({
        t: Number(e.t),
        p: Math.max(0, Number(e.p) || 0),
        d: Math.max(0, Number(e.d) || 0),
        i: typeof e.i === 'string' ? e.i : '',
        k: (e.k === 'paste' || e.k === 'ckpt') ? e.k : 'type',
        seq: Number(e.seq) || 0,
        a: e.a || null,
      }))
    evs.sort((x, y) => (x.t - y.t) || (x.seq - y.seq))

    // A lone checkpoint (opened the editor, typed nothing) isn't a replay.
    const substantive = evs.filter(e => e.k !== 'ckpt').length
    if (evs.length === 0 || substantive === 0) return false

    stop()
    state.mode = 'events'
    state.events = evs
    state.authors = authorsMap || {}
    state.currentEventIdx = -1
    state.runs = []
    state.caretPos = null
    state.activeAuthor = null
    state.activeKind = null
    state.eventBanner = null
    state.liveTypedCount = 0
    state.livePasteCount = 0
    state.liveWordCount = 0

    _pastePrefix = [0]
    _deletePrefix = [0]
    _pasteTexts = []
    for (let i = 0; i < evs.length; i++) {
      const kind = eventDisplayKind(evs[i])
      _pastePrefix.push(_pastePrefix[i] + (kind === 'paste' ? 1 : 0))
      _deletePrefix.push(_deletePrefix[i] + (evs[i].d || 0))
      if (kind === 'paste' && evs[i].i) {
        _pasteTexts.push({ text: evs[i].i, a: evs[i].a || null })
      }
    }
    return true
  }

  function getEventStats() {
    return { pastePrefix: _pastePrefix, deletePrefix: _deletePrefix }
  }

  // ─── Event mode: apply/replay ────────────────────────────────
  /** Reconcile the run list to checkpoint text, preserving provenance. */
  function _reconcileRunsTo(targetText) {
    const current = runsText(state.runs)
    if (current === (targetText || '')) return
    const diffs = dmp.diff_main(current, targetText || '')
    dmp.diff_cleanupSemantic(diffs)
    let pos = 0
    for (const [op, text] of diffs) {
      if (op === 0) {
        pos += text.length
      } else if (op === -1) {
        runsDelete(state.runs, pos, text.length)
      } else {
        // Text we never saw a clean event for (missed sync, collab seam,
        // duplicated events). If the recovered block matches a known paste's
        // content, KEEP the pasted attribution — otherwise a checkpoint
        // reconcile would silently launder pasted text as typed and the
        // sidebar would report "Pasted: 0" next to a visible paste event.
        const attr = _attributeRecoveredText(text)
        runsInsert(state.runs, pos, text, attr.origin, attr.author)
        pos += text.length
      }
    }
  }

  function _attributeRecoveredText(text) {
    if (text && text.length >= 30) {
      const t = text.trim()
      for (const p of _pasteTexts) {
        if (p.text.includes(t) || t.includes(p.text.trim())) {
          return { origin: 'pasted', author: p.a }
        }
      }
    }
    return { origin: 'typed', author: null }
  }

  /** Apply one event to the run list. Returns its display kind + sizes. */
  function _applyEvent(ev) {
    if (ev.k === 'ckpt') {
      _reconcileRunsTo(ev.i)
      return { kind: 'ckpt', insLen: 0, delLen: 0 }
    }
    const kind = eventDisplayKind(ev)
    const total = runsLength(state.runs)
    const pos = Math.max(0, Math.min(ev.p, total))
    const d = Math.max(0, Math.min(ev.d, total - pos))
    if (d > 0) runsDelete(state.runs, pos, d)
    if (ev.i) {
      runsInsert(state.runs, pos, ev.i, kind === 'paste' ? 'pasted' : 'typed', ev.a || null)
    }
    state.caretPos = pos + (ev.i ? ev.i.length : 0)
    return { kind, insLen: ev.i ? ev.i.length : 0, delLen: d }
  }

  function _updateEventMetrics() {
    let typed = 0, pasted = 0
    for (const r of state.runs) {
      if (r.origin === 'pasted') pasted += r.text.length
      else typed += r.text.length
    }
    state.liveTypedCount = typed
    state.livePasteCount = _pastePrefix[state.currentEventIdx + 1] || 0
    // Word count is O(doc) — throttle it for large docs during playback
    const totalLen = typed + pasted
    if (totalLen < 20000 || !state.isPlaying || state.currentEventIdx % 10 === 0) {
      state.liveWordCount = countWords(runsText(state.runs))
    }
  }

  function _finishEventSession() {
    stop()
    _showBanner('end', 'SESSION COMPLETE',
      `${runsLength(state.runs)} characters · ${state.liveWordCount} words`, 2000)
  }

  function _processEvent() {
    if (destroyed || !state.isPlaying) return
    const idx = state.currentEventIdx + 1
    const ev = state.events[idx]
    if (!ev) { _finishEventSession(); return }

    const applied = _applyEvent(ev)
    state.currentEventIdx = idx
    if (applied.kind !== 'ckpt') {
      state.activeAuthor = ev.a || null
      state.activeKind = applied.kind
    }
    _updateEventMetrics()

    const authorName = state.authors[ev.a] || null
    const who = authorName ? ` — ${authorName}` : ''

    if (applied.kind === 'paste') {
      _showBanner('paste', 'CONTENT PASTED', `${applied.insLen} characters${who}`, 1500 / state.speed)
      _scheduleStep(() => _advanceEvent(), 900)
    } else if (applied.kind === 'delete' && applied.delLen >= 20) {
      _showBanner('delete', 'CONTENT DELETED', `${applied.delLen} characters removed${who}`, 1000 / state.speed)
      _scheduleStep(() => _advanceEvent(), 600)
    } else {
      _advanceEvent()
    }
  }

  function _advanceEvent() {
    if (destroyed || !state.isPlaying) return
    const idx = state.currentEventIdx
    const curr = state.events[idx]
    const next = state.events[idx + 1]
    if (!next) { _finishEventSession(); return }

    const gap = Math.max(0, (next.t || 0) - (curr?.t || 0))
    if (gap >= 30000) {
      _showBanner('idle', 'IDLE', `${formatDuration(gap)} of inactivity`, 1200 / state.speed)
    }
    const baseMs = state.trueSpeed
      ? Math.min(gap, 3000)
      : (gap > 2000 ? 400 : Math.max(5, gap / 3))
    _scheduleStep(() => _processEvent(), Math.max(1, baseMs))
  }

  /** Rebuild the document at event index `i` (replays from 0 — run ops are cheap). */
  function seekToEventIndex(i) {
    if (destroyed) return
    const n = state.events.length
    if (n === 0) return
    const idx = Math.min(Math.max(-1, Math.floor(Number(i))), n - 1)
    stop()
    state.runs = []
    state.caretPos = null
    for (let j = 0; j <= idx; j++) _applyEvent(state.events[j])
    state.currentEventIdx = idx
    const lastReal = (() => {
      for (let j = idx; j >= 0; j--) {
        if (state.events[j].k !== 'ckpt') return state.events[j]
      }
      return null
    })()
    state.activeAuthor = lastReal?.a || null
    state.activeKind = lastReal ? eventDisplayKind(lastReal) : null
    _updateEventMetrics()
    state.eventBanner = null
  }

  function setTrueSpeed(v) {
    state.trueSpeed = !!v
  }

  // ─── Playback ────────────────────────────────────────────────
  function play() {
    if (destroyed) return

    if (state.mode === 'events') {
      const nEv = state.events.length
      if (nEv === 0) return
      if (state.currentEventIdx >= nEv - 1) {
        // Replay from the beginning
        state.currentEventIdx = -1
        state.runs = []
        state.caretPos = null
      }
      state.isPlaying = true
      _showBanner('start', 'SESSION START', 'Replaying writing session...', 1000 / state.speed)
      _scheduleStep(() => _processEvent(), 600)
      return
    }

    const n = state.snapshots.length
    if (n === 0) return

    if (n === 1) {
      // Nothing to animate — render statically and mark complete (bug e)
      _renderStatic(0)
      _showBanner('end', 'SESSION COMPLETE', `${state.charTags.length} characters · ${state.liveWordCount} words`, 2000)
      return
    }

    if (state.currentIdx >= n - 1) {
      // Replay from the beginning
      state.currentIdx = 0
      _resetDocState()
    }

    state.isPlaying = true
    _showBanner('start', 'SESSION START', 'Replaying writing session...', 1000 / state.speed)
    _scheduleStep(() => _processSnapshot(), 1000)
  }

  function stop() {
    state.isPlaying = false
    _cancelStep()
    if (bannerTimer) { clearTimeout(bannerTimer); bannerTimer = null }
    if (justAddedTimer) { clearTimeout(justAddedTimer); justAddedTimer = null }
  }

  function _finishSession() {
    // Called only after the FINAL snapshot has been fully processed (bug c)
    stop()
    _showBanner('end', 'SESSION COMPLETE', `${state.charTags.length} characters · ${state.liveWordCount} words`, 2000)
  }

  function _processSnapshot() {
    if (destroyed || !state.isPlaying) return
    const idx = state.currentIdx
    const curr = state.snapshots[idx]
    if (!curr) { stop(); return }

    const prev = idx > 0 ? state.snapshots[idx - 1] : null
    const prevText = prev?.plaintext || ''
    const currText = curr.plaintext || ''
    const event = detectSnapshotEvent(prev, curr)

    _updateMetrics(curr)

    if (event === 'paste') {
      // ── PASTE: banner → instant reveal → hold ──
      const addedLen = Math.max(0, currText.length - prevText.length)
      _showBanner('paste', 'CONTENT PASTED', `${addedLen} characters from clipboard`, 1500 / state.speed)
      _scheduleStep(() => {
        state.charTags = applyDiffToTags(state.charTags, currText, 'pasted')
        _cacheKeyframe(idx)
        // Hold to let the viewer see the red highlight
        _scheduleStep(() => _advance(), 1000)
      }, 700)

    } else if (event === 'delete') {
      // ── DELETE: banner → remove ──
      const removedLen = Math.max(0, prevText.length - currText.length)
      _showBanner('delete', 'CONTENT DELETED', `${removedLen} characters removed`, 1000 / state.speed)
      _scheduleStep(() => {
        state.charTags = applyDiffToTags(state.charTags, currText, 'typed')
        _cacheKeyframe(idx)
        _advance()
      }, 800)

    } else if (event === 'idle') {
      // ── IDLE: skip fast ──
      _cacheKeyframe(idx)
      _advance()

    } else {
      // ── TYPING: diff ONCE per transition, then reveal incrementally (bug a) ──
      const plan = _buildTypingPlan(currText)
      state.charTags = plan.base
      if (plan.insertions.length === 0) {
        // Pure deletion or rearrange
        _cacheKeyframe(idx)
        _advance()
        return
      }
      _revealNext(plan, 0, 0, 0)
    }
  }

  /**
   * Compute the diff from the CURRENT charTags text to targetText exactly
   * once, returning:
   *  - base: charTags with deletions applied and equal runs preserved
   *          (origins kept), WITHOUT the inserted chars
   *  - insertions: [{ pos, chars }] positions are offsets into `base`
   */
  function _buildTypingPlan(targetText) {
    const oldTags = state.charTags
    const fromText = oldTags.map(c => c.ch).join('')
    const diffs = dmp.diff_main(fromText, targetText || '')
    dmp.diff_cleanupSemantic(diffs)

    const base = []
    const insertions = []
    let oldIdx = 0

    for (const [op, text] of diffs) {
      if (op === 0) {
        for (let i = 0; i < text.length; i++) {
          const existing = oldTags[oldIdx]
          base.push(existing
            ? { ch: text[i], origin: existing.origin, justAdded: false }
            : { ch: text[i], origin: 'typed', justAdded: false })
          oldIdx++
        }
      } else if (op === -1) {
        oldIdx += text.length
      } else {
        insertions.push({ pos: base.length, chars: Array.from(text) })
      }
    }

    return { base, insertions }
  }

  /**
   * Reveal one inserted char per tick by splicing into charTags —
   * no diff recomputation, no full array rebuild (bug a).
   */
  function _revealNext(plan, insIdx, charIdx, revealedBefore) {
    if (destroyed || !state.isPlaying) return

    const ins = plan.insertions[insIdx]
    state.charTags.splice(ins.pos + revealedBefore + charIdx, 0, {
      ch: ins.chars[charIdx],
      origin: 'typed',
      justAdded: true,
    })

    let nextIns = insIdx
    let nextChar = charIdx + 1
    let nextRevealedBefore = revealedBefore
    if (nextChar >= ins.chars.length) {
      nextRevealedBefore += ins.chars.length
      nextIns++
      nextChar = 0
    }

    if (nextIns >= plan.insertions.length) {
      // All chars revealed — clear justAdded after a brief flash
      _clearJustAddedSoon()
      _cacheKeyframe(state.currentIdx)
      _advance()
      return
    }

    _scheduleStep(() => _revealNext(plan, nextIns, nextChar, nextRevealedBefore), TYPE_CHAR_BASE_MS)
  }

  function _advance() {
    if (destroyed || !state.isPlaying) return // check before scheduling (bug g)

    const nextIdx = state.currentIdx + 1
    if (nextIdx >= state.snapshots.length) {
      // Every snapshot — including the last — has been processed (bug c)
      _finishSession()
      return
    }
    state.currentIdx = nextIdx

    // Pause between snapshots — real timestamp gap, compressed.
    // Coalesce missing/non-finite timestamps defensively (bug d).
    const curr = state.snapshots[nextIdx]
    const prev = state.snapshots[nextIdx - 1]
    const currTs = Number.isFinite(curr?.timestamp) ? curr.timestamp : (prev?.timestamp ?? 0)
    const prevTs = Number.isFinite(prev?.timestamp) ? prev.timestamp : currTs
    const realGap = Math.max(0, currTs - prevTs)
    // True-speed honors real gaps (capped); default compresses long pauses
    // (>2s become 400ms) and plays short gaps proportionally.
    const baseMs = state.trueSpeed
      ? Math.min(realGap, 3000)
      : (realGap > 2000 ? 400 : Math.max(5, realGap / 3))
    _scheduleStep(() => _processSnapshot(), baseMs)
  }

  // ─── Seeking ─────────────────────────────────────────────────
  /**
   * Rebuild charTags for a target index. Restores from the nearest cached
   * keyframe at or before the target instead of replaying from 0 (bug a),
   * then only applies paste boundaries + the target frame itself.
   */
  function _replayCharTagsTo(targetIdx) {
    let startIdx = -1
    for (const k of keyframeCache.keys()) {
      if (k <= targetIdx && k > startIdx) startIdx = k
    }

    let tags = startIdx >= 0
      ? keyframeCache.get(startIdx).map(c => ({ ch: c.ch, origin: c.origin, justAdded: false }))
      : []

    if (startIdx === targetIdx) {
      state.charTags = tags
      return
    }

    // Frames that must be applied: snapshot 0 (if uncached), every paste
    // boundary after the keyframe, and the target itself.
    const frames = new Set([targetIdx])
    if (startIdx < 0) frames.add(0)
    for (let i = Math.max(1, startIdx + 1); i <= targetIdx; i++) {
      if (detectSnapshotEvent(state.snapshots[i - 1], state.snapshots[i]) === 'paste') {
        if (i - 1 > startIdx) frames.add(i - 1) // frame before paste too
        frames.add(i)
      }
    }

    const sorted = [...frames].filter(i => i > startIdx).sort((a, b) => a - b)
    for (const i of sorted) {
      const s = state.snapshots[i]
      const prev = i > 0 ? state.snapshots[i - 1] : null
      const event = detectSnapshotEvent(prev, s)
      tags = applyDiffToTags(tags, s.plaintext || '', event === 'paste' ? 'pasted' : 'typed')
      _cacheKeyframe(i, tags)
    }

    state.charTags = tags.map(c => ({ ch: c.ch, origin: c.origin, justAdded: false }))
  }

  function seekToIndex(i) {
    if (destroyed) return
    if (state.mode === 'events') { seekToEventIndex(i); return }
    const n = state.snapshots.length
    if (n === 0) return
    const idx = Math.min(Math.max(0, Math.floor(Number(i) || 0)), n - 1)
    stop()
    _replayCharTagsTo(idx)
    state.currentIdx = idx
    _updateMetrics(state.snapshots[idx])
    state.eventBanner = null
  }

  function jumpToStart() {
    if (destroyed) return
    stop()
    if (state.mode === 'events') {
      state.currentEventIdx = -1
      state.runs = []
      state.caretPos = null
      state.activeAuthor = null
      state.activeKind = null
      state.liveTypedCount = 0
      state.livePasteCount = 0
      state.liveWordCount = 0
      state.eventBanner = null
      return
    }
    state.currentIdx = 0
    if (state.snapshots.length === 1) {
      _renderStatic(0) // keep single-snapshot sessions visible (bug e)
    } else {
      _resetDocState()
    }
    state.eventBanner = null
  }

  function jumpToEnd() {
    if (destroyed) return
    if (state.mode === 'events') {
      if (state.events.length === 0) return
      seekToEventIndex(state.events.length - 1)
      return
    }
    if (state.snapshots.length === 0) return
    seekToIndex(state.snapshots.length - 1)
  }

  // ─── Speed (bug b) ───────────────────────────────────────────
  function setSpeed(s) {
    const sp = Number(s)
    if (!Number.isFinite(sp) || sp <= 0) return
    if (sp === state.speed) return
    state.speed = sp
    // Cancel the pending timer and reschedule the SAME step at the new
    // speed — never fork a second timer chain.
    if (state.isPlaying && pendingStep) {
      const { fn, baseMs } = pendingStep
      _scheduleStep(fn, baseMs)
    }
  }

  // ─── Teardown (bug h) ────────────────────────────────────────
  function destroy() {
    stop()
    destroyed = true
    keyframeCache.clear()
    state.eventBanner = null
  }

  return {
    state,
    load,
    loadEvents,
    play,
    stop,
    seekToIndex,
    seekToEventIndex,
    jumpToStart,
    jumpToEnd,
    setSpeed,
    setTrueSpeed,
    getEventStats,
    destroy,
  }
}
