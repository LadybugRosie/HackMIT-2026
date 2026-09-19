<template>
  <div class="join-page">
    <div class="join-card">
      <div v-if="loading" class="join-loading">
        <div class="spinner"></div>
        <span>Loading invitation…</span>
      </div>

      <template v-else-if="error">
        <div class="join-badge err">!</div>
        <h1>Invite unavailable</h1>
        <p class="join-sub">{{ error }}</p>
        <button class="join-btn ghost" @click="router.push('/')">Go home</button>
      </template>

      <template v-else>
        <div class="join-badge">🛡</div>
        <h1>Join “{{ info.topic_title }}”</h1>
        <p class="join-sub">
          <strong>{{ info.inviter_name }}</strong> invited you to co-author in
          <strong>{{ info.lab_name }}</strong>.
        </p>

        <ol class="join-steps">
          <li :class="{ done: !!user }">Sign in or create your account</li>
          <li>Complete a short stylometry enrollment (same topic)</li>
          <li>Start writing — your contribution is verified separately</li>
        </ol>

        <div v-if="!user" class="join-actions">
          <button class="join-btn primary" @click="go('/signup')">Sign up to join</button>
          <button class="join-btn ghost" @click="go('/login')">I already have an account</button>
        </div>
        <div v-else class="join-actions">
          <button class="join-btn primary" :disabled="accepting" @click="accept">
            {{ accepting ? 'Joining…' : 'Join this report' }}
          </button>
        </div>

        <p v-if="acceptError" class="join-err">{{ acceptError }}</p>
        <p class="join-foot">Each co-author is judged against their own enrolled writing profile.</p>
      </template>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import axios from 'axios'
import { getApiUrl } from '@/utils/api-url'
import { useAuth } from '@/composables/auth'

const route = useRoute()
const router = useRouter()
const { user, initAuth } = useAuth()
const API = getApiUrl()
const token = route.params.token
const selfPath = `/join/${token}`

const loading = ref(true)
const error = ref('')
const info = ref({})
const accepting = ref(false)
const acceptError = ref('')

// Send unauthenticated users to auth as a researcher, returning here afterwards.
function go(base) {
  const role = base === '/signup' ? 'role=researcher&' : ''
  router.push(`${base}?${role}next=${encodeURIComponent(selfPath)}`)
}

async function accept() {
  accepting.value = true
  acceptError.value = ''
  try {
    const { data } = await axios.post(`${API}/api/research/join/${token}`)
    if (data.needs_enrollment) {
      const topicParam = encodeURIComponent(data.topic_title || '')
      router.push(
        `/researcher/stylometry-enrollment/${data.lab_id}?topic=${topicParam}&next=${encodeURIComponent(selfPath)}`
      )
      return
    }
    if (data.joined) {
      router.push(
        `/editor/${data.submission_id}?assignment_id=${data.assignment_id}&class_id=${data.lab_id}&collab=1`
      )
    }
  } catch (e) {
    acceptError.value = e.response?.data?.detail || 'Could not join this report. Please try again.'
    accepting.value = false
  }
}

onMounted(async () => {
  try {
    const { data } = await axios.get(`${API}/api/research/join-info/${token}`)
    info.value = data
  } catch (e) {
    error.value = e.response?.data?.detail || 'This invite link is invalid or has expired.'
    loading.value = false
    return
  }
  if (!user.value) await initAuth()
  loading.value = false
  // Already signed in → carry them straight through (enrollment or editor).
  if (user.value) accept()
})
</script>

<style scoped>
.join-page {
  min-height: 100vh; display: flex; align-items: center; justify-content: center;
  background: linear-gradient(135deg, #f5f3ff, #eef2ff);
  padding: 24px;
}
.join-card {
  width: 100%; max-width: 460px; background: #fff; border-radius: 20px;
  padding: 40px 36px; text-align: center;
  box-shadow: 0 20px 60px rgba(79, 70, 229, 0.15);
  border-top: 4px solid #7c3aed;
}
.join-loading { display: flex; flex-direction: column; align-items: center; gap: 14px; color: #5f6368; }
.spinner {
  width: 28px; height: 28px; border: 3px solid #e9d5ff; border-top-color: #7c3aed;
  border-radius: 50%; animation: spin 0.8s linear infinite;
}
@keyframes spin { to { transform: rotate(360deg); } }
.join-badge {
  width: 64px; height: 64px; margin: 0 auto 18px; border-radius: 50%;
  background: linear-gradient(135deg, #7c3aed, #a855f7); color: #fff;
  display: flex; align-items: center; justify-content: center; font-size: 28px;
}
.join-badge.err { background: linear-gradient(135deg, #ef4444, #dc2626); font-weight: 800; }
h1 { font-size: 22px; color: #1a1a2e; margin: 0 0 8px; }
.join-sub { font-size: 14.5px; color: #5f6368; line-height: 1.6; margin: 0 0 22px; }
.join-steps {
  text-align: left; margin: 0 0 24px; padding: 0; list-style: none;
  display: flex; flex-direction: column; gap: 10px;
}
.join-steps li {
  position: relative; padding-left: 30px; font-size: 13.5px; color: #3c4043; counter-increment: step;
}
.join-steps li::before {
  content: counter(step); position: absolute; left: 0; top: -1px;
  width: 20px; height: 20px; border-radius: 50%; background: #ede9fe; color: #7c3aed;
  font-size: 11px; font-weight: 700; display: flex; align-items: center; justify-content: center;
}
.join-steps { counter-reset: step; }
.join-steps li.done { color: #80868b; }
.join-steps li.done::before { content: '✓'; background: #e6f4ea; color: #137333; }
.join-actions { display: flex; flex-direction: column; gap: 10px; }
.join-btn {
  padding: 13px 18px; border-radius: 11px; font-size: 15px; font-weight: 600;
  cursor: pointer; border: none; transition: opacity 0.15s;
}
.join-btn.primary { background: linear-gradient(135deg, #7c3aed, #6d28d9); color: #fff; }
.join-btn.ghost { background: #f5f3ff; color: #6d28d9; }
.join-btn:disabled { opacity: 0.6; cursor: default; }
.join-btn:hover:not(:disabled) { opacity: 0.92; }
.join-err { color: #c5221f; font-size: 13px; margin: 14px 0 0; }
.join-foot { font-size: 11.5px; color: #9aa0a6; margin: 18px 0 0; line-height: 1.5; }
</style>
