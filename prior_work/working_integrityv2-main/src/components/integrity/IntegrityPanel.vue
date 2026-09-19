<template>
  <div class="integrity-panel" :class="{ open: isOpen }">
    <div class="panel-header">
      <h3>Document Integrity</h3>
      <button @click="$emit('close')" class="close-btn">×</button>
    </div>
    
    <div class="panel-content">
      <!-- Trust Score -->
      <div class="trust-score-section">
        <div class="trust-score" :class="trustClass">
          <span class="score-value">{{ trustScore === null ? '—' : trustScore }}</span>
          <span class="score-label">{{ trustScore === null ? 'Not Analyzed' : 'Trust Score' }}</span>
        </div>
        <div class="composition-score">
          <span class="comp-value">{{ compositionScore }}</span>
          <span class="comp-label">Composition</span>
        </div>
      </div>
      
      <!-- Content Mix Bar -->
      <div class="content-mix-section">
        <h4>Content Composition</h4>
        <div class="mix-bar">
          <div 
            class="mix-segment typed" 
            :style="{ width: `${typedPercent}%` }"
            :title="`Typed: ${typedPercent}%`"
          ></div>
          <div 
            class="mix-segment internal" 
            :style="{ width: `${internalPercent}%` }"
            :title="`Internal Copy: ${internalPercent}%`"
          ></div>
          <div 
            class="mix-segment external" 
            :style="{ width: `${externalPercent}%` }"
            :title="`External Paste: ${externalPercent}%`"
          ></div>
        </div>
        <div class="mix-legend">
          <div class="legend-item">
            <span class="legend-color typed"></span>
            <span>Typed ({{ typedPercent }}%)</span>
          </div>
          <div class="legend-item">
            <span class="legend-color internal"></span>
            <span>Own Work ({{ internalPercent }}%)</span>
          </div>
          <div class="legend-item">
            <span class="legend-color external"></span>
            <span>External ({{ externalPercent }}%)</span>
          </div>
        </div>
      </div>
      
      <!-- Flags -->
      <div class="flags-section" v-if="flags.length > 0">
        <h4>Integrity Flags</h4>
        <ul class="flags-list">
          <li v-for="(flag, index) in flags" :key="index" class="flag-item">
            <span class="flag-icon">⚠️</span>
            {{ flag }}
          </li>
        </ul>
      </div>
      
      <!-- External Content Found -->
      <div class="external-spans-section" v-if="externalPastesFound.length > 0">
        <h4>External Content Detected</h4>
        <div class="spans-info">
          <p>{{ externalPastesFound.length }} external paste(s) found in document</p>
          <div class="external-list">
            <div v-for="paste in externalPastesFound" :key="paste.id" class="external-item">
              <span class="paste-indicator">📋</span>
              <span class="paste-preview">{{ paste.preview }}...</span>
              <span v-if="paste.fuzzy" class="match-badge">{{ paste.matchRatio }}% match</span>
            </div>
          </div>
          <p class="highlight-note">🖍️ External content is highlighted in red in the editor</p>
        </div>
      </div>
      
      <!-- NEW: Retyped External Content Warning -->
      <div class="retyped-warning-section" v-if="retypedExternalDetected.length > 0">
        <h4>🚨 RETYPED EXTERNAL CONTENT DETECTED</h4>
        <div class="retyped-info">
          <p class="critical-warning">⚠️ {{ retypedExternalDetected.length }} segment(s) were typed that match previously pasted external content!</p>
          <p class="warning-explanation">This content is being counted as EXTERNAL, reducing trust score.</p>
          <div class="retyped-list">
            <div v-for="(seg, index) in retypedExternalDetected" :key="index" class="retyped-item">
              <div class="match-header">
                <span class="match-indicator">🔄</span>
                <span class="match-ratio">{{ seg.matchRatio }}% match</span>
                <span v-if="seg.wpm > 0" class="wpm-badge">{{ seg.wpm }} WPM</span>
                <span v-if="seg.suspiciousPattern" class="suspicious-badge">⚠️ Suspicious typing</span>
                <span v-if="seg.wasRecentlyPasted" class="recent-badge">⏰ Recent paste</span>
              </div>
              <div class="retyped-full-text">
                <div class="text-label">Complete retyped text:</div>
                <div class="full-text-content">{{ seg.text }}</div>
              </div>
            </div>
          </div>
          <p class="impact-note">💥 Impact: This content reduces your trust score as it appears to be copied by retyping external sources.</p>
        </div>
      </div>
      
      <!-- Analyze Button -->
      <div class="analyze-section">
        <button 
          @click="analyzeIntegrity" 
          class="analyze-btn"
          :disabled="analyzing"
        >
          {{ analyzing ? 'Analyzing...' : '🔍 Analyze Integrity Now' }}
        </button>
        <p class="analyze-note">Click to run text matching algorithm against stored databases</p>
        <p class="analyze-note" v-if="lastAnalyzedTime">
          Last analyzed: {{ lastAnalyzedTime }}
        </p>
        <p class="analyze-error" v-if="analysisError">
          Error: {{ analysisError }}
        </p>
      </div>
      
      <!-- Session Info -->
      <div class="session-info-section">
        <h4>Session Details</h4>
        <div class="info-row">
          <span class="info-label">Session ID:</span>
          <span class="info-value">{{ sessionId?.substring(0, 8) }}...</span>
        </div>
        <div class="info-row" v-if="strictMode">
          <span class="info-label">Mode:</span>
          <span class="info-value strict">Strict Mode</span>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed, ref } from 'vue'
