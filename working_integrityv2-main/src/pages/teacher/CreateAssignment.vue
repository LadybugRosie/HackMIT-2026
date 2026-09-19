<template>
  <div class="create-assignment-page">
    <!-- Header -->
    <header class="page-header">
      <div class="header-left">
        <button @click="goBack" class="back-btn">
          <svg width="24" height="24" viewBox="0 0 24 24" fill="currentColor">
            <path d="M19 6.41L17.59 5 12 10.59 6.41 5 5 6.41 10.59 12 5 17.59 6.41 19 12 13.41 17.59 19 19 17.59 13.41 12z"/>
          </svg>
        </button>
        <h1>{{ isEdit ? 'Edit Assignment' : 'Create Assignment' }}</h1>
      </div>
      <div class="header-actions">
        <button class="btn-text" @click="saveDraft" :disabled="saving">Save Draft</button>
        <button class="btn-primary" @click="saveAndPublish" :disabled="saving || !isValid">
          {{ saving ? 'Saving...' : 'Publish' }}
        </button>
      </div>
    </header>

    <!-- Main Form -->
    <main class="page-content">
      <div class="form-container">
        <!-- Title & Instructions -->
        <div class="form-section">
          <div class="form-group">
            <label>Title *</label>
            <input 
              v-model="form.title" 
              type="text" 
              placeholder="Assignment title"
              class="large-input"
            />
          </div>
          
          <div class="form-group">
            <label>Instructions *</label>
            <textarea 
              v-model="form.instructions" 
              placeholder="Provide detailed instructions for students..."
              rows="6"
            ></textarea>
          </div>
        </div>

        <!-- Points & Due Date -->
        <div class="form-section">
          <h3>Assignment Details</h3>
          <div class="form-row">
            <div class="form-group">
              <label>Points *</label>
              <input v-model.number="form.points" type="number" min="1" max="1000" />
            </div>
            <div class="form-group">
              <label>Due Date *</label>
              <input v-model="form.dueDate" type="datetime-local" />
            </div>
          </div>
        </div>

        <!-- Integrity Tools -->
        <div class="form-section">
          <h3>Integrity Tools</h3>
          <p class="section-desc">Select which academic integrity tools are active for this assignment</p>

          <div class="integrity-tools-list">
            <label class="tool-card" :class="{ active: form.settings.analyze_integrity_enabled }">
              <div class="tool-toggle">
                <input type="checkbox" v-model="form.settings.analyze_integrity_enabled" />
              </div>
              <div class="tool-icon" style="background: #e8f0fe; color: #1a73e8;">
                <svg width="22" height="22" viewBox="0 0 24 24" fill="currentColor"><path d="M3 17.25V21h3.75L17.81 9.94l-3.75-3.75L3 17.25zM20.71 7.04c.39-.39.39-1.02 0-1.41l-2.34-2.34c-.39-.39-1.02-.39-1.41 0l-1.83 1.83 3.75 3.75 1.83-1.83z"/></svg>
              </div>
              <div class="tool-info">
                <span class="tool-name">Content Authenticity</span>
                <span class="tool-desc">Tracks real-time typing vs copy-paste behavior, detects external and internal content sources</span>
              </div>
            </label>

            <label class="tool-card" :class="{ active: form.settings.gptzero_enabled }">
              <div class="tool-toggle">
                <input type="checkbox" v-model="form.settings.gptzero_enabled" />
              </div>
              <div class="tool-icon" style="background: #fef7e0; color: #f9ab00;">
                <svg width="22" height="22" viewBox="0 0 24 24" fill="currentColor"><path d="M21 11c0 5.55-3.84 10.74-9 12-5.16-1.26-9-6.45-9-12V5l9-4 9 4v6zm-9 10c3.75-1 7-5.46 7-9.78V6.3l-7-3.12L5 6.3v4.92C5 15.54 8.25 20 12 21z"/></svg>
              </div>
              <div class="tool-info">
                <span class="tool-name">True AI Detector</span>
                <span class="tool-desc">Detects AI-generated content with 98-99% accuracy on non-contaminated text</span>
              </div>
            </label>

            <label class="tool-card" :class="{ active: form.settings.stylometry_enabled }">
              <div class="tool-toggle">
                <input type="checkbox" v-model="form.settings.stylometry_enabled" />
              </div>
              <div class="tool-icon" style="background: #e6f4ea; color: #1e8e3e;">
                <svg width="22" height="22" viewBox="0 0 24 24" fill="currentColor"><path d="M12 11c1.33 0 4 .67 4 2v1H8v-1c0-1.33 2.67-2 4-2zm0-1c-1.1 0-2-.9-2-2s.9-2 2-2 2 .9 2 2-.9 2-2 2zm6-8H6c-1.1 0-2 .9-2 2v16l4-4h10c1.1 0 2-.9 2-2V4c0-1.1-.9-2-2-2z"/></svg>
              </div>
              <div class="tool-info">
                <span class="tool-name">Authorship Verification (Stylometry)</span>
                <span class="tool-desc">Forensic writing style analysis — compares submission against student's enrolled writing profile</span>
              </div>
            </label>

            <label class="tool-card" :class="{ active: form.settings.face_verification_enabled }">
              <div class="tool-toggle">
                <input type="checkbox" v-model="form.settings.face_verification_enabled" />
              </div>
              <div class="tool-icon" style="background: #fce8e6; color: #c5221f;">
                <svg width="22" height="22" viewBox="0 0 24 24" fill="currentColor"><path d="M9 11.75c-.69 0-1.25.56-1.25 1.25s.56 1.25 1.25 1.25 1.25-.56 1.25-1.25-.56-1.25-1.25-1.25zm6 0c-.69 0-1.25.56-1.25 1.25s.56 1.25 1.25 1.25 1.25-.56 1.25-1.25-.56-1.25-1.25-1.25zM12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm0 18c-4.41 0-8-3.59-8-8 0-.29.02-.58.05-.86 2.36-1.05 4.23-2.98 5.21-5.37C11.07 8.33 14.05 10 17.42 10c.78 0 1.53-.09 2.25-.26.21.71.33 1.47.33 2.26 0 4.41-3.59 8-8 8z"/></svg>
              </div>
              <div class="tool-info">
                <span class="tool-name">Face Verification</span>
                <span class="tool-desc">Periodic webcam identity checks to verify the enrolled student is present</span>
              </div>
            </label>

            <label class="tool-card" :class="{ active: form.settings.check_plagiarism }">
              <div class="tool-toggle">
                <input type="checkbox" v-model="form.settings.check_plagiarism" />
              </div>
              <div class="tool-icon" style="background: #f3e8fd; color: #7b1fa2;">
                <svg width="22" height="22" viewBox="0 0 24 24" fill="currentColor"><path d="M15.5 14h-.79l-.28-.27C15.41 12.59 16 11.11 16 9.5 16 5.91 13.09 3 9.5 3S3 5.91 3 9.5 5.91 16 9.5 16c1.61 0 3.09-.59 4.23-1.57l.27.28v.79l5 4.99L20.49 19l-4.99-5zm-6 0C7.01 14 5 11.99 5 9.5S7.01 5 9.5 5 14 7.01 14 9.5 11.99 14 9.5 14z"/></svg>
              </div>
              <div class="tool-info">
                <span class="tool-name">Plagiarism Database</span>
                <span class="tool-desc">Cross-references against internal peer submissions, 240M+ scholarly works, and web sources</span>
              </div>
            </label>
          </div>

          <!-- Conditional configs for enabled tools -->
          <div class="tool-configs" v-if="form.settings.face_verification_enabled">
            <div class="form-group">
              <label>Face Check Interval (minutes)</label>
              <input
                v-model.number="faceIntervalMinutes"
                type="number"
                min="5"
                max="30"
              />
            </div>
          </div>

          <div class="tool-configs">
            <div class="form-group">
              <label>Minimum Typing Trust Score (%)</label>
              <input
                v-model.number="form.settings.minimum_trust_score"
                type="number"
                min="0"
                max="100"
              />
            </div>
          </div>
        </div>

        <!-- Additional Settings -->
        <div class="form-section">
          <h3>Additional Settings</h3>
          <div class="settings-grid">
            <label class="setting-item">
              <div class="setting-info">
                <span class="setting-name">Auto-Grading</span>
                <span class="setting-desc">Use AI to suggest grades based on rubric</span>
              </div>
              <input type="checkbox" v-model="form.settings.auto_grade_enabled" />
            </label>
          </div>
        </div>

        <!-- Submission Settings -->
        <div class="form-section">
          <h3>Submission Settings</h3>
          
          <label class="setting-item">
            <div class="setting-info">
              <span class="setting-name">Allow Late Submissions</span>
              <span class="setting-desc">Students can submit after the due date</span>
            </div>
            <input type="checkbox" v-model="form.settings.allow_late" />
          </label>
          
          <div class="form-group" v-if="form.settings.allow_late">
            <label>Late Penalty (% per day)</label>
            <input 
              v-model.number="form.settings.late_penalty_percent" 
              type="number" 
              min="0" 
              max="100"
            />
          </div>
        </div>

        <!-- Rubric -->
        <div class="form-section">
          <div class="section-header">
            <div>
              <h3>Grading Rubric</h3>
              <p class="section-desc">Define criteria for consistent grading and auto-grading</p>
            </div>
            <button v-if="rubricMode === 'manual'" class="btn-secondary" @click="addCriterion">
              <svg width="20" height="20" viewBox="0 0 24 24" fill="currentColor">
                <path d="M19 13h-6v6h-2v-6H5v-2h6V5h2v6h6v2z"/>
              </svg>
              Add Criterion
            </button>
          </div>

          <!-- Rubric Mode Tabs -->
          <div class="rubric-mode-tabs">
            <button 
              :class="['mode-tab', { active: rubricMode === 'manual' }]"
              @click="rubricMode = 'manual'"
            >
              <svg width="16" height="16" viewBox="0 0 24 24" fill="currentColor">
                <path d="M3 17.25V21h3.75L17.81 9.94l-3.75-3.75L3 17.25zM20.71 7.04c.39-.39.39-1.02 0-1.41l-2.34-2.34c-.39-.39-1.02-.39-1.41 0l-1.83 1.83 3.75 3.75 1.83-1.83z"/>
              </svg>
              Manual
            </button>
            <button 
              :class="['mode-tab', { active: rubricMode === 'text' }]"
              @click="rubricMode = 'text'"
            >
              <svg width="16" height="16" viewBox="0 0 24 24" fill="currentColor">
                <path d="M14 2H6c-1.1 0-1.99.9-1.99 2L4 20c0 1.1.89 2 1.99 2H18c1.1 0 2-.9 2-2V8l-6-6zm2 16H8v-2h8v2zm0-4H8v-2h8v2zM13 9V3.5L18.5 9H13z"/>
              </svg>
              Type / Paste
            </button>
            <button 
              :class="['mode-tab', { active: rubricMode === 'upload' }]"
              @click="rubricMode = 'upload'"
            >
              <svg width="16" height="16" viewBox="0 0 24 24" fill="currentColor">
                <path d="M9 16h6v-6h4l-7-7-7 7h4zm-4 2h14v2H5z"/>
              </svg>
              Upload File
            </button>
          </div>

          <!-- Manual Mode -->
          <div v-if="rubricMode === 'manual'">
            <div v-if="form.rubric.length > 0" class="rubric-list">
              <div v-for="(criterion, idx) in form.rubric" :key="idx" class="criterion-card">
                <div class="criterion-header">
                  <input 
                    v-model="criterion.name" 
                    placeholder="Criterion name (e.g., Thesis Statement)"
                    class="criterion-name"
                  />
                  <input 
                    v-model.number="criterion.points" 
                    type="number" 
                    placeholder="Pts"
                    class="criterion-points"
                    min="1"
                  />
                  <button class="remove-btn" @click="removeCriterion(idx)">
                    <svg width="20" height="20" viewBox="0 0 24 24" fill="currentColor">
                      <path d="M6 19c0 1.1.9 2 2 2h8c1.1 0 2-.9 2-2V7H6v12zM19 4h-3.5l-1-1h-5l-1 1H5v2h14V4z"/>
                    </svg>
                  </button>
                </div>
                
                <textarea 
                  v-model="criterion.description" 
                  placeholder="Describe what this criterion evaluates..."
                  rows="2"
                  class="criterion-desc"
                ></textarea>
                
                <div class="levels-section">
                  <span class="levels-label">Scoring Levels:</span>
                  <div class="levels-list">
                    <div v-for="(level, lidx) in criterion.levels" :key="lidx" class="level-item">
                      <input v-model="level.name" placeholder="Level name" class="level-name" />
                      <input v-model.number="level.points" type="number" placeholder="Pts" class="level-points" />
                      <textarea 
                        v-model="level.description" 
                        placeholder="Description" 
                        class="level-desc"
                        rows="2"
                      ></textarea>
                      <button v-if="criterion.levels.length > 2" class="remove-level" @click="removeLevel(idx, lidx)">×</button>
                    </div>
                  </div>
                  <button class="add-level-btn" @click="addLevel(idx)">+ Add Level</button>
                </div>
              </div>
            </div>
            
            <div v-else class="empty-rubric">
              <p>No rubric criteria defined. Add criteria for consistent grading.</p>
            </div>
          </div>

          <!-- Text / Paste Mode -->
          <div v-if="rubricMode === 'text'" class="rubric-text-mode">
            <div class="text-format-help">
              <strong>Format: one criterion per line</strong>
              <code>Criterion Name | Points | Description</code>
              <span class="format-example">Example:</span>
              <pre>Thesis Statement | 20 | Clear and well-defined thesis
