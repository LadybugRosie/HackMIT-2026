<template>
  <div class="editor-page-container">
    <!-- Face Verification Gate — only rendered once we know the requirements.
         In assignment mode, wait for assignment data to load first to avoid
         the race condition where FaceVerification skips prematurely. -->
    <FaceVerification
      v-if="(!isAssignmentMode || assignmentDataLoaded) && assignmentToolSettings.face_verification_enabled"
      :session-id="sessionId"
      :check-interval="assignmentFaceInterval"
      :min-check-interval="600000"
      :max-check-interval="1800000"
      :use-random-interval="true"
      :skip-if-hidden="true"
      :is-verified="faceVerified"
      :assignment-requires-face="assignmentRequiresFace"
      @verified="handleFaceVerified"
      @session-terminated="handleSessionTerminated"
      @skip="handleFaceSkipped"
    />
    <!-- 
      💰 PRODUCTION COST-OPTIMIZED SETTINGS:
      - check-interval: 900000 (15 min base)
      - min-check-interval: 600000 (10 min minimum)
      - max-check-interval: 1800000 (30 min maximum)
      - Random intervals for unpredictability
      - Skip when tab hidden
      - Plus: Client-side detection, activity-based skipping
      
      EXPECTED COST: ~$0.004 per 4-hour session (~0.4 cents!)
      vs $0.10+ without optimizations
      
      🧪 FOR TESTING, use these settings:
      :check-interval="10000"
      :min-check-interval="10000"
      :max-check-interval="10000"
      :use-random-interval="false"
      :skip-if-hidden="false"
    -->

    <!-- Session Recorder — captures snapshots for teacher playback (assignment mode only) -->
    <SessionRecorder
      v-if="isAssignmentMode && route.query.assignment_id"
      :assignment-id="route.query.assignment_id"
      :user-id="currentUserId"
    />

    <!-- Live collaborators (collaborative reports only) -->
    <div v-if="isCollabMode" class="collab-bar-float">
      <CollaboratorsBar />
    </div>

    <!-- Invite / collaborators panel -->
    <CollabInvitePanel
      v-if="showInvitePanel && isCollabMode"
      :submission-id="route.params.id"
      :lab-id="route.query.class_id"
      @close="showInvitePanel = false"
    />

    <!-- ========== ASSIGNMENT CONTEXT BAR ========== -->
    <div v-if="isAssignmentMode && assignmentData" class="assignment-bar">
      <div class="assignment-bar-left">
        <button @click="exitAssignment" class="assignment-bar-back" title="Back to assignment">
          <svg width="18" height="18" viewBox="0 0 24 24" fill="currentColor">
            <path d="M20 11H7.83l5.59-5.59L12 4l-8 8 8 8 1.41-1.41L7.83 13H20v-2z"/>
          </svg>
        </button>
        <div class="assignment-bar-info">
          <span class="assignment-bar-title">{{ assignmentData.title }}</span>
          <span class="assignment-bar-class">{{ assignmentClassName }}</span>
        </div>
      </div>
      <div class="assignment-bar-center">
        <span class="assignment-bar-status" :class="assignmentAutoSaveClass">
          {{ assignmentAutoSaveText }}
        </span>
      </div>
      <div class="assignment-bar-right">
        <button
          v-if="isCollabMode"
          class="assignment-bar-invite-btn"
          @click="showInvitePanel = true"
          title="Invite co-authors"
        >
          <svg width="16" height="16" viewBox="0 0 24 24" fill="currentColor">
            <path d="M15 12c2.21 0 4-1.79 4-4s-1.79-4-4-4-4 1.79-4 4 1.79 4 4 4zm-9-2V7H4v3H1v2h3v3h2v-3h3v-2H6zm9 4c-2.67 0-8 1.34-8 4v2h16v-2c0-2.66-5.33-4-8-4z"/>
          </svg>
          Invite
        </button>
        <button class="assignment-bar-instructions-btn" @click="showAssignmentPanel = !showAssignmentPanel">
          <svg width="16" height="16" viewBox="0 0 24 24" fill="currentColor">
            <path d="M11 7h2v2h-2zm0 4h2v6h-2zm1-9C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm0 18c-4.41 0-8-3.59-8-8s3.58-8 8-8 8 3.58 8 8-3.59 8-8 8z"/>
          </svg>
          {{ isResearcherMode ? 'Details' : 'Instructions' }}
        </button>
        <span v-if="!isResearcherMode" class="assignment-bar-due" :class="{ urgent: assignmentUrgent, past: assignmentPastDue }">
          {{ assignmentDueText }}
        </span>
        <button
          class="assignment-bar-submit"
          @click="handleAssignmentSubmit"
          :disabled="assignmentSubmitting"
        >
          <svg v-if="!assignmentSubmitting" width="16" height="16" viewBox="0 0 24 24" fill="currentColor">
            <path d="M2.01 21L23 12 2.01 3 2 10l15 2-15 2z"/>
          </svg>
          <span v-if="assignmentSubmitting" class="assignment-bar-spinner"></span>
          {{ assignmentSubmitting ? 'Submitting...' : 'Submit' }}
        </button>
      </div>
    </div>

    <!-- Assignment Instructions Side Panel -->
    <div v-if="isAssignmentMode && showAssignmentPanel" class="assignment-panel-overlay" @click.self="showAssignmentPanel = false">
      <div class="assignment-panel">
        <div class="assignment-panel-header">
          <h3>{{ isResearcherMode ? 'Report Details' : 'Assignment Details' }}</h3>
          <button @click="showAssignmentPanel = false" class="assignment-panel-close">
            <svg width="20" height="20" viewBox="0 0 24 24" fill="currentColor">
              <path d="M19 6.41L17.59 5 12 10.59 6.41 5 5 6.41 10.59 12 5 17.59 6.41 19 12 13.41 17.59 19 19 17.59 13.41 12z"/>
            </svg>
          </button>
        </div>
        <div class="assignment-panel-body">
          <div class="assignment-panel-section">
            <label>{{ isResearcherMode ? 'Topic' : 'Instructions' }}</label>
            <p>{{ assignmentData?.instructions || (isResearcherMode ? assignmentData?.title : 'No instructions provided.') }}</p>
          </div>
          <div v-if="!isResearcherMode" class="assignment-panel-section">
            <label>Points</label>
            <p>{{ assignmentData?.points }}</p>
          </div>
          <div v-if="!isResearcherMode" class="assignment-panel-section">
            <label>Due Date</label>
            <p>{{ formatFullDate(assignmentData?.due_date) }}</p>
          </div>
          <div v-if="isResearcherMode" class="assignment-panel-section">
            <label>Integrity</label>
            <p>Stylometry only — your writing is verified against your enrolled authorship profile.</p>
          </div>
          <div v-if="!isResearcherMode && assignmentData?.rubric?.length" class="assignment-panel-section">
            <label>Rubric</label>
            <div class="assignment-panel-rubric">
              <div v-for="c in assignmentData.rubric" :key="c.criteria_id" class="rubric-row">
                <span class="rubric-name">{{ c.name }}</span>
                <span class="rubric-pts">{{ c.points }} pts</span>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- Assignment Submit Confirmation Modal -->
    <div v-if="showAssignmentSubmitConfirm" class="assignment-modal-overlay">
      <div class="assignment-submit-modal">
        <h2>{{ isResearcherMode ? 'Submit Report?' : 'Submit Assignment?' }}</h2>
        <p v-if="isResearcherMode">This will run the stylometry check{{ isCollabMode ? ' for each author' : '' }} and generate your report PDF + session video. Once submitted, you cannot edit your work.</p>
        <p v-else>This will run a full integrity analysis and generate your integrity report PDF. Once submitted, you cannot edit your work.</p>
        <div v-if="!isResearcherMode" class="assignment-submit-summary">
          <div class="summary-stat">
            <span class="stat-label">Points</span>
            <span class="stat-value">{{ assignmentData?.points }}</span>
          </div>
        </div>
        <div v-if="assignmentPastDue" class="assignment-late-note">
          This assignment is past due. A late penalty may apply.
        </div>
        <div class="assignment-modal-actions">
          <button class="modal-btn-cancel" @click="showAssignmentSubmitConfirm = false">Cancel</button>
          <button class="modal-btn-submit" @click="confirmAssignmentSubmit" :disabled="assignmentSubmitting">
            {{ assignmentSubmitting ? 'Analyzing & Submitting...' : 'Confirm Submit' }}
          </button>
        </div>
      </div>
    </div>

    <!-- Report Preview Modal - Student reviews the generated integrity report before final submission -->
    <div v-if="showAssignmentReportPreview" class="report-preview-overlay">
      <div class="report-preview-container">
        <div class="report-preview-header">
          <h2>{{ isResearcherMode ? 'Review Your Stylometry Report' : 'Review Your Integrity Report' }}</h2>
          <p>{{ isResearcherMode ? 'Per-author stylometry only — this is your authorship verification.' : 'Please review the generated report below. This will be submitted to your teacher along with your assignment.' }}</p>
        </div>
        <div class="report-preview-frame">
          <iframe :srcdoc="assignmentReportHtml" class="report-preview-iframe" scrolling="yes"></iframe>
        </div>
        <div class="report-preview-actions">
          <button class="report-btn-cancel" @click="cancelReportPreview">
            Go Back & Edit
          </button>
          <button class="report-btn-submit" @click="finalizeAssignmentSubmit" :disabled="assignmentSubmitting">
            {{ assignmentSubmitting ? 'Submitting...' : 'Confirm & Submit' }}
          </button>
        </div>
      </div>
    </div>
    
    <!-- Submission Result Modal — Shows individual integrity signals after submit -->
    <div v-if="showSubmissionResult" class="assignment-modal-overlay">
      <div class="submission-result-modal">
        <div class="result-icon" :class="isResearcherMode ? 'result-high' : submissionResultClass">
          <svg v-if="isResearcherMode || !integrityLegacyMode || resultSignalsOk" width="48" height="48" viewBox="0 0 24 24" fill="currentColor">
            <path d="M9 16.17L4.83 12l-1.42 1.41L9 19 21 7l-1.41-1.41z"/>
          </svg>
          <svg v-else width="48" height="48" viewBox="0 0 24 24" fill="currentColor">
            <path d="M1 21h22L12 2 1 21zm12-3h-2v-2h2v2zm0-4h-2v-4h2v4z"/>
          </svg>
        </div>
        <h2>{{ isResearcherMode ? 'Report Submitted' : 'Assignment Submitted' }}</h2>
        <!-- Individual signals (trust / stylometry / AI): shown only in legacy
             mode (students see no integrity in new mode). Researcher reports
             are stylometry-only. -->
        <template v-if="!isResearcherMode && integrityLegacyMode">
          <div class="result-signals">
            <div class="result-signal" :class="submissionResultClass">
              <div class="signal-value">{{ resultTrustLabel }}</div>
              <div class="signal-label">Typing Trust</div>
            </div>
            <div class="result-signal" :class="resultStyloClass">
              <div class="signal-value">{{ resultStyloLabel }}</div>
              <div class="signal-label">Stylometry</div>
            </div>
            <div class="result-signal" :class="resultAiClass">
              <div class="signal-value">{{ resultAiLabel }}</div>
              <div class="signal-label">AI Detection</div>
            </div>
          </div>
        </template>
        <div v-if="submissionResultData?.isLate" class="result-late">Late submission — penalty may apply</div>
        <div v-if="!isResearcherMode && integrityLegacyMode && submissionResultData?.flags?.length" class="result-flags">
          <div v-for="(flag, i) in submissionResultData.flags" :key="i" class="result-flag">{{ flag }}</div>
        </div>
        <p class="result-note">{{ isResearcherMode ? 'Your individual stylometry results, session replay, PDF and report are ready on the next screen.' : 'Great work — your assignment is in! 🎉 Your teacher will review your writing along with your integrity score and share your grade soon.' }}</p>
        <button class="modal-btn-submit" @click="showSubmissionResult = false; router.push(submissionResultPath(assignmentSubmissionId))">
          {{ isResearcherMode ? 'View Deliverables' : 'Done' }}
        </button>
      </div>
    </div>

    <!-- Editor Content — always mounted so it keeps state. Hidden behind
         the face verification overlay until verified. v-show (not v-if)
         prevents the editor from being destroyed/recreated, which caused
         white-screen and content loss. -->
    <div v-show="faceVerified" class="editor-wrapper">
      <!-- Use chat-only layout for blank template mode -->
      <BlankModuleLayoutNew v-if="selectedMode === 'blank-template'">
        <umo-editor ref="editorRef" v-bind="options" @save="onSave" />
        <IntegrityTracker v-if="integrityStateReady" />
      </BlankModuleLayoutNew>

      <!-- Fallback to existing layout for all other modes -->
      <EditorLayout v-else>
        <umo-editor ref="editorRef" v-bind="options" @save="onSave" />
        <IntegrityTracker v-if="integrityStateReady" />
        <template #toc>
          <div>No content available yet.</div>
        </template>
      </EditorLayout>
    </div>
  </div>
</template>

<script setup>
import EditorLayout from '@/components/EditorLayout.vue'
import BlankModuleLayoutNew from '@/components/BlankModuleLayoutNew.vue'
import IntegrityTracker from '@/components/editor/IntegrityTracker.vue'
import FaceVerification from '@/components/FaceVerification.vue'
import SessionRecorder from '@/components/editor/SessionRecorder.vue'
import CollaboratorsBar from '@/components/collab/CollaboratorsBar.vue'
import CollabInvitePanel from '@/components/collab/CollabInvitePanel.vue'
import { getAuthorSegments } from '@/extensions/authorship'
import { exportSnapshots, clearSnapshots, clearEvents } from '@/utils/snapshotDB'
import { syncEvents } from '@/utils/eventSync'

