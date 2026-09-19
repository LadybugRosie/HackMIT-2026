<template>
  <div :class="['ui-input', { 'ui-input--error': error, 'ui-input--disabled': disabled }]">
    <label v-if="label" :for="inputId" class="ui-input__label">
      {{ label }}
      <span v-if="required" class="ui-input__required">*</span>
    </label>
    <div class="ui-input__wrapper">
      <span v-if="$slots.prefix" class="ui-input__prefix">
        <slot name="prefix"></slot>
      </span>
      <input
        :id="inputId"
        :type="type"
        :value="modelValue"
        :placeholder="placeholder"
        :disabled="disabled"
        :readonly="readonly"
        :required="required"
        :maxlength="maxlength"
        :min="min"
        :max="max"
        :step="step"
        :class="['ui-input__field', { 'ui-input__field--has-prefix': $slots.prefix, 'ui-input__field--has-suffix': $slots.suffix }]"
        @input="$emit('update:modelValue', $event.target.value)"
        @focus="$emit('focus', $event)"
        @blur="$emit('blur', $event)"
      />
      <span v-if="$slots.suffix" class="ui-input__suffix">
        <slot name="suffix"></slot>
      </span>
    </div>
    <p v-if="error" class="ui-input__error">{{ error }}</p>
    <p v-else-if="hint" class="ui-input__hint">{{ hint }}</p>
  </div>
</template>

<script setup>
import { computed } from 'vue'

const props = defineProps({
  modelValue: [String, Number],
  type: {
    type: String,
    default: 'text'
  },
  label: String,
  placeholder: String,
  hint: String,
  error: String,
  disabled: Boolean,
  readonly: Boolean,
  required: Boolean,
  maxlength: [String, Number],
  min: [String, Number],
  max: [String, Number],
  step: [String, Number],
  id: String
})

defineEmits(['update:modelValue', 'focus', 'blur'])

const inputId = computed(() => props.id || `input-${Math.random().toString(36).substr(2, 9)}`)
</script>

<style scoped>
.ui-input {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.ui-input__label {
  font-size: 14px;
  font-weight: 500;
  color: #202124;
}

.ui-input__required {
  color: #ea4335;
  margin-left: 2px;
}

.ui-input__wrapper {
  position: relative;
  display: flex;
  align-items: center;
}

.ui-input__field {
  width: 100%;
  padding: 14px 16px;
  font-size: 15px;
  color: #202124;
  background: white;
  border: 2px solid #e0e0e0;
  border-radius: 12px;
  transition: all 0.2s cubic-bezier(0.4, 0, 0.2, 1);
  outline: none;
}

.ui-input__field::placeholder {
  color: #9aa0a6;
}

.ui-input__field:hover:not(:disabled):not(:focus) {
  border-color: #c0c0c0;
}

.ui-input__field:focus {
  border-color: #1a73e8;
  box-shadow: 0 0 0 4px rgba(26, 115, 232, 0.1);
}

.ui-input__field--has-prefix {
  padding-left: 44px;
}

.ui-input__field--has-suffix {
  padding-right: 44px;
}

.ui-input__prefix,
.ui-input__suffix {
  position: absolute;
  display: flex;
  align-items: center;
  justify-content: center;
  width: 44px;
  color: #5f6368;
}

.ui-input__prefix {
  left: 0;
}

.ui-input__suffix {
  right: 0;
}

.ui-input__error {
  font-size: 13px;
  color: #ea4335;
  margin: 0;
  display: flex;
  align-items: center;
  gap: 4px;
}

.ui-input__hint {
  font-size: 13px;
  color: #5f6368;
  margin: 0;
}

/* Error state */
.ui-input--error .ui-input__field {
  border-color: #ea4335;
}

.ui-input--error .ui-input__field:focus {
  box-shadow: 0 0 0 4px rgba(234, 67, 53, 0.1);
}

/* Disabled state */
.ui-input--disabled .ui-input__field {
  background: #f8f9fa;
  color: #9aa0a6;
  cursor: not-allowed;
}

.ui-input--disabled .ui-input__label {
  color: #9aa0a6;
}
</style>
