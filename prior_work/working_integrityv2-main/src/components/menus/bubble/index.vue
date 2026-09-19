<template>
  <template v-if="editor?.isActive('toc') || editor?.isActive('pagination') || editor?.isActive('horizontalRule') || editor?.getAttributes('image').error">
    </template>

  <template v-else-if="editor?.isActive('image') && !editor?.getAttributes('image').error">
    <menus-toolbar-base-align-left />
    <menus-toolbar-base-align-center />
    <menus-toolbar-base-align-right />
    <div class="divider"></div>
    <menus-bubble-image-flip />
    <menus-bubble-image-proportion />
    <menus-bubble-image-draggable />
    <menus-bubble-image-reset />
    <div class="divider"></div>
    <menus-bubble-image-remove-background v-if="editor?.getAttributes('image')?.type === 'image' || ['image/png', 'image/jpeg'].includes(editor?.getAttributes('image')?.type)" />
    <menus-bubble-image-preview v-if="editor?.getAttributes('image')?.type === 'image' || ['image/png', 'image/jpeg'].includes(editor?.getAttributes('image')?.type)" />
    <menus-bubble-image-open />
    <div class="divider"></div>
    <menus-bubble-image-edit />
    <menus-bubble-node-delete />
  </template>

  <template v-else-if="editor?.isActive('video') || editor?.isActive('audio') || editor?.isActive('file') || editor?.isActive('iframe')">
    <menus-toolbar-base-align-left />
    <menus-toolbar-base-align-center />
    <menus-toolbar-base-align-right />
    <div class="divider"></div>
    <menus-bubble-file-download v-if="editor?.isActive('file') || editor?.isActive('video') || editor?.isActive('audio')" />
    <menus-bubble-node-delete />
  </template>

  <template v-else-if="editor?.isActive('table')">
    <menus-toolbar-table-cells-align />
    <menus-toolbar-table-cells-background />
    <div class="divider"></div>
    <menus-toolbar-table-add-row-before />
    <menus-toolbar-table-add-row-after />
    <menus-toolbar-table-add-column-before />
    <menus-toolbar-table-add-column-after />
    <div class="divider"></div>
    <menus-toolbar-table-delete-row />
    <menus-toolbar-table-delete-column />
    <div class="divider"></div>
    <menus-toolbar-table-merge-cells />
    <menus-toolbar-table-split-cell />

     <div class="divider"></div>
    <MenuToolBarAICalculator />
  </template>

  <template v-else-if="editor?.isActive('codeBlock')">
    <menus-bubble-code-languages />
    <menus-bubble-code-themes />
    <div class="divider"></div>
    <menus-bubble-code-line-numbers />
    <menus-bubble-code-word-wrap />
    <div class="divider"></div>
    <menus-bubble-code-copy />
    <menus-bubble-node-delete />
  </template>

  <template v-else>
    <div
      class="fix-grammar-btn bubble-btn"
      @click="fixGrammar"
      @mouseenter="grammarTooltipVisible = true"
      @mouseleave="grammarTooltipVisible = false"
      :title="'Fix Grammar'"
    >
      <span v-if="isGrammarLoading" style="animation: spin 1s linear infinite;">⟳</span>
      <span v-else style="font-size: 11px; font-weight: bold;">Aa</span>

      <div
        v-if="grammarTooltipVisible"
        class="bubble-tooltip"
      >
        Fix Grammar
      </div>
    </div>
    <div class="divider"></div>
    <menus-toolbar-base-font-size :select="false" />
    <div class="divider"></div>
    <menus-toolbar-base-bold />
    <menus-toolbar-base-italic />
    <menus-toolbar-base-underline />
    <menus-toolbar-base-strike />
    <div class="divider"></div>
    <menus-toolbar-base-align-dropdown />
    <div class="divider"></div>
    <menus-toolbar-base-color />
    <menus-toolbar-base-background-color />
    <menus-toolbar-base-highlight />
    <div class="divider"></div>

    <div
      class="beautify-equation-btn bubble-btn"
      @click="beautifyLatex"
      @mouseenter="latexTooltipVisible = true"
      @mouseleave="latexTooltipVisible = false"
      :title="'Beautify Equation'"
    >
      <span v-if="isLatexLoading" style="animation: spin 1s linear infinite;">⟳</span>
      <span v-else>Σ</span>

      <div
        v-if="latexTooltipVisible"
        class="bubble-tooltip"
      >
        Beautify Equation
      </div>
    </div>

    <div
      class="ai-mathematics-btn bubble-btn"
      @click="aiMathematics"
      @mouseenter="aiMathematicsTooltipVisible = true"
      @mouseleave="aiMathematicsTooltipVisible = false"
      :title="'AI Mathematics'"
    >
      <span v-if="isAiMathematicsLoading" style="animation: spin 1s linear infinite;">⟳</span>
      <span v-else>π</span>

      <div
        v-if="aiMathematicsTooltipVisible"
        class="bubble-tooltip"
      >
        Mathematics
      </div>
    </div>

    <div
      class="generate-graph-btn bubble-btn"
      @click="generateGraph"
      @mouseenter="graphTooltipVisible = true"
      @mouseleave="graphTooltipVisible = false"
      :title="'Generate Graph'"
    >
  <span v-if="isGraphLoading" style="animation: spin 1s linear infinite;">⟳</span>
  <span v-else>📊</span>

  <div
    v-if="graphTooltipVisible"
    class="bubble-tooltip"
  >
    Generate Graph
  </div>
</div>

    <!-- <div
      class="citations-btn"
      @click="getCitations"
      @mouseenter="citationsTooltipVisible = true"
      @mouseleave="citationsTooltipVisible = false"
      :style="{
        position: 'relative',
        display: 'inline-flex',
        alignItems: 'center',
        justifyContent: 'center',
        width: '24px',
        height: '24px',
        border: '1px solid #ccc',
        background: 'white',
        cursor: 'pointer',
        borderRadius: '4px',
        fontSize: '12px',
        fontWeight: 'bold',
        marginRight: '5px'
      }"
      :title="'Add Citations'"
    >
      <span v-if="isCitationsLoading" style="animation: spin 1s linear infinite;">⟳</span>
      <span v-else>📚</span>

      <div
        v-if="citationsTooltipVisible"
        :style="{
          position: 'absolute',
          top: '-2.2rem',
          left: '50%',
          transform: 'translateX(-50%)',
          background: 'white',
          color: 'black',
          padding: '4px 8px',
          borderRadius: '4px',
          fontSize: '12px',
          whiteSpace: 'nowrap',
          zIndex: 1001
        }"
      >
        Add Citations
      </div>
    </div> -->



    <!-- <div class="divider"></div> -->

    <slot name="bubble_menu" />
  </template>

  <GraphModal
    :visible="graphModalVisible"
    :config="graphConfig"
    @close="graphModalVisible = false"
    @insert="insertGraphImage"
  />
