<template>
  <!-- Only show verification modal if not yet verified -->
  <div class="face-verification-overlay" v-if="showVerification && !props.isVerified">
    <div class="verification-modal">
      <div class="modal-header">
        <div class="header-icon">
          <svg width="48" height="48" viewBox="0 0 24 24" fill="currentColor">
            <path d="M9 11.75c-.69 0-1.25.56-1.25 1.25s.56 1.25 1.25 1.25 1.25-.56 1.25-1.25-.56-1.25-1.25-1.25zm6 0c-.69 0-1.25.56-1.25 1.25s.56 1.25 1.25 1.25 1.25-.56 1.25-1.25-.56-1.25-1.25-1.25zM12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm0 18c-4.41 0-8-3.59-8-8 0-.29.02-.58.05-.86 2.36-1.05 4.23-2.98 5.21-5.37C11.07 8.33 14.05 10 17.42 10c.78 0 1.53-.09 2.25-.26.21.71.33 1.47.33 2.26 0 4.41-3.59 8-8 8z"/>
          </svg>
        </div>
        <h2>{{ needsBaselineCapture ? 'Face Registration Required' : 'Face Verification Required' }}</h2>
        <p>{{ needsBaselineCapture ? 'Your instructor requires face verification. Please register your face to continue.' : 'Please verify your identity to access the editor' }}</p>
      </div>
      
      <div class="modal-content">
        <!-- Webcam Feed -->
        <div class="webcam-wrapper">
          <video 
            ref="videoElement" 
            autoplay 
            playsinline 
            class="webcam-feed"
            :class="{ verifying: isVerifying }"
          ></video>
          <div class="webcam-overlay" v-if="isVerifying">
            <div class="scanning-animation"></div>
            <span>Verifying...</span>
          </div>
          <div class="webcam-overlay success" v-if="verificationSuccess">
            <svg width="64" height="64" viewBox="0 0 24 24" fill="currentColor">
              <path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm-2 15l-5-5 1.41-1.41L10 14.17l7.59-7.59L19 8l-9 9z"/>
            </svg>
            <span>Verified!</span>
          </div>
          <div class="webcam-overlay error" v-if="verificationFailed">
            <svg width="64" height="64" viewBox="0 0 24 24" fill="currentColor">
              <path d="M12 2C6.47 2 2 6.47 2 12s4.47 10 10 10 10-4.47 10-10S17.53 2 12 2zm5 13.59L15.59 17 12 13.41 8.41 17 7 15.59 10.59 12 7 8.41 8.41 7 12 10.59 15.59 7 17 8.41 13.41 12 17 15.59z"/>
            </svg>
            <span>{{ errorMessage }}</span>
          </div>
        </div>
        
        <!-- Instructions -->
        <div class="instructions" v-if="!isVerifying && !verificationSuccess && !verificationFailed">
          <p v-if="needsBaselineCapture">📸 Position your face in the frame and click "Register My Face" to set up face verification</p>
          <p v-else>📸 Position your face in the frame and click verify</p>
          <ul>
            <li>Ensure good lighting</li>
            <li>Face the camera directly</li>
            <li>Remove any face coverings</li>
          </ul>
        </div>
        
        <!-- Actions -->
        <div class="modal-actions">
          <!-- Retry camera button when webcam fails -->
          <button 
            v-if="!webcamReady && verificationFailed && !isVerifying" 
            @click="retryWebcam" 
            class="retry-btn"
          >
            <svg width="18" height="18" viewBox="0 0 24 24" fill="currentColor">
              <path d="M17.65 6.35C16.2 4.9 14.21 4 12 4c-4.42 0-7.99 3.58-7.99 8s3.57 8 7.99 8c3.73 0 6.84-2.55 7.73-6h-2.08c-.82 2.33-3.04 4-5.65 4-3.31 0-6-2.69-6-6s2.69-6 6-6c1.66 0 3.14.69 4.22 1.78L13 11h7V4l-2.35 2.35z"/>
            </svg>
            Retry Camera Access
          </button>
          
          <button 
            v-if="!verificationSuccess && !needsBaselineCapture" 
            @click="verifyFace" 
            class="verify-btn"
            :disabled="isVerifying || !webcamReady"
          >
            <span v-if="isVerifying" class="spinner"></span>
            <span v-else>{{ verificationFailed ? 'Try Again' : 'Verify My Face' }}</span>
          </button>
          
          <button 
            v-if="!verificationSuccess && needsBaselineCapture" 
            @click="captureBaseline" 
            class="verify-btn"
            :disabled="isVerifying || !webcamReady"
          >
            <span v-if="isVerifying" class="spinner"></span>
            <span v-else>Register My Face</span>
          </button>
          
          <button 
            v-if="verificationSuccess" 
            @click="proceedToEditor" 
            class="proceed-btn"
          >
            Proceed to Editor
          </button>
          
          <button @click="skipVerification" class="skip-btn" v-if="allowSkip">
            Skip for now
          </button>
        </div>
      </div>
    </div>
  </div>
  
  <!-- Session Check Warning Toast - 3 Strike System -->
  <div 
    class="session-warning-toast" 
    :class="{ 
      'warning-level-1': warningCount === 1,
      'warning-level-2': warningCount === 2,
      'warning-level-3': warningCount >= 3
    }"
    v-if="showSessionWarning"
  >
    <svg width="24" height="24" viewBox="0 0 24 24" fill="currentColor">
      <path d="M1 21h22L12 2 1 21zm12-3h-2v-2h2v2zm0-4h-2v-4h2v4z"/>
    </svg>
    <div class="warning-content">
      <span class="warning-text">{{ sessionWarningMessage }}</span>
      <div class="warning-strikes">
        <span v-for="i in 3" :key="i" class="strike" :class="{ active: i <= warningCount }">●</span>
      </div>
    </div>
  </div>
  
  <!-- Session Terminated Modal -->
  <div class="session-terminated-overlay" v-if="sessionTerminated">
    <div class="terminated-modal">
      <div class="terminated-icon">
        <svg width="64" height="64" viewBox="0 0 24 24" fill="currentColor">
          <path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm1 15h-2v-2h2v2zm0-4h-2V7h2v6z"/>
        </svg>
      </div>
      <h2>Session Terminated</h2>
      <p>{{ terminationReason || 'Identity verification failed. For security reasons, your editing session has been stopped.' }}</p>
      <p class="incident-note">This incident has been logged and will be reviewed by your instructor.</p>
      <p v-if="terminationCountdown > 0" style="font-size: 13px; color: #999; margin-top: 8px;">Redirecting in {{ terminationCountdown }}s...</p>
      <button @click="handleSessionTerminated" class="back-btn">
        Return to Dashboard{{ terminationCountdown > 0 ? ` (${terminationCountdown}s)` : '' }}
      </button>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted, onBeforeUnmount, watch, toRef } from 'vue'
