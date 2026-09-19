<template>
  <aside class="sidebar right paper-outline-sidebar" :class="{ 'toc-hidden': tocHidden }">
    <div class="toc-tab-header">
      <span 
        class="toc-tab" 
        :class="{ 'active': activeRightTab === 'outline' }"
        @click="activeRightTab = 'outline'"
      >
        Paper Outline
      </span>
      <span 
        class="toc-tab" 
        :class="{ 'active': activeRightTab === 'plagChecker' }"
        @click="activeRightTab = 'plagChecker'"
      >
        Plag Checker
      </span>
      <span class="toc-tab-close" @click="toggleTocSidebar">✕</span>
    </div>

    <div class="toc-card-outer">
      <div class="toc-card-inner">
        <!-- Paper Outline Tab -->
        <div v-if="activeRightTab === 'outline'">
          <!-- Show Generated Paper if it exists -->
          <div v-if="generatedPaper" class="generated-paper-view">
            <div class="toc-header-with-copy">
              <div class="toc-title">Generated Paper</div>
              <button 
                class="copy-all-btn"
                @click="copyGeneratedPaper"
                title="Copy entire paper"
              >
                <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                  <rect width="14" height="14" x="8" y="8" rx="2" ry="2"/>
                  <path d="m4 16c-1.1 0-2-.9-2-2V4c0-1.1.9-2 2-2h10c1.1 0 2 .9 2 2"/>
                </svg>
                Copy All
              </button>
            </div>
            
            <div class="toc-content">
              <div v-if="isGeneratingPaper" class="loading">Generating full paper...</div>
              <div v-else class="generated-paper-content" v-html="generatedPaper"></div>
            </div>
            
            <!-- Back to Outline Button -->
            <div class="paper-actions">
              <button class="back-to-outline-btn" @click="clearGeneratedPaper">
                ← Back to Outline
              </button>
            </div>
          </div>
          
          <!-- Show Outline (default view) -->
          <div v-else>
            <div class="toc-header-with-copy">
              <div class="toc-title">Generated Outline</div>
              <button 
                v-if="outlineSections.length > 0" 
                class="copy-all-btn"
                @click="copyEntireOutline"
                :title="'Copy entire outline'"
              >
                <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                  <rect width="14" height="14" x="8" y="8" rx="2" ry="2"/>
                  <path d="m4 16c-1.1 0-2-.9-2-2V4c0-1.1.9-2 2-2h10c1.1 0 2 .9 2 2"/>
                </svg>
                Copy All
              </button>
            </div>
            
            <div class="toc-content">
              <!-- Show full paper generation banner regardless of whether paper is already displayed -->
              <div v-if="isGeneratingPaper" class="loading">Generating full paper...</div>
              <div v-if="isGenerating" class="loading">Generating outline...</div>
              
              <div v-else-if="outlineSections.length > 0" class="toc-sections">
                <div v-for="(section, idx) in outlineSections" :key="`section-${idx}`" class="toc-section">
                  <div class="toc-section-header" @click="toggleSection(idx)">
                    <span class="toc-section-title">{{ section.title }}</span>
                    <span class="toc-section-arrow" :class="{ expanded: section.expanded }">&#8250;</span>
                    <button 
                      class="toc-section-edit" 
                      @click.stop="toggleEditMode(idx)" 
                      :title="section.isEditing ? 'Save' : 'Edit section'"
                    >
                      <svg v-if="!section.isEditing" xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                        <path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7"/>
                        <path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z"/>
                      </svg>
                      <svg v-else xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                        <polyline points="20,6 9,17 4,12"/>
                      </svg>
                    </button>
                  </div>
                  
                  <div v-if="section.expanded" class="toc-section-content">
                    <div 
                      v-if="!section.isEditing"
                      v-html="section.content"
                      class="section-display"
                    ></div>
                    <textarea 
                      v-else
                      v-model="section.content"
                      class="section-editor"
                      @keydown.ctrl.enter="toggleEditMode(idx)"
                      @keydown.meta.enter="toggleEditMode(idx)"
                      rows="8"
                      placeholder="Enter section content..."
                    ></textarea>
                  </div>
                </div>
              </div>
              
              <div v-else class="outline-placeholder">
                No outline generated yet. Use the controls in the left sidebar to generate an outline.
              </div>
            </div>
          </div>

          <!-- Refine Outline Section -->
          <div v-if="outlineSections.length > 0" class="refine-section">
            <div class="refine-header">Refine Outline</div>
            <textarea 
              v-model="refineInstructions"
              class="refine-textarea"
              placeholder="How would you like to refine the outline?"
              rows="3"
            ></textarea>
            <div class="button-group">
              <button 
                class="refine-btn" 
                @click="refineOutline"
                :disabled="!refineInstructions.trim() || isRefining"
              >
                <span v-if="isRefining">Refining...</span>
                <span v-else>Refine Outline</span>
              </button>
              <button 
                class="generate-paper-btn" 
                @click="generateFullPaper"
                :disabled="isGeneratingPaper"
              >
                <span v-if="isGeneratingPaper" class="btn-loading">
                  <svg class="spinner" width="16" height="16" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
                    <circle cx="12" cy="12" r="10" stroke="currentColor" stroke-opacity="0.25" stroke-width="4" />
                    <path d="M22 12a10 10 0 0 1-10 10" stroke="currentColor" stroke-width="4" stroke-linecap="round"/>
                  </svg>
                  Generating Paper...
                </span>
                <span v-else>Generate Full Paper</span>
              </button>
            </div>
          </div>
        </div>

        <!-- Plagiarism Checker Tab -->
        <div v-if="activeRightTab === 'plagChecker'">
          <div class="toc-title">Plagiarism Checker</div>
          <div class="toc-content">
            <button 
              class="plag-checker-btn" 
              @click="checkPlagiarism"
              :disabled="isCheckingPlagiarism"
            >
              <span v-if="!isCheckingPlagiarism">Check for Plagiarism</span>
              <span v-else>Checking...</span>
            </button>
            
            <div v-if="plagiarismResult" class="plagiarism-result">
              <h4>Results:</h4>
              <div v-html="plagiarismResult"></div>
            </div>
            
            <div v-if="plagiarismError" class="plagiarism-error">
              {{ plagiarismError }}
            </div>
          </div>
        </div>
      </div>
    </div>
  </aside>
