<template>
  <div class="playback-viewer">
    <!-- Empty -->
    <div v-if="isEmpty" class="state-message">No playback data available.</div>

    <template v-else>
      <!-- Session header — who + what -->
      <div class="session-header">
        <div class="sh-left">
          <div class="sh-title">{{ meta.title || 'Writing Session' }}</div>
          <div class="sh-authors">
            <template v-if="authorList.length">
              <span v-for="a in authorList" :key="a.uid" class="author-chip">
                <span class="author-dot" :style="{ background: authorColor(a.uid) }"></span>
                {{ a.name }}
              </span>
            </template>
            <span v-else-if="meta.studentName" class="author-chip">
              <span class="author-dot author-dot-neutral"></span>
              {{ meta.studentName }}
            </span>
          </div>
        </div>
        <div class="sh-right">
          <!-- Live "who is working" status -->
          <transition name="fade">
            <span v-if="liveStatus" class="live-status" :class="'ls-' + (pb.activeKind || 'typing')">
              {{ liveStatus }}
            </span>
          </transition>
          <span class="fidelity-badge" :title="isEventMode
            ? 'Replaying the exact recorded keystroke events'
            : 'Reconstructed from periodic snapshots (legacy recording)'">
            {{ isEventMode ? '⚡ Exact replay' : '≈ Reconstructed' }}
          </span>
        </div>
      </div>

      <!-- Timeline -->
      <div class="timeline-section">
        <div class="timeline-bar" @click="onTimelineClick">
          <!-- Event markers (paste = red, delete = amber, idle = gray) -->
          <div v-for="(m, i) in timelineMarkers" :key="'m' + i"
            class="tl-marker" :class="'tlm-' + m.kind"
            :style="{ left: m.pct + '%' }"
            :title="m.label" />
          <div class="tl-progress" :style="{ width: playheadPct + '%' }" />
          <div class="tl-playhead" :style="{ left: playheadPct + '%' }" />
        </div>
        <div class="tl-times">
          <span>{{ formatClockTime(startTime) }}</span>
          <span class="tl-elapsed">{{ elapsedFormatted }}</span>
          <span>{{ formatClockTime(endTime) }}</span>
        </div>
      </div>

      <!-- Controls -->
      <div class="controls">
        <button class="ctrl-btn" @click="engine.jumpToStart">
          <svg width="18" height="18" viewBox="0 0 24 24" fill="currentColor"><path d="M6 6h2v12H6zm3.5 6l8.5 6V6z"/></svg>
        </button>
        <button class="ctrl-btn ctrl-play" @click="togglePlay">
          <svg v-if="!pb.isPlaying" width="22" height="22" viewBox="0 0 24 24" fill="currentColor"><path d="M8 5v14l11-7z"/></svg>
          <svg v-else width="22" height="22" viewBox="0 0 24 24" fill="currentColor"><path d="M6 19h4V5H6v14zm8-14v14h4V5h-4z"/></svg>
        </button>
        <button class="ctrl-btn" @click="engine.jumpToEnd">
          <svg width="18" height="18" viewBox="0 0 24 24" fill="currentColor"><path d="M6 18l8.5-6L6 6v12zM16 6v12h2V6h-2z"/></svg>
        </button>
        <div class="speed-group">
          <button v-for="s in [1,2,5,10]" :key="s" class="spd-btn" :class="{ active: pb.speed === s }" @click="engine.setSpeed(s)">{{ s }}x</button>
        </div>
        <button class="spd-btn true-speed-btn" :class="{ active: pb.trueSpeed }"
          @click="engine.setTrueSpeed(!pb.trueSpeed)"
          title="Honor the real pauses between keystrokes instead of compressing them">
          ⏱ Real time
        </button>
        <span class="snap-counter">
          {{ isEventMode
            ? `${Math.max(0, pb.currentEventIdx + 1)}/${pb.events.length} events`
            : `${pb.currentIdx + 1}/${pb.snapshots.length}` }}
        </span>
      </div>

      <!-- Content -->
      <div class="content-area">
        <!-- Document -->
        <div class="doc-panel">
          <!-- EVENT BANNER OVERLAY -->
          <transition name="banner">
            <div v-if="pb.eventBanner" class="event-banner" :class="'banner-' + pb.eventBanner.type">
              <div class="banner-icon">{{ pb.eventBanner.icon }}</div>
              <div class="banner-label">{{ pb.eventBanner.label }}</div>
              <div class="banner-detail" v-if="pb.eventBanner.detail">{{ pb.eventBanner.detail }}</div>
            </div>
          </transition>

          <div class="doc-paper" ref="docPaper">
            <!-- EVENT MODE: compact runs with provenance + author attribution -->
            <template v-if="isEventMode">
              <template v-for="(piece, i) in displayRuns" :key="i">
                <span v-if="piece.caret" class="cursor"></span>
                <span v-else
                  :class="[piece.origin === 'pasted' ? 'ch-pasted' : '']"
                  :style="runAuthorStyle(piece)"
                  :title="runTitle(piece)"
                >{{ piece.text }}</span>
              </template>
              <span v-if="pb.caretPos === null && pb.isPlaying" class="cursor"></span>
            </template>

            <!-- SNAPSHOT MODE: per-character provenance (legacy sessions) -->
            <template v-else>
              <span v-for="(c, i) in pb.charTags" :key="i"
                :class="[
                  c.origin === 'pasted' ? 'ch-pasted' : '',
                  c.justAdded ? 'ch-just-added' : '',
                ]"
              >{{ c.ch }}</span>
              <span class="cursor" v-if="pb.isPlaying"></span>
            </template>
          </div>
        </div>

        <!-- Sidebar — every metric derived from the document provenance shown
             on screen, so the numbers always match the colored characters. -->
        <div class="sidebar">
          <div class="side-card">
            <div class="sc-label">Words</div>
            <div class="sc-val">{{ pb.liveWordCount }}</div>
          </div>
          <div class="side-card">
            <div class="sc-label">Typed</div>
            <div class="sc-val sc-green">{{ typedCharsInDoc }} <span class="sc-unit">chars<template v-if="docLength > 0"> · {{ typedPct }}%</template></span></div>
          </div>
          <div class="side-card">
            <div class="sc-label">Pasted</div>
            <div class="sc-val" :class="pastedCharsInDoc > 0 ? 'sc-red' : ''">{{ pastedCharsInDoc }} <span class="sc-unit">chars<template v-if="docLength > 0 && pastedCharsInDoc > 0"> · {{ pastedPct }}%</template></span></div>
          </div>
          <div v-if="docLength > 0" class="side-card">
            <div class="sc-label">Composition</div>
            <div class="comp-bar" :title="typedPct + '% typed · ' + pastedPct + '% pasted'">
              <div class="comp-typed" :style="{ width: typedPct + '%' }"></div>
              <div class="comp-pasted" :style="{ width: pastedPct + '%' }"></div>
            </div>
            <div class="comp-caption">{{ typedPct }}% typed · {{ pastedPct }}% pasted</div>
          </div>
          <div class="side-card">
            <div class="sc-label">Deleted</div>
            <div class="sc-val" :class="deletedCharsSoFar > 0 ? 'sc-amber' : ''">{{ deletedCharsSoFar }} <span class="sc-unit">chars</span></div>
          </div>
          <div class="side-card">
            <div class="sc-label">Paste Events</div>
            <div class="sc-val" :class="pasteEventsSoFar > 0 ? 'sc-red' : ''">{{ pasteEventsSoFar }}</div>
          </div>
          <div class="side-card">
            <div class="sc-label">Document Length</div>
            <div class="sc-val">{{ docLength }} <span class="sc-unit">chars</span></div>
          </div>
          <div class="side-card">
            <div class="sc-label">Elapsed</div>
            <div class="sc-val sc-muted">{{ elapsedFormatted }}</div>
          </div>

          <!-- Legend -->
          <div class="side-card legend-card">
            <div class="sc-label">Legend</div>
            <div class="legend-row"><span class="legend-swatch swatch-typed"></span> Typed text</div>
            <div class="legend-row"><span class="legend-swatch swatch-pasted"></span> Pasted text</div>
            <div v-if="!isEventMode" class="legend-row"><span class="legend-swatch swatch-fresh"></span> Just appeared</div>
            <template v-if="isMultiAuthor">
              <div v-for="a in authorList" :key="'lg' + a.uid" class="legend-row">
                <span class="legend-swatch" :style="{ background: authorBg(a.uid), borderBottom: '2px solid ' + authorColor(a.uid) }"></span>
                {{ a.name }}
              </div>
            </template>
          </div>
        </div>
      </div>

      <!-- ═══ Paste events card + Activity timeline ═══ -->
      <div class="events-area">
        <!-- PASTE EVENTS — one row per paste, click to jump to it in the replay -->
        <div class="events-card paste-card">
          <div class="ec-head">
            <span class="ec-title">📋 Paste Events</span>
            <span class="ec-count" :class="pasteSegments.length > 0 ? 'sc-red' : ''">{{ pasteSegments.length }}</span>
          </div>
          <div v-if="pasteSegments.length === 0" class="ec-empty">No pastes detected in this session.</div>
          <div v-else class="ec-list">
            <button v-for="(seg, i) in pasteSegments" :key="'p' + i"
              class="ec-row ec-paste-row" :class="{ current: isCurrentSegment(seg) }"
              @click="jumpToSegment(seg)"
              title="Jump to this paste in the replay">
              <span class="ec-time">{{ formatClockTime(seg.startT) }}</span>
              <span class="ec-icon">📋</span>
              <span class="ec-desc">
                <strong>{{ seg.chars }} chars pasted</strong>
                <span v-if="docLength > 0" class="ec-pct">({{ Math.min(100, Math.round(seg.chars / docLength * 100)) }}% of document)</span>
                <span v-if="seg.authorName" class="ec-author" :style="{ color: authorColor(seg.author) }">
                  by {{ seg.authorName }}
                </span>
                <span v-if="seg.preview" class="ec-preview">“{{ seg.preview }}{{ seg.preview.length >= 300 ? '…' : '' }}”</span>
              </span>
              <span class="ec-jump">▶</span>
            </button>
          </div>
        </div>

        <!-- ACTIVITY TIMELINE — every segment of work, click to jump -->
        <div class="events-card">
          <div class="ec-head">
            <span class="ec-title">🕒 Activity Timeline</span>
            <span class="ec-count">{{ activitySegments.length }}</span>
          </div>
          <div v-if="activitySegments.length === 0" class="ec-empty">No activity recorded.</div>
          <div v-else class="ec-list">
            <button v-for="(seg, i) in activitySegments" :key="'s' + i"
              class="ec-row" :class="['ecr-' + seg.kind, { current: isCurrentSegment(seg) }]"
              @click="jumpToSegment(seg)"
              title="Jump to this moment in the replay">
              <span class="ec-time">{{ formatClockTime(seg.startT) }}</span>
              <span class="ec-icon">{{ segIcon(seg.kind) }}</span>
              <span class="ec-desc">
                <strong>{{ segLabel(seg) }}</strong>
                <span v-if="seg.authorName" class="ec-author" :style="{ color: authorColor(seg.author) }">
                  — {{ seg.authorName }}
                </span>
              </span>
              <span class="ec-jump">▶</span>
            </button>
          </div>
        </div>
      </div>
    </template>
  </div>