import { useRouter } from 'vue-router'
import axios from 'axios'
import { getApiUrl } from '@/utils/api-url'

const props = defineProps({
  sessionId: {
    type: String,
    default: ''
  },
  checkInterval: {
    type: Number,
    default: 600000 // 10 minutes default (was 60 seconds - optimized for cost)
  },
  allowSkip: {
    type: Boolean,
    default: false
  },
  // Cost optimization settings
  minCheckInterval: {
    type: Number,
    default: 300000 // Minimum 5 minutes between checks
  },
  maxCheckInterval: {
    type: Number,
    default: 900000 // Maximum 15 minutes between checks
  },
  useRandomInterval: {
    type: Boolean,
    default: true // Randomize intervals for unpredictability + cost savings
  },
  skipIfHidden: {
    type: Boolean,
    default: true // Don't verify when tab is not visible
  },
  // External verification state (from parent)
  isVerified: {
    type: Boolean,
    default: false
  },
  // Assignment-level face verification requirement (set by teacher)
  // When true, overrides user profile settings - teacher mandates face verification
  assignmentRequiresFace: {
    type: Boolean,
    default: false
  }
})

const emit = defineEmits(['verified', 'session-terminated', 'skip'])

const router = useRouter()
const AUTH_API = getApiUrl()

// State
const showVerification = ref(true)
const webcamReady = ref(false)
const isVerifying = ref(false)
const verificationSuccess = ref(false)
const verificationFailed = ref(false)
const errorMessage = ref('')
const showSessionWarning = ref(false)
const sessionWarningMessage = ref('')
const sessionTerminated = ref(false)
const terminationReason = ref('')
const terminationCountdown = ref(0)
let terminationTimer = null
const needsBaselineCapture = ref(false)

// Refs
const videoElement = ref(null)
let mediaStream = null
let sessionCheckInterval = null
let warningTimeout = null
let lastVerificationTime = 0
let consecutiveSuccessCount = 0
let cameraFailCount = 0 // Track consecutive camera unavailable failures
let isTabVisible = true
let monitoringStarted = false // Prevent double-starting