</template>

<script setup>
import { ref, computed, onUnmounted,nextTick } from 'vue'
import axios from 'axios'
import { API_URL } from '@/utils/api-url.js'
import { useStore } from '@/composables/store.js'
import MenuToolBarAICalculator from './components/MenuToolBarAICalculator.vue'
import GraphModal from './components/GraphModal.vue'
// import debounce from 'lodash/debounce'
const { options, editor } = useStore()

// Reactive state for all functionalities
const isLatexLoading = ref(false)
const isGrammarLoading = ref(false)
const grammarTooltipVisible = ref(false)
const grammarAbortController = ref(null)

const isAiMathematicsLoading = ref(false)
const isCitationsLoading = ref(false)

// Tooltip visibility states
const latexTooltipVisible = ref(false)
const aiMathematicsTooltipVisible = ref(false)
const citationsTooltipVisible = ref(false)

// Abort controllers for cancelling requests
const latexAbortController = ref(null)
const aiMathematicsAbortController = ref(null)
const citationsAbortController = ref(null)



const isGraphLoading = ref(false)
const graphTooltipVisible = ref(false)
const graphAbortController = ref(null)
const graphModalVisible = ref(false)
const graphConfig = ref(null)
const graphInsertRange = ref(null)

// Enhanced UX states
const bubbleVisible = ref(false)
const isButtonProcessing = ref(false)


// Backend URLs
// Ensure your .env.local or .env.development file has these:
// VITE_LAMBDA_BACKEND_URL=https://jfv6blghbfv5lr3wt6sho4kewe0mrifm.lambda-url.us-east-1.on.aws
// VITE_AI_MATH_SOLVER_URL=https://ai-math-solver-production.up.railway.app/solve
const LAMBDA_BACKEND_URL = import.meta.env.VITE_LAMBDA_BACKEND_URL || 'https://jfv6blghbfv5lr3wt6sho4kewe0mrifm.lambda-url.us-east-1.on.aws'
const AI_MATH_SOLVER_URL = import.meta.env.VITE_AI_MATH_SOLVER_URL || 'https://ai-math-solver-production.up.railway.app/solve'


// Extract user_id from query parameters
const userId = computed(() => {
  if (typeof window === 'undefined') return null; // Ensure this runs client-side only
  const urlParams = new URLSearchParams(window.location.search);
  return urlParams.get('user_id');
})

// Debug log
console.log('Vue script setup running, editor:', editor.value)
console.log('Lambda Backend URL:', LAMBDA_BACKEND_URL)
console.log('AI Math Solver URL:', AI_MATH_SOLVER_URL)
console.log('User ID from query params:', userId.value) // Log the extracted user ID

