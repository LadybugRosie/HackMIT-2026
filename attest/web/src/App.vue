<script setup>
import { ref } from 'vue'
import Editor from './components/Editor.vue'
import LedgerPanel from './components/LedgerPanel.vue'

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
  <header>
    <h1>attest</h1>
    <p class="muted">Every edit is hash-chained in your browser before it leaves. The server only accepts events that continue the chain, and a certificate only issues if the ledger replays to exactly the text you submit.</p>
  </header>
  <main>
    <Editor @ready="onReady" />
    <LedgerPanel
      v-if="ledger"
      :state="ledger.state"
      @flush="ledger.flush()"
      @finalize="ledger.finalize()"
      @verify="ledger.verify(getText())"
      @export-cert="download(`attest-cert-${ledger.state.sessionId.slice(0, 8)}.json`, ledger.state.certificate)"
      @export-ledger="download(`attest-ledger-${ledger.state.sessionId.slice(0, 8)}.json`, ledger.exportLedger())"
    />
    <p v-else class="muted">Starting session…</p>
  </main>
</template>
