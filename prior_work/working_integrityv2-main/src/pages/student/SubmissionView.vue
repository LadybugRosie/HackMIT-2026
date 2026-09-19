<template>
  <div class="submission-view-page">
    <!-- Header -->
    <header class="page-header">
      <div class="header-left">
        <button @click="goBack" class="back-btn">
          <svg width="24" height="24" viewBox="0 0 24 24" fill="currentColor">
            <path d="M20 11H7.83l5.59-5.59L12 4l-8 8 8 8 1.41-1.41L7.83 13H20v-2z"/>
          </svg>
        </button>
        <div class="header-info">
          <h1>{{ submission?.assignment_title || 'My Submission' }}</h1>
          <span class="status-text">
            {{ statusText }}
          </span>
        </div>
      </div>
      <div v-if="submission?.grade !== null && submission?.grade !== undefined" class="header-grade">
        <span class="grade">{{ submission.grade }}/{{ submission.assignment_points }}</span>
      </div>
    </header>

    <!-- Main Content -->
    <main class="page-content">
      <div class="content-layout">
        <!-- Submission Content -->
        <div class="content-panel">
          <div class="content-card">
            <h3>Your Work</h3>
            <div class="submission-content">
              <pre>{{ submission?.content || 'No content' }}</pre>
            </div>
            <div class="submission-meta">
              <span>Submitted {{ formatDate(submission?.submitted_at) }}</span>
              <span v-if="submission?.is_late" class="late-badge">Late Submission</span>
            </div>
          </div>
        </div>

        <!-- Sidebar -->
        <div class="sidebar-panel">
          <!-- Grade Card -->
          <div v-if="submission?.status === 'returned'" class="grade-card">
            <h3>Grade</h3>
            <div class="grade-display">
              <span class="grade-value">{{ submission.grade }}</span>
              <span class="grade-max">/ {{ submission.assignment_points }}</span>
            </div>
            <div class="grade-percent" :class="getGradeClass(submission.grade, submission.assignment_points)">
              {{ Math.round((submission.grade / submission.assignment_points) * 100) }}%
            </div>
          </div>

          <!-- Feedback -->
          <div v-if="submission?.feedback" class="feedback-card">
            <h3>Teacher Feedback</h3>
            <pre class="feedback-text">{{ submission.feedback }}</pre>
          </div>

          <!-- View Full Integrity Report — same report teacher sees; always server-generated -->
          <div v-if="integrityLegacyMode && canViewReport" class="report-card">
            <button class="view-report-btn" @click="viewReport">
              <svg width="20" height="20" viewBox="0 0 24 24" fill="currentColor">
                <path d="M14 2H6c-1.1 0-1.99.9-1.99 2L4 20c0 1.1.89 2 1.99 2H18c1.1 0 2-.9 2-2V8l-6-6zm-2 16c-2.05 0-3.81-1.24-4.58-3h1.71c.63.9 1.68 1.5 2.87 1.5 1.93 0 3.5-1.57 3.5-3.5S13.93 9.5 12 9.5c-1.35 0-2.52.78-3.1 1.9l1.6 1.6h-4V9l1.3 1.3C8.69 8.92 10.23 8 12 8c2.76 0 5 2.24 5 5s-2.24 5-5 5z"/>
              </svg>
              View Full Integrity Report
            </button>
            <p class="report-note">Same report your teacher sees. Generated server-side — cannot be forged.</p>
          </div>

          <!-- Authorship Verification (V3 Stylometry) -->
          <div v-if="integrityLegacyMode && styloV3" class="authorship-card" :class="styloV3Class">
            <div class="authorship-header">
              <svg v-if="styloV3.verdict === 'verified'" width="24" height="24" viewBox="0 0 24 24" fill="#1e8e3e"><path d="M9 16.17L4.83 12l-1.42 1.41L9 19 21 7l-1.41-1.41z"/></svg>
              <svg v-else-if="styloV3.verdict === 'flagged'" width="24" height="24" viewBox="0 0 24 24" fill="#d93025"><path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm1 15h-2v-2h2v2zm0-4h-2V7h2v6z"/></svg>
              <svg v-else-if="styloV3.verdict === 'review_required'" width="24" height="24" viewBox="0 0 24 24" fill="#f9ab00"><path d="M1 21h22L12 2 1 21zm12-3h-2v-2h2v2zm0-4h-2v-4h2v4z"/></svg>
              <svg v-else width="24" height="24" viewBox="0 0 24 24" fill="#9aa0a6"><path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm1 15h-2v-6h2v6zm0-8h-2V7h2v2z"/></svg>
              <div>
                <h3 class="authorship-title">{{ styloV3VerdictText }}</h3>
                <span class="authorship-match">{{ Math.round((styloV3.probability || 0) * 100) }}% match</span>
              </div>
            </div>
            <div class="authorship-details">
              <div class="detail-row">
                <span>Profile Strength</span>
                <span class="detail-val">{{ styloV3.profile_strength || 'N/A' }}</span>
              </div>
              <div class="detail-row" v-if="styloV3.cosine_score">
                <span>Cosine Similarity</span>
                <span class="detail-val">{{ (styloV3.cosine_score * 100).toFixed(1) }}%</span>
              </div>
            </div>
          </div>

          <!-- Integrity Report -->
          <div v-if="integrityLegacyMode" class="integrity-card">
            <h3>Integrity Report</h3>
            <div class="integrity-stats">
              <div class="stat-row">
                <span class="stat-label">Trust Score</span>
                <span class="stat-value" :class="getTrustClass(submission?.trust_score)">
                  {{ submission?.trust_score || 0 }}%
                </span>
              </div>
              <div class="stat-row">
                <span class="stat-label">Typed Characters</span>
                <span class="stat-value">{{ typedPercent }}%</span>
              </div>
              <div class="stat-row">
                <span class="stat-label">Pasted Characters</span>
                <span class="stat-value">{{ pastedPercent }}%</span>
              </div>
            </div>

            <div class="trust-bar">
              <div 
                class="trust-fill" 
                :style="{ width: (submission?.trust_score || 0) + '%' }"
                :class="getTrustClass(submission?.trust_score)"
              ></div>
            </div>
            <p class="trust-description">
              {{ getTrustDescription(submission?.trust_score) }}
            </p>
          </div>

          <!-- Plagiarism (if any) -->
          <div v-if="integrityLegacyMode && submission?.plagiarism_score > 0" class="plagiarism-card">
            <h3>Similarity Check</h3>
            <div class="plagiarism-score" :class="getPlagiarismClass(submission.plagiarism_score)">
              {{ submission.plagiarism_score }}% similar
            </div>
            <p class="plagiarism-note">
              Your submission was compared against other submissions in the class.
            </p>
          </div>

          <!-- Rubric Scores (stored as grade_breakdown from backend) -->
          <div v-if="rubricBreakdown && rubricBreakdown.length > 0" class="rubric-card">
            <h3>Rubric Breakdown</h3>
            <div class="rubric-list">
              <div 
                v-for="score in rubricBreakdown" 
                :key="score.criteria_id"
                class="rubric-item"
              >
                <div class="rubric-header">
                  <span class="criteria-name">{{ score.criteria_name || 'Criterion' }}</span>
                  <span class="criteria-score">{{ score.score }}/{{ score.max_score || score.max_points || 0 }}</span>
                </div>
                <div class="score-bar">
                  <div 
                    class="score-fill"
                    :style="{ width: ((score.score / (score.max_score || score.max_points || 1)) * 100) + '%' }"
                  ></div>
                </div>
                <p v-if="score.level_name" class="criteria-level">{{ score.level_name }}</p>
                <p v-if="score.explanation || score.feedback" class="criteria-feedback">{{ score.explanation || score.feedback }}</p>
              </div>
            </div>
          </div>

          <!-- Timeline -->
          <div class="timeline-card">
            <h3>Activity</h3>
            <div class="timeline">
              <div class="timeline-item">
                <div class="timeline-dot"></div>
                <div class="timeline-content">
                  <span class="timeline-title">Started</span>
                  <span class="timeline-date">{{ formatDate(submission?.created_at) }}</span>
                </div>
              </div>
              <div class="timeline-item">
                <div class="timeline-dot"></div>
                <div class="timeline-content">
                  <span class="timeline-title">Submitted</span>
                  <span class="timeline-date">{{ formatDate(submission?.submitted_at) }}</span>
                </div>
              </div>
              <div v-if="submission?.status === 'returned'" class="timeline-item">
                <div class="timeline-dot success"></div>
                <div class="timeline-content">
                  <span class="timeline-title">Graded</span>
                  <span class="timeline-date">{{ formatDate(submission?.graded_at) }}</span>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>

      <!-- Session Replay — the student's own writing session, event by event -->
      <section v-if="snapshots.length > 0 || playbackEvents.length > 0" class="playback-section">
        <h3>Your Session Replay</h3>
        <p class="playback-hint">Watch your own writing session exactly as it happened — every keystroke, paste and pause.</p>
        <PlaybackViewer :snapshots="snapshots" :events="playbackEvents" :authors="playbackAuthors" :meta="playbackMeta" />
      </section>
    </main>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import axios from 'axios'