</template>

<script setup>
import { ref, watch } from 'vue'

// Props
const props = defineProps({
  tocHidden: {
    type: Boolean,
    default: false
  },
  outlineData: {
    type: String,
    default: ''
  },
  isGenerating: {
    type: Boolean,
    default: false
  },
  generatedPaper: {
    type: String,
    default: ''
  }
})

// Emits
const emit = defineEmits(['toggle-sidebar', 'refine-outline', 'generate-full-paper', 'clear-generated-paper'])

// Reactive data
const outlineSections = ref([])
const refineInstructions = ref('')
const isRefining = ref(false)

// Generate Full Paper state
const isGeneratingPaper = ref(false)

// Plagiarism Checker state
const activeRightTab = ref('outline')
const isCheckingPlagiarism = ref(false)
const plagiarismResult = ref(null)
const plagiarismError = ref(null)
// Methods
function toggleTocSidebar() {
  emit('toggle-sidebar')
}

function parseOutlineContent(htmlContent) {
  if (!htmlContent) {
    outlineSections.value = []
    return
  }

  console.log('Parsing HTML content:', htmlContent)

  // Split content by <h3> tags to get sections
  const sections = []
  
  // Use a more robust parsing approach
  const h3Regex = /<h3[^>]*>(.*?)<\/h3>/gi
  const parts = htmlContent.split(h3Regex)
  
  console.log('Split parts:', parts)
  
  // parts[0] would be content before first h3 (ignore)
  // parts[1] would be first h3 content, parts[2] would be content after first h3
  // parts[3] would be second h3 content, parts[4] would be content after second h3
  // etc.
  
  for (let i = 1; i < parts.length; i += 2) {
    const title = parts[i].trim()
    const content = parts[i + 1] ? parts[i + 1].trim() : ''
    
    if (title) {
      // Clean up the content - remove extra whitespace and format properly
      const cleanContent = content
        .replace(/\n\s*\n/g, '\n\n') // normalize line breaks
        .replace(/^\s+|\s+$/g, '') // trim
        .replace(/\n/g, '<br>') // convert newlines to br tags
      
      sections.push({
        title: title,
        content: cleanContent || 'No content available for this section.',
        isEditing: false,
        expanded: false
      })
      
      console.log(`Section: ${title}`)
      console.log(`Content: ${cleanContent}`)
    }
  }
  
  console.log('Parsed sections:', sections)
  outlineSections.value = sections
}

