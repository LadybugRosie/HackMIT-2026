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
      
      <h1>Create your Account</h1>
      <p class="auth-subtitle">to continue to Editorrah</p>
      
      <!-- Role Selection Tabs (Top of Form) -->
      <div class="role-tabs">
        <button 
          type="button"
          :class="['role-tab', { active: role === 'student' }]"
          @click="role = 'student'"
          :disabled="loading"
        >
          <svg width="20" height="20" viewBox="0 0 24 24" fill="currentColor">
            <path d="M12 3L1 9l4 2.18v6L12 21l7-3.82v-6l2-1.09V17h2V9L12 3zm6.82 6L12 12.72 5.18 9 12 5.28 18.82 9zM17 15.99l-5 2.73-5-2.73v-3.72L12 15l5-2.73v3.72z"/>
          </svg>
          Student
        </button>
        <button
          type="button"
          :class="['role-tab', { active: role === 'teacher' }]"
          @click="role = 'teacher'"
          :disabled="loading"
        >
          <svg width="20" height="20" viewBox="0 0 24 24" fill="currentColor">
            <path d="M5 13.18v4L12 21l7-3.82v-4L12 17l-7-3.82zM12 3L1 9l11 6 9-4.91V17h2V9L12 3z"/>
          </svg>
          Teacher
        </button>
        <button
          type="button"
          :class="['role-tab', { active: role === 'researcher' }]"
          @click="role = 'researcher'"
          :disabled="loading"
        >
          <svg width="20" height="20" viewBox="0 0 24 24" fill="currentColor">
            <path d="M19.8 18.4L14 10.67V6.5l1.35-1.69c.26-.33.03-.81-.39-.81H9.04c-.42 0-.65.48-.39.81L10 6.5v4.17L4.2 18.4c-.49.66-.02 1.6.8 1.6h14c.82 0 1.29-.94.8-1.6z"/>
          </svg>
          Researcher
        </button>
      </div>

      <div class="role-info-banner" :class="role">
        <div class="role-info-icon">
          <svg v-if="role === 'student'" width="24" height="24" viewBox="0 0 24 24" fill="currentColor">
            <path d="M12 3L1 9l4 2.18v6L12 21l7-3.82v-6l2-1.09V17h2V9L12 3z"/>
          </svg>
          <svg v-else-if="role === 'researcher'" width="24" height="24" viewBox="0 0 24 24" fill="currentColor">
            <path d="M19.8 18.4L14 10.67V6.5l1.35-1.69c.26-.33.03-.81-.39-.81H9.04c-.42 0-.65.48-.39.81L10 6.5v4.17L4.2 18.4c-.49.66-.02 1.6.8 1.6h14c.82 0 1.29-.94.8-1.6z"/>
          </svg>
          <svg v-else width="24" height="24" viewBox="0 0 24 24" fill="currentColor">
            <path d="M5 13.18v4L12 21l7-3.82v-4L12 17l-7-3.82zM12 3L1 9l11 6 9-4.91V17h2V9L12 3z"/>
          </svg>
        </div>
        <div class="role-info-text">
          <strong>{{ role === 'teacher' ? 'Teacher Account' : role === 'researcher' ? 'Researcher Account' : 'Student Account' }}</strong>
          <span>{{ role === 'teacher' ? 'Create classes, assignments, and grade student work' : role === 'researcher' ? 'Researcher accounts get an integrity-verified writing environment with stylometry, session replay video, and shareable proof-of-authorship.' : 'Join classes, submit assignments, and track your progress' }}</span>
        </div>
      </div>
      
      <form @submit.prevent="handleSignup" class="auth-form">
        <div class="form-row">
          <div class="form-field">
            <input 
              type="text" 
              id="name" 
              v-model="name"
              placeholder=" "
              required
              :disabled="loading"
            />
            <label for="name">Full name</label>
          </div>
        </div>
        
        <div class="form-field">
          <input 
            type="email" 
            id="email" 
            v-model="email"
            placeholder=" "
            required
            :disabled="loading"
          />
          <label for="email">Email address</label>
        </div>
        
        <div class="form-field">
          <input 
            type="text" 
            id="university" 
            v-model="university"
            placeholder=" "
            required
            :disabled="loading"
          />
          <label for="university">University / Institution</label>
        </div>

        <!-- Teacher: Invitation Code (required) -->
        <div v-if="role === 'teacher'" class="form-field">
          <input 
            type="text" 
            id="invitationCode" 
            v-model="invitationCode"
            placeholder=" "
            required
            maxlength="12"
            pattern="[0-9]{12}"
            :disabled="loading"
          />
          <label for="invitationCode">Teacher Invitation Code (12 digits)</label>
          <span class="field-hint">Get this code from your institution administrator</span>
        </div>

        <!-- Researcher: Lab Code (optional) -->
        <div v-else-if="role === 'researcher'" class="form-field">
          <input
            type="text"
            id="labCode"
            v-model="labCode"
            placeholder=" "
            maxlength="8"
            :disabled="loading"
            style="text-transform: uppercase;"
          />
          <label for="labCode">Lab Code (optional)</label>
          <span class="field-hint">Have a lab code? Enter it to join the lab — leave blank to create your own lab</span>
        </div>

        <!-- Student: Class Code (optional) -->
        <div v-else class="form-field">
          <input
            type="text"
            id="classCode"
            v-model="classCode"
            placeholder=" "
            maxlength="8"
            :disabled="loading"
            style="text-transform: uppercase;"
          />
          <label for="classCode">Class Code (optional)</label>
          <span class="field-hint">Have a class code from your teacher? Enter it to auto-join the class</span>
        </div>
        
        <div class="form-row">
          <div class="form-field">
            <input 
              type="password" 
              id="password" 
              v-model="password"
              placeholder=" "
              required
              minlength="8"
              :disabled="loading"
            />
            <label for="password">Password</label>
          </div>
          <div class="form-field">
            <input 
              type="password" 
              id="confirmPassword" 
              v-model="confirmPassword"
              placeholder=" "
              required
              :disabled="loading"
            />
            <label for="confirmPassword">Confirm</label>
          </div>
        </div>
        
        <p class="password-hint">Min 8 characters with uppercase, number, and special character</p>
        
        <div v-if="errorMessage" class="error-msg">
          {{ errorMessage }}
        </div>
        
        <div class="form-actions">
          <router-link :to="'/login?role=' + role" class="link-btn">Sign in instead</router-link>
          <button type="submit" class="primary-btn" :disabled="loading">
            <span v-if="loading" class="spinner"></span>
            <span v-else>Create account</span>
          </button>
        </div>
      </form>
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

