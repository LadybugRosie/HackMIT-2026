<template>
  <div class="session-playback-page">
    <!-- Header -->
    <header class="page-header">
      <div class="header-left">
        <button @click="goBack" class="back-btn">
          <svg width="24" height="24" viewBox="0 0 24 24" fill="currentColor">
            <path d="M20 11H7.83l5.59-5.59L12 4l-8 8 8 8 1.41-1.41L7.83 13H20v-2z"/>
          </svg>
        </button>
        <div class="header-info">
          <h1>Session Playback</h1>
          <span class="subtitle">{{ studentName }} — {{ assignmentTitle }}</span>
        </div>
      </div>
      <div class="header-actions">
        <span class="info-badge">{{ rawSnapshots.length }} snapshots</span>
        <span class="info-badge">{{ formatDuration(totalDurationMs) }}</span>
      </div>
    </header>

    <!-- Loading / Error -->
    <div v-if="loading" class="state-message">Loading playback data...</div>
    <div v-else-if="error" class="state-message error">{{ error }}</div>

    <!-- Viewer (handles the empty state itself) -->
    <PlaybackViewer v-else :snapshots="rawSnapshots" :events="playbackEvents" :authors="playbackAuthors" :meta="viewerMeta" />
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import axios from 'axios'
import { getApiUrl } from '@/utils/api-url'
import { formatDuration } from '@/composables/playback-engine'
import PlaybackViewer from '@/components/playback/PlaybackViewer.vue'

const route = useRoute()
const router = useRouter()
const API = getApiUrl()
const submissionId = route.params.id

const loading = ref(true)
const error = ref(null)
const rawSnapshots = ref([])
const playbackEvents = ref([])
const playbackAuthors = ref({})
const totalDurationMs = ref(0)
const studentName = ref('')
const assignmentTitle = ref('')

const viewerMeta = computed(() => ({
  studentName: studentName.value,
  title: assignmentTitle.value,
  totalDurationMs: totalDurationMs.value,
}))

onMounted(async () => {
  // Snapshots (legacy fallback) and the exact event stream load in parallel;
  // the viewer prefers events when present.
  const [snapResp, evResp] = await Promise.allSettled([
    axios.get(`${API}/api/session-playback/${submissionId}`),
    axios.get(`${API}/api/session-playback/${submissionId}/events`),
  ])

  if (snapResp.status === 'fulfilled') {
    rawSnapshots.value = snapResp.value.data.snapshots || []
    totalDurationMs.value = snapResp.value.data.total_duration_ms || snapResp.value.data.totalDurationMs || 0
  }
  if (evResp.status === 'fulfilled' && evResp.value.data?.found) {
    playbackEvents.value = evResp.value.data.events || []
    playbackAuthors.value = evResp.value.data.authors || {}
  }
  if (snapResp.status === 'rejected' && playbackEvents.value.length === 0) {
    error.value = snapResp.reason?.response?.status === 404 ? 'No playback data found.' : 'Failed to load.'
  }

  try {
    const sub = await axios.get(`${API}/api/submissions/${submissionId}`)
    studentName.value = sub.data?.student_name || 'Student'
    assignmentTitle.value = sub.data?.assignment_title || 'Assignment'
  } catch {}

  loading.value = false
})

function goBack() { router.back() }
</script>

<style scoped>
.session-playback-page {
  max-width: 1200px; margin: 0 auto; padding: 24px;
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
  color: #1a1a1a; background: #f5f5f5; min-height: 100vh;
}

/* Header */
.page-header { display: flex; align-items: center; justify-content: space-between; margin-bottom: 20px; }
.header-left { display: flex; align-items: center; gap: 12px; }
.back-btn { background: none; border: none; cursor: pointer; padding: 8px; border-radius: 8px; color: #6b7280; }
.back-btn:hover { background: #e5e7eb; }
.header-info h1 { margin: 0; font-size: 20px; font-weight: 600; }
.subtitle { color: #6b7280; font-size: 14px; }
.header-actions { display: flex; gap: 8px; }
.info-badge { background: #fff; padding: 5px 12px; border-radius: 16px; font-size: 13px; color: #374151; border: 1px solid #e5e7eb; }
.state-message { text-align: center; padding: 80px 20px; color: #6b7280; }
.state-message.error { color: #dc2626; }
</style>
