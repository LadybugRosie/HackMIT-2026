<template>
  <div class="cursor-chat" @dragover.prevent @drop.prevent="handleDrop">
    <!-- Header -->
    <div class="chat-header">
      <div class="header-content">
        <div class="chat-title">
          <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
            <path d="m3 21 1.9-5.7a8.5 8.5 0 1 1 3.8 3.8z"/>
          </svg>
          AI Assistant
        </div>
        <div class="header-actions">
          <button class="clear-btn" @click="clearChat" title="Clear chat">
            <svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
              <path d="M3 6h18"/>
              <path d="M19 6v14c0 1-1 2-2 2H7c-1 0-2-1-2-2V6"/>
              <path d="M8 6V4c0-1 1-2 2-2h4c1 0 2 1 2 2v2"/>
            </svg>
          </button>
          <button class="close-btn" @click="$emit('toggle-chat')" title="Close chat">
            <svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
              <line x1="18" y1="6" x2="6" y2="18"/>
              <line x1="6" y1="6" x2="18" y2="18"/>
            </svg>
          </button>
        </div>
      </div>
    </div>

    <!-- Chat Messages -->
    <div class="chat-messages" ref="messagesContainer">
      <div v-if="messages.length === 0" class="welcome-message">
        <div class="welcome-icon">
          <svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round">
            <path d="M9 12l2 2 4-4"/>
            <path d="M21 12c.552 0 1-.448 1-1V5c0-.552-.448-1-1-1H3c-.552 0-1 .448-1 1v6c0 .552.448 1 1 1h18z"/>
          </svg>
        </div>
        <h3>AI Writing Assistant</h3>
        <p>Ask me to help with writing, editing, research, or any questions about your document.</p>
        <div class="debug-section">
          <button class="debug-btn" @click="debugEditor">🔍 Debug Editor</button>
          <button class="debug-btn" @click="testEdit">🧪 Test Edit</button>
        </div>
      </div>

      <div v-for="message in messages" :key="message.id" class="message" :class="message.role">
        <div class="message-avatar">
          <div v-if="message.role === 'user'" class="user-avatar">
            <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
              <path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2"/>
              <circle cx="12" cy="7" r="4"/>
            </svg>
          </div>
          <div v-else class="ai-avatar">
            <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
              <path d="M12 8V4H8"/>
              <rect width="16" height="12" x="4" y="8" rx="2"/>
              <path d="m14 8-2-2-2 2"/>
              <path d="M18 12h.01"/>
              <path d="M6 12h.01"/>
            </svg>
          </div>
        </div>
        <div class="message-content">
          <!-- Show attached files if this is a user message with files -->
          <div v-if="message.role === 'user' && message.files && message.files.length > 0" class="attached-files">
            <div v-for="file in message.files" :key="file.name" class="file-item">
              <div class="file-icon">
                <svg v-if="file.type.startsWith('image/')" xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                  <rect width="18" height="18" x="3" y="3" rx="2" ry="2"/>
                  <circle cx="9" cy="9" r="2"/>
                  <path d="m21 15-3.086-3.086a2 2 0 0 0-2.828 0L6 21"/>
                </svg>
                <svg v-else-if="file.type.includes('pdf')" xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                  <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/>
                  <polyline points="14,2 14,8 20,8"/>
                  <line x1="16" y1="13" x2="8" y2="13"/>
                  <line x1="16" y1="17" x2="8" y2="17"/>
                  <polyline points="10,9 9,9 8,9"/>
                </svg>
                <svg v-else xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                  <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/>
                  <polyline points="14,2 14,8 20,8"/>
                  <line x1="16" y1="13" x2="8" y2="13"/>
                  <line x1="16" y1="17" x2="8" y2="17"/>
                </svg>
              </div>
              <div class="file-info">
                <div class="file-name">{{ file.name }}</div>
                <div class="file-size">{{ formatFileSize(file.size) }}</div>
              </div>
            </div>
          </div>
          
          <div class="message-text" v-html="formatMessage(message.content)"></div>
          <div class="message-time">{{ formatTime(message.timestamp) }}</div>
          <div v-if="message.role === 'assistant'" class="message-actions">
            <button 
              v-if="message.patch" 
              class="action-btn primary" 
              @click="applyPatch(message.patch)" 
              title="Apply this edit to document"
            >
              <svg xmlns="http://www.w3.org/2000/svg" width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                <path d="M9 12l2 2 4-4"/>
              </svg>
              Apply
            </button>
            <button class="action-btn" @click="copyMessage(message.content)" title="Copy">
              <svg xmlns="http://www.w3.org/2000/svg" width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                <rect width="14" height="14" x="8" y="8" rx="2" ry="2"/>
                <path d="m4 16c-1.1 0-2-.9-2-2V4c0-1.1.9-2 2-2h10c1.1 0 2 .9 2 2"/>
              </svg>
            </button>
          </div>
        </div>
      </div>

      <!-- Typing indicator -->
      <div v-if="isTyping" class="message assistant typing">
        <div class="message-avatar">
          <div class="ai-avatar">
            <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
              <path d="M12 8V4H8"/>
              <rect width="16" height="12" x="4" y="8" rx="2"/>
              <path d="m14 8-2-2-2 2"/>
              <path d="M18 12h.01"/>
              <path d="M6 12h.01"/>
            </svg>
          </div>
        </div>
        <div class="message-content">
          <div class="typing-indicator">
            <span></span>
            <span></span>
            <span></span>
          </div>
        </div>
      </div>
    </div>

    <!-- File Preview Area -->
    <div v-if="selectedFiles.length > 0" class="file-preview-area">
      <div class="file-preview-header">
        <span class="file-count">{{ selectedFiles.length }} file(s) attached</span>
        <button class="clear-files-btn" @click="clearFiles" title="Clear files">
          <svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
            <line x1="18" y1="6" x2="6" y2="18"/>
            <line x1="6" y1="6" x2="18" y2="18"/>
          </svg>
        </button>
      </div>
      <div class="file-preview-list">
        <div v-for="file in selectedFiles" :key="file.name" class="file-preview-item">
          <div class="file-icon">
            <svg v-if="file.type.startsWith('image/')" xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
              <rect width="18" height="18" x="3" y="3" rx="2" ry="2"/>
              <circle cx="9" cy="9" r="2"/>
              <path d="m21 15-3.086-3.086a2 2 0 0 0-2.828 0L6 21"/>
            </svg>
            <svg v-else-if="file.type.includes('pdf')" xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
              <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/>
              <polyline points="14,2 14,8 20,8"/>
              <line x1="16" y1="13" x2="8" y2="13"/>
              <line x1="16" y1="17" x2="8" y2="17"/>
              <polyline points="10,9 9,9 8,9"/>
            </svg>
            <svg v-else xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
              <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/>
              <polyline points="14,2 14,8 20,8"/>
              <line x1="16" y1="13" x2="8" y2="13"/>
              <line x1="16" y1="17" x2="8" y2="17"/>
            </svg>
          </div>
          <div class="file-info">
            <div class="file-name">{{ file.name }}</div>
            <div class="file-size">{{ formatFileSize(file.size) }}</div>
          </div>
          <button class="remove-file-btn" @click="removeFile(file)" title="Remove file">
            <svg xmlns="http://www.w3.org/2000/svg" width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
              <line x1="18" y1="6" x2="6" y2="18"/>
              <line x1="6" y1="6" x2="18" y2="18"/>
            </svg>
          </button>
        </div>
      </div>
    </div>

    <!-- Input Area -->
    <div class="chat-input-area">
      <div class="input-container">
        <textarea
          ref="chatInput"
          v-model="currentMessage"
          @keydown="handleKeyDown"
          @input="adjustTextareaHeight"
          placeholder="Ask AI anything about your document..."
          rows="1"
          :disabled="isLoading"
        ></textarea>
        <input ref="fileInputRef" type="file" multiple style="display: none" @change="handleFileChange" />
        <button class="send-btn" @click="startWebSearch" title="Web search (/web)">
          <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
            <circle cx="12" cy="12" r="10"/>
            <path d="M2 12h20"/>
            <path d="M12 2a15.3 15.3 0 0 1 4 10 15.3 15.3 0 0 1-4 10 15.3 15.3 0 0 1-4-10 15.3 15.3 0 0 1 4-10z"/>
          </svg>
        </button>
        <button class="send-btn" @click="triggerFilePicker" title="Attach files (/attach)">
          <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
            <path d="M21.44 11.05l-9.19 9.19a6 6 0 0 1-8.49-8.49l9.19-9.19a4 4 0 0 1 5.66 5.66l-9.2 9.19a2 2 0 0 1-2.83-2.83l8.49-8.48"/>
          </svg>
        </button>
        <button 
          class="send-btn" 
          @click="sendMessage" 
          :disabled="!currentMessage.trim() || isLoading"
          :class="{ 'loading': isLoading }"
        >
          <svg v-if="!isLoading" xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
            <path d="m22 2-7 20-4-9-9-4Z"/>
            <path d="M22 2 11 13"/>
          </svg>
          <div v-else class="loading-spinner"></div>
        </button>
      </div>
      <div class="input-hints">
        Press <kbd>Enter</kbd> to send, <kbd>Shift+Enter</kbd> for new line. Commands: <code>/web</code>, <code>/long</code>, <code>/attach</code>
        <span v-if="selectedFiles.length" style="margin-left:8px;color:#6b7280;">{{ selectedFiles.length }} file(s) attached</span>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, nextTick, onMounted, watch } from 'vue'

