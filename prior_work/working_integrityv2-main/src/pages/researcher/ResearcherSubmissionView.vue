<template>
  <div class="submission-view-page">
    <!-- Header -->
    <header class="page-header">
      <div class="header-left">
        <button @click="router.push('/researcher')" class="back-btn">
          <svg width="24" height="24" viewBox="0 0 24 24" fill="currentColor">
            <path d="M20 11H7.83l5.59-5.59L12 4l-8 8 8 8 1.41-1.41L7.83 13H20v-2z"/>
          </svg>
        </button>
        <div class="header-info">
          <h1>{{ title || 'Submission' }}</h1>
        </div>
      </div>
      <div class="summary-chips">
        <!-- Whole-document trust/stylometry verdict intentionally omitted —
             researcher reports surface per-author stylometry only (below). -->
        <span v-if="wordCount != null" class="chip">
          {{ wordCount }} words
        </span>
        <span v-if="submission?.submitted_at" class="chip">
          Submitted {{ formatDate(submission.submitted_at) }}
        </span>
      </div>
    </header>

    <main class="page-content">
      <div v-if="loading" class="loading">
        <div class="spinner"></div>
        <span>Loading submission...</span>
      </div>

      <template v-else>
        <!-- Author(s) + per-author stylometry. Shown for every researcher
             report; collaborative reports add the contribution split. -->
        <section v-if="reportAuthors.length" class="authors-section">
          <div class="authors-head">
            <h2>{{ isMultiAuthor ? 'Authors &amp; Contributions' : 'Author &amp; Stylometry' }}</h2>
            <span class="authors-sub">{{ isMultiAuthor
              ? reportAuthors.length + ' authors · each judged against their own stylometry profile'
              : 'Authorship verified against the enrolled writing profile' }}</span>
          </div>

          <!-- Visual contribution meter — stacked bars colored per author,
               matching each author's live cursor color in the editor. -->
          <div v-if="isMultiAuthor && hasContributions" class="contrib-meter">
            <div class="contrib-block">
              <div class="contrib-track-label"><span>Final document</span><span class="contrib-hint">share of words</span></div>
              <div class="contrib-track">
                <div v-for="a in contributionOrder" :key="'f-' + a.user_id" class="contrib-seg"
                  :style="{ width: (a.contribution?.final_pct || 0) + '%', background: authorColor(a.user_id) }"
                  :title="a.name + ' · ' + (a.contribution?.final_pct ?? 0) + '% · ' + (a.contribution?.final_words ?? 0) + ' words'">
                  <span v-if="(a.contribution?.final_pct || 0) >= 10" class="contrib-seg-label">{{ Math.round(a.contribution?.final_pct || 0) }}%</span>
                </div>
              </div>
            </div>
            <div v-if="hasEffort" class="contrib-block">
              <div class="contrib-track-label"><span>Writing effort</span><span class="contrib-hint">keystrokes</span></div>
              <div class="contrib-track">
                <div v-for="a in contributionOrder" :key="'e-' + a.user_id" class="contrib-seg"
                  :style="{ width: (a.contribution?.effort_pct || 0) + '%', background: authorColor(a.user_id) }"
                  :title="a.name + ' · ' + (a.contribution?.effort_pct ?? 0) + '% · ' + (a.contribution?.keystrokes ?? 0) + ' keys'">
                  <span v-if="(a.contribution?.effort_pct || 0) >= 10" class="contrib-seg-label">{{ Math.round(a.contribution?.effort_pct || 0) }}%</span>
                </div>
              </div>
            </div>
            <div class="contrib-legend">
              <span v-for="a in contributionOrder" :key="'l-' + a.user_id" class="contrib-legend-item">
                <span class="contrib-swatch" :style="{ background: authorColor(a.user_id) }"></span>{{ a.name }}
              </span>
            </div>
          </div>

          <div class="author-table" :class="{ 'single-author': !isMultiAuthor }">
            <div class="author-row author-row-head">
              <span class="col-name">Author</span>
              <template v-if="isMultiAuthor">
                <span class="col-metric">Final doc</span>
                <span class="col-metric">Effort</span>
              </template>
              <span v-else class="col-metric">Words</span>
              <span class="col-verdict">Stylometry verdict</span>
            </div>
            <div v-for="a in reportAuthors" :key="a.user_id" class="author-row">
              <span class="col-name">
                <span class="author-dot"></span>
                {{ a.name }}<span v-if="a.is_primary && isMultiAuthor" class="primary-tag">primary</span>
              </span>
              <template v-if="isMultiAuthor">
                <span class="col-metric">
                  <strong>{{ a.contribution?.final_pct != null ? a.contribution.final_pct + '%' : '—' }}</strong>
                  <span class="metric-sub">{{ a.contribution?.final_words ?? 0 }} words</span>
                </span>
                <span class="col-metric">
                  <strong>{{ a.contribution?.effort_pct != null ? a.contribution.effort_pct + '%' : '—' }}</strong>
                  <span class="metric-sub">{{ a.contribution?.keystrokes ?? 0 }} keys</span>
                </span>
              </template>
              <span v-else class="col-metric">
                <strong>{{ a.contribution?.final_words ?? wordCount ?? '—' }}</strong>
                <span class="metric-sub">in final document</span>
              </span>
              <span class="col-verdict">
                <span v-if="!a.stylometry_enrolled" class="author-verdict gray">not enrolled</span>
                <span v-else-if="!a.stylometry_v3" class="author-verdict gray">pending</span>
                <span v-else class="author-verdict" :class="authorVerdictTone(a.stylometry_v3.verdict)">
                  {{ authorVerdictLabel(a.stylometry_v3) }}
                </span>
              </span>
            </div>
          </div>
        </section>

        <!-- Who wrote what — every passage attributed to its author -->
        <section v-if="isMultiAuthor && contributionSegments.length" class="contrib-doc-section">
          <div class="authors-head">
            <h2>Who Wrote What</h2>
            <span class="authors-sub">Every passage is attributed to its author from the live keystroke record</span>
          </div>
          <div class="cww-legend">
            <span v-for="a in reportAuthors" :key="a.user_id" class="cww-leg">
              <span class="cww-dot" :style="{ background: authorColor(a.user_id) }"></span>
              {{ a.name }}
              <span class="cww-words">{{ a.contribution?.final_words ?? 0 }}w · {{ a.contribution?.final_pct ?? 0 }}%</span>
            </span>
          </div>
          <div class="cww-doc">
            <span v-for="(seg, i) in contributionSegments" :key="i" class="cww-run"
              :style="{ background: authorBg(seg.user_id), boxShadow: 'inset 3px 0 0 ' + authorColor(seg.user_id) }"
              :title="authorNameById(seg.user_id)">{{ seg.text }}</span>
          </div>
        </section>

        <div class="deliverable-cards">
          <!-- (a) Session Replay Video -->
          <div class="deliverable-card">
            <div class="card-title">
              <svg width="22" height="22" viewBox="0 0 24 24" fill="#7c3aed">
                <path d="M17 10.5V7c0-.55-.45-1-1-1H4c-.55 0-1 .45-1 1v10c0 .55.45 1 1 1h12c.55 0 1-.45 1-1v-3.5l4 4v-11l-4 4z"/>
              </svg>
              <h3>Session Replay Video</h3>
            </div>

            <div v-if="videoState === 'probing'" class="card-busy">
              <div class="spinner small"></div>
              <span>Checking for existing video...</span>
            </div>

            <div v-else-if="videoState === 'rendering'" class="card-busy column">
              <span>Rendering session video… {{ renderProgress }}%</span>
              <div class="progress-track">
                <div class="progress-fill" :style="{ width: renderProgress + '%' }"></div>
              </div>
            </div>

            <div v-else-if="videoState === 'uploading'" class="card-busy">
              <div class="spinner small"></div>
              <span>Uploading video...</span>
            </div>

            <div v-else-if="videoState === 'ready'" class="video-block">
              <video :src="videoUrl" controls class="session-video"></video>
              <div class="card-actions">
                <button class="btn-primary" @click="downloadVideo">
                  {{ videoIsMp4 ? 'Download MP4' : 'Download Video' }}
                </button>
                <button v-if="!shareUrl" class="btn-outline" :disabled="shareBusy" @click="createShareLink">
                  {{ shareBusy ? 'Creating link...' : 'Share' }}
                </button>
              </div>
              <div v-if="shareUrl" class="share-block">
                <div class="share-row">
                  <input class="share-input" :value="shareUrl" readonly @focus="$event.target.select()" />
                  <button class="btn-outline small" @click="copyShareUrl">{{ shareCopied ? 'Copied!' : 'Copy' }}</button>
                </div>
                <button class="btn-text danger" :disabled="shareBusy" @click="revokeShareLinks">Revoke links</button>
              </div>
              <p v-if="shareError" class="error-text">{{ shareError }}</p>
              <p v-if="!engineStatus.ffmpeg" class="note-text">Video is in WebM format (MP4 conversion engine unavailable) — it plays in all modern browsers.</p>
            </div>

            <div v-else-if="videoState === 'unavailable'" class="card-empty">
              <p>No session recording is available for this submission.</p>
            </div>

            <div v-else-if="videoState === 'error'" class="card-empty">
              <p class="error-text">{{ videoError }}</p>
              <button class="btn-outline" @click="initVideo">Retry</button>
            </div>
          </div>

          <!-- (b) Original PDF -->
          <div class="deliverable-card">
            <div class="card-title">
              <svg width="22" height="22" viewBox="0 0 24 24" fill="#c5221f">
                <path d="M14 2H6c-1.1 0-1.99.9-1.99 2L4 20c0 1.1.89 2 1.99 2H18c1.1 0 2-.9 2-2V8l-6-6zm-1 7V3.5L18.5 9H13z"/>
              </svg>
              <h3>Original PDF</h3>
            </div>
            <p class="card-description">A snapshot of the submitted document, generated server-side.</p>

            <div class="card-actions">
              <button class="btn-primary" :disabled="pdfBusy" @click="downloadPdf">
                <span v-if="pdfBusy" class="spinner small white"></span>
                {{ pdfBusy ? 'Preparing PDF...' : (pdfReady ? 'Download PDF' : 'Generate PDF') }}
              </button>
            </div>
            <p v-if="pdfError" class="error-text">{{ pdfError }}</p>
          </div>

          <!-- The whole-document integrity report (trust score, flags) is
               intentionally omitted — researcher reports surface per-author
               stylometry only, shown in the "Author & Stylometry" section above. -->
        </div>

        <!-- Interactive playback -->
        <section v-if="snapshots.length > 0 || playbackEvents.length > 0" class="playback-section">
          <h2>Interactive Session Replay</h2>
          <PlaybackViewer :snapshots="snapshots" :events="playbackEvents" :authors="playbackAuthors" :meta="playbackMeta" />
        </section>
      </template>
    </main>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onBeforeUnmount } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import axios from 'axios'