// 3-Strike Warning System
const warningCount = ref(0)
const MAX_WARNINGS = 3
const warningMessages = [
  '⚠️ Warning 1/3: No face detected. Please ensure your face is visible.',
  '⚠️ Warning 2/3: Still no face detected. One more warning and session will end.',
  '🚨 Final Warning 3/3: Session will be terminated if face is not detected!'
]

// COST OPTIMIZATION: Activity tracking
let lastActivityTime = Date.now()
let activityCheckEnabled = true
const IDLE_THRESHOLD = 60000 // 1 minute of no activity = skip verification

// Track user activity
if (typeof document !== 'undefined') {
  const updateActivity = () => {
    lastActivityTime = Date.now()
  }
  document.addEventListener('keydown', updateActivity)
  document.addEventListener('mousedown', updateActivity)
  document.addEventListener('mousemove', updateActivity)
  document.addEventListener('scroll', updateActivity)
}

// COST OPTIMIZATION: Client-side face detection (FREE!)
let faceDetector = null
const canUseNativeFaceDetection = ref(false)

// Initialize native FaceDetector if available
async function initClientSideFaceDetection() {
  if (typeof window !== 'undefined' && 'FaceDetector' in window) {
    try {
      faceDetector = new window.FaceDetector({ fastMode: true, maxDetectedFaces: 1 })
      canUseNativeFaceDetection.value = true
    } catch (e) {
      // FaceDetector not supported - will fall back to server-side detection
    }
  }
}

// Client-side face detection (FREE - no AWS call)
async function detectFaceLocally(imageElement) {
  if (!faceDetector || !canUseNativeFaceDetection.value) {
    return { detected: true } // Assume face present if no local detection
  }
  
  try {
    const faces = await faceDetector.detect(imageElement)
    return { 
      detected: faces.length > 0,
      faceCount: faces.length
    }
  } catch (e) {
    console.warn('Local face detection failed:', e)
    return { detected: true } // Fail-safe: assume face present
  }
}

// Track tab visibility for cost savings
if (typeof document !== 'undefined') {
  document.addEventListener('visibilitychange', () => {
    isTabVisible = document.visibilityState === 'visible'
  })
}

// Initialize webcam
onMounted(async () => {
  // Only check immediately if we already know the requirement
  // Otherwise, the watcher below will trigger when assignmentRequiresFace becomes true
  if (props.assignmentRequiresFace || !props.assignmentRequiresFace) {
    await checkIfVerificationNeeded()
  }
})

// Watch for external verification state changes
watch(() => props.isVerified, (newVal, oldVal) => {
  if (newVal && !oldVal) {
    // Just became verified from parent - start session monitoring
    startSessionMonitoring()
  }
}, { immediate: true })

// CRITICAL: Watch for assignmentRequiresFace becoming true AFTER mount
// This fixes the race condition where assignment data loads after FaceVerification mounts
watch(() => props.assignmentRequiresFace, async (newVal, oldVal) => {
  if (newVal && !oldVal && !props.isVerified && !verificationSuccess.value) {
    // Assignment now requires face verification, but we already skipped it
    showVerification.value = true
    await checkIfVerificationNeeded()
  }
})

async function checkIfVerificationNeeded() {
  try {
    const token = localStorage.getItem('auth_token')
    if (!token) {
      // Not logged in, skip verification
      showVerification.value = false
      emit('verified')
      return
    }
    
    // Check face settings from user profile
    // FIX #7: Use header (axios interceptor), not query param
    const response = await axios.get(`${AUTH_API}/api/auth/face/settings`)
    
    // Determine if face verification is needed:
    // 1. Teacher mandated it for the assignment (assignmentRequiresFace), OR
    // 2. User has it enabled in their profile (face_biometric_enabled)
    const teacherRequires = props.assignmentRequiresFace
    const userEnabled = response.data.face_biometric_enabled
    const hasBaseline = response.data.face_baseline_uploaded
    
    if (!teacherRequires && !userEnabled) {
      // Neither teacher nor user requires face verification
      console.log('👤 Face verification not required (teacher: off, user: off)')
      showVerification.value = false
      emit('verified')
      return
    }
    
    if (!hasBaseline) {
      if (teacherRequires) {
        // Teacher requires face verification but student has no baseline
        // Show the verification modal in "enrollment mode" - capture their face as baseline
        console.log('⚠️ Teacher requires face verification - prompting baseline capture')
        needsBaselineCapture.value = true
        await initWebcam()
      } else {
        // No baseline uploaded, skipping verification
        console.log('👤 No face baseline uploaded, skipping verification')
        showVerification.value = false
        emit('verified')
      }
      return
    }
    
    // Face verification required - either teacher mandated or user enabled
    console.log(`🔐 Face verification required (teacher: ${teacherRequires}, user: ${userEnabled})`)
    await initWebcam()
  } catch (e) {
    console.error('Failed to check face settings:', e)
    // On error, allow access but log the failure
    showVerification.value = false
    emit('verified')
  }
}

