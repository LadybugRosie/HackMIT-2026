<template>
  <div class="enrollment-page">
    <header class="page-header">
      <div class="header-left">
        <button @click="goBack" class="back-btn">
          <svg width="24" height="24" viewBox="0 0 24 24" fill="currentColor">
            <path d="M20 11H7.83l5.59-5.59L12 4l-8 8 8 8 1.41-1.41L7.83 13H20v-2z"/>
          </svg>
        </button>
        <div>
          <h1>Writing Profile Assessment</h1>
          <span class="subtitle">{{ className || 'Loading...' }}</span>
        </div>
      </div>
      <div class="header-badge">
        <svg width="20" height="20" viewBox="0 0 24 24" fill="#1a73e8">
          <path d="M12 1L3 5v6c0 5.55 3.84 10.74 9 12 5.16-1.26 9-6.45 9-12V5l-9-4z"/>
        </svg>
        Secure Assessment
      </div>
    </header>

    <!-- Already enrolled -->
    <div v-if="alreadyEnrolled" class="already-enrolled">
      <svg width="64" height="64" viewBox="0 0 24 24" fill="#1e8e3e">
        <path d="M9 16.17L4.83 12l-1.42 1.41L9 19 21 7l-1.41-1.41z"/>
      </svg>
      <h2>Writing Profile Complete</h2>
      <p>You're enrolled for this course. Profile strength: <strong>{{ enrollmentStatus?.profile_strength }}</strong></p>
      <button class="btn-primary" @click="goBack">Return to Class</button>
    </div>

    <!-- Enrollment form -->
    <main v-else class="enrollment-content">
      <div class="info-banner">
        <svg width="24" height="24" viewBox="0 0 24 24" fill="#1a73e8">
          <path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm1 15h-2v-6h2v6zm0-8h-2V7h2v2z"/>
        </svg>
        <div>
          <strong>{{ pasteAllowed ? 'Writing Style Profile' : 'Exam Condition Assessment' }}</strong>
          <p v-if="pasteAllowed">Answer each prompt in your own words. Your writing style creates a unique fingerprint used to verify authorship on your future documents — the more genuine your writing, the stronger your profile.</p>
          <p v-else>This is a supervised writing assessment. Your writing style creates a unique fingerprint used to verify authorship on all future assignments. Write naturally in your own words — no AI tools, no copy-pasting, no external help. Treat this as an exam.</p>
        </div>
      </div>

      <!-- Progress -->
      <div class="progress-bar">
        <div class="progress-steps">
          <div v-for="i in 3" :key="i" :class="['step', { active: i <= currentStep, completed: samples[i-1].wordCount >= 400 }]">
            <span class="step-number">{{ i }}</span>
            <span class="step-label">Prompt {{ i }}</span>
          </div>
        </div>
        <div class="progress-track">
          <div class="progress-fill" :style="{ width: progressPercent + '%' }"></div>
        </div>
      </div>

      <!-- Sample forms -->
      <div v-for="(sample, idx) in samples" :key="idx" class="sample-card" :class="{ active: currentStep === idx + 1 }">
        <div class="sample-header">
          <h3>Prompt {{ idx + 1 }}</h3>
          <span class="word-badge" :class="{ sufficient: sample.wordCount >= 400, warning: sample.wordCount > 0 && sample.wordCount < 400 }">
            {{ sample.wordCount }}/400 words
          </span>
        </div>
        <div class="prompt-text">
          {{ prompts[idx] || 'Loading prompt...' }}
        </div>
        <div class="textarea-wrapper">
          <textarea
            v-model="sample.text"
            @input="onInput(idx)"
            @paste="handlePaste"
            @drop.prevent
            @dragover.prevent
            :placeholder="'Write your response here (minimum 400 words)...'"
            :disabled="submitting"
            rows="10"
            spellcheck="true"
          ></textarea>
          <div v-if="pasteWarning" class="paste-warning">
            Copy-paste is disabled for this assessment. Please type your response.
          </div>
        </div>
        <div class="sample-footer">
          <button v-if="idx > 0" class="btn-text" @click="currentStep = idx">Previous</button>
          <div class="spacer"></div>
          <button v-if="idx < 2" class="btn-secondary" @click="currentStep = idx + 2" :disabled="sample.wordCount < 400">
            Next Prompt
          </button>
        </div>
      </div>

      <!-- Submit section -->
      <div class="submit-section">
        <div class="readiness-checks">
          <div v-for="(sample, idx) in samples" :key="'check-'+idx" class="check-item" :class="{ ready: sample.wordCount >= 400 }">
            <svg v-if="sample.wordCount >= 400" width="20" height="20" viewBox="0 0 24 24" fill="#1e8e3e">
              <path d="M9 16.17L4.83 12l-1.42 1.41L9 19 21 7l-1.41-1.41z"/>
            </svg>
            <svg v-else width="20" height="20" viewBox="0 0 24 24" fill="#dadce0">
              <circle cx="12" cy="12" r="10" fill="none" stroke="currentColor" stroke-width="2"/>
            </svg>
            Prompt {{ idx + 1 }}: {{ sample.wordCount >= 400 ? 'Complete' : `${sample.wordCount}/400 words` }}
          </div>
        </div>

        <div v-if="submitError" class="error-message">{{ submitError }}</div>

        <button
          class="btn-submit"
          :disabled="!allSamplesReady || submitting"
          @click="submitEnrollment"
        >
          <svg v-if="!submitting" width="24" height="24" viewBox="0 0 24 24" fill="currentColor">
            <path d="M12 1L3 5v6c0 5.55 3.84 10.74 9 12 5.16-1.26 9-6.45 9-12V5l-9-4z"/>
          </svg>
          <span v-if="submitting" class="spinner"></span>
          {{ submitting ? 'Analyzing & Enrolling...' : 'Submit Writing Profile' }}
        </button>
      </div>
    </main>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { useClasses, useStylometryV3 } from '@/composables/classroom'
