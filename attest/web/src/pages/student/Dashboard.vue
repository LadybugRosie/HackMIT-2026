<script setup>
import { onMounted, ref } from 'vue'
import { api } from '../../lib/api.js'
import { dueLabel } from '../../lib/format.js'
import { useAuth } from '../../composables/useAuth.js'
import StatusChip from '../../components/StatusChip.vue'

const auth = useAuth()
const data = ref(null)
const error = ref('')
const code = ref('')
const joinMsg = ref('')
const joining = ref(false)

async function load() {
  try { data.value = await api.get('/api/dashboard') } catch (e) { error.value = e.message }
}
async function join() {
  joining.value = true
  joinMsg.value = ''
  try {
    const c = await api.post('/api/classes/join', { class_code: code.value })
    joinMsg.value = `Joined ${c.name}.`
    code.value = ''
    await load()
  } catch (e) {
    joinMsg.value = e.status === 404 ? 'That class code was not found.' : e.message
  } finally {
    joining.value = false
  }
}
onMounted(load)
</script>

<template>
  <div class="head">
    <h1>Hi, {{ auth.state.user?.name }}</h1>
    <form class="join" @submit.prevent="join">
      <input v-model="code" placeholder="Class code" maxlength="8" style="text-transform: uppercase; width: 130px" required />
      <button class="primary" :disabled="joining">Join class</button>
      <span class="muted small">{{ joinMsg }}</span>
    </form>
  </div>
  <p v-if="error" class="error">{{ error }}</p>

  <template v-if="data">
    <section>
      <h2>My classes</h2>
      <p v-if="!data.classes.length" class="muted">You haven't joined a class yet — enter the code your teacher gave you above.</p>
      <div class="grid">
        <RouterLink v-for="c in data.classes" :key="c.class_id" :to="`/student/classes/${c.class_id}`" class="card link">
          <h3>{{ c.name }}</h3>
          <p class="muted">{{ c.teacher_name }} · {{ c.assignment_count }} assignment{{ c.assignment_count === 1 ? '' : 's' }}</p>
        </RouterLink>
      </div>
    </section>

    <section v-if="data.due_soon.length">
      <h2>Up next</h2>
      <ul class="list">
        <li v-for="a in data.due_soon" :key="a.assignment_id">
          <RouterLink :to="`/student/assignments/${a.assignment_id}`">{{ a.title }}</RouterLink>
          <span class="muted">{{ a.class_name }} · {{ dueLabel(a.due_ms) }}</span>
          <StatusChip :status="a.status" />
        </li>
      </ul>
    </section>
  </template>
</template>

<style scoped>
.head { display: flex; align-items: center; justify-content: space-between; gap: 16px; flex-wrap: wrap; margin-bottom: 8px; }
.join { display: flex; gap: 8px; align-items: center; }
.small { font-size: 13px; }
section { margin: 22px 0; }
.grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(240px, 1fr)); gap: 12px; }
.card.link { text-decoration: none; color: var(--text); display: block; }
.card.link:hover { border-color: var(--accent); }
.card h3 { margin: 0 0 6px; font-size: 16px; } .card p { margin: 0; font-size: 13px; }
.list { list-style: none; padding: 0; margin: 0; display: grid; gap: 8px; }
.list li { display: grid; grid-template-columns: 1fr auto auto; gap: 12px; align-items: center; background: var(--surface); border: 1px solid var(--border); border-radius: 8px; padding: 10px 14px; font-size: 14px; }
</style>