</template>

<script setup>
/**
 * PlaybackViewer.vue — Reusable session playback viewer.
 *
 * Driven by the createPlaybackEngine() state machine. Used by the teacher
 * playback page, the researcher results page, the student submission page
 * and the public share page.
 *
 * Two data sources, chosen automatically:
 *  - events (v2): discrete edit events — exact char-by-char replay with
 *    per-author attribution (collab-aware). Preferred when present.
 *  - snapshots (v1): periodic document states — legacy reconstruction.
 *
 * Props:
 *  - snapshots: raw (possibly delta-compressed) snapshot array
 *  - events:    merged edit-event stream from GET /session-playback/:id/events
 *  - authors:   { user_id: displayName } map for attribution
 *  - meta:      { studentName, title, totalDurationMs } from the host page
 */
import { ref, computed, watch, nextTick, onBeforeUnmount } from 'vue'
import {
  createPlaybackEngine, formatDuration, formatClockTime, detectSnapshotEvent,
  buildEventSegments, buildSnapshotSegments, runsLength,
} from '@/composables/playback-engine'

const props = defineProps({
  snapshots: { type: Array, default: () => [] },
  events: { type: Array, default: () => [] },
  authors: { type: Object, default: () => ({}) },
  meta: { type: Object, default: () => ({}) },
})

