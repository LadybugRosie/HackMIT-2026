<template>
  <div class="grade-submission-page">
    <!-- Header -->
    <header class="page-header">
      <div class="header-left">
        <button @click="goBack" class="back-btn">
          <svg width="24" height="24" viewBox="0 0 24 24" fill="currentColor">
            <path d="M20 11H7.83l5.59-5.59L12 4l-8 8 8 8 1.41-1.41L7.83 13H20v-2z"/>
          </svg>
        </button>
        <div class="header-info">
          <h1>{{ submission?.student_name || 'Loading...' }}</h1>
          <span class="assignment-name">{{ assignmentTitle }}</span>
        </div>
      </div>
      <div class="header-actions">
        <button
          class="btn-playback"
          @click="$router.push(`/teacher/submission/${$route.params.id}/playback`)"
        >
          <svg width="16" height="16" viewBox="0 0 24 24" fill="currentColor" style="margin-right:4px;vertical-align:middle;">
            <path d="M8 5v14l11-7z"/>
          </svg>
          Session Playback
        </button>
        <button
          v-if="submission?.status === 'graded'"
          class="btn-primary"
          @click="returnSubmission"
        >
          Return to Student
        </button>
      </div>
    </header>

    <!-- Individual Integrity Signal Badges (trust / stylometry / AI) -->
    <div class="integrity-signals-section">
      <div class="trust-badge-container">
        <div v-if="toolEnabled.integrity" class="trust-badge" :class="typingTrustClass">
          <span class="trust-badge-value">{{ submission?.trust_score != null ? submission.trust_score + '%' : 'N/A' }}</span>
          <span class="trust-badge-label">Typing Trust</span>
        </div>
        <div v-if="toolEnabled.stylometry" class="trust-badge" :class="styloBadgeClass">
          <span class="trust-badge-value">{{ stylometryText }}</span>
          <span class="trust-badge-label">Stylometry</span>
        </div>
        <div v-if="toolEnabled.gptzero" class="trust-badge" :class="aiBadgeClass">
          <span class="trust-badge-value">{{ aiBadgeText }}</span>
          <span class="trust-badge-label">AI Detection</span>
        </div>
        <span v-if="toolEnabled.plagiarism && similarityPending" class="provisional-tag">
          Similarity pending
        </span>
        <button v-if="submission?.has_report" class="view-report-btn" @click="activeTab = 'report'">
          View Integrity Report
        </button>
      </div>

      <!-- Integrity signals: each shown independently (always expanded in new mode) -->
      <details class="integrity-details" :open="!integrityLegacyMode">
        <summary class="details-toggle">
          <svg width="16" height="16" viewBox="0 0 24 24" fill="currentColor">
            <path d="M12 8l-6 6 1.41 1.41L12 10.83l4.59 4.58L18 14z"/>
          </svg>
          {{ integrityLegacyMode ? 'View Integrity Details' : 'Integrity Signals' }}
        </summary>
        <div class="details-content">
          <!-- Content Authenticity (existing trust_score) -->
          <div v-if="toolEnabled.integrity" class="detail-row">
            <span class="detail-label">Content Authenticity</span>
            <span class="detail-value" :class="getTrustClass(submission?.trust_score)">
              {{ submission?.trust_score || 0 }}%
            </span>
            <span class="detail-desc">{{ typedPercent }}% typed, {{ pastedPercent }}% pasted</span>
          </div>

          <!-- Similarity -->
          <div v-if="toolEnabled.plagiarism" class="detail-row">
            <span class="detail-label">Similarity</span>
            <span v-if="similarityPending" class="detail-value pending">Pending</span>
            <span v-else class="detail-value" :class="getSimilarityClass(submission?.plagiarism_score)">
              {{ submission?.plagiarism_score || 0 }}%
            </span>
            <span class="detail-desc">
              {{ similarityPending ? 'Runs after deadline (peer comparison)' : 'Compared against all peer submissions' }}
            </span>
          </div>

          <!-- True AI Detector -->
          <div v-if="toolEnabled.gptzero" class="detail-row">
            <span class="detail-label">True AI Detector</span>
            <span class="detail-value" :class="aiDetectionClass">{{ aiDetectionText }}</span>
            <span class="detail-desc">
              {{ aiDetectionDesc }}
            </span>
          </div>

          <!-- Stylometry -->
          <div v-if="toolEnabled.stylometry" class="detail-row">
            <span class="detail-label">Authorship Check</span>
            <span class="detail-value" :class="stylometryClass">{{ stylometryText }}</span>
            <span class="detail-desc">
              {{ stylometryDesc }}
            </span>
          </div>

          <!-- Face Verification (if any) -->
          <div v-if="toolEnabled.face && submission?.face_verification_log?.length > 0" class="detail-row">
            <span class="detail-label">Face Verification</span>
            <span class="detail-value">
              {{ faceVerificationSummary }}
            </span>
            <div class="face-log-details">
              <div 
                v-for="(log, idx) in submission.face_verification_log" 
                :key="idx"
                :class="['face-log-item', log.result === 'verified' ? 'verified' : 'failed']"
              >
                <span>{{ formatTime(log.timestamp) }}</span>
                <span>{{ log.result === 'verified' ? 'Verified' : 'Failed' }}</span>
                <span v-if="log.confidence">{{ Math.round(log.confidence * 100) }}%</span>
              </div>
            </div>
          </div>

          <!-- Plagiarism Matches (if any) -->
          <div v-if="toolEnabled.plagiarism && submission?.plagiarism_matches?.length > 0" class="detail-row detail-row-wide">
            <span class="detail-label">Similarity Matches</span>
            <div class="matches-list">
              <div 
                v-for="(match, idx) in submission.plagiarism_matches" 
                :key="idx"
                class="match-item"
              >
                <div class="match-info">
                  <span class="match-source">{{ match.source_type || match.type || 'peer' }}</span>
                  <span class="match-percent">{{ match.similarity_score }}% match</span>
                </div>
                <div v-if="match.matched_text" class="matched-text">
                  "{{ match.matched_text.substring(0, 100) }}..."
                </div>
              </div>
            </div>
          </div>
        </div>
      </details>
    </div>

    <!-- Main Content -->
    <main class="page-content">
      <div class="content-grid">
        <!-- Left: Submission Content -->
        <div class="submission-panel">
          <!-- Tab Bar: Submitted Work | Integrity Report -->
          <div class="submission-tabs">
            <button 
              :class="['tab-btn', { active: activeTab === 'work' }]" 
              @click="activeTab = 'work'"
            >
              Submitted Work
            </button>
            <button
              :class="['tab-btn', { active: activeTab === 'report' }]"
              @click="activeTab = 'report'"
              :disabled="!submission?.has_report"
            >
              Integrity Report (PDF)
            </button>
            <button
              v-if="dossier"
              :class="['tab-btn', { active: activeTab === 'dossier' }]"
              @click="activeTab = 'dossier'"
            >
              Dossier
              <span v-if="dossier.cls !== 'good'" class="tab-badge" :class="dossier.cls">{{ dossier.label }}</span>
            </button>
            <button
              v-if="toolEnabled.plagiarism"
              :class="['tab-btn', { active: activeTab === 'plagiarism' }]"
              @click="activeTab = 'plagiarism'"
            >
              Plagiarism Analysis
              <span v-if="submission?.plagiarism_score > 0" class="tab-badge" :class="getSimilarityClass(submission.plagiarism_score)">
                {{ submission.plagiarism_score }}%
              </span>
            </button>
          </div>

          <!-- TAB 1: Submitted Work -->
          <div v-show="activeTab === 'work'">
            <!-- Submission Content with Inline Annotations -->
            <div class="content-section">
              <div class="content-header">
                <h3>Submitted Work</h3>
                <div v-if="annotations.length > 0" class="annotations-toggle">
                  <label class="toggle-label">
                    <input type="checkbox" v-model="showAnnotations" />
                    <span>Show Comments ({{ annotations.length }})</span>
                  </label>
                </div>
              </div>
              <div class="submission-content" :class="{ 'with-annotations': showAnnotations }">
                <div v-if="showAnnotations && annotations.length > 0" v-html="annotatedContent" class="annotated-text"></div>
                <div v-else-if="hasHtmlContent" v-html="sanitizedHtmlContent" class="rendered-html-content"></div>
                <pre v-else-if="plainContent">{{ plainContent }}</pre>
                <div v-else class="empty-content">No content submitted</div>
              </div>
              <!-- Annotation Legend -->
              <div v-if="showAnnotations && annotations.length > 0" class="annotation-legend">
                <div 
                  v-for="(ann, idx) in annotations" 
                  :key="idx" 
                  :class="['annotation-card', ann.type]"
                >
                  <div class="annotation-marker">
                    <span :class="['type-badge', ann.type]">
                      {{ ann.type === 'praise' ? 'Strength' : ann.type === 'issue' ? 'Issue' : 'Suggestion' }}
                    </span>
                  </div>
                  <div class="annotation-body">
                    <div class="annotation-quote">"{{ ann.highlighted_text }}"</div>
                    <div class="annotation-comment">{{ ann.comment }}</div>
                  </div>
                </div>
              </div>
              <div class="submission-meta">
                <span>Submitted: {{ formatDate(submission?.submitted_at) }}</span>
                <span>{{ submission?.word_count || 0 }} words</span>
                <span v-if="submission?.is_late" class="late-badge">Late Submission</span>
              </div>
            </div>
          </div>

          <!-- TAB 2: Integrity Report (Embedded PDF viewer) -->
          <div v-show="activeTab === 'report'" class="report-tab-content">
            <div v-if="submission?.has_report" class="embedded-report">
              <div class="report-actions-bar">
                <button class="report-action-btn" @click="viewReport">
                  <svg width="16" height="16" viewBox="0 0 24 24" fill="currentColor">
                    <path d="M19 19H5V5h7V3H5c-1.11 0-2 .9-2 2v14c0 1.1.89 2 2 2h14c1.1 0 2-.9 2-2v-7h-2v7zM14 3v2h3.59l-9.83 9.83 1.41 1.41L19 6.41V10h2V3h-7z"/>
                  </svg>
                  Open in New Tab
                </button>
                <button class="report-action-btn" @click="printReport">
                  <svg width="16" height="16" viewBox="0 0 24 24" fill="currentColor">
                    <path d="M19 8H5c-1.66 0-3 1.34-3 3v6h4v4h12v-4h4v-6c0-1.66-1.34-3-3-3zm-3 11H8v-5h8v5zm3-7c-.55 0-1-.45-1-1s.45-1 1-1 1 .45 1 1-.45 1-1 1zm-1-9H6v4h12V3z"/>
                  </svg>
                  Print Report
                </button>
              </div>
              <iframe
                :src="reportIframeSrc"
                class="embedded-report-iframe"
                scrolling="yes"
              ></iframe>
            </div>
            <div v-else class="no-report">
              <svg width="48" height="48" viewBox="0 0 24 24" fill="#9ca3af">
                <path d="M14 2H6c-1.1 0-1.99.9-1.99 2L4 20c0 1.1.89 2 1.99 2H18c1.1 0 2-.9 2-2V8l-6-6zm2 16H8v-2h8v2zm0-4H8v-2h8v2zm-3-5V3.5L18.5 9H13z"/>
              </svg>
              <p>No integrity report available for this submission.</p>
              <small>The student may have submitted before the report generation feature was added.</small>
            </div>
          </div>

          <!-- TAB: Dossier (authorship, plain English) -->
          <div v-show="activeTab === 'dossier'" class="dossier-tab-content">
            <div v-if="dossier" class="dossier">
              <div class="dossier-top">
                <div class="dossier-title">Authorship Check</div>
                <span class="dossier-verdict" :class="dossier.cls">{{ dossier.label }}</span>
              </div>
              <p class="dossier-note">A recommendation to help you decide. The system never accuses on its own; you make the final call.</p>

              <div class="drow">
                <div class="drow-k">Is it the student's own writing?</div>
                <div class="drow-v">{{ dossier.ownText }}</div>
                <div class="drow-score">{{ dossier.scoreText }}</div>
              </div>

              <div class="drow">
                <div class="drow-k">Was it written with AI?</div>
                <div class="drow-v">{{ dossier.aiText }} <span v-if="dossier.aiPct != null" class="drow-num">(AI score {{ dossier.aiPct }}%)</span></div>
              </div>

              <div class="drow">
                <div class="drow-k">Writing session</div>
                <div class="drow-v">
                  <button class="dossier-playback" @click="$router.push(`/teacher/submission/${$route.params.id}/playback`)">Watch how it was written</button>
                  <span class="drow-sub">See the keystrokes and any pasted text. Available only for essays written in the editor.</span>
                </div>
              </div>

              <div class="dossier-do">
                <div class="dossier-do-k">What to do</div>
                <div class="dossier-do-v">{{ dossier.rec }}</div>
              </div>
            </div>
            <div v-else class="no-report">
              <p>No authorship data for this submission yet.</p>
              <small>The student may not be enrolled in stylometry, or the check hasn't run.</small>
            </div>
          </div>

          <!-- TAB 3: Plagiarism Analysis -->
          <div v-show="activeTab === 'plagiarism'" class="plagiarism-tab-content">
            <!-- Run check button (if no results yet or teacher wants to re-run) -->
            <div class="plagiarism-actions-bar">
              <button
                class="btn-run-plagiarism"
                @click="runPlagiarismCheck"
                :disabled="runningPlagiarismCheck"
              >
                <svg v-if="!runningPlagiarismCheck" width="16" height="16" viewBox="0 0 24 24" fill="currentColor">
                  <path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm-2 14.5v-9l6 4.5-6 4.5z"/>
                </svg>
                <svg v-else width="16" height="16" viewBox="0 0 24 24" fill="currentColor" class="spin">
                  <path d="M12 4V1L8 5l4 4V6c3.31 0 6 2.69 6 6 0 1.01-.25 1.97-.7 2.8l1.46 1.46C19.54 15.03 20 13.57 20 12c0-4.42-3.58-8-8-8zm0 14c-3.31 0-6-2.69-6-6 0-1.01.25-1.97.7-2.8L5.24 7.74C4.46 8.97 4 10.43 4 12c0 4.42 3.58 8 8 8v3l4-4-4-4v3z"/>
                </svg>
                {{ runningPlagiarismCheck ? 'Checking...' : (hasPlagiarismResults ? 'Re-run Plagiarism Check' : 'Run Plagiarism Check') }}
              </button>
              <span v-if="submission?.plagiarism_v2_checked_at" class="plagiarism-checked-at">
                Last checked: {{ formatDate(submission.plagiarism_v2_checked_at) }}
              </span>
            </div>

            <!-- Show PlagiarismViewer when we have results -->
            <div v-if="hasPlagiarismResults" class="plagiarism-viewer-wrapper">
              <PlagiarismViewer
                :content="submission?.content || submission?.content_html || ''"
                :plagiarism-score="submission?.plagiarism_score || 0"
                :plagiarism-matches="submission?.plagiarism_matches || []"
              />
            </div>

            <!-- No results yet -->
            <div v-else-if="!runningPlagiarismCheck" class="no-plagiarism-results">
              <svg width="48" height="48" viewBox="0 0 24 24" fill="#9ca3af">
                <path d="M15.5 14h-.79l-.28-.27C15.41 12.59 16 11.11 16 9.5 16 5.91 13.09 3 9.5 3S3 5.91 3 9.5 5.91 16 9.5 16c1.61 0 3.09-.59 4.23-1.57l.27.28v.79l5 4.99L20.49 19l-4.99-5zm-6 0C7.01 14 5 11.99 5 9.5S7.01 5 9.5 5 14 7.01 14 9.5 11.99 14 9.5 14z"/>
              </svg>
              <p>No plagiarism check has been run yet</p>
              <small>Click "Run Plagiarism Check" to scan this submission against scholarly databases, web sources, and peer submissions.</small>
            </div>
          </div>

        </div>

        <!-- Right: Grading Panel -->
        <div class="grading-panel">
          <!-- Flagged Submission Warning -->
          <div v-if="submission?.auto_grade_suggestion?.flagged" class="flagged-submission-card">
            <div class="flagged-header">
              <svg width="24" height="24" viewBox="0 0 24 24" fill="currentColor">
                <path d="M14.4 6L14 4H5v17h2v-7h5.6l.4 2h7V6z"/>
              </svg>
              <h3>Needs Attention</h3>
            </div>
            <p class="flagged-reason">{{ submission.auto_grade_suggestion.flag_reason }}</p>
            <p v-if="submission.auto_grade_suggestion.integrity_notes" class="flagged-integrity">
              {{ submission.auto_grade_suggestion.integrity_notes }}
            </p>
          </div>

          <!-- Low Integrity Warning -->
          <div v-if="lowIntegrityWarning" class="low-trust-card">
            <div class="low-trust-header">
              <svg width="20" height="20" viewBox="0 0 24 24" fill="currentColor">
                <path d="M1 21h22L12 2 1 21zm12-3h-2v-2h2v2zm0-4h-2v-4h2v4z"/>
              </svg>
              <span>Manual Review Required</span>
            </div>
            <p>One or more integrity signals need attention. Please review the signals above carefully before grading.</p>
          </div>

          <!-- Suggested Grade Banner (shows when AI suggestion exists, pre-fills the form) -->
          <div v-if="hasSuggestion && !suggestionDismissed" class="suggested-grade-banner">
            <div class="suggestion-header">
              <span class="suggestion-label">Suggested Grade</span>
              <span class="suggestion-confidence">{{ Math.round((submission.auto_grade_suggestion.confidence || 0) * 100) }}% confidence</span>
            </div>
            <div class="suggestion-score-row">
              <span class="suggestion-score">{{ submission.auto_grade_suggestion.total_score }}/{{ maxPoints }}</span>
              <div class="suggestion-actions">
                <button class="btn-accept-return" @click="acceptAndReturn" :disabled="saving">
                  {{ saving ? 'Saving...' : 'Accept & Return' }}
                </button>
                <button class="btn-edit-grade" @click="editSuggestion">Edit</button>
                <button class="btn-dismiss-sm" @click="dismissAutoGrade">Dismiss</button>
              </div>
            </div>
            <div v-if="submission.auto_grade_suggestion.overall_feedback" class="suggestion-feedback-preview">
              {{ submission.auto_grade_suggestion.overall_feedback }}
            </div>
          </div>

          <!-- Grade Input -->
          <div class="grade-input-card">
            <h3>Grade</h3>
            <div class="grade-input-row">
              <input 
                v-model.number="gradeForm.grade" 
                type="number" 
                :max="maxPoints"
                min="0"
                class="grade-input"
              />
              <span class="grade-max">/ {{ maxPoints }}</span>
            </div>
            <div v-if="submission?.is_late && latePenalty > 0" class="late-penalty">
              <span>Late penalty applied: -{{ latePenalty }}%</span>
              <span>Adjusted: {{ adjustedGrade }}/{{ maxPoints }}</span>
            </div>
          </div>

          <!-- Rubric Scoring (auto-expanded when editing AI suggestion) -->
          <details v-if="rubric && rubric.length > 0" class="rubric-grading-details" :open="rubricExpanded">
            <summary class="rubric-summary" @click.prevent="rubricExpanded = !rubricExpanded">
              <h3>Rubric</h3>
              <span class="rubric-total-inline">{{ rubricTotal }}/{{ maxRubricPoints }}</span>
            </summary>
            <div class="rubric-grading">
              <div class="criteria-list">
                <div 
                  v-for="criterion in rubric" 
                  :key="criterion.criteria_id"
                  class="criterion-item"
                >
                  <div class="criterion-header">
                    <span class="criterion-name">{{ criterion.name }}</span>
                    <span class="criterion-max">{{ criterion.points }} pts</span>
                  </div>
                  <div v-if="criterionExplanations[criterion.criteria_id]" class="criterion-explanation">
                    {{ criterionExplanations[criterion.criteria_id] }}
                  </div>
                  <div class="levels-row">
                    <button
                      v-for="level in criterion.levels"
                      :key="level.name"
                      :class="['level-btn', { selected: rubricScores[criterion.criteria_id] === level.points }]"
                      @click="selectLevel(criterion.criteria_id, level.points)"
                    >
                      <span class="level-name">{{ level.name }}</span>
                      <span class="level-points">{{ level.points }}</span>
                    </button>
                  </div>
                </div>
              </div>
              <div class="rubric-total">
                <span>Rubric Total:</span>
                <span class="total-value">{{ rubricTotal }}/{{ maxRubricPoints }}</span>
              </div>
              <button class="btn-apply-rubric" @click="applyRubricScore">
                Use Rubric Total as Grade
              </button>
            </div>
          </details>

          <!-- Feedback -->
          <div class="feedback-card">
            <div class="feedback-header">
              <h3>Feedback</h3>
              <button 
                class="btn-ai-feedback" 
                @click="generateAIFeedback"
                :disabled="generatingFeedback || !gradeForm.grade"
                :title="!gradeForm.grade ? 'Set a grade first' : 'Generate feedback based on grade and submission'"
              >
                <svg width="14" height="14" viewBox="0 0 24 24" fill="currentColor">
                  <path d="M19 3H5c-1.1 0-2 .9-2 2v14c0 1.1.9 2 2 2h14c1.1 0 2-.9 2-2V5c0-1.1-.9-2-2-2zm-5 14H7v-2h7v2zm3-4H7v-2h10v2zm0-4H7V7h10v2z"/>
                </svg>
                {{ generatingFeedback ? 'Writing...' : 'Generate Feedback' }}
              </button>
            </div>
            <textarea 
              v-model="gradeForm.feedback"
              placeholder="Provide feedback for the student..."
              rows="6"
            ></textarea>
          </div>

          <!-- Re-run Grading (if applicable) -->
          <button 
            v-if="autoGradeEligible && hasRubric && submission?.status !== 'returned'"
            class="btn-rerun-ai" 
            @click="requestAutoGrade"
            :disabled="autoGrading"
          >
            <svg width="16" height="16" viewBox="0 0 24 24" fill="currentColor">
              <path d="M17.65 6.35C16.2 4.9 14.21 4 12 4c-4.42 0-7.99 3.58-7.99 8s3.57 8 7.99 8c3.73 0 6.84-2.55 7.73-6h-2.08c-.82 2.33-3.04 4-5.65 4-3.31 0-6-2.69-6-6s2.69-6 6-6c1.66 0 3.14.69 4.22 1.78L13 11h7V4l-2.35 2.35z"/>
            </svg>
            {{ autoGrading ? 'Analyzing...' : 'Re-analyze Submission' }}
          </button>

          <!-- Save Actions -->
          <div class="save-actions">
            <button 
              class="btn-save"
              @click="saveGrade"
              :disabled="saving"
            >
              {{ saving ? 'Saving...' : 'Save Grade' }}
            </button>
            <button 
              class="btn-save-return"
              @click="saveAndReturn"
              :disabled="saving"
            >
              Save & Return
            </button>
          </div>
        </div>
      </div>
    </main>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, watch } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import axios from 'axios'
