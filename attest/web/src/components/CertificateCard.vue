<script setup>
import { ref } from 'vue'
import { fmtDate } from '../lib/format.js'

const props = defineProps({
  certificate: { type: Object, required: true },
  /** Optional async () => VerifyResponse; when given, a "Verify on server" button appears. */
  verify: { type: Function, default: null },
  /** Optional async () => ledger JSON for download. */
  ledger: { type: Function, default: null },
})
const result = ref(null)
const busy = ref(false)
const short = (h) => (h ? `${h.slice(0, 10)}…${h.slice(-8)}` : '—')

function download(name, obj) {
  const blob = new Blob([JSON.stringify(obj, null, 2)], { type: 'application/json' })
  const a = Object.assign(document.createElement('a'), { href: URL.createObjectURL(blob), download: name })
  a.click()
  URL.revokeObjectURL(a.href)
}
async function runVerify() {
  busy.value = true
  try { result.value = await props.verify() } finally { busy.value = false }
}
async function downloadLedger() {
  download(`attest-ledger-${props.certificate.session_id.slice(0, 8)}.json`, await props.ledger())
}
</script>

<template>
  <section class="card cert">
    <h3>Proof-of-Writing certificate <span class="pill good">{{ certificate.assurance_level }}</span></h3>
    <p class="muted small">
      Binds the submitted text (<span class="mono">{{ short(certificate.doc_sha256) }}</span>) to the ledger that produced it
      (<span class="mono">{{ short(certificate.chain_root) }}</span>, {{ certificate.event_count }} events) · issued {{ fmtDate(certificate.created_ms) }}
    </p>
    <dl>
      <dt>Document hash</dt><dd class="mono">{{ certificate.doc_sha256 }}</dd>
      <dt>Chain root</dt><dd class="mono">{{ certificate.chain_root }}</dd>
      <dt>Merkle root</dt><dd class="mono">{{ certificate.merkle_root }}</dd>
      <dt>Genesis</dt><dd class="mono">{{ certificate.genesis }}</dd>
    </dl>
    <div class="actions">
      <button @click="download(`attest-cert-${certificate.session_id.slice(0, 8)}.json`, certificate)">Download certificate</button>
      <button v-if="ledger" @click="downloadLedger">Download ledger</button>
      <button v-if="verify" class="primary" :disabled="busy" @click="runVerify">{{ busy ? 'Verifying…' : 'Verify on server' }}</button>
    </div>
    <ul v-if="result" class="checks">
      <li v-for="c in result.checks" :key="c.name" :class="c.ok ? 'good' : 'bad'">
        <span class="mono">{{ c.ok ? 'PASS' : 'FAIL' }}</span> {{ c.name }} <small class="muted">{{ c.detail }}</small>
      </li>
      <li class="summary" :class="result.ok ? 'good' : 'bad'">
        {{ result.ok ? 'Certificate verifies' : 'Verification FAILED' }} · level {{ result.assurance_level }}
        <span v-if="result.event_count" class="muted"> · {{ result.event_count }} events re-derived</span>
      </li>
    </ul>
    <p class="muted tiny">Anyone can re-check this offline: <code>python3 verifier/attest_verify.py cert.json text.txt --events ledger.json</code></p>
  </section>
</template>

<style scoped>
h3 { margin: 0 0 6px; font-size: 15px; display: flex; align-items: center; gap: 8px; }
.small { font-size: 13px; margin: 0 0 10px; line-height: 1.5; }
.tiny { font-size: 12px; margin: 10px 0 0; }
dl { display: grid; grid-template-columns: 120px 1fr; gap: 4px 10px; margin: 0 0 10px; font-size: 13px; }
dt { color: var(--muted); } dd { margin: 0; word-break: break-all; font-size: 11.5px; }
.actions { display: flex; flex-wrap: wrap; gap: 8px; }
.checks { list-style: none; padding: 0; margin: 10px 0 0; display: grid; gap: 4px; font-size: 13px; }
.checks .summary { margin-top: 6px; font-weight: 600; }
code { font-family: ui-monospace, Menlo, monospace; font-size: 11px; }
</style>
