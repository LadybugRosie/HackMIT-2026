<template>
  <div class="new-topic-page">
    <header class="page-header">
      <button @click="router.push('/researcher')" class="back-btn">
        <svg width="24" height="24" viewBox="0 0 24 24" fill="currentColor">
          <path d="M20 11H7.83l5.59-5.59L12 4l-8 8 8 8 1.41-1.41L7.83 13H20v-2z"/>
        </svg>
      </button>
      <h1>New Research Topic</h1>
    </header>

    <main class="page-content">
      <div class="topic-form-card">
        <div class="form-intro">
          <svg width="32" height="32" viewBox="0 0 24 24" fill="#7c3aed">
            <path d="M14 2H6c-1.1 0-1.99.9-1.99 2L4 20c0 1.1.89 2 1.99 2H18c1.1 0 2-.9 2-2V8l-6-6zm2 16H8v-2h8v2zm0-4H8v-2h8v2zm-3-5V3.5L18.5 9H13z"/>
          </svg>
          <p>Start a verified writing session. Your typing, edits and sources are tracked so you can prove your work is your own.</p>
        </div>

        <div class="form-group">
          <label for="topic-title">Topic title</label>
          <input
            id="topic-title"
            v-model="title"
            type="text"
            placeholder="e.g., CRISPR off-target effects in primary T cells"
            @keyup.enter="createTopic"
            autofocus
          />
        </div>

        <div class="form-group">
          <label for="topic-description">Description <span class="optional">(optional)</span></label>
          <textarea
            id="topic-description"
            v-model="description"
            rows="3"
            placeholder="Short summary of what this piece will cover"
          ></textarea>
        </div>

        <div v-if="labs.length > 1" class="form-group">
          <label for="topic-lab">Lab</label>
          <select id="topic-lab" v-model="selectedLabId">
            <option v-for="lab in labs" :key="lab.lab_id" :value="lab.lab_id">
              {{ lab.name }}
            </option>
          </select>
        </div>

        <label class="collab-toggle">
          <input type="checkbox" v-model="collaborative" />
          <span class="collab-toggle-text">
            <strong>Collaborative report</strong>
            <span>Co-write with lab members in real time. Each author is judged separately by their own stylometry profile.</span>
          </span>
        </label>

        <p v-if="error" class="error-text">{{ error }}</p>

        <button class="btn-create" :disabled="creating || !title.trim()" @click="createTopic">
          <span v-if="creating" class="spinner"></span>
          {{ creating ? 'Creating...' : (collaborative ? 'Create & Invite Co-Authors' : 'Create & Start Writing') }}
        </button>
      </div>

      <!-- Invite step (collaborative topics, creator already enrolled) -->
      <div v-if="created" class="topic-form-card invite-card">
        <h2 class="invite-title">Invite co-authors</h2>
        <p class="invite-sub">Only lab members who have completed stylometry enrollment can co-author — everyone gets a separate verdict.</p>
        <div v-if="members.length === 0" class="invite-empty">No other lab members yet. You can invite people later.</div>
        <div v-else class="member-list">
          <label
            v-for="m in members"
            :key="m.user_id"
            class="member-row"
            :class="{ disabled: !m.stylometry_enrolled }"
          >
            <input type="checkbox" :value="m.user_id" v-model="selectedInvites" :disabled="!m.stylometry_enrolled" />
            <span class="member-name">{{ m.name }}</span>
            <span class="member-badge" :class="m.stylometry_enrolled ? 'ok' : 'no'">
              {{ m.stylometry_enrolled ? 'enrolled' : 'not enrolled' }}
            </span>
          </label>
        </div>
        <p v-if="inviteError" class="error-text">{{ inviteError }}</p>

        <!-- Shareable invite link — anyone can join after sign-up + enrollment -->
        <div class="invite-link-block">
          <div class="invite-link-head">
            <span class="invite-link-title">Or share an invite link</span>
            <span class="invite-link-note">Anyone can join after signing up &amp; completing stylometry enrollment</span>
          </div>
          <div v-if="!inviteLink" class="invite-link-gen">
            <button class="btn-link-gen" :disabled="linkBusy" @click="generateInviteLink">
              {{ linkBusy ? 'Generating…' : 'Create invite link' }}
            </button>
          </div>
          <div v-else class="invite-link-row">
            <input class="invite-link-input" :value="inviteLink" readonly @focus="$event.target.select()" />
            <button class="btn-link-copy" @click="copyInviteLink">{{ linkCopied ? 'Copied!' : 'Copy' }}</button>
          </div>
        </div>

        <div class="invite-actions">
          <button class="btn-secondary" @click="startWriting">Skip</button>
          <button class="btn-create" :disabled="inviting" @click="inviteAndStart">
            <span v-if="inviting" class="spinner"></span>
            {{ inviting ? 'Inviting…' : (selectedInvites.length ? `Invite ${selectedInvites.length} & Start` : 'Start Writing') }}
          </button>
        </div>
      </div>
    </main>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import axios from 'axios'
import { getApiUrl } from '@/utils/api-url'
import { useAuth } from '@/composables/auth'

