<template>
  <div class="integrity-session-start">
    <div class="session-container">
      <div class="session-header">
        <h1>Start Integrity Session</h1>
        <p>Initialize document tracking to monitor content authenticity</p>
      </div>

      <div class="session-options">
        <div class="option-group">
          <label class="option-label">
            <input 
              type="checkbox" 
              v-model="strictMode"
              class="option-checkbox"
            />
            <span class="option-text">
              <strong>Strict Mode</strong>
              <small>Block all external paste operations</small>
            </span>
          </label>
        </div>

        <div class="session-info">
          <div class="info-item">
            <span class="info-icon">📝</span>
            <span>Typed content will receive highest trust score</span>
          </div>
          <div class="info-item">
            <span class="info-icon">📋</span>
            <span>Internal copy-paste maintains neutral trust</span>
          </div>
          <div class="info-item">
            <span class="info-icon">⚠️</span>
            <span>External paste will reduce trust score</span>
          </div>
        </div>
      </div>

      <div class="session-actions">
        <button 
          @click="startSession" 
          class="start-button"
          :disabled="loading"
        >
          {{ loading ? 'Starting...' : 'Start Session' }}
        </button>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { useStore } from '@/composables/store'
import { getApiUrl } from '@/utils/api-url'
import axios from 'axios'

const router = useRouter()
const store = useStore()

const strictMode = ref(false)
const loading = ref(false)

const INTEGRITY_API = getApiUrl()

const startSession = async () => {
  loading.value = true
  
  try {
    // Call backend to start session
    const response = await axios.post(`${INTEGRITY_API}/api/integrity/session/start`, {
      strict_mode: strictMode.value
    })
    
    const { session_id, doc_id } = response.data
    
    // Store session info in global store
    if (!store.integrity) {
      store.integrity = {}
    }
    
    store.integrity.sessionId = session_id
    store.integrity.docId = doc_id
    store.integrity.strictMode = strictMode.value
    store.integrity.active = true
    
    // Navigate to editor with session
    // Use router to navigate (works in both dev and production)
    router.push(`/editor/1?session=${session_id}`)
  } catch (error) {
    console.error('Failed to start integrity session:', error)
    alert('Failed to start integrity session. Please try again.')
  } finally {
    loading.value = false
  }
}
</script>

<style scoped>
.integrity-session-start {
  min-height: 100vh;
  display: flex;
  align-items: center;
  justify-content: center;
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  padding: 20px;
}

.session-container {
  background: white;
  border-radius: 12px;
  padding: 40px;
  max-width: 500px;
  width: 100%;
  box-shadow: 0 20px 60px rgba(0, 0, 0, 0.15);
}

.session-header {
  text-align: center;
  margin-bottom: 30px;
}

.session-header h1 {
  font-size: 28px;
  margin: 0 0 10px;
  color: #333;
}

.session-header p {
  color: #666;
  font-size: 14px;
}

.session-options {
  margin-bottom: 30px;
}

.option-group {
  margin-bottom: 25px;
}

.option-label {
  display: flex;
  align-items: flex-start;
  cursor: pointer;
  padding: 15px;
  border: 1px solid #e0e0e0;
  border-radius: 8px;
  transition: all 0.2s;
}

.option-label:hover {
  background: #f8f9fa;
  border-color: #667eea;
}

.option-checkbox {
  margin-right: 12px;
  margin-top: 3px;
}

.option-text {
  flex: 1;
  display: flex;
  flex-direction: column;
}

.option-text strong {
  color: #333;
  margin-bottom: 4px;
}

.option-text small {
  color: #666;
  font-size: 12px;
}

.session-info {
  background: #f8f9fa;
  border-radius: 8px;
  padding: 20px;
}

.info-item {
  display: flex;
  align-items: center;
  margin-bottom: 12px;
}

.info-item:last-child {
  margin-bottom: 0;
}

.info-icon {
  margin-right: 10px;
  font-size: 18px;
}

.info-item span:last-child {
  color: #555;
  font-size: 14px;
}

.session-actions {
  text-align: center;
}

.start-button {
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  color: white;
  border: none;
  padding: 14px 40px;
  font-size: 16px;
  font-weight: 600;
  border-radius: 8px;
  cursor: pointer;
  transition: all 0.3s;
  box-shadow: 0 4px 15px rgba(102, 126, 234, 0.3);
}

.start-button:hover:not(:disabled) {
  transform: translateY(-2px);
  box-shadow: 0 6px 20px rgba(102, 126, 234, 0.4);
}

.start-button:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}
</style>