function ensureCompleteSentences(htmlContent) {
  if (!htmlContent.trim()) return htmlContent

  // Create a temporary div to work with the HTML
  const tempDiv = document.createElement('div')
  tempDiv.innerHTML = htmlContent

  // Get the text content to analyze sentences
  const textContent = tempDiv.textContent || tempDiv.innerText || ''

  // Find sentence boundaries (., !, ?) followed by space and capital letter or end of string
  const sentenceRegex = /[.!?](?:\s+[A-Z]|$)/g
  const sentences = []
  let lastIndex = 0
  let match

  while ((match = sentenceRegex.exec(textContent)) !== null) {
    const sentence = textContent.substring(lastIndex, match.index + 1).trim()
    if (sentence) {
      sentences.push(sentence)
    }
    lastIndex = match.index + 1
  }

  // Add any remaining text as incomplete sentence (to be excluded)
  const remainingText = textContent.substring(lastIndex).trim()

  if (sentences.length === 0) {
    // If no complete sentences found, return empty
    return ''
  }

  // Reconstruct HTML with only complete sentences
  const completeSentencesText = sentences.join(' ')

  // If the complete sentences text is significantly shorter than original,
  // it means we're cutting off incomplete sentences
  if (completeSentencesText.length < textContent.length * 0.8 && remainingText.length > 20) {
    // Try to preserve HTML structure while keeping only complete sentences
    return reconstructHtmlWithCompleteSentences(htmlContent, completeSentencesText)
  }

  return htmlContent // Return original if no major truncation needed
}

function reconstructHtmlWithCompleteSentences(originalHtml, completeSentencesText) {
  // Simple approach: if we have a significant truncation,
  // wrap the complete sentences in proper HTML tags
  const tempDiv = document.createElement('div')
  tempDiv.innerHTML = originalHtml

  // Get all paragraph tags and other block elements
  const paragraphs = tempDiv.querySelectorAll('p, div, span, strong, em, i, b')

  if (paragraphs.length > 0) {
    // Try to preserve the structure by checking each paragraph
    let result = ''
    let remainingText = completeSentencesText

    paragraphs.forEach(para => {
      const paraText = para.textContent || para.innerText || ''
      if (remainingText.includes(paraText.substring(0, 50))) {
        // This paragraph is likely included in our complete sentences
        if (remainingText.length >= paraText.length) {
          result += para.outerHTML
          remainingText = remainingText.substring(paraText.length).trim()
        }
      }
    })

    return result || `<p>${completeSentencesText}</p>`
  }

  return `<p>${completeSentencesText}</p>`
}

function toggleSection(index) {
  outlineSections.value[index].expanded = !outlineSections.value[index].expanded
}

function toggleEditMode(index) {
  const section = outlineSections.value[index]
  if (section.isEditing) {
    // Convert plain text back to HTML for display
    section.content = section.content.replace(/\n\n/g, '</p><p>').replace(/\n/g, '<br>')
    if (section.content && !section.content.startsWith('<p>')) {
      section.content = `<p>${section.content}</p>`
    }
  } else {
    // Convert HTML to plain text for editing
    const tempDiv = document.createElement('div')
    tempDiv.innerHTML = section.content
    section.content = tempDiv.textContent || tempDiv.innerText || ''
  }
  section.isEditing = !section.isEditing
}

function refineOutline() {
  if (!refineInstructions.value.trim()) return
  
  isRefining.value = true
  emit('refine-outline', refineInstructions.value.trim())
  refineInstructions.value = ''
}