import { useAuth } from '@/composables/auth'
import { getApiUrl } from '@/utils/api-url'
import PlaybackViewer from '@/components/playback/PlaybackViewer.vue'
import { renderSessionToWebM } from '@/utils/playback-video-renderer'

const props = defineProps(['id'])
const router = useRouter()
const route = useRoute()
const { user, initAuth } = useAuth()

const API = getApiUrl()
const submissionId = computed(() => props.id || route.params.id)

const loading = ref(true)
const submission = ref(null)
const authorsData = ref(null)
const snapshots = ref([])
const playbackEvents = ref([])
const playbackAuthors = ref({})

const isShared = computed(() => !!authorsData.value?.is_shared)
const reportAuthors = computed(() => authorsData.value?.authors || [])
const isMultiAuthor = computed(() => reportAuthors.value.length > 1)

// Deterministic per-author color — matches the editor's collaboration cursor
// hue so the meter, table dots, who-wrote-what runs and live cursors all agree.
function authorHue(id) {
  const str = String(id || 'anonymous')
  let hash = 0
  for (let i = 0; i < str.length; i++) hash = ((hash << 5) - hash + str.charCodeAt(i)) | 0
  return Math.abs(hash) % 360
}
function authorColor(id) { return `hsl(${authorHue(id)}, 65%, 45%)` }
function authorBg(id) { return `hsl(${authorHue(id)}, 70%, 93%)` }
function authorNameById(uid) {
  return reportAuthors.value.find(a => a.user_id === uid)?.name || 'Author'
}
const hasContributions = computed(() =>
  reportAuthors.value.some(a => a.contribution?.final_pct != null || a.contribution?.effort_pct != null)
)
const hasEffort = computed(() =>
  reportAuthors.value.some(a => (a.contribution?.effort_pct || 0) > 0)
)
// Largest contributor first for a stable, readable meter.
const contributionOrder = computed(() =>
  [...reportAuthors.value].sort((x, y) => (y.contribution?.final_pct || 0) - (x.contribution?.final_pct || 0))
)
// Ordered 'who wrote what' runs from the document marks (from /authors).
const contributionSegments = computed(() => authorsData.value?.segments || [])
const totalDurationMs = ref(0)
const engineStatus = ref({ ffmpeg: false, pdf: false })

