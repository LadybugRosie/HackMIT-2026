/**
 * Client for the local hardware-witness helper (native/attest-hid) on 127.0.0.1:8093.
 * The helper is passive: it never talks to the attest server. The browser detects it, starts a
 * witness for the session, polls signed window statements and relays them to /attest-hid.
 * Everything here fails soft — no helper simply means the certificate tops out at L2.
 */
const HID_BASE = import.meta.env.VITE_ATTEST_HID ?? 'http://127.0.0.1:8093'
const DETECT_TIMEOUT_MS = 800

async function call(path, init = {}, timeoutMs = 4000) {
  const ctrl = new AbortController()
  const t = setTimeout(() => ctrl.abort(), timeoutMs)
  try {
    const r = await fetch(`${HID_BASE}${path}`, { ...init, signal: ctrl.signal, headers: { 'content-type': 'application/json', ...(init.headers || {}) } })
    const body = await r.json().catch(() => ({}))
    if (!r.ok) throw Object.assign(new Error(body.error || `helper ${r.status}`), { status: r.status })
    return body
  } finally {
    clearTimeout(t)
  }
}

/** null when no helper is listening (connection refused / timeout). */
export async function detect() {
  try { return await call('/status', {}, DETECT_TIMEOUT_MS) } catch { return null }
}

export const identity = () => call('/identity')
export const enrollSign = (challenge) => call('/enroll-sign', { method: 'POST', body: JSON.stringify({ challenge }) })
export const start = (sid, head) => call('/start', { method: 'POST', body: JSON.stringify({ sid, head }) })
export const statements = (sid, since) => call(`/statements?sid=${encodeURIComponent(sid)}&since=${since}`)
export const seal = (sid, head) => call('/seal', { method: 'POST', body: JSON.stringify({ sid, head }) })
