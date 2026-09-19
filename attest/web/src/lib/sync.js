import { reactive } from 'vue'
import { ChainBuilder, sha256Hex } from './chain.js'

const FLUSH_EVERY_EVENTS = 50
const FLUSH_EVERY_MS = 5000

/**
 * Owns one ledger session: chains events client-side, batches them, ships to /v1/ingest,
 * and exposes reactive state for the LedgerPanel. `getText` returns the current document
 * string exactly as capture.js diffs it.
 */
export class LedgerSync {
  constructor({ apiBase, getText }) {
    this.apiBase = apiBase
    this.getText = getText
    this.chain = null
    this.queue = []
    this.allEvents = []
    this.timer = null
    this.state = reactive({
      sessionId: null, genesis: null, head: null, count: 0, pending: 0,
      replayOk: null, replayLen: 0, error: null, syncing: false, finalized: false,
      certificate: null, verification: null, integrity: null,
    })
  }

  async start() {
    const r = await fetch(`${this.apiBase}/v1/session/start`, {
      method: 'POST', headers: { 'content-type': 'application/json' },
      body: JSON.stringify({ client: 'attest-web' }),
    })
    if (!r.ok) throw new Error(`session start failed: ${r.status}`)
    const s = await r.json()
    this.chain = new ChainBuilder(s.genesis)
    Object.assign(this.state, { sessionId: s.session_id, genesis: s.genesis, head: s.genesis })
    this.timer = setInterval(() => this.flush(), FLUSH_EVERY_MS)
    window.addEventListener('blur', () => this.flush())
    window.addEventListener('beforeunload', () => this.flush(true))
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
    // Wait for in-flight hashing so the batch is contiguous.
    await this.chain._tail
    const batch = this.queue.splice(0, this.queue.length)
    const text = this.getText()
    this.state.syncing = true
    try {
      const r = await fetch(`${this.apiBase}/v1/ingest`, {
        method: 'POST', headers: { 'content-type': 'application/json' }, keepalive,
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

  async finalize() {
    await this.flush()
    if (this.state.error || this.queue.length) return null
    const text = this.getText()
    const r = await fetch(`${this.apiBase}/v1/session/${this.state.sessionId}/finalize`, {
      method: 'POST', headers: { 'content-type': 'application/json' },
      body: JSON.stringify({ final_text: text }),
    })
    if (!r.ok) {
      const body = await r.json().catch(() => ({}))
      this.state.error = `finalize ${r.status}: ${JSON.stringify(body.detail ?? body)}`
      return null
    }
    this.state.certificate = await r.json()
    this.state.finalized = true
    clearInterval(this.timer)
    return this.state.certificate
  }

  async verify(text) {
    const r = await fetch(`${this.apiBase}/v1/verify`, {
      method: 'POST', headers: { 'content-type': 'application/json' },
      body: JSON.stringify({ certificate: this.state.certificate, text, events: this.allEvents }),
    })
    this.state.verification = await r.json()
    return this.state.verification
  }

  exportLedger() {
    return { session_id: this.state.sessionId, genesis: this.state.genesis, events: this.allEvents }
  }
}
