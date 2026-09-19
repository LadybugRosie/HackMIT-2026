<script setup>
import { onMounted, ref } from 'vue'
import { useRoute } from 'vue-router'
import { api } from '../../lib/api.js'
import { fmtDate } from '../../lib/format.js'
import StatusChip from '../../components/StatusChip.vue'
import CertificateCard from '../../components/CertificateCard.vue'
import IntegrityPanel from '../../components/IntegrityPanel.vue'

const route = useRoute()
const sub = ref(null)
const error = ref('')

onMounted(async () => {
  try { sub.value = await api.get(`/api/submissions/${route.params.submissionId}`) } catch (e) { error.value = e.message }
})
const verify = () => api.post(`/api/review/submissions/${sub.value.submission_id}/verify`)
const ledger = () => api.get(`/api/review/submissions/${sub.value.submission_id}/ledger`)
</script>

<template>
  <p v-if="error" class="error">{{ error }}</p>
  <template v-if="sub">
    <p class="muted crumbs"><RouterLink :to="`/student/assignments/${sub.assignment_id}`">← {{ sub.assignment.title }}</RouterLink> · {{ sub.assignment.class_name }}</p>
    <div class="head">
      <h1>{{ sub.assignment.title }}</h1>
      <StatusChip :status="sub.status" />
    </div>
    <p class="muted small">Submitted {{ fmtDate(sub.submitted_ms) }} · {{ [...sub.content].length }} characters</p>

    <div class="grid">
      <div>
        <section v-if="sub.status === 'returned'" class="card grade">
          <h3>Grade: {{ sub.grade }} / {{ sub.assignment.points }}</h3>
          <p class="pre">{{ sub.feedback || 'No written feedback.' }}</p>
        </section>
        <section v-else-if="sub.status === 'graded'" class="card muted small">Graded — your teacher hasn't released it yet.</section>
        <section class="card text"><p class="pre">{{ sub.content }}</p></section>
      </div>
      <aside class="side">
        <CertificateCard v-if="sub.certificate" :certificate="sub.certificate" :verify="verify" :ledger="ledger" />
        <div v-if="sub.integrity" class="card"><IntegrityPanel :integrity="sub.integrity" /></div>
      </aside>
    </div>
  </template>
</template>

<style scoped>
.crumbs { font-size: 13px; margin: 0 0 6px; }
.head { display: flex; align-items: center; gap: 12px; }
.small { font-size: 13px; margin: 4px 0 14px; }
.grid { display: grid; grid-template-columns: minmax(0, 1fr) 360px; gap: 20px; align-items: start; }
.side { display: grid; gap: 14px; }
.grade h3 { margin: 0 0 6px; }
.text .pre, .grade .pre { white-space: pre-wrap; margin: 0; line-height: 1.65; font-size: 15px; }
@media (max-width: 900px) { .grid { grid-template-columns: 1fr; } }
</style>
