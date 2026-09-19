<template>
  <div class="assignment-detail-page">
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
      <div class="header-actions">
        <button class="btn-secondary" @click="editAssignment">
          <svg width="18" height="18" viewBox="0 0 24 24" fill="currentColor">
            <path d="M3 17.25V21h3.75L17.81 9.94l-3.75-3.75L3 17.25zM20.71 7.04c.39-.39.39-1.02 0-1.41l-2.34-2.34c-.39-.39-1.02-.39-1.41 0l-1.83 1.83 3.75 3.75 1.83-1.83z"/>
          </svg>
          Edit
        </button>
        <button 
          v-if="!assignment?.published" 
          class="btn-primary"
          @click="publish"
        >
          Publish
        </button>
        <button 
          v-else 
          class="btn-text"
          @click="unpublish"
        >
          Unpublish
        </button>
      </div>
    </header>

    <!-- Tabs -->
    <nav class="tabs-nav">
      <button 
        :class="['tab', { active: activeTab === 'instructions' }]"
        @click="activeTab = 'instructions'"
      >
        Instructions
      </button>
      <button 
        :class="['tab', { active: activeTab === 'submissions' }]"
        @click="activeTab = 'submissions'"
      >
        Submissions
        <span v-if="submissionStats.total > 0" class="tab-badge">
          {{ submissionStats.submitted }}/{{ submissionStats.total }}
        </span>
      </button>
      <button 
        :class="['tab', { active: activeTab === 'rubric' }]"
        @click="activeTab = 'rubric'"
      >
        Rubric
      </button>
      <button 
        :class="['tab', { active: activeTab === 'settings' }]"
        @click="activeTab = 'settings'"
      >
        Settings
      </button>
    </nav>

    <!-- Content -->
    <main class="page-content">
      <!-- Instructions Tab -->
      <div v-if="activeTab === 'instructions'" class="tab-content">
        <div class="info-card">
          <div class="info-row">
            <div class="info-item">
              <span class="info-label">Due Date</span>
              <span class="info-value">{{ formatDate(assignment?.due_date) }}</span>
            </div>
            <div class="info-item">
              <span class="info-label">Points</span>
              <span class="info-value">{{ assignment?.points }}</span>
            </div>
            <div class="info-item">
              <span class="info-label">Status</span>
              <span :class="['status-badge', assignment?.published ? 'published' : 'draft']">
                {{ assignment?.published ? 'Published' : 'Draft' }}
              </span>
            </div>
          </div>
        </div>

        <div class="instructions-card">
          <h3>Instructions</h3>
          <div class="instructions-content">
            {{ assignment?.instructions }}
          </div>
        </div>

        <div class="integrity-card">
          <h3>Integrity Settings</h3>
          <div class="settings-list">
            <div class="setting-row">
              <span class="setting-label">Face Verification</span>
              <span :class="assignment?.settings?.face_verification_enabled ? 'enabled' : 'disabled'">
                {{ assignment?.settings?.face_verification_enabled ? 'Enabled' : 'Disabled' }}
              </span>
            </div>
            <div class="setting-row">
              <span class="setting-label">Plagiarism Check</span>
              <span :class="assignment?.settings?.check_plagiarism ? 'enabled' : 'disabled'">
                {{ assignment?.settings?.check_plagiarism ? 'Enabled' : 'Disabled' }}
              </span>
            </div>
            <div class="setting-row">
              <span class="setting-label">Auto-Grading (AI)</span>
              <span :class="assignment?.settings?.auto_grade_enabled ? 'enabled' : 'disabled'">
                {{ assignment?.settings?.auto_grade_enabled ? 'Enabled' : 'Disabled' }}
              </span>
            </div>
            <div class="setting-row">
              <span class="setting-label">Minimum Typing Trust Score</span>
              <span class="setting-value-text">{{ assignment?.settings?.minimum_trust_score || 60 }}%</span>
            </div>
          </div>
        </div>
      </div>

      <!-- Submissions Tab -->
      <div v-if="activeTab === 'submissions'" class="tab-content">
        <div class="submissions-header">
          <div class="stats-row">
            <div class="stat-item">
              <span class="stat-value">{{ submissionStats.submitted }}</span>
              <span class="stat-label">Submitted</span>
            </div>
            <div class="stat-item">
              <span class="stat-value">{{ submissionStats.graded }}</span>
              <span class="stat-label">Graded</span>
            </div>
            <div class="stat-item">
              <span class="stat-value">{{ submissionStats.returned }}</span>
              <span class="stat-label">Returned</span>
            </div>
            <div class="stat-item">
              <span class="stat-value">{{ submissionStats.avgScore || '-' }}</span>
              <span class="stat-label">Avg Score</span>
            </div>
          </div>
          <div class="actions-row">
            <button 
              v-if="submissionStats.graded > submissionStats.returned"
              class="btn-secondary"
              @click="bulkReturn"
            >
              Return All Graded
            </button>
          </div>
        </div>

        <div class="submissions-list">
          <div v-if="loading" class="loading">Loading submissions...</div>
          <div v-else-if="submissions.length === 0" class="empty-state">
            <p>No submissions yet</p>
          </div>
          <div v-else>
            <div 
              v-for="sub in submissions" 
              :key="sub.submission_id"
              class="submission-card"
              @click="viewSubmission(sub)"
            >
              <div class="student-info">
                <div class="avatar">{{ getInitials(sub.student_name) }}</div>
                <div class="student-details">
                  <span class="student-name">{{ sub.student_name }}</span>
                  <span class="submitted-at">{{ formatDate(sub.submitted_at) }}</span>
                </div>
              </div>
              <div class="submission-meta">
                <div class="trust-score" :class="getTrustClass(sub.trust_score)">
                  <span class="score-label">Typing Trust</span>
                  <span class="score-value">{{ sub.trust_score }}%</span>
                </div>
                <div v-if="sub.stylometry_verdict" class="trust-score" :class="styloChipClass(sub.stylometry_verdict)">
                  <span class="score-label">Stylometry</span>
                  <span class="score-value stylo-value">{{ styloChipText(sub.stylometry_verdict) }}</span>
                </div>
                <div v-if="sub.ai_probability != null" class="trust-score" :class="aiChipClass(sub.ai_probability)">
                  <span class="score-label">AI</span>
                  <span class="score-value">{{ Math.round(sub.ai_probability * 100) }}%</span>
                </div>
                <div v-if="sub.plagiarism_score > 0" class="plagiarism-score">
                  <span class="score-label">Similarity</span>
                  <span class="score-value">{{ sub.plagiarism_score }}%</span>
                </div>
                <div class="grade-info">
                  <span v-if="sub.grade !== null" class="grade">
                    {{ sub.grade }}/{{ assignment?.points }}
                  </span>
                  <span v-else class="no-grade">Not graded</span>
                </div>
                <span :class="['status-badge', sub.status]">{{ sub.status }}</span>
              </div>
            </div>
          </div>
        </div>
      </div>

      <!-- Rubric Tab -->
      <div v-if="activeTab === 'rubric'" class="tab-content">
        <!-- View Mode: Show existing rubric -->
        <div v-if="!editingRubric && assignment?.rubric && assignment.rubric.length > 0" class="rubric-view">
          <div class="rubric-view-header">
            <div class="rubric-summary">
              <span class="rubric-count">{{ assignment.rubric.length }} criteria</span>
              <span class="rubric-total-pts">{{ rubricTotalPoints }} total points</span>
            </div>
            <button class="btn-secondary" @click="startEditRubric">
              <svg width="16" height="16" viewBox="0 0 24 24" fill="currentColor">
                <path d="M3 17.25V21h3.75L17.81 9.94l-3.75-3.75L3 17.25zM20.71 7.04c.39-.39.39-1.02 0-1.41l-2.34-2.34c-.39-.39-1.02-.39-1.41 0l-1.83 1.83 3.75 3.75 1.83-1.83z"/>
              </svg>
              Edit Rubric
            </button>
          </div>
          <div 
            v-for="criterion in assignment.rubric" 
            :key="criterion.criteria_id"
            class="criterion-card"
          >
            <div class="criterion-header">
              <h4>{{ criterion.name }}</h4>
              <span class="criterion-points">{{ criterion.points }} pts</span>
            </div>
            <p class="criterion-desc">{{ criterion.description }}</p>
            <div class="levels-grid">
              <div 
                v-for="level in criterion.levels" 
                :key="level.name"
                class="level-card"
              >
                <div class="level-header">
                  <span class="level-name">{{ level.name }}</span>
                  <span class="level-points">{{ level.points }} pts</span>
                </div>
                <p class="level-desc">{{ level.description }}</p>
              </div>
            </div>
          </div>
        </div>

        <!-- Edit / Add Mode -->
        <div v-if="editingRubric || !assignment?.rubric || assignment.rubric.length === 0" class="rubric-editor">
          <div class="rubric-editor-header">
            <h3>{{ assignment?.rubric?.length ? 'Edit Rubric' : 'Add Rubric' }}</h3>
            <button v-if="assignment?.rubric?.length" class="btn-text" @click="cancelEditRubric">Cancel</button>
          </div>

          <!-- Mode Tabs -->
          <div class="rubric-mode-tabs">
            <button :class="['mode-tab', { active: rubricMode === 'manual' }]" @click="rubricMode = 'manual'">
              <svg width="16" height="16" viewBox="0 0 24 24" fill="currentColor">
                <path d="M3 17.25V21h3.75L17.81 9.94l-3.75-3.75L3 17.25zM20.71 7.04c.39-.39.39-1.02 0-1.41l-2.34-2.34c-.39-.39-1.02-.39-1.41 0l-1.83 1.83 3.75 3.75 1.83-1.83z"/>
              </svg>
              Manual
            </button>
            <button :class="['mode-tab', { active: rubricMode === 'text' }]" @click="rubricMode = 'text'">
              <svg width="16" height="16" viewBox="0 0 24 24" fill="currentColor">
                <path d="M14 2H6c-1.1 0-1.99.9-1.99 2L4 20c0 1.1.89 2 1.99 2H18c1.1 0 2-.9 2-2V8l-6-6zm2 16H8v-2h8v2zm0-4H8v-2h8v2zM13 9V3.5L18.5 9H13z"/>
              </svg>
              Type / Paste
            </button>
            <button :class="['mode-tab', { active: rubricMode === 'upload' }]" @click="rubricMode = 'upload'">
              <svg width="16" height="16" viewBox="0 0 24 24" fill="currentColor">
                <path d="M9 16h6v-6h4l-7-7-7 7h4zm-4 2h14v2H5z"/>
              </svg>
              Upload File
            </button>
            <button :class="['mode-tab ai-tab', { active: rubricMode === 'ai' }]" @click="rubricMode = 'ai'">
              <svg width="16" height="16" viewBox="0 0 24 24" fill="currentColor">
                <path d="M19.36 10.04C18.67 6.59 15.64 4 12 4 9.11 4 6.6 5.64 5.35 8.04 2.34 8.36 0 10.91 0 14c0 3.31 2.69 6 6 6h13c2.76 0 5-2.24 5-5 0-2.64-2.05-4.78-4.64-4.96z"/>
              </svg>
              AI Generate
            </button>
          </div>

          <!-- Manual Mode -->
          <div v-if="rubricMode === 'manual'" class="rubric-manual-mode">
            <div v-if="rubricCriteria.length > 0" class="rubric-criteria-list">
              <div v-for="(criterion, idx) in rubricCriteria" :key="idx" class="criterion-edit-card">
                <div class="criterion-edit-header">
                  <input v-model="criterion.name" placeholder="Criterion name (e.g., Thesis Statement)" class="criterion-name-input" />
                  <input v-model.number="criterion.points" type="number" placeholder="Pts" class="criterion-pts-input" min="1" />
                  <button class="remove-criterion-btn" @click="rubricCriteria.splice(idx, 1)">
                    <svg width="20" height="20" viewBox="0 0 24 24" fill="currentColor"><path d="M6 19c0 1.1.9 2 2 2h8c1.1 0 2-.9 2-2V7H6v12zM19 4h-3.5l-1-1h-5l-1 1H5v2h14V4z"/></svg>
                  </button>
                </div>
                <textarea v-model="criterion.description" placeholder="Describe what this criterion evaluates..." rows="2" class="criterion-desc-input"></textarea>
                <div class="levels-edit-section">
                  <span class="levels-edit-label">Scoring Levels:</span>
                  <div class="levels-edit-list">
                    <div v-for="(level, lidx) in criterion.levels" :key="lidx" class="level-edit-item">
                      <input v-model="level.name" placeholder="Level name" class="level-name-input" />
                      <input v-model.number="level.points" type="number" placeholder="Pts" class="level-pts-input" />
                      <input v-model="level.description" placeholder="Description" class="level-desc-input" />
                      <button v-if="criterion.levels.length > 2" class="remove-level-btn" @click="criterion.levels.splice(lidx, 1)">&times;</button>
                    </div>
                  </div>
                  <button class="add-level-btn" @click="criterion.levels.push({ name: '', points: 0, description: '' })">+ Add Level</button>
                </div>
              </div>
            </div>
            <div v-else class="empty-rubric-msg">
              <p>No criteria yet. Click below to add one.</p>
            </div>
            <button class="btn-secondary add-criterion-btn" @click="addBlankCriterion">
              <svg width="18" height="18" viewBox="0 0 24 24" fill="currentColor"><path d="M19 13h-6v6h-2v-6H5v-2h6V5h2v6h6v2z"/></svg>
              Add Criterion
            </button>
          </div>

          <!-- Text / Paste Mode -->
          <div v-if="rubricMode === 'text'" class="rubric-text-mode">
            <div class="text-format-help">
              <strong>Format: one criterion per line</strong>
              <code>Criterion Name | Points | Description</code>
              <span class="format-example">Example:</span>
              <pre>Thesis Statement | 20 | Clear and well-defined thesis