async function generateFullPaper() {
  if (outlineSections.value.length === 0) return
  
  try {
    // Immediately reflect loading state on the button
    isGeneratingPaper.value = true
    
    // Get the outline content as a string
    let outlineContent = 'Generated Outline\n\n'
    outlineSections.value.forEach((section, index) => {
      outlineContent += `${index + 1}. ${section.title}\n`
      
      // Get plain text content from section
      const tempDiv = document.createElement('div')
      tempDiv.innerHTML = section.content
      const plainTextContent = tempDiv.textContent || tempDiv.innerText || ''
      
      if (plainTextContent.trim()) {
        outlineContent += `${plainTextContent.trim()}\n\n`
      }
    })
    
    // Let parent manage generating state via setGeneratingPaper(true/false)
    emit('generate-full-paper', outlineContent)
    
  } catch (error) {
    console.error('Error generating full paper:', error)
    alert('Failed to generate full paper. Please try again.')
  }
}

const getEditorContent = () => {
  return document.querySelector('.main-editor')?.innerText || ''
}

const callGPTZeroAPI = async (content) => {
  const formData = new FormData()
  formData.append('user_id', 'user1')
  formData.append('submission_type', 'text')
  formData.append('submitted_text', content)
  
  const response = await fetch('https://web-production-a65cb.up.railway.app/api/gptzero/submit', {
    method: 'POST',
    headers: { 'accept': 'application/json' },
    body: formData
  })
  
  if (!response.ok) throw new Error(`API error: ${response.status}`)
  return await response.json()
}

const formatGPTZeroResult = (result) => {
  const doc = result.documents[0]
  const percentage = (doc.completely_generated_prob * 100).toFixed(1)
  const confidence = doc.confidence_category
  
  let message = `
    <div class="result-item">
      <strong>AI Detection Result:</strong> ${doc.result_message}
    </div>
    <div class="result-item">
      <strong>AI Probability:</strong> ${percentage}%
    </div>
    <div class="result-item">
      <strong>Confidence:</strong> ${confidence}
    </div>
    <div class="result-item">
      <strong>Predicted Class:</strong> ${doc.predicted_class}
    </div>
  `
  
  return message
}

const copyEntireOutline = () => {
  if (outlineSections.value.length === 0) return
  
  let fullContent = 'Generated Outline\n\n'
  
  outlineSections.value.forEach((section, index) => {
    fullContent += `${index + 1}. ${section.title}\n`
    
    // Get plain text content from section
    const tempDiv = document.createElement('div')
    tempDiv.innerHTML = section.content
    const plainTextContent = tempDiv.textContent || tempDiv.innerText || ''
    
    if (plainTextContent.trim()) {
      fullContent += `${plainTextContent.trim()}\n\n`
    }
  })
  
  // Copy to clipboard
  navigator.clipboard.writeText(fullContent.trim()).then(() => {
    console.log('✅ Entire outline copied to clipboard')
    // You could add a toast notification here
  }).catch(err => {
    console.error('❌ Failed to copy outline:', err)
    // Fallback for older browsers
    const textArea = document.createElement('textarea')
    textArea.value = fullContent.trim()
    document.body.appendChild(textArea)
    textArea.select()
    document.execCommand('copy')
    document.body.removeChild(textArea)
  })
}

const copyGeneratedPaper = () => {
  if (!props.generatedPaper) return
  
  // Convert HTML to plain text
  const tempDiv = document.createElement('div')
  tempDiv.innerHTML = props.generatedPaper
  const plainTextContent = tempDiv.textContent || tempDiv.innerText || ''
  
  // Copy to clipboard
  navigator.clipboard.writeText(plainTextContent.trim()).then(() => {
    console.log('✅ Generated paper copied to clipboard')
  }).catch(err => {
    console.error('❌ Failed to copy paper:', err)
    // Fallback for older browsers
    const textArea = document.createElement('textarea')
    textArea.value = plainTextContent.trim()
    document.body.appendChild(textArea)
    textArea.select()
    document.execCommand('copy')
    document.body.removeChild(textArea)
  })
}

const clearGeneratedPaper = () => {
  emit('clear-generated-paper')
}

