<template>
  <div 
    :class="[
      'ui-card',
      `ui-card--${variant}`,
      { 
        'ui-card--clickable': clickable,
        'ui-card--elevated': elevated,
        'ui-card--no-padding': noPadding
      }
    ]"
    @click="clickable && $emit('click', $event)"
  >
    <div v-if="$slots.header || title" class="ui-card__header">
      <slot name="header">
        <h3 v-if="title" class="ui-card__title">{{ title }}</h3>
        <p v-if="subtitle" class="ui-card__subtitle">{{ subtitle }}</p>
      </slot>
      <div v-if="$slots.actions" class="ui-card__actions">
        <slot name="actions"></slot>
      </div>
    </div>
    <div v-if="$slots.default" class="ui-card__body">
      <slot></slot>
    </div>
    <div v-if="$slots.footer" class="ui-card__footer">
      <slot name="footer"></slot>
    </div>
  </div>
</template>

<script setup>
defineProps({
  variant: {
    type: String,
    default: 'default',
    validator: (v) => ['default', 'outlined', 'filled', 'gradient'].includes(v)
  },
  title: String,
  subtitle: String,
  clickable: Boolean,
  elevated: Boolean,
  noPadding: Boolean
})

defineEmits(['click'])
</script>

<style scoped>
.ui-card {
  background: white;
  border-radius: 16px;
  transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
}

.ui-card--default {
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.08), 0 1px 2px rgba(0, 0, 0, 0.06);
}

.ui-card--outlined {
  border: 1px solid #e0e0e0;
  box-shadow: none;
}

.ui-card--filled {
  background: #f8f9fa;
  box-shadow: none;
}

.ui-card--gradient {
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  color: white;
}

.ui-card--elevated {
  box-shadow: 0 8px 24px rgba(0, 0, 0, 0.12), 0 2px 8px rgba(0, 0, 0, 0.08);
}

.ui-card--clickable {
  cursor: pointer;
}

.ui-card--clickable:hover {
  transform: translateY(-2px);
  box-shadow: 0 12px 32px rgba(0, 0, 0, 0.15), 0 4px 12px rgba(0, 0, 0, 0.1);
}

.ui-card--no-padding .ui-card__body {
  padding: 0;
}

.ui-card__header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  padding: 24px 24px 0;
}

.ui-card__title {
  font-size: 18px;
  font-weight: 500;
  margin: 0;
  color: inherit;
}

.ui-card--gradient .ui-card__title {
  color: white;
}

.ui-card__subtitle {
  font-size: 14px;
  color: #5f6368;
  margin: 4px 0 0;
}

.ui-card--gradient .ui-card__subtitle {
  color: rgba(255, 255, 255, 0.8);
}

.ui-card__actions {
  display: flex;
  gap: 8px;
}

.ui-card__body {
  padding: 24px;
}

.ui-card__header + .ui-card__body {
  padding-top: 16px;
}

.ui-card__footer {
  padding: 16px 24px;
  border-top: 1px solid #e0e0e0;
  background: #f8f9fa;
  border-radius: 0 0 16px 16px;
}

.ui-card--gradient .ui-card__footer {
  background: rgba(0, 0, 0, 0.1);
  border-color: rgba(255, 255, 255, 0.2);
}
</style>