// Ensure Step is available for pmSteps hydration
let Step
try {
  // CommonJS require (most bundlers support this interop)
  // eslint-disable-next-line @typescript-eslint/no-var-requires
  Step = require('prosemirror-transform').Step
} catch (e) {
  Step = undefined
}

// Props
const props = defineProps({
  backendUrl: {
    type: String,
    default: 'https://believable-dedication-production.up.railway.app'
  }
})

// Emits
const emit = defineEmits(['toggle-chat'])

// Reactive state
const messages = ref([])
const currentMessage = ref('')
const isLoading = ref(false)
const isTyping = ref(false)
const messagesContainer = ref(null)
const chatInput = ref(null)
const fileInputRef = ref(null)
const selectedFiles = ref([])

// Message management
let messageId = 0

function generateMessageId() {
  return ++messageId
}

function addMessage(role, content, patch = null) {
  const message = {
    id: generateMessageId(),
    role,
    content,
    timestamp: new Date(),
    patch: patch,  // Store patch data for Apply button
    files: patch?.files || null  // Store files info for display
  }
  messages.value.push(message)
  scrollToBottom()
  return message
}

function scrollToBottom() {
  nextTick(() => {
    if (messagesContainer.value) {
      messagesContainer.value.scrollTop = messagesContainer.value.scrollHeight
    }
  })
}