Evidence & Analysis | 30 | Strong supporting evidence with analysis
Organization | 25 | Logical structure and flow
Grammar & Style | 25 | Correct grammar, spelling, punctuation</pre>
            </div>
            <textarea 
              v-model="rubricText" 
              placeholder="Paste or type your rubric here using the format above..."
              rows="10"
              class="rubric-textarea"
            ></textarea>
            <div class="text-actions">
              <button class="btn-secondary" @click="parseRubricText">
                <svg width="16" height="16" viewBox="0 0 24 24" fill="currentColor">
                  <path d="M9 16.17L4.83 12l-1.42 1.41L9 19 21 7l-1.41-1.41z"/>
                </svg>
                Parse &amp; Apply Rubric
              </button>
              <span v-if="rubricParseMessage" :class="['parse-message', rubricParseSuccess ? 'success' : 'error']">
                {{ rubricParseMessage }}
              </span>
            </div>
          </div>

          <!-- Upload Mode -->
          <div v-if="rubricMode === 'upload'" class="rubric-upload-mode">
            <div class="upload-area" 
              @dragover.prevent="dragOver = true" 
              @dragleave="dragOver = false"
              @drop.prevent="handleFileDrop"
              :class="{ 'drag-over': dragOver }"
            >
              <svg width="48" height="48" viewBox="0 0 24 24" fill="#5f6368">
                <path d="M9 16h6v-6h4l-7-7-7 7h4zm-4 2h14v2H5z"/>
              </svg>
              <p>Drag & drop a file here, or click to browse</p>
              <span class="upload-formats">Supported: CSV, JSON, or TXT</span>
              <input 
                type="file" 
                ref="fileInput"
                accept=".csv,.json,.txt"
                @change="handleFileUpload"
                class="file-input"
              />
              <button class="btn-secondary upload-btn" @click="fileInput?.click()">
                Choose File
              </button>
            </div>
            <div class="upload-format-help">
              <strong>Accepted formats:</strong>
              <ul>
                <li><strong>CSV:</strong> columns: name, points, description (header row optional)</li>
                <li><strong>JSON:</strong> array of objects with name, points, description fields</li>
                <li><strong>TXT:</strong> one criterion per line: Name | Points | Description</li>
              </ul>
            </div>
            <span v-if="rubricParseMessage" :class="['parse-message', rubricParseSuccess ? 'success' : 'error']">
              {{ rubricParseMessage }}
            </span>
          </div>
          
          <div v-if="form.rubric.length > 0" class="rubric-total">
            <span>Total Rubric Points: {{ rubricTotal }}</span>
            <span v-if="rubricTotal !== form.points" class="mismatch-warning">
              Should match assignment points ({{ form.points }})
            </span>
          </div>
        </div>
      </div>
    </main>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, watch } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { useAssignments } from '@/composables/classroom'

