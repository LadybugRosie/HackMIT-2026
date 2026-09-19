<script setup>
import { onBeforeUnmount, onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { api } from '../../lib/api.js'
import { dueLabel } from '../../lib/format.js'
import { useAuth } from '../../composables/useAuth.js'
import Editor from '../../components/Editor.vue'
import LedgerPanel from '../../components/LedgerPanel.vue'

const route = useRoute()
const router = useRouter()
const auth = useAuth()
const sub = ref(null)
const session = ref(null)
const ledger = ref(null)
const getText = ref(() => '')
const error = ref('')
const submitting = ref(false)
const confirming = ref(false)
const saved = ref('')
let autosave = null

onMounted(async () => {
  try {
    const s = await api.get(`/api/submissions/${route.params.submissionId}`)
    if (s.status !== 'draft') return router.replace(`/student/submissions/${s.submission_id}`)
    sub.value = s
    session.value = await api.post(`/api/submissions/${s.submission_id}/ledger`)
  } catch (e) {
    error.value = e.message
  }
})

function onReady(payload) {
  ledger.value = payload.ledger
  getText.value = payload.getText
  autosave = setInterval(async () => {
    try { await api.put(`/api/submissions/${sub.value.submission_id}/draft`, { content: getText.value() }); saved.value = `Draft saved ${new Date().toLocaleTimeString()}` } catch {}
  }, 15000)
}

async function submit() {
  if (!confirming.value) { confirming.value = true; return }
  confirming.value = false
  submitting.value = true
  error.value = ''
  try {
    const cert = await ledger.value.finalize()
    if (!cert) { error.value = ledger.value.state.error || 'Could not finalize the ledger — check the panel.'; return }
    const res = await api.post(`/api/submissions/${sub.value.submission_id}/submit`, {
      session_id: ledger.value.state.sessionId, text: getText.value(), certificate: cert,
    })
    router.push(`/student/submissions/${res.submission.submission_id}`)
  } catch (e) {
    const code = e.detail?.code
    error.value = code === 'hash_mismatch' || code === 'not_bound'
      ? 'The text on screen no longer matches the finalized ledger. Reload the page and submit again.'
      : e.message
  } finally {
    submitting.value = false
  }
}

onBeforeUnmount(() => clearInterval(autosave))
</script>

<template>
  <p v-if="error" class="error">{{ error }}</p>
  <template v-if="sub && session">
    <div class="bar">
      <div>
        <p class="muted crumbs"><RouterLink :to="`/student/assignments/${sub.assignment_id}`">← {{ sub.assignment.title }}</RouterLink> · {{ sub.assignment.class_name }}</p>
        <h1>{{ sub.assignment.title }}</h1>
        <p class="muted small">{{ dueLabel(sub.assignment.due_ms) }} · {{ sub.assignment.points }} points <span v-if="saved">· {{ saved }}</span></p>
      </div>
      <div class="submit">
        <span v-if="confirming" class="muted small">Finalizes your ledger into a certificate and locks the text.</span>
        <button v-if="confirming" type="button" @click="confirming = false">Cancel</button>
        <button class="primary big" :disabled="submitting || !ledger || ledger.state.error" @click="submit">
          {{ submitting ? 'Submitting…' : confirming ? 'Confirm submit' : 'Submit' }}
        </button>
      </div>
    </div>

    <details class="card instr"><summary>Instructions</summary><p class="pre">{{ sub.assignment.instructions || '—' }}</p></details>

    <main class="grid">
      <Editor :session="session" :initial-text="session.text" :headers="auth.headers" plain
              placeholder="Start writing. Every edit is chained; pastes are recorded as external text." @ready="onReady" />
      <LedgerPanel v-if="ledger" :state="ledger.state" @flush="ledger.flush()" @finalize="ledger.finalize()"
                   @verify="ledger.verify(getText())" />
    </main>
  </template>
</template>

<style scoped>
.bar { display: flex; justify-content: space-between; align-items: flex-start; gap: 16px; margin-bottom: 10px; }
.crumbs { font-size: 13px; margin: 0 0 4px; }
.small { font-size: 13px; margin: 0; }
.big { padding: 10px 22px; font-size: 15px; }
.submit { display: flex; align-items: center; gap: 10px; flex-wrap: wrap; justify-content: flex-end; }
.instr { margin: 0 0 14px; } .instr summary { cursor: pointer; color: var(--muted); font-size: 14px; }
.pre { white-space: pre-wrap; margin: 8px 0 0; line-height: 1.55; font-size: 14px; }
.grid { display: grid; grid-template-columns: minmax(0, 1fr) 340px; gap: 20px; align-items: start; }
@media (max-width: 900px) { .grid { grid-template-columns: 1fr; } }
</style>