function adjustTextareaHeight() {
  nextTick(() => {
    if (chatInput.value) {
      chatInput.value.style.height = 'auto'
      chatInput.value.style.height = Math.min(chatInput.value.scrollHeight, 120) + 'px'
    }
  })
}

function handleKeyDown(event) {
  if (event.key === 'Enter' && !event.shiftKey) {
    event.preventDefault()
    sendMessage()
  }
}

// Utilities preserved from existing implementation
function getCursorPosition() {
  try {
    if (window.getEditorCursorPosition && typeof window.getEditorCursorPosition === 'function') {
      const pos = window.getEditorCursorPosition()
      if (typeof pos === 'number' && pos >= 0) return pos
    }
  } catch (e) {}
  return 0
}

function getChatHistory() {
  return messages.value.map(m => ({ role: m.role, content: m.content }))
}

function buildApiUrl(path) {
  try {
    const host = window.location.hostname
    const isLocal = host === 'localhost' || host === '127.0.0.1'
    if (isLocal) return `/api${path}`
  } catch (e) {}
  return `${props.backendUrl}/api${path}`
}

// D1: Edit Intent Detection
function detectEditIntent(prompt, hasSelection = false) {
  const editKeywords = [
    'edit', 'rewrite', 'replace', 'convert', 'format', 'fix', 'move', 'swap', 
    'add', 'remove', 'change', 'capitalize', 'APA', 'IEEE', 'bold', 'heading', 
    'active voice', 'grammar', 'improve', 'shorten', 'expand', 'rephrase'
  ]
  
  const isEditKeyword = editKeywords.some(keyword => 
    prompt.toLowerCase().includes(keyword.toLowerCase())
  )
  
  return hasSelection || isEditKeyword || prompt.startsWith('edit:')
}

// D2: Surgical Context Collection - Only Edit What's Needed
function collectEditContext() {
  try {
    const selectedText = getSelectedTextFallback()
    const documentHtml = getDocumentContextFallback()
    
    if (selectedText) {
      return {
        document_html: documentHtml,
        target_text: selectedText,
        edit_scope: 'selection',
        has_selection: true,
        preserve_layout: true
      }
    } else {
      const currentParagraph = getCurrentParagraph()
      if (currentParagraph) {
        return {
          document_html: documentHtml,
          target_text: currentParagraph,
          edit_scope: 'paragraph',
          has_selection: false,
          preserve_layout: true
        }
      } else {
        return {
          document_html: documentHtml,
          target_text: documentHtml,
          edit_scope: 'document',
          has_selection: false,
          preserve_layout: true
        }
      }
    }
  } catch (error) {
    const documentHtml = getDocumentContextFallback()
    return {
      document_html: documentHtml,
      target_text: documentHtml,
      edit_scope: 'document',
      has_selection: false,
      preserve_layout: true
    }
  }
}

function getCurrentParagraph() {
  try {
    const selection = window.getSelection()
    if (selection && selection.rangeCount > 0) {
      const range = selection.getRangeAt(0)
      let node = range.startContainer
      while (node && node.nodeType !== Node.ELEMENT_NODE) {
        node = node.parentNode
      }
      while (node && node.tagName !== 'P' && node.tagName !== 'H1' && node.tagName !== 'H2' && node.tagName !== 'H3') {
        node = node.parentNode
        if (!node || node.tagName === 'BODY') break
      }
      if (node && (node.tagName === 'P' || node.tagName.startsWith('H'))) {
        return node.textContent?.trim() || ''
      }
    }
  } catch (error) {}
  return null
}

function getDocumentContextFallback() {
  try {
    if (window.getEditorHTMLContent && typeof window.getEditorHTMLContent === 'function') {
      const content = window.getEditorHTMLContent()
      return content
    }
    const proseMirror = document.querySelector('.ProseMirror')
    if (proseMirror) {
      const clone = proseMirror.cloneNode(true)
      const editingElements = clone.querySelectorAll('.ProseMirror-widget, .ProseMirror-decoration')
      editingElements.forEach(el => el.remove())
      const content = clone.innerHTML
      return content
    }
    return '<p>Could not access document content</p>'
  } catch (error) {
    return '<p>Error accessing document</p>'
  }
}