// Save progress functionality for TOK templates - integrated with existing system  
const saveTokProgress = async () => {
  console.log('🚀 saveTokProgress called!')
  
  // Safe checks to prevent null reference errors
  const editorAvailable = editor?.value != null
  const userIdAvailable = userId?.value != null
  
  console.log('📊 Editor available:', editorAvailable)
  console.log('📊 UserId available:', userIdAvailable, 'Value:', userId?.value)
  
  if (!editorAvailable || !userIdAvailable) {
    console.warn('❌ Editor or userId not available for save progress')
    console.log('Editor:', editor?.value)
    console.log('UserId:', userId?.value)
    return
  }

  try {
    // Get the template type and ID from URL parameters
    const urlParams = new URLSearchParams(window.location.search)
    const templateType = getTemplateTypeFromURL()
    const tokId = urlParams.get('document_id') || urlParams.get('tok_id') || urlParams.get('sessionId') || getIdFromURL()

    console.log('🔍 Template Type:', templateType)
    console.log('🔍 TOK ID:', tokId)
    console.log('🔍 URL:', window.location.href)
    console.log('🔍 All URL params:', Array.from(urlParams.entries()))

    if (!tokId) {
      console.warn('❌ No TOK document ID found in URL')
      return
    }

    // Get main editor content safely
    let mainContent = ''
    try {
      mainContent = editor.value?.getHTML() || ''
      console.log('📝 Editor content length:', mainContent.length)
    } catch (e) {
      console.error('❌ Failed to get editor content:', e)
      mainContent = ''
    }
    
    // Get comprehensive template-specific data
    let leftSidebarData = {}
    let rightSidebarData = {}
    let essayContentData = []
    let selectedReferencesData = []
    
    try {
      // Get TOK Essay data (AOK1, AOK2, citation style)
      if (templateType === 'tok-essay') {
        console.log('🔍 Collecting TOK Essay data...')
        
        // Try multiple selectors for AOK1
        const aok1Input = document.querySelector('#tokAok1') || 
                         document.querySelector('input[placeholder*="History"]') ||
                         document.querySelector('input[placeholder*="e.g., History"]')
        
        // Try multiple selectors for AOK2  
        const aok2Input = document.querySelector('#tokAok2') ||
                         document.querySelector('input[placeholder*="Natural Sciences"]') ||
                         document.querySelector('input[placeholder*="e.g., Natural Sciences"]')
        
        // Try multiple selectors for citation style
        const citationSelect = document.querySelector('select[v-model="tokEssay.citationStyle"]') || 
                              document.querySelector('.card select') ||
                              document.querySelectorAll('select')[0] // get first select element
        
        console.log('🔍 TOK Essay DOM elements found:')
        console.log('- AOK1 input:', !!aok1Input, 'value:', aok1Input?.value)
        console.log('- AOK2 input:', !!aok2Input, 'value:', aok2Input?.value)
        console.log('- Citation select:', !!citationSelect, 'value:', citationSelect?.value)
        
        leftSidebarData = {
          aok1: aok1Input?.value || '',
          aok2: aok2Input?.value || '', 
          citationStyle: citationSelect?.value || '',
          wordCount: 1700 // default
        }
        
        console.log('🔍 TOK Essay data collected:', leftSidebarData)
      }
      
      // Get TOK Journal data (title, instructions, citation style, word count)
      else if (templateType === 'tok') {
        console.log('🔍 Collecting TOK Journal data...')
        
        const titleInput = document.querySelector('#tokJournalTitle')
        const instructionsInput = document.querySelector('#tokJournalInstructions')  
        const citationSelect = document.querySelector('#tokJournalCitation') ||
                              document.querySelector('select[v-model="tokJournal.citationStyle"]') ||
                              document.querySelectorAll('select')[0]
        
        // Get word count from the word count field
        const wordCountInput = document.querySelector('input[v-model="customWordCount"]') ||
                              document.querySelector('input[type="number"]') ||
                              document.querySelector('input[placeholder*="word"]')
        
        console.log('🔍 TOK Journal DOM elements found:')
        console.log('- Title input:', !!titleInput, 'value:', titleInput?.value)
        console.log('- Instructions textarea:', !!instructionsInput, 'value:', instructionsInput?.value?.substring(0, 50) + '...')
        console.log('- Citation select:', !!citationSelect, 'value:', citationSelect?.value)
        console.log('- Word count input:', !!wordCountInput, 'value:', wordCountInput?.value)
        
        leftSidebarData = {
          title: titleInput?.value || '',
          instructions: instructionsInput?.value || '',
          citationStyle: citationSelect?.value || '',
          wordCount: wordCountInput?.value || 350
        }
        
        console.log('🔍 TOK Journal data collected:', leftSidebarData)
      }
      
      // Get TOK Exhibition data (prompt, objects, references, citation format)
      else if (templateType === 'tok-exhibition') {
        console.log('🔍 Collecting TOK Exhibition data...')
        
        // Try to get data from Vue reactive state or window object
        let tokExhibitionData = {}
        
        // Try to access Vue component data first
        try {
          // Check if we can access the component instance
          const vueApp = document.querySelector('#app').__vue__
          if (vueApp && vueApp.$data && vueApp.$data.tokExhibition) {
            tokExhibitionData = vueApp.$data.tokExhibition
            console.log('✅ Found TOK Exhibition data from Vue component')
          }
        } catch (e) {
          console.log('⚠️ Could not access Vue component data, trying window object')
        }
        
        // Fallback to window object
        if (Object.keys(tokExhibitionData).length === 0) {
          tokExhibitionData = window.tokExhibition || {}
          console.log('📊 Using TOK Exhibition data from window object')
        }
        
        // Also try to collect current step from DOM
        const currentStep = document.querySelector('.exhibition-step h4')?.textContent?.includes('Select TOK Prompt') ? 1 :
                           document.querySelector('.exhibition-step h4')?.textContent?.includes('Select 3 Objects') ? 2 :
                           document.querySelector('.exhibition-step h4')?.textContent?.includes('Select References') ? 3 :
                           document.querySelector('.exhibition-step h4')?.textContent?.includes('Exhibition Essay Generated') ? 4 : 1
        
        leftSidebarData = {
          availablePrompts: tokExhibitionData.availablePrompts || [],
          selectedPrompt: tokExhibitionData.selectedPrompt || null,
          selectedPromptNumber: tokExhibitionData.selectedPromptNumber || null,
          suggestedObjects: tokExhibitionData.suggestedObjects || [],
          selectedObjects: tokExhibitionData.selectedObjects || [],
          exhibitionReferences: tokExhibitionData.exhibitionReferences || [],
          selectedExhibitionReferences: tokExhibitionData.selectedExhibitionReferences || [],
          citationFormat: tokExhibitionData.citationFormat || 'APA7',
          currentStep: tokExhibitionData.currentStep || currentStep
        }
        
        console.log('🔍 TOK Exhibition data collected:')
        console.log('- Available prompts:', leftSidebarData.availablePrompts.length)
        console.log('- Selected prompt:', !!leftSidebarData.selectedPrompt)
        console.log('- Selected objects:', leftSidebarData.selectedObjects.length)
        console.log('- Selected references:', leftSidebarData.selectedExhibitionReferences.length)
        console.log('- Current step:', leftSidebarData.currentStep)
      }
      
      // Get right sidebar content (generated content/outline)
      const rightSidebar = document.querySelector('.sidebar.right .toc-content')
      if (rightSidebar) {
        rightSidebarData = {
          outline: rightSidebar.innerHTML || '',
          outlineText: rightSidebar.textContent || ''
        }
        console.log('📊 Right sidebar outline captured, length:', rightSidebarData.outline.length)
      }
      
      // Get essay content sections if available
      if (window.essayContent && Array.isArray(window.essayContent)) {
        essayContentData = window.essayContent.map(section => ({
          title: section.title || '',
          content: section.content || '',
          expanded: section.expanded || false
        }))
        console.log('📊 Essay content sections captured:', essayContentData.length)
      }
      
      // Get selected references if available  
      if (window.selectedReferences && Array.isArray(window.selectedReferences)) {
        selectedReferencesData = [...window.selectedReferences]
        console.log('📊 Selected references captured:', selectedReferencesData.length)
      }
      
    } catch (e) {
      console.warn('⚠️ Could not access template-specific data:', e)
    }

    // Create comprehensive save data matching the expected API structure  
    const saveData = {
      tok_id: tokId,
      user_id: userId.value,
      data: {
        templateType,
        leftSidebarData,
        rightSidebarData, 
        mainContent,
        essayContent: essayContentData,
        selectedReferences: selectedReferencesData,
        timestamp: new Date().toISOString()
      }
    }

    console.log('💾 Saving TOK progress with data:', saveData)
    console.log('📡 API URL:', `${LAMBDA_BACKEND_URL}/save-progress`)

    const response = await axios.post(
      `${LAMBDA_BACKEND_URL}/save-progress`,
      saveData,
      {
        headers: {
          'Content-Type': 'application/json'
        }
      }
    )

    console.log('✅ TOK progress saved successfully:', response.data)
    return response.data

  } catch (error) {
    console.error('❌ Error saving TOK progress:', error)
    console.error('❌ Error details:', {
      message: error.message,
      response: error.response?.data,
      status: error.response?.status
    })
    // Don't show error notification to user for auto-saves
    if (error.showNotification !== false) {
      showNotification('Failed to save progress', 'error')
    }
    throw error // Re-throw so calling code knows it failed
  }
}