import shortId from '@/utils/short-id'
import { useRoute, useRouter, onBeforeRouteLeave } from 'vue-router'
import { ref, watch, onMounted, onBeforeUnmount, computed, nextTick } from 'vue'
import axios from 'axios'
import { getApiUrl } from '@/utils/api-url'
import { useStore } from '@/composables/store'
import { useAuth } from '@/composables/auth'
import { integrityLegacyMode } from '@/composables/feature-flags'

import { t } from '@/composables/i18n'

const route = useRoute()
const router = useRouter()
const ASSIGN_API = getApiUrl()
const { integrity: integrityState, page: editorPage, editorDestroyed, assignmentToolSettings, editor: storeEditor } = useStore()

// Save the draft (awaited) before any SPA navigation away from the editor, so
// typed/pasted content is never lost on "back". onBeforeUnmount can't await an
// async save; this guard can. The keepalive emergency save remains the backstop.
onBeforeRouteLeave(async () => {
  // Snapshot the integrity tracker's databases synchronously BEFORE leaving:
  // its own save triggers (5s interval + beforeunload/pagehide) do not fire on
  // SPA navigation, so a paste in the final seconds would otherwise be lost
  // from the restore snapshot. Mirrors IntegrityTracker's own save schema.
  try {
    // Local snapshot is UNTRUNCATED — it replaces IntegrityTracker's own full
    // save, and fingerprints regenerated from truncated data could false-flag
    // honest re-pastes. Truncation is only for the network payload.
    const snap = buildIntegrityClientState({ full: true })
    if (isAssignmentMode.value && snap && _snapshotHasData(snap) && route.query.assignment_id) {
      localStorage.setItem('integrity_session_' + route.query.assignment_id, JSON.stringify(snap))
    }
  } catch { /* storage unavailable */ }
  try { flushIntegrityClientState(true) } catch { /* best effort */ }
  try {
    if (isAssignmentMode.value && assignmentContentChanged) {
      await autoSaveAssignmentDraft()
    }
  } catch { /* backstop: emergencySaveDraft() in onBeforeUnmount */ }
})

function _snapshotHasData(s) {
  return !!s && ((s.TYPED_DB?.totalTypedCount > 0)
    || (s.EXTERNAL_DB?.pastes?.length > 0)
    || (s.TIMELINE_DB?.segments?.length > 0))
}

// Snapshot of the integrity tracker's window databases in the EXACT shape that
// IntegrityTracker._restoreIntegrityState and the server client_state expect
// (mirrors the builder in editor/index.vue sendIntegrityEvents).
function buildIntegrityClientState({ full = false } = {}) {
  if (!window.TYPED_DB || !window.EXTERNAL_DB) return null
  return {
    TYPED_DB: {
      allTypedChars: full ? (window.TYPED_DB.allTypedChars || '') : (window.TYPED_DB.allTypedChars || '').slice(-10000),
      totalTypedCount: window.TYPED_DB.totalTypedCount || 0,
    },
    EXTERNAL_DB: {
      pastes: (window.EXTERNAL_DB.pastes || []).map(p => ({ id: p.id, text: p.text, timestamp: p.timestamp })),
      totalPastedChars: window.EXTERNAL_DB.totalPastedChars || 0,
    },
    INTERNAL_DB: {
      pastes: full ? (window.INTERNAL_DB?.pastes || []) : (window.INTERNAL_DB?.pastes || []).slice(-100),
      totalChars: window.INTERNAL_DB?.totalChars || 0,
      copyBuffer: full ? (window.INTERNAL_DB?.copyBuffer || []) : (window.INTERNAL_DB?.copyBuffer || []).slice(-50),
    },
    TIMELINE_DB: {
      segments: full ? (window.TIMELINE_DB?.segments || []) : (window.TIMELINE_DB?.segments || []).slice(-1000),
      deletions: window.TIMELINE_DB?.deletions || 0,
      additions: window.TIMELINE_DB?.additions || 0,
    },
    ts: Date.now()
  }
}

// Push the tracker's paste/typing state to the server on exit, so a browser
// switch never loses the last few seconds of pastes (the periodic ingest only
// ships client_state every 10s). Keepalive + debounced; skips without session.
// `force` bypasses the debounce for terminal events (pagehide/beforeunload/
// route-leave) so the FINAL state always ships.
let _lastClientStateFlush = 0
function flushIntegrityClientState(force = false) {
  if (!isAssignmentMode.value) return
  const sessionId = integrityState.value?.sessionId
  if (!sessionId) return
  const now = Date.now()
  if (!force && now - _lastClientStateFlush < 3000) return
  const clientState = buildIntegrityClientState()
  if (!clientState) return
  // NEVER ship an empty snapshot — after a failed hydration it would
  // overwrite rich server-side client_state with nothing.
  if (!_snapshotHasData(clientState)) return
  const token = localStorage.getItem('auth_token')
  if (!token) return
  _lastClientStateFlush = now
  // Trim timeline harder to stay under the 64KB keepalive cap.
  clientState.TIMELINE_DB.segments = clientState.TIMELINE_DB.segments.slice(-100)
  try {
    fetch(`${ASSIGN_API}/api/integrity/ingest`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', 'Authorization': `Bearer ${token}` },
      body: JSON.stringify({
        session_id: sessionId,
        doc_id: route.query.assignment_id,
        events: [],
        client_state: clientState
      }),
      keepalive: true
    }).catch(() => {})
  } catch { /* page unloading */ }
}

// Researcher mode: same assignment pipeline, different exits.
// user may not be hydrated on hard reload — initAuth() is kicked off in onMounted.
const { user: authUser, initAuth } = useAuth()
const isResearcherMode = computed(() => authUser.value?.role === 'researcher')
const currentUserId = computed(() => authUser.value?.user_id || null)
const isCollabMode = computed(() => route.query.collab === '1')
const showInvitePanel = ref(false)

/** Where "leave the editor" goes for this account type */
function assignmentExitPath() {
  return isResearcherMode.value
    ? '/researcher/dashboard'
    : `/student/assignment/${route.query.assignment_id}`
}

/** Where "submission finished / already submitted" goes for this account type */
function submissionResultPath(submissionId) {
  return isResearcherMode.value && submissionId
    ? `/researcher/submission/${submissionId}`
    : `/student/assignment/${route.query.assignment_id}`
}

// Face verification state
const faceVerified = ref(false)
const assignmentDataLoaded = ref(false) // Tracks if assignment context is loaded
const integrityStateReady = ref(false) // Gates IntegrityTracker mount until server restore completes
// Session ID: starts with a local fallback, then syncs to the backend-created
// session once the editor component initialises the integrity session.
const sessionId = ref('session-' + Date.now() + '-' + Math.random().toString(36).substr(2, 9))

// Assignment-level face verification settings (teacher-configured)
const assignmentRequiresFace = computed(() => {
  return assignmentData.value?.settings?.face_verification_enabled ?? false
})
const assignmentFaceInterval = computed(() => {
  // Use teacher's configured interval, or default to 15 min (cost-optimized)
  return assignmentData.value?.settings?.face_check_interval ?? 900000
})

// Face verification log for submission integrity data
const faceVerificationLog = ref([])

// Face verification handlers
function handleFaceVerified() {
  console.log('✅ Face verified - granting editor access')
  faceVerified.value = true
  faceVerificationLog.value.push({
    timestamp: new Date().toISOString(),
    result: 'verified',
    confidence: 1.0
  })

  // CRITICAL: Force the editor to recalculate its layout after becoming visible.
  // ProseMirror/TipTap doesn't render correctly when its container was display:none.
  // Use setTimeout before nextTick to ensure v-show has taken effect in the DOM.
  setTimeout(() => {
    nextTick(() => {
      window.dispatchEvent(new Event('resize'))
      if (editorRef?.editor && !editorRef.editor.isDestroyed) {
        try {
          editorRef.editor.view.updateState(editorRef.editor.view.state)
        } catch (e) { /* editor may not be ready yet */ }
      }
      // Retry after a longer delay for slow-initializing editors
      setTimeout(() => {
        window.dispatchEvent(new Event('resize'))
        if (editorRef?.editor && !editorRef.editor.isDestroyed) {
          try {
            editorRef.editor.view.updateState(editorRef.editor.view.state)
            editorRef.editor.commands.focus()
          } catch (e) { /* ignore */ }
        }
        // Reload draft content if it was fetched while editor was hidden
        if (window.editorContentFromDatabase) {
          loadContentFromDatabase()
        }
      }, 500)
    })
  }, 150)
}

function handleSessionTerminated() {
  console.log('⚠️ Session terminated due to face mismatch')
  if (isAssignmentMode.value) {
    // Auto-save draft before redirect
    autoSaveAssignmentDraft()
    router.push(assignmentExitPath())
  } else {
    router.push('/dashboard')
  }
}

function handleFaceSkipped() {
  if (!assignmentRequiresFace.value) {
    console.log('⏭️ Face verification skipped (not required)')
    faceVerified.value = true
    // Same re-render kick as handleFaceVerified
    nextTick(() => {
      window.dispatchEvent(new Event('resize'))
      setTimeout(() => {
        window.dispatchEvent(new Event('resize'))
        if (editorRef?.editor && !editorRef.editor.isDestroyed) {
          try {
            editorRef.editor.view.updateState(editorRef.editor.view.state)
            editorRef.editor.commands.focus()
          } catch (e) { /* ignore */ }
        }
        if (window.editorContentFromDatabase) {
          loadContentFromDatabase()
        }
      }, 300)
    })
  } else {
    console.log('⚠️ Face skip attempted but assignment requires it - blocking')
  }
}

// ============================================================================
// ASSIGNMENT MODE - Submit from within the existing UMO editor
// ============================================================================
const isAssignmentMode = computed(() => !!route.query.assignment_id)

// Cross-browser integrity restore: populate window globals from server-stored snapshot.
// NOTE: These globals may be frozen (writable:false) by IntegrityTracker's anti-tamper
// code, so we MUST mutate in-place rather than reassigning.
function _hydrateIntegrityGlobals(state) {
  // Fingerprint generator — same logic as IntegrityTracker (line 31-59)
  function _genFP(text) {
    const norm = text.toLowerCase().replace(/[^a-z0-9\s]/g, ' ').replace(/\s+/g, ' ').trim()
    const words = norm.split(' ').filter(w => w.length >= 3)
    const fp = { words: new Set(words), bigrams: new Set(), trigrams: new Set(), charGrams: new Set() }
    for (let i = 0; i < words.length - 1; i++) fp.bigrams.add(words[i] + ' ' + words[i + 1])
    for (let i = 0; i < words.length - 2; i++) fp.trigrams.add(words[i] + ' ' + words[i + 1] + ' ' + words[i + 2])
    const clean = text.toLowerCase().replace(/\s+/g, '')
    for (let i = 0; i <= clean.length - 6; i++) fp.charGrams.add(clean.substring(i, i + 6))
    return fp
  }

  const restoredPastes = (state.EXTERNAL_DB?.pastes || []).map(p => ({
    ...p, fingerprints: p.text ? _genFP(p.text) : null
  }))

  // If globals already exist (frozen by IntegrityTracker), mutate in-place
  if (window.TYPED_DB) {
    window.TYPED_DB.allTypedChars = state.TYPED_DB?.allTypedChars || ''
    window.TYPED_DB.totalTypedCount = state.TYPED_DB?.totalTypedCount || 0
    window.TYPED_DB.fingerprints = null
    window.TYPED_DB.sessionStart = Date.now()
  } else {
    window.TYPED_DB = {
      allTypedChars: state.TYPED_DB?.allTypedChars || '',
      totalTypedCount: state.TYPED_DB?.totalTypedCount || 0,
      fingerprints: null, sessionStart: Date.now()
    }
  }

  if (window.EXTERNAL_DB) {
    window.EXTERNAL_DB.pastes.length = 0
    window.EXTERNAL_DB.pastes.push(...restoredPastes)
    window.EXTERNAL_DB.totalPastedChars = state.EXTERNAL_DB?.totalPastedChars || 0
    window.EXTERNAL_DB.sessionStart = Date.now()
  } else {
    window.EXTERNAL_DB = {
      pastes: restoredPastes,
      totalPastedChars: state.EXTERNAL_DB?.totalPastedChars || 0,
      sessionStart: Date.now()
    }
  }

  if (window.INTERNAL_DB) {
    window.INTERNAL_DB.pastes.length = 0
    window.INTERNAL_DB.pastes.push(...(state.INTERNAL_DB?.pastes || []))
    window.INTERNAL_DB.totalChars = state.INTERNAL_DB?.totalChars || 0
    window.INTERNAL_DB.copyBuffer.length = 0
    window.INTERNAL_DB.copyBuffer.push(...(state.INTERNAL_DB?.copyBuffer || []))
  } else {
    window.INTERNAL_DB = {
      pastes: state.INTERNAL_DB?.pastes || [],
      totalChars: state.INTERNAL_DB?.totalChars || 0,
      copyBuffer: state.INTERNAL_DB?.copyBuffer || []
    }
  }

  if (window.TIMELINE_DB) {
    window.TIMELINE_DB.segments.length = 0
    window.TIMELINE_DB.segments.push(...(state.TIMELINE_DB?.segments || []))
    window.TIMELINE_DB.deletions = state.TIMELINE_DB?.deletions || 0
    window.TIMELINE_DB.additions = state.TIMELINE_DB?.additions || 0
    window.TIMELINE_DB.currentTypingStart = null
    window.TIMELINE_DB.currentTypingText = ''
    window.TIMELINE_DB.lastKeystroke = Date.now()
  } else {
    window.TIMELINE_DB = {
      segments: state.TIMELINE_DB?.segments || [],
      deletions: state.TIMELINE_DB?.deletions || 0,
      additions: state.TIMELINE_DB?.additions || 0,
      currentTypingStart: null, currentTypingText: '', lastKeystroke: Date.now()
    }
  }

  console.log('🔄 Integrity state hydrated from server —',
    'typed:', window.TYPED_DB.totalTypedCount,
    'pastes:', window.EXTERNAL_DB.pastes.length,
    'segments:', window.TIMELINE_DB.segments.length)
}

