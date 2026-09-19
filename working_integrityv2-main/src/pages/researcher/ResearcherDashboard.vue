<template>
  <div class="researcher-dashboard">
    <!-- First-run onboarding (shows once per researcher) -->
    <ResearcherOnboarding />

    <!-- Header -->
    <header class="dashboard-header">
      <div class="header-left">
        <h1>Research Workspace</h1>
      </div>
      <div class="header-right">
        <button class="btn-primary" @click="router.push('/researcher/topic/new')">
          <svg width="20" height="20" viewBox="0 0 24 24" fill="currentColor">
            <path d="M19 13h-6v6h-2v-6H5v-2h6V5h2v6h6v2z"/>
          </svg>
          New Topic
        </button>
        <div class="user-menu">
          <button class="user-btn" @click="showUserMenu = !showUserMenu">
            <div class="avatar">{{ userInitials }}</div>
            <span>{{ user?.name || user?.email }}</span>
          </button>
          <div v-if="showUserMenu" class="dropdown-menu">
            <router-link to="/profile" class="menu-item">Profile</router-link>
            <button class="menu-item" @click="handleLogout">Logout</button>
          </div>
        </div>
      </div>
    </header>

    <!-- Main Content -->
    <main class="dashboard-content">
      <!-- Verified-report showcase hero (dismissible) -->
      <section v-if="showGuide" class="hero">
        <button class="hero-close" @click="dismissGuide" aria-label="Dismiss">
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><path d="M18 6 6 18M6 6l12 12"/></svg>
        </button>

        <span class="hero-eyebrow">Authorship, verified</span>
        <h1 class="hero-title">Prove your research is<br><span class="hero-accent">genuinely yours.</span></h1>

        <div class="deck" :class="{ ready: heroReady }">
          <span class="deck-bubble v">@you</span>
          <span class="deck-bubble g">@co-author</span>

          <div class="rcard tint4">
            <div class="rc-icon"><svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2"/><circle cx="9" cy="7" r="4"/><path d="M22 21v-2a4 4 0 0 0-3-3.87"/><path d="M16 3.13a4 4 0 0 1 0 7.75"/></svg></div>
            <div class="rc-meta"><div class="rc-title">Per-author credit</div><div class="rc-desc">Each co-author verified separately — see who wrote what.</div></div>
          </div>
          <div class="rcard tint2">
            <div class="rc-icon"><svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"/><path d="m10 8 6 4-6 4Z"/></svg></div>
            <div class="rc-meta"><div class="rc-title">Session replay</div><div class="rc-desc">Replay every keystroke — typed, pasted or deleted.</div></div>
          </div>
          <div class="rcard tint3">
            <div class="rc-icon"><svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round"><path d="M12 10a2 2 0 0 0-2 2c0 1.02-.1 2.51-.26 4"/><path d="M14 13.12c0 2.38 0 6.38-1 8.88"/><path d="M2 12a10 10 0 0 1 18-6"/><path d="M5 19.5C5.5 18 6 15 6 12a6 6 0 0 1 .34-2"/><path d="M9 6.8a6 6 0 0 1 9 5.2v2"/></svg></div>
            <div class="rc-meta"><div class="rc-title">Stylometry</div><div class="rc-desc">Your writing style, measured word&#8209;by&#8209;word.</div></div>
          </div>
          <div class="rcard tint1">
            <div class="rc-icon"><svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M9 17H7A5 5 0 0 1 7 7h2"/><path d="M15 7h2a5 5 0 0 1 0 10h-2"/><line x1="8" y1="12" x2="16" y2="12"/></svg></div>
            <div class="rc-meta"><div class="rc-title">Shareable proof</div><div class="rc-desc">One public link — your video, PDF & verdict.</div></div>
          </div>
          <div class="rcard tint5">
            <div class="rc-icon"><svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round"><path d="M12 3l1.7 4.7L18.5 9.5l-4.8 1.8L12 16l-1.7-4.7L5.5 9.5l4.8-1.8L12 3Z"/><path d="M5 17l.9 2.1L8 20l-2.1.9L5 23l-.9-2.1L2 20l2.1-.9L5 17Z"/></svg></div>
            <div class="rc-meta"><div class="rc-title">AI-aware</div><div class="rc-desc">Flags writing that doesn’t sound like you.</div></div>
          </div>
        </div>

        <p class="hero-sub">Your writing style is like a fingerprint. Editorrah measures yours with <strong>word-level stylometry</strong> to show your work is really your own — backed by a video of you writing and a link you can share with anyone.</p>

        <div class="hero-ctas">
          <button class="hero-btn dark" @click="router.push('/researcher/topic/new')">Create a report</button>
          <button class="hero-btn ghost" @click="dismissGuide">
            Maybe later
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M5 12h14M13 6l6 6-6 6"/></svg>
          </button>
        </div>
      </section>

      <button v-else class="intro-reopen" @click="showGuide = true">
        <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M20 13c0 5-3.5 7.5-7.66 8.95a1 1 0 0 1-.67-.01C7.5 20.5 4 18 4 13V6a1 1 0 0 1 1-1c2 0 4.5-1.2 6.24-2.72a1.17 1.17 0 0 1 1.52 0C14.51 3.81 17 5 19 5a1 1 0 0 1 1 1z"/><path d="m9 12 2 2 4-4"/></svg>
        How authorship verification works
      </button>

      <div class="content-grid">
        <!-- Topics Column -->
        <section class="topics-section">
          <h2>My Topics</h2>

          <div v-if="loadingTopics" class="loading">
            <div class="spinner"></div>
            <span>Loading topics...</span>
          </div>

          <div v-else-if="topics.length === 0" class="empty-state">
            <svg width="96" height="96" viewBox="0 0 24 24" fill="#dadce0">
              <path d="M14 2H6c-1.1 0-1.99.9-1.99 2L4 20c0 1.1.89 2 1.99 2H18c1.1 0 2-.9 2-2V8l-6-6zm2 16H8v-2h8v2zm0-4H8v-2h8v2zm-3-5V3.5L18.5 9H13z"/>
            </svg>
            <h3>No Topics Yet</h3>
            <p>Create your first research topic to start a verified writing session</p>
            <button class="btn-primary" @click="router.push('/researcher/topic/new')">
              Create Your First Topic
            </button>
          </div>

          <div v-else class="topics-grid">
            <div
              v-for="topic in topics"
              :key="topic.topic_id"
              class="topic-card"
              @click="openTopic(topic)"
            >
              <div class="topic-card-header">
                <h3>{{ topic.title }}</h3>
                <span class="status-badge" :class="topic.status">{{ statusLabel(topic.status) }}</span>
              </div>
              <div class="topic-chips">
                <span v-if="topic.lab_name" class="chip lab-chip">{{ topic.lab_name }}</span>
                <span v-if="topic.is_shared" class="chip shared-chip">👥 {{ topic.author_count }} authors{{ topic.is_owner ? '' : ' · shared with you' }}</span>
                <span class="chip">{{ topic.word_count || 0 }} words</span>
                <span v-if="topic.stylometry_verdict" class="chip verdict-chip" :class="topic.stylometry_verdict">
                  {{ styloLabel(topic.stylometry_verdict, topic.stylometry_probability) }}
                </span>
              </div>
              <div class="topic-footer">
                <span class="topic-date">{{ formatDate(topic.submitted_at || topic.created_at) }}</span>
                <div class="deliverable-icons">
                  <span v-if="topic.has_video" class="deliverable-icon" title="Session video available">
                    <svg width="16" height="16" viewBox="0 0 24 24" fill="#7c3aed">
                      <path d="M17 10.5V7c0-.55-.45-1-1-1H4c-.55 0-1 .45-1 1v10c0 .55.45 1 1 1h12c.55 0 1-.45 1-1v-3.5l4 4v-11l-4 4z"/>
                    </svg>
                  </span>
                  <span v-if="topic.has_pdf" class="deliverable-icon" title="PDF available">
                    <svg width="16" height="16" viewBox="0 0 24 24" fill="#c5221f">
                      <path d="M14 2H6c-1.1 0-1.99.9-1.99 2L4 20c0 1.1.89 2 1.99 2H18c1.1 0 2-.9 2-2V8l-6-6zm-1 7V3.5L18.5 9H13z"/>
                    </svg>
                  </span>
                </div>
              </div>
            </div>
          </div>

          <!-- Hallucination Checker card -->
          <div class="tool-card" @click="router.push('/researcher/hallucination-check')">
            <div class="tool-icon">
              <svg width="28" height="28" viewBox="0 0 24 24" fill="#7c3aed">
                <path d="M15.5 14h-.79l-.28-.27C15.41 12.59 16 11.11 16 9.5 16 5.91 13.09 3 9.5 3S3 5.91 3 9.5 5.91 16 9.5 16c1.61 0 3.09-.59 4.23-1.57l.27.28v.79l5 4.99L20.49 19l-4.99-5zm-6 0C7.01 14 5 11.99 5 9.5S7.01 5 9.5 5 14 7.01 14 9.5 11.99 14 9.5 14z"/>
              </svg>
            </div>
            <div class="tool-info">
              <h3>Hallucination Checker</h3>
              <p>Verify claims &amp; references in any document</p>
            </div>
            <svg width="24" height="24" viewBox="0 0 24 24" fill="#9aa0a6">
              <path d="M8.59 16.59L13.17 12 8.59 7.41 10 6l6 6-6 6-1.41-1.41z"/>
            </svg>
          </div>
        </section>

        <!-- Labs Sidebar -->
        <aside class="labs-section">
          <h2>My Labs</h2>

          <div v-if="loadingLabs" class="loading small">
            <div class="spinner"></div>
          </div>

          <div v-else-if="labs.length === 0 && !showCreateLab && !showJoinLab" class="empty-state small">
            <svg width="64" height="64" viewBox="0 0 24 24" fill="#dadce0">
              <path d="M12 3L1 9l4 2.18v6L12 21l7-3.82v-6l2-1.09V17h2V9L12 3z"/>
            </svg>
            <h3>No Labs Yet</h3>
            <p>Create a lab for your research group or join one with a code</p>
          </div>

          <div v-else class="labs-list">
            <div
              v-for="lab in labs"
              :key="lab.lab_id"
              class="lab-card"
              @click="router.push(`/researcher/lab/${lab.lab_id}`)"
            >
              <div class="lab-card-top">
                <span class="lab-name">{{ lab.name }}</span>
                <span v-if="lab.is_pi" class="pi-badge">PI</span>
              </div>
              <div class="lab-card-bottom">
                <span class="lab-code" @click.stop="copyLabCode(lab)">
                  <code>{{ lab.lab_code }}</code>
                  <svg width="14" height="14" viewBox="0 0 24 24" fill="currentColor">
                    <path d="M16 1H4c-1.1 0-2 .9-2 2v14h2V3h12V1zm3 4H8c-1.1 0-2 .9-2 2v14c0 1.1.9 2 2 2h11c1.1 0 2-.9 2-2V7c0-1.1-.9-2-2-2zm0 16H8V7h11v14z"/>
                  </svg>
                  <span v-if="copiedLabId === lab.lab_id" class="copied-text">Copied!</span>
                </span>
                <span class="member-count">{{ lab.member_count }} member{{ lab.member_count === 1 ? '' : 's' }}</span>
              </div>
            </div>
          </div>

          <!-- Lab actions -->
          <div class="lab-actions">
            <button v-if="!showCreateLab" class="btn-outline" @click="showCreateLab = true; showJoinLab = false">
              Create Lab
            </button>
            <button v-if="!showJoinLab" class="btn-outline" @click="showJoinLab = true; showCreateLab = false">
              Join Lab
            </button>
          </div>

          <!-- Create lab inline form -->
          <div v-if="showCreateLab" class="inline-form">
            <h4>Create Lab</h4>
            <input v-model="newLabName" type="text" placeholder="Lab name" @keyup.enter="createLab" />
            <textarea v-model="newLabDescription" rows="2" placeholder="Description (optional)"></textarea>
            <p v-if="labError" class="error-text">{{ labError }}</p>
            <div class="form-actions">
              <button class="btn-text" @click="closeLabForms">Cancel</button>
              <button class="btn-primary small" :disabled="labBusy || !newLabName.trim()" @click="createLab">
                {{ labBusy ? 'Creating...' : 'Create' }}
              </button>
            </div>
          </div>

          <!-- Join lab inline form -->
          <div v-if="showJoinLab" class="inline-form">
            <h4>Join Lab</h4>
            <input v-model="joinLabCode" type="text" placeholder="Lab code" class="code-input" @keyup.enter="joinLab" />
            <p v-if="labError" class="error-text">{{ labError }}</p>
            <div class="form-actions">
              <button class="btn-text" @click="closeLabForms">Cancel</button>
              <button class="btn-primary small" :disabled="labBusy || !joinLabCode.trim()" @click="joinLab">
                {{ labBusy ? 'Joining...' : 'Join' }}
              </button>
            </div>
          </div>
        </aside>
      </div>
    </main>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import axios from 'axios'
