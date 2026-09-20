<script setup>
import { computed } from 'vue'
import IntegrityPanel from './IntegrityPanel.vue'

const props = defineProps({ state: { type: Object, required: true } })
const emit = defineEmits(['flush', 'finalize', 'verify', 'export-ledger', 'export-cert', 'enroll', 'checkpoint', 'enroll-hid'])

const short = (h) => (h ? `${h.slice(0, 8)}…${h.slice(-6)}` : '—')
const clock = (ms) => new Date(ms).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' })
const attSummary = computed(() => props.state.certificate?.claims?.attestation ?? null)
const hid = computed(() => props.state.hid ?? {})
const hidStatus = computed(() => {
  const h = hid.value
  if (!h.available) return { label: 'no helper', cls: 'muted' }
  if (h.permission !== 'granted') return { label: 'needs Input Monitoring', cls: 'warn' }
  if (!h.enrolled) return { label: 'not enrolled', cls: 'warn' }
  if (h.injections?.length) return { label: 'injection detected', cls: 'bad' }
  if (h.witnessing) return { label: `witnessing · seal → ${props.state.levelPreview}`, cls: 'good' }
  return { label: props.state.finalized ? 'sealed' : 'idle', cls: 'muted' }
})
const hidLevelText = computed(() => props.state.certificate?.assurance_level === 'L3' ? 'L3 (software witness)' : props.state.certificate?.assurance_level)
const status = computed(() => {
  if (props.state.error) return { label: 'error', cls: 'bad' }
  if (props.state.finalized) return { label: 'finalized', cls: 'good' }
  if (props.state.syncing) return { label: 'syncing', cls: 'warn' }
  if (props.state.pending) return { label: `${props.state.pending} pending`, cls: 'warn' }
  return { label: 'in sync', cls: 'good' }
})
</script>

