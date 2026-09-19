<script setup>
import { onMounted, ref } from 'vue'
import { api } from '../../lib/api.js'
import { fmtDate } from '../../lib/format.js'
import { useAuth } from '../../composables/useAuth.js'
import StatusChip from '../../components/StatusChip.vue'

const auth = useAuth()
const data = ref(null)
const error = ref('')
const newName = ref('')
const creating = ref(false)

async function load() {
  try { data.value = await api.get('/api/dashboard') } catch (e) { error.value = e.message }
}
async function createClass() {
  creating.value = true
  try {
    await api.post('/api/classes', { name: newName.value })
    newName.value = ''
    await load()
  } catch (e) {
    error.value = e.message
  } finally {
    creating.value = false
  }
}
onMounted(load)
</script>

<template>
  <div class="head">
    <h1>Welcome, {{ auth.state.user?.name }}</h1>
    <form class="create" @submit.prevent="createClass">
      <input v-model="newName" placeholder="New class name" required style="width: 200px" />
      <button class="primary" :disabled="creating">Create class</button>
    </form>
  </div>
  <p v-if="error" class="error">{{ error }}</p>

  <template v-if="data">
    <div class="tiles">
      <div class="tile"><b>{{ data.tiles.classes }}</b><span>Classes</span></div>
      <div class="tile"><b>{{ data.tiles.students }}</b><span>Students</span></div>
      <div class="tile"><b>{{ data.tiles.assignments }}</b><span>Assignments</span></div>
      <div class="tile" :class="{ hot: data.tiles.to_grade }"><b>{{ data.tiles.to_grade }}</b><span>To grade</span></div>
    </div>

    <section>
      <h2>My classes</h2>
      <p v-if="!data.classes.length" class="muted">Create your first class above; students join with the code it gets.</p>
      <div class="grid">
        <RouterLink v-for="c in data.classes" :key="c.class_id" :to="`/teacher/classes/${c.class_id}`" class="card link">
          <h3>{{ c.name }}</h3>
          <p class="muted">{{ c.student_count }} student{{ c.student_count === 1 ? '' : 's' }} · {{ c.assignment_count }} assignment{{ c.assignment_count === 1 ? '' : 's' }}</p>
          <p class="mono code">code {{ c.class_code }}</p>
        </RouterLink>
      </div>
    </section>

    <section v-if="data.recent.length">
      <h2>Recent submissions</h2>
      <ul class="list">
        <li v-for="s in data.recent" :key="s.submission_id">
          <RouterLink :to="`/teacher/submissions/${s.submission_id}`"><b>{{ s.student_name }}</b> · {{ s.title }}</RouterLink>
          <span class="muted">{{ s.class_name }} · {{ fmtDate(s.submitted_ms) }}</span>
          <StatusChip :status="s.status" />
        </li>
      </ul>
    </section>
  </template>
</template>

<style scoped>
.head { display: flex; align-items: center; justify-content: space-between; gap: 16px; flex-wrap: wrap; }
.create { display: flex; gap: 8px; }
.tiles { display: grid; grid-template-columns: repeat(4, 1fr); gap: 12px; margin: 14px 0 8px; }
.tile { background: var(--surface); border: 1px solid var(--border); border-radius: 10px; padding: 14px 16px; display: grid; }
.tile b { font-size: 26px; } .tile span { color: var(--muted); font-size: 13px; }
.tile.hot b { color: var(--warn); }
section { margin: 22px 0; }
.grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(240px, 1fr)); gap: 12px; }
.card.link { text-decoration: none; color: var(--text); display: block; }
.card.link:hover { border-color: var(--accent); }
.card h3 { margin: 0 0 6px; font-size: 16px; } .card p { margin: 0; font-size: 13px; }
.code { margin-top: 8px !important; color: var(--accent); }
.list { list-style: none; padding: 0; margin: 0; display: grid; gap: 8px; }
.list li { display: grid; grid-template-columns: 1fr auto auto; gap: 12px; align-items: center; background: var(--surface); border: 1px solid var(--border); border-radius: 8px; padding: 10px 14px; font-size: 14px; }
@media (max-width: 700px) { .tiles { grid-template-columns: 1fr 1fr; } }
</style>
