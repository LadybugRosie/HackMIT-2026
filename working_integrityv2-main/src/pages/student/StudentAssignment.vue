<template>
  <div class="student-assignment-page">
    <!-- Header -->
    <header class="page-header">
      <div class="header-left">
        <button @click="goBack" class="back-btn">
          <svg width="24" height="24" viewBox="0 0 24 24" fill="currentColor">
            <path d="M20 11H7.83l5.59-5.59L12 4l-8 8 8 8 1.41-1.41L7.83 13H20v-2z"/>
          </svg>
        </button>
        <div class="header-info">
          <h1>{{ assignment?.title || 'Loading...' }}</h1>
          <span class="class-name">{{ className }}</span>
        </div>
      </div>
      <div class="header-status">
        <span v-if="submission?.status === 'returned'" class="grade-badge">
          {{ submission.grade }}/{{ assignment?.points }}
        </span>
        <span v-else-if="submission?.status === 'submitted'" class="status-badge submitted">
          Submitted
        </span>
        <span v-else-if="isPastDue" class="status-badge late">
          Past Due
        </span>
        <span v-else class="status-badge pending">
          {{ dueText }}
        </span>
      </div>
    </header>

    <!-- Main Content -->
    <main class="page-content">
      <div class="content-layout">
        <!-- Left: Assignment Details -->
        <div class="details-panel">
          <!-- Assignment Info -->
          <div class="info-card">
            <div class="info-grid">
              <div class="info-item">
                <span class="info-label">Due Date</span>
                <span class="info-value" :class="{ urgent: isUrgent, past: isPastDue }">
                  {{ formatFullDate(assignment?.due_date) }}
                </span>
              </div>
              <div class="info-item">
                <span class="info-label">Points</span>
                <span class="info-value">{{ assignment?.points }}</span>
              </div>
            </div>
          </div>

          <!-- Instructions -->
          <div class="instructions-card">
            <h3>Instructions</h3>
            <div class="instructions-content">
              {{ assignment?.instructions || 'No instructions provided' }}
            </div>
          </div>

          <!-- Integrity Requirements (hidden from students in new mode) -->
          <div v-if="integrityLegacyMode" class="requirements-card">
            <h3>Requirements</h3>
            <div class="requirements-list">
              <div v-if="assignment?.settings?.face_verification_enabled" class="requirement-item">
                <svg width="20" height="20" viewBox="0 0 24 24" fill="#1a73e8">
                  <path d="M9 11.75c-.69 0-1.25.56-1.25 1.25s.56 1.25 1.25 1.25 1.25-.56 1.25-1.25-.56-1.25-1.25-1.25zm6 0c-.69 0-1.25.56-1.25 1.25s.56 1.25 1.25 1.25 1.25-.56 1.25-1.25-.56-1.25-1.25-1.25zM12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm0 18c-4.41 0-8-3.59-8-8 0-.29.02-.58.05-.86 2.36-1.05 4.23-2.98 5.21-5.37C11.07 8.33 14.05 10 17.42 10c.78 0 1.53-.09 2.25-.26.21.71.33 1.47.33 2.26 0 4.41-3.59 8-8 8z"/>
                </svg>
                <span>Face verification will be required during work</span>
              </div>
              <div v-if="assignment?.settings?.stylometry_enabled !== false" class="requirement-item">
                <svg width="20" height="20" viewBox="0 0 24 24" fill="#1a73e8">
                  <path d="M12 1L3 5v6c0 5.55 3.84 10.74 9 12 5.16-1.26 9-6.45 9-12V5l-9-4zm-2 16l-4-4 1.41-1.41L10 14.17l6.59-6.59L18 9l-8 8z"/>
                </svg>
                <span>Stylometry enrollment required — your writing style will be verified</span>
              </div>
              <div v-if="assignment?.settings?.analyze_integrity_enabled !== false" class="requirement-item">
                <svg width="20" height="20" viewBox="0 0 24 24" fill="#1a73e8">
                  <path d="M19 3H5c-1.1 0-2 .9-2 2v14c0 1.1.9 2 2 2h14c1.1 0 2-.9 2-2V5c0-1.1-.9-2-2-2zM9 17H7v-7h2v7zm4 0h-2V7h2v10zm4 0h-2v-4h2v4z"/>
                </svg>
                <span>Your typing patterns will be monitored for integrity</span>
              </div>
              <div v-if="assignment?.settings?.gptzero_enabled !== false" class="requirement-item">
                <svg width="20" height="20" viewBox="0 0 24 24" fill="#1a73e8">
                  <path d="M21 10.12h-6.78l2.74-2.82c-2.73-2.7-7.15-2.8-9.88-.1-2.73 2.71-2.73 7.08 0 9.79s7.15 2.71 9.88 0C18.32 15.65 19 14.08 19 12.1h2c0 1.98-.88 4.55-2.64 6.29-3.51 3.48-9.21 3.48-12.72 0-3.5-3.47-3.5-9.11 0-12.58 3.51-3.47 9.14-3.49 12.65 0L21 3v7.12z"/>
                </svg>
                <span>Content will be analyzed by True AI Detector</span>
              </div>
              <div v-if="assignment?.settings?.check_plagiarism" class="requirement-item">
                <svg width="20" height="20" viewBox="0 0 24 24" fill="#1a73e8">
                  <path d="M14 2H6c-1.1 0-1.99.9-1.99 2L4 20c0 1.1.89 2 1.99 2H18c1.1 0 2-.9 2-2V8l-6-6zm-2 16c-2.05 0-3.81-1.24-4.58-3h1.71c.63.9 1.68 1.5 2.87 1.5 1.93 0 3.5-1.57 3.5-3.5S13.93 9.5 12 9.5c-1.35 0-2.52.78-3.1 1.9l1.6 1.6h-4V9l1.3 1.3C8.69 8.92 10.23 8 12 8c2.76 0 5 2.24 5 5s-2.24 5-5 5z"/>
                </svg>
                <span>Work will be checked for plagiarism</span>
              </div>
            </div>
          </div>

          <!-- Rubric (if available) -->
          <div v-if="assignment?.rubric && assignment.rubric.length > 0" class="rubric-card">
            <h3>Grading Rubric</h3>
            <div class="rubric-list">
              <div 
                v-for="criterion in assignment.rubric" 
                :key="criterion.criteria_id"
                class="criterion-item"
              >
                <div class="criterion-header">
                  <span class="criterion-name">{{ criterion.name }}</span>
                  <span class="criterion-points">{{ criterion.points }} pts</span>
                </div>
                <p class="criterion-desc">{{ criterion.description }}</p>
              </div>
            </div>
          </div>
        </div>

        <!-- Right: Work Panel -->
        <div class="work-panel">
          <!-- Submission Status -->
          <div v-if="submission?.status === 'returned'" class="grade-card">
            <div class="grade-header">
              <h3>Your Grade</h3>
              <span class="graded-date">Graded {{ formatDate(submission.graded_at) }}</span>
            </div>
            <div class="grade-display">
              <span class="grade-value">{{ submission.grade }}</span>
              <span class="grade-max">/ {{ assignment?.points }}</span>
            </div>
            <div class="grade-percent" :class="getGradeClass(submission.grade, assignment?.points)">
              {{ Math.round((submission.grade / assignment?.points) * 100) }}%
            </div>
            <div v-if="submission.feedback" class="feedback-section">
              <h4>Teacher Feedback</h4>
              <pre class="feedback-text-pre">{{ submission.feedback }}</pre>
            </div>
            <div v-if="submission.grade_breakdown && submission.grade_breakdown.length" class="rubric-scores">
              <h4>Rubric Breakdown</h4>
              <div 
                v-for="score in submission.grade_breakdown" 
                :key="score.criteria_id"
                class="rubric-score-item"
              >
                <span class="criteria-name">{{ score.criteria_name || getCriterionName(score.criteria_id) }}</span>
                <span class="criteria-score">{{ score.score }}/{{ score.max_score || getCriterionPoints(score.criteria_id) }}</span>
                <p v-if="score.level_name" class="score-level">{{ score.level_name }}</p>
                <p v-if="score.explanation" class="score-explanation">{{ score.explanation }}</p>
              </div>
            </div>
            <div v-if="integrityLegacyMode" class="returned-actions">
              <button class="btn-download-pdf" @click="downloadReportAsPdf">
                <svg width="18" height="18" viewBox="0 0 24 24" fill="currentColor">
                  <path d="M19 9h-4V3H9v6H5l7 7 7-7zM5 18v2h14v-2H5z"/>
                </svg>
                Download Report as PDF
              </button>
            </div>
          </div>

          <div v-else-if="submission?.status === 'submitted' || submission?.status === 'graded'" class="submitted-card">
            <svg width="64" height="64" viewBox="0 0 24 24" fill="#1e8e3e">
              <path d="M9 16.17L4.83 12l-1.42 1.41L9 19 21 7l-1.41-1.41z"/>
            </svg>
            <h3>Assignment Submitted</h3>
            <p>Submitted on {{ formatFullDate(submission.submitted_at) }}</p>
            <div v-if="integrityLegacyMode" class="integrity-summary">
              <div class="integrity-item">
                <span class="label">Typing Trust</span>
                <span class="value" :class="getTrustClass(submission.trust_score)">
                  {{ submission.trust_score }}%
                </span>
              </div>
            </div>
            <p class="awaiting-grade-note" v-if="submission?.status === 'submitted'">
              Your teacher is reviewing your work. You'll receive your grade soon.
            </p>
            <p class="awaiting-grade-note" v-else-if="submission?.status === 'graded'">
              Your work has been graded and will be returned to you shortly.
            </p>
            <div v-if="integrityLegacyMode" class="submitted-actions">
              <button class="btn-download-pdf" @click="downloadReportAsPdf">
                <svg width="18" height="18" viewBox="0 0 24 24" fill="currentColor">
                  <path d="M19 9h-4V3H9v6H5l7 7 7-7zM5 18v2h14v-2H5z"/>
                </svg>
                Download Report as PDF
              </button>
            </div>
          </div>

          <div v-else class="work-card">
            <h3>Your Work</h3>
            <p v-if="isPastDue && !assignment?.settings?.allow_late" class="late-warning">
              This assignment is past due and no longer accepting submissions.
            </p>
            <p v-else-if="isPastDue && assignment?.settings?.allow_late" class="late-warning">
              This assignment is past due. A {{ assignment?.settings?.late_penalty_percent }}% penalty will be applied.
            </p>
            <p v-else>
              Open the editor to start working on this assignment.
            </p>
            
            <button 
              v-if="!isPastDue || assignment?.settings?.allow_late"
              class="btn-primary btn-large"
              @click="startWork"
              :disabled="checkingStylometry"
            >
              <svg v-if="!checkingStylometry" width="24" height="24" viewBox="0 0 24 24" fill="currentColor">
                <path d="M3 17.25V21h3.75L17.81 9.94l-3.75-3.75L3 17.25zM20.71 7.04c.39-.39.39-1.02 0-1.41l-2.34-2.34c-.39-.39-1.02-.39-1.41 0l-1.83 1.83 3.75 3.75 1.83-1.83z"/>
              </svg>
              {{ checkingStylometry ? 'Checking requirements...' : (submission?.status === 'draft' ? 'Continue Working' : 'Start Assignment') }}
            </button>

            <div v-if="submission?.status === 'draft'" class="draft-info">
              <span>Draft saved {{ formatDate(submission.updated_at) }}</span>
            </div>
          </div>

          <!-- Stylometry Enrollment Required Modal -->
          <div v-if="showStylometryPrompt" class="stylometry-prompt-card">
            <div class="stylometry-icon">
              <svg width="48" height="48" viewBox="0 0 24 24" fill="#1a73e8">
                <path d="M12 1L3 5v6c0 5.55 3.84 10.74 9 12 5.16-1.26 9-6.45 9-12V5l-9-4zm-2 16l-4-4 1.41-1.41L10 14.17l6.59-6.59L18 9l-8 8z"/>
              </svg>
            </div>
            <h3>Stylometry Enrollment Required</h3>
            <p>Before you can work on this assignment, you need to complete stylometry enrollment. This helps us verify your unique writing style for integrity purposes.</p>
            <p class="stylometry-note">You'll need to provide a writing sample (at least 400 words) that represents your natural writing style.</p>
            <div class="stylometry-actions">
              <button class="btn-primary" @click="goToStylometryEnrollment">
                <svg width="20" height="20" viewBox="0 0 24 24" fill="currentColor">
                  <path d="M12 1L3 5v6c0 5.55 3.84 10.74 9 12 5.16-1.26 9-6.45 9-12V5l-9-4z"/>
                </svg>
                Enroll Now
              </button>
              <button class="btn-secondary" @click="showStylometryPrompt = false">Cancel</button>
            </div>
          </div>

          <!-- Tips -->
          <div class="tips-card">
            <h4>Tips for Success</h4>
            <ul>
              <li>Type your work naturally - your typing patterns are tracked</li>
              <li>Avoid copy-pasting from external sources</li>
              <li v-if="assignment?.settings?.face_verification_enabled">
                Stay visible in your camera during the session
              </li>
              <li>Save your work frequently</li>
              <li>Submit before the deadline to avoid penalties</li>
            </ul>
          </div>
        </div>
      </div>
    </main>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { useAssignments, useClasses, useStylometryV3 } from '@/composables/classroom'