import { useStore } from '@/composables/store'
import { getApiUrl } from '@/utils/api-url'
import axios from 'axios'

const props = defineProps({
  isOpen: {
    type: Boolean,
    default: false
  }
})

const emit = defineEmits(['close', 'analyze'])

const { integrity, editor } = useStore()
const highlightingExternal = ref(false)
const analyzing = ref(false)

const INTEGRITY_API = getApiUrl()

const analysisError = ref(null)

// Analyze integrity - triggers text matching algorithm
const analyzeIntegrity = async () => {
  analysisError.value = null
  if (window.analyzeIntegrityNow) {
    analyzing.value = true
    try {
      const result = await window.analyzeIntegrityNow()
      console.log('✅ Analysis completed:', result)
      if (result && typeof result.trustScore === 'number') {
        analysisError.value = null
      }
    } catch (e) {
      console.error('Integrity analysis error:', e)
      analysisError.value = e.message || 'Analysis failed'
    } finally {
      analyzing.value = false
    }
  } else {
    alert('Integrity tracker not loaded. Please reload the page.')
  }
}

// Computed properties - PERSIST last scores, don't reset
const trustScore = computed(() => {
  if (integrity?.value?.lastAnalyzed) {
    return integrity?.value?.scores?.trust ?? 0
  }
  return null
})

const compositionScore = computed(() => {
  if (integrity?.value?.lastAnalyzed) {
    return integrity?.value?.scores?.composition ?? 0
  }
  return null
})

// CRITICAL FIX: Use SESSION-BASED mix, not current document mix
// This ensures the percentages reflect the entire session history, not just what's currently visible
const typedPercent = computed(() => {
  // Prefer sessionMix if available (session-based), fallback to mix (current doc)
  const sessionTyped = integrity?.value?.sessionMix?.typed
  const currentTyped = integrity?.value?.mix?.typed || 0
  return Math.round((sessionTyped !== undefined ? sessionTyped : currentTyped) * 100)
})
const internalPercent = computed(() => {
  const sessionInternal = integrity?.value?.sessionMix?.internal
  const currentInternal = integrity?.value?.mix?.internal || 0
  return Math.round((sessionInternal !== undefined ? sessionInternal : currentInternal) * 100)
})
const externalPercent = computed(() => {
  const sessionExternal = integrity?.value?.sessionMix?.external
  const currentExternal = integrity?.value?.mix?.external || 0
  return Math.round((sessionExternal !== undefined ? sessionExternal : currentExternal) * 100)
})

const trustClass = computed(() => {
  if (trustScore.value >= 70) return 'high'
  if (trustScore.value >= 50) return 'medium'
  return 'low'
})

const flags = computed(() => integrity?.value?.flags || [])
const extSpans = computed(() => integrity?.value?.extSpans || [])
const externalPastesFound = computed(() => integrity?.value?.externalPastesFound || [])
const retypedExternalDetected = computed(() => integrity?.value?.retypedExternalDetected || []) // NEW
const sessionId = computed(() => integrity?.value?.sessionId)
const strictMode = computed(() => integrity?.value?.strictMode)

// Track when last analyzed
const lastAnalyzedTime = computed(() => {
  if (integrity?.value?.lastAnalyzed) {
    const date = new Date(integrity.value.lastAnalyzed)
    const now = new Date()
    const diff = Math.floor((now - date) / 1000) // seconds
    
    if (diff < 60) return `${diff} seconds ago`
    if (diff < 3600) return `${Math.floor(diff / 60)} minutes ago`
    if (diff < 86400) return `${Math.floor(diff / 3600)} hours ago`
    return date.toLocaleTimeString()
  }
  return null
})

// Methods
const highlightExternal = () => {
  highlightingExternal.value = !highlightingExternal.value
  
  if (highlightingExternal.value && editor.value) {
    // Add highlights to external spans
    extSpans.value.forEach(span => {
      // TipTap decorations would be applied here
    })
  }
}
</script>