import { useAuth } from '@/composables/auth'
import { getApiUrl } from '@/utils/api-url'
import ResearcherOnboarding from '@/components/researcher/ResearcherOnboarding.vue'

const API = getApiUrl()
const router = useRouter()
const { user, logout, initAuth } = useAuth()

const showUserMenu = ref(false)
const loadingTopics = ref(false)
const loadingLabs = ref(false)
const topics = ref([])
const labs = ref([])

// Showcase hero — shown until the user dismisses it.
const showGuide = ref(true)
const heroReady = ref(false) // triggers the deck fan-out animation
function dismissGuide() {
  showGuide.value = false
  try { localStorage.setItem('editorrah_research_guide_hidden', '1') } catch { /* ignore */ }
}

const showCreateLab = ref(false)
const showJoinLab = ref(false)
const newLabName = ref('')
const newLabDescription = ref('')
const joinLabCode = ref('')
const labError = ref('')
const labBusy = ref(false)
const copiedLabId = ref(null)

const userInitials = computed(() => {
  const source = user.value?.name || user.value?.email
  if (!source) return '?'
  return source.charAt(0).toUpperCase()
})

function statusLabel(status) {
  if (status === 'draft') return 'Draft'
  if (status === 'submitted') return 'Submitted'
  if (status === 'graded') return 'Reviewed'
  return status
}