import { useSubmissions } from '@/composables/classroom'
import { getApiUrl } from '@/utils/api-url'
import { integrityLegacyMode } from '@/composables/feature-flags'
import PlaybackViewer from '@/components/playback/PlaybackViewer.vue'

const router = useRouter()
const route = useRoute()
const submissionId = route.params.id

const { fetchSubmission, currentSubmission: submission } = useSubmissions()

// Session replay — students may watch their own recording (backend already
// authorizes owners; the viewer prefers the exact event stream when present)
const snapshots = ref([])
const playbackEvents = ref([])
const playbackAuthors = ref({})

const playbackMeta = computed(() => ({
  studentName: submission.value?.student_name || 'You',
  title: submission.value?.assignment_title || 'My Submission',
  totalDurationMs: 0,
}))

const statusText = computed(() => {
  if (!submission.value) return ''
  switch (submission.value.status) {
    case 'returned': return 'Graded'
    case 'graded': return 'Grading Complete'
    case 'submitted': return 'Submitted - Awaiting Grade'
    case 'draft': return 'Draft'
    default: return submission.value.status
  }
})

const canViewReport = computed(() => {
  const s = submission.value?.status
  return s === 'submitted' || s === 'graded' || s === 'returned'
})

const styloV3 = computed(() => submission.value?.stylometry_v3 || null)