Evidence & Analysis | 30 | Strong supporting evidence
Organization | 25 | Logical structure and flow
Grammar & Style | 25 | Correct grammar and punctuation</pre>
            </div>
            <textarea v-model="rubricText" placeholder="Paste or type your rubric here..." rows="10" class="rubric-textarea"></textarea>
            <button class="btn-secondary" @click="parseRubricFromText">
              <svg width="16" height="16" viewBox="0 0 24 24" fill="currentColor"><path d="M9 16.17L4.83 12l-1.42 1.41L9 19 21 7l-1.41-1.41z"/></svg>
              Parse &amp; Apply
            </button>
          </div>

          <!-- Upload File Mode -->
          <div v-if="rubricMode === 'upload'" class="rubric-upload-mode">
            <div class="upload-area" @dragover.prevent="dragOver = true" @dragleave="dragOver = false" @drop.prevent="handleFileDrop" :class="{ 'drag-over': dragOver }">
              <svg width="48" height="48" viewBox="0 0 24 24" fill="#5f6368"><path d="M9 16h6v-6h4l-7-7-7 7h4zm-4 2h14v2H5z"/></svg>
              <p>Drag & drop a file here, or click to browse</p>
              <span class="upload-formats">Supported: CSV, JSON, TXT, PDF, DOCX (PDF/DOCX parsed by AI)</span>
              <input type="file" ref="rubricFileInput" accept=".csv,.json,.txt,.pdf,.docx" @change="handleFileUpload" class="file-input-hidden" />
              <button class="btn-secondary" @click="rubricFileInput?.click()">Choose File</button>
            </div>
          </div>

          <!-- AI Generate Mode -->
          <div v-if="rubricMode === 'ai'" class="rubric-ai-mode">
            <div class="ai-mode-info">
              <svg width="24" height="24" viewBox="0 0 24 24" fill="#1a73e8"><path d="M19.36 10.04C18.67 6.59 15.64 4 12 4 9.11 4 6.6 5.64 5.35 8.04 2.34 8.36 0 10.91 0 14c0 3.31 2.69 6 6 6h13c2.76 0 5-2.24 5-5 0-2.64-2.05-4.78-4.64-4.96z"/></svg>
              <div>
                <strong>AI Rubric Generator</strong>
                <p>Paste your assignment instructions, rubric description, or any document text and AI will generate a structured rubric.</p>
              </div>
            </div>
            <textarea v-model="aiRubricInput" placeholder="Paste assignment instructions, rubric description, or any text...&#10;&#10;Example: Create a rubric for a 5-paragraph essay on climate change. Grade on thesis, evidence, analysis, organization, and grammar." rows="8" class="ai-rubric-textarea"></textarea>
            <button class="btn-primary ai-generate-btn" @click="generateRubricWithAI" :disabled="aiGenerating || !aiRubricInput.trim()">
              <svg v-if="!aiGenerating" width="18" height="18" viewBox="0 0 24 24" fill="currentColor"><path d="M19.36 10.04C18.67 6.59 15.64 4 12 4 9.11 4 6.6 5.64 5.35 8.04 2.34 8.36 0 10.91 0 14c0 3.31 2.69 6 6 6h13c2.76 0 5-2.24 5-5 0-2.64-2.05-4.78-4.64-4.96zM14 13v4h-4v-4H7l5-5 5 5h-3z"/></svg>
              {{ aiGenerating ? 'Generating rubric...' : 'Generate Rubric with AI' }}
            </button>
          </div>

          <!-- Status Message -->
          <div v-if="rubricMessage" :class="['rubric-status', rubricMessageSuccess ? 'success' : 'error']">
            {{ rubricMessage }}
          </div>

          <!-- Rubric Preview & Save -->
          <div v-if="rubricCriteria.length > 0" class="rubric-save-section">
            <div class="rubric-save-header">
              <span class="rubric-total-badge">Total: {{ editRubricTotal }} / {{ assignment?.points || 100 }} pts</span>
              <span v-if="editRubricTotal !== (assignment?.points || 100)" class="rubric-mismatch-warn">
                Points don't match assignment total
              </span>
            </div>
            <button class="btn-primary save-rubric-btn" @click="saveRubric" :disabled="savingRubric">
              {{ savingRubric ? 'Saving...' : 'Save Rubric' }}
            </button>
          </div>
        </div>
      </div>

      <!-- Settings Tab -->
      <div v-if="activeTab === 'settings'" class="tab-content">
        <div class="settings-card">
          <h3>Assignment Settings</h3>
          <div class="settings-grid">
            <div class="setting-item">
              <span class="setting-label">Late Submissions</span>
              <span class="setting-value">
                {{ assignment?.settings?.allow_late ? 'Allowed' : 'Not Allowed' }}
                <span v-if="assignment?.settings?.allow_late">
                  ({{ assignment?.settings?.late_penalty_percent }}% penalty/day)
                </span>
              </span>
            </div>
            <div class="setting-item">
              <span class="setting-label">Max Attempts</span>
              <span class="setting-value">{{ assignment?.settings?.max_attempts || 1 }}</span>
            </div>
            <div class="setting-item">
              <span class="setting-label">Plagiarism Threshold</span>
              <span class="setting-value">{{ assignment?.settings?.plagiarism_threshold }}%</span>
            </div>
            <div class="setting-item">
              <span class="setting-label">Face Check Interval</span>
              <span class="setting-value">
                {{ Math.round((assignment?.settings?.face_check_interval || 600000) / 60000) }} minutes
              </span>
            </div>
          </div>
        </div>

        <div class="danger-zone">
          <h3>Danger Zone</h3>
          <button 
            class="btn-danger"
            @click="deleteAssignment"
            :disabled="submissions.length > 0"
          >
            Delete Assignment
          </button>
          <p v-if="submissions.length > 0" class="warning-text">
            Cannot delete assignment with existing submissions
          </p>
        </div>
      </div>
    </main>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { useAssignments, useSubmissions, useClasses } from '@/composables/classroom'