function styloLabel(verdict, probability) {
  const names = {
    verified: 'verified',
    flagged: 'flagged',
    review_required: 'review required',
    insufficient_data: 'insufficient data'
  }
  let label = `Stylometry: ${names[verdict] || verdict || '—'}`
  if (probability != null) label += ` · ${Math.round(probability * 100)}%`
  return label
}

function formatDate(dateStr) {
  if (!dateStr) return ''
  return new Date(dateStr).toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' })
}

function openTopic(topic) {
  if (topic.status === 'draft') {
    const collab = topic.is_shared ? '&collab=1' : ''
    router.push(`/editor/${topic.submission_id}?assignment_id=${topic.topic_id}&class_id=${topic.lab_id}${collab}`)
  } else {
    router.push(`/researcher/submission/${topic.submission_id}`)
  }
}

function copyLabCode(lab) {
  navigator.clipboard.writeText(lab.lab_code)
  copiedLabId.value = lab.lab_id
  setTimeout(() => { copiedLabId.value = null }, 2000)
}

function closeLabForms() {
  showCreateLab.value = false
  showJoinLab.value = false
  labError.value = ''
}

async function fetchTopics() {
  loadingTopics.value = true
  try {
    const resp = await axios.get(`${API}/api/research/topics`)
    topics.value = resp.data.topics || []
  } catch (e) {
    console.error('Failed to fetch topics:', e)
  } finally {
    loadingTopics.value = false
  }
}