const styloV3Class = computed(() => {
  const v = styloV3.value?.verdict
  if (v === 'verified') return 'verdict-verified'
  if (v === 'flagged') return 'verdict-flagged'
  if (v === 'review_required') return 'verdict-review'
  return 'verdict-inconclusive'
})

const styloV3VerdictText = computed(() => {
  const v = styloV3.value?.verdict
  if (v === 'verified') return 'Authorship Verified'
  if (v === 'flagged') return 'Authorship Flagged'
  if (v === 'review_required') return 'Manual Review Needed'
  return 'Inconclusive'
})

const typedPercent = computed(() => {
  const mix = submission.value?.content_mix
  if (!mix) return 0
  return Math.round((mix.typed || 0) * 100)
})

const pastedPercent = computed(() => {
  const mix = submission.value?.content_mix
  if (!mix) return 0
  return Math.round(((mix.internal || 0) + (mix.external || 0)) * 100)
})

const rubricBreakdown = computed(() => {
  // Backend stores rubric scores as 'grade_breakdown'
  return submission.value?.grade_breakdown || submission.value?.rubric_scores || []
})

function formatDate(date) {
  if (!date) return '-'
  return new Date(date).toLocaleString('en-US', {
    month: 'short',
    day: 'numeric',
    year: 'numeric',
    hour: 'numeric',
    minute: '2-digit'
  })
}

