<script setup>
import { onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { api } from '../../lib/api.js'
import { dueLabel } from '../../lib/format.js'
import StatusChip from '../../components/StatusChip.vue'

const route = useRoute()
const router = useRouter()
const a = ref(null)
const error = ref('')
const busy = ref(false)

onMounted(async () => {
  try { a.value = await api.get(`/api/assignments/${route.params.assignmentId}`) } catch (e) { error.value = e.message }
})

async function start() {
  busy.value = true
  try {
    const sub = await api.post('/api/submissions/start', { assignment_id: a.value.assignment_id })
    router.push(sub.status === 'draft' ? `/write/${sub.submission_id}` : `/student/submissions/${sub.submission_id}`)
  } catch (e) {
    error.value = e.message
  } finally {
    busy.value = false
  }
}
</script>

<template>
  <p v-if="error" class="error">{{ error }}</p>
  <template v-if="a">
    <p class="muted crumbs"><RouterLink to="/student">My classes</RouterLink> / <RouterLink :to="`/student/classes/${a.class_id}`">{{ a.class_name }}</RouterLink></p>
    <div class="head">
      <div>
        <h1>{{ a.title }}</h1>
        <p class="muted">{{ dueLabel(a.due_ms) }} · {{ a.points }} points</p>
      </div>
      <StatusChip :status="a.my_submission?.status || 'not_started'" />
    </div>

    <div class="card body">
      <h2>Instructions</h2>
      <p class="pre">{{ a.instructions || 'No instructions were given.' }}</p>
    </div>

    <div class="card notice">
      <b>How your work is verified.</b> Your writing session is recorded as a hash-chained ledger in your own browser:
      every edit, paste and pause. When you submit, a certificate binds that ledger to your exact text. Your teacher
      sees where text came from and how it was written — not a verdict.
      <span v-if="!a.settings.allow_paste" class="warn"> Pasting from outside this document is disabled for this assignment.</span>
    </div>

    <div class="actions">
      <template v-if="!a.my_submission || a.my_submission.status === 'draft'">
        <button class="primary" :disabled="busy" @click="start">{{ a.my_submission ? 'Continue writing' : 'Start writing' }}</button>
      </template>
      <RouterLink v-else class="btn" :to="`/student/submissions/${a.my_submission.submission_id}`">View my submission</RouterLink>
    </div>
  </template>
</template>

<style scoped>
.crumbs { font-size: 13px; margin: 0 0 8px; }
.head { display: flex; justify-content: space-between; align-items: flex-start; gap: 12px; }
.body { margin: 16px 0; } .body h2 { font-size: 14px; color: var(--muted); text-transform: uppercase; letter-spacing: 0.04em; }
.pre { white-space: pre-wrap; margin: 0; line-height: 1.6; }
.notice { font-size: 14px; line-height: 1.55; color: var(--muted); border-left: 3px solid var(--accent); }
.notice b { color: var(--text); }
.actions { margin-top: 18px; }
.btn { display: inline-block; padding: 8px 14px; border-radius: 6px; border: 1px solid var(--border); background: var(--surface-2); color: var(--text); text-decoration: none; }
</style>
