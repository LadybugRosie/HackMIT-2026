<script setup>
import { onMounted, ref } from 'vue'
import { useRoute } from 'vue-router'
import { api } from '../../lib/api.js'
import { dueLabel } from '../../lib/format.js'
import StatusChip from '../../components/StatusChip.vue'

const route = useRoute()
const data = ref(null)
const error = ref('')
onMounted(async () => {
  try { data.value = await api.get(`/api/classes/${route.params.classId}`) } catch (e) { error.value = e.message }
})
</script>

<template>
  <p class="muted crumbs"><RouterLink to="/student">My classes</RouterLink> / {{ data?.class.name }}</p>
  <p v-if="error" class="error">{{ error }}</p>
  <template v-if="data">
    <h1>{{ data.class.name }}</h1>
    <p class="muted">Taught by {{ data.class.teacher_name }}</p>
    <h2>Assignments</h2>
    <p v-if="!data.assignments.length" class="muted">Nothing posted yet.</p>
    <ul class="list">
      <li v-for="a in data.assignments" :key="a.assignment_id">
        <div>
          <RouterLink :to="`/student/assignments/${a.assignment_id}`"><b>{{ a.title }}</b></RouterLink>
          <div class="muted small">{{ dueLabel(a.due_ms) }} · {{ a.points }} pts</div>
        </div>
        <span v-if="a.my_submission?.grade != null" class="good">{{ a.my_submission.grade }} / {{ a.points }}</span>
        <StatusChip :status="a.my_submission?.status || 'not_started'" />
      </li>
    </ul>
  </template>
</template>

<style scoped>
.crumbs { font-size: 13px; margin: 0 0 8px; }
.small { font-size: 13px; }
.list { list-style: none; padding: 0; margin: 0; display: grid; gap: 8px; }
.list li { display: grid; grid-template-columns: 1fr auto auto; gap: 12px; align-items: center; background: var(--surface); border: 1px solid var(--border); border-radius: 8px; padding: 12px 14px; font-size: 14px; }
</style>