function getGradeClass(grade, maxPoints) {
  const percent = (grade / maxPoints) * 100
  if (percent >= 90) return 'excellent'
  if (percent >= 80) return 'good'
  if (percent >= 70) return 'average'
  return 'poor'
}

function getTrustClass(score) {
  if (score >= 80) return 'high'
  if (score >= 60) return 'medium'
  return 'low'
}

function getPlagiarismClass(score) {
  if (score <= 20) return 'low'
  if (score <= 40) return 'medium'
  return 'high'
}

async function viewReport() {
  try {
    const API = getApiUrl()
    const res = await axios.get(`${API}/api/submissions/${submissionId}/report`, { responseType: 'text' })
    const blob = new Blob([res.data], { type: 'text/html' })
    window.open(URL.createObjectURL(blob), '_blank')
  } catch { alert('Failed to load report') }
}

function getTrustDescription(score) {
  if (!score) return 'No integrity data available'
  if (score >= 80) return 'Excellent integrity score. Your work shows authentic typing patterns.'
  if (score >= 60) return 'Good integrity score. Minor concerns with typing patterns.'
  return 'Low integrity score. Significant portions may not be original typing.'
}

function goBack() {
  // Navigate to a known route instead of router.back() to prevent state loss
  if (submission.value?.assignment_id) {
    router.push(`/student/assignment/${submission.value.assignment_id}`)
  } else {
    router.push('/student/dashboard')
  }
}

onMounted(async () => {
  await fetchSubmission(submissionId)

  // Load the session recording (non-blocking; section hides when absent)
  const API = getApiUrl()
  const [snapResp, evResp] = await Promise.allSettled([
    axios.get(`${API}/api/session-playback/${submissionId}`),
    axios.get(`${API}/api/session-playback/${submissionId}/events`),
  ])
  if (snapResp.status === 'fulfilled') {
    snapshots.value = snapResp.value.data.snapshots || []
  }
  if (evResp.status === 'fulfilled' && evResp.value.data?.found) {
    playbackEvents.value = evResp.value.data.events || []
    playbackAuthors.value = evResp.value.data.authors || {}
  }
})
</script>

<style scoped>
.submission-view-page {
  min-height: 100vh;
  background: #f8f9fa;
}

/* Session replay section */
.playback-section {
  max-width: 1200px;
  margin: 24px auto 0;
  padding: 0 24px 24px;
}
.playback-section h3 {
  font-size: 18px;
  color: #202124;
  margin: 0 0 4px;
}
.playback-hint {
  font-size: 13px;
  color: #5f6368;
  margin: 0 0 14px;
}

.page-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 16px 24px;
  background: white;
  border-bottom: 1px solid #e0e0e0;
}

.header-left {
  display: flex;
  align-items: center;
  gap: 16px;
}

.back-btn {
  width: 40px;
  height: 40px;
  border: none;
  background: transparent;
  border-radius: 50%;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  color: #5f6368;
}

.back-btn:hover {
  background: #f1f3f4;
}

.header-info h1 {
  font-size: 20px;
  font-weight: 500;
  margin: 0;
  color: #202124;
}

.status-text {
  font-size: 14px;
  color: #5f6368;
}

.header-grade .grade {
  font-size: 24px;
  font-weight: 600;
  color: #1e8e3e;
}

/* Content Layout */
.page-content {
  max-width: 1200px;
  margin: 0 auto;
  padding: 24px;
}

.content-layout {
  display: grid;
  grid-template-columns: 1fr 360px;
  gap: 24px;
}

/* Content Panel */
.content-panel {
  display: flex;
  flex-direction: column;
  gap: 20px;
}