async function fetchLabs() {
  loadingLabs.value = true
  try {
    const resp = await axios.get(`${API}/api/research/labs`)
    labs.value = resp.data.labs || []
  } catch (e) {
    console.error('Failed to fetch labs:', e)
  } finally {
    loadingLabs.value = false
  }
}

async function createLab() {
  if (!newLabName.value.trim()) return
  labBusy.value = true
  labError.value = ''
  try {
    await axios.post(`${API}/api/research/labs`, {
      name: newLabName.value.trim(),
      description: newLabDescription.value.trim()
    })
    newLabName.value = ''
    newLabDescription.value = ''
    showCreateLab.value = false
    await fetchLabs()
  } catch (e) {
    labError.value = e.response?.data?.detail || 'Failed to create lab'
  } finally {
    labBusy.value = false
  }
}

async function joinLab() {
  if (!joinLabCode.value.trim()) return
  labBusy.value = true
  labError.value = ''
  try {
    await axios.post(`${API}/api/research/labs/join`, {
      lab_code: joinLabCode.value.trim().toUpperCase()
    })
    joinLabCode.value = ''
    showJoinLab.value = false
    await fetchLabs()
  } catch (e) {
    if (e.response?.status === 404) {
      labError.value = 'Invalid lab code'
    } else if (e.response?.status === 400) {
      labError.value = 'You are already a member of this lab'
    } else {
      labError.value = e.response?.data?.detail || 'Failed to join lab'
    }
  } finally {
    labBusy.value = false
  }
}