import { useSubmissions, useAssignments } from '@/composables/classroom'
import { getApiUrl } from '@/utils/api-url'
import { integrityLegacyMode } from '@/composables/feature-flags'
import PlagiarismViewer from '@/components/PlagiarismViewer.vue'

const router = useRouter()
const route = useRoute()
const submissionId = route.params.id

const { 
  fetchSubmission, 
  currentSubmission: submission, 
  gradeSubmission, 
  returnSubmission: returnSub,
  requestAutoGrade: autoGrade,
  approveAutoGrade: approveAuto
} = useSubmissions()

const { fetchAssignment, currentAssignment } = useAssignments()

const saving = ref(false)
const autoGrading = ref(false)
const showAnnotations = ref(true)
const activeTab = ref('work')
const generatingFeedback = ref(false)
const rubricExpanded = ref(false)
const runningPlagiarismCheck = ref(false)

const gradeForm = ref({
  grade: 0,
  feedback: ''
})

const rubricScores = ref({})

// ============================================================
// BASIC COMPUTED PROPERTIES
// ============================================================
const assignmentTitle = computed(() => currentAssignment.value?.title || '')
const maxPoints = computed(() => currentAssignment.value?.points || 100)
const rubric = computed(() => currentAssignment.value?.rubric || [])
const hasRubric = computed(() => rubric.value.length > 0)
const latePenalty = computed(() => currentAssignment.value?.settings?.late_penalty_percent || 0)

