<template>
  <div class="auth-page">
    <div class="auth-card">
      <div class="auth-logo">
        <svg width="48" height="48" viewBox="0 0 48 48" class="logo-icon">
          <path fill="#1a73e8" d="M42,37c0,2.762-2.238,5-5,5H11c-2.761,0-5-2.238-5-5V11c0-2.762,2.239-5,5-5h26c2.762,0,5,2.238,5,5V37z"/>
          <path fill="#FFFFFF" d="M24 16A5 5 0 1 0 24 26A5 5 0 1 0 24 16Z"/>
          <path fill="#FFFFFF" d="M33,30c0-3.5-3.5-5-9-5s-9,1.5-9,5v2h18V30z"/>
        </svg>
      </div>

      <!-- Success state -->
      <template v-if="success">
        <h1>Password reset</h1>
        <p class="auth-subtitle">Your password has been reset successfully.</p>
        <div class="success-icon">
          <svg width="64" height="64" viewBox="0 0 24 24" fill="#34a853">
            <path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm-2 15l-5-5 1.41-1.41L10 14.17l7.59-7.59L19 8l-9 9z"/>
          </svg>
        </div>
        <div class="form-actions" style="justify-content: center; margin-top: 24px;">
          <router-link to="/login" class="primary-btn" style="text-decoration: none;">Sign in</router-link>
        </div>
      </template>

      <!-- Reset form -->
      <template v-else>
        <h1>Set new password</h1>
        <p class="auth-subtitle">Enter your new password below</p>

        <form @submit.prevent="handleReset" class="auth-form">
          <div class="form-field">
            <input
              type="password"
              id="password"
              v-model="password"
              placeholder=" "
              required
              :disabled="submitting"
            />
            <label for="password">New password</label>
          </div>

          <div class="form-field">
            <input
              type="password"
              id="confirmPassword"
              v-model="confirmPassword"
              placeholder=" "
              required
              :disabled="submitting"
            />
            <label for="confirmPassword">Confirm password</label>
          </div>

          <ul class="password-rules">
            <li :class="{ met: password.length >= 8 }">At least 8 characters</li>
            <li :class="{ met: /[A-Z]/.test(password) }">One uppercase letter</li>
            <li :class="{ met: /[0-9]/.test(password) }">One number</li>
            <li :class="{ met: /[!@#$%^&*()_+\-=\[\]{}|;:,.<>?\/~`]/.test(password) }">One special character</li>
          </ul>

          <div v-if="errorMessage" class="error-msg">
            {{ errorMessage }}
          </div>

          <div class="form-actions">
            <router-link to="/login" class="link-btn">Back to sign in</router-link>
            <button type="submit" class="primary-btn" :disabled="submitting">
              <span v-if="submitting" class="spinner"></span>
              <span v-else>Reset password</span>
            </button>
          </div>
        </form>
      </template>
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
import { useRoute, useRouter } from 'vue-router'
import axios from 'axios'
import { getApiUrl } from '@/utils/api-url'

const route = useRoute()
const router = useRouter()
const API = getApiUrl()

const password = ref('')
const confirmPassword = ref('')
const errorMessage = ref('')
const submitting = ref(false)
const success = ref(false)
const resetToken = ref('')

onMounted(() => {
  resetToken.value = route.query.token || ''
  if (!resetToken.value) {
    errorMessage.value = 'Invalid reset link. Please request a new one.'
  }
})

async function handleReset() {
  errorMessage.value = ''

  if (!resetToken.value) {
    errorMessage.value = 'Invalid reset link. Please request a new one.'
    return
  }

  if (password.value !== confirmPassword.value) {
    errorMessage.value = 'Passwords do not match'
    return
  }

  if (password.value.length < 8) {
    errorMessage.value = 'Password must be at least 8 characters'
    return
  }

  submitting.value = true

  try {
    const response = await axios.post(`${API}/api/auth/reset-password`, {
      token: resetToken.value,
      new_password: password.value
    })

    if (response.data.success) {
      success.value = true
    }
  } catch (err) {
    const detail = err.response?.data?.detail
    if (typeof detail === 'string') {
      errorMessage.value = detail
    } else if (Array.isArray(detail)) {
      errorMessage.value = detail.map(d => d.msg || d).join('. ')
    } else {
      errorMessage.value = 'Something went wrong. Please try again.'
    }
  } finally {
    submitting.value = false
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

.success-icon {
  margin: 24px 0;
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

.password-rules {
  list-style: none;
  padding: 0;
  margin: 0 0 16px 0;
  font-size: 12px;
  color: #5f6368;
}

.password-rules li {
  padding: 2px 0 2px 20px;
  position: relative;
}

.password-rules li::before {
  content: '\2715';
  position: absolute;
  left: 0;
  color: #dadce0;
}

.password-rules li.met::before {
  content: '\2713';
  color: #34a853;
}

.password-rules li.met {
  color: #34a853;
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
