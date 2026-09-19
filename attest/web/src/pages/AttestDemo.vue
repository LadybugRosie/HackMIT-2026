<script setup>
import { ref } from 'vue'
import Editor from '../components/Editor.vue'
import LedgerPanel from '../components/LedgerPanel.vue'

const ledger = ref(null)
const getText = ref(() => '')

function onReady(payload) {
  ledger.value = payload.ledger
  getText.value = payload.getText
}

function download(name, obj) {
  const blob = new Blob([JSON.stringify(obj, null, 2)], { type: 'application/json' })
  const a = Object.assign(document.createElement('a'), { href: URL.createObjectURL(blob), download: name })
  a.click()
  URL.revokeObjectURL(a.href)
}
</script>

<template>
  <header class="demo-head">
    <h1>attest <span class="muted">— engine demo</span></h1>
    <p class="muted">Every edit is hash-chained in your browser before it leaves. The server only accepts events that continue the chain, and a certificate only issues if the ledger replays to exactly the text you submit. Enroll this Mac's Secure Enclave key and the chain head is also signed on-device and timestamped by an independent authority, lifting the certificate to L2. This page is the bare engine; the classroom around it is the product.</p>
  </header>
  <main class="demo-grid">
    <Editor @ready="onReady" />
    <LedgerPanel
      v-if="ledger"
      :state="ledger.state"
      @flush="ledger.flush()"
      @finalize="ledger.finalize()"
      @verify="ledger.verify(getText())"
      @enroll="ledger.enroll().catch(() => {})"
      @checkpoint="ledger.checkpoint('discouraged').catch(() => {})"
      @enroll-hid="ledger.enrollHid().catch(() => {})"
      @export-cert="download(`attest-cert-${ledger.state.sessionId.slice(0, 8)}.json`, ledger.state.certificate)"
      @export-ledger="download(`attest-ledger-${ledger.state.sessionId.slice(0, 8)}.json`, ledger.exportLedger())"
    />
    <p v-else class="muted">Starting session…</p>
  </main>
</template>

<style scoped>
.demo-head h1 { margin: 0 0 6px; font-size: 22px; }
.demo-head p { margin: 0 0 20px; max-width: 70ch; }
.demo-grid { display: grid; grid-template-columns: minmax(0, 1fr) 340px; gap: 20px; align-items: start; }
@media (max-width: 900px) { .demo-grid { grid-template-columns: 1fr; } }
</style>