// Helper functions to determine template type and ID
const getTemplateTypeFromURL = () => {
  const path = window.location.pathname
  const search = window.location.search
  
  console.log('🔍 Detecting template type from URL:')
  console.log('- Path:', path)
  console.log('- Search:', search)
  
  // Check query parameters first (most reliable)
  if (search.includes('selectmodule=tok_essay') || search.includes('selectmodule=tok-essay')) {
    console.log('✅ Detected: tok-essay from query params')
    return 'tok-essay'
  }
  if (search.includes('selectmodule=tok-exhibition')) {
    console.log('✅ Detected: tok-exhibition from query params')
    return 'tok-exhibition'
  }
  if (search.includes('selectmodule=tok')) {
    console.log('✅ Detected: tok from query params')
    return 'tok'
  }
  if (search.includes('selectmodule=essay')) {
    console.log('✅ Detected: essay from query params')
    return 'essay'
  }
  
  // Check URL path as fallback
  if (path.includes('tok-essay')) {
    console.log('✅ Detected: tok-essay from path')
    return 'tok-essay'
  }
  if (path.includes('tok-exhibition')) {
    console.log('✅ Detected: tok-exhibition from path')
    return 'tok-exhibition'
  }
  if (path.includes('tok-journal') || path.includes('tok')) {
    console.log('✅ Detected: tok from path')
    return 'tok'
  }
  if (path.includes('essay')) {
    console.log('✅ Detected: essay from path')
    return 'essay'
  }
  
  console.warn('⚠️ Could not detect template type, defaulting to general')
  return 'general'
}

const getIdFromURL = () => {
  const path = window.location.pathname
  const segments = path.split('/')
  return segments[segments.length - 1] || segments[segments.length - 2]
}

// Helper function to show notifications (replace with your notification system)
const showNotification = (message, type = 'info') => {
  console.log(`[${type.toUpperCase()}] ${message}`)
  // Only show console logs, no alerts for better UX
  // You can replace this with your Vue notification system if needed
}

// Helper function to get selected text and range
const getSelection = () => {
  if (!editor.value) return null

  const { from, to } = editor.value.state.selection
  if (from === to) return null

  const selectedText = editor.value.state.doc.textBetween(from, to, "\n", " ").trim()
  return { from, to, selectedText }
}




// const generateGraph = async () => {
//   console.log('generateGraph called')

//   const selection = getSelection()
//   if (!selection) {
//     showNotification('Please select some text or table data', 'error')
//     return
//   }

//   const { from, to, selectedText } = selection

//   // Abort any existing request
//   if (graphAbortController.value) {
//     graphAbortController.value.abort()
//   }

//   graphAbortController.value = new AbortController()

//   try {
//     isGraphLoading.value = true

  
//     const isTable = editor.value.isActive('table')
    
//     const formData = new FormData()
//     formData.append('input_type', isTable ? 'table' : 'text')
//     formData.append('description', selectedText)
    
//     if (isTable) {
  
//       const tableContent = getTableContent()
//       formData.append('text_input', tableContent)
//     } else {
//       formData.append('text_input', selectedText)
//     }

//     const response = await axios.post(
//       `${LAMBDA_BACKEND_URL}/api/generate-graph`,
//       formData,
//       {
//         signal: graphAbortController.value.signal,
//         headers: {
//           'Content-Type': 'multipart/form-data'
//         }
//       }
//     )

 
//     const currentSelection = editor.value.state.selection
//     if (currentSelection.from !== from || currentSelection.to !== to) {
//       showNotification('Graph Generation Aborted: Selection changed', 'error')
//       return
//     }

//     const imageData = response.data.image
//     if (!imageData) {
//       showNotification('No graph image was generated', 'error')
//       return
//     }


//     editor.value
//       .chain()
//       .focus()
//       .deleteRange({ from, to })
//       .setImage({ src: imageData })
//       .run()

//     showNotification('Graph generated successfully!', 'success')

//   } catch (error) {
//     if (axios.isCancel(error)) {
//       showNotification('Graph Generation Aborted', 'error')
//     } else {
//       console.error("Error in generateGraph:", error)
//       showNotification('Failed to generate graph', 'error')
//     }
//   } finally {
//     isGraphLoading.value = false
//   }
// }
// Replace your generateGraph function with this:

// const generateGraph = debounce(async () => {
//   console.log('generateGraph called')

//   if (isGraphLoading.value || graphAbortController.value) {
//     console.log('Graph generation already in progress, ignoring call')
//     return
//   }
  
//   const selection = getSelection()
//   if (!selection) {
//     showNotification('Please select some text or table data', 'error')
//     return
//   }

//   const { from, to, selectedText } = selection

//   if (graphAbortController.value) {
//     graphAbortController.value.abort()
//   }

//   graphAbortController.value = new AbortController()

//   try {
//     isGraphLoading.value = true
    
//     // Store the original positions before making the API call
//     const originalFrom = from
//     const originalTo = to
    
//     const formData = new FormData()
//     formData.append('input_type', 'text')
//     formData.append('description', selectedText)
//     formData.append('text_input', selectedText)

//     const response = await axios.post(
//       `${LAMBDA_BACKEND_URL}/api/generate-graph`,
//       formData,
//       {
//         signal: graphAbortController.value.signal,
//         headers: {
//           'Content-Type': 'multipart/form-data'
//         },
//         timeout: 30000
//       }
//     )
    
//     const imageData = response.data?.image
//     if (!imageData) {
//       showNotification('No graph image was generated', 'error')
//       return
//     }
    
//     // Get the current document size
//     const docSize = editor.value.state.doc.content.size
    
//     // Calculate safe positions for replacement
//     const safeFrom = Math.min(originalFrom, docSize)
//     const safeTo = Math.min(originalTo, docSize)
    
//     // If the entire selection is out of range, insert at the end
//     if (safeFrom >= docSize) {
//       editor.value
//         .chain()
//         .focus()
//         .insertContentAt(docSize, { type: 'image', attrs: { src: imageData } })
//         .run()
//     } else {
//       // Otherwise, replace the original selection (or what's left of it)
//       editor.value
//         .chain()
//         .focus()
//         .deleteRange({ from: safeFrom, to: safeTo })
//         .insertContentAt(safeFrom, { type: 'image', attrs: { src: imageData } })
//         .run()
//     }
    
//     showNotification('Graph generated successfully!', 'success')
    
//   } catch (error) {
//     if (axios.isCancel(error)) {
//       console.log('Graph generation was cancelled')
//       showNotification('Graph Generation Cancelled', 'info')
//     } else if (error.code === 'ECONNABORTED') {
//       console.error("Request timeout:", error)
//       showNotification('Graph generation timed out', 'error')
//     } else {
//       console.error("Error in generateGraph:", error)
//       showNotification(
//         `Failed to generate graph: ${error.response?.data?.message || error.message}`, 
//         'error'
//       )
//     }
//   } finally {
//     isGraphLoading.value = false
//     if (graphAbortController.value) {
//       graphAbortController.value = null
//     }
    
//   }
// }, 500, { leading: true, trailing: false })
// Advanced mathematical expression processor