// Integrity tool toggles from assignment settings (default true for backward compat)
const toolEnabled = computed(() => {
  const s = currentAssignment.value?.settings || {}
  return {
    integrity: s.analyze_integrity_enabled !== false,
    gptzero: s.gptzero_enabled !== false,
    stylometry: s.stylometry_enabled !== false,
    face: s.face_verification_enabled !== false,
    plagiarism: s.check_plagiarism !== false
  }
})

const maxRubricPoints = computed(() => {
  return rubric.value.reduce((sum, c) => sum + c.points, 0)
})

const rubricTotal = computed(() => {
  return Object.values(rubricScores.value).reduce((sum, score) => sum + score, 0)
})

const adjustedGrade = computed(() => {
  if (!submission.value?.is_late) return gradeForm.value.grade
  const penalty = latePenalty.value / 100
  return Math.round(gradeForm.value.grade * (1 - penalty))
})

// ============================================================
// INDIVIDUAL INTEGRITY SIGNAL COMPUTED PROPERTIES
// ============================================================
// Whether peer-similarity (plagiarism) has run — independent signal keyed on
// the batch-check timestamp server-side.
const similarityPending = computed(() => {
  const s = submission.value
  if (!s) return true
  return s.similarity_pending ?? true
})

// "Manual review" prompt: any individual signal out of range, or server flags.
const lowIntegrityWarning = computed(() => {
  const s = submission.value
  if (!s) return false
  return (s.integrity_flags?.length || 0) > 0
    || (s.trust_score != null && s.trust_score < 60)
    || stylometryClass.value === 'bad'
    || (s.ai_detection?.ai_probability != null && s.ai_detection.ai_probability >= 0.6)
})

