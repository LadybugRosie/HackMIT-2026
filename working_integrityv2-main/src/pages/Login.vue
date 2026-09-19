<template>
  <div class="auth-page">
    <div class="auth-card">
      <!-- Logo -->
      <div class="auth-logo">
        <svg width="48" height="48" viewBox="0 0 48 48" class="logo-icon">
          <path fill="#1a73e8" d="M42,37c0,2.762-2.238,5-5,5H11c-2.761,0-5-2.238-5-5V11c0-2.762,2.239-5,5-5h26c2.762,0,5,2.238,5,5V37z"/>
          <path fill="#FFFFFF" d="M24 16A5 5 0 1 0 24 26A5 5 0 1 0 24 16Z"/>
          <path fill="#FFFFFF" d="M33,30c0-3.5-3.5-5-9-5s-9,1.5-9,5v2h18V30z"/>
        </svg>
      </div>
      
      <h1>Sign in</h1>
      <p class="auth-subtitle">to continue to Editorrah</p>
      
      <!-- Role Selector Tabs -->
      <div class="role-tabs">
        <button 
          type="button"
          :class="['role-tab', { active: selectedRole === 'student' }]"
          @click="selectedRole = 'student'"
        >
          <svg width="20" height="20" viewBox="0 0 24 24" fill="currentColor">
            <path d="M12 3L1 9l4 2.18v6L12 21l7-3.82v-6l2-1.09V17h2V9L12 3zm6.82 6L12 12.72 5.18 9 12 5.28 18.82 9zM17 15.99l-5 2.73-5-2.73v-3.72L12 15l5-2.73v3.72z"/>
          </svg>
          Student
        </button>
        <button
          type="button"
          :class="['role-tab', { active: selectedRole === 'teacher' }]"
          @click="selectedRole = 'teacher'"
        >
          <svg width="20" height="20" viewBox="0 0 24 24" fill="currentColor">
            <path d="M5 13.18v4L12 21l7-3.82v-4L12 17l-7-3.82zM12 3L1 9l11 6 9-4.91V17h2V9L12 3z"/>
          </svg>
          Teacher
        </button>
        <button
          type="button"
          :class="['role-tab', { active: selectedRole === 'researcher' }]"
          @click="selectedRole = 'researcher'"
        >
          <svg width="20" height="20" viewBox="0 0 24 24" fill="currentColor">
            <path d="M19.8 18.4L14 10.67V6.5l1.35-1.69c.26-.33.03-.81-.39-.81H9.04c-.42 0-.65.48-.39.81L10 6.5v4.17L4.2 18.4c-.49.66-.02 1.6.8 1.6h14c.82 0 1.29-.94.8-1.6z"/>
          </svg>
          Researcher
        </button>
      </div>

      <p class="role-hint">
        {{ selectedRole === 'teacher' ? 'Sign in to manage your classes and assignments' : selectedRole === 'researcher' ? 'Sign in to access your lab and integrity-verified writing environment' : 'Sign in to access your courses and submit work' }}
      </p>
      
      <form @submit.prevent="handleLogin" class="auth-form">
        <div class="form-field">
          <input 
            type="email" 
            id="email" 
            v-model="email"
            placeholder=" "
            required
            :disabled="loading"
          />
          <label for="email">Email</label>
        </div>
        
        <div class="form-field">
          <input 
            type="password" 
            id="password" 
            v-model="password"
            placeholder=" "
            required
            :disabled="loading"
          />
          <label for="password">Password</label>
        </div>
        
        <div v-if="errorMessage" class="error-msg">
          {{ errorMessage }}
        </div>
        
        <div class="forgot-password">
          <a href="#" class="link-btn small" @click.prevent="showForgotModal = true">Forgot password?</a>
        </div>
        
        <div class="form-actions">
          <router-link :to="'/signup?role=' + selectedRole" class="link-btn">Create account</router-link>
          <button type="submit" class="primary-btn" :disabled="loading">
            <span v-if="loading" class="spinner"></span>
            <span v-else>Sign in</span>
          </button>
        </div>
      </form>
    </div>
    
    <!-- Forgot Password Modal -->
    <div v-if="showForgotModal" class="modal-overlay" @click.self="closeForgotModal">
      <div class="modal-card">
        <h2>Reset your password</h2>
        <p class="modal-subtitle">Enter your email and we'll send you a reset link.</p>

        <form @submit.prevent="handleForgotPassword" class="auth-form">
          <div class="form-field">
            <input
              type="email"
              id="forgotEmail"
              v-model="forgotEmail"
              placeholder=" "
              required
              :disabled="forgotLoading"
            />
            <label for="forgotEmail">Email</label>
          </div>

          <div v-if="forgotSuccess" class="success-msg">
            If an account exists with that email, we've sent a password reset link. Please check your inbox.
          </div>

          <div v-if="forgotError" class="error-msg">
            {{ forgotError }}
          </div>

          <div class="form-actions">
            <button type="button" class="link-btn" @click="closeForgotModal">Cancel</button>
            <button type="submit" class="primary-btn" :disabled="forgotLoading || forgotSuccess">
              <span v-if="forgotLoading" class="spinner"></span>
              <span v-else-if="forgotSuccess">Sent</span>
              <span v-else>Send reset link</span>
            </button>
          </div>
        </form>
      </div>
    </div>

    <footer class="auth-footer">
      <select class="lang-select">
        <option>English (United States)</option>
      </select>
      <div class="footer-links">
        <a href="#">Help</a>
        <a href="#">Privacy</a>
        <a href="#">Terms</a>
      </div>
    </footer>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { useAuth } from '@/composables/auth'
