/**
 * Toast Composable
 * Simple toast notifications for the app
 */
import { ref } from 'vue'

const toasts = ref([])
let toastId = 0

export function useToast() {
  function show({ message, description = '', type = 'info', duration = 5000 }) {
    const id = ++toastId
    toasts.value.push({ id, message, description, type, duration })
    
    if (duration > 0) {
      setTimeout(() => remove(id), duration)
    }
    
    return id
  }
  
  function remove(id) {
    const index = toasts.value.findIndex(t => t.id === id)
    if (index > -1) {
      toasts.value.splice(index, 1)
    }
  }
  
  function success(message, description) {
    return show({ message, description, type: 'success' })
  }
  
  function error(message, description) {
    return show({ message, description, type: 'error' })
  }
  
  function warning(message, description) {
    return show({ message, description, type: 'warning' })
  }
  
  function info(message, description) {
    return show({ message, description, type: 'info' })
  }
  
  function clear() {
    toasts.value = []
  }
  
  return {
    toasts,
    show,
    remove,
    success,
    error,
    warning,
    info,
    clear
  }
}
