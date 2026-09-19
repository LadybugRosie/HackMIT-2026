<template>
  <Teleport to="body">
    <TransitionGroup name="toast" tag="div" class="ui-toast-container">
      <div 
        v-for="toast in toasts" 
        :key="toast.id"
        :class="['ui-toast', `ui-toast--${toast.type}`]"
      >
        <div class="ui-toast__icon">
          <svg v-if="toast.type === 'success'" width="24" height="24" viewBox="0 0 24 24" fill="currentColor">
            <path d="M9 16.17L4.83 12l-1.42 1.41L9 19 21 7l-1.41-1.41z"/>
          </svg>
          <svg v-else-if="toast.type === 'error'" width="24" height="24" viewBox="0 0 24 24" fill="currentColor">
            <path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm1 15h-2v-2h2v2zm0-4h-2V7h2v6z"/>
          </svg>
          <svg v-else-if="toast.type === 'warning'" width="24" height="24" viewBox="0 0 24 24" fill="currentColor">
            <path d="M1 21h22L12 2 1 21zm12-3h-2v-2h2v2zm0-4h-2v-4h2v4z"/>
          </svg>
          <svg v-else width="24" height="24" viewBox="0 0 24 24" fill="currentColor">
            <path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm1 15h-2v-6h2v6zm0-8h-2V7h2v2z"/>
          </svg>
        </div>
        <div class="ui-toast__content">
          <p class="ui-toast__message">{{ toast.message }}</p>
          <p v-if="toast.description" class="ui-toast__description">{{ toast.description }}</p>
        </div>
        <button class="ui-toast__close" @click="removeToast(toast.id)">
          <svg width="20" height="20" viewBox="0 0 24 24" fill="currentColor">
            <path d="M19 6.41L17.59 5 12 10.59 6.41 5 5 6.41 10.59 12 5 17.59 6.41 19 12 13.41 17.59 19 19 17.59 13.41 12z"/>
          </svg>
        </button>
        <div class="ui-toast__progress" :style="{ animationDuration: toast.duration + 'ms' }"></div>
      </div>
    </TransitionGroup>
  </Teleport>
</template>

<script setup>
import { ref } from 'vue'

const toasts = ref([])
let toastId = 0

function addToast({ message, description, type = 'info', duration = 5000 }) {
  const id = ++toastId
  toasts.value.push({ id, message, description, type, duration })
  
  if (duration > 0) {
    setTimeout(() => removeToast(id), duration)
  }
  
  return id
}

function removeToast(id) {
  const index = toasts.value.findIndex(t => t.id === id)
  if (index > -1) {
    toasts.value.splice(index, 1)
  }
}

// Expose methods
defineExpose({
  success: (message, description) => addToast({ message, description, type: 'success' }),
  error: (message, description) => addToast({ message, description, type: 'error' }),
  warning: (message, description) => addToast({ message, description, type: 'warning' }),
  info: (message, description) => addToast({ message, description, type: 'info' }),
  remove: removeToast
})
</script>

<style scoped>
.ui-toast-container {
  position: fixed;
  top: 24px;
  right: 24px;
  z-index: 2000;
  display: flex;
  flex-direction: column;
  gap: 12px;
  max-width: 420px;
  width: 100%;
  pointer-events: none;
}

.ui-toast {
  display: flex;
  align-items: flex-start;
  gap: 12px;
  padding: 16px;
  background: white;
  border-radius: 12px;
  box-shadow: 0 8px 24px rgba(0, 0, 0, 0.15), 0 2px 8px rgba(0, 0, 0, 0.1);
  pointer-events: auto;
  position: relative;
  overflow: hidden;
}

.ui-toast__icon {
  flex-shrink: 0;
  width: 24px;
  height: 24px;
}

.ui-toast--success .ui-toast__icon {
  color: #1e8e3e;
}

.ui-toast--error .ui-toast__icon {
  color: #d93025;
}

.ui-toast--warning .ui-toast__icon {
  color: #f9ab00;
}

.ui-toast--info .ui-toast__icon {
  color: #1a73e8;
}

.ui-toast__content {
  flex: 1;
  min-width: 0;
}

.ui-toast__message {
  font-size: 14px;
  font-weight: 500;
  color: #202124;
  margin: 0;
}

.ui-toast__description {
  font-size: 13px;
  color: #5f6368;
  margin: 4px 0 0;
}

.ui-toast__close {
  flex-shrink: 0;
  width: 28px;
  height: 28px;
  border: none;
  background: transparent;
  border-radius: 50%;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  color: #5f6368;
  margin: -4px -4px 0 0;
  transition: all 0.2s;
}

.ui-toast__close:hover {
  background: #f1f3f4;
  color: #202124;
}

.ui-toast__progress {
  position: absolute;
  bottom: 0;
  left: 0;
  height: 3px;
  background: currentColor;
  opacity: 0.3;
  animation: progress linear forwards;
}

@keyframes progress {
  from { width: 100%; }
  to { width: 0%; }
}

.ui-toast--success .ui-toast__progress {
  background: #1e8e3e;
}

.ui-toast--error .ui-toast__progress {
  background: #d93025;
}

.ui-toast--warning .ui-toast__progress {
  background: #f9ab00;
}

.ui-toast--info .ui-toast__progress {
  background: #1a73e8;
}

/* Animations */
.toast-enter-active {
  animation: toast-in 0.3s cubic-bezier(0.4, 0, 0.2, 1);
}

.toast-leave-active {
  animation: toast-out 0.3s cubic-bezier(0.4, 0, 0.2, 1);
}

@keyframes toast-in {
  from {
    opacity: 0;
    transform: translateX(100%);
  }
  to {
    opacity: 1;
    transform: translateX(0);
  }
}

@keyframes toast-out {
  from {
    opacity: 1;
    transform: translateX(0);
  }
  to {
    opacity: 0;
    transform: translateX(100%);
  }
}

@media (max-width: 480px) {
  .ui-toast-container {
    left: 16px;
    right: 16px;
    max-width: none;
  }
}
</style>