.content-card {
  background: white;
  border-radius: 12px;
  padding: 24px;
}

.content-card h3 {
  margin: 0 0 16px;
  font-size: 18px;
  color: #202124;
}

.submission-content {
  background: #f8f9fa;
  border-radius: 8px;
  padding: 20px;
  max-height: 600px;
  overflow-y: auto;
}

.submission-content pre {
  margin: 0;
  white-space: pre-wrap;
  font-family: inherit;
  line-height: 1.6;
  color: #3c4043;
}

.submission-meta {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-top: 16px;
  font-size: 13px;
  color: #5f6368;
}

.late-badge {
  background: #fce8e6;
  color: #d93025;
  padding: 4px 12px;
  border-radius: 12px;
  font-weight: 500;
}

/* Sidebar */
.sidebar-panel {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.report-card {
  background: white;
  border-radius: 12px;
  padding: 16px;
}

.view-report-btn {
  width: 100%;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 10px;
  padding: 14px 24px;
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  color: white;
  border: none;
  border-radius: 10px;
  font-weight: 600;
  font-size: 15px;
  cursor: pointer;
  transition: all 0.2s;
}
.view-report-btn:hover { opacity: 0.9; transform: translateY(-1px); }

.report-note {
  margin: 8px 0 0 0;
  font-size: 12px;
  color: #5f6368;
  line-height: 1.4;
}

.grade-card,
.feedback-card,
.integrity-card,
.plagiarism-card,
.rubric-card,
.timeline-card {
  background: white;
  border-radius: 12px;
  padding: 20px;
}

.grade-card h3,
.feedback-card h3,
.integrity-card h3,
.plagiarism-card h3,
.rubric-card h3,
.timeline-card h3 {
  margin: 0 0 16px;
  font-size: 16px;
  color: #202124;
}

/* Grade Card */
.grade-display {
  text-align: center;
  margin-bottom: 8px;
}

.grade-value {
  font-size: 48px;
  font-weight: 600;
  color: #202124;
}

.grade-max {
  font-size: 24px;
  color: #5f6368;
}

.grade-percent {
  text-align: center;
  font-size: 20px;
  font-weight: 500;
}

.grade-percent.excellent {
  color: #1e8e3e;
}

.grade-percent.good {
  color: #1a73e8;
}

.grade-percent.average {
  color: #f9ab00;
}

.grade-percent.poor {
  color: #d93025;
}

/* Feedback Card */
.feedback-text {
  margin: 0;
  line-height: 1.6;
  color: #3c4043;
  white-space: pre-wrap;
  font-family: inherit;
  font-size: 14px;
  max-height: 400px;
  overflow-y: auto;
}

/* Integrity Card */
.integrity-stats {
  display: flex;
  flex-direction: column;
  gap: 12px;
  margin-bottom: 16px;
}

.stat-row {
  display: flex;
  justify-content: space-between;
}

.stat-label {
  color: #5f6368;
}

.stat-value {
  font-weight: 500;
}

.stat-value.high {
  color: #1e8e3e;
}

.stat-value.medium {
  color: #f9ab00;
}

.stat-value.low {
  color: #d93025;
}

.trust-bar {
  height: 8px;
  background: #e0e0e0;
  border-radius: 4px;
  overflow: hidden;
  margin-bottom: 12px;
}

.trust-fill {
  height: 100%;
  border-radius: 4px;
  transition: width 0.3s;
}

.trust-fill.high {
  background: #1e8e3e;
}

.trust-fill.medium {
  background: #f9ab00;
}

.trust-fill.low {
  background: #d93025;
}

.trust-description {
  margin: 0;
  font-size: 13px;
  color: #5f6368;
  line-height: 1.5;
}

/* Plagiarism Card */
.plagiarism-score {
  font-size: 24px;
  font-weight: 600;
  margin-bottom: 8px;
}

.plagiarism-score.low {
  color: #1e8e3e;
}

.plagiarism-score.medium {
  color: #f9ab00;
}

.plagiarism-score.high {
  color: #d93025;
}

.plagiarism-note {
  margin: 0;
  font-size: 13px;
  color: #5f6368;
}

/* Rubric Card */
.rubric-list {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.rubric-item {
  padding-bottom: 16px;
  border-bottom: 1px solid #e0e0e0;
}

.rubric-item:last-child {
  padding-bottom: 0;
  border-bottom: none;
}

.rubric-header {
  display: flex;
  justify-content: space-between;
  margin-bottom: 8px;
}

.criteria-name {
  font-weight: 500;
  color: #202124;
}

.criteria-score {
  color: #1a73e8;
  font-weight: 500;
}

.score-bar {
  height: 6px;
  background: #e0e0e0;
  border-radius: 3px;
  overflow: hidden;
}

.score-fill {
  height: 100%;
  background: #1a73e8;
  border-radius: 3px;
}

.criteria-level {
  margin: 4px 0 0;
  font-size: 12px;
  font-weight: 500;
  color: #1a73e8;
}

.criteria-feedback {
  margin: 8px 0 0;
  font-size: 13px;
  color: #5f6368;
  line-height: 1.4;
}

/* Timeline Card */
.timeline {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.timeline-item {
  display: flex;
  gap: 12px;
}

.timeline-dot {
  width: 12px;
  height: 12px;
  border-radius: 50%;
  background: #dadce0;
  margin-top: 4px;
}

.timeline-dot.success {
  background: #1e8e3e;
}

.timeline-content {
  display: flex;
  flex-direction: column;
}

.timeline-title {
  font-weight: 500;
  color: #202124;
}

.timeline-date {
  font-size: 13px;
  color: #5f6368;
}

/* Authorship Card */
.authorship-card {
  border-radius: 12px;
  padding: 20px;
  border: 2px solid;
}
.authorship-card.verdict-verified { background: #e6f4ea; border-color: #1e8e3e; }
.authorship-card.verdict-flagged { background: #fce8e6; border-color: #d93025; }
.authorship-card.verdict-review { background: #fef7e0; border-color: #f9ab00; }
.authorship-card.verdict-inconclusive { background: #f1f3f4; border-color: #dadce0; }

.authorship-header {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 12px;
}

.authorship-title {
  margin: 0;
  font-size: 16px;
  color: #202124;
}

.authorship-match {
  font-size: 14px;
  font-weight: 600;
  color: #3c4043;
}

.authorship-details {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.detail-row {
  display: flex;
  justify-content: space-between;
  font-size: 13px;
  color: #5f6368;
}

.detail-val { font-weight: 500; color: #202124; }

/* Authorship Card */
.authorship-card {
  border-radius: 12px;
  padding: 20px;
  border-left: 4px solid #9aa0a6;
  background: white;
}
.authorship-card.verdict-verified { border-left-color: #1e8e3e; background: #f0faf3; }
.authorship-card.verdict-flagged { border-left-color: #d93025; background: #fef2f0; }
.authorship-card.verdict-review { border-left-color: #f9ab00; background: #fefce8; }
.authorship-card.verdict-inconclusive { border-left-color: #9aa0a6; background: #f8f9fa; }

.authorship-header {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 16px;
}
.authorship-title {
  margin: 0;
  font-size: 16px;
  color: #202124;
}
.authorship-match {
  font-size: 13px;
  color: #5f6368;
}
.authorship-details {
  display: flex;
  flex-direction: column;
  gap: 8px;
}
.detail-row {
  display: flex;
  justify-content: space-between;
  font-size: 13px;
  color: #5f6368;
}
.detail-val {
  font-weight: 500;
  color: #202124;
}

@media (max-width: 1024px) {
  .content-layout {
    grid-template-columns: 1fr;
  }
}
</style>
