<template>
  <div class="lab-view-page">
    <!-- Header -->
    <header class="page-header">
      <div class="header-content">
        <button @click="router.push('/researcher')" class="back-btn">
          <svg width="24" height="24" viewBox="0 0 24 24" fill="white">
            <path d="M20 11H7.83l5.59-5.59L12 4l-8 8 8 8 1.41-1.41L7.83 13H20v-2z"/>
          </svg>
        </button>
        <div class="lab-info">
          <h1>{{ lab?.name || 'Lab' }}</h1>
          <p v-if="lab?.description">{{ lab.description }}</p>
        </div>
        <div class="header-badges">
          <span v-if="isPi" class="pi-badge">PI</span>
          <div class="lab-code-badge" v-if="lab?.lab_code">
            <span>Lab Code:</span>
            <code>{{ lab.lab_code }}</code>
            <button @click="copyCode" class="copy-btn" title="Copy lab code">
              <svg width="16" height="16" viewBox="0 0 24 24" fill="white">
                <path d="M16 1H4c-1.1 0-2 .9-2 2v14h2V3h12V1zm3 4H8c-1.1 0-2 .9-2 2v14c0 1.1.9 2 2 2h11c1.1 0 2-.9 2-2V7c0-1.1-.9-2-2-2zm0 16H8V7h11v14z"/>
              </svg>
            </button>
            <span v-if="copied" class="copied-text">Copied!</span>
          </div>
          <span class="member-count-badge">{{ members.length }} member{{ members.length === 1 ? '' : 's' }}</span>
        </div>
      </div>
    </header>

    <main class="page-content">
      <div v-if="loading" class="loading">
        <div class="spinner"></div>
        <span>Loading lab members...</span>
      </div>

      <div v-else-if="loadError" class="error-card">
        <p>{{ loadError }}</p>
        <button class="btn-primary" @click="loadMembers">Retry</button>
      </div>

      <div v-else>
        <h2>Members</h2>
        <div v-if="members.length === 0" class="empty-state">
          <svg width="64" height="64" viewBox="0 0 24 24" fill="#dadce0">
            <path d="M16 11c1.66 0 2.99-1.34 2.99-3S17.66 5 16 5c-1.66 0-3 1.34-3 3s1.34 3 3 3zm-8 0c1.66 0 2.99-1.34 2.99-3S9.66 5 8 5C6.34 5 5 6.34 5 8s1.34 3 3 3z"/>
          </svg>
          <h3>No members yet</h3>
          <p>Share the lab code <code>{{ lab?.lab_code }}</code> with your group</p>
        </div>

        <div v-else class="members-list">
          <div v-for="member in members" :key="member.user_id" class="member-card">
            <div class="member-row">
              <div class="member-avatar">
                {{ member.name?.[0]?.toUpperCase() || 'R' }}
              </div>
              <div class="member-info">
                <span class="member-name">{{ member.name }}</span>
                <span class="member-email">{{ member.email }}</span>
              </div>
              <span class="member-joined">Joined {{ formatDate(member.joined_at) }}</span>
              <span class="enroll-badge" :class="{ enrolled: member.stylometry_enrolled }">
                {{ member.stylometry_enrolled ? 'Stylometry Enrolled' : 'Not Enrolled' }}
              </span>
            </div>

            <!-- Member submissions -->
            <div v-if="member.submissions?.length > 0" class="submissions-list">
              <div
                v-for="sub in member.submissions"
                :key="sub.submission_id"
                class="submission-row"
              >
                <div class="submission-title">
                  <span class="topic-title">{{ sub.topic_title }}</span>
                  <span class="submission-meta">{{ sub.word_count || 0 }} words<template v-if="sub.submitted_at"> • {{ formatDate(sub.submitted_at) }}</template></span>
                </div>
                <div class="submission-chips">
                  <span class="status-badge" :class="sub.status">{{ statusLabel(sub.status) }}</span>
                  <span v-if="sub.is_shared" class="chip shared-chip">👥 {{ sub.report_authors.length }} authors</span>
                  <template v-if="sub.is_shared">
                    <span
                      v-for="a in sub.report_authors"
                      :key="a.name"
                      class="chip verdict-chip"
                      :class="a.verdict || 'gray'"
                      :title="(a.final_pct != null ? a.final_pct + '% · ' : '') + a.name"
                    >{{ a.name?.split(' ')[0] }}: {{ a.verdict || 'pending' }}</span>
                  </template>
                  <span v-else-if="sub.stylometry_verdict" class="chip verdict-chip" :class="sub.stylometry_verdict">
                    {{ styloLabel(sub.stylometry_verdict, sub.stylometry_probability) }}
                  </span>
                  <span v-if="!sub.is_shared && sub.trust_score != null" class="chip">Trust {{ sub.trust_score }}%</span>
                  <span v-if="!sub.is_shared && sub.ai_probability != null" class="chip">AI {{ Math.round(sub.ai_probability * 100) }}%</span>
                </div>
                <router-link
                  v-if="sub.status !== 'draft'"
                  :to="`/researcher/submission/${sub.submission_id}`"
                  class="report-link"
                >
                  Report
                </router-link>
                <span v-else class="draft-note">In progress</span>
              </div>
            </div>
            <p v-else class="no-submissions">No submissions yet</p>
          </div>
        </div>
      </div>
    </main>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import axios from 'axios'