import { getApiUrl } from '@/utils/api-url'
import { integrityLegacyMode } from '@/composables/feature-flags'
import axios from 'axios'

const router = useRouter()
const route = useRoute()
const assignmentId = route.params.id

const { fetchAssignment, currentAssignment: assignment, getMySubmission } = useAssignments()
const { fetchClass } = useClasses()
const { getCourseEnrollmentStatus } = useStylometryV3()

const submission = ref(null)
const className = ref('')
const stylometryEnrolled = ref(false)
const checkingStylometry = ref(false)

const isPastDue = computed(() => {
  if (!assignment.value?.due_date) return false
  return new Date(assignment.value.due_date) < new Date()
})

const isUrgent = computed(() => {
  if (!assignment.value?.due_date) return false
  const hours = (new Date(assignment.value.due_date) - new Date()) / (1000 * 60 * 60)
  return hours > 0 && hours < 24
})

const dueText = computed(() => {
  if (!assignment.value?.due_date) return ''
  const hours = (new Date(assignment.value.due_date) - new Date()) / (1000 * 60 * 60)
  if (hours < 1) return 'Due soon'
  if (hours < 24) return `Due in ${Math.round(hours)} hours`
  const days = Math.floor(hours / 24)
  return `Due in ${days} day${days > 1 ? 's' : ''}`
})