<style scoped>
.integrity-panel {
  position: fixed;
  right: -400px;
  top: 0;
  width: 400px;
  height: 100vh;
  background: white;
  box-shadow: -2px 0 10px rgba(0, 0, 0, 0.1);
  transition: right 0.3s ease;
  z-index: 1000;
  display: flex;
  flex-direction: column;
}

.integrity-panel.open {
  right: 0;
}

.panel-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 20px;
  border-bottom: 1px solid #e0e0e0;
}

.panel-header h3 {
  margin: 0;
  font-size: 18px;
  color: #333;
}

.close-btn {
  background: none;
  border: none;
  font-size: 24px;
  cursor: pointer;
  color: #666;
  padding: 0;
  width: 30px;
  height: 30px;
  display: flex;
  align-items: center;
  justify-content: center;
}

.close-btn:hover {
  color: #333;
}

.panel-content {
  flex: 1;
  overflow-y: auto;
  padding: 20px;
}

/* Trust Score Section */
.trust-score-section {
  display: flex;
  gap: 20px;
  margin-bottom: 30px;
}

.trust-score,
.composition-score {
  flex: 1;
  text-align: center;
  padding: 20px;
  border-radius: 12px;
  background: #f8f9fa;
}

.trust-score {
  border: 2px solid #e0e0e0;
}

.trust-score.high {
  border-color: #4caf50;
  background: #f1f8f4;
}

.trust-score.medium {
  border-color: #ff9800;
  background: #fff8f1;
}

.trust-score.low {
  border-color: #f44336;
  background: #fef1f1;
}

.score-value,
.comp-value {
  display: block;
  font-size: 36px;
  font-weight: bold;
  margin-bottom: 5px;
}

.trust-score.high .score-value {
  color: #4caf50;
}

.trust-score.medium .score-value {
  color: #ff9800;
}

.trust-score.low .score-value {
  color: #f44336;
}

.comp-value {
  color: #667eea;
}

.score-label,
.comp-label {
  font-size: 12px;
  color: #666;
  text-transform: uppercase;
}

/* Content Mix Section */
.content-mix-section {
  margin-bottom: 30px;
}

.content-mix-section h4 {
  margin: 0 0 15px;
  font-size: 14px;
  color: #666;
  text-transform: uppercase;
}

.mix-bar {
  height: 30px;
  border-radius: 15px;
  overflow: hidden;
  display: flex;
  background: #f0f0f0;
  margin-bottom: 15px;
}

.mix-segment {
  height: 100%;
  transition: width 0.3s ease;
}

.mix-segment.typed {
  background: #4caf50;
}

.mix-segment.internal {
  background: #2196f3;
}

.mix-segment.external {
  background: #f44336;
}