async function initWebcam() {
  try {
    // Reset error state on retry
    verificationFailed.value = false
    errorMessage.value = ''
    
    mediaStream = await navigator.mediaDevices.getUserMedia({
      video: { facingMode: 'user', width: 640, height: 480 }
    })
    
    if (videoElement.value) {
      videoElement.value.srcObject = mediaStream
      webcamReady.value = true
    }
  } catch (e) {
    console.error('Webcam access failed:', e)
    errorMessage.value = 'Could not access webcam. Please check permissions and try again.'
    verificationFailed.value = true
    webcamReady.value = false
  }
}

async function retryWebcam() {
  // Stop any existing stream
  if (mediaStream) {
    mediaStream.getTracks().forEach(t => t.stop())
    mediaStream = null
  }
  await initWebcam()
}

async function captureFrame() {
  if (!videoElement.value) return null
  
  const canvas = document.createElement('canvas')
  canvas.width = videoElement.value.videoWidth
  canvas.height = videoElement.value.videoHeight
  
  const ctx = canvas.getContext('2d')
  ctx.drawImage(videoElement.value, 0, 0)
  
  return canvas.toDataURL('image/jpeg', 0.9)
}

async function verifyFace() {
  isVerifying.value = true
  verificationFailed.value = false
  errorMessage.value = ''
  
  try {
    const token = localStorage.getItem('auth_token')
    const imageBase64 = await captureFrame()
    
    if (!imageBase64) {
      throw new Error('Failed to capture image')
    }
    
    // FIX #7: Use header, not query param
    const response = await axios.post(
      `${AUTH_API}/api/auth/face/verify-access`,
      { image_base64: imageBase64 }
    )
    
    if (response.data.verified) {
      verificationSuccess.value = true
      
      // Start session monitoring
      startSessionMonitoring()
      
      // Auto-proceed after brief success display
      setTimeout(() => {
        proceedToEditor()
      }, 1500)
    } else if (response.data.bypass) {
      // Server allowed bypass
      verificationSuccess.value = true
      setTimeout(() => proceedToEditor(), 500)
    } else {
      verificationFailed.value = true
      errorMessage.value = response.data.message || 'Face not recognized'
    }
  } catch (e) {
    console.error('Face verification error:', e)
    verificationFailed.value = true
    errorMessage.value = e.response?.data?.detail || 'Verification failed. Please try again.'
  } finally {
    isVerifying.value = false
  }
}

async function captureBaseline() {
  isVerifying.value = true
  verificationFailed.value = false
  errorMessage.value = ''
  
  try {
    const token = localStorage.getItem('auth_token')
    const imageBase64 = await captureFrame()
    
    if (!imageBase64) {
      throw new Error('Failed to capture image')
    }
    
    // FIX #7: Use header, not query param
    const response = await axios.post(
      `${AUTH_API}/api/auth/face/upload-baseline-base64`,
      { image_base64: imageBase64 }
    )
    
    if (response.data.success) {
      // Baseline captured - now switch to verification mode
      needsBaselineCapture.value = false
      verificationSuccess.value = true
      
      // Start session monitoring since face is now registered
      startSessionMonitoring()
      
      // Auto-proceed after brief success display
      setTimeout(() => {
        proceedToEditor()
      }, 1500)
    } else {
      verificationFailed.value = true
      errorMessage.value = response.data.message || 'Failed to register face'
    }
  } catch (e) {
    console.error('Face baseline capture error:', e)
    verificationFailed.value = true
    errorMessage.value = e.response?.data?.detail || 'Could not register face. Ensure good lighting and try again.'
  } finally {
    isVerifying.value = false
  }
}

