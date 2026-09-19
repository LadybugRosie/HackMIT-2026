<template>
  <button 
    :class="[
      'ui-button',
      `ui-button--${variant}`,
      `ui-button--${size}`,
      { 
        'ui-button--loading': loading,
        'ui-button--icon-only': iconOnly,
        'ui-button--full-width': fullWidth
      }
    ]"
    :disabled="disabled || loading"
    @click="$emit('click', $event)"
  >
    <span v-if="loading" class="ui-button__spinner"></span>
    <span v-if="$slots.icon && !loading" class="ui-button__icon">
      <slot name="icon"></slot>
    </span>
    <span v-if="!iconOnly" class="ui-button__text">
      <slot></slot>
    </span>
  </button>
</template>

<script setup>
defineProps({
  variant: {
    type: String,
    default: 'primary',
    validator: (v) => ['primary', 'secondary', 'text', 'danger', 'success', 'outline'].includes(v)
  },
  size: {
    type: String,
    default: 'medium',
    validator: (v) => ['small', 'medium', 'large'].includes(v)
  },
  disabled: Boolean,
  loading: Boolean,
  iconOnly: Boolean,
  fullWidth: Boolean
})

defineEmits(['click'])
</script>

<style scoped>
.ui-button {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  font-family: 'Google Sans', 'Roboto', -apple-system, BlinkMacSystemFont, sans-serif;
  font-weight: 500;
  border-radius: 8px;
  cursor: pointer;
  transition: all 0.2s cubic-bezier(0.4, 0, 0.2, 1);
  border: none;
  outline: none;
  position: relative;
  overflow: hidden;
}

/* Ripple effect */
.ui-button::after {
  content: '';
  position: absolute;
  inset: 0;
  background: currentColor;
  opacity: 0;
  transition: opacity 0.2s;
}

.ui-button:active::after {
  opacity: 0.1;
}

/* Sizes */
.ui-button--small {
  padding: 6px 16px;
  font-size: 13px;
  min-height: 32px;
}

.ui-button--medium {
  padding: 10px 24px;
  font-size: 14px;
  min-height: 40px;
}

.ui-button--large {
  padding: 14px 32px;
  font-size: 16px;
  min-height: 48px;
}

/* Variants */
.ui-button--primary {
  background: linear-gradient(135deg, #1a73e8 0%, #1557b0 100%);
  color: white;
  box-shadow: 0 2px 4px rgba(26, 115, 232, 0.3);
}

.ui-button--primary:hover:not(:disabled) {
  box-shadow: 0 4px 12px rgba(26, 115, 232, 0.4);
  transform: translateY(-1px);
}

.ui-button--secondary {
  background: #f8f9fa;
  color: #5f6368;
  border: 1px solid #dadce0;
}

.ui-button--secondary:hover:not(:disabled) {
  background: #e8eaed;
  border-color: #c5c8cb;
}

.ui-button--outline {
  background: transparent;
  color: #1a73e8;
  border: 2px solid #1a73e8;
}

.ui-button--outline:hover:not(:disabled) {
  background: rgba(26, 115, 232, 0.08);
}

.ui-button--text {
  background: transparent;
  color: #1a73e8;
  padding-left: 12px;
  padding-right: 12px;
}

.ui-button--text:hover:not(:disabled) {
  background: rgba(26, 115, 232, 0.08);
}

.ui-button--danger {
  background: linear-gradient(135deg, #ea4335 0%, #c5221f 100%);
  color: white;
  box-shadow: 0 2px 4px rgba(234, 67, 53, 0.3);
}

.ui-button--danger:hover:not(:disabled) {
  box-shadow: 0 4px 12px rgba(234, 67, 53, 0.4);
  transform: translateY(-1px);
}

.ui-button--success {
  background: linear-gradient(135deg, #34a853 0%, #1e8e3e 100%);
  color: white;
  box-shadow: 0 2px 4px rgba(52, 168, 83, 0.3);
}

.ui-button--success:hover:not(:disabled) {
  box-shadow: 0 4px 12px rgba(52, 168, 83, 0.4);
  transform: translateY(-1px);
}

/* States */
.ui-button:disabled {
  opacity: 0.6;
  cursor: not-allowed;
  transform: none !important;
  box-shadow: none !important;
}

.ui-button--loading {
  pointer-events: none;
}

.ui-button--full-width {
  width: 100%;
}

.ui-button--icon-only {
  padding: 0;
  width: 40px;
  border-radius: 50%;
}

.ui-button--icon-only.ui-button--small {
  width: 32px;
  min-height: 32px;
}

.ui-button--icon-only.ui-button--large {
  width: 48px;
  min-height: 48px;
}

/* Spinner */
.ui-button__spinner {
  width: 16px;
  height: 16px;
  border: 2px solid currentColor;
  border-top-color: transparent;
  border-radius: 50%;
  animation: spin 0.8s linear infinite;
}

@keyframes spin {
  to { transform: rotate(360deg); }
}

.ui-button__icon {
  display: flex;
  align-items: center;
  justify-content: center;
}

.ui-button__icon :deep(svg) {
  width: 20px;
  height: 20px;
}

.ui-button--small .ui-button__icon :deep(svg) {
  width: 16px;
  height: 16px;
}

.ui-button--large .ui-button__icon :deep(svg) {
  width: 24px;
  height: 24px;
}
</style>
