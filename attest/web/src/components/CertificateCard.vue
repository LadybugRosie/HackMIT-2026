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
const att = props.certificate.claims?.attestation ?? null
const LEVEL_TEXT = {
  L0: 'ledger chain valid', L1: 'ledger bound to this text', L2: 'ledger bound to this text and signed on the student’s device',
  L3: 'L2 + a hardware witness below the browser saw a physical key-down for every keystroke (software witness — see README)',
}
const hid = att?.hid ?? null
const levelLabel = props.certificate.assurance_level === 'L3' ? 'L3 · witness' : props.certificate.assurance_level

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
    <h3>Proof-of-Writing certificate <span class="pill" :class="certificate.assurance_level >= 'L2' ? 'strong' : 'good'" :title="LEVEL_TEXT[certificate.assurance_level]">{{ levelLabel }}</span></h3>
    <p class="muted small">
      Binds the submitted text (<span class="mono">{{ short(certificate.doc_sha256) }}</span>) to the ledger that produced it
      (<span class="mono">{{ short(certificate.chain_root) }}</span>, {{ certificate.event_count }} events) · issued {{ fmtDate(certificate.created_ms) }}
    </p>
    <p v-if="att" class="small att" :class="att.final_head_signed ? 'good' : 'muted'">
      <template v-if="att.final_head_signed">
        Final chain head signed by the student’s enrolled device key{{ att.uv_at_seal ? ' with Touch ID' : '' }} ·
        {{ att.device_checkpoints }} device checkpoint{{ att.device_checkpoints === 1 ? '' : 's' }}
        <template v-if="att.timestamps"> · {{ att.timestamps }} trusted timestamp{{ att.timestamps === 1 ? '' : 's' }} ({{ att.first_timestamp?.slice(0, 16).replace('T', ' ') }}–{{ att.last_timestamp?.slice(11, 16) }} UTC)</template>
      </template>
      <template v-else>No device signature — the ledger is bound to the text (L1) but not to a particular machine.</template>
    </p>
    <p v-if="hid" class="small att" :class="hid.supports_l3 ? 'good' : 'warn'">
      <template v-if="hid.supports_l3">
        Hardware witness: {{ hid.windows }} windows, {{ Math.round(hid.coverage_ratio * 100) }}% coverage, editor {{ hid.ledger_kd }} / keyboard {{ hid.hw_kd }} key-downs, no injection ·
        {{ hid.devices.map((d) => `${d.builtin ? 'built-in keyboard' : d.id} ${Math.round(d.share * 100)}%`).join(', ') }} ·
        helper {{ hid.helper_trusted === true ? 'pinned' : hid.helper_trusted === false ? 'NOT pinned' : 'unpinned (software witness)' }}
      </template>
      <template v-else>Hardware witness present but did not qualify: {{ hid.reasons?.join('; ') || 'see verify output' }}</template>
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
      <li v-for="c in result.checks" :key="c.name" :class="c.ok ? 'good' : c.info ? 'warn' : 'bad'">
        <span class="mono">{{ c.ok ? 'PASS' : c.info ? 'INFO' : 'FAIL' }}</span> {{ c.name }} <small class="muted">{{ c.detail }}</small>
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
.pill.strong { color: var(--accent); }
.att { margin: -4px 0 10px; }
code { font-family: ui-monospace, Menlo, monospace; font-size: 11px; }
</style>