function proceedToEditor() {
  showVerification.value = false
  // DON'T stop webcam here - we need it for background session monitoring!
  // stopWebcam() is now only called on unmount or when face biometric is disabled
  emit('verified')
}

function skipVerification() {
  showVerification.value = false
  stopWebcam()
  emit('skip')
}

function stopWebcam() {
  if (mediaStream) {
    mediaStream.getTracks().forEach(track => track.stop())
    mediaStream = null
  }
}

// Session Monitoring (Periodic Checks) - COST OPTIMIZED
// Scheduling strategy:
//   1st check:  10-30 seconds after editor opens (catch early cheaters)
//   2nd check:  1-3 minutes later
//   Subsequent: use increasing random intervals based on consecutive successes
//   Max cap:    props.maxCheckInterval (default 30 min)
let checkNumber = 0

function startSessionMonitoring() {
  // Prevent double-starting
  if (monitoringStarted) return
  monitoringStarted = true
  checkNumber = 0
  
  // Initialize client-side face detection (FREE!)
  initClientSideFaceDetection()
  
  // Re-init webcam for background monitoring (hidden)
  initBackgroundWebcam()
  
  // Schedule first check
  scheduleNextCheck()
}

function getSmartInterval() {
  checkNumber++
  
  // 1st check: 3-10 seconds (immediate deterrent, always within 10s)
  if (checkNumber === 1) {
    return 3000 + Math.floor(Math.random() * 7000) // 3-10s
  }
  
  // 2nd check: 1-3 minutes later
  if (checkNumber === 2) {
    return 60000 + Math.floor(Math.random() * 120000) // 60-180s
  }
  
  // 3rd check: 3-5 minutes
  if (checkNumber === 3) {
    return 180000 + Math.floor(Math.random() * 120000) // 3-5 min
  }
  
  // Subsequent checks: use configured min/max with random intervals
  const min = props.minCheckInterval
  const max = props.maxCheckInterval
  let interval = Math.floor(Math.random() * (max - min + 1)) + min
  
  // If user has been verified successfully multiple times, gradually increase interval
  // This saves costs for legitimate users while still catching cheaters
  if (consecutiveSuccessCount >= 3) {
    interval = Math.min(interval * 1.5, props.maxCheckInterval)
  }
  
  return interval
}

function scheduleNextCheck() {
  const nextInterval = getSmartInterval()
  
  sessionCheckInterval = setTimeout(async () => {
    await performSessionCheck()
    // Schedule next check after this one completes
    scheduleNextCheck()
  }, nextInterval)
}

async function initBackgroundWebcam() {
  try {
    if (!mediaStream || !mediaStream.active) {
      mediaStream = await navigator.mediaDevices.getUserMedia({
        video: { facingMode: 'user', width: 320, height: 240 }
      })
    }
  } catch (e) {
    console.warn('Background webcam init failed:', e)
  }
}

// Detect covered/obstructed camera by checking average pixel brightness
function isFrameBlackedOut(canvas) {
  const ctx = canvas.getContext('2d')
  const imageData = ctx.getImageData(0, 0, canvas.width, canvas.height)
  const data = imageData.data
  // Sample every 40th pixel for performance (RGBA stride = 4)
  let totalBrightness = 0
  let sampleCount = 0
  for (let i = 0; i < data.length; i += 160) { // 40 pixels * 4 channels
    totalBrightness += (data[i] + data[i + 1] + data[i + 2]) / 3
    sampleCount++
  }
  const avgBrightness = totalBrightness / sampleCount
  // < 10 = camera covered (black), > 250 = camera pointed at bright light
  return avgBrightness < 10 || avgBrightness > 250
}