const assignmentData = ref(null)
const assignmentClassName = ref('')
const assignmentSubmitting = ref(false)
const showAssignmentPanel = ref(false)
const showAssignmentSubmitConfirm = ref(false)
const showAssignmentReportPreview = ref(false)
const showSubmissionResult = ref(false)
const submissionResultData = ref(null)
const assignmentReportHtml = ref('')
const assignmentReportData = ref(null)
const assignmentSubmissionId = ref(null)
const assignmentAutoSaveStatus = ref('idle') // idle | saving | saved | error
let assignmentAutoSaveTimer = null
let assignmentContentChanged = false

const assignmentAutoSaveText = computed(() => {
  if (assignmentAutoSaveStatus.value === 'saving') return 'Saving draft...'
  if (assignmentAutoSaveStatus.value === 'saved') return 'Draft saved'
  if (assignmentAutoSaveStatus.value === 'too_large') return 'Cloud backup paused — document too large (saved on this device only)'
  if (assignmentAutoSaveStatus.value === 'error') return 'Save failed'
  return ''
})

const assignmentAutoSaveClass = computed(() => assignmentAutoSaveStatus.value)

const submissionResultClass = computed(() => {
  const score = submissionResultData.value?.trustScore ?? 0
  if (score >= 80) return 'result-high'
  if (score >= 60) return 'result-medium'
  return 'result-low'
})

const resultStyloClass = computed(() => {
  const v = submissionResultData.value?.styloVerdict
  if (v === 'verified') return 'result-high'
  if (v === 'flagged') return 'result-low'
  return 'result-medium'
})

const resultAiClass = computed(() => {
  const p = submissionResultData.value?.aiProbability
  if (p == null || p < 0.3) return 'result-high'
  if (p < 0.6) return 'result-medium'
  return 'result-low'
})

const resultTrustLabel = computed(() => {
  const t = submissionResultData.value?.trustScore
  return t != null ? `${t}%` : 'N/A'
})

const resultStyloLabel = computed(() => {
  const v = submissionResultData.value?.styloVerdict
  if (!v) return 'N/A'
  if (v === 'review_required') return 'Review'
  return v.charAt(0).toUpperCase() + v.slice(1)
})

const resultAiLabel = computed(() => {
  const p = submissionResultData.value?.aiProbability
  return p != null ? `${Math.round(p * 100)}% AI` : 'N/A'
})

const resultSignalsOk = computed(() => {
  const d = submissionResultData.value || {}
  return (d.trustScore ?? 0) >= 60
    && d.styloVerdict !== 'flagged'
    && (d.aiProbability == null || d.aiProbability < 0.6)
})

const assignmentPastDue = computed(() => {
  if (!assignmentData.value?.due_date) return false
  return new Date(assignmentData.value.due_date) < new Date()
})

const assignmentUrgent = computed(() => {
  if (!assignmentData.value?.due_date) return false
  const hours = (new Date(assignmentData.value.due_date) - new Date()) / (1000 * 60 * 60)
  return hours > 0 && hours < 24
})

const assignmentDueText = computed(() => {
  if (!assignmentData.value?.due_date) return ''
  const diff = new Date(assignmentData.value.due_date) - new Date()
  if (diff < 0) return 'Past due'
  const hours = diff / (1000 * 60 * 60)
  if (hours < 1) return 'Due soon'
  if (hours < 24) return `Due in ${Math.round(hours)}h`
  return `Due in ${Math.floor(hours / 24)}d`
})

function formatFullDate(date) {
  if (!date) return '-'
  return new Date(date).toLocaleString('en-US', {
    month: 'short', day: 'numeric', year: 'numeric',
    hour: 'numeric', minute: '2-digit'
  })
}

function getEditorContentForSubmission() {
  // Use the existing getEditorHTMLContent function
  if (window.getEditorHTMLContent) {
    return window.getEditorHTMLContent()
  }
  return ''
}

async function autoSaveAssignmentDraft() {
  if (!isAssignmentMode.value) return
  const content = getEditorContentForSubmission()
  if (!content || !content.trim()) return
  
  const token = localStorage.getItem('auth_token')
  if (!token) return
  
  assignmentAutoSaveStatus.value = 'saving'
  try {
    const response = await axios.post(`${ASSIGN_API}/api/submissions`, {
      assignment_id: route.query.assignment_id,
      content: content,
      content_html: content
    })
    assignmentAutoSaveStatus.value = 'saved'
    if (response.data.submission_id) {
      assignmentSubmissionId.value = response.data.submission_id
    }
    assignmentContentChanged = false
    setTimeout(() => {
      if (assignmentAutoSaveStatus.value === 'saved') assignmentAutoSaveStatus.value = 'idle'
    }, 3000)
  } catch (e) {
    console.error('Assignment auto-save failed:', e)
    // A 413/400 "too large" is PERSISTENT — every future autosave will fail
    // the same way, so the cloud copy is frozen. Show a sticky warning
    // (localStorage still has the full document on this device).
    const detail = e.response?.data?.detail || ''
    if (e.response?.status === 413 || (e.response?.status === 400 && /too large/i.test(detail))) {
      assignmentAutoSaveStatus.value = 'too_large'
    } else {
      assignmentAutoSaveStatus.value = 'error'
    }
  }
}