function getSelectedTextFallback() {
  const selection = window.getSelection()
  if (selection && selection.toString().trim()) {
    return selection.toString().trim()
  }
  return ''
}

function preserveDocumentSpacing(originalHtml, newHtml) {
  try {
    const originalParaCount = (originalHtml.match(/<p[^>]*>/g) || []).length
    const newParaCount = (newHtml.match(/<p[^>]*>/g) || []).length
    if (originalParaCount !== newParaCount && originalParaCount > 0) {
      const originalParas = originalHtml.match(/<p[^>]*>.*?<\/p>/gs) || []
      const newText = newHtml.replace(/<[^>]*>/g, ' ').replace(/\s+/g, ' ').trim()
      if (originalParas.length > 0) {
        const words = newText.split(' ')
        const wordsPerPara = Math.ceil(words.length / originalParas.length)
        let reconstructed = ''
        for (let i = 0; i < originalParas.length; i++) {
          const paraWords = words.slice(i * wordsPerPara, (i + 1) * wordsPerPara)
          if (paraWords.length > 0) {
            reconstructed += `<p>${paraWords.join(' ')}</p>`
          }
        }
        if (reconstructed) {
          return reconstructed
        }
      }
    }
    let processedHtml = newHtml
    processedHtml = processedHtml.replace(/<\/p><p>/g, '</p>\n<p>')
    processedHtml = processedHtml.replace(/>\s+</g, '><')
    processedHtml = processedHtml.replace(/<p>/g, '<p>')
    return processedHtml
  } catch (error) {
    return newHtml
  }
}

async function sendMessage() {
  if (!currentMessage.value.trim() || isLoading.value) return
  
  const userMessage = currentMessage.value.trim()
  currentMessage.value = ''
  adjustTextareaHeight()
  
  const lower = userMessage.toLowerCase()
  if (lower.startsWith('/web ')) {
    const query = userMessage.slice(5).trim()
    addMessage('user', userMessage)
    await sendWebSearch(query)
    return
  }
  if (lower.startsWith('/long ')) {
    const rest = userMessage.slice(6).trim()
    addMessage('user', userMessage)
    await sendLongForm(rest)
    return
  }
  if (lower === '/attach') {
    triggerFilePicker()
    return
  }
  if (lower.startsWith('/ask ') || selectedFiles.value.length > 0) {
    const question = lower.startsWith('/ask ') ? userMessage.slice(5).trim() : userMessage
    await sendFilesWithQuestion(question)
    return
  }

  // Add user message for regular chat
  addMessage('user', userMessage)

  // D1: Detect if this is an edit request
  const selectedText = getSelectedText()
  const isEdit = detectEditIntent(userMessage, !!selectedText)
  
  if (isEdit) {
    await sendEditRequest(userMessage)
  } else {
    await sendWriteRequest(userMessage)
  }
}

// D3: Surgical Edit Request
async function sendEditRequest(instruction) {
  isLoading.value = true
  isTyping.value = true
  
  try {
    const context = collectEditContext()
    if (!context) {
      throw new Error('Could not access editor context')
    }
    
    let surgicalInstruction = instruction
    if (context.edit_scope === 'selection') {
      surgicalInstruction = `${instruction}. ONLY modify this selected text: "${context.target_text}". Return ONLY the modified version of this text, preserving the exact same structure and formatting.`
    } else if (context.edit_scope === 'paragraph') {
      surgicalInstruction = `${instruction}. ONLY modify this paragraph: "${context.target_text}". Return ONLY the modified version of this paragraph, preserving the exact same structure and formatting.`
    } else {
      surgicalInstruction = `${instruction}. Modify the document while preserving the overall structure and layout.`
    }
    
    const recentHistory = messages.value.slice(-10).map(msg => ({
      role: msg.role,
      content: msg.content
    }))
    
    // Compose optional fields expected by Swagger
    const editor = getEditorInstance()
    const tiptapJson = editor && typeof editor.getJSON === 'function' ? editor.getJSON() : {}
    const sel = editor?.state?.selection
    const caretFrom = typeof sel?.from === 'number' ? sel.from : 0
    const caret_path = [caretFrom]

    const response = await fetch(buildApiUrl(`/run/edit`), {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        html_document: context.document_html,
        tiptap_json: tiptapJson,
        caret_path,
        selection_range: getSelectionRangeForBackend() || {},
        instruction: surgicalInstruction,
        chat_history: recentHistory
      })
    })
    
    if (!response.ok) {
      throw new Error(`HTTP error! status: ${response.status}`)
    }
    
    const result = await response.json()
    
    const patch = {
      pmSteps: result.tiptap_operations || [],
      htmlFallback: result.new_html,
      summary: result.edit_summary,
      context: context
    }
    
    const suggestionText = `**Edit Suggestion**: ${result.edit_summary}\n\n${result.new_html || 'Applied changes to document.'}`
    addMessage('assistant', suggestionText, patch)
    
  } catch (error) {
    isTyping.value = false
    addMessage('assistant', `Error applying edit: ${error.message}`)
  } finally {
    isLoading.value = false
    isTyping.value = false
  }
}

