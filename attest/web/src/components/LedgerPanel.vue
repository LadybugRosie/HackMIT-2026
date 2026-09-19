<script setup>
import { computed } from 'vue'
import IntegrityPanel from './IntegrityPanel.vue'

const props = defineProps({ state: { type: Object, required: true } })
const emit = defineEmits(['flush', 'finalize', 'verify', 'export-ledger', 'export-cert'])

const short = (h) => (h ? `${h.slice(0, 8)}…${h.slice(-6)}` : '—')
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

    <section v-if="state.certificate" class="cert">
      <h3>Certificate <span class="pill good">{{ state.certificate.assurance_level }}</span></h3>
      <dl>
        <dt>doc_sha256</dt><dd class="mono">{{ short(state.certificate.doc_sha256) }}</dd>
        <dt>chain_root</dt><dd class="mono">{{ short(state.certificate.chain_root) }}</dd>
        <dt>merkle_root</dt><dd class="mono">{{ short(state.certificate.merkle_root) }}</dd>
        <dt>events</dt><dd>{{ state.certificate.event_count }}</dd>
      </dl>
      <div class="actions">
        <button @click="emit('export-cert')">Download certificate</button>
        <button @click="emit('export-ledger')">Download ledger</button>
        <button class="primary" @click="emit('verify')">Verify current text</button>
      </div>
      <ul v-if="state.verification" class="checks">
        <li v-for="c in state.verification.checks" :key="c.name" :class="c.ok ? 'good' : 'bad'">
          <span class="mono">{{ c.ok ? 'PASS' : 'FAIL' }}</span> {{ c.name }} <small class="muted">{{ c.detail }}</small>
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
.cert { border-top: 1px solid var(--border); margin-top: 14px; padding-top: 14px; }
.checks { list-style: none; padding: 0; margin: 8px 0 0; display: grid; gap: 4px; }
.checks .summary { margin-top: 6px; font-weight: 600; }
.hint { font-size: 12px; margin-top: 10px; }
</style>
