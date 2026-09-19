<template>
  <div :class="['ui-progress', `ui-progress--${variant}`]">
    <div v-if="showLabel" class="ui-progress__header">
      <span class="ui-progress__label">{{ label }}</span>
      <span class="ui-progress__value">{{ displayValue }}</span>
    </div>
    <div class="ui-progress__track">
      <div 
        class="ui-progress__fill"
        :style="{ width: percentage + '%' }"
        :class="{ 'ui-progress__fill--animated': animated }"
      ></div>
    </div>
  </div>
</template>

<script setup>
import { computed } from 'vue'

const props = defineProps({
  value: {
    type: Number,
    default: 0
  },
  max: {
    type: Number,
    default: 100
  },
  variant: {
    type: String,
    default: 'primary',
    validator: (v) => ['primary', 'success', 'warning', 'danger', 'gradient'].includes(v)
  },
  label: String,
  showLabel: Boolean,
  showPercentage: {
    type: Boolean,
    default: true
  },
  animated: Boolean
})

const percentage = computed(() => {
  return Math.min(100, Math.max(0, (props.value / props.max) * 100))
})

const displayValue = computed(() => {
  if (props.showPercentage) {
    return Math.round(percentage.value) + '%'
  }
  return `${props.value}/${props.max}`
})
</script>

<style scoped>
.ui-progress {
  width: 100%;
}

.ui-progress__header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 8px;
}

.ui-progress__label {
  font-size: 14px;
  font-weight: 500;
  color: #202124;
}

.ui-progress__value {
  font-size: 14px;
  color: #5f6368;
}

.ui-progress__track {
  height: 8px;
  background: #e0e0e0;
  border-radius: 4px;
  overflow: hidden;
}

.ui-progress__fill {
  height: 100%;
  border-radius: 4px;
  transition: width 0.4s cubic-bezier(0.4, 0, 0.2, 1);
}

.ui-progress__fill--animated {
  animation: progress-pulse 2s infinite;
}

@keyframes progress-pulse {
  0%, 100% {
    opacity: 1;
  }
  50% {
    opacity: 0.7;
  }
}

/* Variants */
.ui-progress--primary .ui-progress__fill {
  background: linear-gradient(90deg, #1a73e8, #4285f4);
}

.ui-progress--success .ui-progress__fill {
  background: linear-gradient(90deg, #1e8e3e, #34a853);
}

.ui-progress--warning .ui-progress__fill {
  background: linear-gradient(90deg, #f9ab00, #fbbc04);
}

.ui-progress--danger .ui-progress__fill {
  background: linear-gradient(90deg, #d93025, #ea4335);
}

.ui-progress--gradient .ui-progress__fill {
  background: linear-gradient(90deg, #667eea, #764ba2, #f093fb);
  background-size: 200% 100%;
  animation: gradient-shift 3s ease infinite;
}

@keyframes gradient-shift {
  0% { background-position: 0% 50%; }
  50% { background-position: 100% 50%; }
  100% { background-position: 0% 50%; }
}
</style>