function getSelectionRangeForBackend() {
  try {
    const editor = getEditorInstance()
    if (!editor) return null
    const { from, to } = editor.state.selection || {}
    if (typeof from === 'number' && typeof to === 'number') {
      return { from, to }
    }
    return null
  } catch (e) {
    return null
  }
}

async function sendWriteRequest(userMessage) {
  isLoading.value = true
  isTyping.value = true
  
  try {
    const documentContext = getDocumentContext()
    const selectedText = getSelectedText()
    
    const recentHistory = messages.value.slice(-10).map(msg => ({
      role: msg.role,
      content: msg.content
    }))
    
    const response = await fetch(buildApiUrl(`/run/write`), {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        text: selectedText ? `${userMessage}\n\nSelected text: ${selectedText}` : userMessage,
        context: documentContext,
        // Default to non-streaming to match backend behavior, but handle streaming if provided
        stream: false,
        chat_history: recentHistory,
        cursor_position: getCursorPosition()
      })
    })
    
    if (!response.ok) {
      throw new Error(`HTTP error! status: ${response.status}`)
    }
    
    const contentType = response.headers.get('content-type') || ''
    if (contentType.includes('text/event-stream')) {
      // Handle streaming response
      const reader = response.body.getReader()
      const decoder = new TextDecoder()
      let assistantMessage = addMessage('assistant', '')
      isTyping.value = false
      while (true) {
        const { done, value } = await reader.read()
        if (done) break
        const chunk = decoder.decode(value, { stream: true })
        const lines = chunk.split('\n')
        for (const line of lines) {
          if (line.startsWith('data: ')) {
            try {
              const data = JSON.parse(line.slice(6))
              if (data.chunk) {
                assistantMessage.content += data.chunk
                messages.value = [...messages.value]
                scrollToBottom()
              }
            } catch (e) {
              // ignore invalid JSON lines
            }
          }
        }
      }
    } else {
      // Non-streaming JSON
      const data = await response.json()
      const text = data.reply || data.text || data.result || 'Done.'
      addMessage('assistant', text)
    }
    
  } catch (error) {
    isTyping.value = false
    addMessage('assistant', 'Sorry, I encountered an error. Please try again.')
  } finally {
    isLoading.value = false
    isTyping.value = false
  }
}

// Apply backend-supplied ProseMirror Step JSON list ("pmStep" operations)
function applyPmSteps(editor, operations) {
  try {
    const pmSteps = operations
      .filter((op) => op.type === 'pmStep' && op.step)
      .map((op) => Step.fromJSON(editor.state.schema, op.step))

    if (!pmSteps.length) return

    let tr = editor.state.tr
    pmSteps.forEach((step) => {
      tr = tr.step(step)
    })
    editor.view.dispatch(tr.scrollIntoView())
  } catch (e) {
    // pm steps failed, ignore
  }
}

function applyPatch(patch) {
  try {
    const editor = getEditorInstance()
    if (!editor) {
      throw new Error('Editor not available')
    }

    if (patch.pmSteps && patch.pmSteps.length > 0) {
      applyPmSteps(editor, patch.pmSteps)
      addMessage('system', `✅ Applied: ${patch.summary}`)
      return
    }

    if (patch.htmlFallback) {
      applyHtmlFallback(patch.htmlFallback, patch.context)
      addMessage('system', `✅ Applied: ${patch.summary}`)
      return
    }

    throw new Error('No applicable patch data found')

  } catch (error) {
    addMessage('system', `❌ Apply failed: ${error.message}`)
  }
}

function applyHtmlFallback(newHtml) {
  if (window.loadEditorContentFromDatabase) {
    window.editorContentFromDatabase = newHtml
    window.loadEditorContentFromDatabase()
  } else {
    const editor = getEditorInstance()
    if (editor && editor.commands) {
      editor.commands.setContent(newHtml, false)
    }
  }
}

async function sendWebSearch(query) {
  try {
    isLoading.value = true
    isTyping.value = true
    const params = new URLSearchParams()
    params.set('query', query)
    const resp = await fetch(buildApiUrl(`/run/web-search`), {
      method: 'POST',
      headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
      body: params.toString(),
    })
    if (!resp.ok) throw new Error(`HTTP ${resp.status}`)
    const data = await resp.json()
    
    if (data.error) {
      addMessage('assistant', `Web search error: ${data.error}`)
      return
    }
    
    let text = data.text || 'No results.'
    if (data.citations && data.citations.length > 0) {
      text += '<br><br><strong>Sources:</strong><br>'
      data.citations.forEach((citation, i) => {
        const title = citation.title || `Source ${i + 1}`
        text += `<a href="${citation.url}" target="_blank" rel="noopener">[${i + 1}] ${title}</a><br>`
      })
    }
    
    addMessage('assistant', text)
  } catch (e) {
    addMessage('assistant', `Web search failed: ${e.message}`)
  } finally {
    isLoading.value = false
    isTyping.value = false
  }
}