const API = getApiUrl()
const router = useRouter()
const { user: authUser, initAuth } = useAuth()

const title = ref('')
const description = ref('')
const labs = ref([])
const selectedLabId = ref(null)
const creating = ref(false)
const error = ref('')
const collaborative = ref(false)

// Invite step state (collaborative reports)
const created = ref(null)          // {submission_id, topic_id, lab_id}
const members = ref([])
const selectedInvites = ref([])
const inviting = ref(false)
const inviteError = ref('')

// Shareable invite-link state
const inviteLink = ref('')
const linkBusy = ref(false)
const linkCopied = ref(false)

async function generateInviteLink() {
  if (!created.value?.submission_id) return
  linkBusy.value = true
  try {
    const resp = await axios.post(
      `${API}/api/research/submissions/${created.value.submission_id}/invite-link`
    )
    // Build from the current origin so the link works in every environment.
    inviteLink.value = `${window.location.origin}/join/${resp.data.token}`
  } catch (e) {
    inviteError.value = e.response?.data?.detail || 'Failed to create invite link'
  } finally {
    linkBusy.value = false
  }
}

async function copyInviteLink() {
  try {
    await navigator.clipboard.writeText(inviteLink.value)
    linkCopied.value = true
    setTimeout(() => { linkCopied.value = false }, 1800)
  } catch { /* clipboard unavailable — the field is selectable */ }
}

function editorPath(r, collab) {
  const suffix = collab ? '&collab=1' : ''
  return `/editor/${r.submission_id}?assignment_id=${r.topic_id}&class_id=${r.lab_id}${suffix}`
}

async function fetchLabs() {
  try {
    const resp = await axios.get(`${API}/api/research/labs`)
    labs.value = resp.data.labs || []
    if (labs.value.length > 0) {
      selectedLabId.value = labs.value[0].lab_id
    }
  } catch (e) {
    console.error('Failed to fetch labs:', e)
  }
}

async function createTopic() {
  if (!title.value.trim() || creating.value) return
  creating.value = true
  error.value = ''

  try {
    const body = { title: title.value.trim(), collaborative: collaborative.value }
    if (description.value.trim()) body.description = description.value.trim()
    if (selectedLabId.value) body.lab_id = selectedLabId.value

    const resp = await axios.post(`${API}/api/research/topics`, body)
    const r = resp.data
    const path = editorPath(r, collaborative.value)

    // Not enrolled → must enroll first; invites can be sent later from the editor/dashboard.
    if (!r.stylometry_enrolled) {
      const topicParam = encodeURIComponent(r.title || title.value.trim())
      router.push(`/researcher/stylometry-enrollment/${r.lab_id}?topic=${topicParam}&next=${encodeURIComponent(path)}`)
      return
    }

    // Collaborative + enrolled → show the invite step before opening the editor.
    if (collaborative.value) {
      created.value = r
      await fetchMembers(r.lab_id)
      creating.value = false
      return
    }

    router.push(path)
  } catch (e) {
    error.value = e.response?.data?.detail || 'Failed to create topic'
    creating.value = false
  }
}

async function fetchMembers(labId) {
  try {
    const resp = await axios.get(`${API}/api/research/labs/${labId}/members`)
    const me = (resp.data.members || []).map(m => ({
      user_id: m.user_id, name: m.name, stylometry_enrolled: m.stylometry_enrolled,
    }))
    // exclude the creator (already an author)
    const myId = authUser.value?.user_id
    members.value = me.filter(m => m.user_id !== myId)
  } catch (e) {
    members.value = []
  }
}

async function inviteAndStart() {
  if (!created.value) return
  inviting.value = true
  inviteError.value = ''
  try {
    for (const uid of selectedInvites.value) {
      await axios.post(`${API}/api/research/submissions/${created.value.submission_id}/invite-author`, { user_id: uid })
    }
    startWriting()
  } catch (e) {
    inviteError.value = e.response?.data?.detail || 'Failed to invite one or more members'
    inviting.value = false
  }
}

function startWriting() {
  router.push(editorPath(created.value, true))
}

onMounted(() => {
  if (!authUser.value) initAuth().catch(() => {})
  fetchLabs()
})
</script>

<style scoped>
.new-topic-page {
  min-height: 100vh;
  background: #f8f9fa;
}

.page-header {
  display: flex;
  align-items: center;
  gap: 16px;
  padding: 16px 24px;
  background: white;
  border-bottom: 1px solid #e0e0e0;
}

.page-header h1 {
  font-size: 20px;
  font-weight: 500;
  margin: 0;
  color: #202124;
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
  max-width: 640px;
  margin: 0 auto;
  padding: 40px 24px;
}

.topic-form-card {
  background: white;
  border-radius: 16px;
  padding: 32px;
  border-top: 4px solid #7c3aed;
}

.form-intro {
  display: flex;
  gap: 16px;
  align-items: flex-start;
  background: #f5f1fe;
  border-radius: 12px;
  padding: 16px 20px;
  margin-bottom: 28px;
}

.form-intro p {
  margin: 0;
  font-size: 14px;
  color: #3c4043;
  line-height: 1.5;
}

