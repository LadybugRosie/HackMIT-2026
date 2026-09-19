<template>
  <div class="shared-page">
    <!-- Loading -->
    <div v-if="loading" class="center-state">
      <div class="spinner"></div>
      <span>Loading verified session...</span>
    </div>

    <!-- Expired / invalid -->
    <div v-else-if="expired" class="center-state expired">
      <svg width="72" height="72" viewBox="0 0 24 24" fill="#dadce0">
        <path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm5 13.59L15.59 17 12 13.41 8.41 17 7 15.59 10.59 12 7 8.41 8.41 7 12 10.59 15.59 7 17 8.41 13.41 12 17 15.59z"/>
      </svg>
      <h2>Link expired or revoked</h2>
      <p>This shared session is no longer available. Ask the author for a new link.</p>
    </div>

    <!-- Content -->
    <template v-else>
      <!-- Branded header -->
      <header class="brand-header">
        <div class="brand-row">
          <div class="brand-mark">
            <svg width="28" height="28" viewBox="0 0 24 24" fill="white">
              <path d="M12 1L3 5v6c0 5.55 3.84 10.74 9 12 5.16-1.26 9-6.45 9-12V5l-9-4z"/>
            </svg>
          </div>
          <span class="brand-name">Editorrah Authorship-Verified Writing Session</span>
        </div>
        <h1>{{ meta?.title }}</h1>
        <div class="meta-row">
          <span v-if="meta?.author_name" class="author">by {{ meta.author_name }}</span>
          <span v-if="meta?.submitted_at" class="date">{{ formatDate(meta.submitted_at) }}</span>
        </div>
        <div class="summary-chips">
          <span v-if="meta?.author_count" class="chip">{{ meta.author_count }} author{{ meta.author_count > 1 ? 's' : '' }}</span>
          <span v-if="meta?.word_count" class="chip">{{ meta.word_count }} words</span>
        </div>
      </header>

      <main class="shared-content">
        <!-- Authors & per-author stylometry -->
        <section v-if="authors.length" class="content-card">
          <h2>{{ isMulti ? 'Authors &amp; Contributions' : 'Author &amp; Stylometry' }}</h2>

          <!-- Contribution meter -->
          <div v-if="isMulti && hasContributions" class="contrib-meter">
            <div class="contrib-block">
              <div class="contrib-track-label"><span>Final document</span><span class="contrib-hint">share of words</span></div>
              <div class="contrib-track">
                <div v-for="a in contributionOrder" :key="'f-' + a.user_id" class="contrib-seg"
                  :style="{ width: (a.contribution?.final_pct || 0) + '%', background: authorColor(a.user_id) }">
                  <span v-if="(a.contribution?.final_pct || 0) >= 10" class="contrib-seg-label">{{ Math.round(a.contribution?.final_pct || 0) }}%</span>
                </div>
              </div>
            </div>
            <div class="contrib-legend">
              <span v-for="a in contributionOrder" :key="'l-' + a.user_id" class="contrib-legend-item">
                <span class="contrib-swatch" :style="{ background: authorColor(a.user_id) }"></span>{{ a.name }}
              </span>
            </div>
          </div>

          <div class="author-table" :class="{ 'single-author': !isMulti }">
            <div class="author-row author-row-head">
              <span class="col-name">Author</span>
              <span class="col-metric">{{ isMulti ? 'Final doc' : 'Words' }}</span>
              <span class="col-verdict">Stylometry verdict</span>
            </div>
            <div v-for="a in authors" :key="a.user_id" class="author-row">
              <span class="col-name">
                <span class="author-dot" :style="{ background: authorColor(a.user_id) }"></span>{{ a.name }}
              </span>
              <span class="col-metric">
                <strong>{{ isMulti ? (a.contribution?.final_pct ?? 0) + '%' : (a.contribution?.final_words ?? meta?.word_count ?? '—') }}</strong>
                <span class="metric-sub">{{ isMulti ? (a.contribution?.final_words ?? 0) + ' words' : 'in final document' }}</span>
              </span>
              <span class="col-verdict">
                <span v-if="!a.stylometry_v3" class="author-verdict gray">pending</span>
                <span v-else class="author-verdict" :class="verdictTone(a.stylometry_v3.verdict)">{{ verdictLabel(a.stylometry_v3) }}</span>
              </span>
            </div>
          </div>
        </section>

        <!-- Who wrote what -->
        <section v-if="isMulti && segments.length" class="content-card">
          <h2>Who Wrote What</h2>
          <div class="cww-legend">
            <span v-for="a in authors" :key="a.user_id" class="cww-leg">
              <span class="cww-dot" :style="{ background: authorColor(a.user_id) }"></span>{{ a.name }}
            </span>
          </div>
          <div class="cww-doc">
            <span v-for="(seg, i) in segments" :key="i" class="cww-run"
              :style="{ background: authorBg(seg.user_id), boxShadow: 'inset 3px 0 0 ' + authorColor(seg.user_id) }"
              :title="authorNameById(seg.user_id)">{{ seg.text }}</span>
          </div>
        </section>

        <!-- Video -->
        <section v-if="videoAvailable" class="content-card">
          <h2>Session Replay</h2>
          <div v-if="videoLoading" class="card-busy">
            <div class="spinner small"></div>
            <span>Loading video...</span>
          </div>
          <video v-else-if="videoUrl" :src="videoUrl" controls autoplay muted class="session-video"></video>
          <p v-else class="muted-text">Video could not be loaded.</p>
        </section>

        <!-- Interactive replay -->
        <section v-if="snapshots.length > 0 || playbackEvents.length > 0" class="content-card">
          <h2>Interactive Replay</h2>
          <PlaybackViewer :snapshots="snapshots" :events="playbackEvents" :authors="playbackAuthors" :meta="playbackMeta" />
        </section>

        <!-- Original PDF -->
        <section v-if="pdfAvailable" class="content-card">
          <h2>Original Document (PDF)</h2>
          <p class="muted-text">A server-generated snapshot of the submitted document.</p>
          <button class="pdf-btn" :disabled="pdfBusy" @click="downloadPdf">
            {{ pdfBusy ? 'Preparing…' : 'Download PDF' }}
          </button>
        </section>

        <!-- Report -->
        <section v-if="reportHtml" class="content-card">
          <button class="collapse-toggle" @click="reportOpen = !reportOpen">
            <h2>Stylometry Report</h2>
            <svg width="24" height="24" viewBox="0 0 24 24" fill="#5f6368" :class="{ rotated: reportOpen }">
              <path d="M7.41 8.59L12 13.17l4.59-4.58L18 10l-6 6-6-6 1.41-1.41z"/>
            </svg>
          </button>
          <iframe
            v-if="reportOpen"
            :srcdoc="reportHtml"
            sandbox=""
            class="report-frame"
            title="Stylometry report"
          ></iframe>
        </section>

        <footer class="shared-footer">
          <p>This session was recorded and its authorship verified by Editorrah's stylometry engine.</p>
        </footer>
      </main>
    </template>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onBeforeUnmount } from 'vue'