<template>
  <aside class="panel">
    <h2>Ledger <span class="pill" :class="status.cls">{{ status.label }}</span></h2>

    <dl>
      <dt>Session</dt><dd class="mono">{{ short(state.sessionId) }}</dd>
      <dt>Genesis</dt><dd class="mono">{{ short(state.genesis) }}</dd>
      <dt>Chain head</dt><dd class="mono head">{{ short(state.head) }}</dd>
      <dt>Events acked</dt><dd>{{ state.count }}</dd>
      <dt>Replay binds</dt>
      <dd>
        <span v-if="state.replayOk === null" class="muted">no batch yet</span>
        <span v-else :class="state.replayOk ? 'good' : 'bad'">{{ state.replayOk ? `yes (${state.replayLen} chars)` : 'MISMATCH' }}</span>
      </dd>
    </dl>

    <p v-if="state.error" class="error mono">{{ state.error }}</p>

    <div class="actions">
      <button @click="emit('flush')" :disabled="state.finalized">Flush now</button>
      <button class="primary" @click="emit('finalize')" :disabled="state.finalized || !state.count">Finalize → certificate</button>
    </div>

    <IntegrityPanel v-if="state.integrity" :integrity="state.integrity" />

    <section class="device">
      <h3>Device key <span class="pill" :class="state.credentials.length ? 'good' : 'muted'">{{ state.credentials.length ? (state.finalized ? 'used' : `seal → ${state.levelPreview}`) : 'none · seal → L1' }}</span></h3>
      <template v-if="!state.webauthn">
        <p class="hint muted">This browser has no WebAuthn support, so the certificate stays at L1 (ledger bound to text).</p>
      </template>
      <template v-else-if="!state.credentials.length">
        <p class="hint muted">Enroll a key that lives in this Mac's Secure Enclave. At submit, one Touch ID signs the final chain head, so the certificate proves the ledger was on <em>this</em> device. Meanwhile the head is timestamped by an independent authority every 3 minutes — silently.</p>
        <div class="actions">
          <button class="primary" :disabled="state.enrolling || state.finalized" @click="emit('enroll')">{{ state.enrolling ? 'Waiting for Touch ID…' : 'Enroll this device' }}</button>
        </div>
      </template>
      <template v-else>
        <dl>
          <dt>Key</dt><dd class="mono">{{ short(state.credentials[0].credential_id) }}<span v-if="state.credentials.length > 1" class="muted"> +{{ state.credentials.length - 1 }}</span></dd>
          <dt>Checkpoints</dt><dd>{{ state.checkpoints.length }}<span class="muted"> this page load · {{ state.checkpoints.filter((c) => c.device).length }} device-signed</span></dd>
        </dl>
        <ul v-if="state.checkpoints.length" class="ckpts">
          <li v-for="c in state.checkpoints.slice(-4)" :key="c.head" class="mono">
            {{ clock(c.ts) }} · head {{ c.head.slice(0, 8) }} · {{ c.at }} events{{ c.device ? (c.uv ? ' · Touch ID' : ' · device') : '' }}
            <span v-if="c.timestamp" class="good"> · TSA {{ c.timestamp.replace('T', ' ').replace('Z', 'Z') }}</span>
            <span v-else-if="c.timestampError" class="warn" :title="c.timestampError"> · no TSA</span>
          </li>
        </ul>
        <div class="actions">
          <button :disabled="state.signing || state.finalized || !state.count" @click="emit('checkpoint')" title="Optional: a device-signed checkpoint mid-session (Touch ID)">{{ state.signing ? 'Signing…' : 'Sign head now (Touch ID)' }}</button>
        </div>
      </template>
      <p v-if="state.attestError" class="warn small">{{ state.attestError }}</p>
    </section>

    <section class="device">
      <h3>Hardware witness <span class="pill" :class="hidStatus.cls">{{ hidStatus.label }}</span></h3>
      <template v-if="!hid.available">
        <p class="hint muted">Run <code>native/attest-hid</code> for L3: a helper below the browser counts <em>physical</em> key-downs and signs them, so the certificate can prove the keystrokes were typed, not injected. It never records which keys.</p>
      </template>
      <template v-else-if="hid.permission !== 'granted'">
        <p class="hint muted">Helper found, but macOS has not granted it Input Monitoring. System Settings → Privacy &amp; Security → Input Monitoring → enable <em>attest-hid</em>, then relaunch it.</p>
      </template>
      <template v-else-if="!hid.enrolled">
        <p class="hint muted">Helper running ({{ hid.backend === 'secure_enclave' ? 'Secure Enclave key' : 'software key' }}){{ hid.witnessing ? ' and already counting for this session' : '' }}. Enroll its key under your account so its statements count.</p>
        <div class="actions">
          <button class="primary" :disabled="hid.enrolling || state.finalized" @click="emit('enroll-hid')">{{ hid.enrolling ? 'Enrolling…' : 'Enroll witness' }}</button>
        </div>
      </template>
      <template v-else>
        <dl>
          <dt>Helper</dt><dd class="mono">{{ short(hid.cdhash) }} <span class="muted">· {{ hid.backend === 'secure_enclave' ? 'Enclave key' : 'software key' }}</span></dd>
          <dt>Windows</dt><dd>{{ hid.windows }} <span class="muted">relayed</span></dd>
          <dt v-if="hid.summary">Key-downs</dt>
          <dd v-if="hid.summary" :class="hid.summary.hw_kd >= hid.summary.ledger_kd - hid.summary.pending_kd ? 'good' : 'bad'">
            editor {{ hid.summary.ledger_kd - hid.summary.pending_kd }} · keyboard {{ hid.summary.hw_kd }} {{ hid.summary.hw_kd >= hid.summary.ledger_kd - hid.summary.pending_kd ? '✓' : '✗' }}
            <span v-if="hid.summary.pending_kd" class="muted"> · {{ hid.summary.pending_kd }} in the open window</span>
          </dd>
          <dt v-if="hid.summary?.devices?.length">Devices</dt>
          <dd v-if="hid.summary?.devices?.length" class="mono">
            <span v-for="d in hid.summary.devices" :key="d.id">{{ d.id }}{{ d.builtin ? ' (built-in)' : '' }} {{ Math.round(d.share * 100) }}% </span>
          </dd>
        </dl>
        <ul v-if="hid.injections?.length" class="ckpts bad">
          <li v-for="w in hid.injections" :key="w.seq" class="mono">{{ clock(w.t0) }}–{{ clock(w.t1) }} · editor {{ w.ledger_kd }} · keyboard {{ w.hw_kd }} — injected</li>
        </ul>
        <p v-else-if="hid.summary && hid.summary.coverage_ratio < 1" class="warn small">Coverage {{ Math.round(hid.summary.coverage_ratio * 100) }}% — some keystrokes were typed before the witness started.</p>
      </template>
      <p v-if="hid.error" class="warn small">{{ hid.error }}</p>
    </section>

    <section v-if="state.certificate" class="cert">
      <h3>Certificate <span class="pill good">{{ hidLevelText }}</span></h3>
      <dl>
        <dt>doc_sha256</dt><dd class="mono">{{ short(state.certificate.doc_sha256) }}</dd>
        <dt>chain_root</dt><dd class="mono">{{ short(state.certificate.chain_root) }}</dd>
        <dt>merkle_root</dt><dd class="mono">{{ short(state.certificate.merkle_root) }}</dd>
        <dt>events</dt><dd>{{ state.certificate.event_count }}</dd>
        <dt>issuer</dt><dd class="mono">{{ state.certificate.issuer ? `key ${state.certificate.issuer.key_id}` : '—' }}</dd>
        <template v-if="attSummary">
          <dt>device</dt>
          <dd>
            <span v-if="attSummary.final_head_signed" class="good">final head signed{{ attSummary.uv_at_seal ? ' with Touch ID' : '' }}</span>
            <span v-else class="muted">not signed</span>
            · {{ attSummary.device_checkpoints }} checkpoint{{ attSummary.device_checkpoints === 1 ? '' : 's' }}
          </dd>
          <dt>timestamps</dt>
          <dd><span v-if="attSummary.timestamps">{{ attSummary.timestamps }} · {{ attSummary.first_timestamp?.slice(11, 19) }}–{{ attSummary.last_timestamp?.slice(11, 19) }} UTC</span><span v-else class="muted">none</span></dd>
          <template v-if="attSummary.hid">
            <dt>witness</dt>
            <dd>
              <span :class="attSummary.hid.supports_l3 ? 'good' : 'warn'">{{ attSummary.hid.supports_l3 ? 'agrees with the ledger' : 'did not qualify' }}</span>
              · {{ attSummary.hid.windows }} windows · editor {{ attSummary.hid.ledger_kd }} / keyboard {{ attSummary.hid.hw_kd }}
              <span v-if="attSummary.hid.reasons?.length" class="warn"> · {{ attSummary.hid.reasons[0] }}</span>
            </dd>
          </template>
        </template>
      </dl>
      <div class="actions">
        <button @click="emit('export-cert')">Download certificate</button>
        <button @click="emit('export-ledger')">Download ledger</button>
        <button class="primary" @click="emit('verify')">Verify current text</button>
      </div>
      <ul v-if="state.verification" class="checks">
        <li v-for="c in state.verification.checks" :key="c.name" :class="c.ok ? 'good' : c.info ? 'warn' : 'bad'">
          <span class="mono">{{ c.ok ? 'PASS' : c.info ? 'INFO' : 'FAIL' }}</span> {{ c.name }} <small class="muted">{{ c.detail }}</small>
        </li>
        <li class="summary" :class="state.verification.ok ? 'good' : 'bad'">
          {{ state.verification.ok ? 'Certificate verifies' : 'Verification FAILED' }} · level {{ state.verification.assurance_level }}
        </li>
      </ul>
      <p class="hint muted">Edit the text after finalizing, then verify again — the doc hash check should fail.</p>
    </section>
  </aside>
