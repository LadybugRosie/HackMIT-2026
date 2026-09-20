import { reactive } from 'vue'
import { ChainBuilder, sha256Hex } from './chain.js'
import { enroll as waEnroll, listCredentials, signHead, webauthnAvailable } from './webauthn.js'
import * as hid from './hid.js'

const FLUSH_EVERY_EVENTS = 50
const FLUSH_EVERY_MS = 5000
const CHECKPOINT_EVERY_MS = 3 * 60_000 // silent trusted-timestamp checkpoint over the head every ~3 minutes
const HID_POLL_MS = 6000               // relay the helper's signed windows to the server

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
    this.ckptTimer = null
    this.hidTimer = null
    this.hidSince = -1
    this.resumed = false
    this.sealing = false
    this.state = reactive({
      sessionId: null, genesis: null, head: null, count: 0, pending: 0,
      replayOk: null, replayLen: 0, error: null, syncing: false, finalized: false,
      certificate: null, verification: null, integrity: null, resumed: false,
      // Stage 3 (L2): device key + checkpoints
      webauthn: webauthnAvailable(), credentials: [], enrolling: false, signing: false,
      checkpoints: [], levelPreview: 'L1', attestError: null,
      // Stage 4 (L3): hardware witness
      hid: { available: false, permission: null, enrolled: false, keyId: null, backend: null, cdhash: null,
             witnessing: false, seg: null, windows: 0, relayed: 0, lastWindow: null, injections: [], summary: null,
             error: null, enrolling: false },
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
    clearInterval(this.ckptTimer)
    clearInterval(this.hidTimer)
    this.timer = this.ckptTimer = this.hidTimer = null
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
    this._armCheckpoints()
    this.refreshCredentials()
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
    if (!finalized) { this._arm(); this._armCheckpoints() }
    this.refreshCredentials()
  }

  async record(raw) {
    if (!this.chain || this.state.finalized || this.sealing) return
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

  /**
   * Idempotent: returns the existing certificate if the session was already finalized.
   * Sealing: stop recording, flush, and — when a device key is enrolled — sign the final head
   * with user verification (Touch ID) so the certificate can reach L2. If the signature is
   * declined the session still finalizes, at L1.
   */
  async finalize() {
    if (this.state.certificate) return this.state.certificate
    this.sealing = true
    await this.flush()
    if (this.state.error || this.queue.length) { this.sealing = false; return null }
    if (this.state.credentials.length && this.state.webauthn) {
      try { await this.checkpoint('required') } catch (e) { this.state.attestError = `seal signature skipped: ${e.message}` }
    }
    await this.sealWitness() // same final head as the device seal; `sealing` keeps it from moving
    const text = this.getText()
    const r = await this._fetch(`/v1/session/${this.state.sessionId}/finalize`, {
      method: 'POST', body: JSON.stringify({ final_text: text }),
    })
    if (!r.ok) {
      const body = await r.json().catch(() => ({}))
      this.state.error = `finalize ${r.status}: ${JSON.stringify(body.detail ?? body)}`
      this.sealing = false
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

  // -- Stage 3 (L2): device key + checkpoints ---------------------------------------------

  get _sessionPath() { return `/v1/session/${this.state.sessionId}` }

  async refreshCredentials() {
    if (!this.state.sessionId) return
    let all = []
    try { all = await listCredentials((p, i) => this._fetch(p, i), this._sessionPath) } catch { all = [] }
    this.state.credentials = all.filter((c) => (c.type ?? 'webauthn') === 'webauthn')
    const hidCred = all.find((c) => c.type === 'hid')
    this.state.hid.enrolled = !!hidCred
    this.detectHid(hidCred)
  }

  _armCheckpoints() {
    clearInterval(this.ckptTimer)
    this.ckptTimer = null
    if (!this.state.finalized) {
      this.ckptTimer = setInterval(() => this.timestampHead().catch(() => {}), CHECKPOINT_EVERY_MS)
    }
  }

  /**
   * Silent checkpoint: an RFC 3161 timestamp over the current head. No device key, no prompt — the
   * TSA's clock alone carries the "this ledger state existed by T" argument. The device signature
   * (Touch ID) happens once, at the seal.
   */
  async timestampHead() {
    if (this.state.finalized || this.state.signing || !this.state.count) return null
    await this.flush()
    while (this.state.syncing) await new Promise((r) => setTimeout(r, 50))
    if (this.queue.length || this.state.error) return null
    const head = this.chain.head
    if (this.state.checkpoints.some((c) => c.head === head)) return null // nothing new since the last one
    const r = await this._fetch(`${this._sessionPath}/timestamp`, { method: 'POST', body: JSON.stringify({ head }) })
    if (!r.ok) return null
    const res = await r.json()
    const ts = res.results[0]
    this.state.checkpoints = [...this.state.checkpoints, {
      head, at: res.at_event_count, ts: Date.now(), uv: false, device: false,
      timestamp: ts?.ok ? ts.data.gen_time : null, tsa: ts?.ok ? ts.data.tsa : null, timestampError: null,
    }]
    this.state.levelPreview = res.level_if_sealed_now
    return res
  }

  /** Create a device-bound key for this session's owner (Touch ID once). */
  async enroll(label = null) {
    this.state.enrolling = true
    this.state.attestError = null
    try {
      const cred = await waEnroll((p, i) => this._fetch(p, i), this._sessionPath, label)
      this.state.credentials = [...this.state.credentials, cred]
      this._armCheckpoints()
      return cred
    } catch (e) {
      this.state.attestError = e.name === 'NotAllowedError' ? 'Enrollment cancelled' : e.message
      throw e
    } finally {
      this.state.enrolling = false
    }
  }

  // -- Stage 4 (L3): hardware witness ----------------------------------------------------------

  /** Probe 127.0.0.1:8093; if the helper is up and its key is enrolled, start witnessing. */
  async detectHid(hidCred = null) {
    const st = await hid.detect()
    const h = this.state.hid
    if (!st) { h.available = false; h.witnessing = false; return }
    Object.assign(h, { available: true, permission: st.permission, keyId: st.key_id, backend: st.key_backend, cdhash: st.cdhash })
    if (h.enrolled && hidCred && hidCred.credential_id !== st.key_id) {
      h.error = 'a different witness key is enrolled for this account — re-enroll to use this helper'
    }
    if (st.permission === 'granted' && !h.witnessing && !this.state.finalized) await this.startWitness()
  }

  /** Register the helper's Secure Enclave key under this session's owner (no Touch ID: silent key). */
  async enrollHid() {
    const h = this.state.hid
    h.enrolling = true
    h.error = null
    try {
      const opts = await (await this._fetch(`${this._sessionPath}/enroll/options`)).json()
      const ident = await hid.identity()
      const signed = await hid.enrollSign(opts.challenge)
      const r = await this._fetch(`${this._sessionPath}/enroll-hid`, {
        method: 'POST',
        body: JSON.stringify({ public_key: ident.public_key, key_id: ident.key_id, cdhash: ident.cdhash,
          key_backend: ident.key_backend, signature: signed.signature, helper_version: ident.helper_version }),
      })
      if (!r.ok) { const b = await r.json().catch(() => ({})); throw new Error(b.detail?.detail || b.detail || `enroll-hid ${r.status}`) }
      h.enrolled = true
      if (h.witnessing) await this.relayHid()
      else await this.startWitness()
    } catch (e) {
      h.error = e.message
      throw e
    } finally {
      h.enrolling = false
    }
  }

  /** Anchor a witness segment at a head the server already holds, then relay windows as they close. */
  async startWitness() {
    const h = this.state.hid
    if (!h.available || h.witnessing || this.state.finalized) return
    try {
      await this.flush()
      while (this.state.syncing) await new Promise((r) => setTimeout(r, 50))
      const res = await hid.start(this.state.sessionId, this.chain.head)  // counting starts now, enrolled or not
      Object.assign(h, { witnessing: true, seg: res.seg, error: null })
      this.hidSince = -1
      clearInterval(this.hidTimer)
      this.hidTimer = setInterval(() => this.relayHid().catch(() => {}), HID_POLL_MS)
    } catch (e) {
      h.error = `witness: ${e.message}`
    }
  }

  /** Forward closed windows the helper has produced since the last relay (needs an enrolled key). */
  async relayHid(retried = false) {
    const h = this.state.hid
    if (!h.witnessing || !h.enrolled) return
    let res
    try {
      res = await hid.statements(this.state.sessionId, this.hidSince)
    } catch (e) {
      if (e.status === 404) {
        // The helper was restarted and no longer knows this session: open a new segment anchored
        // at the current head. Keystrokes typed in between are honestly unwitnessed (coverage < 100%).
        h.witnessing = false
        clearInterval(this.hidTimer)
        h.error = 'witness helper restarted — starting a new segment'
        await this.startWitness()
        return
      }
      throw e
    }
    const sts = res.statements || []
    if (!sts.length) return
    const r = await this._fetch(`${this._sessionPath}/attest-hid`, {
      method: 'POST', body: JSON.stringify({ key_id: h.keyId, statements: sts }),
    })
    if (!r.ok) {
      const b = await r.json().catch(() => ({}))
      const d = b.detail || {}
      if (d.code === 'hid_chain_break' && Number.isInteger(d.expected_seq) && !retried) {
        // After a page reload the server already holds part of this segment: resume from its tail.
        this.hidSince = d.expected_seq - 1
        return this.relayHid(true)
      }
      h.error = `relay ${r.status}: ${d.detail || JSON.stringify(b.detail ?? b)}`
      if (d.code === 'hid_chain_break' || d.code === 'unknown_head') { h.witnessing = false; clearInterval(this.hidTimer) }
      return
    }
    h.error = null
    const out = await r.json()
    this.hidSince = out.seq_to
    h.relayed += out.accepted
    h.windows = out.hid?.windows ?? h.windows
    h.summary = out.hid ?? null
    h.injections = out.hid?.injection_windows ?? []
    const last = sts[sts.length - 1]
    h.lastWindow = { t0: last.t0, t1: last.t1, hw: last.kd, final: !!last.final }
    this.state.levelPreview = out.level_if_sealed_now
    if (out.final) { h.witnessing = false; clearInterval(this.hidTimer) }
  }

  /** Terminal statement anchored at the final head; called during finalize after the device seal. */
  async sealWitness() {
    const h = this.state.hid
    if (!h.witnessing) return
    try {
      await hid.seal(this.state.sessionId, this.chain.head)
      await this.relayHid()
    } catch (e) {
      h.error = `seal witness: ${e.message}`
    }
  }

  /**
   * Sign the current chain head with the enrolled key. Flushes first so the head the device
   * signs is one the server has. On macOS the platform authenticator prompts Touch ID regardless
   * of `uv`, so this is used for the seal ('required') and the optional manual button — the
   * periodic checkpoints use timestampHead() instead.
   */
  async checkpoint(uv = 'discouraged') {
    if (!this.state.credentials.length || this.state.finalized || this.state.signing) return null
    this.state.signing = true
    this.state.attestError = null
    try {
      await this.flush()
      while (this.state.syncing) await new Promise((r) => setTimeout(r, 50)) // an in-flight batch must land first
      if (this.queue.length || this.state.error) throw new Error('ledger not in sync')
      const head = this.chain.head
      const res = await signHead((p, i) => this._fetch(p, i), this._sessionPath, head,
        this.state.credentials.map((c) => c.credential_id), uv)
      const wa = res.results.find((r) => r.kind === 'webauthn')
      const ts = res.results.find((r) => r.kind === 'timestamp')
      this.state.checkpoints = [...this.state.checkpoints, {
        head, at: res.at_event_count, ts: Date.now(), uv: !!wa?.data?.uv, device: true,
        timestamp: ts?.ok ? ts.data.gen_time : null, tsa: ts?.ok ? ts.data.tsa : null, timestampError: ts && !ts.ok ? ts.detail : null,
      }]
      this.state.levelPreview = res.level_if_sealed_now
      return res
    } catch (e) {
      this.state.attestError = e.name === 'NotAllowedError' ? 'Signature cancelled' : e.message
      throw e
    } finally {
      this.state.signing = false
    }
  }
}