const checkPlagiarism = async () => {
  try {
    isCheckingPlagiarism.value = true
    plagiarismResult.value = null
    plagiarismError.value = null
    
    const content = getEditorContent()
    if (!content || content.trim().length < 50) {
      throw new Error('Content is too short to check for plagiarism')
    }
    
    const result = await callGPTZeroAPI(content)
    plagiarismResult.value = formatGPTZeroResult(result)
  } catch (error) {
    plagiarismError.value = error.message || 'Failed to check plagiarism'
    console.error('Plagiarism check error:', error)
  } finally {
    isCheckingPlagiarism.value = false
  }
}


// Watch for changes in outline data
watch(() => props.outlineData, (newOutlineData) => {
  parseOutlineContent(newOutlineData)
}, { immediate: true })

// Expose methods for parent component
defineExpose({
  parseOutlineContent,
  setRefining: (value) => {
    isRefining.value = value
  },
  setGeneratingPaper: (value) => {
    isGeneratingPaper.value = value
  }
})
</script>

<style scoped>
.paper-outline-sidebar {
  width: 320px;
  min-width: 260px;
  max-width: 340px;
  padding: 0;
  gap: 0;
  background: #fff;
  box-shadow: none;
  border-left: 1.5px solid #e5e7eb;
  display: flex;
  flex-direction: column;
  align-items: stretch;
  justify-content: flex-start;
  overflow-y: auto;
  scrollbar-width: thin;
  scrollbar-color: #b6c6e3 #f1f5f9;
  height: 100vh;
  box-sizing: border-box;
  transition: transform 0.3s ease-in-out;
}

.paper-outline-sidebar::-webkit-scrollbar {
  width: 8px;
  background: #f1f5f9;
  border-radius: 8px;
}

.paper-outline-sidebar::-webkit-scrollbar-thumb {
  background: #b6c6e3;
  border-radius: 8px;
}

.paper-outline-sidebar.toc-hidden {
  transform: translateX(100%);
}

.toc-tab-header {
  display: flex;
  align-items: center;
  height: 48px;
  border-bottom: 1.5px solid #e5e7eb;
  background: #fff;
  padding: 0 16px 0 0;
  font-size: 1.08em;
  font-weight: 500;
  position: relative;
}

.toc-tab {
  padding: 0 18px;
  height: 100%;
  display: flex;
  align-items: center;
  border-bottom: 2.5px solid #2563eb;
  color: #222;
  background: #fff;
  border-radius: 8px 8px 0 0;
  font-weight: 600;
  margin-right: 8px;
}

.toc-tab-close {
  margin-left: auto;
  color: #2563eb;
  font-size: 1.2em;
  cursor: pointer;
  padding: 2px 8px;
  border-radius: 6px;
  transition: background 0.2s;
  user-select: none;
}

.toc-tab-close:hover {
  background: #e5e7eb;
}

.toc-card-outer {
  flex: 1 1 auto;
  display: flex;
  flex-direction: column;
  align-items: stretch;
  justify-content: flex-start;
  padding: 0;
  background: #fff;
  height: 100%;
  box-sizing: border-box;
}

.toc-card-inner {
  background: #fff;
  border-radius: 0;
  box-shadow: none;
  border: none;
  padding: 18px 16px;
  min-height: 100%;
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: stretch;
  gap: 10px;
  box-sizing: border-box;
}

.toc-header-with-copy {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 8px;
}

.toc-title {
  font-size: 1.08em;
  font-weight: 600;
  color: #222;
  margin-bottom: 0;
}

.copy-all-btn {
  display: flex;
  align-items: center;
  gap: 6px;
  background: #2563eb;
  color: white;
  border: none;
  border-radius: 6px;
  padding: 6px 12px;
  font-size: 0.85em;
  font-weight: 500;
  cursor: pointer;
  transition: all 0.2s;
  box-shadow: 0 1px 3px rgba(37, 99, 235, 0.3);
}

.copy-all-btn:hover {
  background: #1d4ed8;
  transform: translateY(-1px);
  box-shadow: 0 2px 6px rgba(37, 99, 235, 0.4);
}

.copy-all-btn:active {
  transform: translateY(0);
  box-shadow: 0 1px 3px rgba(37, 99, 235, 0.3);
}