const engine = createPlaybackEngine()
const pb = engine.state

const docPaper = ref(null)

// Load whichever source is richer: events (exact) > snapshots (reconstructed)
function reload() {
  const ok = props.events?.length
    ? engine.loadEvents(props.events, props.authors || {})
    : false
  if (!ok) engine.load(props.snapshots || [])
}
watch(() => [props.snapshots, props.events], reload, { immediate: true })

// ─── Mode helpers ────────────────────────────────────────────
const isEventMode = computed(() => pb.mode === 'events')
const isEmpty = computed(() =>
  pb.mode === 'events' ? pb.events.length === 0 : pb.snapshots.length === 0)

// ─── Authors ─────────────────────────────────────────────────
const authorList = computed(() => {
  const out = []
  for (const [uid, name] of Object.entries(pb.authors || {})) {
    out.push({ uid, name })
  }
  // Single-author legacy fallback: the host page's meta name
  if (!out.length && isEventMode.value) {
    const uids = new Set(pb.events.map(e => e.a).filter(Boolean))
    for (const uid of uids) out.push({ uid, name: props.meta?.studentName || 'Author' })
  }
  return out
})
const isMultiAuthor = computed(() => authorList.value.length > 1)

function authorHue(id) {
  const str = String(id || 'anonymous')
  let hash = 0
  for (let i = 0; i < str.length; i++) hash = ((hash << 5) - hash + str.charCodeAt(i)) | 0
  return Math.abs(hash) % 360
}
function authorColor(id) { return id ? `hsl(${authorHue(id)}, 65%, 45%)` : '#6b7280' }
function authorBg(id) { return id ? `hsl(${authorHue(id)}, 70%, 93%)` : '#f3f4f6' }

