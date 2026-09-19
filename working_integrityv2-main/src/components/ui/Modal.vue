<template>
  <Teleport to="body">
    <Transition name="modal">
      <div v-if="modelValue" class="ui-modal-overlay" @click.self="closeOnBackdrop && close()">
        <div 
          :class="['ui-modal', `ui-modal--${size}`]"
          role="dialog"
          aria-modal="true"
        >
          <div v-if="$slots.header || title" class="ui-modal__header">
            <slot name="header">
              <h2 class="ui-modal__title">{{ title }}</h2>
            </slot>
            <button v-if="showClose" class="ui-modal__close" @click="close">
              <svg width="24" height="24" viewBox="0 0 24 24" fill="currentColor">
                <path d="M19 6.41L17.59 5 12 10.59 6.41 5 5 6.41 10.59 12 5 17.59 6.41 19 12 13.41 17.59 19 19 17.59 13.41 12z"/>
              </svg>
            </button>
          </div>
          <div class="ui-modal__body">
            <slot></slot>
          </div>
          <div v-if="$slots.footer" class="ui-modal__footer">
            <slot name="footer"></slot>
          </div>
        </div>
      </div>
    </Transition>
  </Teleport>
</template>

<script setup>
import { watch, onMounted, onUnmounted } from 'vue'

const props = defineProps({
  modelValue: Boolean,
  title: String,
  size: {
    type: String,
    default: 'medium',
    validator: (v) => ['small', 'medium', 'large', 'fullscreen'].includes(v)
  },
  showClose: {
    type: Boolean,
    default: true
  },
  closeOnBackdrop: {
    type: Boolean,
    default: true
  },
  closeOnEscape: {
    type: Boolean,
    default: true
  }
})

const emit = defineEmits(['update:modelValue', 'close'])

function close() {
  emit('update:modelValue', false)
  emit('close')
}

function handleEscape(e) {
  if (e.key === 'Escape' && props.closeOnEscape && props.modelValue) {
    close()
  }
}

watch(() => props.modelValue, (isOpen) => {
  if (isOpen) {
    document.body.style.overflow = 'hidden'
  } else {
    document.body.style.overflow = ''
  }
})

onMounted(() => {
  document.addEventListener('keydown', handleEscape)
})

onUnmounted(() => {
  document.removeEventListener('keydown', handleEscape)
  document.body.style.overflow = ''
})
</script>

<style scoped>
.ui-modal-overlay {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.5);
  backdrop-filter: blur(4px);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 1000;
  padding: 20px;
}

.ui-modal {
  background: white;
  border-radius: 20px;
  box-shadow: 0 24px 48px rgba(0, 0, 0, 0.2);
  display: flex;
  flex-direction: column;
  max-height: calc(100vh - 40px);
  animation: modal-enter 0.3s cubic-bezier(0.4, 0, 0.2, 1);
}

.ui-modal--small {
  width: 100%;
  max-width: 400px;
}

.ui-modal--medium {
  width: 100%;
  max-width: 560px;
}

.ui-modal--large {
  width: 100%;
  max-width: 800px;
}

.ui-modal--fullscreen {
  width: calc(100% - 40px);
  height: calc(100% - 40px);
  max-width: none;
  border-radius: 16px;
}

.ui-modal__header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 24px 24px 0;
  flex-shrink: 0;
}

.ui-modal__title {
  font-size: 22px;
  font-weight: 500;
  color: #202124;
  margin: 0;
}

.ui-modal__close {
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
  transition: all 0.2s;
  margin: -8px -8px 0 0;
}

.ui-modal__close:hover {
  background: #f1f3f4;
  color: #202124;
}

.ui-modal__body {
  padding: 24px;
  overflow-y: auto;
  flex: 1;
}

.ui-modal__header + .ui-modal__body {
  padding-top: 16px;
}

.ui-modal__footer {
  display: flex;
  justify-content: flex-end;
  gap: 12px;
  padding: 16px 24px;
  border-top: 1px solid #e0e0e0;
  flex-shrink: 0;
}

/* Animations */
@keyframes modal-enter {
  from {
    opacity: 0;
    transform: scale(0.95) translateY(10px);
  }
  to {
    opacity: 1;
    transform: scale(1) translateY(0);
  }
}

.modal-enter-active {
  transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
}

.modal-leave-active {
  transition: all 0.2s cubic-bezier(0.4, 0, 0.2, 1);
}

.modal-enter-from,
.modal-leave-to {
  opacity: 0;
}

.modal-enter-from .ui-modal,
.modal-leave-to .ui-modal {
  transform: scale(0.95) translateY(10px);
}
</style>