.copy-all-btn svg {
  flex-shrink: 0;
}

.toc-content {
  flex: 1;
  color: #64748b;
  font-size: 1em;
  overflow-y: auto;
  scrollbar-width: thin;
  scrollbar-color: #b6c6e3 #f1f5f9;
  margin-bottom: 16px;
}

.toc-content::-webkit-scrollbar {
  width: 8px;
  background: #f1f5f9;
  border-radius: 8px;
}

.toc-content::-webkit-scrollbar-thumb {
  background: #b6c6e3;
  border-radius: 8px;
}

.loading {
  text-align: center;
  padding: 20px;
  color: #64748b;
  font-style: italic;
}

.outline-placeholder {
  color: #94a3b8;
  font-style: italic;
  text-align: center;
  padding: 20px;
  font-size: 0.9em;
  line-height: 1.5;
}

.toc-sections {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.toc-section {
  background: none;
  border: none;
  box-shadow: none;
  margin: 0;
  padding: 0;
}

.toc-section-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 12px 16px;
  background: #f8fafc;
  cursor: pointer;
  transition: background 0.2s;
  border-bottom: 1px solid #e5e7eb;
  font-weight: 600;
  border-radius: 0;
}

.toc-section-header:hover {
  background: #f1f5f9;
}

.toc-section-title {
  font-weight: 600;
  color: #374151;
  font-size: 0.95em;
  flex: 1;
  text-align: left;
}

.toc-section-arrow {
  font-size: 1.2em;
  color: #6b7280;
  transition: transform 0.2s;
  font-weight: bold;
  margin-left: 8px;
}

.toc-section-arrow.expanded {
  transform: rotate(90deg);
}

.toc-section-edit {
  margin-left: 10px;
  color: #2563eb;
  font-size: 1.1em;
  cursor: pointer;
  background: none;
  border: none;
  padding: 2px 6px;
  border-radius: 4px;
  transition: background 0.2s;
  display: flex;
  align-items: center;
  position: relative;
  z-index: 2;
}

.toc-section-edit:hover {
  background: #e5e7eb;
}

.toc-section-content {
  padding: 0 0 16px 0;
  background: none;
  border: none;
  font-size: 0.97em;
  line-height: 1.6;
  color: #222;
  margin: 0;
  width: 100%;
  max-width: 100%;
  overflow-x: auto;
  word-break: break-word;
  white-space: pre-line;
}

.section-display {
  word-break: break-word;
  white-space: pre-line;
}

.section-display :deep(p) {
  margin: 0 0 12px 0;
}

.section-display :deep(p:last-child) {
  margin-bottom: 0;
}

.section-display :deep(ul), 
.section-display :deep(ol) {
  margin: 8px 0;
  padding-left: 20px;
}

.section-display :deep(li) {
  margin-bottom: 4px;
}

.section-editor {
  width: 100%;
  border: 1px solid #d1d5db;
  border-radius: 6px;
  padding: 12px;
  font-size: 0.95em;
  line-height: 1.6;
  font-family: inherit;
  resize: vertical;
  outline: none;
  transition: border-color 0.2s;
}

.section-editor:focus {
  border-color: #2563eb;
  box-shadow: 0 0 0 3px rgba(37, 99, 235, 0.1);
}