// Video state
const videoState = ref('probing') // probing | rendering | uploading | ready | unavailable | error
const renderProgress = ref(0)
const videoUrl = ref(null)
const videoBlobType = ref('')
const videoError = ref('')

// Share state
const shareUrl = ref('')
const shareBusy = ref(false)
const shareCopied = ref(false)
const shareError = ref('')

// PDF state
const pdfBusy = ref(false)
const pdfReady = ref(false)
const pdfError = ref('')

// Report state
const reportLoading = ref(false)
const reportHtml = ref('')
const reportError = ref('')

const title = computed(() =>
  submission.value?.assignment_title || submission.value?.topic_title || submission.value?.title || ''
)

// Only ever the AUTHOR's name — never fall back to the viewer's own name
// (a co-author or PI watching someone else's replay must not see themselves
// labeled as the writer).
const authorName = computed(() =>
  submission.value?.student_name
  || submission.value?.author_name
  || reportAuthors.value.find(a => a.is_primary)?.name
  || reportAuthors.value[0]?.name
  || 'Author'
)

function authorVerdictTone(v) {
  if (v === 'verified') return 'green'
  if (v === 'flagged') return 'red'
  if (v === 'review_required' || v === 'inconclusive') return 'amber'
  return 'gray'
}
function authorVerdictLabel(s) {
  const v = s?.verdict
  const cos = s?.cosine_score
  const pct = (cos != null) ? ` · ${Math.round(cos * 100)}%` : ''
  if (v === 'verified') return `Verified${pct}`
  if (v === 'flagged') return `Flagged${pct}`
  if (v === 'unavailable') return 'Unavailable'
  if (v === 'review_required') return 'Needs review'
  if (v === 'inconclusive') return 'Inconclusive'
  return v || 'Pending'
}

