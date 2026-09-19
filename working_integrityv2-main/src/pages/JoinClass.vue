<template>
  <div class="join-class-page">
    <div class="join-container">
      <div class="join-card">
        <div class="card-header">
          <router-link to="/student/dashboard" class="back-link">
            <svg width="24" height="24" viewBox="0 0 24 24" fill="currentColor">
              <path d="M20 11H7.83l5.59-5.59L12 4l-8 8 8 8 1.41-1.41L7.83 13H20v-2z"/>
            </svg>
          </router-link>
          <h1>Join a Class</h1>
        </div>

        <div class="card-body">
          <div class="icon-wrapper">
            <svg width="80" height="80" viewBox="0 0 24 24" fill="#1a73e8">
              <path d="M12 3L1 9l4 2.18v6L12 21l7-3.82v-6l2-1.09V17h2V9L12 3zm6.82 6L12 12.72 5.18 9 12 5.28 18.82 9zM17 15.99l-5 2.73-5-2.73v-3.72L12 15l5-2.73v3.72z"/>
            </svg>
          </div>

          <p class="instructions">
            Ask your teacher for the class code, then enter it below.
          </p>

          <div class="form-group">
            <label>Class Code</label>
            <input 
              v-model="classCode" 
              type="text" 
              placeholder="Enter class code"
              class="code-input"
              :class="{ error: error }"
              @keyup.enter="joinClass"
              @input="error = ''"
              maxlength="8"
            />
            <p v-if="error" class="error-text">{{ error }}</p>
          </div>

          <div class="code-tips">
            <h4>Where to find the code:</h4>
            <ul>
              <li>Ask your teacher for the class code</li>
              <li>Class codes are typically 6-8 characters</li>
              <li>The code is case-insensitive</li>
            </ul>
          </div>
        </div>

        <div class="card-footer">
          <router-link to="/student/dashboard" class="btn-text">Cancel</router-link>
          <button 
            class="btn-primary" 
            @click="joinClass"
            :disabled="!classCode.trim() || joining"
          >
            {{ joining ? 'Joining...' : 'Join' }}
          </button>
        </div>
      </div>

      <!-- Success Modal -->
      <div v-if="showSuccess" class="success-overlay">
        <div class="success-modal">
          <div class="success-icon">
            <svg width="64" height="64" viewBox="0 0 24 24" fill="#1e8e3e">
              <path d="M9 16.17L4.83 12l-1.42 1.41L9 19 21 7l-1.41-1.41z"/>
            </svg>
          </div>
          <h2>You're in!</h2>
          <p>You've successfully joined <strong>{{ joinedClass?.name }}</strong></p>
          <button class="btn-primary" @click="goToClass">Go to Class</button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { useClasses } from '@/composables/classroom'

const router = useRouter()
const { joinClass: join } = useClasses()

const classCode = ref('')
const error = ref('')
const joining = ref(false)
const showSuccess = ref(false)
const joinedClass = ref(null)

async function joinClass() {
  if (!classCode.value.trim()) return
  
  joining.value = true
  error.value = ''
  
  const result = await join(classCode.value.trim().toUpperCase())
  
  joining.value = false
  
  if (result.success) {
    joinedClass.value = result.data
    showSuccess.value = true
  } else {
    error.value = result.error || 'Invalid class code. Please check and try again.'
  }
}

function goToClass() {
  if (joinedClass.value?.class_id) {
    router.push(`/student/class/${joinedClass.value.class_id}`)
  } else {
    router.push('/student/dashboard')
  }
}
</script>

<style scoped>
.join-class-page {
  min-height: 100vh;
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 20px;
}

.join-container {
  width: 100%;
  max-width: 480px;
}

.join-card {
  background: white;
  border-radius: 16px;
  overflow: hidden;
  box-shadow: 0 20px 40px rgba(0,0,0,0.2);
}

.card-header {
  display: flex;
  align-items: center;
  gap: 16px;
  padding: 20px 24px;
  border-bottom: 1px solid #e0e0e0;
}

.back-link {
  width: 40px;
  height: 40px;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: 50%;
  color: #5f6368;
  text-decoration: none;
}

.back-link:hover {
  background: #f1f3f4;
}

.card-header h1 {
  font-size: 20px;
  font-weight: 500;
  margin: 0;
  color: #202124;
}

.card-body {
  padding: 32px 24px;
}

.icon-wrapper {
  text-align: center;
  margin-bottom: 24px;
}

.instructions {
  text-align: center;
  color: #5f6368;
  margin: 0 0 24px;
  font-size: 16px;
}

.form-group {
  margin-bottom: 24px;
}

.form-group label {
  display: block;
  font-weight: 500;
  margin-bottom: 8px;
  color: #202124;
}

.code-input {
  width: 100%;
  padding: 20px;
  border: 2px solid #dadce0;
  border-radius: 12px;
  font-size: 24px;
  text-align: center;
  text-transform: uppercase;
  letter-spacing: 6px;
  box-sizing: border-box;
  transition: border-color 0.2s;
  color: #202124 !important;
  background: #fff !important;
}

.code-input:focus {
  outline: none;
  border-color: #1a73e8;
}

.code-input.error {
  border-color: #d93025;
}

.error-text {
  color: #d93025;
  font-size: 14px;
  margin: 8px 0 0;
  text-align: center;
}

.code-tips {
  background: #f8f9fa;
  border-radius: 12px;
  padding: 16px 20px;
}

.code-tips h4 {
  margin: 0 0 12px;
  font-size: 14px;
  color: #202124;
}

.code-tips ul {
  margin: 0;
  padding-left: 20px;
}

.code-tips li {
  font-size: 14px;
  color: #5f6368;
  margin-bottom: 8px;
}

.code-tips li:last-child {
  margin-bottom: 0;
}

.card-footer {
  display: flex;
  justify-content: flex-end;
  gap: 12px;
  padding: 16px 24px;
  border-top: 1px solid #e0e0e0;
  background: #f8f9fa;
}

.btn-text {
  padding: 12px 24px;
  border: none;
  background: transparent;
  color: #5f6368;
  font-weight: 500;
  text-decoration: none;
  border-radius: 8px;
  cursor: pointer;
}

.btn-text:hover {
  background: #e8e8e8;
}

.btn-primary {
  padding: 12px 32px;
  border: none;
  background: #1a73e8;
  color: white;
  font-weight: 500;
  border-radius: 8px;
  cursor: pointer;
  transition: background 0.2s;
}

.btn-primary:hover:not(:disabled) {
  background: #1557b0;
}

.btn-primary:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

/* Success Modal */
.success-overlay {
  position: fixed;
  inset: 0;
  background: rgba(0,0,0,0.6);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 1000;
}

.success-modal {
  background: white;
  border-radius: 16px;
  padding: 40px;
  text-align: center;
  max-width: 360px;
  width: 90%;
}

.success-icon {
  margin-bottom: 20px;
}

.success-modal h2 {
  margin: 0 0 12px;
  font-size: 24px;
  color: #202124;
}

.success-modal p {
  margin: 0 0 24px;
  color: #5f6368;
}

.success-modal .btn-primary {
  width: 100%;
}
</style>
