<script setup>
import { onMounted, ref } from 'vue'
import { useRoute } from 'vue-router'
import { api } from '../../lib/api.js'
import { dueLabel, fmtDate } from '../../lib/format.js'

const route = useRoute()
const data = ref(null)
const error = ref('')
const copied = ref(false)

async function load() {
  try { data.value = await api.get(`/api/classes/${route.params.classId}`) } catch (e) { error.value = e.message }
}
async function copyCode() {
  try { await navigator.clipboard.writeText(data.value.class.class_code); copied.value = true; setTimeout(() => (copied.value = false), 1500) } catch {}
}
async function regenerate() {
  if (!confirm('Generate a new class code? The old code stops working immediately.')) return
  const r = await api.post(`/api/classes/${route.params.classId}/regenerate-code`)
  data.value.class.class_code = r.class_code
}
onMounted(load)
</script>

<template>
  <p class="muted crumbs"><RouterLink to="/teacher">Dashboard</RouterLink> / {{ data?.class.name }}</p>
  <p v-if="error" class="error">{{ error }}</p>
  <template v-if="data">
    <div class="head">
      <h1>{{ data.class.name }}</h1>
      <div class="codebox">
        <span class="muted">Class code</span>
        <b class="mono">{{ data.class.class_code }}</b>
        <button @click="copyCode">{{ copied ? 'Copied' : 'Copy' }}</button>
        <button @click="regenerate" title="Invalidate the current code">↻</button>
      </div>
    </div>

    <div class="cols">
      <section>
        <div class="sec-head">
          <h2>Assignments</h2>
          <RouterLink class="btn primary" :to="`/teacher/classes/${data.class.class_id}/assignments/new`">New assignment</RouterLink>
        </div>
        <p v-if="!data.assignments.length" class="muted">No assignments yet.</p>
        <ul class="list">
          <li v-for="a in data.assignments" :key="a.assignment_id">
            <div>
              <RouterLink :to="`/teacher/assignments/${a.assignment_id}`"><b>{{ a.title }}</b></RouterLink>
              <span v-if="!a.published" class="pill warn">Draft</span>
              <div class="muted small">{{ dueLabel(a.due_ms) }} · {{ a.points }} pts</div>
            </div>
            <div class="counts muted small">
              {{ a.submission_counts.submitted + a.submission_counts.graded + a.submission_counts.returned }} / {{ data.roster.length }} submitted
              <span v-if="a.submission_counts.submitted" class="warn"> · {{ a.submission_counts.submitted }} to grade</span>
            </div>
          </li>
        </ul>
      </section>

      <section>
        <h2>Students <span class="muted">({{ data.roster.length }})</span></h2>
        <p v-if="!data.roster.length" class="muted">Share the class code — students appear here when they join.</p>
        <ul class="roster">
          <li v-for="s in data.roster" :key="s.user_id">
            <b>{{ s.name }}</b><span class="muted small">{{ s.email }}</span><span class="muted small">joined {{ fmtDate(s.joined_ms) }}</span>
          </li>
        </ul>
      </section>
    </div>
  </template>
</template>

<style scoped>
.crumbs { font-size: 13px; margin: 0 0 8px; }
.head { display: flex; justify-content: space-between; align-items: center; gap: 12px; flex-wrap: wrap; }
.codebox { display: flex; align-items: center; gap: 10px; background: var(--surface); border: 1px solid var(--border); border-radius: 8px; padding: 6px 12px; font-size: 14px; }
.codebox b { font-size: 18px; letter-spacing: 0.08em; color: var(--accent); }
.cols { display: grid; grid-template-columns: 2fr 1fr; gap: 24px; margin-top: 18px; }
.sec-head { display: flex; justify-content: space-between; align-items: center; }
.btn { text-decoration: none; padding: 7px 12px; border-radius: 6px; border: 1px solid var(--border); font-size: 14px; }
.btn.primary { background: var(--accent); border-color: var(--accent); color: #fff; font-weight: 600; }
.small { font-size: 13px; }
.list, .roster { list-style: none; padding: 0; margin: 0; display: grid; gap: 8px; }
.list li { display: flex; justify-content: space-between; gap: 12px; align-items: center; background: var(--surface); border: 1px solid var(--border); border-radius: 8px; padding: 12px 14px; font-size: 14px; }
.list .pill { margin-left: 8px; }
.roster li { display: grid; gap: 2px; background: var(--surface); border: 1px solid var(--border); border-radius: 8px; padding: 10px 12px; font-size: 14px; }
@media (max-width: 800px) { .cols { grid-template-columns: 1fr; } }
</style>
