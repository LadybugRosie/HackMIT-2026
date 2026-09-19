<script setup>
import { computed, onMounted, ref } from 'vue'
import { useRoute } from 'vue-router'
import { api } from '../../lib/api.js'
import { fmtDate } from '../../lib/format.js'
import StatusChip from '../../components/StatusChip.vue'
import CertificateCard from '../../components/CertificateCard.vue'
import IntegrityPanel from '../../components/IntegrityPanel.vue'
import PlaybackViewer from '../../components/PlaybackViewer.vue'

const route = useRoute()
const sub = ref(null)
const playback = ref(null)
const tab = ref('text')
const error = ref('')
const grade = ref('')
const feedback = ref('')
const saving = ref(false)
const saved = ref('')

async function load() {
  try {
    sub.value = await api.get(`/api/submissions/${route.params.submissionId}`)
    grade.value = sub.value.grade ?? ''
    feedback.value = sub.value.feedback ?? ''
  } catch (e) { error.value = e.message }
}
onMounted(load)

async function openPlayback() {
  tab.value = 'playback'
  if (!playback.value) playback.value = await api.get(`/api/review/submissions/${sub.value.submission_id}/playback`)
}

/** Text as runs, external spans (code-point offsets from the certificate's integrity claims) highlighted. */
const runs = computed(() => {
  if (!sub.value) return []
  const cps = [...sub.value.content]
  const spans = [...(sub.value.integrity?.ext_spans ?? [])].sort((a, b) => a.start - b.start)
  const out = []
  let pos = 0
  for (const s of spans) {
    if (s.start > pos) out.push({ ext: false, text: cps.slice(pos, s.start).join('') })
    out.push({ ext: true, text: cps.slice(s.start, s.end).join('') })
    pos = s.end
  }
  if (pos < cps.length) out.push({ ext: false, text: cps.slice(pos).join('') })
  return out
})

const verify = () => api.post(`/api/review/submissions/${sub.value.submission_id}/verify`)
const ledger = () => api.get(`/api/review/submissions/${sub.value.submission_id}/ledger`)

async function saveGrade(andReturn = false) {
  saving.value = true
  error.value = ''
  try {
    sub.value = await api.post(`/api/submissions/${sub.value.submission_id}/grade`, { grade: Number(grade.value), feedback: feedback.value })
    if (andReturn) sub.value = await api.post(`/api/submissions/${sub.value.submission_id}/return`)
    saved.value = andReturn ? 'Returned to student.' : 'Grade saved.'
  } catch (e) {
    error.value = typeof e.detail === 'string' ? e.detail : e.message
  } finally {
    saving.value = false
  }
}
</script>

<template>
  <p v-if="error" class="error">{{ error }}</p>
  <template v-if="sub">
    <p class="muted crumbs">
      <RouterLink to="/teacher">Dashboard</RouterLink> /
      <RouterLink :to="`/teacher/classes/${sub.assignment.class_id}`">{{ sub.assignment.class_name }}</RouterLink> /
      <RouterLink :to="`/teacher/assignments/${sub.assignment_id}`">{{ sub.assignment.title }}</RouterLink>
    </p>
    <div class="head">
      <div>
        <h1>{{ sub.student_name }} <span class="muted">· {{ sub.assignment.title }}</span></h1>
        <p class="muted small">Submitted {{ fmtDate(sub.submitted_ms) }} · {{ [...sub.content].length }} characters</p>
      </div>
      <StatusChip :status="sub.status" />
    </div>

    <div class="grid">
      <div class="main">
        <div class="tabs">
          <button :class="{ on: tab === 'text' }" @click="tab = 'text'">Submitted text</button>
          <button :class="{ on: tab === 'playback' }" @click="openPlayback">Playback</button>
          <span class="legend muted small" v-if="tab === 'text'"><i class="sw"></i> pasted from outside</span>
        </div>
        <section v-if="tab === 'text'" class="card text">
          <p class="pre"><span v-for="(r, i) in runs" :key="i" :class="{ ext: r.ext }">{{ r.text }}</span></p>
        </section>
        <section v-else class="card">
          <PlaybackViewer v-if="playback" :payload="playback" />
          <p v-else class="muted">Loading ledger…</p>
        </section>

        <section class="card grade">
          <h3>Grade</h3>
          <div class="row">
            <label>Score <input v-model="grade" type="number" min="0" :max="sub.assignment.points" step="0.5" style="width: 110px" /> <span class="muted">/ {{ sub.assignment.points }}</span></label>
          </div>
          <label>Feedback <textarea v-model="feedback" rows="4" placeholder="What worked, what to improve…"></textarea></label>
          <div class="row actions">
            <button :disabled="saving || grade === ''" @click="saveGrade(false)">Save grade</button>
            <button class="primary" :disabled="saving || grade === ''" @click="saveGrade(true)">Save &amp; return to student</button>
            <span class="muted small">{{ saved }}</span>
          </div>
        </section>
      </div>

      <aside class="side">
        <CertificateCard v-if="sub.certificate" :certificate="sub.certificate" :verify="verify" :ledger="ledger" />
        <div v-if="sub.integrity" class="card"><IntegrityPanel :integrity="sub.integrity" /></div>
        <section class="card">
          <h3>Citations <span class="pill" :class="sub.factcheck_status === 'done' ? 'good' : 'muted'">{{ sub.factcheck_status }}</span></h3>
          <p class="muted small">Citation and link verification arrives with Stage 5.</p>
        </section>
        <section class="card">
          <h3>Similarity <span class="pill" :class="sub.similarity_status === 'done' ? 'good' : 'muted'">{{ sub.similarity_status }}</span></h3>
          <p class="muted small">In-class similarity arrives with Stage 6.</p>
        </section>
      </aside>
    </div>
  </template>
</template>

<style scoped>
.crumbs { font-size: 13px; margin: 0 0 6px; }
.head { display: flex; justify-content: space-between; align-items: center; gap: 12px; }
.head h1 { margin: 0; } .head .muted { font-weight: 400; }
.small { font-size: 13px; margin: 4px 0 14px; }
.grid { display: grid; grid-template-columns: minmax(0, 1fr) 360px; gap: 20px; align-items: start; }
.main, .side { display: grid; gap: 14px; }
.tabs { display: flex; align-items: center; gap: 6px; }
.tabs button { background: transparent; border-color: transparent; color: var(--muted); }
.tabs button.on { background: var(--surface); border-color: var(--border); color: var(--text); font-weight: 600; }
.legend { margin-left: auto; display: inline-flex; align-items: center; gap: 6px; }
.sw { display: inline-block; width: 12px; height: 12px; border-radius: 2px; background: color-mix(in srgb, var(--bad) 30%, transparent); }
.text .pre { white-space: pre-wrap; margin: 0; line-height: 1.7; font-size: 15px; }
.ext { background: color-mix(in srgb, var(--bad) 30%, transparent); border-radius: 2px; }
.grade h3, .side h3 { margin: 0 0 8px; font-size: 15px; display: flex; align-items: center; gap: 8px; }
.row { display: flex; align-items: center; gap: 10px; flex-wrap: wrap; }
.row label { display: flex; align-items: center; gap: 8px; }
.grade label { margin-bottom: 8px; }
.actions { margin-top: 6px; }
@media (max-width: 900px) { .grid { grid-template-columns: 1fr; } }
</style>