const props = defineProps(['classId', 'assignmentId', 'isEdit'])
const router = useRouter()
const route = useRoute()
const { createAssignment, updateAssignment, fetchAssignment, currentAssignment, publishAssignment } = useAssignments()

const saving = ref(false)
const rubricMode = ref('manual')
const rubricText = ref('')
const rubricParseMessage = ref('')
const rubricParseSuccess = ref(false)
const dragOver = ref(false)
const fileInput = ref(null)

const form = ref({
  title: '',
  instructions: '',
  points: 100,
  dueDate: '',
  settings: {
    analyze_integrity_enabled: true,
    gptzero_enabled: true,
    stylometry_enabled: true,
    face_verification_enabled: true,
    check_plagiarism: true,
    face_check_interval: 600000,
    face_max_warnings: 3,
    strict_mode: false,
    minimum_trust_score: 60,
    allow_late: true,
    late_penalty_percent: 10,
    max_attempts: 1,
    plagiarism_threshold: 40,
    auto_grade_enabled: false
  },
  rubric: []
})

const faceIntervalMinutes = computed({
  get: () => form.value.settings.face_check_interval / 60000,
  set: (val) => { form.value.settings.face_check_interval = val * 60000 }
})

const rubricTotal = computed(() => {
  return form.value.rubric.reduce((sum, c) => sum + (c.points || 0), 0)
})