async function performSessionCheck() {
  try {
    const token = localStorage.getItem('auth_token')
    if (!token) return
    
    const now = Date.now()
    const isTestingMode = props.minCheckInterval <= 15000
    
    // Skip if tab is hidden
    if (props.skipIfHidden && !isTabVisible) return
    
    // Skip if user is idle
    const idleTime = now - lastActivityTime
    if (!isTestingMode && idleTime > IDLE_THRESHOLD) return
    
    // Minimum time between checks
    const timeSinceLastCheck = now - lastVerificationTime
    if (!isTestingMode && timeSinceLastCheck < props.minCheckInterval) return
    
    // Reinit webcam if needed
    if (!mediaStream || !mediaStream.active) {
      await initBackgroundWebcam()
      await new Promise(resolve => setTimeout(resolve, 500))
    }
    
    // If webcam still unavailable, escalate as camera failure
    if (!mediaStream || !mediaStream.active) {
      cameraFailCount++
      if (cameraFailCount >= MAX_WARNINGS) {
        clearTimeout(sessionCheckInterval)
        terminationReason.value = 'Your camera has been unavailable for too long. The session has been stopped for integrity reasons.'
        sessionTerminated.value = true
        terminationCountdown.value = 10
        startTerminationCountdown()
        return
      }
      // Show warning about camera
      warningCount.value++
      showSessionWarning.value = true
      sessionWarningMessage.value = warningMessages[Math.min(warningCount.value, MAX_WARNINGS) - 1]
      if (warningTimeout) clearTimeout(warningTimeout)
      warningTimeout = setTimeout(() => { showSessionWarning.value = false }, 8000)
      return
    }
    
    // Camera is available - reset camera fail counter
    cameraFailCount = 0
    
    // Create a hidden video element to capture frame
    const tempVideo = document.createElement('video')
    tempVideo.srcObject = mediaStream
    tempVideo.autoplay = true
    tempVideo.playsInline = true
    
    await new Promise(resolve => {
      tempVideo.onloadeddata = resolve
      setTimeout(resolve, 1000)
    })
    
    const canvas = document.createElement('canvas')
    canvas.width = tempVideo.videoWidth || 320
    canvas.height = tempVideo.videoHeight || 240
    const ctx = canvas.getContext('2d')
    ctx.drawImage(tempVideo, 0, 0)
    
    // BLACK FRAME DETECTION: Check if camera is covered (saves AWS costs)
    if (isFrameBlackedOut(canvas)) {
      warningCount.value++
      if (warningCount.value >= MAX_WARNINGS) {
        clearTimeout(sessionCheckInterval)
        terminationReason.value = 'Your camera appears to be covered. The session has been stopped for integrity reasons.'
        sessionTerminated.value = true
        terminationCountdown.value = 10
        startTerminationCountdown()
        return
      }
      showSessionWarning.value = true
      sessionWarningMessage.value = warningMessages[warningCount.value - 1]
      if (warningTimeout) clearTimeout(warningTimeout)
      warningTimeout = setTimeout(() => { showSessionWarning.value = false }, 8000)
      return // Skip AWS call - no point sending a black frame
    }
    
    // Client-side face detection FIRST (FREE!)
    if (canUseNativeFaceDetection.value && !isTestingMode) {
      const localResult = await detectFaceLocally(canvas)
      
      if (!localResult.detected) {
        warningCount.value++
        
        if (warningCount.value >= MAX_WARNINGS) {
          clearTimeout(sessionCheckInterval)
          terminationReason.value = 'No face was detected after multiple checks. The session has been stopped for integrity reasons.'
          sessionTerminated.value = true
          terminationCountdown.value = 10
          startTerminationCountdown()
          return
        }
        
        showSessionWarning.value = true
        sessionWarningMessage.value = warningMessages[warningCount.value - 1]
        if (warningTimeout) clearTimeout(warningTimeout)
        warningTimeout = setTimeout(() => { showSessionWarning.value = false }, 8000)
        return // Skip AWS call
      }
    }
    
    // Send to AWS for verification
    const imageBase64 = canvas.toDataURL('image/jpeg', 0.7)
    lastVerificationTime = now
    
    const response = await axios.post(
      `${AUTH_API}/api/auth/face/verify-session`,
      { 
        image_base64: imageBase64,
        session_id: props.sessionId
      }
    )
    
    if (response.data.stop_session) {
      // Don't terminate on the very first periodic check — the webcam and
      // lighting may not have stabilised yet. Treat the first failure as a
      // warning so the student isn't kicked out within 10 seconds of opening
      // the editor. Only terminate after MAX_WARNINGS consecutive failures.
      warningCount.value++
      consecutiveSuccessCount = 0

      if (warningCount.value >= MAX_WARNINGS) {
        clearTimeout(sessionCheckInterval)
        warningCount.value = 0
        terminationReason.value = response.data.matched_identity
          ? `A different enrolled user was detected (matched: ${response.data.matched_identity}).`
          : 'Identity verification failed — a different person was detected.'
        sessionTerminated.value = true
        terminationCountdown.value = 10
        startTerminationCountdown()
      } else {
        showSessionWarning.value = true
        sessionWarningMessage.value = warningMessages[warningCount.value - 1]
        if (warningTimeout) clearTimeout(warningTimeout)
        warningTimeout = setTimeout(() => { showSessionWarning.value = false }, 8000)
      }
    } else if (response.data.warning) {
      consecutiveSuccessCount = 0
      warningCount.value++
      
      if (warningCount.value >= MAX_WARNINGS) {
        clearTimeout(sessionCheckInterval)
        terminationReason.value = response.data.message || 'Too many verification warnings. The session has been stopped.'
        sessionTerminated.value = true
        terminationCountdown.value = 10
        startTerminationCountdown()
        return
      }
      
      showSessionWarning.value = true
      sessionWarningMessage.value = warningMessages[warningCount.value - 1] || response.data.message
      if (warningTimeout) clearTimeout(warningTimeout)
      warningTimeout = setTimeout(() => { showSessionWarning.value = false }, 8000)
    } else if (response.data.verified) {
      if (warningCount.value > 0) warningCount.value = 0
      consecutiveSuccessCount++
    }
  } catch (e) {
    // Don't terminate on network errors, just reset success streak
    consecutiveSuccessCount = 0
  }
}