// Badge classes for the three individual signal chips
const typingTrustClass = computed(() => {
  const score = submission.value?.trust_score
  if (score == null) return 'trust-na'
  if (score >= 80) return 'trust-high'
  if (score >= 60) return 'trust-medium'
  return 'trust-low'
})

const styloBadgeClass = computed(() => {
  const c = stylometryClass.value
  if (c === 'good') return 'trust-high'
  if (c === 'bad') return 'trust-low'
  if (c === 'warning') return 'trust-medium'
  return 'trust-na'
})

// Did AI detection actually produce a result? Anything without an explicit
// success is "not run" — including legacy rows whose failed runs were stored
// as {ai_probability: 0, predicted_class: 'unknown'} with no status field.
function aiDetectionRan(d) {
  if (!d) return false
  if (d.status && d.status !== 'success') return false
  const p = d.ai_probability
  if (p == null) return false
  if (p === 0 && (!d.predicted_class || d.predicted_class === 'skipped' || d.predicted_class === 'unknown')) return false
  return true
}

const aiBadgeClass = computed(() => {
  const d = submission.value?.ai_detection
  if (!aiDetectionRan(d)) return 'trust-na'
  const p = d.ai_probability
  if (p < 0.3) return 'trust-high'
  if (p < 0.6) return 'trust-medium'
  return 'trust-low'
})

const aiBadgeText = computed(() => {
  const d = submission.value?.ai_detection
  if (!aiDetectionRan(d)) return 'Not run'
  return `${Math.round(d.ai_probability * 100)}%`
})

// Auto-grade eligibility mirrors the server gate: trust >= 60, stylometry not
// flagged, AI probability < 0.6 (or not run).
const autoGradeEligible = computed(() => {
  const s = submission.value
  if (!s) return false
  const verdict = (s.stylometry_v3 || s.stylometry || {}).verdict
  const ai = s.ai_detection?.ai_probability
  return (s.trust_score ?? 0) >= 60
    && verdict !== 'flagged'
    && (ai == null || ai < 0.6)
})

// ============================================================
// INTEGRITY DETAIL COMPUTED PROPERTIES (for dropdown)
// ============================================================
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

const stylometryClass = computed(() => {
  const v3 = submission.value?.stylometry_v3
  const s = v3 || submission.value?.stylometry
  if (!s) return 'neutral'
  if (s.verdict === 'verified' || s.verified === true) return 'good'
  if (s.verdict === 'flagged' || s.verified === false) return 'bad'
  if (s.verdict === 'review_required') return 'warning'
  if (s.verdict === 'inconclusive') return 'neutral'
  return 'neutral'
})

const stylometryText = computed(() => {
  const v3 = submission.value?.stylometry_v3
  const s = v3 || submission.value?.stylometry
  if (!s) return 'Not Enrolled'
  if (s.verdict === 'verified' || s.verified === true) return 'Match'
  if (s.verdict === 'flagged' || s.verified === false) return 'Flagged'
  if (s.verdict === 'review_required') return 'Needs Review'
  if (s.verdict === 'inconclusive') return 'Inconclusive'
  if (s.status === 'skipped' || s.status === 'error') return 'Skipped'
  return 'Pending'
})

const stylometryDesc = computed(() => {
  const v3 = submission.value?.stylometry_v3
  const s = v3 || submission.value?.stylometry
  if (!s) return 'Student has not enrolled writing samples yet'
  const matchPct = v3 ? Math.round((v3.cosine_score ?? 0) * 100) : Math.round((s.score ?? s.similarity ?? 0) * 100)
  if (s.verdict === 'verified' || s.verified === true) return `Written by this student. ${matchPct}% style similarity`
  if (s.verdict === 'flagged' || s.verified === false) return `May not be this student's writing. ${matchPct}% style similarity`
  if (s.verdict === 'review_required') return `Could not confirm authorship. ${matchPct}% style similarity, manual review needed`
  if (s.verdict === 'inconclusive') return `Not enough data to confirm authorship. ${matchPct}% style similarity`
  return 'Authorship check was skipped or encountered an error'
})

const dossier = computed(() => {
  const s = submission.value?.stylometry_v3 || submission.value?.stylometry
  if (!s || !s.verdict) return null
  const ai = submission.value?.ai_detection || {}
  const name = submission.value?.student_name || 'this student'
  const cosinePct = Math.round((s.cosine_score ?? s.score ?? 0) * 100)
  const z = s.z_score != null ? (s.z_score).toFixed(2) : null
  const aiRan = aiDetectionRan(submission.value?.ai_detection)
  const aiPct = aiRan ? Math.round((ai.ai_probability ?? 0) * 100) : null
  const v = s.verdict
  const aiHigh = aiRan && aiPct >= 60
  const label = v === 'verified' ? 'Looks genuine' : v === 'flagged' ? 'Flagged' : v === 'review_required' ? 'Needs review' : 'Inconclusive'
  const cls = v === 'verified' ? 'good' : v === 'flagged' ? 'bad' : 'warning'
  // Honest wording: only claim what we can back up. We can tell AI reliably; we CANNOT
  // reliably tell "copied a classmate" from "outside help" on a shared prompt, so we don't.
  let ownText
  if (v === 'verified') ownText = `This reads like ${name}'s own writing.`
  else if (aiHigh) ownText = `This does not read like ${name}'s own writing.`
  else ownText = `We could not confirm this is ${name}'s own writing. It may be copied or written with outside help.`
  let aiText
  if (!aiRan) aiText = `AI detection did not run for this submission.`
  else if (aiPct < 30) aiText = `Likely written by a person.`
  else if (aiPct < 60) aiText = `Unclear. Could be a person, or partly AI.`
  else aiText = `Likely AI generated.`
  let scoreText
  if (z == null) scoreText = `Style match to their own writing: ${cosinePct}%.`
  else if (v === 'verified') scoreText = `Style match ${cosinePct}%, and it stands out as theirs (confidence ${z}, above the 1.7 we need to confirm).`
  else scoreText = `Style match ${cosinePct}%, but classmates score about the same on this shared prompt, so it does not stand out (confidence ${z}, below the 1.7 we need to confirm).`
  let rec
  if (v === 'verified') rec = `No action needed. This matches the student's own writing.`
  else if (aiHigh) rec = `This looks AI generated. Watch the writing session and ask the student how they wrote it. You make the final call.`
  else rec = `Review this one. Watch the writing session if available and ask the student about their process. You make the final call.`
  return { label, cls, cosinePct, z, aiPct, ownText, aiText, scoreText, rec }
})

const aiDetectionClass = computed(() => {
  const d = submission.value?.ai_detection
  if (!aiDetectionRan(d)) return 'neutral'
  const prob = d.ai_probability
  if (prob < 0.3) return 'good'
  if (prob < 0.6) return 'neutral'
  return 'bad'
})

const aiDetectionText = computed(() => {
  const d = submission.value?.ai_detection
  if (!aiDetectionRan(d)) return 'Not run'
  const pct = Math.round(d.ai_probability * 100)
  return `${pct}% AI probability`
})

const aiDetectionDesc = computed(() => {
  const d = submission.value?.ai_detection
  if (!aiDetectionRan(d)) {
    return 'AI detection was not run for this submission'
  }
  const prob = d.ai_probability
  const pct = Math.round(prob * 100)
  if (prob < 0.3) return `${pct}% AI detected — likely written by the student`
  if (prob < 0.6) return `${pct}% AI detected — some AI usage possible`
  return `${pct}% AI detected — likely AI-generated content`
})

const faceVerificationSummary = computed(() => {
  const logs = submission.value?.face_verification_log || []
  if (!logs.length) return 'None'
  const verified = logs.filter(l => l.result === 'verified').length
  return `${verified}/${logs.length} checks passed`
})

// ============================================================
// SUGGESTION PROPERTIES
// ============================================================
const suggestionDismissed = ref(false)

const hasSuggestion = computed(() => {
  return !!submission.value?.auto_grade_suggestion &&
    submission.value?.status !== 'returned'
})

const criterionExplanations = computed(() => {
  const scores = submission.value?.auto_grade_suggestion?.criteria_scores
  if (!scores) return {}
  const map = {}
  for (const cs of scores) {
    if (cs.criteria_id && cs.explanation) map[cs.criteria_id] = cs.explanation
  }
  return map
})

const hasPlagiarismResults = computed(() => {
  return (submission.value?.plagiarism_score > 0) || (submission.value?.plagiarism_matches?.length > 0)
})