const router = useRouter()
const route = useRoute()
const { signup, loading } = useAuth()

const name = ref('')
const email = ref('')
const university = ref('')
const password = ref('')
const confirmPassword = ref('')
const invitationCode = ref('')
const classCode = ref('')
const labCode = ref('')
const role = ref('student')
const errorMessage = ref('')

// Check URL params for pre-selected role and class code
onMounted(() => {
  if (route.query.role === 'teacher' || route.query.role === 'researcher') {
    role.value = route.query.role
  }
  if (route.query.class_code) {
    classCode.value = route.query.class_code
  }
})

async function handleSignup() {
  errorMessage.value = ''
  
  if (!name.value || !email.value || !university.value || !password.value) {
    errorMessage.value = 'Please fill in all required fields'
    return
  }
  
  // Teachers require invitation code
  if (role.value === 'teacher') {
    if (!invitationCode.value) {
      errorMessage.value = 'Invitation code is required for teacher accounts'
      return
    }
    if (invitationCode.value.length !== 12 || !/^\d{12}$/.test(invitationCode.value)) {
      errorMessage.value = 'Invitation code must be exactly 12 digits'
      return
    }
  }
  
  if (password.value !== confirmPassword.value) {
    errorMessage.value = 'Passwords do not match'
    return
  }
  
  if (password.value.length < 8) {
    errorMessage.value = 'Password must be at least 8 characters'
    return
  }
  if (!/[A-Z]/.test(password.value)) {
    errorMessage.value = 'Password must contain at least one uppercase letter'
    return
  }
  if (!/[0-9]/.test(password.value)) {
    errorMessage.value = 'Password must contain at least one number'
    return
  }
  if (!/[!@#$%^&*()_+\-=\[\]{}|;:,.<>?/~`]/.test(password.value)) {
    errorMessage.value = 'Password must contain at least one special character'
    return
  }
  
  const result = await signup(
    email.value,
    password.value,
    name.value,
    university.value,
    role.value === 'teacher' ? invitationCode.value : null,
    role.value,
    role.value === 'student' ? classCode.value.trim().toUpperCase() || null
      : role.value === 'researcher' ? labCode.value.trim().toUpperCase() || null
      : null
  )

  if (result.success) {
    // Honor a ?next= redirect (e.g. a co-author invite link), else role dashboard.
    if (route.query.next) {
      router.push(String(route.query.next))
    } else if (role.value === 'teacher') {
      router.push('/teacher/dashboard')
    } else if (role.value === 'researcher') {
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
  margin: 0 0 20px 0;
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

.role-tab:hover:not(.active):not(:disabled) {
  border-color: #1a73e8;
  background: #f8f9fa;
}

.role-tab.active {
  border-color: #1a73e8;
  background: #e8f0fe;
  color: #1a73e8;
}

.role-tab:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}

.role-tab svg {
  flex-shrink: 0;
}

/* Role Info Banner */
.role-info-banner {
  display: flex;
  align-items: flex-start;
  gap: 12px;
  padding: 16px;
  border-radius: 12px;
  margin-bottom: 24px;
  transition: all 0.3s ease;
}

.role-info-banner.student {
  background: linear-gradient(135deg, #e8f5e9 0%, #c8e6c9 100%);
  border: 1px solid #a5d6a7;
}

.role-info-banner.teacher {
  background: linear-gradient(135deg, #e3f2fd 0%, #bbdefb 100%);
  border: 1px solid #90caf9;
}

.role-info-banner.researcher {
  background: linear-gradient(135deg, #f3e8ff 0%, #e9d5ff 100%);
  border: 1px solid #d8b4fe;
}

.role-info-icon {
  width: 40px;
  height: 40px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}

.role-info-banner.student .role-info-icon {
  background: #4caf50;
  color: white;
}

.role-info-banner.teacher .role-info-icon {
  background: #1a73e8;
  color: white;
}

.role-info-banner.researcher .role-info-icon {
  background: #7c3aed;
  color: white;
}

.role-info-text {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.role-info-text strong {
  font-size: 15px;
  color: #202124;
}

.role-info-text span {
  font-size: 13px;
  color: #5f6368;
}

.field-hint {
  display: block;
  font-size: 12px;
  color: #5f6368;
  margin-top: 6px;
}

.auth-form {
  text-align: left;
}

.form-row {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 16px;
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

.password-hint {
  font-size: 12px;
  color: #5f6368;
  margin: -16px 0 24px 0;
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
  min-width: 130px;
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

@media (max-width: 480px) {
  .auth-card {
    padding: 32px 24px;
  }
  
  .form-row {
    grid-template-columns: 1fr;
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