async function handleLogout() {
  await logout()
  router.push('/login')
}

onMounted(async () => {
  try { if (localStorage.getItem('editorrah_research_guide_hidden') === '1') showGuide.value = false } catch { /* ignore */ }
  // Fan the deck out on the next frames so the entrance animation plays.
  requestAnimationFrame(() => requestAnimationFrame(() => { heroReady.value = true }))
  if (!user.value) await initAuth()
  await Promise.all([fetchTopics(), fetchLabs()])
})
</script>

<style scoped>
.researcher-dashboard {
  min-height: 100vh;
  background: #f8f9fa;
}

/* ── Verified-report showcase hero ── */
.hero {
  position: relative; overflow: hidden; text-align: center;
  margin-bottom: 24px; padding: 46px 32px 40px; border-radius: 24px;
  background:
    radial-gradient(120% 120% at 50% -8%, #f1eefe 0%, rgba(241,238,254,0) 56%),
    linear-gradient(180deg, #ffffff 0%, #fcfcfe 100%);
  border: 1px solid #eceaf3;
  box-shadow: 0 1px 2px rgba(16,24,40,0.05), 0 28px 60px -36px rgba(40,32,90,0.26);
}
.hero::before {
  content: ""; position: absolute; inset: 0; pointer-events: none; z-index: 0;
  background-image:
    linear-gradient(rgba(20,16,60,0.035) 1px, transparent 1px),
    linear-gradient(90deg, rgba(20,16,60,0.035) 1px, transparent 1px);
  background-size: 30px 30px;
  -webkit-mask-image: radial-gradient(120% 90% at 50% 0%, #000 30%, transparent 75%);
          mask-image: radial-gradient(120% 90% at 50% 0%, #000 30%, transparent 75%);
}
.hero > * { position: relative; z-index: 1; }
.hero-close {
  position: absolute; top: 18px; right: 18px; z-index: 5;
  width: 30px; height: 30px; display: flex; align-items: center; justify-content: center;
  background: rgba(255,255,255,0.7); border: none; color: #9aa0ad; border-radius: 8px; cursor: pointer;
  transition: background 0.15s, color 0.15s;
}
.hero-close:hover { background: #f1f0f6; color: #5a5b6a; }
.hero-eyebrow {
  display: inline-block; font-size: 11px; font-weight: 600; letter-spacing: 0.16em;
  text-transform: uppercase; color: #6a4ff0; margin-bottom: 14px;
}
.hero-title {
  font-size: clamp(30px, 4.6vw, 50px); font-weight: 800; letter-spacing: -0.032em;
  line-height: 1.04; color: #15141d; margin: 0 auto; max-width: 700px;
}
.hero-accent { color: #6a4ff0; }
.hero-sub {
  max-width: 540px; margin: 28px auto 0; font-size: 14.5px; line-height: 1.62; color: #5c5d6e;
}
.hero-sub strong { color: #15141d; font-weight: 700; }
.hero-ctas { display: flex; gap: 12px; justify-content: center; margin-top: 24px; }
.hero-btn {
  border: none; border-radius: 999px; padding: 12px 24px; font-size: 14.5px; font-weight: 600;
  cursor: pointer; display: inline-flex; align-items: center; gap: 8px;
  transition: transform 0.15s, box-shadow 0.2s, border-color 0.2s;
}
.hero-btn.dark { background: #15141d; color: #fff; box-shadow: 0 12px 26px -14px rgba(0,0,0,0.55); }
.hero-btn.dark:hover { transform: translateY(-2px); }
.hero-btn.ghost { background: #fff; color: #2a2b33; border: 1px solid #e6e4ee; }
.hero-btn.ghost:hover { transform: translateY(-2px); border-color: #d3d0e0; }
.hero-btn.ghost svg { color: #6a4ff0; }

/* fanned deck */
.deck { position: relative; width: min(720px, 92%); height: 296px; margin: 30px auto 6px; }
.rcard {
  position: absolute; left: 50%; top: 8px; width: 188px; height: 236px; border-radius: 18px;
  padding: 15px; overflow: hidden; cursor: default;
  display: flex; flex-direction: column; justify-content: flex-end;
  border: 1px solid rgba(20,16,60,0.06);
  box-shadow: 0 18px 34px -16px rgba(30,22,80,0.42), 0 3px 10px -5px rgba(30,22,80,0.3);
  transform-origin: 50% 178%;
  transform: translateX(-50%) rotate(0deg) translateY(42px); opacity: 0;
  transition: transform 0.6s cubic-bezier(.2,.8,.2,1), box-shadow 0.35s, opacity 0.5s;
}
.tint1 { background: linear-gradient(160deg, #eef4ff, #fff); }
.tint2 { background: linear-gradient(160deg, #effdf9, #fff); }
.tint3 { background: linear-gradient(160deg, #f3f0ff, #fff); }
.tint4 { background: linear-gradient(160deg, #fff7ed, #fff); }
.tint5 { background: linear-gradient(160deg, #fff1f3, #fff); }
.rc-icon {
  position: absolute; top: 14px; left: 14px; width: 36px; height: 36px; border-radius: 11px;
  background: #fff; border: 1px solid rgba(20,16,60,0.06); color: #6a4ff0;
  display: flex; align-items: center; justify-content: center;
  box-shadow: 0 2px 8px -3px rgba(40,32,90,0.25);
}
.rc-title { font-size: 15px; font-weight: 700; color: #15141d; letter-spacing: -0.01em; }
.rc-desc { font-size: 11.5px; line-height: 1.42; color: #6f7080; margin-top: 5px; }

.deck.ready .rcard { opacity: 1; }
.deck.ready .rcard:nth-of-type(1) { transform: translateX(-50%) rotate(-24deg); transition-delay: 0.10s; }
.deck.ready .rcard:nth-of-type(2) { transform: translateX(-50%) rotate(-12deg); transition-delay: 0.16s; }
.deck.ready .rcard:nth-of-type(3) { transform: translateX(-50%) rotate(0deg); transition-delay: 0.22s; z-index: 6; }
.deck.ready .rcard:nth-of-type(4) { transform: translateX(-50%) rotate(12deg); transition-delay: 0.16s; }
.deck.ready .rcard:nth-of-type(5) { transform: translateX(-50%) rotate(24deg); transition-delay: 0.10s; }
.deck.ready .rcard:hover {
  transform: translateX(-50%) rotate(0deg) translateY(-30px) scale(1.07) !important;
  z-index: 30 !important;
  box-shadow: 0 40px 60px -22px rgba(30,22,80,0.52), 0 8px 20px -8px rgba(30,22,80,0.4);
}

.deck-bubble {
  position: absolute; z-index: 8; font-size: 12px; font-weight: 600; color: #fff;
  padding: 5px 11px; border-radius: 13px 13px 13px 4px;
  box-shadow: 0 8px 16px -6px rgba(30,22,80,0.4); animation: hbob 3.2s ease-in-out infinite;
}
.deck-bubble.v { background: #6a4ff0; left: calc(50% - 205px); top: 38px; }
.deck-bubble.g { background: #1fb16b; left: calc(50% + 150px); top: 64px; animation-delay: 1.1s; border-radius: 13px 13px 4px 13px; }
@keyframes hbob { 0%,100% { transform: translateY(0); } 50% { transform: translateY(-7px); } }

.intro-reopen {
  display: inline-flex; align-items: center; gap: 8px; margin-bottom: 22px;
  background: #fff; border: 1px solid #eceaf3; color: #44454f;
  font-size: 13.5px; font-weight: 500; padding: 10px 16px; border-radius: 10px;
  cursor: pointer; transition: background 0.15s, border-color 0.15s, box-shadow 0.15s;
  box-shadow: 0 1px 2px rgba(16,24,40,0.04);
}
.intro-reopen:hover { background: #fafafb; border-color: #e0dded; }
.intro-reopen svg { color: #6a4ff0; }

@media (max-width: 760px) {
  .hero { padding: 32px 18px 28px; }
  .deck { transform: scale(0.82); height: 250px; margin-top: 16px; }
  .deck-bubble.v { left: calc(50% - 150px); }
  .deck-bubble.g { left: calc(50% + 110px); }
}

.dashboard-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 16px 24px;
  background: white;
  border-bottom: 1px solid #e0e0e0;
  position: sticky;
  top: 0;
  z-index: 100;
}

.header-left h1 {
  font-size: 24px;
  font-weight: 500;
  margin: 0;
  color: #202124;
}

.header-right {
  display: flex;
  align-items: center;
  gap: 16px;
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

.btn-primary.small {
  padding: 8px 16px;
}

.user-menu {
  position: relative;
}

.user-btn {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 12px;
  border: none;
  background: transparent;
  cursor: pointer;
  border-radius: 24px;
  color: #5f6368;
}

.user-btn:hover {
  background: #f1f3f4;
}

.avatar {
  width: 32px;
  height: 32px;
  border-radius: 50%;
  background: #7c3aed;
  color: white;
  display: flex;
  align-items: center;
  justify-content: center;
  font-weight: 500;
}

.dropdown-menu {
  position: absolute;
  top: 100%;
  right: 0;
  margin-top: 8px;
  background: white;
  border-radius: 8px;
  box-shadow: 0 4px 12px rgba(0,0,0,0.15);
  min-width: 160px;
  overflow: hidden;
  z-index: 10;
}

.menu-item {
  display: block;
  width: 100%;
  padding: 12px 16px;
  border: none;
  background: transparent;
  text-align: left;
  cursor: pointer;
  color: #202124;
  text-decoration: none;
  font-size: 14px;
}

.menu-item:hover {
  background: #f8f9fa;
}

/* Layout */
.dashboard-content {
  max-width: 1200px;
  margin: 0 auto;
  padding: 24px;
}

.content-grid {
  display: grid;
  grid-template-columns: 1fr 320px;
  gap: 24px;
  align-items: start;
}

section h2, aside h2 {
  font-size: 18px;
  font-weight: 500;
  color: #202124;
  margin: 0 0 16px;
}

/* Topics */
.topics-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
  gap: 16px;
  margin-bottom: 24px;
}

.topic-card {
  background: white;
  border-radius: 12px;
  padding: 20px;
  cursor: pointer;
  transition: box-shadow 0.2s;
  border-top: 4px solid #7c3aed;
}

.topic-card:hover {
  box-shadow: 0 4px 12px rgba(0,0,0,0.12);
}

.topic-card-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 12px;
  margin-bottom: 12px;
}

.topic-card-header h3 {
  margin: 0;
  font-size: 16px;
  font-weight: 500;
  color: #202124;
  line-height: 1.4;
}

.status-badge {
  flex-shrink: 0;
  padding: 4px 12px;
  border-radius: 12px;
  font-size: 12px;
  font-weight: 500;
}

.status-badge.draft {
  background: #fef7e0;
  color: #b06000;
}

.status-badge.submitted {
  background: #e6f4ea;
  color: #137333;
}

.status-badge.graded {
  background: #f5f1fe;
  color: #7c3aed;
}

.topic-chips {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  margin-bottom: 14px;
}

.chip {
  padding: 4px 10px;
  border-radius: 12px;
  font-size: 12px;
  font-weight: 500;
  background: #f1f3f4;
  color: #5f6368;
}

.lab-chip {
  background: #f5f1fe;
  color: #7c3aed;
}

.shared-chip {
  background: #e8f0fe;
  color: #1a73e8;
}

.verdict-chip.verified { background: #e6f4ea; color: #137333; }
.verdict-chip.flagged { background: #fce8e6; color: #c5221f; }
.verdict-chip.review_required { background: #fef7e0; color: #b06000; }
.verdict-chip.insufficient_data { background: #f1f3f4; color: #5f6368; }

.topic-footer {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.topic-date {
  font-size: 12px;
  color: #80868b;
}

.deliverable-icons {
  display: flex;
  gap: 8px;
}

.deliverable-icon {
  display: flex;
  align-items: center;
}

/* Tool card */
.tool-card {
  display: flex;
  align-items: center;
  gap: 16px;
  background: white;
  border-radius: 12px;
  padding: 20px;
  cursor: pointer;
  transition: box-shadow 0.2s;
  border: 1px solid #ede9fe;
}

.tool-card:hover {
  box-shadow: 0 4px 12px rgba(124, 58, 237, 0.15);
}

.tool-icon {
  width: 52px;
  height: 52px;
  border-radius: 12px;
  background: #f5f1fe;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}

.tool-info {
  flex: 1;
}

.tool-info h3 {
  margin: 0 0 4px;
  font-size: 16px;
  font-weight: 500;
  color: #202124;
}

.tool-info p {
  margin: 0;
  font-size: 13px;
  color: #5f6368;
}

/* Labs sidebar */
.labs-section {
  background: white;
  border-radius: 12px;
  padding: 20px;
}

.labs-list {
  display: flex;
  flex-direction: column;
  gap: 10px;
  margin-bottom: 16px;
}

.lab-card {
  border: 1px solid #e8eaed;
  border-radius: 10px;
  padding: 14px;
  cursor: pointer;
  transition: border-color 0.2s, box-shadow 0.2s;
}

.lab-card:hover {
  border-color: #c4b5fd;
  box-shadow: 0 2px 8px rgba(124, 58, 237, 0.1);
}

.lab-card-top {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 8px;
}

.lab-name {
  font-weight: 500;
  color: #202124;
  font-size: 14px;
}

.pi-badge {
  background: #7c3aed;
  color: white;
  font-size: 11px;
  font-weight: 600;
  padding: 2px 8px;
  border-radius: 10px;
}

.lab-card-bottom {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.lab-code {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  font-size: 12px;
  color: #7c3aed;
  cursor: pointer;
}

.lab-code code {
  background: #f5f1fe;
  padding: 2px 8px;
  border-radius: 4px;
  font-weight: 600;
}

.lab-code:hover {
  color: #5b21b6;
}

.copied-text {
  font-size: 11px;
  color: #137333;
  font-weight: 500;
}

.member-count {
  font-size: 12px;
  color: #5f6368;
}

.lab-actions {
  display: flex;
  gap: 8px;
}

.btn-outline {
  flex: 1;
  padding: 10px 12px;
  border: 1px solid #dadce0;
  background: white;
  border-radius: 8px;
  font-weight: 500;
  font-size: 13px;
  color: #7c3aed;
  cursor: pointer;
}

.btn-outline:hover {
  background: #faf8ff;
  border-color: #c4b5fd;
}

/* Inline forms */
.inline-form {
  margin-top: 16px;
  border-top: 1px solid #f1f3f4;
  padding-top: 16px;
}

.inline-form h4 {
  margin: 0 0 12px;
  font-size: 14px;
  font-weight: 500;
  color: #202124;
}

.inline-form input,
.inline-form textarea {
  width: 100%;
  padding: 10px 12px;
  border: 1px solid #dadce0;
  border-radius: 8px;
  font-size: 14px;
  box-sizing: border-box;
  margin-bottom: 10px;
  font-family: inherit;
  color: #202124;
  background: #fff;
}

.inline-form input:focus,
.inline-form textarea:focus {
  outline: none;
  border-color: #7c3aed;
}

.inline-form .code-input {
  text-transform: uppercase;
  letter-spacing: 2px;
  text-align: center;
  font-weight: 600;
}

.form-actions {
  display: flex;
  justify-content: flex-end;
  gap: 8px;
}

.btn-text {
  padding: 8px 14px;
  border: none;
  background: transparent;
  color: #5f6368;
  font-weight: 500;
  cursor: pointer;
  border-radius: 8px;
  font-size: 13px;
}

.btn-text:hover {
  background: #f1f3f4;
}

.error-text {
  color: #d93025;
  font-size: 13px;
  margin: 0 0 10px;
}

/* Empty states */
.empty-state {
  text-align: center;
  padding: 48px 20px;
  background: white;
  border-radius: 12px;
  margin-bottom: 24px;
}

.empty-state.small {
  padding: 24px 12px;
  margin-bottom: 16px;
  background: transparent;
}

.empty-state h3 {
  margin: 16px 0 8px;
  color: #202124;
  font-size: 16px;
}

.empty-state p {
  color: #5f6368;
  margin: 0 0 20px;
  font-size: 14px;
}

.empty-state.small p {
  margin-bottom: 0;
  font-size: 13px;
}

/* Loading */
.loading {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 12px;
  padding: 48px;
  color: #5f6368;
}

.loading.small {
  padding: 24px;
}

.spinner {
  width: 36px;
  height: 36px;
  border: 3px solid #e0e0e0;
  border-top-color: #7c3aed;
  border-radius: 50%;
  animation: spin 1s linear infinite;
}

@keyframes spin {
  to { transform: rotate(360deg); }
}

@media (max-width: 900px) {
  .content-grid {
    grid-template-columns: 1fr;
  }
}
</style>