const reportBlobUrl = ref('')
watch(() => submission.value?.has_report, async (hasReport) => {
  if (!hasReport) { reportBlobUrl.value = ''; return }
  try {
    const API = getApiUrl()
    const res = await axios.get(`${API}/api/submissions/${submissionId}/report`, { responseType: 'text' })
    const blob = new Blob([res.data], { type: 'text/html' })
    reportBlobUrl.value = URL.createObjectURL(blob)
  } catch { reportBlobUrl.value = '' }
}, { immediate: true })
const reportIframeSrc = computed(() => reportBlobUrl.value)

const annotations = computed(() => {
  const autoGradeSuggestion = submission.value?.auto_grade_suggestion
  if (!autoGradeSuggestion) return []
  return autoGradeSuggestion.inline_annotations || []
})

// ============================================================
// CONTENT DISPLAY
// ============================================================
function stripHtml(html) {
  if (!html) return ''
  let text = html
  for (const tag of ['</p>', '</div>', '</h1>', '</h2>', '</h3>', '</h4>', '<br>', '<br/>', '<br />']) {
    text = text.split(tag).join('\n')
  }
  let result = ''
  let inTag = false
  for (const ch of text) {
    if (ch === '<') inTag = true
    else if (ch === '>') inTag = false
    else if (!inTag) result += ch
  }
  const textarea = document.createElement('textarea')
  textarea.innerHTML = result
  result = textarea.value
  return result.split('\n').map(l => l.trim()).filter(l => l).join('\n')
}

const hasHtmlContent = computed(() => {
  const html = submission.value?.content_html || submission.value?.content || ''
  return html.includes('<') && html.includes('>')
})

const sanitizedHtmlContent = computed(() => {
  const html = submission.value?.content_html || submission.value?.content || ''
  if (!html) return ''
  return html.replace(/<script[^>]*>[\s\S]*?<\/script>/gi, '')
})

const plainContent = computed(() => {
  const content = submission.value?.content || submission.value?.content_html || ''
  if (!content) return ''
  return content.includes('<') ? stripHtml(content) : content
})

const annotatedContent = computed(() => {
  const content = plainContent.value
  if (!content || annotations.value.length === 0) return ''
  
  const segments = []
  for (const ann of annotations.value) {
    const idx = content.indexOf(ann.highlighted_text)
    if (idx !== -1) {
      segments.push({
        start: idx,
        end: idx + ann.highlighted_text.length,
        type: ann.type || 'suggestion',
        comment: ann.comment
      })
    }
  }
  
  segments.sort((a, b) => a.start - b.start)
  
  const clean = []
  let lastEnd = 0
  for (const seg of segments) {
    if (seg.start >= lastEnd) {
      clean.push(seg)
      lastEnd = seg.end
    }
  }
  
  let html = ''
  let pos = 0
  for (const seg of clean) {
    if (seg.start > pos) {
      html += escapeHtml(content.slice(pos, seg.start))
    }
    const tooltipText = escapeHtml(seg.comment)
    html += `<mark class="annotation-highlight annotation-${seg.type}" title="${tooltipText}">${escapeHtml(content.slice(seg.start, seg.end))}</mark>`
    pos = seg.end
  }
  if (pos < content.length) {
    html += escapeHtml(content.slice(pos))
  }
  
  return html
})

function escapeHtml(text) {
  return text
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/\n/g, '<br/>')
}

// ============================================================
// HELPER FUNCTIONS
// ============================================================
function getTrustClass(score) {
  if (score >= 80) return 'good'
  if (score >= 60) return 'neutral'
  return 'bad'
}

function getSimilarityClass(score) {
  if (score <= 15) return 'good'
  if (score <= 40) return 'neutral'
  return 'bad'
}

async function _fetchReportHtml() {
  const API = getApiUrl()
  const res = await axios.get(`${API}/api/submissions/${submissionId}/report`, { responseType: 'text' })
  return res.data
}

async function viewReport() {
  try {
    const html = await _fetchReportHtml()
    const blob = new Blob([html], { type: 'text/html' })
    window.open(URL.createObjectURL(blob), '_blank')
  } catch { alert('Failed to load report') }
}

async function printReport() {
  try {
    const html = await _fetchReportHtml()
    const blob = new Blob([html], { type: 'text/html' })
    const printWin = window.open(URL.createObjectURL(blob), '_blank')
    if (printWin) {
      printWin.addEventListener('load', () => {
        setTimeout(() => printWin.print(), 500)
      })
    }
  } catch { alert('Failed to load report') }
}

function formatDate(date) {
  if (!date) return '-'
  return new Date(date).toLocaleString()
}

function formatTime(timestamp) {
  if (!timestamp) return '-'
  return new Date(timestamp).toLocaleTimeString()
}

function goBack() {
  if (submission.value?.assignment_id) {
    router.push(`/teacher/assignment/${submission.value.assignment_id}`)
  } else {
    router.push('/teacher/dashboard')
  }
}

// ============================================================
// GRADING ACTIONS
// ============================================================
function selectLevel(criteriaId, points) {
  rubricScores.value[criteriaId] = points
}

function applyRubricScore() {
  const scaled = Math.round((rubricTotal.value / maxRubricPoints.value) * maxPoints.value)
  gradeForm.value.grade = scaled
}

function editSuggestion() {
  rubricExpanded.value = true
  suggestionDismissed.value = true
}

async function acceptAndReturn() {
  const result = await approveAuto(submissionId)
  if (result.success) {
    await returnSub(submissionId)
    if (submission.value?.assignment_id) {
      router.push(`/teacher/assignment/${submission.value.assignment_id}`)
    } else {
      router.push('/teacher/dashboard')
    }
  }
}

async function requestAutoGrade() {
  autoGrading.value = true
  const result = await autoGrade(submissionId)
  autoGrading.value = false
  
  if (result.success) {
    suggestionDismissed.value = false
    await fetchSubmission(submissionId)
    showAnnotations.value = true
  } else {
    alert('Auto-grading failed: ' + (result.error || 'Unknown error. Make sure the assignment has a rubric.'))
  }
}

async function approveAutoGrade() {
  const result = await approveAuto(submissionId)
  if (result.success) {
    suggestionDismissed.value = true
    await fetchSubmission(submissionId)
  }
}

function dismissAutoGrade() {
  suggestionDismissed.value = true
}

async function generateAIFeedback() {
  generatingFeedback.value = true
  const API = getApiUrl()
  
  let criteriaScores = null
  if (Object.keys(rubricScores.value).length > 0 && rubric.value.length > 0) {
    criteriaScores = Object.entries(rubricScores.value).map(([criteria_id, score]) => {
      const criterion = rubric.value.find(c => c.criteria_id === criteria_id)
      return {
        criteria_id,
        criteria_name: criterion?.name || '',
        score,
        max_score: criterion?.points || 0
      }
    })
  }
  
  try {
    const res = await axios.post(`${API}/api/submissions/${submissionId}/generate-feedback`, {
      grade: gradeForm.value.grade,
      max_grade: maxPoints.value,
      criteria_scores: criteriaScores
    })
    
    if (res.data.success && res.data.feedback) {
      if (gradeForm.value.feedback?.trim()) {
        gradeForm.value.feedback += '\n\n--- AI-Generated ---\n' + res.data.feedback
      } else {
        gradeForm.value.feedback = res.data.feedback
      }
    }
  } catch (e) {
    const detail = e.response?.data?.detail
    const errMsg = typeof detail === 'string' ? detail : (Array.isArray(detail) ? detail.map(err => err.msg || 'Error').join('; ') : 'Unknown error')
    alert('Failed to generate feedback: ' + errMsg)
  } finally {
    generatingFeedback.value = false
  }
}

async function runPlagiarismCheck() {
  runningPlagiarismCheck.value = true
  const API = getApiUrl()

  try {
    await axios.post(
      `${API}/api/plagiarism/check-submission/${submissionId}`,
      { check_internal: true, check_scholarly: true, check_web: true },
      { timeout: 120000 }
    )
    // Reload submission to get updated plagiarism data
    await fetchSubmission(submissionId)
  } catch (e) {
    const detail = e.response?.data?.detail
    const errMsg = typeof detail === 'string' ? detail : 'Plagiarism check failed. Please try again.'
    alert(errMsg)
  } finally {
    runningPlagiarismCheck.value = false
  }
}

async function saveGrade() {
  saving.value = true
  
  let criteriaScoresPayload = null
  if (Object.keys(rubricScores.value).length > 0 && rubric.value.length > 0) {
    criteriaScoresPayload = Object.entries(rubricScores.value).map(([criteria_id, score]) => {
      const criterion = rubric.value.find(c => c.criteria_id === criteria_id)
      const matchedLevel = criterion?.levels?.find(l => l.points === score)
      return {
        criteria_id,
        criteria_name: criterion?.name || '',
        score,
        max_score: criterion?.points || 0,
        level_name: matchedLevel?.name || '',
        explanation: matchedLevel?.description || ''
      }
    })
  }
  
  const result = await gradeSubmission(submissionId, {
    grade: gradeForm.value.grade,
    feedback: gradeForm.value.feedback,
    criteria_scores: criteriaScoresPayload
  })
  saving.value = false
  
  if (result.success) {
    await fetchSubmission(submissionId)
  }
}