import { getApiUrl } from '@/utils/api-url'

const props = defineProps(['id'])
const router = useRouter()
const route = useRoute()

const API = getApiUrl()
const labId = computed(() => props.id || route.params.id)

const loading = ref(false)
const loadError = ref('')
const lab = ref(null)
const isPi = ref(false)
const members = ref([])
const copied = ref(false)

function formatDate(dateStr) {
  if (!dateStr) return ''
  return new Date(dateStr).toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' })
}

function statusLabel(status) {
  if (status === 'draft') return 'Draft'
  if (status === 'submitted') return 'Submitted'
  if (status === 'graded') return 'Reviewed'
  return status
}

function styloLabel(verdict, probability) {
  const names = {
    verified: 'verified',
    flagged: 'flagged',
    review_required: 'review required',
    insufficient_data: 'insufficient data'
  }
  let label = `Stylometry: ${names[verdict] || verdict || '—'}`
  if (probability != null) label += ` · ${Math.round(probability * 100)}%`
  return label
}

function copyCode() {
  navigator.clipboard.writeText(lab.value?.lab_code || '')
  copied.value = true
  setTimeout(() => { copied.value = false }, 2000)
}

async function loadMembers() {
  loading.value = true
  loadError.value = ''
  try {
    const resp = await axios.get(`${API}/api/research/labs/${labId.value}/members`)
    lab.value = resp.data.lab
    isPi.value = !!resp.data.is_pi
    members.value = resp.data.members || []
  } catch (e) {
    loadError.value = e.response?.data?.detail || 'Failed to load lab members'
  } finally {
    loading.value = false
  }
}

onMounted(() => {
  loadMembers()
})
</script>

<style scoped>
.lab-view-page {
  min-height: 100vh;
  background: #f8f9fa;
}

.page-header {
  padding: 20px 24px;
  background: #7c3aed;
  color: white;
}

.header-content {
  max-width: 1100px;
  margin: 0 auto;
  display: flex;
  align-items: center;
  gap: 20px;
  flex-wrap: wrap;
}

.back-btn {
  width: 40px;
  height: 40px;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: 50%;
  border: none;
  background: transparent;
  cursor: pointer;
}

.back-btn:hover {
  background: rgba(255,255,255,0.15);
}

.lab-info {
  flex: 1;
  min-width: 200px;
}

.lab-info h1 {
  font-size: 24px;
  font-weight: 500;
  margin: 0;
}

.lab-info p {
  font-size: 14px;
  opacity: 0.9;
  margin: 4px 0 0;
}

.header-badges {
  display: flex;
  align-items: center;
  gap: 12px;
  flex-wrap: wrap;
}

.pi-badge {
  background: white;
  color: #7c3aed;
  font-size: 12px;
  font-weight: 700;
  padding: 4px 12px;
  border-radius: 12px;
}

.lab-code-badge {
  display: flex;
  align-items: center;
  gap: 8px;
  background: rgba(255,255,255,0.2);
  padding: 8px 16px;
  border-radius: 20px;
  font-size: 14px;
}

.lab-code-badge code {
  font-weight: 600;
}

.copy-btn {
  width: 28px;
  height: 28px;
  border: none;
  background: transparent;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: 50%;
}

.copy-btn:hover {
  background: rgba(255,255,255,0.2);
}

.copied-text {
  font-size: 12px;
  font-weight: 600;
}

.member-count-badge {
  background: rgba(255,255,255,0.2);
  padding: 8px 16px;
  border-radius: 20px;
  font-size: 14px;
}

.page-content {
  max-width: 1100px;
  margin: 0 auto;
  padding: 24px;
}

