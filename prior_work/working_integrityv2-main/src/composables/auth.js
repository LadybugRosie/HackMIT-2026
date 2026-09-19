/**
 * Authentication Composable
 * Handles user authentication state and API calls
 */
import { ref, computed } from 'vue'
import axios from 'axios'
import { getApiUrl } from '@/utils/api-url'

// Smart API URL detection for production
const AUTH_API = getApiUrl()

// Global auth state
const user = ref(null)
const token = ref(localStorage.getItem('auth_token') || null)
const loading = ref(false)
const error = ref(null)

// Computed
const isAuthenticated = computed(() => !!token.value && !!user.value)
const isTeacher = computed(() => user.value?.role === 'teacher')
const isStudent = computed(() => user.value?.role === 'student' || !user.value?.role)
const isResearcher = computed(() => user.value?.role === 'researcher')
const userRole = computed(() => user.value?.role || 'student')

// Initialize - check if token is valid
async function initAuth() {
  const savedToken = localStorage.getItem('auth_token')
  if (!savedToken) {
    return false
  }
  
  try {
    // FIX #7: Use header (axios interceptor adds Bearer), not query param
    const response = await axios.get(`${AUTH_API}/api/auth/verify`)
    if (response.data.valid) {
      token.value = savedToken
      user.value = response.data.user
      return true
    } else {
      localStorage.removeItem('auth_token')
      token.value = null
      user.value = null
      return false
    }
  } catch (e) {
    console.error('Auth verification failed:', e)
    localStorage.removeItem('auth_token')
    token.value = null
    user.value = null
    return false
  }
}

// Signup with role support
async function signup(email, password, name, university, invitationCode, role = 'student', classCode = null) {
  loading.value = true
  error.value = null
  
  // Teachers require invitation code
  if (role === 'teacher' && (!invitationCode || invitationCode.trim() === '')) {
    error.value = 'Invitation code is required for teacher accounts'
    loading.value = false
    return { success: false, error: error.value }
  }
  
  const requestBody = {
    email,
    password,
    name,
    university,
    role: role
  }
  
  // Add invitation_code for teachers
  if (role === 'teacher' && invitationCode) {
    requestBody.invitation_code = invitationCode.trim()
  }
  
  // Add class_code for students (class to join) and researchers (optional lab code)
  if ((role === 'student' || role === 'researcher') && classCode) {
    requestBody.class_code = classCode.trim().toUpperCase()
  }
  
  try {
    const response = await axios.post(`${AUTH_API}/api/auth/signup`, requestBody)
    
    if (response.data.success) {
      token.value = response.data.token
      user.value = response.data.user
      localStorage.setItem('auth_token', response.data.token)
      return { success: true, user: response.data.user, joinedClass: response.data.joined_class }
    }
  } catch (e) {
    console.error('Signup error:', e)
    console.error('Signup response:', e.response?.data)
    
    // Better error messages
    if (e.response?.data?.detail) {
      if (typeof e.response.data.detail === 'string') {
        error.value = e.response.data.detail
      } else if (Array.isArray(e.response.data.detail)) {
        // Handle Pydantic validation errors
        const errors = e.response.data.detail.map(err => {
          if (err.loc && err.loc.includes('invitation_code')) {
            return 'Invitation code is required for teacher accounts'
          }
          return err.msg || 'Validation error'
        })
        error.value = errors.join(', ')
      } else {
        error.value = 'Signup failed'
      }
    } else if (!e.response) {
      // No response at all - network error or CORS block
      error.value = `Cannot reach server at ${AUTH_API}. Please check if the backend is running.`
    } else {
      error.value = e.response?.data?.message || `Signup failed (${e.response?.status || 'unknown'}). Please try again.`
    }
    return { success: false, error: error.value }
  } finally {
    loading.value = false
  }
}

// Login
async function login(email, password) {
  loading.value = true
  error.value = null
  
  try {
    const response = await axios.post(`${AUTH_API}/api/auth/login`, {
      email,
      password
    })
    
    if (response.data.success) {
      token.value = response.data.token
      user.value = response.data.user
      localStorage.setItem('auth_token', response.data.token)
      return { success: true }
    }
  } catch (e) {
    console.error('Login error:', e)
    if (!e.response) {
      error.value = `Login failed: unable to reach API at ${AUTH_API}. Is the backend running?`
    } else {
      const detail = e.response?.data?.detail
      if (typeof detail === 'string') {
        error.value = detail
      } else if (Array.isArray(detail)) {
        error.value = detail.map(err => err.msg || 'Validation error').join('; ')
      } else {
        error.value = 'Login failed'
      }
    }
    return { success: false, error: error.value }
  } finally {
    loading.value = false
  }
}