import { useRoute } from 'vue-router'
import axios from 'axios'
import { getApiUrl } from '@/utils/api-url'
import PlaybackViewer from '@/components/playback/PlaybackViewer.vue'

const props = defineProps(['token'])
const route = useRoute()

const API = getApiUrl()
const shareToken = computed(() => props.token || route.params.token)

const loading = ref(true)
const expired = ref(false)
const meta = ref(null)
const videoAvailable = ref(false)
const videoLoading = ref(false)
const videoUrl = ref(null)
const snapshots = ref([])
const playbackEvents = ref([])
const playbackAuthors = ref({})
const totalDurationMs = ref(0)
const reportHtml = ref('')
const reportOpen = ref(false)
const authors = ref([])
const segments = ref([])
const pdfAvailable = ref(false)
const pdfBusy = ref(false)

const isMulti = computed(() => authors.value.length > 1)
const hasContributions = computed(() => authors.value.some(a => a.contribution?.final_pct != null))
const contributionOrder = computed(() =>
  [...authors.value].sort((x, y) => (y.contribution?.final_pct || 0) - (x.contribution?.final_pct || 0))
)

function authorHue(id) {
  const s = String(id || 'anon'); let h = 0
  for (let i = 0; i < s.length; i++) h = ((h << 5) - h + s.charCodeAt(i)) | 0
  return Math.abs(h) % 360
}
function authorColor(id) { return `hsl(${authorHue(id)}, 65%, 45%)` }
function authorBg(id) { return `hsl(${authorHue(id)}, 70%, 93%)` }
function authorNameById(uid) { return authors.value.find(a => a.user_id === uid)?.name || 'Author' }
function verdictTone(v) {
  if (v === 'verified') return 'green'
  if (v === 'flagged') return 'red'
  if (v === 'review_required' || v === 'inconclusive') return 'amber'
  return 'gray'
}
function verdictLabel(s) {
  const v = s?.verdict, cos = s?.cosine_score
  const pct = (cos != null) ? ` · ${Math.round((cos <= 1 ? cos : cos / 100) * 100)}%` : ''
  if (v === 'verified') return `Verified${pct}`
  if (v === 'flagged') return `Flagged${pct}`
  if (v === 'review_required') return 'Needs review'
  return v || 'Pending'
}

