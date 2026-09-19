<template>
  <div class="hallucination-page">
    <header class="page-header">
      <div class="header-left">
        <button @click="router.push('/researcher')" class="back-btn">
          <svg width="24" height="24" viewBox="0 0 24 24" fill="currentColor">
            <path d="M20 11H7.83l5.59-5.59L12 4l-8 8 8 8 1.41-1.41L7.83 13H20v-2z"/>
          </svg>
        </button>
        <div>
          <h1>Hallucination Checker</h1>
          <span class="subtitle">Verify claims, DOIs and URLs in any document</span>
        </div>
      </div>
    </header>

    <main class="page-content">
      <!-- Input surface -->
      <div class="input-card">
        <div class="input-grid">
          <!-- Text input -->
          <div class="text-input-zone">
            <label>Paste text</label>
            <textarea
              v-model="text"
              rows="10"
              placeholder="Paste text to verify — claims, citations, DOIs and URLs will be checked..."
              :disabled="checking"
            ></textarea>
            <span class="word-counter">{{ textWordCount }} words</span>
          </div>

          <!-- File input -->
          <div
            class="file-drop-zone"
            :class="{ dragging: isDragging, 'has-file': !!file }"
            @dragover.prevent="isDragging = true"
            @dragleave.prevent="isDragging = false"
            @drop.prevent="onDrop"
            @click="!file && fileInput?.click()"
          >
            <input
              ref="fileInput"
              type="file"
              accept=".pdf,.docx,.txt,.md"
              class="hidden-input"
              @change="onFileSelected"
            />
            <template v-if="!file">
              <svg width="44" height="44" viewBox="0 0 24 24" fill="#9aa0a6">
                <path d="M19.35 10.04C18.67 6.59 15.64 4 12 4 9.11 4 6.6 5.64 5.35 8.04 2.34 8.36 0 10.91 0 14c0 3.31 2.69 6 6 6h13c2.76 0 5-2.24 5-5 0-2.64-2.05-4.78-4.65-4.96zM14 13v4h-4v-4H7l5-5 5 5h-3z"/>
              </svg>
              <p><strong>Drop a document here</strong> or click to browse</p>
              <span class="file-types">.pdf, .docx, .txt, .md</span>
            </template>
            <template v-else>
              <svg width="36" height="36" viewBox="0 0 24 24" fill="#7c3aed">
                <path d="M14 2H6c-1.1 0-1.99.9-1.99 2L4 20c0 1.1.89 2 1.99 2H18c1.1 0 2-.9 2-2V8l-6-6zm-1 7V3.5L18.5 9H13z"/>
              </svg>
              <p class="file-name">{{ file.name }}</p>
              <span class="file-size">{{ formatSize(file.size) }}</span>
              <button class="btn-text danger" @click.stop="clearFile">Remove</button>
            </template>
          </div>
        </div>

        <div class="doctype-row">
          <label>Document type</label>
          <div class="doctype-toggle" role="tablist">
            <button
              type="button"
              :class="{ active: mode === 'general' }"
              :disabled="checking"
              @click="mode = 'general'"
            >Student Essay / Report</button>
            <button
              type="button"
              :class="{ active: mode === 'published_paper' }"
              :disabled="checking"
              @click="mode = 'published_paper'"
            >Published Paper Audit</button>
          </div>
          <span class="doctype-hint">
            {{ mode === 'published_paper'
              ? 'Maps numbered citations ([14], [2]–[5]) to the reference list and checks whether each cited source supports the claim.'
              : 'General claim, DOI and URL verification.' }}
          </span>
        </div>

        <div class="check-controls">
          <div class="mode-select">
            <label>Verification mode</label>
            <select v-model="evidenceMode" :disabled="checking">
              <option value="REGISTRY_ONLY">Registry Only (DOI/URL + Knowledge Base)</option>
              <option value="OFFLINE_ONLY">Offline Only (Knowledge Base)</option>
              <option value="HYBRID">Hybrid (Full Web Retrieval)</option>
            </select>
          </div>
          <button class="btn-check" :disabled="checking || !canCheck" @click="runCheck">
            <span v-if="checking" class="spinner small white"></span>
            {{ checking ? 'Checking...' : 'Check' }}
          </button>
        </div>
        <p v-if="checkError" class="error-text">{{ checkError }}</p>
      </div>

      <!-- Loading -->
      <div v-if="checking" class="loading-card">
        <div class="spinner"></div>
        <p>Verifying claims, DOIs and URLs…</p>
        <span class="loading-sub">This may take a moment for longer documents</span>
      </div>

      <!-- Results -->
      <div v-else-if="results" class="results-card">
        <div class="results-header">
          <h2>Results<template v-if="checkedFilename"> — {{ checkedFilename }}</template></h2>
          <span v-if="results.extracted_word_count" class="extracted-count">{{ results.extracted_word_count }} words extracted</span>
        </div>
        <FactCheckResults :results="results" light />
      </div>

      <!-- History -->
      <section class="history-section">
        <h2>Recent Checks</h2>
        <div v-if="history.length === 0" class="empty-history">
          <p>No previous checks yet. Your verification history will appear here.</p>
        </div>
        <div v-else class="history-list">
          <div v-for="check in history" :key="check.check_id" class="history-row">
            <div class="history-source">
              <svg v-if="check.source === 'file'" width="20" height="20" viewBox="0 0 24 24" fill="#7c3aed">
                <path d="M14 2H6c-1.1 0-1.99.9-1.99 2L4 20c0 1.1.89 2 1.99 2H18c1.1 0 2-.9 2-2V8l-6-6zm-1 7V3.5L18.5 9H13z"/>
              </svg>
              <svg v-else width="20" height="20" viewBox="0 0 24 24" fill="#5f6368">
                <path d="M3 5h18v2H3V5zm0 4h18v2H3V9zm0 4h12v2H3v-2zm0 4h12v2H3v-2z"/>
              </svg>
              <div class="history-info">
                <span class="history-name">{{ check.filename || 'Pasted text' }}</span>
                <span class="history-meta">{{ formatDate(check.created_at) }} • {{ check.word_count || 0 }} words • {{ check.claim_count || 0 }} claims</span>
              </div>
            </div>
            <div v-if="check.summary" class="history-counts">
              <span class="count-pill supported" title="Supported">✓ {{ check.summary.supported || 0 }}</span>
              <span class="count-pill unsupported" title="Unsupported">? {{ check.summary.unsupported || 0 }}</span>
              <span class="count-pill contradicted" title="Contradicted">✗ {{ check.summary.contradicted || 0 }}</span>
              <span class="count-pill unknown" title="Unknown">○ {{ check.summary.unknown || 0 }}</span>
            </div>
          </div>
        </div>
      </section>
    </main>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import axios from 'axios'