import { useAuth } from '@/composables/auth'
import { getApiUrl } from '@/utils/api-url'
import axios from 'axios'

// Demo accounts allowed to paste enrollment samples (bypasses the typing-only rule).
const PASTE_ALLOWED_EMAILS = ['easyjoey1982@gmail.com', 'charlesdickens@editorrah.com']

// Easy, general prompts ABOUT the researcher's entered topic. Anyone can answer
// these naturally in their own words, and free writing still yields a strong
// style fingerprint. {topic} is filled in from the topic the researcher entered.
function buildTopicPrompts(topic) {
  const t = (topic || '').trim()
  if (!t) {
    return [
      'Describe a subject you know well. What is it about, and why does it interest you?',
      'Explain something you have learned recently. What is it, and how would you describe it to a friend?',
      'Write about a question you find fascinating and how you would go about exploring it.',
    ]
  }
  return [
    `In your own words, what is "${t}" about? Explain it simply, as if you were describing it to a friend who has never heard of it.`,
    `Why does "${t}" matter to you, and why do you think it is important? Share your own thoughts and opinions.`,
    `What questions or ideas do you have about "${t}"? Describe what you would like to find out and how you might explore it.`,
  ]
}

const router = useRouter()
const route = useRoute()
const classId = route.params.classId

const { user, initAuth } = useAuth()
const { fetchClass, currentClass } = useClasses()
const { getCourseEnrollmentStatus, enrollInCourse } = useStylometryV3()

// Researchers may paste during enrollment; students remain typing-only (anti-cheat).
const pasteAllowed = computed(() =>
  user.value?.role === 'researcher' || PASTE_ALLOWED_EMAILS.includes(user.value?.email)
)

const className = computed(() => currentClass.value?.name || '')
const prompts = ref([])
const currentStep = ref(1)
const pasteWarning = ref(false)
const submitting = ref(false)
const submitError = ref(null)
const alreadyEnrolled = ref(false)
const enrollmentStatus = ref(null)

const samples = ref([
  { text: '', wordCount: 0 },
  { text: '', wordCount: 0 },
  { text: '', wordCount: 0 },
])

const allSamplesReady = computed(() => samples.value.every(s => s.wordCount >= 400))

const progressPercent = computed(() => {
  const completed = samples.value.filter(s => s.wordCount >= 400).length
  return Math.round((completed / 3) * 100)
})

function onInput(idx) {
  const text = samples.value[idx].text.trim()
  samples.value[idx].wordCount = text ? text.split(/\s+/).length : 0
}

let pasteTimeout = null
function onPasteBlocked() {
  pasteWarning.value = true
  clearTimeout(pasteTimeout)
  pasteTimeout = setTimeout(() => { pasteWarning.value = false }, 3000)
}

function handlePaste(e) {
  if (pasteAllowed.value) return
  e.preventDefault()
  onPasteBlocked()
}

async function submitEnrollment() {
  submitError.value = null
  submitting.value = true

  try {
    const sampleTexts = samples.value.map(s => s.text.trim())
    const result = await enrollInCourse(classId, sampleTexts)

    if (!result.success) {
      submitError.value = result.error
      return
    }

    alreadyEnrolled.value = true
    enrollmentStatus.value = result.data

    // Researchers arrive with a ?next= redirect target (e.g. back into the editor).
    if (route.query.next) {
      router.push(String(route.query.next))
    }
  } catch (e) {
    submitError.value = e.message || 'Enrollment failed'
  } finally {
    submitting.value = false
  }
}

