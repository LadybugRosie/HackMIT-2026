<template>
  <div class="editor-container">
    <!-- Main Editor Area -->
    <main class="main-editor">
      <slot></slot>
    </main>

    <!-- Cursor-like AI Chat Panel -->
    <aside class="ai-chat-panel" :class="{ 'chat-hidden': chatHidden }">
      <CursorChat 
        :backend-url="backendUrl"
        @toggle-chat="toggleChat"
      />
    </aside>

    <!-- Chat Toggle Button (when hidden) -->
    <div v-if="chatHidden" class="chat-toggle-btn" @click="toggleChat">
      <svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
        <path d="m3 21 1.9-5.7a8.5 8.5 0 1 1 3.8 3.8z"/>
      </svg>
    </div>
  </div>
</template>

<script setup>
import { ref } from 'vue'
import CursorChat from './CursorChat.vue'

// Props
const props = defineProps({
  leftHidden: Boolean,
  tocHidden: Boolean
})

// Emits
const emit = defineEmits(['toggle-left-sidebar', 'toggle-toc-sidebar'])

// Chat state
const chatHidden = ref(false)
const backendUrl = 'https://believable-dedication-production.up.railway.app'

// Functions
function toggleChat() {
  chatHidden.value = !chatHidden.value
}
</script>

<style scoped>
.editor-container {
  display: flex;
  height: 100%;
  position: relative;
  background: #ffffff;
}

.main-editor {
  flex: 1;
  transition: all 0.3s ease;
  overflow: hidden;
}

.ai-chat-panel {
  width: 400px;
  background: #f8f9fa;
  border-left: 1px solid #e1e5e9;
  transition: all 0.3s ease;
  overflow: hidden;
}

.ai-chat-panel.chat-hidden {
  width: 0;
  border-left: none;
}

.chat-toggle-btn {
  position: fixed;
  top: 20px;
  right: 20px;
  width: 48px;
  height: 48px;
  background: #007acc;
  color: white;
  border: none;
  border-radius: 8px;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  box-shadow: 0 2px 8px rgba(0, 122, 204, 0.3);
  z-index: 1000;
  transition: all 0.2s ease;
}

.chat-toggle-btn:hover {
  background: #005a9e;
  transform: translateY(-1px);
  box-shadow: 0 4px 12px rgba(0, 122, 204, 0.4);
}

.chat-toggle-btn:active {
  transform: translateY(0);
}

/* Ensure editor takes full width when chat is hidden */
.editor-container:has(.chat-hidden) .main-editor {
  margin-right: 0;
}
</style>