import { getApiUrl } from '@/utils/api-url'
import FactCheckResults from '@/components/integrity/FactCheckResults.vue'

const API = getApiUrl()
const router = useRouter()

const text = ref('')
const file = ref(null)
const fileInput = ref(null)
const isDragging = ref(false)
const evidenceMode = ref('REGISTRY_ONLY')
const mode = ref('general')  // 'general' | 'published_paper'
const checking = ref(false)
const checkError = ref('')
const results = ref(null)
const checkedFilename = ref('')
const history = ref([])

const ACCEPTED_EXTENSIONS = ['.pdf', '.docx', '.txt', '.md']

const textWordCount = computed(() => {
  const t = text.value.trim()
  return t ? t.split(/\s+/).length : 0
})

const canCheck = computed(() => !!file.value || text.value.trim().length > 0)

function formatSize(bytes) {
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`
}

function formatDate(dateStr) {
  if (!dateStr) return ''
  return new Date(dateStr).toLocaleDateString('en-US', { month: 'short', day: 'numeric', hour: 'numeric', minute: '2-digit' })
}

function isAcceptedFile(f) {
  const name = f.name.toLowerCase()
  return ACCEPTED_EXTENSIONS.some(ext => name.endsWith(ext))
}

function onFileSelected(e) {
  const selected = e.target.files?.[0]
  if (selected && isAcceptedFile(selected)) {
    file.value = selected
    checkError.value = ''
  } else if (selected) {
    checkError.value = 'Unsupported file type. Use .pdf, .docx, .txt or .md'
  }
  e.target.value = ''
}

function onDrop(e) {
  isDragging.value = false
  const dropped = e.dataTransfer.files?.[0]
  if (dropped && isAcceptedFile(dropped)) {
    file.value = dropped
    checkError.value = ''
  } else if (dropped) {
    checkError.value = 'Unsupported file type. Use .pdf, .docx, .txt or .md'
  }
}

function clearFile() {
  file.value = null
}

async function runCheck() {
  if (!canCheck.value || checking.value) return
  checking.value = true
  checkError.value = ''
  results.value = null
  checkedFilename.value = ''

  try {
    let started
    if (file.value) {
      const form = new FormData()
      form.append('file', file.value)
      form.append('evidence_mode', evidenceMode.value)
      form.append('mode', mode.value)
      const resp = await axios.post(`${API}/api/hallucination/check-file`, form, {
        headers: { 'Content-Type': 'multipart/form-data' },
        timeout: 180000  // allow large (up to 100MB) upload + text extraction; the check itself runs async
      })
      started = resp.data
      checkedFilename.value = file.value.name
    } else {
      const resp = await axios.post(`${API}/api/hallucination/check`, {
        text: text.value,
        evidence_mode: evidenceMode.value,
        mode: mode.value
      }, { timeout: 60000 })
      started = resp.data
    }

    // Short text / extraction errors return a direct result (no job_id).
    if (!started.job_id) {
      results.value = started
    } else {
      const done = await pollJob(started.job_id)
      results.value = done
      if (done.filename) checkedFilename.value = done.filename
    }
    fetchHistory()
  } catch (e) {
    checkError.value = e.response?.data?.detail || e.message || 'Verification failed. Please try again.'
  } finally {
    checking.value = false
  }
}

// Poll a fact-check job until it finishes. Each poll is a short request, so the
// edge proxy never resets the connection (fixes ERR_HTTP2_PROTOCOL_ERROR on long docs).
async function pollJob(jobId) {
  const deadline = Date.now() + 20 * 60 * 1000  // up to 20 minutes (full papers take longer)
  while (Date.now() < deadline) {
    await new Promise(r => setTimeout(r, 3000))
    let resp
    try {
      resp = await axios.get(`${API}/api/hallucination/job/${jobId}`, { timeout: 30000 })
    } catch (e) {
      if (e.response?.status === 404) throw new Error('Verification job expired — please try again')
      continue  // transient hiccup — keep polling
    }
    const d = resp.data
    if (d.status === 'processing') continue
    if (d.status === 'error') throw new Error(d.error || 'Verification failed')
    return d  // done — full result payload
  }
  throw new Error('Verification timed out. Try a shorter document.')
}

async function fetchHistory() {
  try {
    const resp = await axios.get(`${API}/api/hallucination/history`)
    history.value = resp.data.checks || []
  } catch (e) {
    console.error('Failed to fetch check history:', e)
  }
}

onMounted(() => {
  fetchHistory()
})
</script>

<style scoped>
.hallucination-page {
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
  font-size: 13px;
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

.back-btn:hover {
  background: #f1f3f4;
}

.page-content {
  max-width: 960px;
  margin: 0 auto;
  padding: 24px;
}

/* Input card */
.input-card {
  background: white;
  border-radius: 12px;
  padding: 24px;
  border-top: 4px solid #7c3aed;
  margin-bottom: 24px;
}

.input-grid {
  display: grid;
  grid-template-columns: 1fr 280px;
  gap: 20px;
  margin-bottom: 20px;
}

.text-input-zone {
  display: flex;
  flex-direction: column;
  position: relative;
}

.text-input-zone label,
.mode-select label {
  font-size: 14px;
  font-weight: 500;
  color: #202124;
  margin-bottom: 8px;
  display: block;
}

.text-input-zone textarea {
  flex: 1;
  width: 100%;
  padding: 14px 16px;
  border: 1px solid #dadce0;
  border-radius: 8px;
  font-size: 14px;
  line-height: 1.6;
  font-family: inherit;
  color: #202124;
  background: #fff;
  resize: vertical;
  box-sizing: border-box;
  min-height: 220px;
}

.text-input-zone textarea:focus {
  outline: none;
  border-color: #7c3aed;
  box-shadow: 0 0 0 2px rgba(124, 58, 237, 0.15);
}

.word-counter {
  position: absolute;
  bottom: 10px;
  right: 14px;
  font-size: 12px;
  color: #80868b;
  background: rgba(255,255,255,0.9);
  padding: 2px 8px;
  border-radius: 8px;
}

/* File drop zone */
.file-drop-zone {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 8px;
  border: 2px dashed #dadce0;
  border-radius: 12px;
  padding: 24px 16px;
  text-align: center;
  cursor: pointer;
  transition: border-color 0.2s, background 0.2s;
  margin-top: 26px;
}

.file-drop-zone:hover {
  border-color: #c4b5fd;
  background: #faf8ff;
}

.file-drop-zone.dragging {
  border-color: #7c3aed;
  background: #f5f1fe;
}

.file-drop-zone.has-file {
  cursor: default;
  border-style: solid;
  border-color: #c4b5fd;
  background: #faf8ff;
}

.file-drop-zone p {
  margin: 0;
  font-size: 14px;
  color: #3c4043;
}

.file-types {
  font-size: 12px;
  color: #80868b;
}

.file-name {
  font-weight: 500;
  word-break: break-all;
}

.file-size {
  font-size: 12px;
  color: #5f6368;
}

.hidden-input {
  display: none;
}

/* Document-type toggle */
.doctype-row {
  margin-bottom: 16px;
}

.doctype-row label {
  font-size: 14px;
  font-weight: 500;
  color: #202124;
  margin-bottom: 8px;
  display: block;
}

.doctype-toggle {
  display: inline-flex;
  border: 1px solid #dadce0;
  border-radius: 10px;
  overflow: hidden;
  background: #f8f9fa;
}

.doctype-toggle button {
  border: none;
  background: transparent;
  padding: 10px 18px;
  font-size: 13.5px;
  font-weight: 600;
  color: #5f6368;
  cursor: pointer;
  transition: background 0.15s, color 0.15s;
}

.doctype-toggle button + button {
  border-left: 1px solid #dadce0;
}

.doctype-toggle button.active {
  background: #7c3aed;
  color: #fff;
}

.doctype-toggle button:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}

.doctype-hint {
  display: block;
  margin-top: 8px;
  font-size: 12.5px;
  color: #5f6368;
  line-height: 1.5;
}

/* Controls */
.check-controls {
  display: flex;
  align-items: flex-end;
  justify-content: space-between;
  gap: 16px;
  flex-wrap: wrap;
}

.mode-select select {
  padding: 12px 14px;
  border: 1px solid #dadce0;
  border-radius: 8px;
  font-size: 14px;
  color: #202124;
  background: white;
  cursor: pointer;
  min-width: 300px;
}

.mode-select select:focus {
  outline: none;
  border-color: #7c3aed;
}

.btn-check {
  display: inline-flex;
  align-items: center;
  gap: 10px;
  padding: 14px 40px;
  border: none;
  background: linear-gradient(135deg, #7c3aed, #6d28d9);
  color: white;
  font-weight: 600;
  font-size: 15px;
  border-radius: 10px;
  cursor: pointer;
  transition: all 0.2s;
}

.btn-check:hover:not(:disabled) {
  transform: translateY(-1px);
  box-shadow: 0 4px 12px rgba(124, 58, 237, 0.3);
}

.btn-check:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.btn-text {
  border: none;
  background: transparent;
  font-weight: 500;
  font-size: 13px;
  cursor: pointer;
  padding: 4px 10px;
  border-radius: 6px;
}

.btn-text.danger {
  color: #c5221f;
}

.btn-text.danger:hover {
  background: #fce8e6;
}

.error-text {
  color: #d93025;
  font-size: 13px;
  margin: 12px 0 0;
}

/* Loading */
.loading-card {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 12px;
  background: white;
  border-radius: 12px;
  padding: 60px 24px;
  margin-bottom: 24px;
  text-align: center;
}

.loading-card p {
  margin: 0;
  color: #202124;
  font-weight: 500;
  font-size: 16px;
}

.loading-sub {
  font-size: 13px;
  color: #5f6368;
}

/* Results */
.results-card {
  background: white;
  border-radius: 12px;
  padding: 24px;
  margin-bottom: 24px;
}

.results-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 16px;
  flex-wrap: wrap;
  gap: 8px;
}

.results-header h2 {
  font-size: 17px;
  font-weight: 500;
  color: #202124;
  margin: 0;
}

.extracted-count {
  font-size: 13px;
  color: #5f6368;
}

.summary-strip {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
  margin-bottom: 20px;
}

.summary-pill {
  padding: 6px 14px;
  border-radius: 16px;
  font-size: 13px;
  font-weight: 500;
}

.summary-pill.supported { background: #e6f4ea; color: #137333; }
.summary-pill.unsupported { background: #fef7e0; color: #b06000; }
.summary-pill.contradicted { background: #fce8e6; color: #c5221f; }
.summary-pill.unknown { background: #f1f3f4; color: #5f6368; }

/* History */
.history-section h2 {
  font-size: 18px;
  font-weight: 500;
  color: #202124;
  margin: 0 0 16px;
}

.empty-history {
  background: white;
  border-radius: 12px;
  padding: 32px;
  text-align: center;
}

.empty-history p {
  margin: 0;
  color: #5f6368;
  font-size: 14px;
}

.history-list {
  background: white;
  border-radius: 12px;
  overflow: hidden;
}

.history-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 16px;
  padding: 14px 20px;
  border-bottom: 1px solid #f1f3f4;
  flex-wrap: wrap;
}

.history-row:last-child {
  border-bottom: none;
}

.history-source {
  display: flex;
  align-items: center;
  gap: 12px;
}

.history-info {
  display: flex;
  flex-direction: column;
}

.history-name {
  font-weight: 500;
  color: #202124;
  font-size: 14px;
}

.history-meta {
  font-size: 12px;
  color: #80868b;
}

.history-counts {
  display: flex;
  gap: 6px;
}

.count-pill {
  padding: 3px 10px;
  border-radius: 12px;
  font-size: 12px;
  font-weight: 600;
}

.count-pill.supported { background: #e6f4ea; color: #137333; }
.count-pill.unsupported { background: #fef7e0; color: #b06000; }
.count-pill.contradicted { background: #fce8e6; color: #c5221f; }
.count-pill.unknown { background: #f1f3f4; color: #5f6368; }

/* Spinner */
.spinner {
  width: 36px;
  height: 36px;
  border: 3px solid #e0e0e0;
  border-top-color: #7c3aed;
  border-radius: 50%;
  animation: spin 1s linear infinite;
}

.spinner.small {
  width: 18px;
  height: 18px;
  border-width: 2px;
}

.spinner.white {
  border-color: rgba(255,255,255,0.3);
  border-top-color: white;
}

@keyframes spin {
  to { transform: rotate(360deg); }
}

@media (max-width: 768px) {
  .input-grid {
    grid-template-columns: 1fr;
  }
  .file-drop-zone {
    margin-top: 0;
  }
  .mode-select select {
    min-width: 0;
    width: 100%;
  }
}
</style>