const generateGraph = async () => {
  if (isGraphLoading.value) return

  const selection = getSelection()
  if (!selection) {
    showNotification('Please select some text', 'error')
    return
  }

  const { from, to, selectedText } = selection
  graphInsertRange.value = { from, to }
  isGraphLoading.value = true

  if (graphAbortController.value) {
    graphAbortController.value.abort()
  }
  graphAbortController.value = new AbortController()

  try {
    const response = await axios.post(
      `${API_URL}/api/generate-graph`,
      { text: selectedText },
      {
        signal: graphAbortController.value.signal,
        headers: { 'Content-Type': 'application/json' },
        timeout: 30000,
      }
    )

    graphConfig.value = response.data
    graphModalVisible.value = true
  } catch (error) {
    if (axios.isCancel(error)) {
      showNotification('Graph generation cancelled', 'info')
    } else {
      console.error('Graph generation error:', error)
      showNotification('Failed to generate graph. Try a clearer expression.', 'error')
    }
  } finally {
    isGraphLoading.value = false
    graphAbortController.value = null
  }
}

const insertGraphImage = (dataUrl) => {
  graphModalVisible.value = false
  if (!graphInsertRange.value || !editor.value) return

  const { from, to } = graphInsertRange.value
  const tr = editor.value.state.tr
  tr.delete(from, to)
  const imageNode = editor.value.schema.nodes.image.create({ src: dataUrl })
  tr.insert(from, imageNode)
  editor.value.view.dispatch(tr)

  nextTick(() => editor.value.commands.blur())
  showNotification('Graph inserted!', 'success')
  graphInsertRange.value = null
}

const getTableContent = () => {
  if (!editor.value.isActive('table')) return ''
  

  const { selection } = editor.value.state
  const { from, to } = selection
  
  let tableContent = ''
  for (let i = from; i <= to; i++) {
    const node = editor.value.state.doc.nodeAt(i)
    if (node && node.type.name === 'table_cell') {
      tableContent += node.textContent + '\t'
    } else if (node && node.type.name === 'table_row') {
      tableContent += '\n'
    }
  }
  
  return tableContent.trim()
}


// Beautify LaTeX function
const beautifyLatex = async () => {
  console.log('beautifyLatex called')

  const selection = getSelection()
  if (!selection) {
    showNotification('Please select some text', 'error')
    return
  }

  const { from, to, selectedText } = selection

  // Abort any existing request
  if (latexAbortController.value) {
    latexAbortController.value.abort()
  }

  latexAbortController.value = new AbortController()

  try {
    isLatexLoading.value = true

    const response = await axios.post(
      `${API_URL}/api/beautify-equation`,
      { text: selectedText },
      {
        signal: latexAbortController.value.signal,
        headers: {
          'Content-Type': 'application/json'
        }
      }
    )

    // Check if selection hasn't changed
    const currentSelection = editor.value.state.selection
    if (currentSelection.from !== from || currentSelection.to !== to) {
      showNotification('LaTeX Beautify Aborted: Selection changed', 'error')
      return
    }

    // Backend should return PURE LaTeX without delimiters
    const latexEquation = response.data.replace(/^\$+|\$+$/g, '')

    if (!latexEquation) {
      showNotification('No LaTeX equation found for the selected text', 'error')
      return
    }

    console.log('Received LaTeX:', latexEquation)

    // Replace the selected text with wrapped LaTeX
   editor.value
  .chain()
  .focus()
  .deleteRange({ from, to })
  .insertInlineMath({ latex: latexEquation })
  .run()

    showNotification('LaTeX equation inserted successfully!', 'success')

  } catch (error) {
    if (axios.isCancel(error)) {
      showNotification('LaTeX Beautify Aborted', 'error')
    } else {
      console.error("Error in beautifyLatex:", error)
      showNotification('Failed to get LaTeX equation from API', 'error')
    }
  } finally {
    isLatexLoading.value = false
  }
}

// Fix Grammar function
const fixGrammar = async () => {
  const selection = getSelection()
  if (!selection) {
    showNotification('Please select some text', 'error')
    return
  }

  const { from, to, selectedText } = selection

  if (grammarAbortController.value) {
    grammarAbortController.value.abort()
  }

  grammarAbortController.value = new AbortController()

  try {
    isGrammarLoading.value = true

    const response = await axios.post(
      `${API_URL}/api/fix-grammar`,
      { text: selectedText },
      {
        signal: grammarAbortController.value.signal,
        headers: { 'Content-Type': 'application/json' }
      }
    )

    const currentSelection = editor.value.state.selection
    if (currentSelection.from !== from || currentSelection.to !== to) {
      showNotification('Grammar fix aborted: selection changed', 'error')
      return
    }

    const corrected = response.data.corrected_text
    if (!corrected) {
      showNotification('No corrections returned', 'error')
      return
    }

    editor.value
      .chain()
      .focus()
      .deleteRange({ from, to })
      .insertContent(corrected, { parseOptions: { preserveWhitespace: 'full' } })
      .run()

    showNotification('Grammar fixed!', 'success')
  } catch (error) {
    if (axios.isCancel(error)) {
      showNotification('Grammar fix aborted', 'error')
    } else {
      console.error('Error in fixGrammar:', error)
      showNotification('Failed to fix grammar', 'error')
    }
  } finally {
    isGrammarLoading.value = false
  }
}