async function sendLongForm(rest) {
  try {
    isLoading.value = true
    isTyping.value = true
    let words = 10000
    const match = rest.match(/^(\d+)\s+(.*)$/)
    const prompt = match ? match[2] : rest
    if (match) words = parseInt(match[1]) || 10000
    const params = new URLSearchParams()
    params.set('prompt', prompt)
    params.set('target_words', String(words))
    const resp = await fetch(buildApiUrl(`/run/longform`), {
      method: 'POST',
      headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
      body: params.toString(),
    })
    if (!resp.ok) throw new Error(`HTTP ${resp.status}`)
    const data = await resp.json()
    addMessage('assistant', data.text || data.result || 'Done.')
  } catch (e) {
    addMessage('assistant', `Long-form generation failed: ${e.message}`)
  } finally {
    isLoading.value = false
    isTyping.value = false
  }
}

function triggerFilePicker() {
  fileInputRef.value?.click()
}

function handleFileChange(e) {
  const files = Array.from(e.target.files || [])
  const newFiles = [...selectedFiles.value, ...files]
  if (newFiles.length > 10) {
    selectedFiles.value = newFiles.slice(0, 10)
    addMessage('assistant', `Maximum 10 files allowed. Only the first 10 files were selected.`)
  } else {
    selectedFiles.value = newFiles
  }
  if (e.target) e.target.value = ''
}

function handleDrop(e) {
  const files = Array.from(e.dataTransfer?.files || [])
  if (files.length) {
    const newFiles = [...selectedFiles.value, ...files]
    if (newFiles.length > 10) {
      selectedFiles.value = newFiles.slice(0, 10)
      addMessage('assistant', `Maximum 10 files allowed. Only the first 10 files were selected.`)
    } else {
      selectedFiles.value = newFiles
    }
  }
}

function clearFiles() {
  selectedFiles.value = []
}

function removeFile(fileToRemove) {
  selectedFiles.value = selectedFiles.value.filter(f => f !== fileToRemove)
}

function formatFileSize(bytes) {
  if (bytes === 0) return '0 Bytes'
  const k = 1024
  const sizes = ['Bytes', 'KB', 'MB', 'GB']
  const i = Math.floor(Math.log(bytes) / Math.log(k))
  return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i]
}

async function sendFilesWithQuestion(question) {
  try {
    if (selectedFiles.value.length > 10) {
      addMessage('assistant', 'Error: Maximum 10 files allowed per request. Please remove some files and try again.')
      return
    }
    if (selectedFiles.value.length === 0) {
      addMessage('assistant', 'Error: No files selected.')
      return
    }
    isLoading.value = true
    isTyping.value = true
    const filesInfo = selectedFiles.value.map(f => ({
      name: f.name,
      type: f.type,
      size: f.size
    }))
    addMessage('user', question, { files: filesInfo })
    const fd = new FormData()
    fd.append('prompt', question)
    const recentHistory = messages.value.slice(-10).map(msg => ({
      role: msg.role,
      content: msg.content
    }))
    fd.append('chat_history', JSON.stringify(recentHistory))
    for (const f of selectedFiles.value) {
      fd.append('files', f)
    }
    const resp = await fetch(buildApiUrl(`/run/ask-with-files`), {
      method: 'POST',
      body: fd,
    })
    if (!resp.ok) {
      const errorText = await resp.text()
      throw new Error(`HTTP ${resp.status}: ${errorText}`)
    }
    const data = await resp.json()
    addMessage('assistant', data.answer || 'Done.')
    selectedFiles.value = []
  } catch (e) {
    addMessage('assistant', `File processing failed: ${e.message}`)
  } finally {
    isLoading.value = false
    isTyping.value = false
  }
}

function startWebSearch() {
  currentMessage.value = '/web '
  nextTick(() => chatInput.value?.focus())
}

function clearChat() {
  messages.value = []
}

function formatMessage(content) {
  return content
    .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
    .replace(/\*(.*?)\*/g, '<em>$1</em>')
    .replace(/`(.*?)`/g, '<code>$1</code>')
    .replace(/\n/g, '<br>')
}

function formatTime(timestamp) {
  return timestamp.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
}

async function copyMessage(content) {
  try {
    await navigator.clipboard.writeText(content)
  } catch (err) {}
}

// Editor helpers
function getEditorInstance() {
  if (window.editorRef?.editor) return window.editorRef.editor
  if (window.currentEditor) return window.currentEditor
  const proseMirrorEl = document.querySelector('.ProseMirror')
  if (proseMirrorEl) {
    let current = proseMirrorEl
    while (current) {
      if (current.__vueParentComponent) {
        const component = current.__vueParentComponent
        if (component.ctx?.editor) return component.ctx.editor
        if (component.setupState?.editor) return component.setupState.editor
        if (component.props?.editor) return component.props.editor
      }
      current = current.parentElement
    }
  }
  return null
}

function getDocumentContext() {
  try {
    if (window.getEditorHTMLContent && typeof window.getEditorHTMLContent === 'function') {
      const content = window.getEditorHTMLContent()
      return content.slice(-2000)
    }
  } catch (error) {}
  return ''
}

