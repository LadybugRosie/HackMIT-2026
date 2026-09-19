import { reactive } from 'vue'

/** Mirrors server replay rules on code-point arrays, with a parallel provenance array. */
export function applyEvent(cps, origins, ev) {
  if (ev.k === 'ckpt') {
    const t = [...(ev.i || '')]
    return [t, Array(t.length).fill(ev.origin || 'EXT')]
  }
  if (ev.k === 'type' || ev.k === 'paste') {
    const ins = [...(ev.i || '')]
    cps.splice(ev.p, ev.d, ...ins)
    origins.splice(ev.p, ev.d, ...Array(ins.length).fill(ev.origin || 'T'))
  }
  return [cps, origins]
}

/** Group consecutive code points by origin -> [{ origin, text }]. */
export function toRuns(cps, origins) {
  const runs = []
  for (let i = 0; i < cps.length; i++) {
    const last = runs[runs.length - 1]
    if (last && last.origin === origins[i]) last.text += cps[i]
    else runs.push({ origin: origins[i], text: cps[i] })
  }
  return runs
}

const PAUSE_BEAT_MS = 600
const TYPE_BEAT_MS = 110
const MAX_REAL_GAP_MS = 30_000

export class PlaybackEngine {
  constructor(payload) {
    this.events = payload.events
    this.n = this.events.length
    this.pauseAfter = new Map(payload.pauses.map((p) => [p.after_seq, p.ms]))
    this.injected = (payload.hid_windows || []).filter((w) => w.injected)
    this._cps = []
    this._origins = []
    this._timer = null
    this.state = reactive({
      index: 0, text: '', runs: [], playing: false, speed: 4, realtime: false,
      elapsedMs: 0, durationMs: payload.duration_ms, markers: this._markers(),
    })
  }

  _markers() {
    const out = []
    // Hardware-witness injection windows: a band over the events that fell inside them.
    for (const w of this.injected) {
      let from = -1, to = -1
      this.events.forEach((e, i) => { if (e.ts >= w.t0 && e.ts < w.t1) { if (from < 0) from = i; to = i } })
      if (from >= 0) out.push({ i: from, to: to + 1, kind: 'injected', hw: w.hw_kd })
    }
    this.events.forEach((e, i) => {
      if (e.k === 'paste') out.push({ i, kind: e.origin === 'INT' ? 'internal' : 'paste' })
      else if (e.k === 'ckpt') out.push({ i, kind: 'paste' })
      else if (e.d > 0) out.push({ i, kind: 'delete' })
      if (this.pauseAfter.has(e.seq)) out.push({ i, kind: 'pause', ms: this.pauseAfter.get(e.seq) })
    })
    return out
  }

  _publish() {
    const s = this.state
    s.text = this._cps.join('')
    s.runs = toRuns(this._cps, this._origins)
    s.elapsedMs = s.index ? this.events[s.index - 1].ts - this.events[0].ts : 0
  }

  seek(n) {
    n = Math.max(0, Math.min(this.n, Math.round(n)))
    this._cps = []
    this._origins = []
    for (let i = 0; i < n; i++) [this._cps, this._origins] = applyEvent(this._cps, this._origins, this.events[i])
    this.state.index = n
    this._publish()
  }

  step() {
    if (this.state.index >= this.n) return false
    ;[this._cps, this._origins] = applyEvent(this._cps, this._origins, this.events[this.state.index])
    this.state.index++
    this._publish()
    return true
  }

  play() {
    if (this.state.playing) return
    if (this.state.index >= this.n) this.seek(0)
    this.state.playing = true
    const tick = () => {
      if (!this.state.playing) return
      if (!this.step()) { this.state.playing = false; return }
      const done = this.events[this.state.index - 1]
      const next = this.events[this.state.index]
      let delay
      if (this.state.realtime && next) delay = Math.min(next.ts - done.ts, MAX_REAL_GAP_MS)
      else delay = this.pauseAfter.has(done.seq) ? PAUSE_BEAT_MS : TYPE_BEAT_MS
      this._timer = setTimeout(tick, delay / this.state.speed)
    }
    tick()
  }

  pause() {
    this.state.playing = false
    clearTimeout(this._timer)
  }

  toStart() { this.pause(); this.seek(0) }
  toEnd() { this.pause(); this.seek(this.n) }
  nextMarker() {
    const m = this.state.markers.find((m) => m.i >= this.state.index)
    this.pause()
    this.seek(m ? m.i + 1 : this.n)
  }
  destroy() { this.pause() }
}

export function fmtClock(ms) {
  const s = Math.floor(ms / 1000)
  const m = Math.floor(s / 60)
  return `${m}:${String(s % 60).padStart(2, '0')}`
}