.form-group {
  margin-bottom: 20px;
}

.form-group label {
  display: block;
  font-weight: 500;
  margin-bottom: 8px;
  color: #202124;
  font-size: 14px;
}

.optional {
  font-weight: 400;
  color: #80868b;
}

.form-group input,
.form-group textarea,
.form-group select {
  width: 100%;
  padding: 14px 16px;
  border: 1px solid #dadce0;
  border-radius: 8px;
  font-size: 15px;
  box-sizing: border-box;
  font-family: inherit;
  color: #202124;
  background: #fff;
}

.form-group input:focus,
.form-group textarea:focus,
.form-group select:focus {
  outline: none;
  border-color: #7c3aed;
  box-shadow: 0 0 0 2px rgba(124, 58, 237, 0.15);
}

.error-text {
  color: #d93025;
  font-size: 14px;
  margin: 0 0 16px;
}

.btn-create {
  width: 100%;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 10px;
  padding: 16px 24px;
  border: none;
  background: linear-gradient(135deg, #7c3aed, #6d28d9);
  color: white;
  font-weight: 600;
  font-size: 16px;
  border-radius: 10px;
  cursor: pointer;
  transition: all 0.2s;
}

.btn-create:hover:not(:disabled) {
  transform: translateY(-1px);
  box-shadow: 0 4px 12px rgba(124, 58, 237, 0.3);
}

.btn-create:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.spinner {
  width: 18px;
  height: 18px;
  border: 2px solid rgba(255,255,255,0.3);
  border-top-color: white;
  border-radius: 50%;
  animation: spin 0.6s linear infinite;
}

@keyframes spin {
  to { transform: rotate(360deg); }
}

/* Collaborative toggle */
.collab-toggle {
  display: flex;
  align-items: flex-start;
  gap: 12px;
  padding: 14px 16px;
  border: 1px solid #dadce0;
  border-radius: 10px;
  margin-bottom: 20px;
  cursor: pointer;
}
.collab-toggle input { margin-top: 3px; width: 16px; height: 16px; accent-color: #7c3aed; }
.collab-toggle-text { display: flex; flex-direction: column; gap: 3px; }
.collab-toggle-text strong { font-size: 14px; color: #202124; }
.collab-toggle-text span { font-size: 12.5px; color: #5f6368; line-height: 1.45; }

/* Invite card */
.invite-card { margin-top: 20px; }
.invite-title { font-size: 18px; margin: 0 0 4px; color: #202124; }
.invite-sub { font-size: 13px; color: #5f6368; margin: 0 0 16px; line-height: 1.5; }
.invite-empty { font-size: 13px; color: #80868b; padding: 12px 0; }
.member-list { display: flex; flex-direction: column; gap: 6px; margin-bottom: 16px; }
.member-row {
  display: flex; align-items: center; gap: 10px;
  padding: 10px 12px; border: 1px solid #e5e7eb; border-radius: 8px; cursor: pointer;
}
.member-row.disabled { opacity: 0.6; cursor: not-allowed; }
.member-row input { width: 16px; height: 16px; accent-color: #7c3aed; }
.member-name { flex: 1; font-size: 14px; color: #202124; }
.member-badge { font-size: 11px; font-weight: 600; padding: 2px 8px; border-radius: 10px; }
.member-badge.ok { background: #e6f4ea; color: #137333; }
.member-badge.no { background: #fce8e6; color: #c5221f; }
/* Shareable invite link */
.invite-link-block {
  margin: 4px 0 18px; padding: 16px; border: 1px dashed #d6bcfa;
  border-radius: 10px; background: #faf7ff;
}
.invite-link-head { display: flex; flex-direction: column; gap: 2px; margin-bottom: 12px; }
.invite-link-title { font-size: 13.5px; font-weight: 700; color: #6d28d9; }
.invite-link-note { font-size: 11.5px; color: #80868b; }
.btn-link-gen {
  background: #fff; border: 1px solid #c4b5fd; color: #6d28d9; cursor: pointer;
  font-size: 13px; font-weight: 600; padding: 9px 16px; border-radius: 8px;
}
.btn-link-gen:hover:not(:disabled) { background: #f3eeff; }
.btn-link-gen:disabled { opacity: 0.6; cursor: default; }
.invite-link-row { display: flex; gap: 8px; }
.invite-link-input {
  flex: 1; min-width: 0; font-size: 12.5px; color: #3c4043;
  padding: 9px 11px; border: 1px solid #e5e7eb; border-radius: 8px; background: #fff;
}
.btn-link-copy {
  background: #7c3aed; color: #fff; border: none; cursor: pointer;
  font-size: 13px; font-weight: 600; padding: 9px 16px; border-radius: 8px;
}
.invite-actions { display: flex; gap: 12px; }
.invite-actions .btn-create { flex: 1; }
.btn-secondary {
  padding: 16px 24px; border: 1px solid #dadce0; background: #fff;
  color: #3c4043; font-weight: 600; font-size: 15px; border-radius: 10px; cursor: pointer;
}
.btn-secondary:hover { background: #f8f9fa; }
</style>
