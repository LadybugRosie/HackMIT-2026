<template>
  <div 
    :class="['ui-skeleton', `ui-skeleton--${variant}`]"
    :style="customStyle"
  >
    <slot></slot>
  </div>
</template>

<script setup>
import { computed } from 'vue'

const props = defineProps({
  variant: {
    type: String,
    default: 'rectangle',
    validator: (v) => ['rectangle', 'circle', 'text', 'card'].includes(v)
  },
  width: String,
  height: String,
  lines: {
    type: Number,
    default: 1
  }
})

const customStyle = computed(() => ({
  width: props.width,
  height: props.height
}))
</script>

<style scoped>
.ui-skeleton {
  background: linear-gradient(
    90deg,
    #f0f0f0 25%,
    #e0e0e0 50%,
    #f0f0f0 75%
  );
  background-size: 200% 100%;
  animation: shimmer 1.5s infinite;
  border-radius: 8px;
}

@keyframes shimmer {
  0% {
    background-position: 200% 0;
  }
  100% {
    background-position: -200% 0;
  }
}

.ui-skeleton--rectangle {
  min-height: 20px;
}

.ui-skeleton--circle {
  width: 48px;
  height: 48px;
  border-radius: 50%;
}

.ui-skeleton--text {
  height: 16px;
  border-radius: 4px;
}

.ui-skeleton--card {
  min-height: 200px;
  border-radius: 16px;
}
</style>
