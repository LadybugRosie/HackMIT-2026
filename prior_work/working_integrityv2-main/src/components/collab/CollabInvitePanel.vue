<template>
  <div class="invite-overlay" @click.self="$emit('close')">
    <div class="invite-panel">
      <div class="invite-header">
        <h3>Collaborators</h3>
        <button class="invite-close" @click="$emit('close')">
          <svg width="20" height="20" viewBox="0 0 24 24" fill="currentColor">
            <path d="M19 6.41L17.59 5 12 10.59 6.41 5 5 6.41 10.59 12 5 17.59 6.41 19 12 13.41 17.59 19 19 17.59 13.41 12z"/>
          </svg>
        </button>
      </div>

      <div class="invite-body">
        <div v-if="loading" class="invite-loading">Loading…</div>
        <template v-else>
          <!-- Current authors -->
          <div class="invite-section">
            <span class="invite-label">On this report ({{ authors.length }})</span>
            <div v-for="a in authors" :key="a.user_id" class="author-pill">
              <span class="author-dot"></span>
              <span class="author-name">{{ a.name }}</span>
              <span v-if="a.is_primary" class="tag primary">creator</span>
              <span class="tag" :class="a.stylometry_enrolled ? 'ok' : 'no'">
                {{ a.stylometry_enrolled ? 'enrolled' : 'not enrolled' }}
              </span>
            </div>
          </div>

          <!-- Invitable members -->
          <div class="invite-section">
            <span class="invite-label">Lab members</span>
            <p v-if="invitable.length === 0" class="invite-empty">No other lab members to invite.</p>
            <div v-for="m in invitable" :key="m.user_id" class="member-row" :class="{ disabled: !m.stylometry_enrolled }">
              <span class="author-name">{{ m.name }}</span>
              <span class="tag" :class="m.stylometry_enrolled ? 'ok' : 'no'">
                {{ m.stylometry_enrolled ? 'enrolled' : 'not enrolled' }}
              </span>
              <button
                v-if="canInvite"
                class="invite-btn"
                :disabled="!m.stylometry_enrolled || invitingId === m.user_id"
                :title="m.stylometry_enrolled ? 'Invite as co-author' : 'Must complete stylometry enrollment first'"
                @click="invite(m)"
              >{{ invitingId === m.user_id ? '…' : 'Invite' }}</button>
            </div>
          </div>

          <p v-if="error" class="invite-error">{{ error }}</p>
          <p class="invite-note">Only stylometry-enrolled members can co-author — each author is judged against their own profile.</p>
        </template>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import axios from 'axios'
import { getApiUrl } from '@/utils/api-url'
import { useAuth } from '@/composables/auth'

const props = defineProps({
  submissionId: { type: String, required: true },
  labId: { type: String, default: '' },
})
defineEmits(['close'])

const API = getApiUrl()
const { user } = useAuth()

const loading = ref(true)
const authors = ref([])
const members = ref([])
const primaryId = ref(null)
const invitingId = ref(null)
const error = ref('')

const canInvite = computed(() => primaryId.value === user.value?.user_id)
const invitable = computed(() => {
  const authorIds = new Set(authors.value.map(a => a.user_id))
  return members.value.filter(m => !authorIds.has(m.user_id))
})

async function load() {
  loading.value = true
  try {
    const a = await axios.get(`${API}/api/research/submissions/${props.submissionId}/authors`)
    authors.value = a.data.authors || []
    primaryId.value = a.data.primary_author_id
    if (props.labId) {
      const m = await axios.get(`${API}/api/research/labs/${props.labId}/members`)
      members.value = (m.data.members || []).map(x => ({
        user_id: x.user_id, name: x.name, stylometry_enrolled: x.stylometry_enrolled,
      }))
    }
  } catch (e) {
    error.value = e.response?.data?.detail || 'Failed to load collaborators'
  } finally {
    loading.value = false
  }
}

async function invite(m) {
  invitingId.value = m.user_id
  error.value = ''
  try {
    await axios.post(`${API}/api/research/submissions/${props.submissionId}/invite-author`, { user_id: m.user_id })
    await load()
  } catch (e) {
    error.value = e.response?.data?.detail || 'Failed to invite'
  } finally {
    invitingId.value = null
  }
}

onMounted(load)
</script>

<style scoped>
.invite-overlay {
  position: fixed; inset: 0; background: rgba(0,0,0,0.4);
  display: flex; align-items: flex-start; justify-content: flex-end; z-index: 200;
}
.invite-panel {
  width: 380px; max-width: 92vw; height: 100vh; background: #fff;
  box-shadow: -4px 0 24px rgba(0,0,0,0.15); display: flex; flex-direction: column;
}
.invite-header {
  display: flex; align-items: center; justify-content: space-between;
  padding: 18px 20px; border-bottom: 1px solid #e5e7eb;
}
.invite-header h3 { margin: 0; font-size: 17px; color: #202124; }
.invite-close { background: none; border: none; cursor: pointer; color: #5f6368; padding: 4px; border-radius: 6px; }
.invite-close:hover { background: #f1f3f4; }
.invite-body { flex: 1; overflow-y: auto; padding: 18px 20px; }
.invite-loading { color: #5f6368; font-size: 14px; padding: 20px 0; }
.invite-section { margin-bottom: 22px; }
.invite-label { display: block; font-size: 11px; font-weight: 700; text-transform: uppercase; letter-spacing: 0.05em; color: #80868b; margin-bottom: 10px; }
.author-pill, .member-row {
  display: flex; align-items: center; gap: 8px;
  padding: 9px 10px; border: 1px solid #e5e7eb; border-radius: 8px; margin-bottom: 6px;
}
.member-row.disabled { opacity: 0.7; }
.author-dot { width: 9px; height: 9px; border-radius: 50%; background: #7c3aed; flex-shrink: 0; }
.author-name { flex: 1; font-size: 14px; color: #202124; }
.tag { font-size: 10px; font-weight: 700; text-transform: uppercase; padding: 2px 7px; border-radius: 9px; }
.tag.primary { background: #f5f1fe; color: #7c3aed; }
.tag.ok { background: #e6f4ea; color: #137333; }
.tag.no { background: #fce8e6; color: #c5221f; }
.invite-btn {
  background: #7c3aed; color: #fff; border: none; cursor: pointer;
  font-size: 12px; font-weight: 600; padding: 5px 12px; border-radius: 7px;
}
.invite-btn:disabled { opacity: 0.4; cursor: not-allowed; }
.invite-empty { font-size: 13px; color: #80868b; margin: 0; }
.invite-error { color: #c5221f; font-size: 13px; }
.invite-note { font-size: 12px; color: #80868b; line-height: 1.5; margin-top: 8px; }
</style>