const isValid = computed(() => {
  return form.value.title.trim() && 
         form.value.instructions.trim() && 
         form.value.points > 0 && 
         form.value.dueDate
})

function addCriterion() {
  form.value.rubric.push({
    criteria_id: crypto.randomUUID(),
    name: '',
    description: '',
    points: 20,
    levels: [
      { name: 'Excellent', points: 20, description: 'Exceeds expectations' },
      { name: 'Good', points: 15, description: 'Meets expectations' },
      { name: 'Satisfactory', points: 10, description: 'Partially meets expectations' },
      { name: 'Needs Improvement', points: 5, description: 'Below expectations' }
    ]
  })
}

function removeCriterion(idx) {
  form.value.rubric.splice(idx, 1)
}

function addLevel(criterionIdx) {
  form.value.rubric[criterionIdx].levels.push({
    name: 'New Level',
    points: 0,
    description: 'Description'
  })
}

function removeLevel(criterionIdx, levelIdx) {
  form.value.rubric[criterionIdx].levels.splice(levelIdx, 1)
}

// ---- Rubric Text Parsing ----
function parseRubricText() {
  rubricParseMessage.value = ''
  rubricParseSuccess.value = false
  
  const text = rubricText.value.trim()
  if (!text) {
    rubricParseMessage.value = 'Please enter rubric text first'
    return
  }
  
  const parsed = parseTextToRubric(text)
  if (parsed.length === 0) {
    rubricParseMessage.value = 'Could not parse any criteria. Use format: Name | Points | Description'
    return
  }
  
  form.value.rubric = parsed
  rubricMode.value = 'manual'
  rubricParseMessage.value = `Successfully parsed ${parsed.length} criteria`
  rubricParseSuccess.value = true
}

