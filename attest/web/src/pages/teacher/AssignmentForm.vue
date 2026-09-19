<script setup>
import { computed, onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { api } from '../../lib/api.js'
import { localInputToMs, msToLocalInput } from '../../lib/format.js'

const route = useRoute()
const router = useRouter()
const isEdit = computed(() => !!route.params.assignmentId)
const form = ref({
  title: '', instructions: '', due: '', points: 100, published: true,
  settings: { factcheck: true, similarity: true, allow_paste: true, min_trust: 0 },
})
const error = ref('')
const busy = ref(false)
let classId = route.params.classId

onMounted(async () => {
  if (!isEdit.value) return
  try {
    const a = await api.get(`/api/assignments/${route.params.assignmentId}`)
    classId = a.class_id
    form.value = { title: a.title, instructions: a.instructions, due: msToLocalInput(a.due_ms), points: a.points,
                   published: a.published, settings: { ...a.settings } }
  } catch (e) { error.value = e.message }
})

async function save() {
  busy.value = true
  error.value = ''
  const body = { title: form.value.title, instructions: form.value.instructions, due_ms: localInputToMs(form.value.due),
                 points: Number(form.value.points), published: form.value.published, settings: form.value.settings }
  try {
    const a = isEdit.value
      ? await api.put(`/api/assignments/${route.params.assignmentId}`, body)
      : await api.post('/api/assignments', { class_id: classId, ...body })
    router.push(`/teacher/assignments/${a.assignment_id}`)
  } catch (e) {
    error.value = Array.isArray(e.detail) ? e.detail.map((d) => d.msg).join(' ') : e.message
  } finally {
    busy.value = false
  }
}
</script>

<template>
  <form class="form" @submit.prevent="save">
    <h1>{{ isEdit ? 'Edit assignment' : 'New assignment' }}</h1>
    <label>Title <input v-model="form.title" required maxlength="200" /></label>
    <label>Instructions <textarea v-model="form.instructions" rows="6" placeholder="What should students write?"></textarea></label>
    <div class="row">
      <label>Due <input v-model="form.due" type="datetime-local" /></label>
      <label>Points <input v-model="form.points" type="number" min="0" max="10000" /></label>
    </div>

    <fieldset>
      <legend>Integrity checks</legend>
      <label class="check"><input v-model="form.settings.factcheck" type="checkbox" /> Verify citations and links (Crossref / web) after submission</label>
      <label class="check"><input v-model="form.settings.similarity" type="checkbox" /> Compare against other submissions in this class</label>
      <label class="check"><input v-model="form.settings.allow_paste" type="checkbox" /> Allow pasting from outside the document (recorded as external text either way)</label>
    </fieldset>

    <label class="check"><input v-model="form.published" type="checkbox" /> Published — visible to students</label>

    <p v-if="error" class="error">{{ error }}</p>
    <div class="actions">
      <button class="primary" :disabled="busy">{{ busy ? 'Saving…' : isEdit ? 'Save changes' : 'Create assignment' }}</button>
      <button type="button" @click="router.back()">Cancel</button>
    </div>
  </form>
</template>

<style scoped>
.form { max-width: 680px; display: grid; gap: 14px; }
.row { display: grid; grid-template-columns: 1fr 1fr; gap: 14px; }
fieldset { border: 1px solid var(--border); border-radius: 8px; padding: 10px 14px 14px; display: grid; gap: 8px; }
legend { color: var(--muted); font-size: 13px; padding: 0 6px; }
.check { display: flex; align-items: center; gap: 8px; color: var(--text); font-size: 14px; }
.check input { width: auto; }
.actions { display: flex; gap: 8px; }
</style>