.page-content h2 {
  font-size: 18px;
  font-weight: 500;
  color: #202124;
  margin: 0 0 16px;
}

/* Members */
.members-list {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.member-card {
  background: white;
  border-radius: 12px;
  padding: 20px;
}

.member-row {
  display: flex;
  align-items: center;
  gap: 16px;
  flex-wrap: wrap;
}

.member-avatar {
  width: 40px;
  height: 40px;
  background: #7c3aed;
  color: white;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  font-weight: 500;
  flex-shrink: 0;
}

.member-info {
  flex: 1;
  display: flex;
  flex-direction: column;
  min-width: 160px;
}

.member-name {
  font-weight: 500;
  color: #202124;
}

.member-email {
  font-size: 13px;
  color: #5f6368;
}

.member-joined {
  font-size: 13px;
  color: #5f6368;
}

.enroll-badge {
  padding: 4px 12px;
  border-radius: 12px;
  font-size: 12px;
  font-weight: 500;
  background: #f1f3f4;
  color: #5f6368;
}

.enroll-badge.enrolled {
  background: #e6f4ea;
  color: #137333;
}

/* Submissions */
.submissions-list {
  margin-top: 16px;
  border-top: 1px solid #f1f3f4;
}

.submission-row {
  display: flex;
  align-items: center;
  gap: 16px;
  padding: 12px 0;
  border-bottom: 1px solid #f1f3f4;
  flex-wrap: wrap;
}

.submission-row:last-child {
  border-bottom: none;
}

.submission-title {
  flex: 1;
  display: flex;
  flex-direction: column;
  min-width: 180px;
}

.topic-title {
  font-weight: 500;
  color: #202124;
  font-size: 14px;
}

.submission-meta {
  font-size: 12px;
  color: #80868b;
}

.submission-chips {
  display: flex;
  gap: 6px;
  flex-wrap: wrap;
}

.chip {
  padding: 4px 10px;
  border-radius: 12px;
  font-size: 12px;
  font-weight: 500;
  background: #f1f3f4;
  color: #5f6368;
}

.status-badge {
  padding: 4px 12px;
  border-radius: 12px;
  font-size: 12px;
  font-weight: 500;
}

.status-badge.draft { background: #fef7e0; color: #b06000; }
.status-badge.submitted { background: #e6f4ea; color: #137333; }
.status-badge.graded { background: #f5f1fe; color: #7c3aed; }

.verdict-chip.verified { background: #e6f4ea; color: #137333; }
.verdict-chip.flagged { background: #fce8e6; color: #c5221f; }
.verdict-chip.review_required { background: #fef7e0; color: #b06000; }
.verdict-chip.insufficient_data,
.verdict-chip.gray,
.verdict-chip.unavailable { background: #f1f3f4; color: #5f6368; }
.shared-chip { background: #e8f0fe; color: #1a73e8; }

.report-link {
  padding: 6px 16px;
  border: 1px solid #dadce0;
  border-radius: 16px;
  color: #7c3aed;
  font-size: 13px;
  font-weight: 500;
  text-decoration: none;
}

.report-link:hover {
  background: #faf8ff;
  border-color: #c4b5fd;
}

.draft-note {
  font-size: 13px;
  color: #80868b;
}

.no-submissions {
  margin: 12px 0 0;
  font-size: 13px;
  color: #80868b;
}

/* Loading / error / empty */
.loading {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 12px;
  padding: 60px;
  color: #5f6368;
}

.spinner {
  width: 40px;
  height: 40px;
  border: 3px solid #e0e0e0;
  border-top-color: #7c3aed;
  border-radius: 50%;
  animation: spin 1s linear infinite;
}

@keyframes spin {
  to { transform: rotate(360deg); }
}

.error-card {
  text-align: center;
  padding: 48px 20px;
  background: white;
  border-radius: 12px;
}

.error-card p {
  color: #d93025;
  margin: 0 0 16px;
}

.btn-primary {
  padding: 10px 24px;
  border: none;
  background: #7c3aed;
  color: white;
  font-weight: 500;
  border-radius: 8px;
  cursor: pointer;
}

.btn-primary:hover {
  background: #6d28d9;
}

.empty-state {
  text-align: center;
  padding: 60px 20px;
  background: white;
  border-radius: 12px;
}

.empty-state h3 {
  margin: 16px 0 8px;
  color: #202124;
}

.empty-state p {
  color: #5f6368;
  margin: 0;
}

.empty-state code {
  background: #f5f1fe;
  padding: 4px 12px;
  border-radius: 4px;
  color: #7c3aed;
}
</style>