function getSelectedText() {
  try {
    const editor = getEditorInstance()
    if (editor && editor.state) {
      const { from, to } = editor.state.selection
      if (from !== to) {
        const selectedText = editor.state.doc.textBetween(from, to, ' ')
        if (selectedText.trim()) return selectedText.trim()
      }
    }
    const selection = window.getSelection()
    if (selection && selection.toString().trim()) {
      return selection.toString().trim()
    }
    const editorElement = document.querySelector('.ProseMirror')
    if (editorElement) {
      const selection = editorElement.ownerDocument.getSelection()
      if (selection && selection.toString().trim()) {
        return selection.toString().trim()
      }
    }
  } catch (error) {}
  return ''
}

// Debug utilities
function debugEditor() {
  addMessage('assistant', 'Debug info logged to console. Check browser developer tools.')
}

function testEdit() {
  const currentContent = getDocumentContextFallback()
  const testResult = {
    new_html: currentContent + '<p><strong>🧪 TEST EDIT APPLIED SUCCESSFULLY!</strong> This paragraph was added via the edit system.</p>',
    edit_summary: 'Test edit completed - added test paragraph',
    tiptap_operations: []
  }
  applyHtmlFallback(testResult.new_html)
  addMessage('assistant', `✅ Test edit applied`)
}

// Focus input when component mounts
onMounted(() => {
  if (chatInput.value) {
    chatInput.value.focus()
  }
})

// Watch for input changes to adjust height
watch(currentMessage, () => {
  adjustTextareaHeight()
})
</script>

<style scoped>
.cursor-chat {
  display: flex;
  flex-direction: column;
  height: 100vh;
  background: #ffffff;
  border-left: 1px solid #e1e5e9;
}

/* Header */
.chat-header {
  padding: 16px 20px;
  border-bottom: 1px solid #e1e5e9;
  background: #ffffff;
}

.header-content {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.chat-title {
  display: flex;
  align-items: center;
  gap: 8px;
  font-weight: 600;
  color: #1f2937;
  font-size: 14px;
}

.header-actions {
  display: flex;
  gap: 8px;
}

.clear-btn, .close-btn {
  padding: 6px;
  background: none;
  border: none;
  border-radius: 4px;
  cursor: pointer;
  color: #6b7280;
  transition: all 0.2s;
}

.clear-btn:hover, .close-btn:hover {
  background: #f3f4f6;
  color: #374151;
}

/* Messages */
.chat-messages {
  flex: 1;
  overflow-y: auto;
  padding: 0;
  scroll-behavior: smooth;
}

.welcome-message {
  padding: 40px 20px;
  text-align: center;
  color: #6b7280;
}

.welcome-icon {
  width: 48px;
  height: 48px;
  background: #f3f4f6;
  border-radius: 12px;
  display: flex;
  align-items: center;
  justify-content: center;
  margin: 0 auto 16px;
  color: #9ca3af;
}

.welcome-message h3 {
  margin: 0 0 8px 0;
  color: #1f2937;
  font-size: 18px;
  font-weight: 600;
}

.welcome-message p {
  margin: 0 0 24px 0;
  font-size: 14px;
  line-height: 1.5;
}

.debug-section {
  display: flex;
  gap: 8px;
  margin-bottom: 16px;
}

.debug-btn {
  padding: 6px 12px;
  background: #e5e7eb;
  border: 1px solid #d1d5db;
  border-radius: 4px;
  font-size: 11px;
  cursor: pointer;
  color: #374151;
  transition: all 0.2s;
}

.debug-btn:hover {
  background: #d1d5db;
}

.message {
  display: flex;
  gap: 12px;
  padding: 16px 20px;
  align-items: flex-start;
}

.message.user {
  background: #f8f9fa;
}

.message-avatar {
  flex-shrink: 0;
  width: 32px;
  height: 32px;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: 6px;
}

.user-avatar {
  background: #007acc;
  color: white;
  width: 100%;
  height: 100%;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: 6px;
}

.ai-avatar {
  background: #f3f4f6;
  color: #6b7280;
  width: 100%;
  height: 100%;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: 6px;
}

.message-content {
  flex: 1;
  min-width: 0;
}

.message-text {
  font-size: 14px;
  line-height: 1.5;
  color: #1f2937;
  word-wrap: break-word;
}

.message-text code {
  background: #f3f4f6;
  padding: 2px 4px;
  border-radius: 3px;
  font-size: 13px;
  font-family: 'Monaco', 'Consolas', monospace;
}

.message-time {
  font-size: 11px;
  color: #9ca3af;
  margin-top: 4px;
}

.message-actions {
  display: flex;
  gap: 4px;
  margin-top: 8px;
  opacity: 0;
  transition: opacity 0.2s;
}

.message:hover .message-actions {
  opacity: 1;
}

.action-btn {
  padding: 4px 8px;
  background: none;
  border: 1px solid #e5e7eb;
  border-radius: 4px;
  cursor: pointer;
  color: #6b7280;
  transition: all 0.2s;
  font-size: 11px;
  display: flex;
  align-items: center;
  gap: 4px;
}

.action-btn.primary {
  background: #007acc;
  color: white;
  border-color: #007acc;
  font-weight: 500;
}

.action-btn.primary:hover {
  background: #005a9e;
  border-color: #005a9e;
}

.action-btn:hover {
  background: #f3f4f6;
  border-color: #d1d5db;
  color: #374151;
}

/* Typing indicator */
.typing .message-content {
  padding: 8px 0;
}

.typing-indicator {
  display: flex;
  gap: 4px;
  align-items: center;
}

.typing-indicator span {
  width: 6px;
  height: 6px;
  background: #9ca3af;
  border-radius: 50%;
  animation: typing 1.4s infinite ease-in-out;
}

.typing-indicator span:nth-child(2) {
  animation-delay: 0.2s;
}

.typing-indicator span:nth-child(3) {
  animation-delay: 0.4s;
}

@keyframes typing {
  0%, 60%, 100% {
    transform: translateY(0);
    opacity: 0.4;
  }
  30% {
    transform: translateY(-10px);
    opacity: 1;
  }
}

/* File Preview Area */
.file-preview-area {
  border-top: 1px solid #e1e5e9;
  background: #f8f9fa;
  padding: 12px 20px;
}

.file-preview-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 8px;
}

