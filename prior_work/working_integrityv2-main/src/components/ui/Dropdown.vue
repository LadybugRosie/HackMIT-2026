<template>
  <div class="ui-dropdown" ref="dropdownRef">
    <div class="ui-dropdown__trigger" @click="toggle">
      <slot name="trigger">
        <button class="ui-dropdown__button">
          {{ label }}
          <svg width="20" height="20" viewBox="0 0 24 24" fill="currentColor" :class="{ 'rotated': isOpen }">
            <path d="M7.41 8.59L12 13.17l4.59-4.58L18 10l-6 6-6-6 1.41-1.41z"/>
          </svg>
        </button>
      </slot>
    </div>
    <Transition name="dropdown">
      <div v-if="isOpen" :class="['ui-dropdown__menu', `ui-dropdown__menu--${position}`]">
        <slot>
          <div
            v-for="item in items"
            :key="item.id || item.label"
            :class="['ui-dropdown__item', { 'ui-dropdown__item--disabled': item.disabled, 'ui-dropdown__item--danger': item.danger }]"
            @click="selectItem(item)"
          >
            <span v-if="item.icon" class="ui-dropdown__item-icon" v-html="item.icon"></span>
            <span class="ui-dropdown__item-label">{{ item.label }}</span>
          </div>
        </slot>
      </div>
    </Transition>
  </div>
</template>

<script setup>
import { ref, onMounted, onUnmounted } from 'vue'

const props = defineProps({
  items: {
    type: Array,
    default: () => []
  },
  label: String,
  position: {
    type: String,
    default: 'bottom-left',
    validator: (v) => ['bottom-left', 'bottom-right', 'top-left', 'top-right'].includes(v)
  }
})

const emit = defineEmits(['select'])

const isOpen = ref(false)
const dropdownRef = ref(null)

function toggle() {
  isOpen.value = !isOpen.value
}

function close() {
  isOpen.value = false
}

function selectItem(item) {
  if (item.disabled) return
  emit('select', item)
  close()
}

function handleClickOutside(e) {
  if (dropdownRef.value && !dropdownRef.value.contains(e.target)) {
    close()
  }
}

onMounted(() => {
  document.addEventListener('click', handleClickOutside)
})

onUnmounted(() => {
  document.removeEventListener('click', handleClickOutside)
})

defineExpose({ open: () => isOpen.value = true, close, toggle })
</script>

<style scoped>
.ui-dropdown {
  position: relative;
  display: inline-block;
}

.ui-dropdown__button {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 10px 16px;
  background: white;
  border: 1px solid #dadce0;
  border-radius: 8px;
  font-size: 14px;
  font-weight: 500;
  color: #202124;
  cursor: pointer;
  transition: all 0.2s;
}

.ui-dropdown__button:hover {
  background: #f8f9fa;
  border-color: #c0c0c0;
}

.ui-dropdown__button svg {
  transition: transform 0.2s;
}

.ui-dropdown__button svg.rotated {
  transform: rotate(180deg);
}

.ui-dropdown__menu {
  position: absolute;
  min-width: 200px;
  background: white;
  border-radius: 12px;
  box-shadow: 0 8px 24px rgba(0, 0, 0, 0.15), 0 2px 8px rgba(0, 0, 0, 0.1);
  padding: 8px 0;
  z-index: 100;
  overflow: hidden;
}

.ui-dropdown__menu--bottom-left {
  top: 100%;
  left: 0;
  margin-top: 8px;
}

.ui-dropdown__menu--bottom-right {
  top: 100%;
  right: 0;
  margin-top: 8px;
}

.ui-dropdown__menu--top-left {
  bottom: 100%;
  left: 0;
  margin-bottom: 8px;
}

.ui-dropdown__menu--top-right {
  bottom: 100%;
  right: 0;
  margin-bottom: 8px;
}

.ui-dropdown__item {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 12px 16px;
  font-size: 14px;
  color: #202124;
  cursor: pointer;
  transition: background 0.15s;
}

.ui-dropdown__item:hover {
  background: #f1f3f4;
}

.ui-dropdown__item--disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.ui-dropdown__item--disabled:hover {
  background: transparent;
}

.ui-dropdown__item--danger {
  color: #d93025;
}

.ui-dropdown__item--danger:hover {
  background: #fce8e6;
}

.ui-dropdown__item-icon {
  display: flex;
  align-items: center;
  justify-content: center;
  color: #5f6368;
}

.ui-dropdown__item--danger .ui-dropdown__item-icon {
  color: #d93025;
}

.ui-dropdown__item-icon :deep(svg) {
  width: 20px;
  height: 20px;
}

/* Animations */
.dropdown-enter-active {
  animation: dropdown-in 0.2s cubic-bezier(0.4, 0, 0.2, 1);
}

.dropdown-leave-active {
  animation: dropdown-out 0.15s cubic-bezier(0.4, 0, 0.2, 1);
}

@keyframes dropdown-in {
  from {
    opacity: 0;
    transform: translateY(-8px) scale(0.95);
  }
  to {
    opacity: 1;
    transform: translateY(0) scale(1);
  }
}

@keyframes dropdown-out {
  from {
    opacity: 1;
    transform: translateY(0) scale(1);
  }
  to {
    opacity: 0;
    transform: translateY(-8px) scale(0.95);
  }
}
</style>