</template>

<style scoped>
.panel { border: 1px solid var(--border); border-radius: 8px; background: var(--surface); padding: 16px 18px; font-size: 14px; }
h2, h3 { margin: 0 0 12px; font-size: 15px; display: flex; align-items: center; gap: 8px; }
dl { display: grid; grid-template-columns: 110px 1fr; gap: 6px 10px; margin: 0 0 12px; }
dt { color: var(--muted); } dd { margin: 0; }
.mono { font-family: ui-monospace, SFMono-Regular, Menlo, monospace; font-size: 12.5px; }
.head { color: var(--accent); }
.pill { font-size: 11px; padding: 2px 8px; border-radius: 999px; border: 1px solid currentColor; font-weight: 600; }
.good { color: var(--good); } .bad { color: var(--bad); } .warn { color: var(--warn); } .muted { color: var(--muted); }
.error { background: color-mix(in srgb, var(--bad) 12%, transparent); padding: 8px; border-radius: 6px; word-break: break-all; }
.actions { display: flex; flex-wrap: wrap; gap: 8px; margin: 10px 0; }
button { padding: 7px 12px; border-radius: 6px; border: 1px solid var(--border); background: var(--surface-2); color: var(--text); cursor: pointer; }
button.primary { background: var(--accent); border-color: var(--accent); color: #fff; }
button:disabled { opacity: 0.45; cursor: not-allowed; }
.cert, .device { border-top: 1px solid var(--border); margin-top: 14px; padding-top: 14px; }
.pill.muted { color: var(--muted); }
.ckpts { list-style: none; padding: 0; margin: 0 0 8px; display: grid; gap: 3px; font-size: 11.5px; }
.small { font-size: 12px; margin: 6px 0 0; }
.checks { list-style: none; padding: 0; margin: 8px 0 0; display: grid; gap: 4px; }
.checks .summary { margin-top: 6px; font-weight: 600; }
.hint { font-size: 12px; margin-top: 10px; }
</style>