function runAuthorStyle(piece) {
  // Per-author tint only matters when several people wrote together;
  // pasted text keeps its red treatment from the class.
  if (!isMultiAuthor.value || !piece.author || piece.origin === 'pasted') return {}
  return {
    background: authorBg(piece.author),
    borderBottom: `2px solid ${authorColor(piece.author)}`,
  }
}
function runTitle(piece) {
  const who = pb.authors?.[piece.author]
  if (!who) return undefined
  return piece.origin === 'pasted' ? `Pasted by ${who}` : `Typed by ${who}`
}

// Live "who is working" chip
const liveStatus = computed(() => {
  if (!pb.isPlaying) return ''
  const name = pb.authors?.[pb.activeAuthor] || props.meta?.studentName || ''
  if (!name && !pb.activeKind) return ''
  const verb = pb.activeKind === 'paste' ? 'pasted'
    : pb.activeKind === 'delete' ? 'is deleting'
    : 'is typing…'
  return name ? `✍️ ${name} ${verb}` : ''
})

// ─── Document rendering (event mode) ─────────────────────────
// Runs with the caret spliced in at its exact plaintext offset.
const displayRuns = computed(() => {
  const runs = pb.runs
  const caret = pb.caretPos
  if (caret === null || caret === undefined) {
    return runs.map(r => ({ text: r.text, origin: r.origin, author: r.author }))
  }
  const out = []
  let off = 0
  let placed = false
  for (const r of runs) {
    const end = off + r.text.length
    if (!placed && caret >= off && caret <= end) {
      const local = caret - off
      if (local > 0) out.push({ text: r.text.slice(0, local), origin: r.origin, author: r.author })
      out.push({ caret: true })
      if (local < r.text.length) out.push({ text: r.text.slice(local), origin: r.origin, author: r.author })
      placed = true
    } else {
      out.push({ text: r.text, origin: r.origin, author: r.author })
    }
    off = end
  }
  if (!placed) out.push({ caret: true })
  return out
})

// ─── Timeline ────────────────────────────────────────────────
const currentSnap = computed(() => pb.snapshots[pb.currentIdx] || null)

const startTime = computed(() => {
  const t = isEventMode.value ? pb.events[0]?.t : pb.snapshots[0]?.timestamp
  return Number.isFinite(t) ? t : 0
})

const endTime = computed(() => {
  const t = isEventMode.value
    ? pb.events[pb.events.length - 1]?.t
    : pb.snapshots[pb.snapshots.length - 1]?.timestamp
  return Number.isFinite(t) ? t : 0
})

const currentTime = computed(() => {
  if (isEventMode.value) {
    if (pb.currentEventIdx < 0) return startTime.value
    const t = pb.events[pb.currentEventIdx]?.t
    return Number.isFinite(t) ? t : startTime.value
  }
  const ts = currentSnap.value?.timestamp
  return Number.isFinite(ts) ? ts : startTime.value
})

const elapsedFormatted = computed(() => formatDuration(currentTime.value - startTime.value))

// Guard range===0 and non-finite timestamps (bug d)
const playheadPct = computed(() => {
  const range = endTime.value - startTime.value
  if (!Number.isFinite(range) || range <= 0) return 0
  return Math.min(100, Math.max(0, ((currentTime.value - startTime.value) / range) * 100))
})

// ─── Activity segments (shared by timeline markers, lists, paste card) ───
const activitySegments = computed(() => {
  return isEventMode.value
    ? buildEventSegments(pb.events, pb.authors || {})
    : buildSnapshotSegments(pb.snapshots)
})

const pasteSegments = computed(() => activitySegments.value.filter(s => s.kind === 'paste'))