function goBack() {
  if (route.query.next) {
    router.push(String(route.query.next))
    return
  }
  router.push(`/student/class/${classId}`)
}

onMounted(async () => {
  // On a hard refresh, `user` ref is empty until initAuth re-hydrates it from
  // the saved token. The paste allowlist depends on user.email, so do this first.
  if (!user.value) await initAuth()

  await fetchClass(classId)

  // Check if already enrolled
  const statusResult = await getCourseEnrollmentStatus(classId)
  if (statusResult.success && statusResult.data.enrolled) {
    alreadyEnrolled.value = true
    enrollmentStatus.value = statusResult.data
    return
  }

  // Researchers get easy, general prompts ABOUT their entered topic (and may
  // paste) — reliable, on-topic, and still strong free-text style samples.
  if (user.value?.role === 'researcher') {
    prompts.value = buildTopicPrompts(route.query.topic)
    return
  }

  // Fetch prompts from the enrollment assignment
  const API = getApiUrl()
  try {
    const assignmentId = statusResult.data?.enrollment_assignment_id
    if (assignmentId) {
      const resp = await axios.get(`${API}/api/assignments/${assignmentId}`)
      const data = resp.data
      if (data.stylometry_prompts && data.stylometry_prompts.length >= 3) {
        prompts.value = data.stylometry_prompts
      } else {
        extractPromptsFromInstructions(data.instructions)
      }
    } else {
      // Generate prompts via API
      const resp = await axios.post(`${API}/api/stylometry/v3/generate-prompts`, null, {
        params: { class_id: classId }
      })
      prompts.value = resp.data.prompts || []
    }
  } catch (e) {
    const subject = currentClass.value?.subject || 'this course'
    prompts.value = [
      `Write about a topic in ${subject} that interests you and explain why it matters.`,
      `Describe a concept from ${subject} you find challenging and how you approach understanding it.`,
      `Reflect on something you've learned about ${subject} recently and how it changed your thinking.`,
    ]
  }
})

function extractPromptsFromInstructions(instructions) {
  if (!instructions) return
  const matches = instructions.match(/PROMPT \d+:\n([\s\S]*?)(?=\n\nPROMPT|\s*$)/g)
  if (matches && matches.length >= 3) {
    prompts.value = matches.map(m => m.replace(/^PROMPT \d+:\n/, '').trim())
  }
}
</script>

