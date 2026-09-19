/**
 * Client-side forward hash chain. Must match server/attest/chain.py byte-for-byte:
 *   canon(e) = JSON of {d,i,k,p,prev,seq,src,ts} with keys sorted, no whitespace, raw UTF-8
 *   hash(e)  = SHA256( canon(e) || prev )   (prev as lowercase hex ASCII)
 * Timestamps/positions are integers; positions count Unicode code points.
 */
const CANON_KEYS = ['d', 'i', 'k', 'p', 'prev', 'seq', 'src', 'ts'] // already sorted

export function canon(event) {
  const obj = {}
  for (const k of CANON_KEYS) obj[k] = event[k] === undefined ? null : event[k]
  return JSON.stringify(obj)
}

const enc = new TextEncoder()

export async function sha256Hex(input) {
  const bytes = typeof input === 'string' ? enc.encode(input) : input
  const digest = await crypto.subtle.digest('SHA-256', bytes)
  return [...new Uint8Array(digest)].map((b) => b.toString(16).padStart(2, '0')).join('')
}

export async function linkHash(event) {
  const c = enc.encode(canon(event))
  const p = enc.encode(event.prev)
  const buf = new Uint8Array(c.length + p.length)
  buf.set(c, 0)
  buf.set(p, c.length)
  return sha256Hex(buf)
}

/** Builds chained events sequentially so seq/prev never interleave under async hashing. */
export class ChainBuilder {
  constructor(genesis) {
    this.head = genesis
    this.seq = 0
    this._tail = Promise.resolve()
  }

  /** raw = { ts, p, d, i, k, src? } → resolves to the fully chained event. */
  append(raw) {
    const run = async () => {
      const event = {
        seq: this.seq, ts: raw.ts, p: raw.p, d: raw.d, i: raw.i, k: raw.k,
        src: raw.src ?? null, prev: this.head,
      }
      event.hash = await linkHash(event)
      this.head = event.hash
      this.seq += 1
      return event
    }
    const p = this._tail.then(run)
    this._tail = p.catch(() => {})
    return p
  }
}