// AI Mathematics function
const aiMathematics = async () => {
  console.log('aiMathematics called')

  const selection = getSelection()
  if (!selection) {
    showNotification('Please select some text', 'error')
    return
  }

  const { from, to, selectedText } = selection

  // Abort any existing request
  if (aiMathematicsAbortController.value) {
    aiMathematicsAbortController.value.abort()
  }

  aiMathematicsAbortController.value = new AbortController()

  try {
    isAiMathematicsLoading.value = true

    console.log('Sending request to:', `${AI_MATH_SOLVER_URL}`)
    console.log('Request payload:', { question: selectedText })

    const response = await axios.post(
      `${AI_MATH_SOLVER_URL}`, // Uses the full URL from AI_MATH_SOLVER_URL constant
      { question: selectedText },
      {
        signal: aiMathematicsAbortController.value.signal,
        headers: {
          'Content-Type': 'application/json'
        }
      }
    )

    console.log('Full API response:', response)
    console.log('Response data:', response.data)
    console.log('Response status:', response.status)

    // Check if selection hasn't changed
    const currentSelection = editor.value.state.selection
    if (currentSelection.from !== from || currentSelection.to !== to) {
      showNotification('AI Mathematics Aborted: Selection changed', 'error')
      return
    }

    // Handle different possible response formats
    let latexEquation = ''

    if (typeof response.data === 'string') {
      // If response.data is directly a string (like "$5 + 5 = 10$")
      latexEquation = response.data.replace(/^\$+|\$+$/g, '')
    } else if (response.data && response.data.solution) {
      // If response has a solution property
      latexEquation = response.data.solution.replace(/^\$+|\$+$/g, '')
    } else if (response.data && response.data.result) {
      // If response has a result property
      latexEquation = response.data.result.replace(/^\$+|\$+$/g, '')
    } else if (response.data && response.data.answer) {
      // If response has an answer property
      latexEquation = response.data.answer.replace(/^\$+|\$+$/g, '')
    } else {
      console.error('Unexpected response format:', response.data)
      showNotification('Unexpected response format from API', 'error')
      return
    }

    if (!latexEquation || latexEquation.trim() === '') {
      showNotification('No LaTeX equation found for the selected text', 'error')
      return
    }

    console.log('Processed LaTeX equation:', latexEquation)

    editor.value
  .chain()
  .focus()
  .deleteRange({ from, to })
  .insertInlineMath({ latex: latexEquation })
  .run()


    showNotification('LaTeX equation inserted successfully!', 'success')

  } catch (error) {
    if (axios.isCancel(error)) {
      showNotification('AI Mathematics Aborted', 'error')
    } else {
      console.error("Error in aiMathematics:", error)
      console.error("Error details:", {
        message: error.message,
        response: error.response,
        status: error.response?.status,
        data: error.response?.data
      })

      if (error.response?.status === 404) {
        showNotification('API endpoint not found. Please check the URL.', 'error')
      } else if (error.response?.status >= 500) {
        showNotification('Server error. Please try again later.', 'error')
      } else if (error.code === 'NETWORK_ERROR') {
        showNotification('Network error. Please check your connection.', 'error')
      } else {
        showNotification(`Failed to get LaTeX equation from API: ${error.message}`, 'error')
      }
    }
  } finally {
    isAiMathematicsLoading.value = false
  }
}

// Citations function
// const getCitations = async () => {
//   console.log('getCitations called')

//   const selection = getSelection()
//   if (!selection) {
//     showNotification('Please select some text', 'error')
//     return
//   }

//   const { from, to, selectedText } = selection

//   // Word count check
//   const wordCount = selectedText.trim().split(/\s+/).filter(word => word.length > 0).length
//   if (wordCount < 10) {
//     showNotification('Please select at least 10 words for citation generation', 'error')
//     return
//   }

//   // Abort any existing request
//   if (citationsAbortController.value) {
//     citationsAbortController.value.abort()
//   }

//   citationsAbortController.value = new AbortController()

//   try {
//     isCitationsLoading.value = true

  
//     // Ensure userId.value is correctly populated from the cookie.
//     if (!userId.value) {
//         showNotification('User ID not found. Please log in or ensure user_id cookie is set.', 'error');
//         return; // Prevent making the request if user_id is missing
//     }

//     const requestBody = {
//       user_id: userId.value, // Use the computed ref's value
//       text: selectedText
//     };

//     console.log('Sending citations request with payload:', requestBody); // Log the payload for verification

//     const response = await axios.post(
//       `${LAMBDA_BACKEND_URL}/api/detect-missing-citations`, // Corrected path: added /api prefix
//       requestBody, // Pass the requestBody object including user_id
//       {
//         signal: citationsAbortController.value.signal,
//         headers: {
//           'Content-Type': 'application/json'
//         }
//       }
//     )

//     // Check if selection hasn't changed
//     const currentSelection = editor.value.state.selection
//     if (currentSelection.from !== from || currentSelection.to !== to) {
//       showNotification('Citations Aborted: Selection changed', 'error')
//       return
//     }

//     const citationsText = response.data.citations || response.data

//     if (!citationsText) {
//       showNotification('No citations found for the selected text', 'error')
//       return
//     }

//     console.log('Received citations:', citationsText)

//     // Append citations to the selected text
//     editor.value
//       .chain()
//       .focus()
//       .setTextSelection(to) // Move cursor to end of selection
//       .insertContent(` ${citationsText}`)
//       .run()

//     showNotification('Citations added successfully!', 'success')

//   } catch (error) {
//     if (axios.isCancel(error)) {
//       showNotification('Citations Aborted', 'error')
//     } else {
//       console.error("Error in getCitations:", error)
//       showNotification('Failed to generate citations', 'error')
//     }
//   } finally {
//     isCitationsLoading.value = false
//   }
// }

// Retrieve progress functionality
const retrieveTokProgress = async () => {
  console.log('🔄 Retrieving TOK progress...')
  
  if (!userId?.value) {
    console.warn('❌ UserId not available for retrieve progress')
    return null
  }

  try {
    // Get the TOK ID from URL parameters
    const urlParams = new URLSearchParams(window.location.search)
    const tokId = urlParams.get('document_id') || urlParams.get('tok_id') || urlParams.get('sessionId') || getIdFromURL()

    if (!tokId) {
      console.warn('❌ No TOK document ID found in URL for retrieval')
      return null
    }

    console.log('📡 Retrieving from URL:', `${LAMBDA_BACKEND_URL}/tok-draft/${tokId}`)

    const response = await axios.get(
      `${LAMBDA_BACKEND_URL}/tok-draft/${tokId}`,
      {
        headers: {
          'Content-Type': 'application/json'
        }
      }
    )

    console.log('✅ TOK progress retrieved successfully:', response.data)
    
    // Load the retrieved data back into the editor and forms
    if (response.data?.payload) {
      const data = response.data.payload
      
      // Load main content into editor
      if (data.mainContent && editor?.value) {
        editor.value.commands.setContent(data.mainContent)
        console.log('📝 Loaded main content into editor')
      }
      
      // Load comprehensive TOK template data back into forms and state
      loadTokTemplateData(data, data.templateType)
      
      // Load right sidebar data if needed
      if (data.rightSidebarData?.outline) {
        console.log('📊 Right sidebar outline data available')
      }
    }

    return response.data

  } catch (error) {
    console.error('❌ Error retrieving TOK progress:', error)
    console.error('❌ Error details:', {
      message: error.message,
      response: error.response?.data,
      status: error.response?.status
    })
    return null
  }
}