import axios from 'axios'
import { getApiUrl } from '@/utils/api-url'

const router = useRouter()
const route = useRoute()
const { login, loading, user } = useAuth()

const email = ref('')
const password = ref('')
const errorMessage = ref('')
const selectedRole = ref('student')

// Check URL params for pre-selected role
onMounted(() => {
  if (route.query.role === 'teacher' || route.query.role === 'researcher') {
    selectedRole.value = route.query.role
  }
})

const showForgotModal = ref(false)
const forgotEmail = ref('')
const forgotLoading = ref(false)
const forgotSuccess = ref(false)
const forgotError = ref('')

function closeForgotModal() {
  showForgotModal.value = false
  forgotEmail.value = ''
  forgotSuccess.value = false
  forgotError.value = ''
}

async function handleForgotPassword() {
  forgotError.value = ''
  forgotSuccess.value = false

  if (!forgotEmail.value) {
    forgotError.value = 'Please enter your email'
    return
  }

  forgotLoading.value = true
  try {
    const API = getApiUrl()
    await axios.post(`${API}/api/auth/forgot-password`, {
      email: forgotEmail.value
    })
    forgotSuccess.value = true
  } catch (err) {
    forgotError.value = 'Something went wrong. Please try again.'
  } finally {
    forgotLoading.value = false
  }
}

async function handleLogin() {
  errorMessage.value = ''
  
  if (!email.value || !password.value) {
    errorMessage.value = 'Please fill in all fields'
    return
  }
  
  const result = await login(email.value, password.value)
  
  if (result.success) {
    // Check if user role matches selected role
    const userRole = user.value?.role || 'student'
    if (userRole !== selectedRole.value) {
      errorMessage.value = `This account is registered as a ${userRole}. Please select the correct role above or use a different account.`
      return
    }
    
    // Honor a ?next= redirect (e.g. a co-author invite link), else role dashboard.
    if (route.query.next) {
      router.push(String(route.query.next))
    } else if (user.value?.role === 'teacher') {
      router.push('/teacher/dashboard')
    } else if (user.value?.role === 'researcher') {
      router.push('/researcher/dashboard')
    } else {
      router.push('/student/dashboard')
    }
  } else {
    errorMessage.value = result.error
  }
}
</script>

<style scoped>
.auth-page {
  min-height: 100vh;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  background: #f8f9fa;
  padding: 20px;
  font-family: 'Google Sans', 'Roboto', -apple-system, BlinkMacSystemFont, sans-serif;
}

.auth-card {
  width: 100%;
  max-width: 450px;
  background: white;
  border: 1px solid #dadce0;
  border-radius: 8px;
  padding: 48px 40px;
  text-align: center;
}

.auth-logo {
  margin-bottom: 16px;
}

h1 {
  font-size: 24px;
  font-weight: 400;
  color: #202124;
  margin: 0 0 8px 0;
}

.auth-subtitle {
  font-size: 16px;
  color: #5f6368;
  margin: 0 0 24px 0;
}

/* Role Tabs */
.role-tabs {
  display: flex;
  gap: 8px;
  margin-bottom: 16px;
}

.role-tab {
  flex: 1;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 6px;
  padding: 14px 8px;
  border: 2px solid #dadce0;
  border-radius: 12px;
  background: white;
  color: #5f6368;
  font-size: 14px;
  font-weight: 500;
  cursor: pointer;
  transition: all 0.2s ease;
}