// Logout
async function logout() {
  try {
    // FIX #7: Use header, not query param (axios interceptor adds Bearer)
    if (token.value) {
      await axios.post(`${AUTH_API}/api/auth/logout`)
    }
  } catch (e) {
    console.error('Logout error:', e)
  }
  
  token.value = null
  user.value = null
  localStorage.removeItem('auth_token')
}

// Update profile
async function updateProfile(name, university) {
  loading.value = true
  error.value = null
  
  try {
    if (!token.value) {
      throw new Error('Not authenticated - please log in again')
    }
    
    // FIX #7: Use header, not query param
    const response = await axios.put(`${AUTH_API}/api/auth/profile`, {
      name,
      university
    })
    
    if (response.data.success) {
      user.value = response.data.user
      return { success: true }
    }
    
    return { success: false, error: 'Update failed' }
  } catch (e) {
    console.error('Profile update error:', e)
    error.value = e.response?.data?.detail || e.message || 'Update failed'
    
    // If auth error, clear token
    if (e.response?.status === 401) {
      token.value = null
      user.value = null
      localStorage.removeItem('auth_token')
    }
    
    return { success: false, error: error.value }
  } finally {
    loading.value = false
  }
}

// Upload profile image
async function uploadProfileImage(file) {
  loading.value = true
  error.value = null
  
  try {
    if (!token.value) {
      throw new Error('Not authenticated - please log in again')
    }
    
    const formData = new FormData()
    formData.append('image', file)

    const response = await axios.post(`${AUTH_API}/api/auth/upload-image`, formData, {
      headers: {
        'Content-Type': 'multipart/form-data'
      }
    })
    
    if (response.data.success) {
      user.value = { ...user.value, profile_image: response.data.profile_image }
      return { success: true }
    }
    
    return { success: false, error: 'Upload failed' }
  } catch (e) {
    console.error('Image upload error:', e)
    error.value = e.response?.data?.detail || e.message || 'Upload failed'
    
    // If auth error, clear token
    if (e.response?.status === 401) {
      token.value = null
      user.value = null
      localStorage.removeItem('auth_token')
    }
    
    return { success: false, error: error.value }
  } finally {
    loading.value = false
  }
}

// Face biometric functions
async function getFaceSettings() {
  try {
    if (!token.value) return null
    // FIX #7: Use header, not query param
    const response = await axios.get(`${AUTH_API}/api/auth/face/settings`)
    return response.data
  } catch (e) {
    console.error('Failed to get face settings:', e)
    return null
  }
}

async function uploadFaceBaseline(file) {
  loading.value = true
  error.value = null
  
  try {
    if (!token.value) {
      throw new Error('Not authenticated')
    }
    
    const formData = new FormData()
    formData.append('image', file)

    const response = await axios.post(`${AUTH_API}/api/auth/face/upload-baseline`, formData, {
      headers: { 'Content-Type': 'multipart/form-data' }
    })
    
    if (response.data.success) {
      // Update user state
      if (user.value) {
        user.value.face_biometric_enabled = true
        user.value.face_baseline_uploaded = true
      }
      return { success: true, data: response.data }
    }
    return { success: false, error: 'Upload failed' }
  } catch (e) {
    console.error('Face baseline upload error:', e)
    error.value = e.response?.data?.detail || 'Upload failed'
    return { success: false, error: error.value }
  } finally {
    loading.value = false
  }
}

async function toggleFaceBiometric(enabled) {
  loading.value = true
  error.value = null
  
  try {
    if (!token.value) {
      throw new Error('Not authenticated')
    }
    
    // FIX #7: Use header, not query param
    const response = await axios.put(
      `${AUTH_API}/api/auth/face/settings`,
      { face_biometric_enabled: enabled }
    )
    
    if (response.data.success) {
      if (user.value) {
        user.value.face_biometric_enabled = enabled
      }
      return { success: true }
    }
    return { success: false, error: 'Update failed' }
  } catch (e) {
    console.error('Toggle face biometric error:', e)
    error.value = e.response?.data?.detail || 'Update failed'
    return { success: false, error: error.value }
  } finally {
    loading.value = false
  }
}

async function verifyFaceForAccess(imageBase64) {
  try {
    if (!token.value) {
      throw new Error('Not authenticated')
    }
    
    // FIX #7: Use header, not query param
    const response = await axios.post(
      `${AUTH_API}/api/auth/face/verify-access`,
      { image_base64: imageBase64 }
    )
    
    return response.data
  } catch (e) {
    console.error('Face verification error:', e)
    return { verified: false, error: e.response?.data?.detail || 'Verification failed' }
  }
}

export function useAuth() {
  return {
    user,
    token,
    loading,
    error,
    isAuthenticated,
    isTeacher,
    isStudent,
    isResearcher,
    userRole,
    initAuth,
    signup,
    login,
    logout,
    updateProfile,
    uploadProfileImage,
    // Face biometric
    getFaceSettings,
    uploadFaceBaseline,
    toggleFaceBiometric,
    verifyFaceForAccess
  }
}
