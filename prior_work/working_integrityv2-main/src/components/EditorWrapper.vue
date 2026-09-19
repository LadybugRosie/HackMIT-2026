<template>
  <div>
    <!-- Face Verification Gate -->
    <FaceVerification 
      v-if="!faceVerified"
      :session-id="sessionId"
      :check-interval="60000"
      @verified="handleFaceVerified"
      @session-terminated="handleSessionTerminated"
      @skip="handleFaceSkipped"
    />
    
    <!-- Main Editor Content (only shown after face verification) -->
    <template v-if="faceVerified">
      <!-- Render BlankModuleLayout for blank template mode -->
      <BlankModuleLayout 
        v-if="selectedMode === 'blank-template'"
        :left-hidden="leftHidden"
        :toc-hidden="tocHidden"
        @toggle-left-sidebar="toggleLeftSidebar"
        @toggle-toc-sidebar="toggleTocSidebar"
      />
      
      <!-- Render existing EditorLayout for all other modes -->
      <EditorLayout v-else />
    </template>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import EditorLayout from './EditorLayout.vue'
import BlankModuleLayout from './BlankModuleLayoutNew.vue'
import FaceVerification from './FaceVerification.vue'

const router = useRouter()

// Sidebar state
const leftHidden = ref(false)
const tocHidden = ref(false)

// Mode management
const selectedMode = ref('none')

// Face verification state
const faceVerified = ref(false)
const sessionId = ref('')

// Function to get mode from query parameters
function getModeFromQueryParams() {
  const urlParams = new URLSearchParams(window.location.search)
  const selectmodule = urlParams.get('selectmodule')
  
  if (selectmodule === 'essay') {
    return 'essay'
  } else if (selectmodule === 'paper') {
    return 'paper-template'
  } else if (selectmodule === 'blank') {
    return 'blank-template'
  } else if (selectmodule === 'tok_essay') {
    return 'tok-essay'
  } else if (selectmodule === 'tok') {
    return 'tok'
  } else if (selectmodule === 'tok-exhibition') {
    return 'tok-exhibition'
  }
  
  return 'none'
}

// Toggle functions
function toggleLeftSidebar() {
  leftHidden.value = !leftHidden.value
}

function toggleTocSidebar() {
  tocHidden.value = !tocHidden.value
}

// Face verification handlers
function handleFaceVerified() {
  console.log('✅ Face verified - granting editor access')
  faceVerified.value = true
}

function handleSessionTerminated() {
  console.log('⚠️ Session terminated due to face mismatch')
  router.push('/dashboard')
}

function handleFaceSkipped() {
  console.log('⏭️ Face verification skipped')
  faceVerified.value = true
}

onMounted(() => {
  selectedMode.value = getModeFromQueryParams()
  
  // Generate session ID for face monitoring
  sessionId.value = 'session-' + Date.now() + '-' + Math.random().toString(36).substr(2, 9)
})
</script>

<style scoped>
/* No additional styles needed - components handle their own styling */
</style>