.refine-section {
  margin-top: auto;
  padding-top: 16px;
  border-top: 1px solid #e5e7eb;
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.refine-header {
  font-weight: 600;
  color: #374151;
  font-size: 1em;
}

.refine-textarea {
  width: 100%;
  border: 1px solid #d1d5db;
  border-radius: 6px;
  padding: 12px;
  font-size: 0.95em;
  line-height: 1.5;
  font-family: inherit;
  resize: vertical;
  outline: none;
  transition: border-color 0.2s;
  box-sizing: border-box;
}

.refine-textarea:focus {
  border-color: #2563eb;
  box-shadow: 0 0 0 3px rgba(37, 99, 235, 0.1);
}

.refine-btn {
  background: #2563eb;
  color: #fff;
  border: none;
  border-radius: 6px;
  padding: 10px 16px;
  font-size: 0.95em;
  font-weight: 500;
  cursor: pointer;
  transition: background 0.2s;
  align-self: flex-start;
}

.refine-btn:hover:not(:disabled) {
  background: #1d4ed8;
}

.refine-btn:disabled {
  background: #94a3b8;
  cursor: not-allowed;
}

.button-group {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
}

.generate-paper-btn {
  background: #16a34a;
  color: #fff;
  border: none;
  border-radius: 6px;
  padding: 10px 16px;
  font-size: 0.95em;
  font-weight: 500;
  cursor: pointer;
  transition: background 0.2s;
  flex: 1;
  min-width: 140px;
}

.generate-paper-btn:hover:not(:disabled) {
  background: #15803d;
}

.generate-paper-btn:disabled {
  background: #94a3b8;
  cursor: not-allowed;
}

.generate-paper-btn.loading {
  pointer-events: none;
  opacity: 0.5;
}

.generate-paper-btn.loading .spinner {
  display: inline-block;
  animation: spin 1s linear infinite;
}

.generate-paper-btn.loading .btn-text {
  opacity: 0;
}

.refine-btn {
  flex: 1;
  min-width: 120px;
}

.generated-paper-content {
  font-size: 0.9em;
  line-height: 1.6;
  color: #222;
  padding: 16px;
  background: #fafbfc;
  border-radius: 6px;
  border: 1px solid #e5e7eb;
  margin-bottom: 16px;
}

.generated-paper-content :deep(h3) {
  color: #1f2937;
  font-size: 1.1em;
  font-weight: 600;
  margin: 20px 0 12px 0;
  padding-bottom: 8px;
  border-bottom: 2px solid #e5e7eb;
}

.generated-paper-content :deep(h3:first-child) {
  margin-top: 0;
}

.generated-paper-content :deep(p) {
  margin: 0 0 14px 0;
  text-align: justify;
}

.generated-paper-content :deep(p:last-child) {
  margin-bottom: 0;
}

.paper-actions {
  padding: 16px 0 0 0;
  border-top: 1px solid #e5e7eb;
  margin-top: auto;
}

.back-to-outline-btn {
  background: #6b7280;
  color: #fff;
  border: none;
  border-radius: 6px;
  padding: 8px 16px;
  font-size: 0.9em;
  font-weight: 500;
  cursor: pointer;
  transition: background 0.2s;
  width: 100%;
}

.back-to-outline-btn:hover {
  background: #4b5563;
}
.plag-checker-btn {
  padding: 10px 16px;
  background-color: #2563eb;
  color: white;
  border: none;
  border-radius: 6px;
  cursor: pointer;
  font-size: 0.95em;
  font-weight: 500;
  width: 100%;
  margin-bottom: 16px;
  transition: background-color 0.2s;
}

.plag-checker-btn:hover:not(:disabled) {
  background-color: #1d4ed8;
}

.plag-checker-btn:disabled {
  background-color: #94a3b8;
  cursor: not-allowed;
}

.plagiarism-result, .plagiarism-error {
  padding: 12px;
  border-radius: 6px;
  font-size: 0.9em;
  line-height: 1.5;
}

.plagiarism-result {
  background-color: #f0fdf4;
  border-left: 4px solid #16a34a;
  color: #166534;
}

.plagiarism-error {
  background-color: #fef2f2;
  border-left: 4px solid #dc2626;
  color: #991b1b;
}

.result-item {
  margin-bottom: 10px;
  padding-bottom: 10px;
  border-bottom: 1px solid #e5e7eb;
}

.result-item:last-child {
  border-bottom: none;
  margin-bottom: 0;
}

/* Update the tab styles to match your existing design */
.toc-tab {
  padding: 0 18px;
  height: 100%;
  display: flex;
  align-items: center;
  color: #64748b;
  background: #fff;
  border-radius: 8px 8px 0 0;
  font-weight: 500;
  margin-right: 8px;
  cursor: pointer;
  transition: all 0.2s ease;
  border-bottom: 2.5px solid transparent;
}

.toc-tab.active {
  color: #2563eb;
  font-weight: 600;
  border-bottom: 2.5px solid #2563eb;
}

.toc-tab:hover {
  background: #f8fafc;
}
</style>