function emergencySaveDraft() {
  if (!isAssignmentMode.value) return
  const content = getEditorContentForSubmission()
  if (!content || !content.trim()) return
  const token = localStorage.getItem('auth_token')
  if (!token) return
  
  const payload = JSON.stringify({
    assignment_id: route.query.assignment_id,
    content: content,
    content_html: content
  })
  
  const url = `${ASSIGN_API}/api/submissions`

  // Chromium rejects keepalive bodies over ~64KB with a swallowed promise
  // rejection — for large drafts use a normal fetch (visibility-hidden fires
  // early enough to usually complete) and fall back to sync XHR on failure.
  const oversized = new TextEncoder().encode(payload).length > 60000

  const sendXhr = () => {
    try {
      const xhr = new XMLHttpRequest()
      xhr.open('POST', url, false)
      xhr.setRequestHeader('Content-Type', 'application/json')
      xhr.setRequestHeader('Authorization', `Bearer ${token}`)
      xhr.send(payload)
    } catch { /* page is unloading, nothing we can do */ }
  }

  try {
    fetch(url, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${token}`
      },
      body: payload,
      keepalive: !oversized
    }).catch(() => { if (oversized) sendXhr() })
  } catch {
    sendXhr()
  }
}

// ─── Bulletproof local draft backup + restore ──────────────────────────────
// The server save can lose a race with a fast "back" navigation, and the
// editor's content re-injection on return is timing-fragile. localStorage is
// synchronous and instant, so it never loses content; on return we re-inject
// it reliably (retrying until the editor is ready and verifying it stuck).
function draftLocalKey() {
  return 'editorrah_draft_' + (route.query.assignment_id || '')
}
let _draftRestored = false
let _draftRestoreTries = 0
function backupDraftLocally() {
  try {
    const html = window.getEditorHTMLContent ? window.getEditorHTMLContent() : ''
    if (html && html.replace(/<[^>]*>/g, '').trim()) {
      // uid scoping: on a shared computer another user's local backup must
      // never be restored into (or autosaved over) this user's submission.
      localStorage.setItem(draftLocalKey(), JSON.stringify({ html, ts: Date.now(), uid: currentUserId.value || null }))
    }
  } catch { /* storage unavailable */ }
}
// Returns { html, ts } from the local backup, or null. Tolerates the legacy
// plain-string format (treated as oldest so the server always wins over it).
function readLocalDraft() {
  let raw = null
  try { raw = localStorage.getItem(draftLocalKey()) } catch { return null }
  if (!raw) return null
  try {
    const o = JSON.parse(raw)
    // A backup written by a DIFFERENT logged-in user is poison — drop it.
    if (o && o.uid && currentUserId.value && o.uid !== currentUserId.value) {
      try { localStorage.removeItem(draftLocalKey()) } catch { /* ignore */ }
      return null
    }
    if (o && typeof o.html === 'string' && o.html.replace(/<[^>]*>/g, '').trim()) {
      return { html: o.html, ts: Number(o.ts) || 0 }
    }
  } catch {
    if (raw.replace(/<[^>]*>/g, '').trim()) return { html: raw, ts: 0 }
  }
  return null
}
function restoreDraftIfNeeded() {
  if (_draftRestored) return
  // COLLAB MODE: the Yjs document is the single source of truth. Calling
  // setContent here clears the editor, which deletes the shared Yjs content
  // and syncs that deletion to every client + the server — wiping everyone's
  // work. Never inject in collab; Yjs restores the doc from the collab server.
  if (route.query.collab === '1') { _draftRestored = true; return }
  const target = window.editorContentFromDatabase
  if (!target || !target.replace(/<[^>]*>/g, '').trim()) return
  const ed = editorRef?.editor
  if (!ed || ed.isDestroyed || !ed.view) {
    if (_draftRestoreTries++ < 40) setTimeout(restoreDraftIfNeeded, 250)
    return
  }
  // Never overwrite content the user already started typing this session —
  // but stash the losing draft so it is never unrecoverable (the next
  // autosave would otherwise overwrite the server copy with only new typing).
  if ((ed.getText() || '').trim().length > 0) {
    try { localStorage.setItem(draftLocalKey() + '_rescued', JSON.stringify({ html: target, ts: Date.now() })) } catch { /* ignore */ }
    _draftRestored = true
    return
  }
  try { ed.commands.setContent(target, false) } catch { /* verified + retried below */ }
  setTimeout(() => {
    const after = (editorRef?.editor?.getText() || '').trim()
    if (after.length === 0 && _draftRestoreTries++ < 40) {
      setTimeout(restoreDraftIfNeeded, 250)
    } else {
      _draftRestored = true
    }
  }, 160)
}

async function exitAssignment() {
  if (assignmentContentChanged) {
    await autoSaveAssignmentDraft()
  }
  router.push(assignmentExitPath())
}

function handleAssignmentSubmit() {
  const content = getEditorContentForSubmission()
  if (!content || content.replace(/<[^>]*>/g, '').trim().length < 20) {
    alert('Please write more content before submitting.')
    return
  }
  showAssignmentSubmitConfirm.value = true
}

async function confirmAssignmentSubmit() {
  assignmentSubmitting.value = true
  showAssignmentSubmitConfirm.value = false
  
  const token = localStorage.getItem('auth_token')
  const content = getEditorContentForSubmission()
  
  // First save as draft to get submission_id
  try {
    const draftRes = await axios.post(`${ASSIGN_API}/api/submissions`, {
      assignment_id: route.query.assignment_id,
      content: content,
      content_html: content
    })

    if (draftRes.data.submission_id) {
      assignmentSubmissionId.value = draftRes.data.submission_id
    }
  } catch (e) {
    console.error('Failed to save draft before submit:', e)
  }
  
  if (!assignmentSubmissionId.value) {
    alert('Failed to save your work. Please try again.')
    assignmentSubmitting.value = false
    return
  }
  
  // Set up callback for when print/analysis pipeline completes
  // The print.vue component will call this after generating the integrity report
  window._assignmentSubmitCallback = (reportData) => {
    window._assignmentSubmitCallback = null // Clear callback
    
    // Handle report generation failure
    if (reportData.error) {
      assignmentSubmitting.value = false
      alert('Report generation failed: ' + (reportData.errorMessage || 'Unknown error. Please try again.'))
      return
    }
    
    // Store the original report data (for upload)
    assignmentReportData.value = reportData

    // Researcher module: stylometry-ONLY report with every co-author's real
    // verdict (no trust/authenticity score). Student preview below is untouched.
    if (isResearcherMode.value) {
      showResearcherStylometryPreview(reportData)
      return
    }

    // New mode: students skip the integrity-report preview entirely and submit
    // directly. The full report was still generated above and is uploaded for
    // the teacher inside finalizeAssignmentSubmit() (which reads assignmentReportData).
    if (!integrityLegacyMode.value) {
      finalizeAssignmentSubmit()
      return
    }

    // Add screen-friendly styles for the preview
    // CRITICAL: The parent page sets global `html, body { height: 100vh; overflow: hidden; }`
    // which gets copied into the iframe via getStylesHtml(). We MUST override that
    // so the iframe content can scroll and render properly.
    const screenStyles = `<style id="screen-preview-overrides">
      /* Override global overflow:hidden from editor page styles */
      html, html[theme-mode] {
        overflow-y: auto !important;
        overflow-x: hidden !important;
        height: auto !important;
        min-height: 100% !important;
      }
      body, body.umo-editor-container, body.is-print { 
        padding: 40px !important; 
        max-width: 900px !important; 
        margin: 0 auto !important; 
        background: #f5f5f5 !important;
        min-height: auto !important;
        height: auto !important;
        overflow: visible !important;
        overflow-y: auto !important;
      }
      /* Override any fixed/absolute positioned elements from editor */
      .editor-page-container,
      .editor-fullscreen,
      .umo-editor-container {
        position: static !important;
        height: auto !important;
        overflow: visible !important;
      }
      .editor-container {
        background: white !important;
        padding: 40px !important;
        border-radius: 12px !important;
        box-shadow: 0 2px 8px rgba(0,0,0,0.1) !important;
        margin-bottom: 24px !important;
        height: auto !important;
        overflow: visible !important;
      }
      .integrity-report-page {
        background: white !important;
        border-radius: 12px !important;
        overflow: visible !important;
        box-shadow: 0 2px 8px rgba(0,0,0,0.1) !important;
        margin-bottom: 24px !important;
      }
      .timeline-report-page {
        background: white !important;
        border-radius: 12px !important;
        overflow: visible !important;
        box-shadow: 0 2px 8px rgba(0,0,0,0.1) !important;
        margin-bottom: 24px !important;
      }
      /* Hide any editor UI elements that shouldn't appear in report */
      .toolbar, .floating-menu, .canvas-controls, .zoom-controls,
      .umo-toolbar, .umo-bubble-menu, .statusbar { 
        display: none !important; 
      }
    </style>`
    // Inject screen styles BEFORE </body> so they come LAST and override everything
    let previewHtml = reportData.reportHtml
    if (previewHtml.includes('</body>')) {
      previewHtml = previewHtml.replace('</body>', screenStyles + '</body>')
    } else if (previewHtml.includes('</html>')) {
      previewHtml = previewHtml.replace('</html>', screenStyles + '</html>')
    } else {
      previewHtml = previewHtml + screenStyles
    }
    assignmentReportHtml.value = previewHtml
    
    assignmentSubmitting.value = false
    showAssignmentReportPreview.value = true
  }
  
  // Trigger the print/analysis pipeline - this runs stylometry, AI detection,
  // generates the integrity report with highlighted external content,
  // and then calls our callback above instead of opening the print dialog
  const { printing: printingState } = useStore()
  printingState.value = true
}

/**
 * Researcher-only deliverable report: per-author stylometry ONLY — no trust
 * score, authenticity score, AI or security sections. Students never see this.
 * @param authors list from GET /authors (name, user_id, stylometry_v3,
 *   stylometry_enrolled). Falls back to the submitter + whole-document
 *   stylometry when the per-author list isn't available.
 */
function buildResearcherStylometryReport(reportData, authors) {
  if (!authors || !authors.length) {
    const sty = reportData?.stylometry || {}
    let sim = sty.cosine_score ?? sty.score ?? sty.similarity
    if (sim != null && sim > 1) sim = sim / 100
    authors = [{
      name: authUser.value?.name || 'Researcher',
      user_id: currentUserId.value,
      stylometry_enrolled: true,
      stylometry_v3: { verdict: sty.verdict || 'review_required', cosine_score: sim },
    }]
  }
  const colorFor = (id) => {
    const s = String(id || 'anon'); let h = 0
    for (let i = 0; i < s.length; i++) h = ((h << 5) - h + s.charCodeAt(i)) | 0
    return `hsl(${Math.abs(h) % 360},65%,45%)`
  }
  const rows = authors.map((a) => {
    const v = a.stylometry_v3 || {}
    const enrolled = a.stylometry_enrolled !== false
    let cos = v.cosine_score
    if (cos != null && cos > 1) cos = cos / 100
    const pct = cos != null ? Math.round(cos * 100) : null
    const verdict = !enrolled ? 'not_enrolled' : (v.verdict || 'pending')
    const tone = verdict === 'verified' ? '#15803d'
      : verdict === 'flagged' ? '#b91c1c'
      : (verdict === 'pending' || verdict === 'not_enrolled') ? '#64748b' : '#b45309'
    const soft = verdict === 'verified' ? '#e7f6ec'
      : verdict === 'flagged' ? '#fdeaea'
      : (verdict === 'pending' || verdict === 'not_enrolled') ? '#f1f5f9' : '#fdf3e6'
    const label = verdict === 'verified' ? 'Verified'
      : verdict === 'flagged' ? 'Flagged'
      : verdict === 'not_enrolled' ? 'Not enrolled'
      : verdict === 'pending' ? 'Pending' : 'Review'
    const initials = (a.name || '?').trim().split(/\s+/).map(w => w[0]).slice(0, 2).join('').toUpperCase()
    return `<div class="card">
      <div class="who">
        <div class="avatar" style="background:${colorFor(a.user_id || a.name)}">${initials}</div>
        <div class="info">
          <div class="name">${a.name || 'Author'}</div>
          <div class="track"><div class="fill" style="width:${pct || 0}%;background:${tone}"></div></div>
          <div class="cap">${pct != null ? `Style similarity ${pct}%` : 'Awaiting analysis'}</div>
        </div>
      </div>
      <div class="pill" style="color:${tone};background:${soft}">${label}${pct != null ? ` · ${pct}%` : ''}</div>
    </div>`
  }).join('')
  return `<!doctype html><html><head><meta charset="utf-8"><title>Stylometry Report</title><style>
    *{box-sizing:border-box;margin:0;padding:0}
    body{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,Helvetica,Arial,sans-serif;color:#0f172a;background:#f6f7fb;padding:32px}
    .wrap{max-width:720px;margin:0 auto}
    .hero{background:linear-gradient(135deg,#6d5dfc,#8b5cf6 55%,#a855f7);color:#fff;border-radius:18px;padding:26px 30px;box-shadow:0 10px 30px rgba(124,58,237,.25)}
    .hero h1{font-size:22px;font-weight:800;letter-spacing:-.01em}
    .hero p{font-size:13.5px;opacity:.92;margin-top:6px}
    .count{margin:22px 4px 12px;font-size:11.5px;font-weight:700;letter-spacing:.06em;text-transform:uppercase;color:#64748b}
    .card{display:flex;align-items:center;justify-content:space-between;gap:18px;background:#fff;border:1px solid #eceef3;border-radius:14px;padding:16px 18px;margin-bottom:12px;box-shadow:0 1px 2px rgba(15,23,42,.05)}
    .who{display:flex;align-items:center;gap:14px;flex:1;min-width:0}
    .avatar{width:42px;height:42px;border-radius:50%;color:#fff;font-weight:700;font-size:15px;display:flex;align-items:center;justify-content:center;flex-shrink:0}
    .info{flex:1;min-width:0}
    .name{font-size:16px;font-weight:700;color:#0f172a}
    .track{height:6px;border-radius:4px;background:#eef1f6;margin:7px 0 5px;overflow:hidden}
    .fill{height:100%;border-radius:4px;transition:width .5s ease}
    .cap{font-size:11.5px;color:#94a3b8}
    .pill{font-size:13px;font-weight:800;padding:8px 16px;border-radius:20px;white-space:nowrap}
    .foot{margin-top:18px;font-size:11.5px;color:#94a3b8;text-align:center}
  </style></head><body><div class="wrap">
    <div class="hero"><h1>🛡 Stylometry Report</h1>
      <p>Each author's writing verified against their own enrolled stylometric profile.</p></div>
    <div class="count">${authors.length} author${authors.length > 1 ? 's' : ''}</div>
    ${rows}
    <div class="foot">Authorship verification by Editorrah · stylometry only</div>
  </div></body></html>`
}

/**
 * Compute every co-author's individual stylometry now (so the preview shows
 * all of them with real verdicts), then open the stylometry-only preview.
 */
const researcherPreviewAuthors = ref([])
async function showResearcherStylometryPreview(reportData) {
  const sid = assignmentSubmissionId.value
  try {
    let segments = []
    if (isCollabMode.value && editorRef?.editor) {
      segments = getAuthorSegments(editorRef.editor)
        .filter(s => s.uid && s.uid !== 'unknown')
        .map(s => ({ user_id: s.uid, text: s.text }))
    }
    if (!segments.length && currentUserId.value && editorRef?.editor) {
      segments = [{ user_id: currentUserId.value, text: editorRef.editor.getText() || '' }]
    }
    if (segments.length && sid) {
      await Promise.allSettled([
        axios.post(`${ASSIGN_API}/api/research/submissions/${sid}/verify-authors`, { segments }),
        axios.post(`${ASSIGN_API}/api/research/submissions/${sid}/compute-contributions`, { segments }),
      ])
    }
    if (sid) {
      const r = await axios.get(`${ASSIGN_API}/api/research/submissions/${sid}/authors`)
      researcherPreviewAuthors.value = r.data.authors || []
    }
  } catch (e) {
    researcherPreviewAuthors.value = []
  } finally {
    assignmentReportHtml.value = buildResearcherStylometryReport(reportData, researcherPreviewAuthors.value)
    assignmentSubmitting.value = false
    showAssignmentReportPreview.value = true
  }
}

// After student reviews the report and confirms submission
async function finalizeAssignmentSubmit() {
  assignmentSubmitting.value = true
  
  const token = localStorage.getItem('auth_token')
  const content = getEditorContentForSubmission()
  const reportData = assignmentReportData.value
  
  try {
    // Step 1: Upload the report HTML separately (as text/html to bypass JSON size limit)
    // CRITICAL: Add CSS overrides to make the report displayable standalone.
    // The editor page sets `html, body { overflow: hidden; height: 100vh; }` which
    // gets copied into the report HTML via getStylesHtml(). Without overrides,
    // the report is unscrollable and appears corrupted for teachers/students.
    const reportOverrideStyles = `<style id="standalone-report-overrides">
      html, html[theme-mode] {
        overflow-y: auto !important;
        overflow-x: hidden !important;
        height: auto !important;
        min-height: 100% !important;
      }
      body, body.umo-editor-container, body.is-print {
        padding: 40px !important;
        max-width: 900px !important;
        margin: 0 auto !important;
        background: #f5f5f5 !important;
        min-height: auto !important;
        height: auto !important;
        overflow: visible !important;
        overflow-y: auto !important;
      }
      .editor-page-container, .editor-fullscreen, .umo-editor-container {
        position: static !important;
        height: auto !important;
        overflow: visible !important;
      }
      .editor-container {
        background: white !important;
        padding: 40px !important;
        border-radius: 12px !important;
        box-shadow: 0 2px 8px rgba(0,0,0,0.1) !important;
        margin-bottom: 24px !important;
        height: auto !important;
        overflow: visible !important;
      }
      .integrity-report-page, .timeline-report-page {
        background: white !important;
        border-radius: 12px !important;
        overflow: visible !important;
        box-shadow: 0 2px 8px rgba(0,0,0,0.1) !important;
        margin-bottom: 24px !important;
      }
      .toolbar, .floating-menu, .canvas-controls, .zoom-controls,
      .umo-toolbar, .umo-bubble-menu, .statusbar {
        display: none !important;
      }
    </style>`
    
    // Researchers store the stylometry-only report (no trust score); students
    // store the full integrity report exactly as before.
    let uploadHtml = isResearcherMode.value
      ? buildResearcherStylometryReport(reportData, researcherPreviewAuthors.value)
      : reportData.reportHtml
    if (uploadHtml.includes('</body>')) {
      uploadHtml = uploadHtml.replace('</body>', reportOverrideStyles + '</body>')
    } else if (uploadHtml.includes('</html>')) {
      uploadHtml = uploadHtml.replace('</html>', reportOverrideStyles + '</html>')
    } else {
      uploadHtml = uploadHtml + reportOverrideStyles
    }
    
    // FIX #7: Use header (axios interceptor adds Bearer), not query param
    await axios.post(
      `${ASSIGN_API}/api/submissions/${assignmentSubmissionId.value}/upload-report`,
      uploadHtml,
      { headers: { 'Content-Type': 'text/html; charset=utf-8' } }
    )
    
    // Step 2: Upload session playback snapshots (keyed by submission_id for teacher playback)
    try {
      const assignmentId = route.query.assignment_id
      // Flush any unsynced edit events FIRST — the snapshot upload below
      // links every synced event chunk to this submission server-side.
      await syncEvents(assignmentId, currentUserId.value)
      const playbackData = await exportSnapshots(assignmentId, currentUserId.value)
      if (playbackData && playbackData.snapshots?.length > 0) {
        await axios.post(
          `${ASSIGN_API}/api/session-playback/${assignmentSubmissionId.value}`,
          playbackData
        )
        // Clear THIS user's local data now that it is persisted server-side.
        // (userId-scoped: never wipe another user's recording on a shared browser)
        await clearSnapshots(assignmentId, currentUserId.value)
        await clearEvents(assignmentId, currentUserId.value)
      }
    } catch (e) {
      console.warn('Session playback upload failed (non-critical):', e.message)
    }

    // Step 3: Submit the assignment (JSON body without the large report_html)
    const submitResp = await axios.post(`${ASSIGN_API}/api/submissions/${assignmentSubmissionId.value}/submit`, {
      content: content,
      content_html: content,
      session_id: sessionId.value,
      integrity_data: {
        trust_score: reportData.baseTrustScore ?? reportData.trustScore,
        content_mix: reportData.contentMix,
        flags: reportData.flags,
        face_verification_log: faceVerificationLog.value,
        analysis: reportData.analysis,
        external_pastes_found: reportData.externalPastesFound,
        stylometry: reportData.stylometry ? {
          verified: reportData.stylometry.verified,
          score: reportData.stylometry.score,
          similarity: reportData.stylometry.score ?? reportData.stylometry.similarity,
          verdict: reportData.stylometry.verdict,
          confidence: reportData.stylometry.confidence,
          probability: reportData.stylometry.probability,
          cosine_score: reportData.stylometry.cosine_score,
          version: reportData.stylometry.version || 'v3',
        } : null,
        ai_detection: reportData.aiDetection ? {
          ai_probability: reportData.aiDetection.ai_probability,
          predicted_class: reportData.aiDetection.predicted_class,
          status: reportData.aiDetection.status || (reportData.aiDetection.skipped ? 'skipped' : null)
        } : null,
        chunk_analysis: reportData.chunkAnalysis || null
      }
    })

    // Step 4 (researcher reports): per-author stylometry + contribution.
    // Collaborative reports split the merged Yjs doc by authorship marks;
    // a single-author report attributes the whole document to its author so
    // its stylometry verdict + word count still render on the results page.
    if (isResearcherMode.value && editorRef?.editor) {
      try {
        let segments = []
        if (isCollabMode.value) {
          segments = getAuthorSegments(editorRef.editor)
            .filter(s => s.uid && s.uid !== 'unknown')
            .map(s => ({ user_id: s.uid, text: s.text }))
        }
        // Fall back to the whole document under the submitting author when
        // there are no authorship marks (single-author, or an unmarked doc).
        if (!segments.length && currentUserId.value) {
          segments = [{ user_id: currentUserId.value, text: editorRef.editor.getText() || '' }]
        }
        if (segments.length) {
          const sid = assignmentSubmissionId.value
          await Promise.allSettled([
            axios.post(`${ASSIGN_API}/api/research/submissions/${sid}/verify-authors`, { segments }),
            axios.post(`${ASSIGN_API}/api/research/submissions/${sid}/compute-contributions`, { segments }),
          ])
        }
      } catch (e) {
        console.warn('Per-author analysis failed (non-critical):', e.message)
      }
    }

    assignmentSubmitting.value = false
    showAssignmentReportPreview.value = false

    // Clear auto-save + the local draft backup (it's submitted now)
    if (assignmentAutoSaveTimer) clearInterval(assignmentAutoSaveTimer)
    assignmentContentChanged = false
    try { localStorage.removeItem(draftLocalKey()) } catch { /* ignore */ }

    // Individual signals from the submit response (only present in legacy
    // mode); fall back to the client-side report data when hidden.
    const trustScore = submitResp.data?.trust_score ?? reportData.baseTrustScore ?? reportData.trustScore ?? null
    const styloVerdict = submitResp.data?.stylometry_verdict ?? reportData.stylometry?.verdict ?? null
    const aiProbability = submitResp.data?.ai_probability ?? reportData.aiDetection?.ai_probability ?? null
    const flags = submitResp.data?.flags || []
    const isLate = submitResp.data?.is_late || false
    submissionResultData.value = { trustScore, styloVerdict, aiProbability, flags, isLate }
    showSubmissionResult.value = true
  } catch (e) {
    assignmentSubmitting.value = false
    const errMsg = e.response?.data?.detail || e.message || 'Unknown error'
    alert('Submission failed: ' + errMsg)
  }
}

function cancelReportPreview() {
  showAssignmentReportPreview.value = false
  assignmentReportHtml.value = ''
  assignmentReportData.value = null
}

/**
 * Block a researcher from the editor until they've completed stylometry
 * enrollment in the topic's lab. Runs on every editor mount; redirects to
 * enrollment (returning here afterwards) when not enrolled. Fail-open on
 * transient errors so a network blip never locks out an enrolled user.
 */
// A collaborative report's content lives ONLY in the shared Yjs document,
// which loads exclusively when the editor is in collab mode (?collab=1). If a
// shared report is opened without it (direct link, LMS, a navigation that
// dropped the param), the editor binds to the per-user draft instead and the
// shared content appears lost. Detect is_shared and reload with collab=1 so the
// editor always binds to Yjs for collaborative reports.
async function enforceCollabForSharedReport() {
  if (route.query.collab === '1') return
  const aid = route.query.assignment_id
  if (!aid) return
  if (!authUser.value) { try { await initAuth() } catch { return } }
  if (authUser.value?.role !== 'researcher') return
  try {
    // Key collab off the TOPIC, not the per-user submission: a co-author's own
    // submission has is_shared=False, which would otherwise leave them in solo
    // mode while the creator is in the shared Yjs doc — they'd never see each
    // other's work. If the topic is collaborative, every participant joins Yjs.
    const { data } = await axios.get(`${ASSIGN_API}/api/research/topics/${aid}/collab-status`)
    if (data && data.collaborative) {
      const url = new URL(window.location.href)
      url.searchParams.set('collab', '1')
      window.location.replace(url.toString()) // full reload so the editor re-inits in collab
    }
  } catch { /* not a research topic / unreachable — leave as-is */ }
}

async function enforceResearcherStylometryGate() {
  if (!authUser.value) {
    try { await initAuth() } catch { return }
  }
  if (authUser.value?.role !== 'researcher') return
  const labId = route.query.class_id
  if (!labId) return
  try {
    const { data } = await axios.get(`${ASSIGN_API}/api/research/enrollment/${labId}`)
    if (data && data.enrolled === false) {
      const topic = encodeURIComponent(assignmentData.value?.title || '')
      const back = encodeURIComponent(route.fullPath)
      router.replace(`/researcher/stylometry-enrollment/${labId}?topic=${topic}&next=${back}`)
    }
  } catch { /* fail-open: create-flow gate + submit-time verdict still apply */ }
}

async function loadAssignmentContext() {
  if (!isAssignmentMode.value) {
    integrityStateReady.value = true  // No server restore needed
    return
  }
  if (!localStorage.getItem('auth_token')) {
    integrityStateReady.value = true
    return
  }


  // =========================================================================
  // CLEAR STALE STATE from any previous assignment.
  // This runs BEFORE IntegrityTracker mounts (gated by integrityStateReady),
  // so nulling globals is safe — IntegrityTracker will reinitialize fresh,
  // or _hydrateIntegrityGlobals() will restore from server for THIS assignment.
  //
  // NOTE: IntegrityTracker freezes these with Object.defineProperty(writable:false)
  // so we CANNOT reassign them. Instead, clear their contents in-place.
  // =========================================================================

  if (window.TYPED_DB) {
    window.TYPED_DB.allTypedChars = ''; window.TYPED_DB.totalTypedCount = 0
    window.TYPED_DB.fingerprints = null; window.TYPED_DB.sessionStart = Date.now()
  }
  if (window.EXTERNAL_DB) {
    window.EXTERNAL_DB.pastes.length = 0; window.EXTERNAL_DB.totalPastedChars = 0
    window.EXTERNAL_DB.sessionStart = Date.now()
  }
  if (window.INTERNAL_DB) {
    window.INTERNAL_DB.pastes.length = 0; window.INTERNAL_DB.totalChars = 0
    window.INTERNAL_DB.copyBuffer.length = 0
  }
  if (window.TIMELINE_DB) {
    window.TIMELINE_DB.segments.length = 0; window.TIMELINE_DB.deletions = 0
    window.TIMELINE_DB.additions = 0; window.TIMELINE_DB.currentTypingStart = null
    window.TIMELINE_DB.currentTypingText = ''; window.TIMELINE_DB.lastKeystroke = Date.now()
  }
  if (window.AUTOTYPER_DB) {
    window.AUTOTYPER_DB.ikiBuffer.length = 0; window.AUTOTYPER_DB.lastKeystrokeTime = 0
    window.AUTOTYPER_DB.untrustedEventCount = 0; window.AUTOTYPER_DB.totalEventCount = 0
    window.AUTOTYPER_DB.analysisResult = null
  }
  window.PROVENANCE_TRACKER = null
  window.editorContentFromDatabase = null
  window.lastKnownEditorContent = null
  window.lastContentTimestamp = null

  // Reset Vue store integrity state so no stale scores/pastes carry over
  integrityState.value = {
    active: false,
    sessionId: null,
    docId: null,
    scores: { trust: null, composition: null },
    mix: { typed: 1.0, internal: 0, external: 0 },
    sessionMix: null,
    flags: [],
    devtoolsOpened: false,
    devtoolsTimestamp: null,
    extSpans: [],
    strictMode: false,
    lastAnalyzed: null,
    externalPastesFound: [],
    retypedExternalDetected: [],
    analysis: null
  }

  try {
    // Load assignment data
    const res = await axios.get(`${ASSIGN_API}/api/assignments/${route.query.assignment_id}`)
    assignmentData.value = res.data
    assignmentDataLoaded.value = true

    // Stylometry needs class_id in the URL (print.vue reads it at submit).
    // Backfill it from the assignment if the link dropped it.
    if (route.query.assignment_id && !route.query.class_id && res.data?.class_id) {
      router.replace({ query: { ...route.query, class_id: res.data.class_id } })
    }

    // Sync teacher's tool toggles to global store so statusbar/IntegrityPanel can read them
    const s = res.data?.settings || {}
    assignmentToolSettings.value = {
      analyze_integrity_enabled: s.analyze_integrity_enabled !== false,
      gptzero_enabled: s.gptzero_enabled !== false,
      stylometry_enabled: s.stylometry_enabled !== false,
      face_verification_enabled: s.face_verification_enabled !== false,
      check_plagiarism: s.check_plagiarism !== false,
    }

    // If face verification disabled by teacher, auto-grant editor access
    if (s.face_verification_enabled === false && !faceVerified.value) {
      faceVerified.value = true
    }

    // Load class name (use the assignment's class_id when the URL lacked it —
    // the router.replace backfill above may not be reflected in route yet)
    const _classId = route.query.class_id || res.data?.class_id
    if (_classId) {
      try {
        const classRes = await axios.get(`${ASSIGN_API}/api/classes/${_classId}`)
        assignmentClassName.value = classRes.data.name || ''
      } catch (e) {
        console.warn('Failed to load class name:', e)
      }
    }

    // Shared-computer guard: if the locally-saved integrity state belongs to a
    // DIFFERENT user (previous login on this machine), drop it before any
    // arbitration — otherwise user B inherits user A's paste/typing databases.
    try {
      if (!authUser.value) await initAuth()
      const _ownerKey = `integrity_owner_${route.query.assignment_id}`
      const _prevOwner = localStorage.getItem(_ownerKey)
      if (currentUserId.value) {
        if (_prevOwner && _prevOwner !== currentUserId.value) {
          localStorage.removeItem(`integrity_session_${route.query.assignment_id}`)
          localStorage.removeItem(draftLocalKey())
          console.log('🔒 Cleared integrity/draft local state from previous user on this machine')
        }
        localStorage.setItem(_ownerKey, currentUserId.value)
      }
    } catch { /* storage unavailable */ }

    // Cross-browser integrity restore: fetch server-stored client_state
    try {
      const assignmentId = route.query.assignment_id
      const token = localStorage.getItem('auth_token')
      const lookupRes = await axios.get(
        `${ASSIGN_API}/api/integrity/session/lookup`,
        { params: { doc_id: assignmentId }, headers: { Authorization: `Bearer ${token}` } }
      )
      if (lookupRes.data.found && lookupRes.data.client_state) {
        const serverState = lookupRes.data.client_state
        // Only use server data if localStorage is older, missing, or EMPTY.
        // Critical: an empty localStorage with a newer timestamp must NEVER
        // beat server data that has real paste/typing info. This happens when
        // a student opens in a new browser — IntegrityTracker writes empty
        // state to localStorage before server hydration runs.
        const localKey = `integrity_session_${assignmentId}`
        const localRaw = localStorage.getItem(localKey)
        let useServer = true
        if (localRaw) {
          try {
            const local = JSON.parse(localRaw)
            // IntegrityTracker discards local state older than 24h at restore
            // time — treat it as empty here too, so an expired local snapshot
            // can never block hydration from the server (which has no TTL).
            const localExpired = !local.ts || (Date.now() - local.ts > 24 * 60 * 60 * 1000)
            const localHasData = !localExpired && (
                                 (local.TYPED_DB?.totalTypedCount > 0) ||
                                 (local.EXTERNAL_DB?.pastes?.length > 0) ||
                                 (local.TIMELINE_DB?.segments?.length > 0))
            const serverHasData = (serverState.TYPED_DB?.totalTypedCount > 0) ||
                                  (serverState.EXTERNAL_DB?.pastes?.length > 0) ||
                                  (serverState.TIMELINE_DB?.segments?.length > 0)

            if (!localHasData && serverHasData) {
              // Empty localStorage, server has real data — ALWAYS use server
              console.log('🔄 localStorage is empty but server has data — using server')
              useServer = true
            } else if (localHasData && !serverHasData) {
              // Local has data, server is empty — keep local
              console.log('📦 localStorage has data, server is empty — keeping local')
              useServer = false
            } else if (local.ts > (serverState.ts || 0) && localHasData) {
              // Both have data, local is newer — keep local
              console.log('📦 localStorage is newer with real data, skipping server restore')
              useServer = false
            } else if (!localHasData && !serverHasData) {
              // Both empty — skip server call
              console.log('📦 Both empty, skipping server restore')
              useServer = false
            }
            // else: server is newer or same age with data — use server (default)
          } catch { /* corrupted localStorage, use server */ }
        }
        if (useServer) {
          _hydrateIntegrityGlobals(serverState)
          // Only set sessionId if not already set by index.vue — overwriting
          // triggers IntegrityTracker's session-switch watcher which wipes
          // the databases we just hydrated.
          if (!integrityState.value) integrityState.value = {}
          if (!integrityState.value.sessionId) {
            integrityState.value.sessionId = lookupRes.data.session_id
          }
          integrityState.value.docId = assignmentId
        }
      }
    } catch (e) {
      console.warn('⚠️ Server integrity restore failed, falling back to localStorage:', e)
    }
    // Allow IntegrityTracker to mount now
    integrityStateReady.value = true

    // Check for existing submission (draft)
    try {
      const subRes = await axios.get(
        `${ASSIGN_API}/api/assignments/${route.query.assignment_id}/my-submission`
      )
      const sub = subRes.data.submission
      if (sub) {
        assignmentSubmissionId.value = sub.submission_id
        if (sub.status === 'submitted' || sub.status === 'graded' || sub.status === 'returned') {
          // Already submitted — researchers land on their deliverables page
          if (!isResearcherMode.value) {
            alert('This assignment has already been submitted.')
          }
          router.replace(submissionResultPath(sub.submission_id))
          return
        }
      }
      // Reconcile the SERVER draft (the cross-browser source of truth) with the
      // local backup (a same-browser instant net) — whichever is NEWER wins, so
      // editing in another browser is never overwritten by a stale local copy.
      const serverContent = (sub && (sub.content_html || sub.content)) || ''
      const serverTs = (sub && sub.updated_at) ? Date.parse(sub.updated_at) : 0
      const serverHas = serverContent.replace(/<[^>]*>/g, '').trim().length > 0
      const local = readLocalDraft()  // { html, ts } | null
      // Clock-skew guard: a local ts from the future (bad client clock) must
      // not let a stale local backup beat a genuinely newer server draft.
      if (local && local.ts > Date.now() + 60000) local.ts = 0
      let best = ''
      if (local && (!serverHas || local.ts >= serverTs)) best = local.html
      else if (serverHas) best = serverContent
      // Rescue whichever non-empty draft LOST the reconcile, so a mis-pick is
      // never unrecoverable (next autosave overwrites the server copy).
      try {
        const loser = (best === (local && local.html)) ? (serverHas ? serverContent : '') : (local ? local.html : '')
        if (loser && loser !== best && loser.replace(/<[^>]*>/g, '').trim()) {
          localStorage.setItem(draftLocalKey() + '_rescued', JSON.stringify({ html: loser, ts: Date.now() }))
        }
      } catch { /* ignore */ }
      if (best && best.replace(/<[^>]*>/g, '').trim()) {
        window.editorContentFromDatabase = best
        restoreDraftIfNeeded()
      }
    } catch (e) {
      // my-submission failed — fall back to the local backup so nothing is lost.
      const local = readLocalDraft()
      if (local) { window.editorContentFromDatabase = local.html; restoreDraftIfNeeded() }
    }
    
    // Auto-save every 10 seconds (reduced from 30s to minimise data loss)
    assignmentAutoSaveTimer = setInterval(() => {
      if (assignmentContentChanged) {
        autoSaveAssignmentDraft()
      }
    }, 10000)
    
    // Track content changes and debounce a save 3s after last keystroke
    let draftDebounce = null
    const trackChanges = () => {
      assignmentContentChanged = true
      backupDraftLocally()         // instant, synchronous local backup of live content
      clearTimeout(draftDebounce)
      draftDebounce = setTimeout(() => {
        autoSaveAssignmentDraft()
      }, 1500)
    }
    document.addEventListener('keydown', trackChanges)
    // keydown misses mouse/context-menu paste and drag-drop. The editor's
    // 'update' event is the authoritative change signal — it fires on EVERY
    // content change (typed, pasted by any method, dropped, deleted), so the
    // draft is always marked dirty and gets saved/flushed on navigation.
    document.addEventListener('paste', trackChanges, true)
    const _attachDraftUpdate = (ed) => {
      if (ed && !ed.isDestroyed) { ed.on('update', trackChanges); return true }
      return false
    }
    let _stopDraftWatch = null
    if (!_attachDraftUpdate(storeEditor.value)) {
      _stopDraftWatch = watch(storeEditor, (ed) => {
        if (_attachDraftUpdate(ed) && _stopDraftWatch) _stopDraftWatch()
      })
    }
    editorCleanupFunctions.push(() => {
      document.removeEventListener('keydown', trackChanges)
      document.removeEventListener('paste', trackChanges, true)
      if (storeEditor.value && !storeEditor.value.isDestroyed) storeEditor.value.off('update', trackChanges)
      if (_stopDraftWatch) _stopDraftWatch()
      clearTimeout(draftDebounce)
    })
    
  } catch (e) {
    console.error('Failed to load assignment:', e)
    integrityStateReady.value = true  // Always allow IntegrityTracker to mount
  }
}
const selectedMode = computed(() => {
  const selectmodule = route.query.selectmodule
  if (selectmodule === 'blank') return 'blank-template'
  if (selectmodule === 'paper') return 'paper-template'
  if (selectmodule === 'essay') return 'essay'
  if (selectmodule === 'tok_essay') return 'tok-essay'
  if (selectmodule === 'tok') return 'tok'
  if (selectmodule === 'tok-exhibition') return 'tok-exhibition'
  return 'none'
})

const anynumber = route.params.anynumber
console.log('Dynamic anynumber param:', anynumber)
const editorRef = $ref(null)
const templates = computed(() => [
  {
    title: t('templates.workTask.title'),
    description: t('templates.workTask.description'),
    content: t('templates.workTask.content'),
  },
  {
    title: t('templates.weeklyReport.title'),
    description: t('templates.weeklyReport.description'),
    content: t('templates.weeklyReport.content'),
  },
])
// Save cursor position whenever it changes
const saveCursorPosition = (editor) => {
  if (editor && editor.view && editor.view.state) {
    const { from, to } = editor.view.state.selection
    const doc = editor.view.state.doc
    const maxPos = doc.content.size
    
    // Only save valid cursor positions (not at position 0 which is outside content)
    if (from >= 1 && to >= 1 && from <= maxPos && to <= maxPos) {
      const cursorData = {
        from,
        to,
        timestamp: Date.now()
      }
      localStorage.setItem('editor.cursor', JSON.stringify(cursorData))
    }
  }
}

// Dynamic cursor position finder that works across all systems
const findOptimalCursorPosition = (doc) => {
  if (!doc || doc.content.size === 0) {
    return { from: 1, to: 1 }
  }
  
  // Helper function to find first editable position recursively
  const findFirstEditablePosition = (node, startPos = 1) => {
    let currentPos = startPos
    
    if (node.type.name === 'page') {
      // For page nodes, look inside the page content
      currentPos += 1 // Account for page opening
      if (node.content && node.content.size > 0) {
        const result = findFirstEditablePosition(node.content, currentPos)
        if (result) return result
      }
      // If page is empty, position at the start of page content
      return currentPos
    }
    
    if (node.content) {
      // This is a Fragment or has child content
      for (let i = 0; i < node.childCount; i++) {
        const child = node.child(i)
        
        // Check if this child is a text block where we can place cursor
        if (child.isTextblock && child.type.name !== 'codeBlock') {
          // Position at the start of text content, accounting for opening tag
          return currentPos + 1
        }
        
        // For other content types, recurse into them
        if (child.content && child.content.size > 0) {
          const result = findFirstEditablePosition(child, currentPos + 1)
          if (result) return result
        }
        
        currentPos += child.nodeSize
      }
    }
    
    // If no specific position found, return the start position
    return startPos
  }
  
  let optimalPos = findFirstEditablePosition(doc)
  
  // Ensure position is within bounds
  const maxPos = doc.content.size
  optimalPos = Math.max(1, Math.min(optimalPos, maxPos))
  
  return { from: optimalPos, to: optimalPos }
}

// Restore cursor position with MS Word-like default behavior
const restoreCursorPosition = (editor) => {
  try {
    if (!editor || !editor.view) return
    
    const savedCursor = localStorage.getItem('editor.cursor')
    const doc = editor.view.state.doc
    const maxPos = doc.content.size
    
    let targetFrom = null
    let targetTo = null
    
    // Try to restore saved cursor position
    if (savedCursor) {
      try {
        const cursorData = JSON.parse(savedCursor)
        
        // Don't restore if cursor data is too old (more than 1 hour)
        if (Date.now() - cursorData.timestamp <= 60 * 60 * 1000) {
          // Ensure positions are within document bounds and valid
          if (cursorData.from >= 1 && cursorData.from <= maxPos && 
              cursorData.to >= 1 && cursorData.to <= maxPos) {
            targetFrom = cursorData.from
            targetTo = cursorData.to
          }
        }
      } catch (parseError) {
        console.warn('Failed to parse saved cursor position:', parseError)
      }
    }
    
    // If no valid saved cursor, find optimal position dynamically
    if (targetFrom === null) {
      const optimalPos = findOptimalCursorPosition(doc)
      targetFrom = optimalPos.from
      targetTo = optimalPos.to
    }
    
    // Ensure positions are within valid bounds and never at position 0
    targetFrom = Math.max(1, Math.min(targetFrom, maxPos || 1))
    targetTo = Math.max(1, Math.min(targetTo, maxPos || 1))
    
    // Set cursor position
    editor.commands.setTextSelection({ from: targetFrom, to: targetTo })
    
    // Scroll to cursor position after a short delay
    setTimeout(() => {
      try {
        editor.commands.focus()
        if (editor.commands.scrollIntoView) {
          editor.commands.scrollIntoView()
        }
      } catch (scrollError) {
        console.warn('Failed to scroll cursor into view:', scrollError)
      }
    }, 100)
    
  } catch (error) {
    console.warn('Failed to restore cursor position:', error)
    // Ultimate fallback - find optimal position dynamically
    try {
      if (editor && editor.commands) {
        const doc = editor.view.state.doc
        const optimalPos = findOptimalCursorPosition(doc)
        editor.commands.setTextSelection(optimalPos.from)
        editor.commands.focus()
      }
    } catch (fallbackError) {
      console.warn('Ultimate fallback cursor positioning failed:', fallbackError)
    }
  }
}

// Debounced save functionality
let saveTimeout = null;
const SAVE_DELAY = 2000; // 2 seconds after user stops typing

const debouncedSave = async (content) => {
  // Cancel previous save if user is still typing
  if (saveTimeout) {
    clearTimeout(saveTimeout);
    console.log('⏰ Previous save cancelled - user still typing');
  }
  
  // Set new save after delay
  saveTimeout = setTimeout(async () => {
    console.log('💾 Debounced save triggered after user stopped typing');
    
    if (window.saveDocumentFromEditor && typeof window.saveDocumentFromEditor === 'function') {
      try {
        await window.saveDocumentFromEditor(content);
        console.log('✅ Debounced save completed');
      } catch (error) {
        console.warn('⚠️ Debounced save failed:', error);
      }
    }
    
    saveTimeout = null;
  }, SAVE_DELAY);
  
  console.log(`⏰ Debounced save scheduled in ${SAVE_DELAY/1000} seconds`);
};

const onSave = async (content, page, document) => {
  console.log('🔄 onSave called with content length:', document?.content?.length || 0);
  
  // Store content in memory for immediate access
  if (document?.content) {
    window.editorContentFromDatabase = document.content;
    console.log('✅ Content stored in memory cache');
    
    // Trigger debounced save
    debouncedSave(document.content);
  }
  
  // Save cursor position when saving
  if (editorRef?.editor) {
    saveCursorPosition(editorRef.editor);
  }
  
  return new Promise((resolve, reject) => {
    setTimeout(() => {
      const success = true;
      if (success) {
        console.log('✅ onSave completed');
        resolve('保存成功');
      } else {
        reject('保存失败');
      }
    }, 100);
  });
}
// Watch for cursor position changes and save them
const setupCursorTracking = () => {
  if (editorRef?.editor) {
    const editor = editorRef.editor
    
    // Track cursor changes with debouncing to avoid excessive saves
    let saveTimeout
    const debouncedSave = () => {
      clearTimeout(saveTimeout)
      saveTimeout = setTimeout(() => {
        saveCursorPosition(editor)
      }, 500) // Save after 500ms of no cursor movement
    }
    
    // Listen for selection changes
    editor.on('selectionUpdate', debouncedSave)
    
    // Also save on focus/blur to catch manual cursor placement
    editor.on('focus', debouncedSave)
    
    // Store timeout IDs for cleanup
    const timeoutIds = []
    
    // Restore cursor position when editor is ready
    // Wait for editor to be fully initialized
    const timeout1 = setTimeout(() => {
      if (editor && editor.view && !editor.isDestroyed) {
        restoreCursorPosition(editor)
      }
    }, 800)
    timeoutIds.push(timeout1)
    
    // Additional restoration attempt for slow loading
    const timeout2 = setTimeout(() => {
      if (editor && editor.view && !editor.isDestroyed) {
        restoreCursorPosition(editor)
      }
    }, 1500)
    timeoutIds.push(timeout2)
    
    // Cleanup function for unmount
    const cleanup = () => {
      clearTimeout(saveTimeout)
      timeoutIds.forEach(id => clearTimeout(id))
      editor.off('selectionUpdate', debouncedSave)
      editor.off('focus', debouncedSave)
    }
    
    // Store cleanup function for later use
    editorCleanupFunctions.push(cleanup)
  }
}

// Store cleanup functions
const editorCleanupFunctions = []

const options = $ref({
  toolbar: {
    // defaultMode: 'classic',
    // menus: ['base'],
    enableSourceEditor: true,
  },
  document: {
    // title: '测试文档',
    content: '',
    autofocus: false, // Disable autofocus so we can control cursor position manually
  },
  templates,
  cdnUrl: 'https://cdn.umodoc.com',
  shareUrl: 'https://umodoc.com',
  file: {
    // allowedMimeTypes: [
    //   'application/pdf',
    //   'image/svg+xml',
    //   'video/mp4',
    //   'audio/*',
    // ],
  },
  assistant: {
    enabled: true,
  },
  async onFileUpload(file) {
    if (!file) throw new Error('没有找到要上传的文件')
    console.log('onUpload', file)
    await new Promise((resolve) => setTimeout(resolve, 3000))
    return {
      id: shortId(),
      url: file.url || URL.createObjectURL(file),
      name: file.name,
      type: file.type,
      size: file.size,
    }
  },
  async onCustomImportWordMethod(file) {
    return {
      value: '<p>测试导入word</p>',
    }
  },
})

// Setup cursor tracking when editor is ready
watch(() => editorRef?.editor, (editor) => {
  if (editor) {
    setupCursorTracking()
    // Robustly re-inject the draft the moment the editor is ready.
    restoreDraftIfNeeded()
    editor.on('create', () => restoreDraftIfNeeded())

    // Check if database content is already available and load it
    setTimeout(() => {
      if (window.editorContentFromDatabase) {
        loadContentFromDatabase();
      }
    }, 200);
    
    // Also setup a listener for when the editor content is ready
    editor.on('create', () => {
      // Prevent any automatic focus to position 0
      setTimeout(() => {
        if (editor && editor.view && !editor.isDestroyed) {
          restoreCursorPosition(editor)
        }
      }, 100)
      
      // Additional check after a longer delay to ensure cursor doesn't jump to 0
      setTimeout(() => {
        if (editor && editor.view && !editor.isDestroyed) {
          const { from } = editor.view.state.selection
          if (from === 0) {
            console.warn('Cursor detected at position 0, correcting...')
            restoreCursorPosition(editor)
          }
        }
      }, 500)
    })
    
    // Listen for focus events and prevent cursor from going to position 0
    editor.on('focus', () => {
      setTimeout(() => {
        if (editor && editor.view && !editor.isDestroyed) {
          const { from } = editor.view.state.selection
          if (from === 0) {
            console.warn('Cursor at position 0 on focus, correcting...')
            restoreCursorPosition(editor)
          }
        }
      }, 10)
    })
    
    // Handle document changes to prevent cursor from going to invalid positions
    // BUT don't interfere with pagination operations
    const handleEditorUpdate = ({ editor, transaction }) => {
      try {
        // Skip cursor correction during pagination operations
        const isPaginationUpdate = transaction.getMeta('runPaginationOnUpdate') || 
                                  transaction.getMeta('checkPagination') || 
                                  transaction.getMeta('forcePagination') ||
                                  transaction.getMeta('inserting') ||
                                  transaction.getMeta('deleting')
        
        if (isPaginationUpdate) {
          return // Let pagination complete without cursor interference
        }
        
        setTimeout(() => {
          try {
            if (editor && editor.view && !editor.isDestroyed) {
              const { from, to } = editor.view.state.selection
              const doc = editor.view.state.doc
              
              // Check if cursor is at invalid position after content changes
              if (from <= 0 || to <= 0 || from > doc.content.size) {
                const optimalPos = findOptimalCursorPosition(doc)
                editor.commands.setTextSelection({ from: optimalPos.from, to: optimalPos.to })
                editor.commands.focus()
              }
            }
          } catch (error) {
            console.warn('Error in cursor position update:', error)
          }
        }, 50) // Longer delay to let pagination complete
      } catch (error) {
        console.warn('Error in editor update handler:', error)
      }
    }
    
    editor.on('update', handleEditorUpdate)
    
    // Store the handler for cleanup
    editorCleanupFunctions.push(() => {
      editor.off('update', handleEditorUpdate)
    })
  }
}, { immediate: true })

// Save cursor position when page is about to unload
onBeforeUnmount(() => {
  // Remove editor-active class so other pages can scroll
  document.documentElement.classList.remove('editor-active')
  document.body.classList.remove('editor-active')
  
  if (editorRef?.editor) {
    saveCursorPosition(editorRef.editor)
  }
  
  // Clear any pending debounced save
  if (saveTimeout) {
    clearTimeout(saveTimeout);
    console.log('🧹 Cleared pending debounced save on unmount');
  }
  
  // Clear assignment auto-save timer
  if (assignmentAutoSaveTimer) {
    clearInterval(assignmentAutoSaveTimer)
  }
  // Clear global callback
  window._assignmentSubmitCallback = null
  // Final save on SPA navigation (onBeforeUnmount fires for route changes)
  if (isAssignmentMode.value && assignmentContentChanged) {
    emergencySaveDraft()
  }
  
  // Clean up all editor-related resources
  editorCleanupFunctions.forEach(cleanup => {
    try {
      cleanup()
    } catch (error) {
      console.warn('Error during editor cleanup:', error)
    }
  })
  editorCleanupFunctions.length = 0
})

// Function to load content from database with retry prevention
const loadContentFromDatabase = (() => {
  let retryCount = 0;
  const maxRetries = 10;
  let isLoading = false;
  
  return () => {
    // Never inject into a collaborative editor — Yjs owns the document and
    // setContent would clear/overwrite the shared content (and sync the wipe).
    if (route.query.collab === '1') return false
    // Never wipe content the user already typed — this legacy injector does
    // clearContent()+setContent() and would erase early keystrokes (e.g. the
    // first second after the face-verification gate unlocks).
    if (editorRef?.editor && !editorRef.editor.isDestroyed && (editorRef.editor.getText() || '').trim().length > 0) {
      console.log('⏭️ loadContentFromDatabase skipped — user content already present');
      return true;
    }
    console.log('🔄 loadContentFromDatabase called');
    console.log('editorRef exists:', !!editorRef);
    console.log('editorRef.editor exists:', !!editorRef?.editor);
    console.log('window.editorContentFromDatabase exists:', !!window.editorContentFromDatabase);
    console.log('Current retry count:', retryCount);
    
    if (isLoading) {
      console.log('⚠️ Already loading, skipping...');
      return false;
    }
    
    if (!window.editorContentFromDatabase) {
      console.log('❌ No content to load from database');
      return false;
    }

    // Try different ways to check if editor is ready
    const editorElement = document.querySelector('.umo-editor .ProseMirror') || 
                         document.querySelector('.ProseMirror');
    
    if (!editorRef?.editor && !editorElement) {
      if (retryCount >= maxRetries) {
        console.log('❌ Max retries reached, giving up');
        retryCount = 0; // Reset for future attempts
        return false;
      }
      
      console.log(`⚠️ Editor not ready, will retry... (${retryCount + 1}/${maxRetries})`);
      retryCount++;
      isLoading = true;
      
      // Retry after editor is ready
      setTimeout(() => {
        isLoading = false;
        loadContentFromDatabase();
      }, 300 * retryCount); // Increasing delay
      return false;
    }

    try {
      console.log('✅ Loading content from database, length:', window.editorContentFromDatabase.length);
      console.log('Content preview:', window.editorContentFromDatabase.substring(0, 100) + '...');
      
      isLoading = true;
      let contentLoaded = false;
      
      // Method 1: Try editor instance if available
      if (editorRef?.editor && !editorRef.editor.isDestroyed) {
        try {
          editorRef.editor.commands.clearContent();
          editorRef.editor.commands.setContent(window.editorContentFromDatabase);
          contentLoaded = true;
          console.log('✅ Content loaded via editor instance');
        } catch (error) {
          console.warn('⚠️ Editor instance method failed:', error);
        }
      }
      
      // Method 2: Try component methods if available
      if (!contentLoaded && editorRef && typeof editorRef.setContent === 'function') {
        try {
          editorRef.setContent(window.editorContentFromDatabase);
          contentLoaded = true;
          console.log('✅ Content loaded via component method');
        } catch (error) {
          console.warn('⚠️ Component method failed:', error);
        }
      }
      
      // Method 3: Direct DOM manipulation as fallback
      if (!contentLoaded && editorElement) {
        try {
          editorElement.innerHTML = window.editorContentFromDatabase;
          contentLoaded = true;
          console.log('✅ Content loaded via DOM manipulation');
        } catch (error) {
          console.warn('⚠️ DOM manipulation failed:', error);
        }
      }
      
      if (contentLoaded) {
        // Restore cursor position after content is set
        setTimeout(() => {
          if (editorRef?.editor) {
            restoreCursorPosition(editorRef.editor);
          }
        }, 100);
        
        console.log('✅ Content loaded successfully into editor');
        retryCount = 0; // Reset retry count on success
        isLoading = false;
        return true;
      } else {
        throw new Error('All content loading methods failed');
      }
    } catch (error) {
      console.error('❌ Error loading content into editor:', error);
      isLoading = false;
      return false;
    }
  };
})();

// Function to get HTML content from editor
const getEditorHTMLContent = () => {
  // First try the editor instance if available
  if (editorRef?.editor && !editorRef.editor.isDestroyed) {
    try {
      return editorRef.editor.getHTML();
    } catch (error) {
      console.warn('Error getting HTML from editor:', error);
    }
  }
  
  // Try to get content from the editor component methods
  if (editorRef && typeof editorRef.getHTML === 'function') {
    try {
      return editorRef.getHTML();
    } catch (error) {
      console.warn('Error getting HTML from editor component:', error);
    }
  }
  
  // Fallback to DOM query
  const editorElement = document.querySelector('.umo-editor .ProseMirror') || 
                       document.querySelector('.ProseMirror');
  if (editorElement && editorElement.innerHTML) {
    return editorElement.innerHTML;
  }
  
  // Last resort: return cached content
  if (window.editorContentFromDatabase) {
    return window.editorContentFromDatabase;
  }
  
  return '';
};

// Expose functions globally so EditorLayout can call them
window.loadEditorContentFromDatabase = loadContentFromDatabase;
window.getEditorHTMLContent = getEditorHTMLContent;

// Watch for editor initialization to automatically load content
watch(() => editorRef?.editor, (newEditor) => {
  if (newEditor && window.editorContentFromDatabase) {
    console.log('🎯 Editor initialized and content available, loading...');
    setTimeout(() => {
      loadContentFromDatabase();
    }, 300); // Give editor a moment to fully initialize
  }
}, { immediate: true });

// Sync sessionId with the real backend session once the editor creates it.
// This ensures the submit call sends the correct session_id that the server knows.
watch(() => integrityState.value?.sessionId, (backendId) => {
  if (backendId && backendId !== sessionId.value) {
    console.log('🔗 Syncing sessionId to backend session:', backendId)
    sessionId.value = backendId
  }
}, { immediate: true })

// Also save cursor position when page is about to be unloaded (refresh/close)
onMounted(() => {
  // COLLAB GATE: shared reports must open in collab mode so the editor binds to
  // the shared Yjs doc (where the content lives), not the per-user draft. May
  // full-reload with ?collab=1; runs first so nothing else matters if it does.
  enforceCollabForSharedReport()

  // INTEGRITY GATE: a researcher must complete stylometry enrollment in this
  // topic's lab before the editor is usable. This is the single choke point all
  // entry paths pass through (create flow, dashboard click, direct URL, invite).
  enforceResearcherStylometryGate()

  // Hydrate auth user (role/user_id) on hard reloads — needed for researcher
  // exit paths and user-scoped snapshot keying. Fire-and-forget.
  if (!authUser.value) {
    initAuth().catch(() => {})
  }

  // Add editor-active class to html+body to enable overflow:hidden only for editor
  document.documentElement.classList.add('editor-active')
  document.body.classList.add('editor-active')
  
  // CRITICAL: Reset stale global state that could hide the statusbar/editor UI.
  // These persist across SPA navigations because useStore is createGlobalState.
  if (editorPage.value) {
    editorPage.value.preview = { enabled: false, laserPointer: true }
  }
  editorDestroyed.value = false

  // Load assignment context if in assignment mode
  loadAssignmentContext()
  
  const handleBeforeUnload = (e) => {
    if (editorRef?.editor) {
      saveCursorPosition(editorRef.editor)
    }
    // Save assignment draft content before tab close / hard refresh
    if (isAssignmentMode.value && assignmentContentChanged) {
      emergencySaveDraft()
      flushIntegrityClientState(true)
      // Show browser-native "unsaved changes" prompt
      e.preventDefault()
      e.returnValue = ''
    }
  }
  
  // Save when tab becomes hidden (user switches tab or minimises)
  const handleVisibilityChange = () => {
    if (document.visibilityState === 'hidden' && isAssignmentMode.value) {
      if (assignmentContentChanged) emergencySaveDraft()
      flushIntegrityClientState()
    }
  }

  // pagehide is the most reliable unload event on mobile / modern browsers.
  // Terminal event → force past the debounce so the FINAL state always ships.
  const handlePageHide = () => {
    if (isAssignmentMode.value) {
      if (assignmentContentChanged) emergencySaveDraft()
      flushIntegrityClientState(true)
    }
  }
  
  // Global keyboard handler for Ctrl+A to ensure proper cursor behavior
  const handleKeyDown = (event) => {
    if ((event.ctrlKey || event.metaKey) && event.key === 'a') {
      // Let the default behavior happen, but fix cursor positioning after
      setTimeout(() => {
        if (editorRef?.editor && editorRef.editor.view && !editorRef.editor.isDestroyed) {
          const { from, to } = editorRef.editor.state.selection
          const doc = editorRef.editor.state.doc
          
          // Ensure selection is properly bounded (never starting at 0)
          if (from === 0 && doc.content.size > 0) {
            const properFrom = Math.max(1, from)
            const properTo = Math.min(doc.content.size, to)
            editorRef.editor.commands.setTextSelection({ from: properFrom, to: properTo })
          }
        }
      }, 10)
    }
    
    // Handle backspace after select all
    if (event.key === 'Backspace' || event.key === 'Delete') {
      setTimeout(() => {
        if (editorRef?.editor && editorRef.editor.view && !editorRef.editor.isDestroyed) {
          const { from, to } = editorRef.editor.state.selection
          const doc = editorRef.editor.state.doc
          
          // If document is now empty or cursor is at invalid position, restore optimal position
          if (from <= 0 || to <= 0 || (from === to && doc.content.size === 0)) {
            // Document might be empty after delete, ensure we have minimal content
            if (doc.content.size === 0) {
              // Insert a paragraph to ensure document structure
              editorRef.editor.commands.setContent('<p></p>')
              setTimeout(() => {
                const optimalPos = findOptimalCursorPosition(editorRef.editor.state.doc)
                editorRef.editor.commands.setTextSelection(optimalPos.from)
                editorRef.editor.commands.focus()
                
                // Trigger pagination check after restoring cursor
                setTimeout(() => {
                  const tr = editorRef.editor.state.tr.setMeta('checkPagination', true)
                  editorRef.editor.view.dispatch(tr)
                }, 10)
              }, 5)
            } else {
              const optimalPos = findOptimalCursorPosition(doc)
              editorRef.editor.commands.setTextSelection(optimalPos.from)
              
              // Trigger pagination check after cursor positioning
              setTimeout(() => {
                const tr = editorRef.editor.state.tr.setMeta('checkPagination', true)
                editorRef.editor.view.dispatch(tr)
              }, 10)
            }
          }
        }
      }, 10)
    }
  }
  
  window.addEventListener('beforeunload', handleBeforeUnload)
  document.addEventListener('visibilitychange', handleVisibilityChange)
  window.addEventListener('pagehide', handlePageHide)
  document.addEventListener('keydown', handleKeyDown, true)
  
  onBeforeUnmount(() => {
    window.removeEventListener('beforeunload', handleBeforeUnload)
    document.removeEventListener('visibilitychange', handleVisibilityChange)
    window.removeEventListener('pagehide', handlePageHide)
    document.removeEventListener('keydown', handleKeyDown, true)
  })
})
</script>

<style>
/* Editor-specific: applied via .editor-active class on html+body (added/removed in script) */
html.editor-active,
body.editor-active {
  height: 100vh !important;
  overflow: hidden !important;
}

.editor-page-container {
  height: 100vh;
  width: 100%;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

/* Floating live-collaborators bar (collaborative reports) */
.collab-bar-float {
  position: fixed;
  top: 12px;
  right: 16px;
  z-index: 60;
}

/* The v-show wrapper must participate in flex layout and fill remaining space */
.editor-page-container > .editor-wrapper {
  flex: 1 !important;
  min-height: 0 !important;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

/* Editor layouts must fill remaining space (not hardcode 100vh).
   CRITICAL: The .editor-wrapper div sits between .editor-page-container
   and the editor layout components, so CSS child selectors (>) must go
   through .editor-wrapper, not directly from .editor-page-container. */
.editor-wrapper > .editor-fullscreen,
.editor-page-container > .editor-fullscreen {
  flex: 1 !important;
  height: auto !important;
  min-height: 0 !important;
  max-height: 100% !important;
  overflow: hidden;
}
.editor-wrapper > .editor-fullscreen > .editor-content-area,
.editor-page-container > .editor-fullscreen > .editor-content-area {
  height: 100% !important;
  max-height: 100% !important;
  min-height: 0 !important;
}
.editor-wrapper > .editor-container,
.editor-page-container > .editor-container {
  flex: 1 !important;
  height: auto !important;
  min-height: 0 !important;
  max-height: 100% !important;
  overflow: hidden;
}
/* Ensure the umo-editor-container inside also uses flex sizing */
.editor-wrapper .umo-editor-container {
  height: 100% !important;
  max-height: 100% !important;
  display: flex !important;
  flex-direction: column !important;
}
.editor-wrapper .umo-main {
  flex: 1 !important;
  min-height: 0 !important;
  overflow: auto !important;
}
.editor-wrapper .umo-footer {
  flex-shrink: 0 !important;
}

/* ========== ASSIGNMENT BAR ========== */
.assignment-bar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 6px 16px;
  background: #1a73e8;
  color: white;
  z-index: 1000;
  position: relative;
  flex-shrink: 0;
}

.assignment-bar-left {
  display: flex;
  align-items: center;
  gap: 10px;
  flex: 1;
}

.assignment-bar-back {
  width: 32px;
  height: 32px;
  border: none;
  background: rgba(255,255,255,0.15);
  border-radius: 50%;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  color: white;
  transition: background 0.2s;
}
.assignment-bar-back:hover { background: rgba(255,255,255,0.3); }

.assignment-bar-info {
  display: flex;
  flex-direction: column;
}

.assignment-bar-title {
  font-size: 14px;
  font-weight: 600;
  line-height: 1.2;
}

.assignment-bar-class {
  font-size: 11px;
  opacity: 0.8;
}

.assignment-bar-center {
  flex: 1;
  text-align: center;
}

.assignment-bar-status {
  font-size: 12px;
  opacity: 0.9;
}
.assignment-bar-status.saving { color: #fdd835; }
.assignment-bar-status.saved { color: #a5d6a7; }
.assignment-bar-status.error { color: #ef9a9a; }

.assignment-bar-right {
  display: flex;
  align-items: center;
  gap: 10px;
  flex: 1;
  justify-content: flex-end;
}

.assignment-bar-instructions-btn {
  display: flex;
  align-items: center;
  gap: 4px;
  padding: 5px 12px;
  background: rgba(255,255,255,0.15);
  border: none;
  border-radius: 6px;
  color: white;
  font-size: 12px;
  cursor: pointer;
  transition: background 0.2s;
}
.assignment-bar-instructions-btn:hover { background: rgba(255,255,255,0.3); }

.assignment-bar-invite-btn {
  display: flex;
  align-items: center;
  gap: 5px;
  padding: 5px 12px;
  background: rgba(255,255,255,0.95);
  border: none;
  border-radius: 6px;
  color: #7c3aed;
  font-size: 12px;
  font-weight: 600;
  cursor: pointer;
  transition: background 0.2s;
}
.assignment-bar-invite-btn:hover { background: #fff; }

.assignment-bar-due {
  font-size: 12px;
  padding: 3px 10px;
  border-radius: 12px;
  background: rgba(255,255,255,0.15);
}
.assignment-bar-due.urgent { background: #f9ab00; color: #000; }
.assignment-bar-due.past { background: #d93025; }

.assignment-bar-submit {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 6px 18px;
  background: white;
  color: #1a73e8;
  border: none;
  border-radius: 6px;
  font-weight: 600;
  font-size: 13px;
  cursor: pointer;
  transition: all 0.2s;
}
.assignment-bar-submit:hover:not(:disabled) { background: #e8f0fe; }
.assignment-bar-submit:disabled { opacity: 0.5; cursor: not-allowed; }

.assignment-bar-spinner {
  width: 14px;
  height: 14px;
  border: 2px solid rgba(26,115,232,0.3);
  border-top-color: #1a73e8;
  border-radius: 50%;
  animation: spin-assign 0.8s linear infinite;
}
@keyframes spin-assign { to { transform: rotate(360deg); } }

/* ========== ASSIGNMENT PANEL (side panel) ========== */
.assignment-panel-overlay {
  position: fixed;
  inset: 0;
  background: rgba(0,0,0,0.3);
  z-index: 9999;
}

.assignment-panel {
  position: fixed;
  top: 0;
  right: 0;
  width: 380px;
  max-width: 90vw;
  height: 100vh;
  background: white;
  box-shadow: -4px 0 20px rgba(0,0,0,0.15);
  display: flex;
  flex-direction: column;
  z-index: 10000;
  animation: slide-in-right 0.2s ease-out;
}
@keyframes slide-in-right {
  from { transform: translateX(100%); }
  to { transform: translateX(0); }
}

.assignment-panel-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 16px 20px;
  border-bottom: 1px solid #e0e0e0;
}
.assignment-panel-header h3 { margin: 0; font-size: 18px; color: #202124; }

.assignment-panel-close {
  width: 32px;
  height: 32px;
  border: none;
  background: transparent;
  border-radius: 50%;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  color: #5f6368;
}
.assignment-panel-close:hover { background: #f1f3f4; }

.assignment-panel-body {
  flex: 1;
  overflow-y: auto;
  padding: 20px;
}

.assignment-panel-section {
  margin-bottom: 20px;
}
.assignment-panel-section label {
  display: block;
  font-size: 12px;
  font-weight: 600;
  color: #5f6368;
  text-transform: uppercase;
  margin-bottom: 6px;
}
.assignment-panel-section p {
  margin: 0;
  font-size: 14px;
  color: #202124;
  line-height: 1.6;
  white-space: pre-wrap;
}

.assignment-panel-rubric {
  display: flex;
  flex-direction: column;
  gap: 6px;
}
.rubric-row {
  display: flex;
  justify-content: space-between;
  padding: 8px 12px;
  background: #f8f9fa;
  border-radius: 6px;
  font-size: 13px;
}
.rubric-name { color: #202124; }
.rubric-pts { color: #1a73e8; font-weight: 600; }

/* ========== ASSIGNMENT SUBMIT MODAL ========== */
.assignment-modal-overlay {
  position: fixed;
  inset: 0;
  background: rgba(0,0,0,0.6);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 10001;
}

.assignment-submit-modal {
  background: white;
  border-radius: 16px;
  padding: 32px;
  max-width: 420px;
  width: 90%;
  box-shadow: 0 20px 60px rgba(0,0,0,0.2);
}
.assignment-submit-modal h2 {
  margin: 0 0 8px;
  font-size: 22px;
  color: #202124;
}
.assignment-submit-modal p {
  margin: 0 0 20px;
  color: #5f6368;
  line-height: 1.5;
}

.assignment-submit-summary {
  display: flex;
  gap: 16px;
  margin-bottom: 20px;
}
.summary-stat {
  flex: 1;
  text-align: center;
  padding: 12px;
  background: #f8f9fa;
  border-radius: 8px;
}
.stat-label {
  display: block;
  font-size: 11px;
  color: #5f6368;
  text-transform: uppercase;
  margin-bottom: 4px;
}
.stat-value {
  font-size: 20px;
  font-weight: 600;
  color: #202124;
}

.assignment-late-note {
  padding: 10px;
  background: #fce8e6;
  border-radius: 8px;
  color: #d93025;
  font-size: 13px;
  text-align: center;
  margin-bottom: 20px;
}

.assignment-modal-actions {
  display: flex;
  gap: 12px;
}
.modal-btn-cancel {
  flex: 1;
  padding: 12px;
  border: 1px solid #dadce0;
  background: white;
  border-radius: 8px;
  font-weight: 500;
  color: #5f6368;
  cursor: pointer;
}
.modal-btn-cancel:hover { background: #f8f9fa; }

.modal-btn-submit {
  flex: 1;
  padding: 12px;
  border: none;
  background: #1a73e8;
  color: white;
  border-radius: 8px;
  font-weight: 600;
  cursor: pointer;
}
.modal-btn-submit:hover:not(:disabled) { background: #1557b0; }
.modal-btn-submit:disabled { opacity: 0.5; cursor: not-allowed; }

/* Report Preview Overlay */
.report-preview-overlay {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background: rgba(0,0,0,0.8);
  z-index: 99998;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 20px;
}
.report-preview-container {
  background: white;
  border-radius: 16px;
  width: 95vw;
  height: 92vh;
  max-width: 1200px;
  display: flex;
  flex-direction: column;
  overflow: hidden;
  box-shadow: 0 20px 60px rgba(0,0,0,0.4);
}
.report-preview-header {
  padding: 20px 24px 12px;
  border-bottom: 1px solid #e8eaed;
  flex-shrink: 0;
}
.report-preview-header h2 {
  margin: 0 0 4px 0;
  font-size: 20px;
  color: #1f2937;
}
.report-preview-header p {
  margin: 0;
  font-size: 14px;
  color: #5f6368;
}
.report-preview-frame {
  flex: 1;
  min-height: 0;
  overflow: auto;
}
.report-preview-iframe {
  width: 100%;
  height: 100%;
  border: none;
  overflow: auto;
}
.report-preview-actions {
  padding: 16px 24px;
  border-top: 1px solid #e8eaed;
  display: flex;
  gap: 12px;
  justify-content: flex-end;
  flex-shrink: 0;
}
.report-btn-cancel {
  padding: 12px 24px;
  border: 1px solid #dadce0;
  background: white;
  border-radius: 8px;
  font-weight: 500;
  color: #5f6368;
  cursor: pointer;
  font-size: 14px;
}
.report-btn-cancel:hover { background: #f8f9fa; }
.report-btn-submit {
  padding: 12px 32px;
  border: none;
  background: linear-gradient(135deg, #1a73e8, #1557b0);
  color: white;
  border-radius: 8px;
  font-weight: 600;
  cursor: pointer;
  font-size: 14px;
}
.report-btn-submit:hover:not(:disabled) { background: linear-gradient(135deg, #1557b0, #0d47a1); }
.report-btn-submit:disabled { opacity: 0.5; cursor: not-allowed; }

/* Submission Result Modal */
.submission-result-modal {
  background: white;
  border-radius: 16px;
  padding: 40px;
  max-width: 420px;
  width: 90%;
  text-align: center;
  box-shadow: 0 20px 60px rgba(0,0,0,0.3);
}
.result-icon {
  width: 72px;
  height: 72px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  margin: 0 auto 16px;
}
.result-icon.result-high { background: #e6f4ea; color: #1e8e3e; }
.result-icon.result-medium { background: #fef7e0; color: #f9ab00; }
.result-icon.result-low { background: #fce8e6; color: #d93025; }
.submission-result-modal h2 {
  margin: 0 0 20px;
  font-size: 22px;
  font-weight: 500;
  color: #202124;
}
.result-signals {
  display: flex;
  gap: 10px;
  justify-content: center;
  margin-bottom: 16px;
}
.result-signal {
  flex: 1;
  min-width: 0;
  padding: 12px 8px;
  border-radius: 10px;
  background: #f8f9fa;
}
.result-signal .signal-value {
  font-size: 20px;
  font-weight: 700;
  white-space: nowrap;
}
.result-signal .signal-label {
  font-size: 11px;
  color: #5f6368;
  font-weight: 500;
  margin-top: 4px;
  text-transform: uppercase;
  letter-spacing: 0.5px;
}
.result-signal.result-high { background: #e6f4ea; }
.result-signal.result-high .signal-value { color: #1e8e3e; }
.result-signal.result-medium { background: #fef7e0; }
.result-signal.result-medium .signal-value { color: #f9ab00; }
.result-signal.result-low { background: #fce8e6; }
.result-signal.result-low .signal-value { color: #d93025; }
.result-label {
  font-size: 14px;
  color: #5f6368;
  margin: 0 0 16px;
  font-weight: 500;
}
.result-late {
  background: #fce8e6;
  color: #d93025;
  padding: 8px 16px;
  border-radius: 8px;
  font-size: 13px;
  font-weight: 500;
  margin-bottom: 12px;
}
.result-flags {
  display: flex;
  flex-direction: column;
  gap: 6px;
  margin-bottom: 16px;
}
.result-flag {
  background: #fef7e0;
  color: #b06000;
  padding: 6px 12px;
  border-radius: 6px;
  font-size: 12px;
  text-align: left;
}
.result-note {
  font-size: 13px;
  color: #5f6368;
  line-height: 1.5;
  margin: 0 0 24px;
}
</style> 