.role-tab:hover:not(.active) {
  border-color: #1a73e8;
  background: #f8f9fa;
}

.role-tab.active {
  border-color: #1a73e8;
  background: #e8f0fe;
  color: #1a73e8;
}

.role-tab svg {
  flex-shrink: 0;
}

.role-hint {
  font-size: 13px;
  color: #5f6368;
  text-align: center;
  margin: 0 0 24px 0;
  min-height: 18px;
}

.auth-form {
  text-align: left;
}

.form-field {
  position: relative;
  margin-bottom: 24px;
}

.form-field input {
  width: 100%;
  padding: 16px;
  border: 1px solid #dadce0;
  border-radius: 4px;
  font-size: 16px;
  color: #202124;
  transition: border-color 0.2s;
  box-sizing: border-box;
}

.form-field input:focus {
  outline: none;
  border-color: #1a73e8;
  border-width: 2px;
  padding: 15px;
}

.form-field label {
  position: absolute;
  left: 16px;
  top: 50%;
  transform: translateY(-50%);
  font-size: 16px;
  color: #5f6368;
  pointer-events: none;
  transition: all 0.15s ease;
  background: white;
  padding: 0 4px;
}

.form-field input:focus + label,
.form-field input:not(:placeholder-shown) + label {
  top: 0;
  font-size: 12px;
  color: #1a73e8;
}

.form-field input:not(:focus):not(:placeholder-shown) + label {
  color: #5f6368;
}

.error-msg {
  background: #fce8e6;
  color: #c5221f;
  padding: 12px 16px;
  border-radius: 4px;
  font-size: 14px;
  margin-bottom: 24px;
}

.form-actions {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-top: 32px;
}

.link-btn {
  font-size: 14px;
  font-weight: 500;
  color: #1a73e8;
  text-decoration: none;
}

.link-btn:hover {
  text-decoration: underline;
}

.link-btn.small {
  font-size: 13px;
}

.forgot-password {
  text-align: right;
  margin-bottom: 16px;
}

.primary-btn {
  padding: 10px 24px;
  background: #1a73e8;
  color: white;
  border: none;
  border-radius: 4px;
  font-size: 14px;
  font-weight: 500;
  cursor: pointer;
  transition: background 0.2s, box-shadow 0.2s;
  min-width: 90px;
  display: flex;
  align-items: center;
  justify-content: center;
}

.primary-btn:hover:not(:disabled) {
  background: #1557b0;
  box-shadow: 0 1px 2px rgba(0, 0, 0, 0.3);
}

.primary-btn:disabled {
  opacity: 0.7;
  cursor: not-allowed;
}

.spinner {
  width: 18px;
  height: 18px;
  border: 2px solid rgba(255, 255, 255, 0.3);
  border-top-color: white;
  border-radius: 50%;
  animation: spin 0.8s linear infinite;
}

@keyframes spin {
  to { transform: rotate(360deg); }
}

.auth-footer {
  display: flex;
  justify-content: space-between;
  align-items: center;
  width: 100%;
  max-width: 450px;
  margin-top: 24px;
  padding: 0 8px;
}

.lang-select {
  border: none;
  background: transparent;
  font-size: 12px;
  color: #5f6368;
  cursor: pointer;
}

.footer-links {
  display: flex;
  gap: 24px;
}

.footer-links a {
  font-size: 12px;
  color: #5f6368;
  text-decoration: none;
}

.footer-links a:hover {
  color: #202124;
}

/* Forgot Password Modal */
.modal-overlay {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background: rgba(0, 0, 0, 0.5);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 1000;
  padding: 20px;
}

.modal-card {
  background: white;
  border-radius: 8px;
  padding: 40px;
  width: 100%;
  max-width: 400px;
  text-align: center;
}

.modal-card h2 {
  font-size: 20px;
  font-weight: 400;
  color: #202124;
  margin: 0 0 8px 0;
}

.modal-subtitle {
  font-size: 14px;
  color: #5f6368;
  margin: 0 0 24px 0;
}

.success-msg {
  background: #e6f4ea;
  color: #137333;
  padding: 12px 16px;
  border-radius: 4px;
  font-size: 14px;
  margin-bottom: 16px;
  text-align: left;
}

@media (max-width: 480px) {
  .auth-card {
    padding: 32px 24px;
  }
  
  .form-actions {
    flex-direction: column-reverse;
    gap: 24px;
  }
  
  .primary-btn {
    width: 100%;
  }
}
</style>
