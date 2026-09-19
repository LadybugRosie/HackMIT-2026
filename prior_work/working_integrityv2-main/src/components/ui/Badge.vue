<template>
  <span 
    :class="[
      'ui-badge',
      `ui-badge--${variant}`,
      `ui-badge--${size}`,
      { 'ui-badge--dot': dot, 'ui-badge--pulse': pulse }
    ]"
  >
    <span v-if="dot" class="ui-badge__dot"></span>
    <slot v-else></slot>
  </span>
</template>

<script setup>
defineProps({
  variant: {
    type: String,
    default: 'default',
    validator: (v) => ['default', 'primary', 'success', 'warning', 'danger', 'info'].includes(v)
  },
  size: {
    type: String,
    default: 'medium',
    validator: (v) => ['small', 'medium', 'large'].includes(v)
  },
  dot: Boolean,
  pulse: Boolean
})
</script>

<style scoped>
.ui-badge {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  font-weight: 500;
  border-radius: 100px;
  white-space: nowrap;
  transition: all 0.2s;
}

/* Sizes */
.ui-badge--small {
  padding: 2px 8px;
  font-size: 11px;
  min-height: 20px;
}

.ui-badge--medium {
  padding: 4px 12px;
  font-size: 12px;
  min-height: 24px;
}

.ui-badge--large {
  padding: 6px 16px;
  font-size: 14px;
  min-height: 28px;
}

/* Variants */
.ui-badge--default {
  background: #f1f3f4;
  color: #5f6368;
}

.ui-badge--primary {
  background: #e8f0fe;
  color: #1a73e8;
}

.ui-badge--success {
  background: #e6f4ea;
  color: #1e8e3e;
}

.ui-badge--warning {
  background: #fef7e0;
  color: #f9ab00;
}

.ui-badge--danger {
  background: #fce8e6;
  color: #d93025;
}

.ui-badge--info {
  background: #e4f7fb;
  color: #0097a7;
}

/* Dot variant */
.ui-badge--dot {
  padding: 0;
  min-width: auto;
  min-height: auto;
  background: transparent;
}

.ui-badge__dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: currentColor;
}

.ui-badge--dot.ui-badge--default .ui-badge__dot {
  background: #9aa0a6;
}

.ui-badge--dot.ui-badge--primary .ui-badge__dot {
  background: #1a73e8;
}

.ui-badge--dot.ui-badge--success .ui-badge__dot {
  background: #1e8e3e;
}

.ui-badge--dot.ui-badge--warning .ui-badge__dot {
  background: #f9ab00;
}

.ui-badge--dot.ui-badge--danger .ui-badge__dot {
  background: #d93025;
}

.ui-badge--dot.ui-badge--large .ui-badge__dot {
  width: 12px;
  height: 12px;
}

/* Pulse animation */
.ui-badge--pulse .ui-badge__dot {
  animation: pulse 2s infinite;
}

@keyframes pulse {
  0% {
    box-shadow: 0 0 0 0 currentColor;
    opacity: 1;
  }
  70% {
    box-shadow: 0 0 0 8px currentColor;
    opacity: 0;
  }
  100% {
    box-shadow: 0 0 0 0 currentColor;
    opacity: 0;
  }
}
</style>