const router = useRouter()
const route = useRoute()
const assignmentId = route.params.id

const { fetchAssignment, currentAssignment: assignment, publishAssignment, unpublishAssignment, deleteAssignment: removeAssignment, getAssignmentSubmissions, updateAssignment, parseRubricWithAI } = useAssignments()
const { bulkReturnSubmissions } = useSubmissions()
const { fetchClass } = useClasses()

const activeTab = ref('instructions')
const submissions = ref([])
const loading = ref(false)
const className = ref('')

// Rubric management state
const editingRubric = ref(false)
const rubricMode = ref('manual')
const rubricCriteria = ref([])
const rubricText = ref('')
const aiRubricInput = ref('')
const aiGenerating = ref(false)
const savingRubric = ref(false)
const rubricMessage = ref('')
const rubricMessageSuccess = ref(false)
const dragOver = ref(false)
const rubricFileInput = ref(null)

const rubricTotalPoints = computed(() => {
  if (!assignment.value?.rubric) return 0
  return assignment.value.rubric.reduce((sum, c) => sum + (c.points || 0), 0)
})

const editRubricTotal = computed(() => {
  return rubricCriteria.value.reduce((sum, c) => sum + (c.points || 0), 0)
})

const submissionStats = computed(() => {
  const total = submissions.value.length
  const submitted = submissions.value.filter(s => s.status !== 'draft').length
  const graded = submissions.value.filter(s => s.status === 'graded' || s.status === 'returned').length
  const returned = submissions.value.filter(s => s.status === 'returned').length
  const scores = submissions.value.filter(s => s.grade !== null).map(s => s.grade)
  const avgScore = scores.length > 0 
    ? Math.round(scores.reduce((a, b) => a + b, 0) / scores.length) 
    : null
  
  return { total, submitted, graded, returned, avgScore }
})