async function saveAndReturn() {
  await saveGrade()
  await returnSubmission()
}

async function returnSubmission() {
  const result = await returnSub(submissionId)
  if (result.success) {
    if (submission.value?.assignment_id) {
      router.push(`/teacher/assignment/${submission.value.assignment_id}`)
    } else {
      router.push('/teacher/dashboard')
    }
  }
}

// ============================================================
// LIFECYCLE
// ============================================================
watch(submission, (newVal) => {
  if (newVal) {
    // If already graded, use existing grade
    if (newVal.grade) {
      gradeForm.value.grade = newVal.grade
      gradeForm.value.feedback = newVal.feedback || ''
      if (newVal.grade_breakdown) {
        newVal.grade_breakdown.forEach(rs => {
          rubricScores.value[rs.criteria_id] = rs.score
        })
      }
    }
    // Otherwise, auto-fill from AI suggestion so teacher just reviews
    else if (newVal.auto_grade_suggestion && !newVal.grade) {
      const s = newVal.auto_grade_suggestion
      gradeForm.value.grade = s.total_score || 0
      gradeForm.value.feedback = s.overall_feedback || ''
      if (s.criteria_scores) {
        for (const cs of s.criteria_scores) {
          if (cs.criteria_id) rubricScores.value[cs.criteria_id] = cs.score
        }
      }
    }
  }
})

onMounted(async () => {
  await fetchSubmission(submissionId)
  
  if (submission.value?.assignment_id) {
    await fetchAssignment(submission.value.assignment_id)
  }
})
</script>

<style scoped>
/* ============================================================ */
/* PAGE LAYOUT                                                   */
/* ============================================================ */
.grade-submission-page {
  height: 100vh;
  background: #f8f9fa;
  overflow: hidden;
  display: flex;
  flex-direction: column;
}