// Helper function to load comprehensive TOK template data back into forms
const loadTokTemplateData = (data, templateType) => {
  console.log('🔄 Loading TOK template data:', data, 'for template:', templateType)
  
  try {
    const leftSidebarData = data.leftSidebarData || {}
    const rightSidebarData = data.rightSidebarData || {}
    const essayContent = data.essayContent || []
    const selectedReferences = data.selectedReferences || []
    
    // Load template-specific left sidebar data
    switch (templateType) {
      case 'tok-essay':
        if (leftSidebarData.aok1) {
          const aok1Input = document.querySelector('#tokAok1')
          if (aok1Input) {
            aok1Input.value = leftSidebarData.aok1
            aok1Input.dispatchEvent(new Event('input', { bubbles: true }))
          }
        }
        if (leftSidebarData.aok2) {
          const aok2Input = document.querySelector('#tokAok2')
          if (aok2Input) {
            aok2Input.value = leftSidebarData.aok2
            aok2Input.dispatchEvent(new Event('input', { bubbles: true }))
          }
        }
        if (leftSidebarData.citationStyle) {
          const citationSelect = document.querySelector('.card select')
          if (citationSelect) {
            citationSelect.value = leftSidebarData.citationStyle
            citationSelect.dispatchEvent(new Event('change', { bubbles: true }))
          }
        }
        console.log('✅ TOK Essay data loaded')
        break
        
      case 'tok':
        if (leftSidebarData.title) {
          const titleInput = document.querySelector('#tokJournalTitle')
          if (titleInput) {
            titleInput.value = leftSidebarData.title
            titleInput.dispatchEvent(new Event('input', { bubbles: true }))
          }
        }
        if (leftSidebarData.instructions) {
          const instructionsInput = document.querySelector('#tokJournalInstructions')
          if (instructionsInput) {
            instructionsInput.value = leftSidebarData.instructions
            instructionsInput.dispatchEvent(new Event('input', { bubbles: true }))
          }
        }
        if (leftSidebarData.citationStyle) {
          const citationSelect = document.querySelector('#tokJournalCitation')
          if (citationSelect) {
            citationSelect.value = leftSidebarData.citationStyle
            citationSelect.dispatchEvent(new Event('change', { bubbles: true }))
          }
        }
        console.log('✅ TOK Journal data loaded')
        break
        
      case 'tok-exhibition':
        // Restore TOK Exhibition state to window object for Vue reactivity
        if (window.tokExhibition) {
          Object.assign(window.tokExhibition, {
            availablePrompts: leftSidebarData.availablePrompts || [],
            selectedPrompt: leftSidebarData.selectedPrompt || null,
            selectedPromptNumber: leftSidebarData.selectedPromptNumber || null,
            suggestedObjects: leftSidebarData.suggestedObjects || [],
            selectedObjects: leftSidebarData.selectedObjects || [],
            exhibitionReferences: leftSidebarData.exhibitionReferences || [],
            selectedExhibitionReferences: leftSidebarData.selectedExhibitionReferences || [],
            citationFormat: leftSidebarData.citationFormat || 'APA7',
            currentStep: leftSidebarData.currentStep || 1
          })
        }
        console.log('✅ TOK Exhibition data loaded')
        break
    }
    
    // Load essay content sections if available
    if (essayContent.length > 0) {
      window.essayContent = essayContent
      console.log('✅ Essay content sections loaded:', essayContent.length)
    }
    
    // Load selected references if available
    if (selectedReferences.length > 0) {
      window.selectedReferences = selectedReferences
      console.log('✅ Selected references loaded:', selectedReferences.length)
    }
    
    // Restore saved right sidebar outline (generated outline) if available
    // Inject for TOK Journal and TOK Essay, but only if a container exists and not already filled
    if (rightSidebarData.outline && (templateType === 'tok' || templateType === 'tok-essay')) {
      const injectOutline = (html) => {
        const rightSidebar =
          document.querySelector('.sidebar.right .toc-content') ||
          document.querySelector('.paper-outline-sidebar .toc-content') ||
          document.querySelector('#tokEssayRight .toc-content') ||
          document.querySelector('.tok-essay .toc-content')
        if (rightSidebar) {
          // Don't overwrite if already populated meaningfully
          const already = rightSidebar.innerHTML && rightSidebar.innerHTML.trim().length > 20
          if (!already) {
            rightSidebar.innerHTML = html
            console.log('✅ Restored generated outline in right sidebar')
          } else {
            console.log('ℹ️ Outline container already populated; skipping injection')
          }
          return true
        }
        return false
      }

      // Immediate attempt
      const okNow = injectOutline(rightSidebarData.outline)
      if (!okNow) {
        console.warn('⚠️ Right sidebar container not found; scheduling retries to inject outline')
        // Keep a copy on window so other components can use it if needed
        window.__tokSavedOutlineHTML = rightSidebarData.outline
        // Retry a few times to handle mount timing after tab reopen/navigation
        let attempts = 0
        const maxAttempts = 15
        const timer = setInterval(() => {
          attempts++
          if (injectOutline(window.__tokSavedOutlineHTML)) {
            clearInterval(timer)
          } else if (attempts >= maxAttempts) {
            clearInterval(timer)
            console.warn('⚠️ Failed to inject outline after retries')
          }
        }, 200)
      }
    }
    
    // Optionally render selected references into a known container if it exists
    if (selectedReferences.length > 0 && (templateType === 'tok' || templateType === 'tok-essay')) {
      const refsContainer =
        document.querySelector('.selected-references, #tokSelectedReferences, .references-list') ||
        document.querySelector('#tokEssayReferences') ||
        document.querySelector('.tok-essay .references-list')
      if (refsContainer) {
        try {
          // Render as a simple list; adjust if the template has a different format
          const list = Array.isArray(selectedReferences) ? selectedReferences : [selectedReferences]
          refsContainer.innerHTML = `<ul>${list.map(r => `<li>${typeof r === 'string' ? r : JSON.stringify(r)}</li>`).join('')}</ul>`
          console.log('✅ Rendered selected references into container')
        } catch (e) {
          console.warn('⚠️ Could not render selected references:', e)
        }
      }
    }
    
    console.log('✅ TOK template data loaded successfully')
  } catch (error) {
    console.error('❌ Error loading TOK template data:', error)
  }
}

