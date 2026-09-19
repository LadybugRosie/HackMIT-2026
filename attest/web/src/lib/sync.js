import { reactive } from 'vue'
import { ChainBuilder, sha256Hex } from './chain.js'

const FLUSH_EVERY_EVENTS = 50
const FLUSH_EVERY_MS = 5000

/**
 * Owns one ledger session: chains events client-side, batches them, ships to /v1/ingest,
 * and exposes reactive state for the LedgerPanel. `getText` returns the current document
 * string exactly as capture.js diffs it. `headers` (object or function) is spread into every
 * request so the classroom app can authenticate bound sessions.
 */
export class LedgerSync {
  constructor({ apiBase = '', getText, headers = {} }) {
    this.apiBase = apiBase
    this.getText = getText
    this.headers = headers
    this.chain = null
    this.queue = []
    this.allEvents = []
    this.timer = null
    this.resumed = false
    this.state = reactive({
      sessionId: null, genesis: null, head: null, count: 0, pending: 0,
      replayOk: null, replayLen: 0, error: null, syncing: false, finalized: false,
      certificate: null, verification: null, integrity: null, resumed: false,
    })
  }

  _fetch(path, init = {}) {
    const extra = typeof this.headers === 'function' ? this.headers() : this.headers
    return fetch(`${this.apiBase}${path}`, {
      ...init,
      headers: { 'content-type': 'application/json', ...extra, ...(init.headers || {}) },
    })
  }

  _arm() {
    if (this.timer) return
    this.timer = setInterval(() => this.flush(), FLUSH_EVERY_MS)
    this._onBlur = () => this.flush()
    this._onUnload = () => this.flush(true)
    window.addEventListener('blur', this._onBlur)
    window.addEventListener('beforeunload', this._onUnload)
  }

  stop() {
    clearInterval(this.timer)
    this.timer = null
    if (this._onBlur) window.removeEventListener('blur', this._onBlur)
    if (this._onUnload) window.removeEventListener('beforeunload', this._onUnload)
  }

  /** Fresh, unbound session (the engine demo). */
  async start() {
    const r = await this._fetch('/v1/session/start', { method: 'POST', body: JSON.stringify({ client: 'attest-web' }) })
    if (!r.ok) throw new Error(`session start failed: ${r.status}`)
    const s = await r.json()
    this.chain = new ChainBuilder(s.genesis)
    Object.assign(this.state, { sessionId: s.session_id, genesis: s.genesis, head: s.genesis })
    this._arm()
  }

  /** Continue a session the server already holds (bound to a submission). */
  async resume({ session_id, genesis, chain_head, event_count, finalized = false }) {
    this.chain = new ChainBuilder(genesis)
    this.chain.head = chain_head
    this.chain.seq = event_count
    this.resumed = true
    Object.assign(this.state, {
      sessionId: session_id, genesis, head: chain_head, count: event_count, resumed: true, finalized: !!finalized,
    })
    if (!finalized) this._arm()
  }

  async record(raw) {
    if (!this.chain || this.state.finalized) return
    const ev = await this.chain.append(raw)
    this.queue.push(ev)
    this.allEvents.push(ev)
    this.state.head = ev.hash
    this.state.pending = this.queue.length
    if (this.queue.length >= FLUSH_EVERY_EVENTS) this.flush()
  }

  async flush(keepalive = false) {
    if (this.state.syncing || this.queue.length === 0 || this.state.error) return
    await this.chain._tail // wait for in-flight hashing so the batch is contiguous
    const batch = this.queue.splice(0, this.queue.length)
    const text = this.getText()
    this.state.syncing = true
    try {
      const r = await this._fetch('/v1/ingest', {
        method: 'POST', keepalive,
        body: JSON.stringify({
          session_id: this.state.sessionId, events: batch,
          content_sha256: await sha256Hex(text), content_len: [...text].length,
        }),
      })
      if (!r.ok) {
        const body = await r.json().catch(() => ({}))
        this.state.error = `ingest ${r.status}: ${JSON.stringify(body.detail ?? body)}`
        this.queue.unshift(...batch)
        return
      }
      const res = await r.json()
      Object.assign(this.state, {
        count: res.event_count, replayOk: res.replay_ok, replayLen: res.replay_len,
        pending: this.queue.length, integrity: res.integrity ?? this.state.integrity,
      })
      if (res.chain_head !== this.chain.head && this.queue.length === 0) {
        this.state.error = 'server head diverged from client head'
      }
    } catch (e) {
      this.state.error = String(e)
      this.queue.unshift(...batch)
    } finally {
      this.state.syncing = false
    }
  }

  /** Idempotent: returns the existing certificate if the session was already finalized. */
  async finalize() {
    if (this.state.certificate) return this.state.certificate
    await this.flush()
    if (this.state.error || this.queue.length) return null
    const text = this.getText()
    const r = await this._fetch(`/v1/session/${this.state.sessionId}/finalize`, {
      method: 'POST', body: JSON.stringify({ final_text: text }),
    })
    if (!r.ok) {
      const body = await r.json().catch(() => ({}))
      this.state.error = `finalize ${r.status}: ${JSON.stringify(body.detail ?? body)}`
      return null
    }
    this.state.certificate = await r.json()
    this.state.finalized = true
    this.stop()
    return this.state.certificate
  }

  /** Resumed sessions only hold this page-load's events, so verify certificate-only then. */
  async verify(text) {
    const r = await this._fetch('/v1/verify', {
      method: 'POST',
      body: JSON.stringify({ certificate: this.state.certificate, text, events: this.resumed ? undefined : this.allEvents }),
    })
    this.state.verification = await r.json()
    return this.state.verification
  }

  exportLedger() {
    return { session_id: this.state.sessionId, genesis: this.state.genesis, events: this.allEvents }
  }
}