const timelineMarkers = computed(() => {
  const range = endTime.value - startTime.value
  if (!Number.isFinite(range) || range <= 0) return []
  const out = []
  for (const seg of activitySegments.value) {
    if (seg.kind !== 'paste' && seg.kind !== 'delete') continue
    out.push({
      pct: Math.min(100, Math.max(0, ((seg.startT - startTime.value) / range) * 100)),
      kind: seg.kind,
      label: seg.kind === 'paste'
        ? `Paste — ${seg.chars} chars${seg.authorName ? ' by ' + seg.authorName : ''}`
        : `Deletion — ${seg.chars} chars`,
    })
  }
  return out
})

function segIcon(kind) {
  return { typing: '⌨️', paste: '📋', delete: '⌫', idle: '⏸️' }[kind] || '📝'
}
function segLabel(seg) {
  if (seg.kind === 'typing') {
    const ms = Math.max(0, seg.endT - seg.startT)
    // WPM only when the burst is long enough to be meaningful (>3s)
    const wpm = ms > 3000 ? Math.round((seg.chars / 5) / (ms / 60000)) : 0
    return `Typed ${seg.chars} chars (${formatDuration(ms)}${wpm > 0 ? ` · ${wpm} WPM` : ''})`
  }
  if (seg.kind === 'paste') return `Pasted ${seg.chars} chars`
  if (seg.kind === 'delete') return `Deleted ${seg.chars} chars`
  if (seg.kind === 'idle') return `Idle for ${formatDuration(seg.durMs || 0)}`
  return seg.kind
}

function jumpToSegment(seg) {
  if (isEventMode.value) engine.seekToEventIndex(seg.startIdx)
  else engine.seekToIndex(seg.startIdx)
}

function isCurrentSegment(seg) {
  const idx = isEventMode.value ? pb.currentEventIdx : pb.currentIdx
  return idx >= seg.startIdx && idx <= seg.endIdx
}

// ─── Metrics (mode-aware) ────────────────────────────────────
const pastedCharsInDoc = computed(() => {
  if (isEventMode.value) {
    let n = 0
    for (const r of pb.runs) if (r.origin === 'pasted') n += r.text.length
    return n
  }
  return pb.charTags.filter(c => c.origin === 'pasted').length
})
const typedCharsInDoc = computed(() => {
  if (isEventMode.value) {
    let n = 0
    for (const r of pb.runs) if (r.origin !== 'pasted') n += r.text.length
    return n
  }
  return pb.charTags.filter(c => c.origin !== 'pasted').length
})
const docLength = computed(() =>
  isEventMode.value ? runsLength(pb.runs) : pb.charTags.length)

const pastedPct = computed(() =>
  docLength.value > 0 ? Math.round(pastedCharsInDoc.value / docLength.value * 100) : 0)
const typedPct = computed(() =>
  docLength.value > 0 ? 100 - pastedPct.value : 0)

const pasteEventsSoFar = computed(() => {
  if (isEventMode.value) {
    return engine.getEventStats().pastePrefix[pb.currentEventIdx + 1] || 0
  }
  let n = 0
  for (let i = 1; i <= pb.currentIdx; i++) {
    if (detectSnapshotEvent(pb.snapshots[i - 1], pb.snapshots[i]) === 'paste') n++
  }
  return n
})
const deletedCharsSoFar = computed(() => {
  if (isEventMode.value) {
    return engine.getEventStats().deletePrefix[pb.currentEventIdx + 1] || 0
  }
  let n = 0
  for (let i = 1; i <= pb.currentIdx; i++) {
    const a = (pb.snapshots[i - 1]?.plaintext || '').length
    const b = (pb.snapshots[i]?.plaintext || '').length
    if (b < a) n += (a - b)
  }
  return n
})

// ─── Controls ────────────────────────────────────────────────
function togglePlay() {
  pb.isPlaying ? engine.stop() : engine.play()
}

function onTimelineClick(e) {
  const rect = e.currentTarget.getBoundingClientRect()
  if (!rect.width) return
  const range = endTime.value - startTime.value
  if (!Number.isFinite(range) || range <= 0) return
  const pct = Math.min(1, Math.max(0, (e.clientX - rect.left) / rect.width))
  const targetTime = startTime.value + pct * range

  if (isEventMode.value) {
    const evs = pb.events
    if (evs.length < 2) return
    let closest = -1, minDist = Infinity
    for (let i = 0; i < evs.length; i++) {
      const d = Math.abs(evs[i].t - targetTime)
      if (d < minDist) { minDist = d; closest = i }
    }
    if (closest >= 0) engine.seekToEventIndex(closest)
    return
  }

  const snaps = pb.snapshots
  if (snaps.length < 2) return // nothing to seek with fewer than 2 snapshots (bug f)
  let closest = -1, minDist = Infinity
  for (let i = 0; i < snaps.length; i++) {
    const ts = snaps[i].timestamp
    if (!Number.isFinite(ts)) continue // skip non-finite timestamps (bug f)
    const d = Math.abs(ts - targetTime)
    if (d < minDist) { minDist = d; closest = i }
  }
  if (closest >= 0) engine.seekToIndex(closest)
}