async function downloadPdf() {
  pdfBusy.value = true
  try {
    const resp = await axios.get(`${API}/api/share/${shareToken.value}/pdf`, { responseType: 'blob' })
    const url = URL.createObjectURL(resp.data)
    const a = document.createElement('a')
    a.href = url; a.download = `editorrah-${shareToken.value.slice(0, 6)}.pdf`
    document.body.appendChild(a); a.click(); a.remove()
    URL.revokeObjectURL(url)
  } catch (e) {
    console.error('PDF download failed:', e)
  } finally {
    pdfBusy.value = false
  }
}

const playbackMeta = computed(() => ({
  studentName: meta.value?.author_name || '',
  title: meta.value?.title || '',
  totalDurationMs: totalDurationMs.value
}))

function formatDate(dateStr) {
  if (!dateStr) return ''
  return new Date(dateStr).toLocaleDateString('en-US', { month: 'long', day: 'numeric', year: 'numeric' })
}

async function loadVideo() {
  videoLoading.value = true
  try {
    const resp = await axios.get(`${API}/api/share/${shareToken.value}/video`, {
      responseType: 'blob'
    })
    videoUrl.value = URL.createObjectURL(resp.data)
  } catch (e) {
    console.error('Failed to load shared video:', e)
  } finally {
    videoLoading.value = false
  }
}

onMounted(async () => {
  try {
    const resp = await axios.get(`${API}/api/share/${shareToken.value}`)
    const data = resp.data
    meta.value = data.meta || null
    authors.value = data.authors || []
    segments.value = data.segments || []
    pdfAvailable.value = !!data.pdf_available
    videoAvailable.value = !!data.video_available
    snapshots.value = data.snapshots || []
    playbackEvents.value = data.playback_events || []
    playbackAuthors.value = data.playback_authors || {}
    totalDurationMs.value = data.total_duration_ms || 0
    reportHtml.value = data.report_html || ''
    loading.value = false

    if (videoAvailable.value) {
      loadVideo()
    }
  } catch (e) {
    loading.value = false
    if (e.response?.status === 404 || e.response?.status === 410) {
      expired.value = true
    } else {
      expired.value = true
      console.error('Failed to load shared session:', e)
    }
  }
})

onBeforeUnmount(() => {
  if (videoUrl.value) URL.revokeObjectURL(videoUrl.value)
})
</script>

<style scoped>
.shared-page {
  min-height: 100vh;
  background: #f8f9fa;
}

/* Center states */
.center-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 16px;
  min-height: 70vh;
  color: #5f6368;
  text-align: center;
  padding: 24px;
}

.center-state h2 {
  margin: 8px 0 0;
  color: #202124;
  font-weight: 500;
}

.center-state p {
  margin: 0;
  max-width: 360px;
}

