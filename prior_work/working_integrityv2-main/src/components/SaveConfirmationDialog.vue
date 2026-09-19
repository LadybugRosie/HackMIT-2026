<template>
  <div v-if="showDialog" class="save-dialog-overlay">
    <div class="save-dialog">
      <div class="save-dialog-header">
        <h3>Save Changes?</h3>
      </div>
      
      <div class="save-dialog-body">
        <p>You have unsaved changes. Do you want to save your work before leaving?</p>
      </div>
      
      <div class="save-dialog-actions">
        <button 
          class="save-dialog-btn save-dialog-btn-primary"
          @click="handleSave"
          :disabled="saving"
        >
          {{ saving ? 'Saving...' : 'Save' }}
        </button>
        
        <button 
          class="save-dialog-btn save-dialog-btn-secondary"
          @click="handleDontSave"
          :disabled="saving"
        >
          Don't Save
        </button>
        
        <button 
          class="save-dialog-btn save-dialog-btn-cancel"
          @click="handleCancel"
          :disabled="saving"
        >
          Cancel
        </button>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref } from 'vue'

const props = defineProps({
  showDialog: {
    type: Boolean,
    default: false
  }
})

const emit = defineEmits(['save', 'dont-save', 'cancel'])

const saving = ref(false)

const handleSave = async () => {
  saving.value = true
  try {
    await emit('save')
  } finally {
    saving.value = false
  }
}

const handleDontSave = () => {
  emit('dont-save')
}

const handleCancel = () => {
  emit('cancel')
}
</script>

<style scoped>
.save-dialog-overlay {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background: rgba(0, 0, 0, 0.6);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 999999;
  backdrop-filter: blur(2px);
}

.save-dialog {
  background: white;
  border-radius: 8px;
  box-shadow: 0 4px 20px rgba(0, 0, 0, 0.15);
  width: 400px;
  max-width: 90vw;
}

.save-dialog-header {
  padding: 20px 20px 10px;
  border-bottom: 1px solid #e5e7eb;
}

.save-dialog-header h3 {
  margin: 0;
  font-size: 18px;
  font-weight: 600;
  color: #111827;
}

.save-dialog-body {
  padding: 20px;
}

.save-dialog-body p {
  margin: 0;
  color: #6b7280;
  line-height: 1.5;
}

.save-dialog-actions {
  padding: 20px;
  display: flex;
  gap: 12px;
  justify-content: flex-end;
  border-top: 1px solid #e5e7eb;
}

.save-dialog-btn {
  padding: 8px 16px;
  border-radius: 6px;
  border: 1px solid;
  font-size: 14px;
  font-weight: 500;
  cursor: pointer;
  transition: all 0.2s;
  min-width: 80px;
}

.save-dialog-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.save-dialog-btn-primary {
  background: #2563eb;
  color: white;
  border-color: #2563eb;
}

.save-dialog-btn-primary:hover:not(:disabled) {
  background: #1d4ed8;
  border-color: #1d4ed8;
}

.save-dialog-btn-secondary {
  background: #f3f4f6;
  color: #374151;
  border-color: #d1d5db;
}

.save-dialog-btn-secondary:hover:not(:disabled) {
  background: #e5e7eb;
}

.save-dialog-btn-cancel {
  background: white;
  color: #374151;
  border-color: #d1d5db;
}

.save-dialog-btn-cancel:hover:not(:disabled) {
  background: #f9fafb;
}
</style>