function formatDate(date) {
  if (!date) return '-'
  return new Date(date).toLocaleDateString('en-US', {
    month: 'short',
    day: 'numeric',
    year: 'numeric',
    hour: 'numeric',
    minute: '2-digit'
  })
}

function getInitials(name) {
  if (!name) return '?'
  return name.split(' ').map(n => n[0]).join('').toUpperCase().slice(0, 2)
}

function getTrustClass(score) {
  if (score >= 80) return 'high'
  if (score >= 60) return 'medium'
  return 'low'
}

function styloChipClass(verdict) {
  if (verdict === 'verified') return 'high'
  if (verdict === 'flagged') return 'low'
  return 'medium'
}

function styloChipText(verdict) {
  if (verdict === 'verified') return 'Match'
  if (verdict === 'flagged') return 'Flagged'
  if (verdict === 'review_required') return 'Review'
  if (verdict === 'inconclusive') return 'Inconclusive'
  return verdict
}

function aiChipClass(prob) {
  if (prob < 0.3) return 'high'
  if (prob < 0.6) return 'medium'
  return 'low'
}

function goBack() {
  if (assignment.value?.class_id) {
    router.push(`/teacher/class/${assignment.value.class_id}`)
  } else {
    router.back()
  }
}

function editAssignment() {
  router.push(`/teacher/assignment/${assignmentId}/edit`)
}

async function publish() {
  const result = await publishAssignment(assignmentId)
  if (result.success) {
    assignment.value.published = true
  } else {
    alert('Failed to publish: ' + (result.error || 'Unknown error'))
  }
}

async function unpublish() {
  const result = await unpublishAssignment(assignmentId)
  if (result.success) {
    assignment.value.published = false
  } else {
    alert('Failed to unpublish: ' + (result.error || 'Unknown error'))
  }
}

async function deleteAssignment() {
  if (!confirm('Are you sure you want to delete this assignment?')) return
  
  const result = await removeAssignment(assignmentId)
  if (result.success) {
    router.push(`/teacher/class/${assignment.value.class_id}`)
  }
}

function viewSubmission(sub) {
  router.push(`/teacher/submission/${sub.submission_id}`)
}

async function bulkReturn() {
  const gradedIds = submissions.value
    .filter(s => s.status === 'graded')
    .map(s => s.submission_id)
  
  if (gradedIds.length === 0) return
  
  const result = await bulkReturnSubmissions(gradedIds)
  if (result.success) {
    await loadSubmissions()
  }
}

async function loadSubmissions() {
  loading.value = true
  const result = await getAssignmentSubmissions(assignmentId)
  if (result.success) {
    // Backend returns {submissions: [...], total: N}
    submissions.value = result.data.submissions || result.data
  }
  loading.value = false
}