<style scoped>
.enrollment-page {
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

.header-left h1 {
  font-size: 20px;
  font-weight: 500;
  margin: 0;
  color: #202124;
}

.subtitle {
  font-size: 14px;
  color: #5f6368;
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

.header-badge {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 16px;
  background: #e8f0fe;
  border-radius: 20px;
  font-size: 13px;
  font-weight: 500;
  color: #1a73e8;
}

.already-enrolled {
  max-width: 500px;
  margin: 80px auto;
  text-align: center;
  background: white;
  border-radius: 16px;
  padding: 48px;
}

.already-enrolled h2 {
  margin: 16px 0 8px;
  color: #1e8e3e;
}

.already-enrolled p {
  color: #5f6368;
  margin-bottom: 24px;
}

.enrollment-content {
  max-width: 800px;
  margin: 0 auto;
  padding: 24px;
  display: flex;
  flex-direction: column;
  gap: 20px;
}

.info-banner {
  display: flex;
  gap: 16px;
  padding: 20px;
  background: #e8f0fe;
  border-radius: 12px;
  align-items: flex-start;
}

.info-banner p {
  margin: 4px 0 0;
  font-size: 14px;
  color: #3c4043;
  line-height: 1.5;
}

.info-banner strong {
  color: #202124;
}

/* Progress */
.progress-bar { background: white; border-radius: 12px; padding: 20px; }

.progress-steps {
  display: flex;
  justify-content: space-between;
  margin-bottom: 12px;
}

.step {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 14px;
  color: #9aa0a6;
}

.step.active { color: #1a73e8; font-weight: 500; }
.step.completed { color: #1e8e3e; }

.step-number {
  width: 28px;
  height: 28px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 13px;
  font-weight: 600;
  background: #e8eaed;
  color: #5f6368;
}

.step.active .step-number { background: #1a73e8; color: white; }
.step.completed .step-number { background: #1e8e3e; color: white; }

.progress-track {
  height: 4px;
  background: #e8eaed;
  border-radius: 2px;
  overflow: hidden;
}

.progress-fill {
  height: 100%;
  background: linear-gradient(90deg, #1a73e8, #1e8e3e);
  border-radius: 2px;
  transition: width 0.4s ease;
}

/* Sample card */
.sample-card {
  background: white;
  border-radius: 12px;
  padding: 24px;
  border: 2px solid transparent;
  transition: border-color 0.2s;
}

.sample-card.active { border-color: #1a73e8; }

.sample-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 12px;
}

.sample-header h3 {
  margin: 0;
  font-size: 18px;
  color: #202124;
}

.word-badge {
  padding: 4px 12px;
  border-radius: 16px;
  font-size: 13px;
  font-weight: 500;
  background: #f1f3f4;
  color: #5f6368;
}

.word-badge.warning { background: #fef7e0; color: #e37400; }
.word-badge.sufficient { background: #e6f4ea; color: #1e8e3e; }

.prompt-text {
  background: #f8f9fa;
  padding: 16px;
  border-radius: 8px;
  font-size: 15px;
  line-height: 1.6;
  color: #3c4043;
  margin-bottom: 16px;
  font-style: italic;
}

.textarea-wrapper { position: relative; }

.textarea-wrapper textarea {
  width: 100%;
  min-height: 200px;
  padding: 16px;
  border: 1px solid #dadce0;
  border-radius: 8px;
  font-size: 15px;
  line-height: 1.6;
  color: #202124;
  resize: vertical;
  font-family: inherit;
  box-sizing: border-box;
}

.textarea-wrapper textarea:focus {
  outline: none;
  border-color: #1a73e8;
  box-shadow: 0 0 0 2px rgba(26, 115, 232, 0.2);
}

.paste-warning {
  position: absolute;
  bottom: 8px;
  left: 8px;
  right: 8px;
  background: #fce8e6;
  color: #d93025;
  padding: 8px 16px;
  border-radius: 6px;
  font-size: 13px;
  font-weight: 500;
  text-align: center;
  animation: fadeIn 0.2s;
}

@keyframes fadeIn { from { opacity: 0; transform: translateY(4px); } to { opacity: 1; transform: translateY(0); } }

.sample-footer {
  display: flex;
  align-items: center;
  margin-top: 12px;
}

.spacer { flex: 1; }

/* Submit section */
.submit-section {
  background: white;
  border-radius: 12px;
  padding: 24px;
}

.readiness-checks {
  display: flex;
  flex-direction: column;
  gap: 8px;
  margin-bottom: 20px;
}

.check-item {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 14px;
  color: #5f6368;
}

.check-item.ready { color: #1e8e3e; font-weight: 500; }

.error-message {
  background: #fce8e6;
  color: #d93025;
  padding: 12px 16px;
  border-radius: 8px;
  margin-bottom: 16px;
  font-size: 14px;
}

.btn-submit {
  width: 100%;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 12px;
  padding: 16px 24px;
  border: none;
  background: linear-gradient(135deg, #1a73e8, #1557b0);
  color: white;
  font-weight: 600;
  font-size: 16px;
  border-radius: 10px;
  cursor: pointer;
  transition: all 0.2s;
}

.btn-submit:hover:not(:disabled) {
  transform: translateY(-1px);
  box-shadow: 0 4px 12px rgba(26, 115, 232, 0.3);
}

.btn-submit:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.btn-primary {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  padding: 12px 32px;
  border: none;
  background: #1a73e8;
  color: white;
  font-weight: 500;
  font-size: 15px;
  border-radius: 8px;
  cursor: pointer;
}

.btn-primary:hover { background: #1557b0; }

.btn-secondary {
  padding: 10px 20px;
  border: 1px solid #dadce0;
  background: white;
  color: #1a73e8;
  font-weight: 500;
  border-radius: 8px;
  cursor: pointer;
  font-size: 14px;
}

.btn-secondary:hover { background: #f8f9fa; }
.btn-secondary:disabled { opacity: 0.4; cursor: not-allowed; }

.btn-text {
  padding: 10px 16px;
  border: none;
  background: transparent;
  color: #5f6368;
  font-weight: 500;
  cursor: pointer;
  font-size: 14px;
}

.btn-text:hover { color: #202124; }

.spinner {
  width: 20px;
  height: 20px;
  border: 2px solid rgba(255,255,255,0.3);
  border-top-color: white;
  border-radius: 50%;
  animation: spin 0.6s linear infinite;
}

@keyframes spin { to { transform: rotate(360deg); } }

@media (max-width: 768px) {
  .enrollment-content { padding: 16px; }
  .progress-steps { flex-direction: column; gap: 8px; }
  .header-badge { display: none; }
}
</style>
