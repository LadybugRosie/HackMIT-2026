<script setup>
import { onMounted, ref } from 'vue'
import { useRoute } from 'vue-router'
import { api } from '../../lib/api.js'
import { dueLabel, fmtDate } from '../../lib/format.js'
import StatusChip from '../../components/StatusChip.vue'
import TrustChip from '../../components/TrustChip.vue'

const route = useRoute()
const a = ref(null)
const rows = ref([])
const error = ref('')

async function load() {
  try {
    ;[a.value, rows.value] = await Promise.all([
      api.get(`/api/assignments/${route.params.assignmentId}`),
      api.get(`/api/assignments/${route.params.assignmentId}/submissions`),
    ])
  } catch (e) { error.value = e.message }
}
async function togglePublished() {
  a.value = await api.put(`/api/assignments/${a.value.assignment_id}`, { published: !a.value.published })
}
function citations(r) {
  if (!r.factcheck_summary) return r.factcheck_status === 'pending' ? 'checking…' : '—'
  const s = r.factcheck_summary
  const issues = (s.not_found || 0) + (s.invalid || 0)
  return issues ? `${issues} issue${issues === 1 ? '' : 's'} / ${s.total}` : `${s.valid}/${s.total} ok`
}
onMounted(load)
</script>

<template>
  <p v-if="error" class="error">{{ error }}</p>
  <template v-if="a">
    <p class="muted crumbs"><RouterLink to="/teacher">Dashboard</RouterLink> / <RouterLink :to="`/teacher/classes/${a.class_id}`">{{ a.class_name }}</RouterLink></p>
    <div class="head">
      <div>
        <h1>{{ a.title }} <span v-if="!a.published" class="pill warn">Draft</span></h1>
        <p class="muted">{{ dueLabel(a.due_ms) }} · {{ a.points }} points ·
          checks: <span :class="a.settings.factcheck ? '' : 'strike'">citations</span>, <span :class="a.settings.similarity ? '' : 'strike'">similarity</span></p>
      </div>
      <div class="actions">
        <button @click="togglePublished">{{ a.published ? 'Unpublish' : 'Publish' }}</button>
        <RouterLink class="btn" :to="`/teacher/assignments/${a.assignment_id}/edit`">Edit</RouterLink>
      </div>
    </div>

    <details class="card instr"><summary>Instructions</summary><p class="pre">{{ a.instructions || '—' }}</p></details>

    <h2>Submissions <span class="muted">({{ a.submission_counts.submitted + a.submission_counts.graded + a.submission_counts.returned }} of {{ rows.length }})</span></h2>
    <table class="tbl">
      <thead><tr><th>Student</th><th>Status</th><th>Submitted</th><th title="Trust score and assurance level">Trust</th><th>External</th><th>Similarity</th><th>Citations</th><th>Grade</th></tr></thead>
      <tbody>
        <tr v-for="r in rows" :key="r.student.user_id" :class="{ clickable: r.submission_id && r.status !== 'draft' }">
          <td>
            <RouterLink v-if="r.submission_id && r.status !== 'draft'" :to="`/teacher/submissions/${r.submission_id}`"><b>{{ r.student.name }}</b></RouterLink>
            <b v-else>{{ r.student.name }}</b>
            <div class="muted small">{{ r.student.email }}</div>
          </td>
          <td><StatusChip :status="r.status" /></td>
          <td class="muted">{{ fmtDate(r.submitted_ms) }}</td>
          <td><TrustChip :trust="r.trust" :verdict="r.verdict" :level="r.assurance_level" /></td>
          <td :class="{ bad: r.external_pct > 30 }">{{ r.external_pct == null ? '—' : r.external_pct + '%' }}</td>
          <td :class="{ bad: r.similarity_max >= 40 }">{{ r.similarity_max == null ? (r.similarity_status === 'pending' ? '…' : '—') : r.similarity_max + '%' }}</td>
          <td>{{ citations(r) }}</td>
          <td>{{ r.grade == null ? '—' : `${r.grade} / ${a.points}` }}</td>
        </tr>
      </tbody>
    </table>
    <p v-if="!rows.length" class="muted">No students have joined this class yet.</p>
  </template>
</template>

<style scoped>
.crumbs { font-size: 13px; margin: 0 0 8px; }
.head { display: flex; justify-content: space-between; align-items: flex-start; gap: 12px; flex-wrap: wrap; }
.head h1 .pill { font-size: 11px; vertical-align: middle; margin-left: 6px; }
.actions { display: flex; gap: 8px; }
.btn { text-decoration: none; padding: 8px 14px; border-radius: 6px; border: 1px solid var(--border); background: var(--surface-2); color: var(--text); font-size: 14px; }
.strike { text-decoration: line-through; }
.instr { margin: 14px 0 20px; } .instr summary { cursor: pointer; color: var(--muted); }
.pre { white-space: pre-wrap; margin: 10px 0 0; line-height: 1.55; }
.tbl { width: 100%; border-collapse: collapse; background: var(--surface); border: 1px solid var(--border); border-radius: 8px; overflow: hidden; font-size: 14px; }
.tbl th { text-align: left; font-size: 12px; color: var(--muted); font-weight: 600; padding: 10px 12px; border-bottom: 1px solid var(--border); }
.tbl td { padding: 10px 12px; border-bottom: 1px solid var(--border); vertical-align: middle; }
.tbl tr:last-child td { border-bottom: none; }
.small { font-size: 12px; }
</style>