const wordCount = computed(() => {
  if (submission.value?.word_count != null) return submission.value.word_count
  const content = submission.value?.content
  if (typeof content === 'string' && content.trim()) {
    return content.trim().split(/\s+/).length
  }
  return null
})

const videoIsMp4 = computed(() => videoBlobType.value.includes('mp4'))

const playbackMeta = computed(() => ({
  studentName: authorName.value,
  title: title.value,
  totalDurationMs: totalDurationMs.value
}))

let videoBlob = null

function formatDate(dateStr) {
  if (!dateStr) return ''
  return new Date(dateStr).toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric', hour: 'numeric', minute: '2-digit' })
}

function setVideoBlob(blob) {
  videoBlob = blob
  videoBlobType.value = blob.type || ''
  if (videoUrl.value) URL.revokeObjectURL(videoUrl.value)
  videoUrl.value = URL.createObjectURL(blob)
  videoState.value = 'ready'
}

async function fetchExistingVideo() {
  const resp = await axios.get(`${API}/api/research/submissions/${submissionId.value}/video`, {
    responseType: 'blob'
  })
  return resp.data
}

async function initVideo() {
  videoState.value = 'probing'
  videoError.value = ''
  try {
    // Probe for an existing video first
    const blob = await fetchExistingVideo()
    setVideoBlob(blob)
    return
  } catch (e) {
    if (e.response?.status !== 404) {
      videoError.value = 'Failed to load session video'
      videoState.value = 'error'
      return
    }
    // 404 → no video yet, fall through to generation
  }

  if (!snapshots.value.length) {
    videoState.value = 'unavailable'
    return
  }

  try {
    // Render the session locally into a WebM blob
    videoState.value = 'rendering'
    renderProgress.value = 0
    const rendered = await renderSessionToWebM(snapshots.value, {
      title: title.value,
      authorName: authorName.value,
      onProgress: (p) => {
        const pct = p <= 1 ? p * 100 : p
        renderProgress.value = Math.min(100, Math.round(pct))
      }
    })

    // Upload to the backend (server converts to MP4 when ffmpeg is available)
    videoState.value = 'uploading'
    const form = new FormData()
    form.append('file', rendered, 'session.webm')
    await axios.post(`${API}/api/research/submissions/${submissionId.value}/video`, form, {
      headers: { 'Content-Type': 'multipart/form-data' }
    })

    // Fetch back the stored (possibly converted) video
    const blob = await fetchExistingVideo()
    setVideoBlob(blob)
  } catch (e) {
    console.error('Video generation failed:', e)
    videoError.value = e.response?.data?.detail || 'Failed to generate session video'
    videoState.value = 'error'
  }
}