.file-count {
  font-size: 13px;
  color: #666;
  font-weight: 500;
}

.clear-files-btn {
  background: none;
  border: none;
  padding: 4px;
  border-radius: 4px;
  cursor: pointer;
  color: #999;
  display: flex;
  align-items: center;
  justify-content: center;
}

.clear-files-btn:hover {
  background: #e9ecef;
  color: #666;
}

.file-preview-list {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.file-preview-item {
  display: flex;
  align-items: center;
  gap: 8px;
  background: white;
  border: 1px solid #e1e5e9;
  border-radius: 8px;
  padding: 8px 12px;
  font-size: 13px;
  max-width: 200px;
}

.file-icon {
  color: #666;
  flex-shrink: 0;
}

.file-info {
  flex: 1;
  min-width: 0;
}

.file-name {
  font-weight: 500;
  color: #333;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.file-size {
  color: #999;
  font-size: 11px;
}

.remove-file-btn {
  background: none;
  border: none;
  padding: 2px;
  border-radius: 3px;
  cursor: pointer;
  color: #999;
  flex-shrink: 0;
}

.remove-file-btn:hover {
  background: #f8f9fa;
  color: #666;
}

/* Attached Files in Messages */
.attached-files {
  margin-bottom: 12px;
  padding: 12px;
  background: #f8f9fa;
  border-radius: 8px;
  border: 1px solid #e1e5e9;
}

.file-item {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 6px 0;
  font-size: 13px;
}

.file-item:not(:last-child) {
  border-bottom: 1px solid #e1e5e9;
  padding-bottom: 10px;
  margin-bottom: 4px;
}

/* Input Area */
.chat-input-area {
  border-top: 1px solid #e1e5e9;
  background: #ffffff;
  padding: 16px 20px;
}

.input-container {
  display: flex;
  gap: 8px;
  align-items: flex-end;
}

.input-container textarea {
  flex: 1;
  resize: none;
  border: 1px solid #d1d5db;
  border-radius: 8px;
  padding: 10px 12px;
  font-size: 14px;
  line-height: 1.4;
  font-family: inherit;
  background: #ffffff;
  transition: border-color 0.2s;
  min-height: 20px;
  max-height: 120px;
}

.input-container textarea:focus {
  outline: none;
  border-color: #007acc;
}

.input-container textarea::placeholder {
  color: #9ca3af;
}

.send-btn {
  padding: 10px;
  background: #007acc;
  color: white;
  border: none;
  border-radius: 8px;
  cursor: pointer;
  transition: all 0.2s;
  display: flex;
  align-items: center;
  justify-content: center;
  min-width: 40px;
  height: 40px;
}

.send-btn:hover:not(:disabled) {
  background: #005a9e;
}

.send-btn:disabled {
  background: #d1d5db;
  cursor: not-allowed;
}

.loading-spinner {
  width: 16px;
  height: 16px;
  border: 2px solid transparent;
  border-top: 2px solid white;
  border-radius: 50%;
  animation: spin 1s linear infinite;
}

@keyframes spin {
  0% { transform: rotate(0deg); }
  100% { transform: rotate(360deg); }
}

.input-hints {
  margin-top: 8px;
  font-size: 11px;
  color: #9ca3af;
  text-align: center;
}

.input-hints kbd {
  background: #f3f4f6;
  border: 1px solid #d1d5db;
  border-radius: 3px;
  padding: 1px 4px;
  font-size: 10px;
  font-family: monospace;
}

/* Scrollbar styling */
.chat-messages::-webkit-scrollbar {
  width: 6px;
}

.chat-messages::-webkit-scrollbar-track {
  background: transparent;
}

.chat-messages::-webkit-scrollbar-thumb {
  background: #d1d5db;
  border-radius: 3px;
}

.chat-messages::-webkit-scrollbar-thumb:hover {
  background: #9ca3af;
}
</style>