/* ============================================================ */
/* HEADER                                                        */
/* ============================================================ */
.page-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 12px 24px;
  background: white;
  border-bottom: 1px solid #e0e0e0;
  flex-shrink: 0;
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
.back-btn:hover { background: #f1f3f4; }

.header-info h1 {
  font-size: 20px;
  font-weight: 500;
  margin: 0;
  color: #202124;
}

.assignment-name {
  font-size: 14px;
  color: #5f6368;
}

.header-actions {
  display: flex;
  gap: 12px;
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
.btn-primary:hover { background: #1557b0; }
.btn-secondary {
  padding: 10px 24px;
  border: 1px solid #d1d5db;
  background: #fff;
  color: #374151;
  font-weight: 500;
  border-radius: 8px;
  cursor: pointer;
  display: inline-flex;
  align-items: center;
}
.btn-secondary:hover { background: #f3f4f6; }
.btn-playback {
  padding: 10px 24px;
  border: 1.5px solid #764ba2;
  background: #f5f0ff;
  color: #764ba2;
  font-weight: 600;
  border-radius: 8px;
  cursor: pointer;
  display: inline-flex;
  align-items: center;
}
.btn-playback:hover { background: #ede5ff; }

/* ============================================================ */
/* INDIVIDUAL INTEGRITY SIGNALS SECTION                          */
/* ============================================================ */
.integrity-signals-section {
  background: white;
  border-bottom: 1px solid #e0e0e0;
  padding: 16px 24px;
  flex-shrink: 0;
}

.trust-badge-container {
  display: flex;
  align-items: center;
  gap: 16px;
}

.trust-badge {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 8px 20px;
  border-radius: 24px;
  font-weight: 600;
}

.view-report-btn {
  padding: 8px 16px;
  background: #4f46e5;
  color: white;
  border: none;
  border-radius: 8px;
  font-size: 13px;
  font-weight: 600;
  cursor: pointer;
  transition: background 0.2s;
}
.view-report-btn:hover {
  background: #4338ca;
}

.trust-badge-value {
  font-size: 28px;
  font-weight: 700;
}

.trust-badge-label {
  font-size: 13px;
  font-weight: 500;
  opacity: 0.85;
}

.trust-badge.trust-high {
  background: #e6f4ea;
  color: #1e8e3e;
}

.trust-badge.trust-medium {
  background: #fef7e0;
  color: #e37400;
}

.trust-badge.trust-low {
  background: #fce8e6;
  color: #d93025;
}

.trust-badge.trust-na {
  background: #f3f4f6;
  color: #6b7280;
}

.provisional-tag {
  font-size: 12px;
  color: #5f6368;
  background: #f1f3f4;
  padding: 4px 10px;
  border-radius: 12px;
  font-weight: 500;
}

/* Expandable Integrity Details */
.integrity-details {
  margin-top: 12px;
}

.details-toggle {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 13px;
  font-weight: 500;
  color: #5f6368;
  cursor: pointer;
  list-style: none;
  user-select: none;
}
.details-toggle::-webkit-details-marker { display: none; }
.details-toggle svg {
  transition: transform 0.2s;
  transform: rotate(180deg);
}
.integrity-details[open] .details-toggle svg {
  transform: rotate(0deg);
}

.details-content {
  display: flex;
  flex-direction: column;
  gap: 12px;
  margin-top: 12px;
  padding: 16px;
  background: #f8f9fa;
  border-radius: 10px;
}

.detail-row {
  display: grid;
  grid-template-columns: 160px 140px 1fr;
  align-items: center;
  gap: 12px;
  font-size: 13px;
}

.detail-row-wide {
  grid-template-columns: 160px 1fr;
}

.detail-label {
  font-weight: 600;
  color: #5f6368;
}

.detail-value {
  font-weight: 600;
  padding: 2px 10px;
  border-radius: 6px;
  display: inline-block;
  text-align: center;
}

.detail-value.good { background: #e6f4ea; color: #1e8e3e; }
.detail-value.neutral { background: #fef7e0; color: #e37400; }
.detail-value.bad { background: #fce8e6; color: #d93025; }
.detail-value.pending { background: #f1f3f4; color: #5f6368; }

.detail-desc {
  color: #80868b;
  font-size: 12px;
}

/* Face Verification in details */
.face-log-details {
  grid-column: 2 / -1;
  display: flex;
  flex-direction: column;
  gap: 4px;
  margin-top: 4px;
}

.face-log-item {
  display: flex;
  gap: 12px;
  padding: 4px 10px;
  border-radius: 6px;
  font-size: 12px;
}
.face-log-item.verified { background: #e6f4ea; color: #1e8e3e; }
.face-log-item.failed { background: #fce8e6; color: #d93025; }

/* Similarity matches in details */
.matches-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
  margin-top: 4px;
}

.match-item {
  background: #fce8e6;
  border-radius: 8px;
  padding: 10px 12px;
}

.match-info {
  display: flex;
  justify-content: space-between;
  margin-bottom: 6px;
}

.match-source { font-weight: 500; color: #d93025; font-size: 12px; }
.match-percent { color: #d93025; font-weight: 600; font-size: 12px; }
.matched-text { font-size: 12px; color: #5f6368; font-style: italic; }

/* ============================================================ */
/* CONTENT GRID                                                  */
/* ============================================================ */
.page-content {
  padding: 20px 24px;
  flex: 1;
  overflow: hidden;
}

.content-grid {
  display: grid;
  grid-template-columns: 1fr 380px;
  gap: 20px;
  max-width: 1400px;
  margin: 0 auto;
  height: 100%;
}

/* ============================================================ */
/* SUBMISSION PANEL (LEFT)                                       */
/* ============================================================ */
.submission-panel {
  display: flex;
  flex-direction: column;
  overflow-y: auto;
  padding-right: 4px;
}

/* Tabs */
.submission-tabs {
  display: flex;
  background: white;
  border-radius: 12px 12px 0 0;
  border-bottom: 2px solid #e8eaed;
  overflow: hidden;
}

.tab-btn {
  flex: 1;
  padding: 14px 20px;
  border: none;
  background: transparent;
  font-weight: 600;
  font-size: 14px;
  color: #5f6368;
  cursor: pointer;
  transition: all 0.2s;
  position: relative;
}
.tab-btn.active { color: #1a73e8; background: #f0f4ff; }
.tab-btn.active::after {
  content: '';
  position: absolute;
  bottom: -2px; left: 0; right: 0;
  height: 2px;
  background: #1a73e8;
}
.tab-btn:hover:not(.active):not(:disabled) { background: #f8f9fa; }
.tab-btn:disabled { opacity: 0.4; cursor: not-allowed; }

/* Dossier tab */
.dossier-tab-content { padding: 4px 2px 8px; }
.dossier-top { display: flex; align-items: center; justify-content: space-between; gap: 12px; }
.dossier-title { font-size: 20px; font-weight: 700; color: #202124; }
.dossier-verdict { font-size: 13px; font-weight: 700; padding: 6px 14px; border-radius: 999px; white-space: nowrap; }
.dossier-verdict.good { background: #e6f4ea; color: #1e8e3e; }
.dossier-verdict.warning { background: #fef7e0; color: #e37400; }
.dossier-verdict.bad { background: #fce8e6; color: #d93025; }
.dossier-note { color: #5f6368; font-size: 13px; margin: 6px 0; }
.drow { padding: 16px 0; border-top: 1px solid #eceef0; }
.drow-k { font-size: 12px; font-weight: 600; color: #80868b; text-transform: uppercase; letter-spacing: .5px; }
.drow-v { font-size: 15px; color: #202124; margin-top: 6px; line-height: 1.5; }
.drow-num { color: #80868b; font-weight: 600; font-size: 13px; }
.drow-sub { display: block; color: #80868b; font-size: 12px; margin-top: 6px; }
.drow-score { margin-top: 8px; font-size: 13px; color: #3c4043; }
.drow-score b { color: #1a73e8; }
.dossier-playback { background: #f3eeff; color: #6b3fd4; border: 1px solid #d9caff; border-radius: 8px; padding: 8px 16px; font-size: 13px; font-weight: 600; cursor: pointer; }
.dossier-playback:hover { background: #ede5ff; }
.dossier-do { margin-top: 18px; background: #e8f0fe; border: 1px solid #d2e3fc; border-radius: 12px; padding: 14px 18px; }
.dossier-do-k { font-size: 12px; font-weight: 700; color: #1967d2; text-transform: uppercase; letter-spacing: .5px; margin-bottom: 5px; }
.dossier-do-v { color: #202124; font-size: 15px; line-height: 1.5; }
.tab-badge.good { background: #e6f4ea; color: #1e8e3e; }
.tab-badge.warning { background: #fef7e0; color: #e37400; }
.tab-badge.bad { background: #fce8e6; color: #d93025; }

/* Report tab */
.report-tab-content {
  background: white;
  border-radius: 0 0 12px 12px;
  overflow: hidden;
}
.embedded-report {
  display: flex;
  flex-direction: column;
  height: calc(100vh - 260px);
}
.report-actions-bar {
  display: flex;
  gap: 8px;
  padding: 10px 16px;
  background: #f8f9fa;
  border-bottom: 1px solid #e8eaed;
}
.report-action-btn {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 8px 14px;
  border: 1px solid #dadce0;
  background: white;
  border-radius: 6px;
  font-size: 13px;
  font-weight: 500;
  color: #5f6368;
  cursor: pointer;
  transition: all 0.15s;
}
.report-action-btn:hover { background: #f0f4ff; color: #1a73e8; border-color: #1a73e8; }
.embedded-report-iframe {
  flex: 1;
  width: 100%;
  border: none;
  min-height: 600px;
  overflow: auto;
}
.no-report {
  padding: 60px 24px;
  text-align: center;
  color: #9ca3af;
}
.no-report p { margin: 16px 0 4px; font-size: 16px; color: #6b7280; }
.no-report small { font-size: 13px; }

/* Content section */
.content-section {
  background: white;
  border-radius: 0 0 12px 12px;
  padding: 24px;
}

.content-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 16px;
}
.content-header h3 { margin: 0; font-size: 18px; color: #202124; }

.annotations-toggle { display: flex; align-items: center; }
.toggle-label {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 13px;
  font-weight: 500;
  color: #5f6368;
  cursor: pointer;
}
.toggle-label input[type="checkbox"] { width: 16px; height: 16px; cursor: pointer; }

.submission-content {
  background: #f8f9fa;
  border-radius: 8px;
  padding: 20px;
  max-height: 500px;
  overflow-y: auto;
}
.submission-content pre {
  margin: 0;
  white-space: pre-wrap;
  font-family: inherit;
  line-height: 1.6;
}

.rendered-html-content {
  line-height: 1.6;
  font-size: 14px;
  color: #202124 !important;
  word-wrap: break-word;
}
.rendered-html-content * { color: #202124 !important; }
.rendered-html-content a { color: #1a73e8 !important; }
.rendered-html-content mark, .rendered-html-content .highlight { color: inherit !important; }
.rendered-html-content img { max-width: 100%; height: auto; border-radius: 4px; margin: 8px 0; }
.rendered-html-content p { margin: 0 0 8px; }
.rendered-html-content h1, .rendered-html-content h2, .rendered-html-content h3 { margin: 16px 0 8px; }

.empty-content {
  color: #9ca3af;
  font-style: italic;
  padding: 20px;
  text-align: center;
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

/* Annotations */
.annotated-text {
  white-space: pre-wrap;
  line-height: 1.8;
  font-family: inherit;
  font-size: 14px;
}

.annotation-highlight {
  padding: 2px 4px;
  border-radius: 3px;
  cursor: pointer;
  position: relative;
  transition: all 0.2s;
}
.annotation-highlight:hover { filter: brightness(0.95); }
.annotation-praise { background: rgba(30, 142, 62, 0.15); border-bottom: 2px solid #1e8e3e; }
.annotation-suggestion { background: rgba(249, 171, 0, 0.15); border-bottom: 2px solid #f9ab00; }
.annotation-issue { background: rgba(217, 48, 37, 0.15); border-bottom: 2px solid #d93025; }

.annotation-legend {
  display: flex;
  flex-direction: column;
  gap: 10px;
  margin-top: 16px;
  padding-top: 16px;
  border-top: 1px solid #e0e0e0;
}

.annotation-card {
  display: flex;
  gap: 12px;
  padding: 12px;
  border-radius: 8px;
  border-left: 3px solid;
}
.annotation-card.praise { background: #e6f4ea; border-left-color: #1e8e3e; }
.annotation-card.suggestion { background: #fef7e0; border-left-color: #f9ab00; }
.annotation-card.issue { background: #fce8e6; border-left-color: #d93025; }

.type-badge {
  display: inline-block;
  padding: 2px 8px;
  border-radius: 10px;
  font-size: 11px;
  font-weight: 600;
  text-transform: uppercase;
  white-space: nowrap;
}
.type-badge.praise { background: #1e8e3e; color: white; }
.type-badge.suggestion { background: #f9ab00; color: white; }
.type-badge.issue { background: #d93025; color: white; }

.annotation-body { flex: 1; }
.annotation-quote { font-size: 13px; color: #5f6368; font-style: italic; margin-bottom: 4px; }
.annotation-comment { font-size: 14px; color: #202124; line-height: 1.4; }

/* ============================================================ */
/* GRADING PANEL (RIGHT)                                         */
/* ============================================================ */
.grading-panel {
  display: flex;
  flex-direction: column;
  gap: 14px;
  overflow-y: auto;
  padding-right: 4px;
}

/* Flagged Submission Card */
.flagged-submission-card {
  background: #fef2f2;
  border: 2px solid #fca5a5;
  border-radius: 12px;
  padding: 16px;
}
.flagged-header {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-bottom: 10px;
  color: #dc2626;
}
.flagged-header h3 { margin: 0; font-size: 15px; color: #dc2626; }
.flagged-reason { margin: 0 0 6px; font-size: 13px; color: #991b1b; line-height: 1.5; font-weight: 500; }
.flagged-integrity { margin: 0; font-size: 12px; color: #6b7280; line-height: 1.4; padding-top: 8px; border-top: 1px solid #fecaca; }

/* Low Trust Warning Card */
.low-trust-card {
  background: #fef2f2;
  border: 1px solid #fca5a5;
  border-radius: 12px;
  padding: 16px;
}
.low-trust-header {
  display: flex;
  align-items: center;
  gap: 8px;
  font-weight: 600;
  color: #d93025;
  margin-bottom: 8px;
  font-size: 14px;
}
.low-trust-card p {
  margin: 0;
  font-size: 13px;
  color: #5f6368;
  line-height: 1.5;
}

/* Suggested Grade Banner */
.suggested-grade-banner {
  background: white;
  border: 2px solid #667eea;
  border-radius: 12px;
  padding: 16px;
}
.suggestion-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 10px;
}
.suggestion-label {
  font-size: 13px;
  font-weight: 600;
  color: #667eea;
  text-transform: uppercase;
  letter-spacing: 0.5px;
}
.suggestion-confidence {
  font-size: 12px;
  color: #9ca3af;
  background: #f3f4f6;
  padding: 3px 10px;
  border-radius: 10px;
}
.suggestion-score-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 10px;
}
.suggestion-score {
  font-size: 32px;
  font-weight: 700;
  color: #202124;
}
.suggestion-actions {
  display: flex;
  gap: 6px;
}
.btn-accept-return {
  padding: 8px 16px;
  background: #667eea;
  color: white;
  border: none;
  border-radius: 8px;
  font-weight: 600;
  font-size: 13px;
  cursor: pointer;
}
.btn-accept-return:hover:not(:disabled) { background: #5568d3; }
.btn-accept-return:disabled { opacity: 0.5; cursor: not-allowed; }
.btn-edit-grade {
  padding: 8px 12px;
  background: white;
  color: #667eea;
  border: 1px solid #667eea;
  border-radius: 8px;
  font-weight: 500;
  font-size: 13px;
  cursor: pointer;
}
.btn-edit-grade:hover { background: #f0f0ff; }
.btn-dismiss-sm {
  padding: 8px 10px;
  background: transparent;
  color: #9ca3af;
  border: none;
  font-size: 12px;
  cursor: pointer;
}
.btn-dismiss-sm:hover { color: #6b7280; }
.suggestion-feedback-preview {
  font-size: 13px;
  color: #5f6368;
  line-height: 1.5;
  border-top: 1px solid #e5e7eb;
  padding-top: 10px;
}
.criterion-explanation {
  font-size: 12px;
  color: #667eea;
  margin-bottom: 6px;
  line-height: 1.4;
  font-style: italic;
}

/* Grade Input Card */
.grade-input-card, .feedback-card {
  background: white;
  border-radius: 12px;
  padding: 18px;
}
.grade-input-card h3, .feedback-card h3 {
  margin: 0 0 14px;
  font-size: 15px;
  color: #202124;
}

.grade-input-row {
  display: flex;
  align-items: baseline;
  gap: 8px;
}
.grade-input {
  width: 100px;
  font-size: 32px;
  font-weight: 600;
  padding: 8px 12px;
  border: 2px solid #dadce0;
  border-radius: 8px;
  text-align: center;
  color: #202124;
  background: white;
}
.grade-input:focus { outline: none; border-color: #1a73e8; }
.grade-input-row .grade-max { font-size: 24px; color: #5f6368; }

.late-penalty {
  margin-top: 12px;
  padding: 10px 12px;
  background: #fef7e0;
  border-radius: 8px;
  font-size: 13px;
  color: #f9ab00;
  display: flex;
  justify-content: space-between;
}

/* Rubric Grading (collapsible) */
.rubric-grading-details {
  background: white;
  border-radius: 12px;
  overflow: hidden;
}
.rubric-summary {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 18px;
  cursor: pointer;
  list-style: none;
  user-select: none;
}
.rubric-summary::-webkit-details-marker { display: none; }
.rubric-summary h3 { margin: 0; font-size: 15px; color: #202124; }
.rubric-total-inline { font-weight: 600; color: #1a73e8; font-size: 14px; }

.rubric-grading {
  padding: 0 18px 18px;
}
.criteria-list {
  display: flex;
  flex-direction: column;
  gap: 14px;
  max-height: 350px;
  overflow-y: auto;
  padding-right: 4px;
}
.criterion-item {
  border: 1px solid #e0e0e0;
  border-radius: 8px;
  padding: 12px;
}
.criterion-header {
  display: flex;
  justify-content: space-between;
  margin-bottom: 10px;
}
.criterion-name { font-weight: 500; color: #202124; }
.criterion-max { color: #5f6368; }

.levels-row {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
}
.level-btn {
  flex: 1;
  min-width: 65px;
  padding: 8px;
  border: 1px solid #dadce0;
  border-radius: 6px;
  background: white;
  cursor: pointer;
  text-align: center;
}
.level-btn:hover { background: #f8f9fa; }
.level-btn.selected { background: #e8f0fe; border-color: #1a73e8; }
.level-name { display: block; font-size: 11px; color: #5f6368; }
.level-points { display: block; font-weight: 600; color: #202124; }
.level-btn.selected .level-points { color: #1a73e8; }

.rubric-total {
  display: flex;
  justify-content: space-between;
  margin-top: 14px;
  padding: 10px 12px;
  background: #f8f9fa;
  border-radius: 8px;
  font-weight: 500;
}
.total-value { color: #1a73e8; }

.btn-apply-rubric {
  width: 100%;
  margin-top: 10px;
  padding: 10px;
  border: 1px solid #1a73e8;
  background: white;
  color: #1a73e8;
  border-radius: 8px;
  font-weight: 500;
  cursor: pointer;
}
.btn-apply-rubric:hover { background: #e8f0fe; }

/* Feedback */
.feedback-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 12px;
}
.feedback-header h3 { margin: 0; }

.btn-ai-feedback {
  display: flex;
  align-items: center;
  gap: 5px;
  padding: 6px 12px;
  border: 1px solid #667eea;
  background: #f0f0ff;
  color: #667eea;
  border-radius: 6px;
  font-size: 12px;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.15s;
}
.btn-ai-feedback:hover:not(:disabled) { background: #667eea; color: white; }
.btn-ai-feedback:disabled { opacity: 0.4; cursor: not-allowed; }

.feedback-card textarea {
  width: 100%;
  padding: 12px;
  border: 1px solid #dadce0;
  border-radius: 8px;
  font-size: 14px;
  resize: vertical;
  box-sizing: border-box;
  color: #202124;
  background: white;
}
.feedback-card textarea:focus { outline: none; border-color: #1a73e8; }

/* Re-run AI button */
.btn-rerun-ai {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  width: 100%;
  padding: 10px;
  border: 1px solid #667eea;
  background: #f8f8ff;
  color: #667eea;
  border-radius: 8px;
  font-weight: 500;
  font-size: 13px;
  cursor: pointer;
  transition: all 0.15s;
}
.btn-rerun-ai:hover:not(:disabled) { background: #667eea; color: white; }
.btn-rerun-ai:disabled { opacity: 0.5; cursor: not-allowed; }

/* Save Actions */
.save-actions {
  display: flex;
  gap: 12px;
}
.btn-save, .btn-save-return {
  flex: 1;
  padding: 14px;
  border: none;
  border-radius: 8px;
  font-weight: 500;
  cursor: pointer;
}
.btn-save {
  background: white;
  color: #1a73e8;
  border: 1px solid #1a73e8;
}
.btn-save:hover:not(:disabled) { background: #e8f0fe; }
.btn-save-return { background: #1a73e8; color: white; }
.btn-save-return:hover:not(:disabled) { background: #1557b0; }
.btn-save:disabled, .btn-save-return:disabled { opacity: 0.5; cursor: not-allowed; }

/* ============================================================ */
/* PLAGIARISM TAB                                                */
/* ============================================================ */
.plagiarism-tab-content {
  background: white;
  border-radius: 0 0 12px 12px;
  padding: 0;
  min-height: 300px;
}

.plagiarism-actions-bar {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 12px 16px;
  background: #f8f9fa;
  border-bottom: 1px solid #e8eaed;
}

.btn-run-plagiarism {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 10px 20px;
  border: 1px solid #1a73e8;
  background: #1a73e8;
  color: white;
  border-radius: 8px;
  font-weight: 600;
  font-size: 13px;
  cursor: pointer;
  transition: all 0.15s;
}
.btn-run-plagiarism:hover:not(:disabled) { background: #1557b0; }
.btn-run-plagiarism:disabled { opacity: 0.6; cursor: not-allowed; }

.plagiarism-checked-at {
  font-size: 12px;
  color: #5f6368;
}

.plagiarism-viewer-wrapper {
  padding: 16px;
  max-height: calc(100vh - 340px);
  overflow-y: auto;
}

.no-plagiarism-results {
  padding: 60px 24px;
  text-align: center;
  color: #9ca3af;
}
.no-plagiarism-results p { margin: 16px 0 4px; font-size: 16px; color: #6b7280; }
.no-plagiarism-results small { font-size: 13px; }

.tab-badge {
  display: inline-block;
  padding: 2px 8px;
  border-radius: 10px;
  font-size: 11px;
  font-weight: 700;
  margin-left: 6px;
}
.tab-badge.good { background: #e6f4ea; color: #1e8e3e; }
.tab-badge.neutral { background: #fef7e0; color: #e37400; }
.tab-badge.bad { background: #fce8e6; color: #d93025; }

@keyframes spin {
  from { transform: rotate(0deg); }
  to { transform: rotate(360deg); }
}
.spin { animation: spin 1s linear infinite; }

/* ============================================================ */
/* RESPONSIVE                                                    */
/* ============================================================ */
@media (max-width: 1024px) {
  .content-grid {
    grid-template-columns: 1fr;
  }
  .detail-row {
    grid-template-columns: 120px 100px 1fr;
  }
}
</style>