function parseTextToRubric(text) {
  const lines = text.split('\n').map(l => l.trim()).filter(l => l.length > 0)
  const criteria = []
  
  for (const line of lines) {
    // Skip header-like lines
    if (line.toLowerCase().startsWith('name') && line.toLowerCase().includes('point')) continue
    if (line.startsWith('#') || line.startsWith('//')) continue
    
    const parts = line.split('|').map(p => p.trim())
    
    if (parts.length >= 2) {
      const name = parts[0]
      const points = parseInt(parts[1]) || 20
      const description = parts.length >= 3 ? parts[2] : ''
      
      if (name) {
        criteria.push(buildCriterion(name, points, description))
      }
    } else {
      // Try comma-separated
      const commaParts = line.split(',').map(p => p.trim())
      if (commaParts.length >= 2) {
        const name = commaParts[0]
        const points = parseInt(commaParts[1]) || 20
        const description = commaParts.length >= 3 ? commaParts[2] : ''
        if (name && !isNaN(parseInt(commaParts[1]))) {
          criteria.push(buildCriterion(name, points, description))
          continue
        }
      }
      // Single line - treat as criterion name with default points
      if (line.length > 0) {
        criteria.push(buildCriterion(line, 20, ''))
      }
    }
  }
  
  return criteria
}

function buildCriterion(name, points, description) {
  return {
    criteria_id: crypto.randomUUID(),
    name: name || 'Unnamed Criterion',
    description: description || 'No description provided',
    points,
    levels: [
      { name: 'Excellent', points: points, description: 'Exceeds expectations' },
      { name: 'Good', points: Math.round(points * 0.75), description: 'Meets expectations' },
      { name: 'Satisfactory', points: Math.round(points * 0.5), description: 'Partially meets expectations' },
      { name: 'Needs Improvement', points: Math.round(points * 0.25), description: 'Below expectations' }
    ]
  }
}

// ---- Rubric File Upload ----
function handleFileDrop(event) {
  dragOver.value = false
  const file = event.dataTransfer.files[0]
  if (file) processRubricFile(file)
}

function handleFileUpload(event) {
  const file = event.target.files[0]
  if (file) processRubricFile(file)
}

function processRubricFile(file) {
  rubricParseMessage.value = ''
  rubricParseSuccess.value = false
  
  const reader = new FileReader()
  reader.onload = (e) => {
    const content = e.target.result
    const ext = file.name.split('.').pop().toLowerCase()
    
    try {
      let parsed = []
      
      if (ext === 'json') {
        parsed = parseJsonRubric(content)
      } else if (ext === 'csv') {
        parsed = parseCsvRubric(content)
      } else {
        // txt or other - use text parser
        parsed = parseTextToRubric(content)
      }
      
      if (parsed.length === 0) {
        rubricParseMessage.value = 'No criteria found in the file. Check the format.'
        return
      }
      
      form.value.rubric = parsed
      rubricMode.value = 'manual'
      rubricParseMessage.value = `Successfully imported ${parsed.length} criteria from ${file.name}`
      rubricParseSuccess.value = true
    } catch (err) {
      rubricParseMessage.value = `Error parsing file: ${err.message}`
    }
  }
  reader.readAsText(file)
}

function parseJsonRubric(content) {
  const data = JSON.parse(content)
  const items = Array.isArray(data) ? data : (data.rubric || data.criteria || [])
  
  return items.map(item => buildCriterion(
    item.name || item.criterion || item.title || 'Unnamed',
    parseInt(item.points || item.max_points || item.score) || 20,
    item.description || item.desc || ''
  ))
}