// ---- Rubric Management ----
function startEditRubric() {
  editingRubric.value = true
  rubricMode.value = 'manual'
  rubricMessage.value = ''
  // Deep copy existing rubric for editing
  rubricCriteria.value = JSON.parse(JSON.stringify(assignment.value?.rubric || []))
}

function cancelEditRubric() {
  editingRubric.value = false
  rubricCriteria.value = []
  rubricMessage.value = ''
}

function addBlankCriterion() {
  rubricCriteria.value.push({
    criteria_id: crypto.randomUUID(),
    name: '',
    description: '',
    points: 20,
    levels: [
      { name: 'Excellent', points: 20, description: '' },
      { name: 'Good', points: 15, description: '' },
      { name: 'Satisfactory', points: 10, description: '' },
      { name: 'Needs Improvement', points: 5, description: '' }
    ]
  })
}

function buildCriterionFromParsed(name, points, description) {
  return {
    criteria_id: crypto.randomUUID(),
    name,
    description,
    points,
    levels: [
      { name: 'Excellent', points: points, description: '' },
      { name: 'Good', points: Math.round(points * 0.75), description: '' },
      { name: 'Satisfactory', points: Math.round(points * 0.5), description: '' },
      { name: 'Needs Improvement', points: Math.round(points * 0.25), description: '' }
    ]
  }
}

function parseRubricFromText() {
  rubricMessage.value = ''
  const text = rubricText.value.trim()
  if (!text) {
    rubricMessage.value = 'Please enter rubric text first'
    rubricMessageSuccess.value = false
    return
  }
  const lines = text.split('\n').map(l => l.trim()).filter(l => l.length > 0)
  const parsed = []
  for (const line of lines) {
    if (line.toLowerCase().startsWith('name') && line.toLowerCase().includes('point')) continue
    if (line.startsWith('#') || line.startsWith('//')) continue
    const parts = line.split('|').map(p => p.trim())
    if (parts.length >= 2) {
      const name = parts[0]
      const points = parseInt(parts[1]) || 20
      const description = parts.length >= 3 ? parts[2] : ''
      if (name) parsed.push(buildCriterionFromParsed(name, points, description))
    } else {
      const commaParts = line.split(',').map(p => p.trim())
      if (commaParts.length >= 2 && !isNaN(parseInt(commaParts[1]))) {
        parsed.push(buildCriterionFromParsed(commaParts[0], parseInt(commaParts[1]) || 20, commaParts[2] || ''))
      } else if (line.length > 0) {
        parsed.push(buildCriterionFromParsed(line, 20, ''))
      }
    }
  }
  if (parsed.length === 0) {
    rubricMessage.value = 'Could not parse criteria. Use: Name | Points | Description'
    rubricMessageSuccess.value = false
    return
  }
  rubricCriteria.value = parsed
  rubricMode.value = 'manual'
  rubricMessage.value = `Parsed ${parsed.length} criteria`
  rubricMessageSuccess.value = true
}

function handleFileDrop(event) {
  dragOver.value = false
  const file = event.dataTransfer.files[0]
  if (file) processRubricFile(file)
}

function handleFileUpload(event) {
  const file = event.target.files[0]
  if (file) processRubricFile(file)
}