function downloadVideo() {
  if (!videoBlob) return
  const ext = videoIsMp4.value ? 'mp4' : 'webm'
  const a = document.createElement('a')
  a.href = videoUrl.value
  a.download = `${(title.value || 'session').replace(/[^\w\- ]+/g, '')} - session.${ext}`
  document.body.appendChild(a)
  a.click()
  document.body.removeChild(a)
}

async function createShareLink() {
  shareBusy.value = true
  shareError.value = ''
  try {
    const resp = await axios.post(`${API}/api/research/submissions/${submissionId.value}/share`, {
      scope: ['video', 'playback', 'report']
    })
    shareUrl.value = resp.data.share_url
  } catch (e) {
    shareError.value = e.response?.data?.detail || 'Failed to create share link'
  } finally {
    shareBusy.value = false
  }
}

function copyShareUrl() {
  navigator.clipboard.writeText(shareUrl.value)
  shareCopied.value = true
  setTimeout(() => { shareCopied.value = false }, 2000)
}

async function revokeShareLinks() {
  shareBusy.value = true
  shareError.value = ''
  try {
    await axios.delete(`${API}/api/research/submissions/${submissionId.value}/share`)
    shareUrl.value = ''
  } catch (e) {
    shareError.value = e.response?.data?.detail || 'Failed to revoke share links'
  } finally {
    shareBusy.value = false
  }
}

async function downloadPdf() {
  pdfBusy.value = true
  pdfError.value = ''
  try {
    if (!pdfReady.value) {
      await axios.post(`${API}/api/research/submissions/${submissionId.value}/generate-pdf`)
      pdfReady.value = true
    }
    const resp = await axios.get(`${API}/api/research/submissions/${submissionId.value}/pdf`, {
      responseType: 'blob'
    })
    const url = URL.createObjectURL(resp.data)
    const a = document.createElement('a')
    a.href = url
    a.download = `${(title.value || 'submission').replace(/[^\w\- ]+/g, '')}.pdf`
    document.body.appendChild(a)
    a.click()
    document.body.removeChild(a)
    URL.revokeObjectURL(url)
  } catch (e) {
    if (e.response?.status === 503) {
      pdfError.value = 'The PDF engine is temporarily unavailable on the server. Please try again in a few minutes.'
    } else {
      pdfError.value = e.response?.data?.detail || 'Failed to generate PDF'
    }
  } finally {
    pdfBusy.value = false
  }
}