/* Branded header */
.brand-header {
  background: linear-gradient(135deg, #7c3aed 0%, #5b21b6 100%);
  color: white;
  padding: 40px 24px 32px;
  text-align: center;
}

.brand-row {
  display: inline-flex;
  align-items: center;
  gap: 10px;
  margin-bottom: 20px;
  background: rgba(255,255,255,0.12);
  border-radius: 24px;
  padding: 8px 20px;
}

.brand-mark {
  display: flex;
  align-items: center;
}

.brand-name {
  font-size: 14px;
  font-weight: 600;
  letter-spacing: 0.02em;
}

.brand-header h1 {
  font-size: 28px;
  font-weight: 500;
  margin: 0 0 10px;
}

.meta-row {
  display: flex;
  justify-content: center;
  gap: 16px;
  font-size: 14px;
  opacity: 0.9;
  margin-bottom: 18px;
  flex-wrap: wrap;
}

.summary-chips {
  display: flex;
  justify-content: center;
  gap: 8px;
  flex-wrap: wrap;
}

.chip {
  padding: 6px 14px;
  border-radius: 16px;
  font-size: 13px;
  font-weight: 600;
  background: rgba(255,255,255,0.15);
  color: white;
}

.verdict-chip.verified { background: rgba(52, 211, 153, 0.25); }
.verdict-chip.flagged { background: rgba(251, 113, 133, 0.3); }
.verdict-chip.review_required { background: rgba(251, 191, 36, 0.25); }

/* Content */
.shared-content {
  max-width: 900px;
  margin: 0 auto;
  padding: 24px;
  display: flex;
  flex-direction: column;
  gap: 20px;
}

.content-card {
  background: white;
  border-radius: 12px;
  padding: 24px;
}

.content-card h2 {
  font-size: 17px;
  font-weight: 500;
  color: #202124;
  margin: 0 0 16px;
}

.session-video {
  width: 100%;
  border-radius: 8px;
  background: #000;
}

.card-busy {
  display: flex;
  align-items: center;
  gap: 12px;
  color: #5f6368;
  font-size: 14px;
  padding: 12px 0;
}

.muted-text {
  color: #5f6368;
  font-size: 14px;
  margin: 0;
}

/* Collapsible report */
.collapse-toggle {
  display: flex;
  align-items: center;
  justify-content: space-between;
  width: 100%;
  border: none;
  background: transparent;
  cursor: pointer;
  padding: 0;
}

.collapse-toggle h2 {
  margin: 0;
}

.collapse-toggle svg {
  transition: transform 0.2s ease;
}

.collapse-toggle svg.rotated {
  transform: rotate(180deg);
}

.report-frame {
  width: 100%;
  height: 600px;
  border: 1px solid #e8eaed;
  border-radius: 8px;
  background: white;
  margin-top: 16px;
}

.shared-footer {
  text-align: center;
  padding: 12px 0 32px;
}

.shared-footer p {
  color: #80868b;
  font-size: 13px;
  margin: 0;
}

/* Spinner */
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

@keyframes spin {
  to { transform: rotate(360deg); }
}

/* Per-author table */
.author-table { display: flex; flex-direction: column; }
.author-row { display: grid; grid-template-columns: 2fr 1fr 1.4fr; gap: 12px; align-items: center; padding: 12px 4px; border-bottom: 1px solid #f1f3f4; }
.author-table.single-author .author-row { grid-template-columns: 2fr 1fr 1.4fr; }
.author-row:last-child { border-bottom: none; }
.author-row-head { font-size: 11px; text-transform: uppercase; letter-spacing: 0.05em; color: #80868b; font-weight: 600; border-bottom: 1px solid #e5e7eb; }
.col-name { display: flex; align-items: center; gap: 9px; font-size: 14.5px; color: #202124; font-weight: 500; }
.author-dot { width: 10px; height: 10px; border-radius: 50%; flex-shrink: 0; }
.col-metric { display: flex; flex-direction: column; }
.col-metric strong { font-size: 15px; color: #202124; }
.metric-sub { font-size: 11px; color: #80868b; }
.col-verdict { display: flex; }
.author-verdict { font-size: 12px; font-weight: 600; padding: 4px 10px; border-radius: 12px; }
.author-verdict.green { background: #e6f4ea; color: #137333; }
.author-verdict.red { background: #fce8e6; color: #c5221f; }
.author-verdict.amber { background: #fff3e8; color: #b06000; }
.author-verdict.gray { background: #f1f3f4; color: #5f6368; }

/* Contribution meter */
.contrib-meter { margin: 4px 0 20px; display: flex; flex-direction: column; gap: 12px; }
.contrib-block { display: flex; flex-direction: column; gap: 6px; }
.contrib-track-label { display: flex; justify-content: space-between; align-items: baseline; font-size: 12px; color: #5f6368; font-weight: 600; }
.contrib-hint { font-weight: 400; color: #9aa0a6; font-size: 11px; }
.contrib-track { display: flex; height: 22px; border-radius: 7px; overflow: hidden; background: #f1f3f4; }
.contrib-seg { display: flex; align-items: center; justify-content: center; min-width: 2px; transition: width 0.4s ease; }
.contrib-seg-label { font-size: 11px; font-weight: 700; color: #fff; text-shadow: 0 1px 1px rgba(0,0,0,0.25); }
.contrib-legend { display: flex; flex-wrap: wrap; gap: 14px; }
.contrib-legend-item { display: flex; align-items: center; gap: 6px; font-size: 12.5px; color: #3c4043; }
.contrib-swatch { width: 12px; height: 12px; border-radius: 3px; flex-shrink: 0; }

/* Who wrote what */
.cww-legend { display: flex; flex-wrap: wrap; gap: 16px; margin: 0 0 14px; }
.cww-leg { display: flex; align-items: center; gap: 7px; font-size: 13.5px; font-weight: 600; color: #202124; }
.cww-dot { width: 11px; height: 11px; border-radius: 50%; flex-shrink: 0; }
.cww-doc { font-family: 'Georgia', 'Times New Roman', serif; font-size: 15.5px; line-height: 2.1; color: #1a1a1a; }
.cww-run { padding: 2px 1px; border-radius: 2px; }

/* PDF button */
.pdf-btn { margin-top: 12px; background: #7c3aed; color: #fff; border: none; cursor: pointer; font-size: 14px; font-weight: 600; padding: 11px 22px; border-radius: 10px; }
.pdf-btn:disabled { opacity: 0.6; cursor: default; }
</style>
