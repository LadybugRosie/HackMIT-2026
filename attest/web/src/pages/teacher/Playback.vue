<script setup>
import { onMounted, ref } from 'vue'
import { useRoute } from 'vue-router'
import { api } from '../../lib/api.js'
import PlaybackViewer from '../../components/PlaybackViewer.vue'

const route = useRoute()
const sub = ref(null)
const payload = ref(null)
const error = ref('')
onMounted(async () => {
  try {
    ;[sub.value, payload.value] = await Promise.all([
      api.get(`/api/submissions/${route.params.submissionId}`),
      api.get(`/api/review/submissions/${route.params.submissionId}/playback`),
    ])
  } catch (e) { error.value = e.message }
})
</script>

<template>
  <p v-if="error" class="error">{{ error }}</p>
  <template v-if="sub && payload">
    <p class="muted crumbs"><RouterLink :to="`/teacher/submissions/${sub.submission_id}`">← Back to review</RouterLink></p>
    <h1>{{ sub.student_name }} <span class="muted">· {{ sub.assignment.title }} · session replay</span></h1>
    <PlaybackViewer :payload="payload" />
  </template>
</template>

<style scoped>
.crumbs { font-size: 13px; margin: 0 0 6px; }
h1 .muted { font-weight: 400; }
</style>