async function loadReport() {
  reportLoading.value = true
  reportError.value = ''
  try {
    const resp = await axios.get(`${API}/api/submissions/${submissionId.value}/report`, {
      responseType: 'text',
      transformResponse: [(data) => data]
    })
    reportHtml.value = resp.data
  } catch (e) {
    reportError.value = 'Failed to load stylometry report'
  } finally {
    reportLoading.value = false
  }
}

function openReportInNewTab() {
  const blob = new Blob([reportHtml.value], { type: 'text/html' })
  const url = URL.createObjectURL(blob)
  window.open(url, '_blank')
  setTimeout(() => URL.revokeObjectURL(url), 60000)
}

onMounted(async () => {
  if (!user.value) await initAuth()

  loading.value = true
  try {
    const [subResp, playbackResp, eventsResp, statusResp, authorsResp] = await Promise.allSettled([
      axios.get(`${API}/api/submissions/${submissionId.value}`),
      axios.get(`${API}/api/session-playback/${submissionId.value}`),
      axios.get(`${API}/api/session-playback/${submissionId.value}/events`),
      axios.get(`${API}/api/research/status`),
      axios.get(`${API}/api/research/submissions/${submissionId.value}/authors`),
    ])

    if (subResp.status === 'fulfilled') {
      submission.value = subResp.value.data
      if (submission.value?.has_pdf) pdfReady.value = true
    }
    if (authorsResp.status === 'fulfilled') {
      authorsData.value = authorsResp.value.data
    }
    if (playbackResp.status === 'fulfilled') {
      snapshots.value = playbackResp.value.data.snapshots || []
      totalDurationMs.value = playbackResp.value.data.total_duration_ms || 0
    }
    if (eventsResp.status === 'fulfilled' && eventsResp.value.data?.found) {
      playbackEvents.value = eventsResp.value.data.events || []
      playbackAuthors.value = eventsResp.value.data.authors || {}
    }
    if (statusResp.status === 'fulfilled') {
      engineStatus.value = statusResp.value.data
    }
  } finally {
    loading.value = false
  }

  // Kick off video + report in parallel (non-blocking for the page)
  initVideo()
  loadReport()
})

onBeforeUnmount(() => {
  if (videoUrl.value) URL.revokeObjectURL(videoUrl.value)
})
</script>

<style scoped>
.submission-view-page {
  min-height: 100vh;
  background: #f8f9fa;
}