.mix-legend {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.legend-item {
  display: flex;
  align-items: center;
  font-size: 13px;
  color: #666;
}

.legend-color {
  width: 12px;
  height: 12px;
  border-radius: 2px;
  margin-right: 8px;
}

.legend-color.typed {
  background: #4caf50;
}

.legend-color.internal {
  background: #2196f3;
}

.legend-color.external {
  background: #f44336;
}

/* Flags Section */
.flags-section {
  margin-bottom: 30px;
}

.flags-section h4 {
  margin: 0 0 15px;
  font-size: 14px;
  color: #666;
  text-transform: uppercase;
}

.flags-list {
  list-style: none;
  padding: 0;
  margin: 0;
}

.flag-item {
  display: flex;
  align-items: flex-start;
  padding: 10px;
  background: #fff8f1;
  border: 1px solid #ffe0b2;
  border-radius: 8px;
  margin-bottom: 8px;
  font-size: 13px;
  color: #666;
}

.flag-icon {
  margin-right: 8px;
}

/* External Spans Section */
.external-spans-section {
  margin-bottom: 30px;
}

.external-spans-section h4 {
  margin: 0 0 15px;
  font-size: 14px;
  color: #666;
  text-transform: uppercase;
}

.spans-info p {
  margin: 0 0 10px;
  font-size: 13px;
  color: #666;
}

.highlight-btn {
  padding: 8px 16px;
  background: #667eea;
  color: white;
  border: none;
  border-radius: 6px;
  font-size: 13px;
  cursor: pointer;
  transition: all 0.2s;
}

.highlight-btn:hover {
  background: #5a67d8;
}

.highlight-btn.active {
  background: #f44336;
}

/* External content list styles */
.external-list {
  margin: 15px 0;
  max-height: 200px;
  overflow-y: auto;
  border: 1px solid #ffe0b2;
  border-radius: 8px;
  background: white;
}

.external-item {
  display: flex;
  align-items: center;
  padding: 10px;
  margin: 0;
  border-bottom: 1px solid #f5f5f5;
  border-left: 3px solid #ff5252;
}

.external-item:last-child {
  border-bottom: none;
}

.paste-indicator {
  margin-right: 10px;
  font-size: 16px;
}

.paste-preview {
  flex: 1;
  font-size: 12px;
  color: #666;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.match-badge {
  background: #ffab91;
  color: #bf360c;
  padding: 2px 8px;
  border-radius: 12px;
  font-size: 11px;
  font-weight: 600;
  margin-left: 10px;
}

.highlight-note {
  margin-top: 10px;
  padding: 10px;
  background: #ffebee;
  border-radius: 6px;
  font-size: 12px;
  color: #c62828;
  text-align: center;
  border: 1px solid #ffcdd2;
}

/* Retyped External Content styles - MORE PROMINENT */
.retyped-warning-section {
  margin-bottom: 30px;
  padding: 20px;
  background: linear-gradient(135deg, #ffebee 0%, #ffcdd2 100%);
  border: 2px solid #f44336;
  border-radius: 12px;
  box-shadow: 0 4px 8px rgba(244, 67, 54, 0.2);
}

.retyped-warning-section h4 {
  margin: 0 0 15px;
  font-size: 16px;
  color: #c62828;
  text-transform: uppercase;
  font-weight: 700;
}

.retyped-info .critical-warning {
  margin: 0 0 10px;
  font-size: 14px;
  color: #c62828;
  font-weight: 600;
}

.retyped-info .warning-explanation {
  margin: 0 0 15px;
  font-size: 13px;
  color: #d32f2f;
  font-weight: 500;
}

.retyped-list {
  margin: 20px 0;
  max-height: 400px;
  overflow-y: auto;
}

.retyped-item {
  background: white;
  border: 2px solid #ff5252;
  border-radius: 8px;
  padding: 15px;
  margin-bottom: 15px;
  box-shadow: 0 2px 4px rgba(0,0,0,0.1);
}

.match-header {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 12px;
  flex-wrap: wrap;
}

.match-indicator {
  font-size: 18px;
}

.match-ratio {
  background: linear-gradient(135deg, #f44336 0%, #e53935 100%);
  color: white;
  padding: 3px 10px;
  border-radius: 12px;
  font-size: 12px;
  font-weight: 600;
}

.wpm-badge {
  background: #fff3e0;
  color: #e65100;
  padding: 3px 10px;
  border-radius: 12px;
  font-size: 11px;
  font-weight: 500;
}

.suspicious-badge {
  background: #ffeb3b;
  color: #c62828;
  padding: 3px 10px;
  border-radius: 12px;
  font-size: 11px;
  font-weight: 600;
}

.recent-badge {
  background: #e8eaf6;
  color: #5e35b1;
  padding: 3px 10px;
  border-radius: 12px;
  font-size: 11px;
  font-weight: 500;
}

.retyped-full-text {
  margin-top: 10px;
  padding-top: 10px;
  border-top: 1px solid #ffcdd2;
}

.text-label {
  font-size: 11px;
  color: #666;
  text-transform: uppercase;
  margin-bottom: 8px;
  font-weight: 600;
}

.full-text-content {
  font-size: 13px;
  color: #212121;
  line-height: 1.6;
  background: #fafafa;
  padding: 12px;
  border-radius: 6px;
  border-left: 4px solid #f44336;
  white-space: pre-wrap;
  word-wrap: break-word;
  max-height: 200px;
  overflow-y: auto;
}

.impact-note {
  margin-top: 15px;
  padding: 10px;
  background: #c62828;
  color: white;
  border-radius: 6px;
  font-size: 12px;
  font-weight: 500;
  text-align: center;
}

/* Session Info Section */
.session-info-section h4 {
  margin: 0 0 15px;
  font-size: 14px;
  color: #666;
  text-transform: uppercase;
}

.info-row {
  display: flex;
  justify-content: space-between;
  padding: 8px 0;
  font-size: 13px;
}

.info-label {
  color: #666;
}

.info-value {
  color: #333;
  font-family: monospace;
}

.info-value.strict {
  color: #f44336;
  font-weight: bold;
}

/* Analyze Section */
.analyze-section {
  margin-bottom: 25px;
  text-align: center;
}

.analyze-btn {
  width: 100%;
  padding: 16px;
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  color: white;
  border: none;
  border-radius: 8px;
  font-size: 16px;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.3s;
  box-shadow: 0 4px 15px rgba(102, 126, 234, 0.3);
}

.analyze-btn:hover:not(:disabled) {
  transform: translateY(-2px);
  box-shadow: 0 6px 20px rgba(102, 126, 234, 0.4);
}

.analyze-btn:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}

.analyze-note {
  margin-top: 8px;
  font-size: 11px;
  color: #999;
  font-style: italic;
}

.analyze-error {
  margin-top: 8px;
  font-size: 12px;
  color: #f44336;
  font-weight: 500;
  padding: 6px 10px;
  background: #fef1f1;
  border-radius: 4px;
}
</style>