// Keep the latest text visible while the document grows
watch(() => (isEventMode.value ? pb.currentEventIdx : pb.charTags.length), () => {
  if (!pb.isPlaying) return
  nextTick(() => {
    if (docPaper.value) docPaper.value.scrollTop = docPaper.value.scrollHeight
  })
})

// Tear the engine down with the component (bug h)
onBeforeUnmount(() => engine.destroy())
</script>

<style scoped>
.playback-viewer {
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
  color: #1a1a1a;
}

.state-message { text-align: center; padding: 80px 20px; color: #6b7280; }

/* Session header */
.session-header {
  display: flex; align-items: center; justify-content: space-between; gap: 12px;
  background: #fff; border-radius: 12px; padding: 12px 20px; margin-bottom: 10px;
  box-shadow: 0 1px 2px rgba(0,0,0,0.05);
}
.sh-title { font-size: 15px; font-weight: 700; color: #111827; }
.sh-authors { display: flex; flex-wrap: wrap; gap: 6px; margin-top: 4px; }
.author-chip {
  display: inline-flex; align-items: center; gap: 6px;
  background: #f9fafb; border: 1px solid #e5e7eb; border-radius: 14px;
  padding: 2px 10px; font-size: 12.5px; font-weight: 600; color: #374151;
}
.author-dot { width: 9px; height: 9px; border-radius: 50%; display: inline-block; }
.author-dot-neutral { background: #6b7280; }
.sh-right { display: flex; align-items: center; gap: 8px; }
.live-status {
  font-size: 13px; font-weight: 700; padding: 4px 12px; border-radius: 14px;
  background: #ecfdf5; color: #047857; border: 1px solid #a7f3d0; white-space: nowrap;
}
.live-status.ls-paste { background: #fef2f2; color: #b91c1c; border-color: #fecaca; }
.live-status.ls-delete { background: #fffbeb; color: #b45309; border-color: #fde68a; }
.fidelity-badge {
  font-size: 11.5px; font-weight: 600; color: #6b7280;
  background: #f3f4f6; border-radius: 12px; padding: 3px 10px; white-space: nowrap;
}
.fade-enter-active, .fade-leave-active { transition: opacity 0.2s; }
.fade-enter-from, .fade-leave-to { opacity: 0; }

/* Timeline */
.timeline-section { background: #fff; border-radius: 12px; padding: 16px 20px; margin-bottom: 10px; box-shadow: 0 1px 2px rgba(0,0,0,0.05); }
.timeline-bar { position: relative; height: 8px; background: #e5e7eb; border-radius: 4px; cursor: pointer; overflow: visible; }
.tl-progress { position: absolute; top: 0; left: 0; height: 100%; background: #3b82f6; border-radius: 4px; transition: width 0.08s linear; }
.tl-playhead {
  position: absolute; top: -6px; width: 20px; height: 20px;
  background: #fff; border: 3px solid #3b82f6; border-radius: 50%;
  transform: translateX(-50%); z-index: 10; pointer-events: none;
  transition: left 0.08s linear; box-shadow: 0 1px 4px rgba(0,0,0,0.15);
}
.tl-marker {
  position: absolute; top: -3px; width: 3px; height: 14px; border-radius: 2px;
  transform: translateX(-50%); z-index: 5; pointer-events: none;
}
.tlm-paste { background: #ef4444; }
.tlm-delete { background: #f59e0b; }
.tl-times { display: flex; justify-content: space-between; margin-top: 8px; font-size: 12px; color: #9ca3af; }
.tl-elapsed { font-weight: 600; color: #374151; font-size: 13px; }

/* Controls */
.controls {
  display: flex; align-items: center; gap: 8px; padding: 10px 16px;
  background: #fff; border-radius: 12px; margin-bottom: 12px; box-shadow: 0 1px 2px rgba(0,0,0,0.05);
}
.ctrl-btn { background: none; border: 1px solid #e5e7eb; padding: 7px; border-radius: 8px; cursor: pointer; color: #374151; display: flex; align-items: center; }
.ctrl-btn:hover { background: #f3f4f6; }
.ctrl-play { background: #3b82f6; color: #fff; border-color: #3b82f6; padding: 10px; border-radius: 50%; }
.ctrl-play:hover { background: #2563eb; }
.speed-group { display: flex; gap: 3px; margin-left: 12px; padding-left: 12px; border-left: 1px solid #e5e7eb; }
.spd-btn { background: #f3f4f6; border: none; padding: 4px 10px; border-radius: 6px; cursor: pointer; font-size: 12px; font-weight: 500; color: #6b7280; }
.spd-btn.active { background: #3b82f6; color: #fff; }
.true-speed-btn { margin-left: 8px; }
.snap-counter { margin-left: auto; font-size: 13px; color: #9ca3af; }

/* Content */
.content-area { display: grid; grid-template-columns: 1fr 250px; gap: 12px; }

/* Document — white paper look */
.doc-panel {
  background: #fff; border-radius: 12px; box-shadow: 0 2px 8px rgba(0,0,0,0.08);
  overflow: hidden; position: relative;
}
.doc-paper {
  padding: 48px 56px; min-height: 500px; max-height: 65vh; overflow-y: auto;
  font-family: 'Georgia', 'Times New Roman', serif;
  font-size: 16px; line-height: 2; color: #1a1a1a;
  white-space: pre-wrap; word-wrap: break-word;
}

/* ─── Character styles ─── */
/* Pasted text: ALWAYS red background + red underline (permanent) */
.ch-pasted {
  background: #fecaca;
  border-bottom: 2px solid #ef4444;
  padding: 0 0.5px;
}
/* Just-added flash: brief green glow for typed, brighter red for pasted */
.ch-just-added {
  animation: charFlash 0.8s ease-out;
}
.ch-pasted.ch-just-added {
  animation: pasteFlash 0.8s ease-out;
}

@keyframes charFlash {
  0% { background: #86efac; }
  100% { background: transparent; }
}
@keyframes pasteFlash {
  0% { background: #fca5a5; box-shadow: 0 0 6px rgba(239,68,68,0.4); }
  100% { background: #fecaca; box-shadow: none; }
}

/* Cursor */
.cursor {
  display: inline-block; width: 2px; height: 1.15em;
  background: #3b82f6; vertical-align: text-bottom;
  margin-left: 1px; animation: blink 0.5s step-end infinite;
}
@keyframes blink { 0%,100% { opacity: 1; } 50% { opacity: 0; } }

/* ═══ EVENT BANNER ═══ */
.event-banner {
  position: absolute; top: 50%; left: 50%; transform: translate(-50%, -50%);
  z-index: 100; padding: 24px 44px; border-radius: 16px;
  text-align: center; backdrop-filter: blur(8px);
  animation: bannerPop 0.25s ease-out;
}
.banner-icon { font-size: 36px; margin-bottom: 8px; }
.banner-label { font-size: 22px; font-weight: 800; letter-spacing: 0.06em; text-transform: uppercase; }
.banner-detail { font-size: 13px; margin-top: 6px; opacity: 0.8; }

.banner-paste {
  background: rgba(254, 202, 202, 0.96); color: #991b1b;
  border: 3px solid #ef4444; box-shadow: 0 8px 40px rgba(239,68,68,0.35);
}
.banner-delete {
  background: rgba(254, 243, 199, 0.96); color: #92400e;
  border: 3px solid #f59e0b; box-shadow: 0 8px 40px rgba(245,158,11,0.3);
}
.banner-start {
  background: rgba(219, 234, 254, 0.96); color: #1e40af;
  border: 3px solid #3b82f6; box-shadow: 0 8px 40px rgba(59,130,246,0.3);
}
.banner-end {
  background: rgba(220, 252, 231, 0.96); color: #166534;
  border: 3px solid #22c55e; box-shadow: 0 8px 40px rgba(34,197,94,0.3);
}
.banner-idle {
  background: rgba(243, 244, 246, 0.96); color: #374151;
  border: 3px solid #9ca3af; box-shadow: 0 8px 40px rgba(107,114,128,0.25);
}

@keyframes bannerPop {
  0% { opacity: 0; transform: translate(-50%, -50%) scale(0.85); }
  100% { opacity: 1; transform: translate(-50%, -50%) scale(1); }
}
.banner-enter-active { animation: bannerPop 0.25s ease-out; }
.banner-leave-active { animation: bannerPop 0.15s ease-in reverse; }

/* Sidebar */
.sidebar { display: flex; flex-direction: column; gap: 8px; }
.side-card { background: #fff; border-radius: 10px; padding: 12px 14px; box-shadow: 0 1px 2px rgba(0,0,0,0.05); }
.sc-label { font-size: 11px; color: #9ca3af; text-transform: uppercase; letter-spacing: 0.04em; margin-bottom: 2px; }
.sc-val { font-size: 18px; font-weight: 600; font-variant-numeric: tabular-nums; }
.sc-unit { font-size: 12px; font-weight: 400; color: #9ca3af; }

/* Composition mini-bar: typed (green) vs pasted (red) share of the document */
.comp-bar {
  display: flex;
  height: 10px;
  border-radius: 5px;
  overflow: hidden;
  background: #e5e7eb;
  margin-top: 6px;
}
.comp-typed { background: #1e8e3e; height: 100%; transition: width 0.3s ease; }
.comp-pasted { background: #d93025; height: 100%; transition: width 0.3s ease; }
.comp-caption { font-size: 11px; color: #6b7280; margin-top: 5px; }
.sc-sub { font-size: 10px; color: #d1d5db; margin-top: 1px; }
.sc-red { color: #dc2626; }
.sc-green { color: #15803d; }
.sc-amber { color: #b45309; }
.sc-muted { color: #6b7280; font-size: 15px; }

.legend-card { font-size: 13px; }
.legend-row { display: flex; align-items: center; gap: 8px; margin-top: 6px; color: #374151; }
.legend-swatch { width: 16px; height: 12px; border-radius: 2px; display: inline-block; }
.swatch-typed { background: #fff; border: 1px solid #d1d5db; }
.swatch-pasted { background: #fecaca; border-bottom: 2px solid #ef4444; }
.swatch-fresh { background: #86efac; }

/* ═══ Events area (paste card + activity timeline) ═══ */
.events-area {
  display: grid; grid-template-columns: 1fr 1fr; gap: 12px; margin-top: 12px;
}
.events-card {
  background: #fff; border-radius: 12px; padding: 14px 16px;
  box-shadow: 0 1px 2px rgba(0,0,0,0.05);
}
.paste-card { border-top: 3px solid #ef4444; }
.ec-head { display: flex; align-items: center; justify-content: space-between; margin-bottom: 8px; }
.ec-title { font-size: 13px; font-weight: 700; color: #374151; text-transform: uppercase; letter-spacing: 0.04em; }
.ec-count { font-size: 15px; font-weight: 700; color: #6b7280; }
.ec-empty { font-size: 13px; color: #9ca3af; padding: 12px 0; }
.ec-list { max-height: 320px; overflow-y: auto; display: flex; flex-direction: column; gap: 4px; }
.ec-row {
  display: flex; align-items: flex-start; gap: 8px; width: 100%;
  background: #f9fafb; border: 1px solid #f3f4f6; border-radius: 8px;
  padding: 7px 10px; cursor: pointer; text-align: left; font-size: 13px; color: #1f2937;
  transition: background 0.12s, border-color 0.12s;
}
.ec-row:hover { background: #eff6ff; border-color: #bfdbfe; }
.ec-row.current { background: #dbeafe; border-color: #3b82f6; }
.ec-paste-row { background: #fef7f7; }
.ec-paste-row:hover { background: #fee2e2; border-color: #fecaca; }
.ecr-delete { background: #fffdf5; }
.ecr-idle { opacity: 0.75; }
.ec-time { font-size: 11.5px; color: #6b7280; font-variant-numeric: tabular-nums; white-space: nowrap; padding-top: 1px; }
.ec-icon { flex-shrink: 0; }
.ec-desc { flex: 1; min-width: 0; }
.ec-author { font-size: 12px; font-weight: 600; margin-left: 4px; }
.ec-pct { font-size: 12px; color: #d93025; font-weight: 600; margin-left: 4px; }
.ec-preview {
  display: block; font-size: 12px; color: #6b7280; font-style: italic;
  margin-top: 2px; overflow: hidden; text-overflow: ellipsis;
  display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical;
}
.ec-jump { color: #9ca3af; font-size: 11px; padding-top: 2px; }

@media (max-width: 900px) {
  .content-area { grid-template-columns: 1fr; }
  .sidebar { display: grid; grid-template-columns: repeat(3, 1fr); }
  .legend-card { grid-column: 1 / -1; }
  .doc-paper { padding: 24px 28px; }
  .events-area { grid-template-columns: 1fr; }
  .session-header { flex-direction: column; align-items: flex-start; }
}
</style>