async function processRubricFile(file) {
  rubricMessage.value = ''
  rubricMessageSuccess.value = false
  const ext = file.name.split('.').pop().toLowerCase()
  
  // For PDF/DOCX/unknown, use AI to parse
  if (ext === 'pdf' || ext === 'docx' || ext === 'doc') {
    // Read as text (will be garbled for binary, but we send to AI which handles it)
    // For PDF, try to extract text first
    const reader = new FileReader()
    reader.onload = async (e) => {
      const text = e.target.result
      rubricMessage.value = 'Sending to AI for parsing...'
      const result = await parseRubricWithAI(text, file.name, assignment.value?.points || 100)
      if (result.success && result.data.rubric?.length > 0) {
        rubricCriteria.value = result.data.rubric
        rubricMode.value = 'manual'
        rubricMessage.value = `AI extracted ${result.data.criteria_count} criteria (${result.data.total_points} pts)`
        rubricMessageSuccess.value = true
      } else {
        rubricMessage.value = result.error || 'AI could not parse rubric from this file'
        rubricMessageSuccess.value = false
      }
    }
    reader.readAsText(file)
    return
  }
  
  // For CSV, JSON, TXT - parse locally
  const reader = new FileReader()
  reader.onload = (e) => {
    const content = e.target.result
    try {
      let parsed = []
      if (ext === 'json') {
        const data = JSON.parse(content)
        const items = Array.isArray(data) ? data : (data.rubric || data.criteria || [])
        parsed = items.map(item => buildCriterionFromParsed(
          item.name || item.criterion || item.title || 'Unnamed',
          parseInt(item.points || item.max_points || item.score) || 20,
          item.description || item.desc || ''
        ))
      } else if (ext === 'csv') {
        const lines = content.split('\n').map(l => l.trim()).filter(l => l.length > 0)
        const firstLine = lines[0]?.toLowerCase() || ''
        const startIdx = (firstLine.includes('name') || firstLine.includes('criterion')) ? 1 : 0
        for (let i = startIdx; i < lines.length; i++) {
          const parts = lines[i].match(/(".*?"|[^",\s]+)(?=\s*,|\s*$)/g) || lines[i].split(',')
          const cleaned = parts.map(p => p.replace(/^"|"$/g, '').trim())
          if (cleaned.length >= 2 && cleaned[0]) {
            parsed.push(buildCriterionFromParsed(cleaned[0], parseInt(cleaned[1]) || 20, cleaned[2] || ''))
          }
        }
      } else {
        // TXT - pipe or comma delimited
        const lines = content.split('\n').map(l => l.trim()).filter(l => l.length > 0)
        for (const line of lines) {
          if (line.startsWith('#') || line.startsWith('//')) continue
          const parts = line.split('|').map(p => p.trim())
          if (parts.length >= 2 && parts[0]) {
            parsed.push(buildCriterionFromParsed(parts[0], parseInt(parts[1]) || 20, parts[2] || ''))
          }
        }
      }
      if (parsed.length === 0) {
        rubricMessage.value = 'No criteria found. Check file format.'
        return
      }
      rubricCriteria.value = parsed
      rubricMode.value = 'manual'
      rubricMessage.value = `Imported ${parsed.length} criteria from ${file.name}`
      rubricMessageSuccess.value = true
    } catch (err) {
      rubricMessage.value = `Error parsing file: ${err.message}`
    }
  }
  reader.readAsText(file)
}

async function generateRubricWithAI() {
  aiGenerating.value = true
  rubricMessage.value = ''
  
  // Include assignment instructions for better context
  const contextText = `Assignment: ${assignment.value?.title || ''}\nInstructions: ${assignment.value?.instructions || ''}\n\nAdditional context from teacher:\n${aiRubricInput.value}`
  
  const result = await parseRubricWithAI(contextText, 'instructions.txt', assignment.value?.points || 100)
  aiGenerating.value = false
  
  if (result.success && result.data.rubric?.length > 0) {
    rubricCriteria.value = result.data.rubric
    rubricMode.value = 'manual'
    rubricMessage.value = `AI generated ${result.data.criteria_count} criteria (${result.data.total_points} pts)`
    rubricMessageSuccess.value = true
  } else {
    rubricMessage.value = result.error || 'AI generation failed. Try again.'
    rubricMessageSuccess.value = false
  }
}

async function saveRubric() {
  savingRubric.value = true
  rubricMessage.value = ''
  
  const result = await updateAssignment(assignmentId, {
    rubric: rubricCriteria.value
  })
  
  savingRubric.value = false
  
  if (result.success) {
    editingRubric.value = false
    rubricMessage.value = 'Rubric saved!'
    rubricMessageSuccess.value = true
    // Refresh assignment data
    await fetchAssignment(assignmentId)
  } else {
    rubricMessage.value = result.error || 'Failed to save rubric'
    rubricMessageSuccess.value = false
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
  
  await loadSubmissions()
})
</script>

<style scoped>
.assignment-detail-page {
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

.header-actions {
  display: flex;
  gap: 12px;
}

.btn-secondary {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 10px 20px;
  border: 1px solid #dadce0;
  background: white;
  border-radius: 8px;
  font-weight: 500;
  color: #5f6368;
  cursor: pointer;
}

.btn-secondary:hover {
  background: #f8f9fa;
}

.btn-primary {
  padding: 10px 24px;
  border: none;
  background: #1a73e8;
  color: white;
  font-weight: 500;
  border-radius: 8px;
  cursor: pointer;
}

.btn-primary:hover {
  background: #1557b0;
}

.btn-text {
  padding: 10px 20px;
  border: none;
  background: transparent;
  color: #5f6368;
  font-weight: 500;
  cursor: pointer;
  border-radius: 8px;
}

.btn-text:hover {
  background: #f1f3f4;
}

/* Tabs */
.tabs-nav {
  display: flex;
  gap: 8px;
  padding: 0 24px;
  background: white;
  border-bottom: 1px solid #e0e0e0;
}

.tab {
  padding: 16px 24px;
  border: none;
  background: transparent;
  font-size: 14px;
  font-weight: 500;
  color: #5f6368;
  cursor: pointer;
  position: relative;
  display: flex;
  align-items: center;
  gap: 8px;
}

.tab:hover {
  color: #1a73e8;
}

.tab.active {
  color: #1a73e8;
}

.tab.active::after {
  content: '';
  position: absolute;
  bottom: 0;
  left: 0;
  right: 0;
  height: 3px;
  background: #1a73e8;
  border-radius: 3px 3px 0 0;
}

.tab-badge {
  background: #e8f0fe;
  color: #1a73e8;
  padding: 2px 8px;
  border-radius: 12px;
  font-size: 12px;
}

/* Content */
.page-content {
  max-width: 1000px;
  margin: 0 auto;
  padding: 24px;
}

.tab-content {
  display: flex;
  flex-direction: column;
  gap: 20px;
}

/* Info Card */
.info-card {
  background: white;
  border-radius: 12px;
  padding: 20px;
}

.info-row {
  display: flex;
  gap: 40px;
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

.status-badge {
  display: inline-block;
  padding: 4px 12px;
  border-radius: 16px;
  font-size: 13px;
  font-weight: 500;
}

.status-badge.published {
  background: #e6f4ea;
  color: #1e8e3e;
}

.status-badge.draft {
  background: #fef7e0;
  color: #f9ab00;
}

.status-badge.submitted {
  background: #e8f0fe;
  color: #1a73e8;
}

.status-badge.graded {
  background: #fce8e6;
  color: #d93025;
}

.status-badge.returned {
  background: #e6f4ea;
  color: #1e8e3e;
}

/* Instructions */
.instructions-card,
.integrity-card {
  background: white;
  border-radius: 12px;
  padding: 24px;
}

.instructions-card h3,
.integrity-card h3 {
  font-size: 16px;
  font-weight: 500;
  margin: 0 0 16px;
  color: #202124;
}

.instructions-content {
  white-space: pre-wrap;
  line-height: 1.6;
  color: #3c4043;
}

.settings-list {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.setting-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 14px 16px;
  background: #f8f9fa;
  border-radius: 8px;
}

.setting-row .setting-label {
  font-size: 14px;
  font-weight: 500;
  color: #202124;
}

.setting-row .setting-value-text {
  font-weight: 600;
  color: #202124;
}

.setting-row .enabled {
  color: #1e8e3e;
  font-weight: 500;
}

.setting-row .disabled {
  color: #9aa0a6;
}

/* Submissions */
.submissions-header {
  background: white;
  border-radius: 12px;
  padding: 20px;
}

.stats-row {
  display: flex;
  gap: 40px;
  margin-bottom: 16px;
}

.stat-item {
  display: flex;
  flex-direction: column;
  align-items: center;
}

.stat-value {
  font-size: 28px;
  font-weight: 600;
  color: #202124;
}

.stat-label {
  font-size: 13px;
  color: #5f6368;
}

.submissions-list {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.submission-card {
  display: flex;
  justify-content: space-between;
  align-items: center;
  background: white;
  border-radius: 12px;
  padding: 16px 20px;
  cursor: pointer;
  transition: box-shadow 0.2s;
}

.submission-card:hover {
  box-shadow: 0 2px 8px rgba(0,0,0,0.1);
}

.student-info {
  display: flex;
  align-items: center;
  gap: 12px;
}

.avatar {
  width: 40px;
  height: 40px;
  border-radius: 50%;
  background: #1a73e8;
  color: white;
  display: flex;
  align-items: center;
  justify-content: center;
  font-weight: 500;
  font-size: 14px;
}

.student-details {
  display: flex;
  flex-direction: column;
}

.student-name {
  font-weight: 500;
  color: #202124;
}

.submitted-at {
  font-size: 13px;
  color: #5f6368;
}

.submission-meta {
  display: flex;
  align-items: center;
  gap: 24px;
}

.trust-score,
.plagiarism-score {
  display: flex;
  flex-direction: column;
  align-items: center;
}

.score-label {
  font-size: 11px;
  color: #5f6368;
}

.score-value {
  font-weight: 600;
}

.score-value.stylo-value {
  font-size: 12px;
}

.trust-score.high .score-value {
  color: #1e8e3e;
}

.trust-score.medium .score-value {
  color: #f9ab00;
}

.trust-score.low .score-value {
  color: #d93025;
}

.plagiarism-score .score-value {
  color: #d93025;
}

.grade-info .grade {
  font-weight: 600;
  color: #202124;
}

.grade-info .no-grade {
  color: #5f6368;
  font-size: 13px;
}

/* Rubric */
.rubric-view {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.criterion-card {
  background: white;
  border-radius: 12px;
  padding: 20px;
}

.criterion-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 8px;
}

.criterion-header h4 {
  margin: 0;
  font-size: 16px;
  color: #202124;
}

.criterion-points {
  font-weight: 600;
  color: #1a73e8;
}

.criterion-desc {
  color: #5f6368;
  margin: 0 0 16px;
}

.levels-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
  gap: 12px;
}

.level-card {
  background: #f8f9fa;
  border-radius: 8px;
  padding: 12px;
}

.level-header {
  display: flex;
  justify-content: space-between;
  margin-bottom: 8px;
}

.level-name {
  font-weight: 500;
  color: #202124;
}

.level-points {
  color: #1a73e8;
  font-weight: 500;
}

.level-desc {
  font-size: 13px;
  color: #5f6368;
  margin: 0;
}

/* Settings Tab */
.settings-card {
  background: white;
  border-radius: 12px;
  padding: 24px;
}

.settings-card h3 {
  margin: 0 0 20px;
  font-size: 18px;
  color: #202124;
}

.settings-grid {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 16px;
}

.setting-item {
  display: flex;
  flex-direction: column;
  gap: 4px;
  padding: 12px;
  background: #f8f9fa;
  border-radius: 8px;
}

.setting-label {
  font-size: 13px;
  color: #5f6368;
}

.setting-value {
  font-weight: 500;
  color: #202124;
}

.danger-zone {
  background: white;
  border-radius: 12px;
  padding: 24px;
  border: 1px solid #fce8e6;
}

.danger-zone h3 {
  margin: 0 0 16px;
  color: #d93025;
}

.btn-danger {
  padding: 10px 20px;
  border: none;
  background: #d93025;
  color: white;
  font-weight: 500;
  border-radius: 8px;
  cursor: pointer;
}

.btn-danger:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.warning-text {
  margin: 12px 0 0;
  font-size: 13px;
  color: #5f6368;
}

.empty-state {
  text-align: center;
  padding: 60px 20px;
  background: white;
  border-radius: 12px;
}

.empty-state p {
  color: #5f6368;
  margin-bottom: 16px;
}

.loading {
  text-align: center;
  padding: 40px;
  color: #5f6368;
}

/* ===== Rubric Editor ===== */
.rubric-view-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 16px;
}

.rubric-summary {
  display: flex;
  gap: 16px;
  align-items: center;
}

.rubric-count,
.rubric-total-pts {
  font-size: 14px;
  font-weight: 500;
  color: #5f6368;
  background: #f1f3f4;
  padding: 4px 12px;
  border-radius: 16px;
}

.rubric-editor {
  background: white;
  border-radius: 12px;
  padding: 24px;
}

.rubric-editor-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 20px;
}

.rubric-editor-header h3 {
  margin: 0;
  font-size: 18px;
  color: #202124;
}

/* Rubric Mode Tabs */
.rubric-mode-tabs {
  display: flex;
  gap: 4px;
  margin-bottom: 20px;
  background: #f1f3f4;
  border-radius: 8px;
  padding: 4px;
}

.mode-tab {
  flex: 1;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 6px;
  padding: 10px 12px;
  border: none;
  background: transparent;
  border-radius: 6px;
  font-size: 13px;
  font-weight: 500;
  color: #5f6368;
  cursor: pointer;
  transition: all 0.2s;
}

.mode-tab:hover:not(.active) {
  background: rgba(0, 0, 0, 0.04);
}

.mode-tab.active {
  background: white;
  color: #1a73e8;
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.1);
}

.mode-tab.ai-tab.active {
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  color: white;
}

/* Manual Mode */
.rubric-criteria-list {
  display: flex;
  flex-direction: column;
  gap: 16px;
  margin-bottom: 16px;
}

.criterion-edit-card {
  border: 1px solid #e0e0e0;
  border-radius: 8px;
  padding: 16px;
}

.criterion-edit-header {
  display: flex;
  gap: 10px;
  margin-bottom: 10px;
  align-items: center;
}

.criterion-name-input {
  flex: 1;
  font-weight: 500;
  padding: 10px 12px;
  border: 1px solid #dadce0;
  border-radius: 6px;
  font-size: 14px;
  color: #202124;
  background: white;
}

.criterion-pts-input {
  width: 80px;
  text-align: center;
  padding: 10px 8px;
  border: 1px solid #dadce0;
  border-radius: 6px;
  font-size: 14px;
}

.remove-criterion-btn {
  width: 36px;
  height: 36px;
  border: none;
  background: transparent;
  border-radius: 50%;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  color: #5f6368;
}

.remove-criterion-btn:hover {
  background: #fce8e6;
  color: #c5221f;
}

.criterion-desc-input {
  width: 100%;
  padding: 10px 12px;
  border: 1px solid #dadce0;
  border-radius: 6px;
  font-size: 13px;
  resize: vertical;
  box-sizing: border-box;
  margin-bottom: 10px;
}

.levels-edit-section {
  background: #f8f9fa;
  border-radius: 8px;
  padding: 12px;
}

.levels-edit-label {
  font-size: 12px;
  font-weight: 600;
  color: #5f6368;
  text-transform: uppercase;
  display: block;
  margin-bottom: 8px;
}

.levels-edit-list {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.level-edit-item {
  display: flex;
  gap: 8px;
  align-items: center;
}

.level-name-input {
  width: 120px;
  padding: 8px;
  border: 1px solid #dadce0;
  border-radius: 4px;
  font-size: 13px;
}

.level-pts-input {
  width: 60px;
  text-align: center;
  padding: 8px;
  border: 1px solid #dadce0;
  border-radius: 4px;
  font-size: 13px;
}

.level-desc-input {
  flex: 1;
  padding: 8px;
  border: 1px solid #dadce0;
  border-radius: 4px;
  font-size: 13px;
}

.remove-level-btn {
  width: 24px;
  height: 24px;
  border: none;
  background: transparent;
  cursor: pointer;
  color: #5f6368;
  font-size: 18px;
  border-radius: 50%;
}

.remove-level-btn:hover {
  background: #fce8e6;
  color: #c5221f;
}

.add-level-btn {
  margin-top: 8px;
  padding: 6px 12px;
  border: none;
  background: transparent;
  color: #1a73e8;
  font-size: 13px;
  cursor: pointer;
  font-weight: 500;
}

.empty-rubric-msg {
  text-align: center;
  padding: 40px 20px;
  background: #f8f9fa;
  border-radius: 8px;
  color: #5f6368;
  margin-bottom: 16px;
}

.add-criterion-btn {
  display: flex;
  align-items: center;
  gap: 8px;
  margin: 0 auto;
}

/* Text Mode */
.rubric-text-mode {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.text-format-help {
  background: #f8f9fa;
  border: 1px solid #e0e0e0;
  border-radius: 8px;
  padding: 16px;
  font-size: 13px;
  color: #5f6368;
}

.text-format-help strong {
  display: block;
  color: #202124;
  margin-bottom: 4px;
}

.text-format-help code {
  display: inline-block;
  background: #e8eaed;
  padding: 2px 8px;
  border-radius: 4px;
  font-size: 13px;
  color: #202124;
  margin: 4px 0;
}

.text-format-help .format-example {
  display: block;
  margin-top: 8px;
  font-size: 12px;
}

.text-format-help pre {
  background: #202124;
  color: #e8eaed;
  padding: 12px;
  border-radius: 6px;
  font-size: 12px;
  margin: 8px 0 0;
  white-space: pre-wrap;
}

.rubric-textarea,
.ai-rubric-textarea {
  width: 100%;
  padding: 16px;
  border: 2px solid #dadce0;
  border-radius: 8px;
  font-size: 14px;
  font-family: 'Roboto Mono', monospace;
  line-height: 1.6;
  box-sizing: border-box;
  resize: vertical;
  transition: border-color 0.2s;
}

.rubric-textarea:focus,
.ai-rubric-textarea:focus {
  outline: none;
  border-color: #1a73e8;
}

/* Upload Mode */
.rubric-upload-mode {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.upload-area {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 12px;
  padding: 40px 20px;
  border: 2px dashed #dadce0;
  border-radius: 12px;
  background: #fafafa;
  text-align: center;
  transition: all 0.2s;
  position: relative;
}

.upload-area.drag-over {
  border-color: #1a73e8;
  background: #e8f0fe;
}

.upload-area p {
  margin: 0;
  color: #5f6368;
}

.upload-formats {
  font-size: 12px;
  color: #80868b;
}

.file-input-hidden {
  position: absolute;
  width: 0;
  height: 0;
  opacity: 0;
}

/* AI Generate Mode */
.rubric-ai-mode {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.ai-mode-info {
  display: flex;
  gap: 12px;
  align-items: flex-start;
  padding: 16px;
  background: #e8f0fe;
  border-radius: 10px;
}

.ai-mode-info strong {
  display: block;
  color: #1a73e8;
  margin-bottom: 4px;
}

.ai-mode-info p {
  margin: 0;
  font-size: 13px;
  color: #5f6368;
  line-height: 1.4;
}

.ai-generate-btn {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  padding: 14px 24px;
  border: none;
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  color: white;
  font-weight: 600;
  border-radius: 8px;
  cursor: pointer;
  font-size: 14px;
}

.ai-generate-btn:hover:not(:disabled) {
  filter: brightness(1.1);
}

.ai-generate-btn:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}

/* Status & Save */
.rubric-status {
  padding: 12px 16px;
  border-radius: 8px;
  font-size: 14px;
  font-weight: 500;
  margin-top: 12px;
}

.rubric-status.success {
  background: #e6f4ea;
  color: #1e8e3e;
}

.rubric-status.error {
  background: #fce8e6;
  color: #d93025;
}

.rubric-save-section {
  margin-top: 20px;
  padding-top: 20px;
  border-top: 1px solid #e0e0e0;
}

.rubric-save-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 16px;
}

.rubric-total-badge {
  font-size: 16px;
  font-weight: 600;
  color: #1a73e8;
}

.rubric-mismatch-warn {
  font-size: 13px;
  color: #f9ab00;
  font-weight: 500;
}

.save-rubric-btn {
  width: 100%;
  padding: 14px;
  font-size: 15px;
}

.save-rubric-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.criterion-name-input:focus,
.criterion-pts-input:focus,
.criterion-desc-input:focus,
.level-name-input:focus,
.level-pts-input:focus,
.level-desc-input:focus {
  outline: none;
  border-color: #1a73e8;
}

/* Ensure all inputs/textareas have dark text on white background */
.criterion-pts-input,
.criterion-desc-input,
.level-name-input,
.level-pts-input,
.level-desc-input,
.rubric-textarea,
.ai-rubric-textarea {
  color: #202124;
  background: white;
}
</style>
