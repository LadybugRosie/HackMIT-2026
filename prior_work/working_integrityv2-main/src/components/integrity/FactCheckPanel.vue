<template>
  <div class="factcheck-panel" :class="{ open: isOpen }">
    <div class="panel-header">
      <h3>Hallucination & Source Check</h3>
      <button @click="$emit('close')" class="close-btn">×</button>
    </div>
    
    <div class="panel-content">
      <!-- Loading State -->
      <div v-if="loading" class="loading-state">
        <div class="spinner"></div>
        <p>Verifying claims and references...</p>
        <p class="loading-sub">Checking DOIs, URLs, and factual accuracy</p>
      </div>
      
      <!-- Error State -->
      <div v-else-if="error" class="error-state">
        <span class="error-icon">⚠️</span>
        <p>{{ error }}</p>
        <button @click="runFactCheck" class="retry-btn">Retry</button>
      </div>
      
      <!-- Results -->
      <div v-else-if="results" class="results-container">
        <!-- Recheck Button -->
        <div class="recheck-section">
          <button @click="runFactCheck" class="recheck-btn" :disabled="loading">
            {{ loading ? 'Checking...' : '🔄 Recheck Document' }}
          </button>
        </div>
        
        <!-- Results rendering (extracted into reusable component) -->
        <FactCheckResults :results="results" />
      </div>
      
      <!-- Empty State -->
      <div v-else class="empty-state">
        <div class="empty-icon">🔍</div>
        <h4>Detect Hallucinations & Verify Sources</h4>
        <p>Check claims, DOIs, URLs for accuracy and catch AI hallucinations</p>
        <button @click="runFactCheck" class="check-btn">
          Run Fact & Source Check
        </button>
        <div class="mode-selector">
          <label>Verification Mode:</label>
          <select v-model="evidenceMode">
            <option value="REGISTRY_ONLY">Registry Only (DOI/URL + Knowledge Base)</option>
            <option value="OFFLINE_ONLY">Offline Only (Knowledge Base)</option>
            <option value="HYBRID">Hybrid (Full Web Retrieval)</option>
          </select>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref } from 'vue'
import { useStore } from '@/composables/store'
import FactCheckResults from './FactCheckResults.vue'

const props = defineProps({
  isOpen: {
    type: Boolean,
    default: false
  }
})

const emit = defineEmits(['close'])

const { editor } = useStore()

const loading = ref(false)
const error = ref(null)
const results = ref(null)
const evidenceMode = ref('REGISTRY_ONLY')

import { getApiUrl } from '@/utils/api-url'

const FACTCHECK_API = `${getApiUrl()}/api/auth/factcheck/verify`