// Expose TOK save function globally so EditorLayout.vue can call it
if (typeof window !== 'undefined') {
  window.saveTokProgress = saveTokProgress
  window.retrieveTokProgress = retrieveTokProgress
  
  // Also expose for manual calls
  window.editorSaveTokProgress = saveTokProgress
  
  // Add manual test function for debugging
  window.testTokSave = async () => {
    console.log('🧪 Manual test of TOK save function triggered!')
    try {
      await saveTokProgress()
      console.log('✅ Manual test completed successfully')
    } catch (error) {
      console.error('❌ Manual test failed:', error)
    }
  }
  
  // Add manual retrieve test function
  window.testTokRetrieve = async () => {
    console.log('🧪 Manual test of TOK retrieve function triggered!')
    try {
      const result = await retrieveTokProgress()
      console.log('✅ Manual retrieve test completed:', result)
    } catch (error) {
      console.error('❌ Manual retrieve test failed:', error)
    }
  }
  
  // Debug function to check if save is being called from events
  window.checkTokSaveSetup = () => {
    console.log('🔍 TOK Save Setup Check:')
    console.log('- saveTokProgress function available:', typeof window.saveTokProgress)
    console.log('- Editor available:', !!(editor?.value))
    console.log('- UserId available:', !!(userId?.value))
    console.log('- Current URL:', window.location.href)
    console.log('- Template type:', getTemplateTypeFromURL())
    console.log('- Left sidebar present:', !!document.querySelector('.sidebar.left'))
    console.log('- Right sidebar present:', !!document.querySelector('.sidebar.right'))
    
    // Test URL parsing
    const urlParams = new URLSearchParams(window.location.search)
    const tokId = urlParams.get('document_id') || urlParams.get('tok_id') || urlParams.get('sessionId') || getIdFromURL()
    console.log('- TOK ID found:', tokId)
    
    // Test if EditorLayout.vue event listeners are working
    console.log('- Event listeners should be attached by EditorLayout.vue')
    console.log('- Try switching tabs or pressing Ctrl+R to test')
    console.log('- Or run: window.testTokSave()')
  }
}

// Cleanup on unmount
onUnmounted(() => {
  if (grammarAbortController.value) {
    grammarAbortController.value.abort()
  }
  if (latexAbortController.value) {
    latexAbortController.value.abort()
  }
  if (aiMathematicsAbortController.value) {
    aiMathematicsAbortController.value.abort()
  }
  if (citationsAbortController.value) {
    citationsAbortController.value.abort()
  }
  // Clean up global functions
  if (typeof window !== 'undefined') {
    delete window.saveTokProgress
    delete window.editorSaveTokProgress
  }
})
</script>

<style lang="less" scoped>
/* ✨ CLEAN GLASSMORPHISM BUBBLE - OVERRIDE EXISTING STYLES */
:deep(.umo-editor-bubble-menu:not(.assistant)) {
  /* Perfect glassmorphism background - override default */
  background: rgba(255, 255, 255, 0.12) !important;
  
  /* Essential backdrop blur */
  backdrop-filter: blur(18px) saturate(160%) !important;
  -webkit-backdrop-filter: blur(18px) saturate(160%) !important;
  
  /* Clean rectangle with soft squircles */
  border-radius: 18px !important;
  border: 1px solid rgba(255, 255, 255, 0.35) !important;
  
  /* Clean shadow - override default */
  box-shadow: 0 10px 30px rgba(0, 0, 0, 0.12) !important;
  
  /* Clean spacing */
  padding: 10px 14px !important;
  display: flex !important;
  align-items: center !important;
  gap: 8px !important;
  flex-wrap: nowrap !important;
  
  /* Smooth entrance animation */
  animation: glassSlideIn 0.3s cubic-bezier(0.25, 0.46, 0.45, 0.94) forwards;
  
  @keyframes glassSlideIn {
    from {
      opacity: 0;
      transform: translateY(-8px) scale(0.95);
    }
    to {
      opacity: 1;
      transform: translateY(0) scale(1);
    }
  }
  
  /* Gentle hover effect */
  &:hover {
    background: rgba(255, 255, 255, 0.18) !important;
    border-color: rgba(255, 255, 255, 0.45) !important;
    box-shadow: 0 15px 40px rgba(0, 0, 0, 0.15) !important;
    transform: translateY(-2px);
    transition: all 0.2s ease;
  }
}

/* Dark theme glassmorphism */
[theme-mode='dark'] {
  :deep(.umo-editor-bubble-menu:not(.assistant)) {
    background: rgba(20, 20, 20, 0.35) !important;
    border-color: rgba(255, 255, 255, 0.16) !important;
    
    &:hover {
      background: rgba(20, 20, 20, 0.45) !important;
      border-color: rgba(255, 255, 255, 0.25) !important;
    }
  }
}

.divider {
  width: 1px;
  height: 16px;
  background: rgba(255, 255, 255, 0.25);
  margin: 0 8px;
  
  &:last-child {
    display: none;
  }
}

/* Glass button styling */
.bubble-btn {
  padding: 8px 10px;
  border-radius: 14px;
  cursor: pointer;
  background: linear-gradient(180deg, rgba(255, 255, 255, 0.22), rgba(255, 255, 255, 0.06));
  border: 1px solid rgba(255, 255, 255, 0.35);
  transition: all 0.2s ease;
  
  &:hover {
    background: linear-gradient(180deg, rgba(255, 255, 255, 0.35), rgba(255, 255, 255, 0.12));
    transform: translateY(-1px);
  }
}

/* Tooltip styling */
.bubble-tooltip {
  position: absolute;
  top: -35px;
  left: 50%;
  transform: translateX(-50%);
  background: rgba(255, 255, 255, 0.95);
  color: black;
  padding: 6px 10px;
  border-radius: 6px;
  font-size: 12px;
  white-space: nowrap;
  z-index: 1001;
  border: 1px solid rgba(0, 0, 0, 0.1);
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.15);
  
  &::after {
    content: '';
    position: absolute;
    top: 100%;
    left: 50%;
    transform: translateX(-50%);
    border: 4px solid transparent;
    border-top-color: rgba(255, 255, 255, 0.95);
  }
}

/* Loading animation */
@keyframes spin {
  0% { transform: rotate(0deg); }
  100% { transform: rotate(360deg); }
}

/* Dark theme glassmorphism */
[theme-mode='dark'] {
  .bubble-btn {
    background: linear-gradient(180deg, rgba(255, 255, 255, 0.1), rgba(255, 255, 255, 0.03)) !important;
    border-color: rgba(255, 255, 255, 0.16) !important;
    color: #ddd !important;
    
    &:hover {
      background: linear-gradient(180deg, rgba(255, 255, 255, 0.18), rgba(255, 255, 255, 0.08)) !important;
      border-color: rgba(255, 255, 255, 0.25) !important;
    }
  }
  
  .divider {
    background: rgba(255, 255, 255, 0.16);
  }
}
</style>