function startTerminationCountdown() {
  if (terminationTimer) clearInterval(terminationTimer)
  terminationTimer = setInterval(() => {
    terminationCountdown.value--
    if (terminationCountdown.value <= 0) {
      clearInterval(terminationTimer)
      handleSessionTerminated()
    }
  }, 1000)
}

function handleSessionTerminated() {
  if (terminationTimer) clearInterval(terminationTimer)
  stopWebcam()
  clearInterval(sessionCheckInterval)
  emit('session-terminated')
}

// Cleanup
onBeforeUnmount(() => {
  stopWebcam()
  if (terminationTimer) clearInterval(terminationTimer)
  if (sessionCheckInterval) {
    clearTimeout(sessionCheckInterval)
  }
  if (warningTimeout) {
    clearTimeout(warningTimeout)
  }
})
</script>

<style scoped>
.face-verification-overlay {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.85);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 10000;
  backdrop-filter: blur(8px);
}

.verification-modal {
  background: white;
  border-radius: 20px;
  max-width: 480px;
  width: 90%;
  overflow: hidden;
  box-shadow: 0 20px 60px rgba(0, 0, 0, 0.3);
  animation: slideUp 0.3s ease-out;
}

@keyframes slideUp {
  from {
    opacity: 0;
    transform: translateY(20px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}

.modal-header {
  text-align: center;
  padding: 32px 24px 16px;
  background: linear-gradient(135deg, #1a73e8 0%, #4285f4 100%);
  color: white;
}

.header-icon {
  margin-bottom: 16px;
}

.header-icon svg {
  opacity: 0.9;
}

.modal-header h2 {
  margin: 0 0 8px;
  font-size: 22px;
  font-weight: 600;
}

.modal-header p {
  margin: 0;
  opacity: 0.9;
  font-size: 14px;
}

.modal-content {
  padding: 24px;
}

.webcam-wrapper {
  position: relative;
  width: 100%;
  aspect-ratio: 4/3;
  border-radius: 12px;
  overflow: hidden;
  background: #000;
  margin-bottom: 20px;
}

.webcam-feed {
  width: 100%;
  height: 100%;
  object-fit: cover;
  transform: scaleX(-1); /* Mirror effect */
}

.webcam-feed.verifying {
  filter: brightness(0.7);
}

.webcam-overlay {
  position: absolute;
  inset: 0;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  background: rgba(0, 0, 0, 0.6);
  color: white;
  font-size: 16px;
  font-weight: 500;
  gap: 12px;
}

.webcam-overlay.success {
  background: rgba(52, 168, 83, 0.85);
}

.webcam-overlay.error {
  background: rgba(217, 48, 37, 0.85);
}

.scanning-animation {
  width: 80px;
  height: 80px;
  border: 3px solid transparent;
  border-top-color: white;
  border-radius: 50%;
  animation: spin 1s linear infinite;
}

@keyframes spin {
  to { transform: rotate(360deg); }
}

.instructions {
  text-align: center;
  margin-bottom: 20px;
}

.instructions p {
  font-size: 15px;
  color: #202124;
  margin: 0 0 12px;
}

.instructions ul {
  list-style: none;
  padding: 0;
  margin: 0;
  display: flex;
  justify-content: center;
  gap: 16px;
  font-size: 13px;
  color: #5f6368;
}

.instructions li::before {
  content: '✓';
  margin-right: 4px;
  color: #34a853;
}

.modal-actions {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.verify-btn {
  width: 100%;
  padding: 14px;
  background: #1a73e8;
  color: white;
  border: none;
  border-radius: 10px;
  font-size: 16px;
  font-weight: 600;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  transition: all 0.2s;
}

.verify-btn:hover:not(:disabled) {
  background: #1557b0;
  transform: translateY(-1px);
}

.verify-btn:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}

.retry-btn {
  width: 100%;
  padding: 14px;
  background: #f9ab00;
  color: white;
  border: none;
  border-radius: 12px;
  font-weight: 600;
  font-size: 16px;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  transition: all 0.2s;
}

.retry-btn:hover {
  background: #f29900;
  transform: translateY(-1px);
}

.proceed-btn {
  width: 100%;
  padding: 14px;
  background: #34a853;
  color: white;
  border: none;
  border-radius: 10px;
  font-size: 16px;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.2s;
}

.proceed-btn:hover {
  background: #2d8e47;
}

.skip-btn {
  width: 100%;
  padding: 12px;
  background: transparent;
  color: #5f6368;
  border: none;
  font-size: 14px;
  cursor: pointer;
}

.skip-btn:hover {
  color: #202124;
}

.spinner {
  width: 20px;
  height: 20px;
  border: 2px solid rgba(255, 255, 255, 0.3);
  border-top-color: white;
  border-radius: 50%;
  animation: spin 0.8s linear infinite;
}

/* Session Warning Toast - 3 Strike System */
.session-warning-toast {
  position: fixed;
  bottom: 24px;
  left: 50%;
  transform: translateX(-50%);
  background: #ff9800;
  color: white;
  padding: 16px 24px;
  border-radius: 12px;
  display: flex;
  align-items: center;
  gap: 16px;
  font-size: 14px;
  font-weight: 500;
  box-shadow: 0 4px 20px rgba(0, 0, 0, 0.3);
  z-index: 10000;
  animation: slideInUp 0.3s ease-out;
  max-width: 90%;
}

.session-warning-toast.warning-level-1 {
  background: #ff9800;
}

.session-warning-toast.warning-level-2 {
  background: #f57c00;
  animation: slideInUp 0.3s ease-out, pulse 0.5s ease-in-out 2;
}

.session-warning-toast.warning-level-3 {
  background: #d32f2f;
  animation: slideInUp 0.3s ease-out, shake 0.5s ease-in-out 3;
}

@keyframes pulse {
  0%, 100% { transform: translateX(-50%) scale(1); }
  50% { transform: translateX(-50%) scale(1.05); }
}

@keyframes shake {
  0%, 100% { transform: translateX(-50%); }
  25% { transform: translateX(calc(-50% - 5px)); }
  75% { transform: translateX(calc(-50% + 5px)); }
}

.warning-content {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.warning-text {
  font-weight: 600;
}

.warning-strikes {
  display: flex;
  gap: 8px;
  font-size: 12px;
}

.warning-strikes .strike {
  opacity: 0.3;
  font-size: 10px;
}

.warning-strikes .strike.active {
  opacity: 1;
  color: white;
}

@keyframes slideInUp {
  from {
    opacity: 0;
    transform: translateX(-50%) translateY(20px);
  }
  to {
    opacity: 1;
    transform: translateX(-50%) translateY(0);
  }
}

/* Session Terminated Modal */
.session-terminated-overlay {
  position: fixed;
  inset: 0;
  background: rgba(217, 48, 37, 0.95);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 10001;
}

.terminated-modal {
  background: white;
  border-radius: 20px;
  padding: 40px;
  max-width: 400px;
  width: 90%;
  text-align: center;
  box-shadow: 0 20px 60px rgba(0, 0, 0, 0.3);
}

.terminated-icon {
  color: #d93025;
  margin-bottom: 20px;
}

.terminated-modal h2 {
  margin: 0 0 16px;
  font-size: 24px;
  color: #d93025;
}

.terminated-modal p {
  margin: 0 0 12px;
  font-size: 15px;
  color: #5f6368;
  line-height: 1.5;
}

.incident-note {
  font-size: 13px !important;
  color: #d93025 !important;
  font-weight: 500;
}

.back-btn {
  margin-top: 24px;
  padding: 14px 32px;
  background: #d93025;
  color: white;
  border: none;
  border-radius: 10px;
  font-size: 15px;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.2s;
}

.back-btn:hover {
  background: #b71c1c;
}
</style>