const runFactCheck = async () => {
  if (!editor.value) {
    error.value = 'Editor not available'
    return
  }
  
  // Get document text
  const text = editor.value.getText()
  
  if (!text || text.trim().length < 10) {
    error.value = 'Document is too short to analyze'
    return
  }
  
  loading.value = true
  error.value = null
  
  // Get auth token from localStorage
  const token = localStorage.getItem('auth_token')
  
  if (!token) {
    error.value = 'No active session. Please log in first.'
    loading.value = false
    return
  }
  
  try {
    // FIX #7: Use Authorization header, not query param
    const response = await fetch(`${FACTCHECK_API}`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${token}`,
      },
      body: JSON.stringify({
        text: text,
        evidence_mode: evidenceMode.value
      })
    })
    
    if (!response.ok) {
      throw new Error(`API error: ${response.status}`)
    }
    
    results.value = await response.json()
    
  } catch (err) {
    error.value = err.message || 'Failed to verify document'
  } finally {
    loading.value = false
  }
}

// Expose for external triggering
defineExpose({ runFactCheck })
</script>

<style scoped>
.factcheck-panel {
  position: fixed;
  right: -480px;
  top: 0;
  width: 480px;
  height: 100vh;
  background: linear-gradient(180deg, #0f0f1a 0%, #1a1a2e 100%);
  box-shadow: -8px 0 40px rgba(0, 0, 0, 0.5);
  transition: right 0.4s cubic-bezier(0.4, 0, 0.2, 1);
  z-index: 1000;
  display: flex;
  flex-direction: column;
  border-left: 1px solid rgba(139, 92, 246, 0.2);
}

.factcheck-panel.open {
  right: 0;
}

.panel-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 24px;
  background: linear-gradient(135deg, rgba(139, 92, 246, 0.15) 0%, rgba(6, 182, 212, 0.1) 100%);
  border-bottom: 1px solid rgba(255, 255, 255, 0.08);
  backdrop-filter: blur(20px);
}

.panel-header h3 {
  margin: 0;
  font-size: 18px;
  font-weight: 700;
  color: #ffffff;
  display: flex;
  align-items: center;
  gap: 10px;
  letter-spacing: -0.02em;
}

.panel-header h3::before {
  content: '🛡️';
  font-size: 20px;
}

.close-btn {
  background: rgba(255, 255, 255, 0.08);
  border: 1px solid rgba(255, 255, 255, 0.1);
  font-size: 20px;
  cursor: pointer;
  color: rgba(255, 255, 255, 0.7);
  padding: 0;
  width: 36px;
  height: 36px;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: 10px;
  transition: all 0.2s ease;
}

.close-btn:hover {
  background: rgba(255, 255, 255, 0.15);
  color: #fff;
  transform: scale(1.05);
}

.panel-content {
  flex: 1;
  overflow-y: auto;
  padding: 24px;
  scrollbar-width: thin;
  scrollbar-color: rgba(139, 92, 246, 0.3) transparent;
}

.panel-content::-webkit-scrollbar {
  width: 6px;
}

.panel-content::-webkit-scrollbar-track {
  background: transparent;
}

.panel-content::-webkit-scrollbar-thumb {
  background: rgba(139, 92, 246, 0.3);
  border-radius: 3px;
}

/* Loading State */
.loading-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 80px 20px;
  text-align: center;
}

.spinner {
  width: 56px;
  height: 56px;
  border: 3px solid rgba(139, 92, 246, 0.2);
  border-top-color: #8b5cf6;
  border-radius: 50%;
  animation: spin 0.8s linear infinite;
  margin-bottom: 24px;
  box-shadow: 0 0 30px rgba(139, 92, 246, 0.3);
}

@keyframes spin {
  to { transform: rotate(360deg); }
}

.loading-state p {
  margin: 0;
  color: #ffffff;
  font-size: 16px;
  font-weight: 500;
}

.loading-sub {
  color: rgba(255, 255, 255, 0.5) !important;
  font-size: 13px !important;
  margin-top: 10px !important;
}

/* Error State */
.error-state {
  text-align: center;
  padding: 60px 20px;
  background: rgba(244, 63, 94, 0.08);
  border-radius: 16px;
  border: 1px solid rgba(244, 63, 94, 0.2);
}

.error-icon {
  font-size: 56px;
  display: block;
  margin-bottom: 16px;
}

.error-state p {
  color: #f87171;
  margin: 0 0 20px;
  font-size: 14px;
}

.retry-btn {
  padding: 12px 28px;
  background: linear-gradient(135deg, #8b5cf6 0%, #6366f1 100%);
  color: white;
  border: none;
  border-radius: 10px;
  cursor: pointer;
  font-weight: 600;
  transition: all 0.3s ease;
  box-shadow: 0 4px 20px rgba(139, 92, 246, 0.3);
}

.retry-btn:hover {
  transform: translateY(-2px);
  box-shadow: 0 8px 30px rgba(139, 92, 246, 0.4);
}

/* Empty State */
.empty-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 60px 24px;
  text-align: center;
  background: rgba(139, 92, 246, 0.05);
  border-radius: 20px;
  border: 1px dashed rgba(139, 92, 246, 0.2);
  margin-top: 20px;
}

.empty-icon {
  font-size: 72px;
  margin-bottom: 24px;
  filter: drop-shadow(0 0 30px rgba(139, 92, 246, 0.3));
}

.empty-state h4 {
  margin: 0 0 12px;
  font-size: 22px;
  color: #ffffff;
  font-weight: 700;
  letter-spacing: -0.02em;
}

.empty-state p {
  margin: 0 0 28px;
  color: rgba(255, 255, 255, 0.5);
  font-size: 14px;
  line-height: 1.6;
  max-width: 280px;
}

.check-btn {
  padding: 16px 36px;
  background: linear-gradient(135deg, #8b5cf6 0%, #6366f1 100%);
  color: white;
  border: none;
  border-radius: 12px;
  font-size: 16px;
  font-weight: 700;
  cursor: pointer;
  transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
  box-shadow: 0 8px 30px rgba(139, 92, 246, 0.35), inset 0 1px 0 rgba(255, 255, 255, 0.1);
  position: relative;
  overflow: hidden;
}

.check-btn::before {
  content: '';
  position: absolute;
  top: 0;
  left: -100%;
  width: 100%;
  height: 100%;
  background: linear-gradient(90deg, transparent, rgba(255, 255, 255, 0.2), transparent);
  transition: left 0.5s ease;
}

.check-btn:hover {
  transform: translateY(-3px);
  box-shadow: 0 12px 40px rgba(139, 92, 246, 0.45), inset 0 1px 0 rgba(255, 255, 255, 0.15);
}

.check-btn:hover::before {
  left: 100%;
}

/* Recheck Section */
.recheck-section {
  margin-bottom: 28px;
  text-align: center;
  padding: 16px;
  background: rgba(16, 185, 129, 0.08);
  backdrop-filter: blur(20px);
  border-radius: 16px;
  border: 1px solid rgba(16, 185, 129, 0.2);
}

.recheck-btn {
  padding: 14px 32px;
  background: linear-gradient(135deg, #10b981 0%, #059669 100%);
  color: white;
  border: none;
  border-radius: 12px;
  font-size: 14px;
  font-weight: 700;
  cursor: pointer;
  transition: all 0.3s ease;
  box-shadow: 0 6px 24px rgba(16, 185, 129, 0.35), inset 0 1px 0 rgba(255, 255, 255, 0.1);
  display: inline-flex;
  align-items: center;
  gap: 10px;
  letter-spacing: -0.01em;
}

.recheck-btn:hover:not(:disabled) {
  transform: translateY(-2px);
  box-shadow: 0 10px 32px rgba(16, 185, 129, 0.45), inset 0 1px 0 rgba(255, 255, 255, 0.15);
}

.recheck-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.mode-selector {
  margin-top: 28px;
  display: flex;
  flex-direction: column;
  gap: 10px;
  align-items: center;
}

.mode-selector label {
  font-size: 12px;
  color: rgba(255, 255, 255, 0.5);
  text-transform: uppercase;
  letter-spacing: 0.05em;
}

.mode-selector select {
  padding: 12px 16px;
  border: 1px solid rgba(255, 255, 255, 0.15);
  border-radius: 10px;
  font-size: 13px;
  background: rgba(255, 255, 255, 0.05);
  color: #ffffff;
  cursor: pointer;
  transition: all 0.2s ease;
  min-width: 260px;
}

.mode-selector select:hover {
  background: rgba(255, 255, 255, 0.08);
  border-color: rgba(255, 255, 255, 0.2);
}

.mode-selector select:focus {
  outline: none;
  border-color: rgba(139, 92, 246, 0.5);
  box-shadow: 0 0 0 3px rgba(139, 92, 246, 0.15);
}

.mode-selector select option {
  background: #1a1a2e;
  color: #ffffff;
}
</style>
