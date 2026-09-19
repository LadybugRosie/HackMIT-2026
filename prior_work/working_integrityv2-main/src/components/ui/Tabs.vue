<template>
  <div class="ui-tabs">
    <div class="ui-tabs__nav" role="tablist">
      <button
        v-for="tab in tabs"
        :key="tab.id"
        :class="['ui-tabs__tab', { 'ui-tabs__tab--active': modelValue === tab.id }]"
        role="tab"
        :aria-selected="modelValue === tab.id"
        @click="$emit('update:modelValue', tab.id)"
      >
        <span v-if="tab.icon" class="ui-tabs__icon" v-html="tab.icon"></span>
        <span class="ui-tabs__label">{{ tab.label }}</span>
        <span v-if="tab.badge" class="ui-tabs__badge">{{ tab.badge }}</span>
      </button>
      <div class="ui-tabs__indicator" :style="indicatorStyle"></div>
    </div>
    <div class="ui-tabs__content">
      <slot></slot>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, watch, nextTick } from 'vue'

const props = defineProps({
  modelValue: [String, Number],
  tabs: {
    type: Array,
    required: true,
    validator: (tabs) => tabs.every(t => t.id && t.label)
  }
})

defineEmits(['update:modelValue'])

const indicatorStyle = ref({})

function updateIndicator() {
  nextTick(() => {
    const activeTab = document.querySelector('.ui-tabs__tab--active')
    if (activeTab) {
      indicatorStyle.value = {
        width: activeTab.offsetWidth + 'px',
        transform: `translateX(${activeTab.offsetLeft}px)`
      }
    }
  })
}

watch(() => props.modelValue, updateIndicator)
onMounted(updateIndicator)
</script>

<style scoped>
.ui-tabs {
  width: 100%;
}

.ui-tabs__nav {
  display: flex;
  position: relative;
  border-bottom: 2px solid #e0e0e0;
  overflow-x: auto;
  scrollbar-width: none;
}

.ui-tabs__nav::-webkit-scrollbar {
  display: none;
}

.ui-tabs__tab {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 16px 24px;
  background: transparent;
  border: none;
  font-size: 14px;
  font-weight: 500;
  color: #5f6368;
  cursor: pointer;
  transition: all 0.2s;
  white-space: nowrap;
  position: relative;
}

.ui-tabs__tab:hover {
  color: #1a73e8;
  background: rgba(26, 115, 232, 0.04);
}

.ui-tabs__tab--active {
  color: #1a73e8;
}

.ui-tabs__icon {
  display: flex;
  align-items: center;
  justify-content: center;
}

.ui-tabs__icon :deep(svg) {
  width: 20px;
  height: 20px;
}

.ui-tabs__badge {
  background: #1a73e8;
  color: white;
  padding: 2px 8px;
  border-radius: 12px;
  font-size: 12px;
  font-weight: 600;
}

.ui-tabs__tab--active .ui-tabs__badge {
  background: #1557b0;
}

.ui-tabs__indicator {
  position: absolute;
  bottom: -2px;
  left: 0;
  height: 3px;
  background: #1a73e8;
  border-radius: 3px 3px 0 0;
  transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
}

.ui-tabs__content {
  padding-top: 24px;
}
</style>