function parseCsvRubric(content) {
  const lines = content.split('\n').map(l => l.trim()).filter(l => l.length > 0)
  if (lines.length === 0) return []
  
  // Check if first line is a header
  const firstLine = lines[0].toLowerCase()
  const startIdx = (firstLine.includes('name') || firstLine.includes('criterion') || firstLine.includes('criteria')) ? 1 : 0
  
  const criteria = []
  for (let i = startIdx; i < lines.length; i++) {
    // Handle quoted CSV fields
    const parts = lines[i].match(/(".*?"|[^",\s]+)(?=\s*,|\s*$)/g) || lines[i].split(',')
    const cleaned = parts.map(p => p.replace(/^"|"$/g, '').trim())
    
    if (cleaned.length >= 2) {
      const name = cleaned[0]
      const points = parseInt(cleaned[1]) || 20
      const description = cleaned.length >= 3 ? cleaned[2] : ''
      if (name) {
        criteria.push(buildCriterion(name, points, description))
      }
    }
  }
  
  return criteria
}

function goBack() {
  if (props.classId) {
    router.push(`/teacher/class/${props.classId}`)
  } else {
    router.back()
  }
}

async function saveDraft() {
  if (!form.value.title.trim()) {
    alert('Please enter a title')
    return
  }
  
  saving.value = true
  const data = prepareData()
  
  let result
  if (props.isEdit && props.assignmentId) {
    result = await updateAssignment(props.assignmentId, data)
  } else {
    data.class_id = props.classId
    result = await createAssignment(data)
  }
  
  saving.value = false
  
  if (result.success) {
    alert('Draft saved!')
    if (!props.isEdit) {
      router.push(`/teacher/assignment/${result.data.assignment_id}`)
    }
  } else {
    alert(result.error)
  }
}

async function saveAndPublish() {
  if (!isValid.value) {
    alert('Please fill in all required fields')
    return
  }
  
  saving.value = true
  const data = prepareData()
  
  let result
  if (props.isEdit && props.assignmentId) {
    result = await updateAssignment(props.assignmentId, data)
  } else {
    data.class_id = props.classId
    result = await createAssignment(data)
  }
  
  if (result.success) {
    // Publish
    const pubResult = await publishAssignment(result.data.assignment_id)
    if (!pubResult.success) {
      alert('Assignment saved but failed to publish: ' + (pubResult.error || 'Unknown error'))
    }
    router.push(`/teacher/assignment/${result.data.assignment_id}`)
  } else {
    alert('Failed to save assignment: ' + (result.error || 'Unknown error'))
  }
  
  saving.value = false
}

function prepareData() {
  // Clean up rubric data - ensure all required fields have values
  let rubric = null
  if (form.value.rubric.length > 0) {
    rubric = form.value.rubric.map(criterion => ({
      ...criterion,
      name: criterion.name.trim() || 'Unnamed Criterion',
      description: criterion.description.trim() || 'No description provided',
      levels: criterion.levels.map(level => ({
        ...level,
        name: level.name.trim() || 'Unnamed Level',
        description: level.description.trim() || 'No description provided'
      }))
    }))
  }
  
  return {
    title: form.value.title,
    instructions: form.value.instructions,
    points: form.value.points,
    due_date: new Date(form.value.dueDate).toISOString(),
    settings: form.value.settings,
    rubric
  }
}

onMounted(async () => {
  // Set default due date to 1 week from now
  const defaultDue = new Date()
  defaultDue.setDate(defaultDue.getDate() + 7)
  defaultDue.setHours(23, 59, 0, 0)
  form.value.dueDate = defaultDue.toISOString().slice(0, 16)
  
  // If editing, load existing data
  if (props.isEdit && props.assignmentId) {
    await fetchAssignment(props.assignmentId)
    if (currentAssignment.value) {
      form.value = {
        title: currentAssignment.value.title,
        instructions: currentAssignment.value.instructions,
        points: currentAssignment.value.points,
        dueDate: new Date(currentAssignment.value.due_date).toISOString().slice(0, 16),
        settings: currentAssignment.value.settings,
        rubric: currentAssignment.value.rubric || []
      }
    }
  }
})
</script>

<style scoped>
.create-assignment-page {
  min-height: 100vh;
  background: #f8f9fa;
}

.page-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 12px 24px;
  background: white;
  border-bottom: 1px solid #e0e0e0;
  position: sticky;
  top: 0;
  z-index: 100;
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

.page-header h1 {
  font-size: 18px;
  font-weight: 500;
  margin: 0;
  color: #202124;
}

.header-actions {
  display: flex;
  gap: 12px;
}

.btn-text {
  padding: 10px 20px;
  border: none;
  background: transparent;
  color: #1a73e8;
  font-weight: 500;
  cursor: pointer;
  border-radius: 8px;
}

.btn-text:hover:not(:disabled) {
  background: rgba(26, 115, 232, 0.04);
}

.btn-primary {
  padding: 10px 24px;
  border: none;
  background: #1a73e8;
  color: white;
  font-weight: 500;
  border-radius: 8px;
  cursor: pointer;
}

.btn-primary:hover:not(:disabled) {
  background: #1557b0;
}

.btn-primary:disabled,
.btn-text:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.page-content {
  max-width: 900px;
  margin: 0 auto;
  padding: 24px;
}

.form-container {
  display: flex;
  flex-direction: column;
  gap: 24px;
}

.form-section {
  background: white;
  border-radius: 12px;
  padding: 24px;
}

.form-section h3 {
  font-size: 18px;
  font-weight: 500;
  margin: 0 0 8px;
  color: #202124;
}

.section-desc {
  font-size: 14px;
  color: #5f6368;
  margin: 0 0 20px;
}

.section-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  margin-bottom: 20px;
}

.form-group {
  margin-bottom: 20px;
}

.form-group:last-child {
  margin-bottom: 0;
}

.form-group label {
  display: block;
  font-size: 14px;
  font-weight: 500;
  color: #202124;
  margin-bottom: 8px;
}

.form-group input,
.form-group textarea {
  width: 100%;
  padding: 12px;
  border: 1px solid #dadce0;
  border-radius: 8px;
  font-size: 14px;
  box-sizing: border-box;
  transition: border-color 0.2s;
  color: #202124;
  background: white;
}

.form-group input:focus,
.form-group textarea:focus {
  outline: none;
  border-color: #1a73e8;
}

.large-input {
  font-size: 18px !important;
  padding: 16px !important;
}

.form-row {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 20px;
}

/* Integrity Tools */
.integrity-tools-list {
  display: flex;
  flex-direction: column;
  gap: 12px;
  margin-bottom: 20px;
}

.tool-card {
  display: flex;
  align-items: center;
  gap: 16px;
  padding: 16px 20px;
  background: #f8f9fa;
  border: 2px solid #e0e0e0;
  border-radius: 12px;
  cursor: pointer;
  transition: all 0.2s;
}

.tool-card:hover {
  background: #f1f3f4;
  border-color: #dadce0;
}

.tool-card.active {
  background: #f8fbff;
  border-color: #1a73e8;
}

.tool-toggle input[type="checkbox"] {
  width: 20px;
  height: 20px;
  cursor: pointer;
  accent-color: #1a73e8;
  flex-shrink: 0;
}

.tool-icon {
  width: 44px;
  height: 44px;
  border-radius: 10px;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}

.tool-info {
  display: flex;
  flex-direction: column;
  gap: 4px;
  min-width: 0;
}

.tool-name {
  font-weight: 600;
  font-size: 15px;
  color: #202124;
}

.tool-desc {
  font-size: 13px;
  color: #5f6368;
  line-height: 1.4;
}

.tool-configs {
  margin-bottom: 8px;
}

/* Settings */
.settings-grid {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 16px;
  margin-bottom: 20px;
}

.setting-item {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 16px;
  background: #f8f9fa;
  border-radius: 8px;
  cursor: pointer;
}

.setting-info {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.setting-name {
  font-weight: 500;
  color: #202124;
}

.setting-desc {
  font-size: 12px;
  color: #5f6368;
}

.setting-item input[type="checkbox"] {
  width: 20px;
  height: 20px;
  cursor: pointer;
}

/* Rubric */
.btn-secondary {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 10px 20px;
  border: 1px solid #dadce0;
  background: white;
  border-radius: 8px;
  font-weight: 500;
  color: #1a73e8;
  cursor: pointer;
}

.btn-secondary:hover {
  background: #f8f9fa;
}

.rubric-list {
  display: flex;
  flex-direction: column;
  gap: 16px;
  max-height: 70vh;
  overflow-y: auto;
  padding-right: 4px;
}

.criterion-card {
  border: 1px solid #e0e0e0;
  border-radius: 8px;
  padding: 16px;
  flex-shrink: 0;
}

.criterion-header {
  display: flex;
  gap: 12px;
  margin-bottom: 12px;
}

.criterion-name {
  flex: 1;
  font-weight: 500;
}

.criterion-points {
  width: 80px;
  text-align: center;
}

.criterion-desc {
  width: 100%;
  margin-bottom: 12px;
}

.remove-btn {
  width: 36px;
  height: 36px;
  border: none;
  background: transparent;
  border-radius: 50%;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  color: #5f6368;
}

.remove-btn:hover {
  background: #fce8e6;
  color: #c5221f;
}

.levels-section {
  background: #f8f9fa;
  border-radius: 8px;
  padding: 12px;
  max-height: 320px;
  overflow-y: auto;
}

.levels-label {
  font-size: 13px;
  font-weight: 500;
  color: #5f6368;
  display: block;
  margin-bottom: 8px;
}

.levels-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.level-item {
  display: flex;
  gap: 8px;
  align-items: flex-start;
}

.level-name {
  width: 120px;
  flex-shrink: 0;
}

.level-points {
  width: 60px;
  text-align: center;
  flex-shrink: 0;
}

.level-desc {
  flex: 1;
  min-width: 0;
  resize: vertical;
  font-family: inherit;
  line-height: 1.4;
}

.level-item input,
.level-item textarea {
  padding: 8px;
  border: 1px solid #dadce0;
  border-radius: 4px;
  font-size: 13px;
  box-sizing: border-box;
  color: #202124;
  background: white;
}

.remove-level {
  width: 24px;
  height: 24px;
  border: none;
  background: transparent;
  cursor: pointer;
  color: #5f6368;
  font-size: 18px;
}

.add-level-btn {
  margin-top: 8px;
  padding: 6px 12px;
  border: none;
  background: transparent;
  color: #1a73e8;
  font-size: 13px;
  cursor: pointer;
}

.empty-rubric {
  text-align: center;
  padding: 40px;
  color: #5f6368;
  background: #f8f9fa;
  border-radius: 8px;
}

.rubric-total {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-top: 16px;
  padding: 12px 16px;
  background: #e8f0fe;
  border-radius: 8px;
  font-weight: 500;
  color: #1a73e8;
}

.mismatch-warning {
  color: #f9ab00;
}

/* Rubric Mode Tabs */
.rubric-mode-tabs {
  display: flex;
  gap: 4px;
  margin-bottom: 20px;
  background: #f1f3f4;
  border-radius: 8px;
  padding: 4px;
}

.mode-tab {
  flex: 1;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 6px;
  padding: 10px 16px;
  border: none;
  background: transparent;
  border-radius: 6px;
  font-size: 13px;
  font-weight: 500;
  color: #5f6368;
  cursor: pointer;
  transition: all 0.2s;
}

.mode-tab:hover:not(.active) {
  background: rgba(0, 0, 0, 0.04);
}

.mode-tab.active {
  background: white;
  color: #1a73e8;
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.1);
}

/* Text Mode */
.rubric-text-mode {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.text-format-help {
  background: #f8f9fa;
  border: 1px solid #e0e0e0;
  border-radius: 8px;
  padding: 16px;
  font-size: 13px;
  color: #5f6368;
}

.text-format-help strong {
  display: block;
  color: #202124;
  margin-bottom: 4px;
}

.text-format-help code {
  display: inline-block;
  background: #e8eaed;
  padding: 2px 8px;
  border-radius: 4px;
  font-size: 13px;
  color: #202124;
  margin: 4px 0;
}

.text-format-help .format-example {
  display: block;
  margin-top: 8px;
  font-size: 12px;
  color: #5f6368;
}

.text-format-help pre {
  background: #202124;
  color: #e8eaed;
  padding: 12px;
  border-radius: 6px;
  font-size: 12px;
  margin: 8px 0 0;
  white-space: pre-wrap;
  overflow-x: auto;
}

.rubric-textarea {
  width: 100%;
  padding: 16px;
  border: 2px solid #dadce0;
  border-radius: 8px;
  font-size: 14px;
  font-family: 'Roboto Mono', monospace;
  line-height: 1.6;
  box-sizing: border-box;
  resize: vertical;
  transition: border-color 0.2s;
}

.rubric-textarea:focus {
  outline: none;
  border-color: #1a73e8;
}

.text-actions {
  display: flex;
  align-items: center;
  gap: 16px;
}

.parse-message {
  font-size: 13px;
  font-weight: 500;
}

.parse-message.success {
  color: #1e8e3e;
}

.parse-message.error {
  color: #d93025;
}

/* Upload Mode */
.rubric-upload-mode {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.upload-area {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 12px;
  padding: 40px 20px;
  border: 2px dashed #dadce0;
  border-radius: 12px;
  background: #fafafa;
  text-align: center;
  transition: all 0.2s;
  position: relative;
}

.upload-area.drag-over {
  border-color: #1a73e8;
  background: #e8f0fe;
}

.upload-area p {
  margin: 0;
  color: #5f6368;
  font-size: 14px;
}

.upload-formats {
  font-size: 12px;
  color: #80868b;
}

.file-input {
  position: absolute;
  width: 0;
  height: 0;
  opacity: 0;
}

.upload-btn {
  margin-top: 4px;
}

.upload-format-help {
  background: #f8f9fa;
  border-radius: 8px;
  padding: 16px;
  font-size: 13px;
  color: #5f6368;
}

.upload-format-help strong {
  display: block;
  color: #202124;
  margin-bottom: 8px;
}

.upload-format-help ul {
  margin: 0;
  padding-left: 20px;
}

.upload-format-help li {
  margin-bottom: 6px;
}

.upload-format-help li:last-child {
  margin-bottom: 0;
}

@media (max-width: 768px) {
  .form-row,
  .settings-grid {
    grid-template-columns: 1fr;
  }
}
</style>