/* Per-author contributions table */
.authors-section {
  background: #fff;
  border: 1px solid #e5e7eb;
  border-radius: 14px;
  padding: 20px 22px;
  margin-bottom: 20px;
}
.authors-head { display: flex; align-items: baseline; gap: 12px; flex-wrap: wrap; margin-bottom: 14px; }
.authors-head h2 { font-size: 18px; margin: 0; color: #202124; }
.authors-sub { font-size: 12.5px; color: #5f6368; }
.author-table { display: flex; flex-direction: column; }
.author-row {
  display: grid;
  grid-template-columns: 2fr 1fr 1fr 1.4fr;
  gap: 12px;
  align-items: center;
  padding: 12px 8px;
  border-bottom: 1px solid #f1f3f4;
}
.author-table.single-author .author-row { grid-template-columns: 2fr 1fr 1.4fr; }

/* Contribution meter */
.contrib-meter { margin: 4px 0 20px; display: flex; flex-direction: column; gap: 12px; }
.contrib-block { display: flex; flex-direction: column; gap: 6px; }
.contrib-track-label { display: flex; justify-content: space-between; align-items: baseline; font-size: 12px; color: #5f6368; font-weight: 600; }
.contrib-hint { font-weight: 400; color: #9aa0a6; font-size: 11px; }
.contrib-track { display: flex; height: 22px; border-radius: 7px; overflow: hidden; background: #f1f3f4; }
.contrib-seg { display: flex; align-items: center; justify-content: center; min-width: 2px; transition: width 0.4s ease; }
.contrib-seg-label { font-size: 11px; font-weight: 700; color: #fff; text-shadow: 0 1px 1px rgba(0,0,0,0.25); }
.contrib-legend { display: flex; flex-wrap: wrap; gap: 14px; margin-top: 2px; }
.contrib-legend-item { display: flex; align-items: center; gap: 6px; font-size: 12.5px; color: #3c4043; }
.contrib-swatch { width: 12px; height: 12px; border-radius: 3px; flex-shrink: 0; }

/* Who wrote what */
.contrib-doc-section {
  background: #fff; border: 1px solid #e5e7eb; border-radius: 14px;
  padding: 20px 22px; margin-bottom: 20px;
}
.cww-legend { display: flex; flex-wrap: wrap; gap: 16px; margin: 4px 0 16px; }
.cww-leg { display: flex; align-items: center; gap: 7px; font-size: 13.5px; font-weight: 600; color: #202124; }
.cww-dot { width: 11px; height: 11px; border-radius: 50%; flex-shrink: 0; }
.cww-words { font-weight: 400; color: #80868b; font-size: 12px; }
.cww-doc {
  font-family: 'Georgia', 'Times New Roman', serif; font-size: 15.5px; line-height: 2.1;
  color: #1a1a1a; max-height: 60vh; overflow-y: auto;
}
.cww-run { padding: 2px 1px; border-radius: 2px; }
.author-row-head {
  font-size: 11px; text-transform: uppercase; letter-spacing: 0.05em;
  color: #80868b; font-weight: 600; border-bottom: 1px solid #e5e7eb;
}
.author-row:last-child { border-bottom: none; }
.col-name { display: flex; align-items: center; gap: 8px; font-size: 14px; color: #202124; font-weight: 500; }
.author-dot { width: 9px; height: 9px; border-radius: 50%; background: #7c3aed; flex-shrink: 0; }
.primary-tag {
  margin-left: 8px; font-size: 10px; font-weight: 700; text-transform: uppercase;
  background: #f5f1fe; color: #7c3aed; padding: 2px 6px; border-radius: 8px;
}
.col-metric { display: flex; flex-direction: column; }
.col-metric strong { font-size: 15px; color: #202124; font-variant-numeric: tabular-nums; }
.metric-sub { font-size: 11px; color: #80868b; }
.col-verdict { display: flex; }
.author-verdict {
  font-size: 12px; font-weight: 600; padding: 4px 10px; border-radius: 12px;
}
.author-verdict.green { background: #e6f4ea; color: #137333; }
.author-verdict.red { background: #fce8e6; color: #c5221f; }
.author-verdict.amber { background: #fff3e8; color: #b06000; }
.author-verdict.gray { background: #f1f3f4; color: #5f6368; }
@media (max-width: 640px) {
  .author-row { grid-template-columns: 1.5fr 1fr 1fr; }
  .col-verdict { grid-column: 1 / -1; }
}

.page-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 16px 24px;
  background: white;
  border-bottom: 1px solid #e0e0e0;
  gap: 16px;
  flex-wrap: wrap;
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

.summary-chips {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
}

.chip {
  padding: 6px 14px;
  border-radius: 16px;
  font-size: 13px;
  font-weight: 500;
  background: #f1f3f4;
  color: #5f6368;
}

.verdict-chip.verified { background: #e6f4ea; color: #137333; }
.verdict-chip.flagged { background: #fce8e6; color: #c5221f; }
.verdict-chip.review_required { background: #fef7e0; color: #b06000; }
.verdict-chip.insufficient_data { background: #f1f3f4; color: #5f6368; }

.page-content {
  max-width: 1100px;
  margin: 0 auto;
  padding: 24px;
}

/* Deliverable cards */
.deliverable-cards {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(320px, 1fr));
  gap: 20px;
  margin-bottom: 32px;
}

.deliverable-card {
  background: white;
  border-radius: 12px;
  padding: 24px;
  border-top: 4px solid #7c3aed;
}

.deliverable-card.report-card {
  grid-column: 1 / -1;
}

.card-title {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-bottom: 16px;
}

.card-title h3 {
  margin: 0;
  font-size: 16px;
  font-weight: 500;
  color: #202124;
}

.card-title .right {
  margin-left: auto;
}

.card-description {
  font-size: 14px;
  color: #5f6368;
  margin: 0 0 16px;
}

.card-busy {
  display: flex;
  align-items: center;
  gap: 12px;
  color: #5f6368;
  font-size: 14px;
  padding: 16px 0;
}

.card-busy.column {
  flex-direction: column;
  align-items: stretch;
}

.progress-track {
  height: 6px;
  background: #e8eaed;
  border-radius: 3px;
  overflow: hidden;
}

.progress-fill {
  height: 100%;
  background: linear-gradient(90deg, #7c3aed, #a78bfa);
  border-radius: 3px;
  transition: width 0.3s ease;
}

.card-empty {
  padding: 16px 0;
}

.card-empty p {
  color: #5f6368;
  font-size: 14px;
  margin: 0 0 12px;
}

/* Video */
.video-block {
  display: flex;
  flex-direction: column;
  gap: 14px;
}

.session-video {
  width: 100%;
  border-radius: 8px;
  background: #000;
  max-height: 360px;
}

.card-actions {
  display: flex;
  gap: 10px;
  flex-wrap: wrap;
}

.btn-primary {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  padding: 10px 20px;
  border: none;
  background: #7c3aed;
  color: white;
  font-weight: 500;
  font-size: 14px;
  border-radius: 8px;
  cursor: pointer;
}

.btn-primary:hover:not(:disabled) {
  background: #6d28d9;
}

.btn-primary:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.btn-outline {
  padding: 10px 20px;
  border: 1px solid #dadce0;
  background: white;
  border-radius: 8px;
  font-weight: 500;
  font-size: 14px;
  color: #7c3aed;
  cursor: pointer;
}

.btn-outline:hover:not(:disabled) {
  background: #faf8ff;
  border-color: #c4b5fd;
}

.btn-outline:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.btn-outline.small {
  padding: 6px 14px;
  font-size: 13px;
}

.btn-text {
  border: none;
  background: transparent;
  font-weight: 500;
  font-size: 13px;
  cursor: pointer;
  padding: 6px 10px;
  border-radius: 6px;
  align-self: flex-start;
}

.btn-text.danger {
  color: #c5221f;
}

.btn-text.danger:hover {
  background: #fce8e6;
}

/* Share */
.share-block {
  display: flex;
  flex-direction: column;
  gap: 8px;
  background: #f8f9fa;
  border-radius: 8px;
  padding: 12px;
}

.share-row {
  display: flex;
  gap: 8px;
}

.share-input {
  flex: 1;
  padding: 8px 12px;
  border: 1px solid #dadce0;
  border-radius: 6px;
  font-size: 13px;
  color: #202124;
  background: white;
  box-sizing: border-box;
  min-width: 0;
}

.note-text {
  font-size: 12px;
  color: #80868b;
  margin: 0;
}

.error-text {
  color: #d93025;
  font-size: 13px;
  margin: 8px 0 0;
}

/* Report */
.report-frame {
  width: 100%;
  height: 600px;
  border: 1px solid #e8eaed;
  border-radius: 8px;
  background: white;
}

/* Playback */
.playback-section h2 {
  font-size: 18px;
  font-weight: 500;
  color: #202124;
  margin: 0 0 16px;
}

/* Loading */
.loading {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 12px;
  padding: 80px;
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

.spinner.small {
  width: 20px;
  height: 20px;
  border-width: 2px;
}

.spinner.white {
  border-color: rgba(255,255,255,0.3);
  border-top-color: white;
}

@keyframes spin {
  to { transform: rotate(360deg); }
}
</style>