function formatDate(date) {
  if (!date) return '-'
  return new Date(date).toLocaleDateString('en-US', {
    month: 'short',
    day: 'numeric'
  })
}

function formatFullDate(date) {
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

function getCriterionName(criteriaId) {
  const criterion = assignment.value?.rubric?.find(c => c.criteria_id === criteriaId)
  return criterion?.name || 'Unknown'
}

function getCriterionPoints(criteriaId) {
  const criterion = assignment.value?.rubric?.find(c => c.criteria_id === criteriaId)
  return criterion?.points || 0
}

function goBack() {
  if (assignment.value?.class_id) {
    router.push(`/student/class/${assignment.value.class_id}`)
  } else {
    router.push('/student/dashboard')
  }
}

async function checkStylometryStatus() {
  if (!assignment.value?.class_id) return
  try {
    const result = await getCourseEnrollmentStatus(assignment.value.class_id)
    stylometryEnrolled.value = result.success && result.data?.enrolled === true
  } catch (e) {
    console.warn('Failed to check stylometry status:', e)
    stylometryEnrolled.value = true
  }
}

async function startWork() {
  // Only check stylometry enrollment if teacher enabled stylometry for this assignment
  const stylometryOn = assignment.value?.settings?.stylometry_enabled !== false
  if (stylometryOn) {
    checkingStylometry.value = true
    await checkStylometryStatus()
    checkingStylometry.value = false

    if (!stylometryEnrolled.value) {
      showStylometryPrompt.value = true
      return
    }
  }
  
  const editorDocId = `assignment-${assignmentId}`
  router.push({
    path: `/editor/${editorDocId}`,
    query: {
      assignment_id: assignmentId,
      class_id: assignment.value?.class_id
    }
  })
}

const showStylometryPrompt = ref(false)

function goToStylometryEnrollment() {
  if (assignment.value?.class_id) {
    router.push(`/student/stylometry-enrollment/${assignment.value.class_id}`)
  } else {
    router.push('/profile')
  }
}

function viewSubmission() {
  router.push(`/student/submission/${submission.value.submission_id}`)
}

async function viewReport() {
  try {
    const API = getApiUrl()
    const res = await axios.get(`${API}/api/submissions/${submission.value.submission_id}/report`, { responseType: 'text' })
    const blob = new Blob([res.data], { type: 'text/html' })
    window.open(URL.createObjectURL(blob), '_blank')
  } catch { alert('Failed to load report') }
}

async function downloadReportAsPdf() {
  const API = getApiUrl()
  try {
    const resp = await axios.get(
      `${API}/api/submissions/${submission.value.submission_id}/report`,
      { responseType: 'text' }
    )
    const html = resp.data
    const printWin = window.open('', '_blank')
    if (!printWin) {
      alert('Please allow pop-ups to download the report.')
      return
    }
    printWin.document.open()
    printWin.document.write(`
      <!DOCTYPE html>
      <html>
      <head>
        <title>Integrity Report - ${assignment.value?.title || 'Report'}</title>
        <style>
          @media print { body { -webkit-print-color-adjust: exact; print-color-adjust: exact; } }
          body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; margin: 0; padding: 20px; background: #fff; color: #202124; }
        </style>
      </head>
      <body>${html}</body>
      </html>
    `)
    printWin.document.close()
    setTimeout(() => { printWin.focus(); printWin.print() }, 800)
  } catch (e) {
    console.error('Report download failed:', e)
    alert('Could not download report. The report may not be available yet.')
  }
}

onMounted(async () => {
  await fetchAssignment(assignmentId)
  
  if (assignment.value?.class_id) {
    const classResult = await fetchClass(assignment.value.class_id)
    if (classResult.success) {
      className.value = classResult.data.name
    }
  }
  
  const subResult = await getMySubmission(assignmentId)
  if (subResult.success && subResult.data) {
    submission.value = subResult.data
  }
})
</script>

<style scoped>
.student-assignment-page {
  min-height: 100vh;
  background: #f8f9fa;
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

.class-name {
  font-size: 14px;
  color: #5f6368;
}

.grade-badge {
  font-size: 20px;
  font-weight: 600;
  color: #1e8e3e;
}

.status-badge {
  padding: 8px 16px;
  border-radius: 20px;
  font-weight: 500;
}

.status-badge.submitted {
  background: #e6f4ea;
  color: #1e8e3e;
}

.status-badge.pending {
  background: #e8f0fe;
  color: #1a73e8;
}

.status-badge.late {
  background: #fce8e6;
  color: #d93025;
}

/* Content Layout */
.page-content {
  max-width: 1200px;
  margin: 0 auto;
  padding: 24px;
}

.content-layout {
  display: grid;
  grid-template-columns: 1fr 400px;
  gap: 24px;
}

/* Details Panel */
.details-panel {
  display: flex;
  flex-direction: column;
  gap: 20px;
}

.info-card,
.instructions-card,
.requirements-card,
.rubric-card {
  background: white;
  border-radius: 12px;
  padding: 24px;
}

.info-grid {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 20px;
}

.info-item {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.info-label {
  font-size: 12px;
  color: #5f6368;
  text-transform: uppercase;
}

.info-value {
  font-size: 16px;
  font-weight: 500;
  color: #202124;
}

.info-value.urgent {
  color: #f9ab00;
}

.info-value.past {
  color: #d93025;
}

.instructions-card h3,
.requirements-card h3,
.rubric-card h3 {
  margin: 0 0 16px;
  font-size: 18px;
  color: #202124;
}

.instructions-content {
  white-space: pre-wrap;
  line-height: 1.6;
  color: #3c4043;
}

/* Requirements */
.requirements-list {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.requirement-item {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 12px;
  background: #f8f9fa;
  border-radius: 8px;
  color: #3c4043;
}

.requirement-item.warning {
  background: #fef7e0;
}

/* Rubric */
.rubric-list {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.criterion-item {
  padding: 16px;
  background: #f8f9fa;
  border-radius: 8px;
}

.criterion-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 8px;
}

.criterion-name {
  font-weight: 500;
  color: #202124;
}

.criterion-points {
  color: #1a73e8;
  font-weight: 500;
}

.criterion-desc {
  margin: 0;
  font-size: 14px;
  color: #5f6368;
}

/* Work Panel */
.work-panel {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.grade-card,
.submitted-card,
.work-card,
.tips-card {
  background: white;
  border-radius: 12px;
  padding: 24px;
}

/* Grade Card */
.grade-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 16px;
}

.grade-header h3 {
  margin: 0;
  color: #202124;
}

.graded-date {
  font-size: 13px;
  color: #5f6368;
}

.grade-display {
  text-align: center;
  margin-bottom: 8px;
}

.grade-value {
  font-size: 64px;
  font-weight: 600;
  color: #202124;
}

.grade-max {
  font-size: 32px;
  color: #5f6368;
}

.grade-percent {
  text-align: center;
  font-size: 24px;
  font-weight: 500;
  margin-bottom: 24px;
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

.feedback-section {
  border-top: 1px solid #e0e0e0;
  padding-top: 16px;
  margin-top: 16px;
}

.feedback-section h4 {
  margin: 0 0 8px;
  font-size: 14px;
  color: #5f6368;
}

.feedback-section p {
  margin: 0;
  line-height: 1.6;
  color: #3c4043;
}

.feedback-text-pre {
  margin: 0;
  white-space: pre-wrap;
  font-family: inherit;
  font-size: 14px;
  line-height: 1.6;
  color: #3c4043;
  max-height: 400px;
  overflow-y: auto;
}

.rubric-scores {
  border-top: 1px solid #e0e0e0;
  padding-top: 16px;
  margin-top: 16px;
}

.score-level {
  font-size: 12px;
  font-weight: 500;
  color: #1a73e8;
  margin: 4px 0 0;
}

.score-explanation {
  font-size: 13px;
  color: #5f6368;
  margin: 4px 0 0;
  line-height: 1.4;
}

.rubric-scores h4 {
  margin: 0 0 12px;
  font-size: 14px;
  color: #5f6368;
}

.rubric-score-item {
  display: flex;
  justify-content: space-between;
  padding: 8px 12px;
  background: #f8f9fa;
  border-radius: 4px;
  margin-bottom: 8px;
}

.criteria-name {
  color: #3c4043;
}

.criteria-score {
  font-weight: 500;
  color: #202124;
}

/* Submitted Card */
.submitted-card {
  text-align: center;
}

.submitted-card h3 {
  margin: 16px 0 8px;
  color: #1e8e3e;
}

.submitted-card p {
  color: #5f6368;
  margin: 0 0 20px;
}

.awaiting-grade-note {
  background: #f0f4ff;
  border: 1px solid #c2d4f8;
  border-radius: 8px;
  padding: 12px 16px;
  font-size: 14px;
  color: #1a56c4;
  text-align: center;
  margin-bottom: 16px !important;
}

.submitted-actions {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.btn-view-report {
  width: 100%;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  padding: 12px 24px;
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  color: white;
  border: none;
  font-weight: 600;
  border-radius: 8px;
  cursor: pointer;
  font-size: 14px;
  transition: all 0.2s;
}

.btn-view-report:hover {
  opacity: 0.9;
  transform: translateY(-1px);
}

.btn-download-pdf {
  width: 100%;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  padding: 12px 24px;
  background: #f8f9fa;
  color: #5f6368;
  border: 1px solid #dadce0;
  font-weight: 500;
  border-radius: 8px;
  cursor: pointer;
  font-size: 14px;
  transition: all 0.2s;
}

.btn-download-pdf:hover {
  background: #e8eaed;
}

.btn-secondary {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
}

.returned-actions {
  display: flex;
  flex-direction: column;
  gap: 12px;
  margin-top: 20px;
  padding-top: 16px;
  border-top: 1px solid #e0e0e0;
}

.integrity-summary {
  display: flex;
  justify-content: center;
  gap: 32px;
  margin-bottom: 20px;
}

.integrity-item {
  display: flex;
  flex-direction: column;
  align-items: center;
}

.integrity-item .label {
  font-size: 12px;
  color: #5f6368;
}

.integrity-item .value {
  font-size: 24px;
  font-weight: 600;
}

.integrity-item .value.high {
  color: #1e8e3e;
}

.integrity-item .value.medium {
  color: #f9ab00;
}

.integrity-item .value.low {
  color: #d93025;
}

/* Work Card */
.work-card h3 {
  margin: 0 0 12px;
  color: #202124;
}

.work-card p {
  color: #5f6368;
  margin: 0 0 20px;
}

.late-warning {
  color: #d93025 !important;
  background: #fce8e6;
  padding: 12px;
  border-radius: 8px;
}

.btn-primary {
  width: 100%;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 12px;
  padding: 16px 24px;
  border: none;
  background: #1a73e8;
  color: white;
  font-weight: 500;
  font-size: 16px;
  border-radius: 8px;
  cursor: pointer;
}

.btn-primary:hover {
  background: #1557b0;
}

.btn-secondary {
  width: 100%;
  padding: 12px 24px;
  border: 1px solid #dadce0;
  background: white;
  color: #5f6368;
  font-weight: 500;
  border-radius: 8px;
  cursor: pointer;
}

.btn-secondary:hover {
  background: #f8f9fa;
}

.draft-info {
  margin-top: 12px;
  text-align: center;
  font-size: 13px;
  color: #5f6368;
}

/* Tips Card */
.tips-card h4 {
  margin: 0 0 12px;
  font-size: 16px;
  color: #202124;
}

.tips-card ul {
  margin: 0;
  padding-left: 20px;
}

.tips-card li {
  margin-bottom: 8px;
  color: #5f6368;
  line-height: 1.5;
}

/* Stylometry Prompt */
.stylometry-prompt-card {
  background: white;
  border-radius: 12px;
  padding: 24px;
  text-align: center;
  border: 2px solid #e8f0fe;
}

.stylometry-icon {
  margin-bottom: 12px;
}

.stylometry-prompt-card h3 {
  margin: 0 0 12px;
  color: #202124;
}

.stylometry-prompt-card p {
  color: #5f6368;
  margin: 0 0 12px;
  line-height: 1.6;
}

.stylometry-note {
  background: #f0f4ff;
  border-radius: 8px;
  padding: 12px;
  font-size: 13px;
  color: #1a56c4 !important;
  margin-bottom: 20px !important;
}

.stylometry-actions {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

@media (max-width: 1024px) {
  .content-layout {
    grid-template-columns: 1fr;
  }
  
  .info-grid {
    grid-template-columns: 1fr;
    gap: 12px;
  }
}
</style>
