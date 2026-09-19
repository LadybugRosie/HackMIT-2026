<template>
  <div class="profile-page">
    <!-- Header -->
    <header class="profile-header">
      <div class="header-left">
        <button class="back-btn" @click="goToDashboard">
          <svg width="24" height="24" viewBox="0 0 24 24" fill="currentColor">
            <path d="M20 11H7.83l5.59-5.59L12 4l-8 8 8 8 1.41-1.41L7.83 13H20v-2z"/>
          </svg>
        </button>
        <span class="header-title">Profile</span>
      </div>
    </header>
    
    <main class="profile-main">
      <div class="profile-card">
        <!-- Profile Image -->
        <div class="profile-image-section">
          <div class="image-wrapper" @click="triggerImageUpload">
            <img 
              v-if="user?.profile_image" 
              :src="user.profile_image" 
              alt="Profile"
              class="profile-image"
              @error="handleImageError"
            />
            <div v-else class="profile-placeholder">
              <svg width="64" height="64" viewBox="0 0 24 24" fill="#9aa0a6">
                <path d="M12 12c2.21 0 4-1.79 4-4s-1.79-4-4-4-4 1.79-4 4 1.79 4 4 4zm0 2c-2.67 0-8 1.34-8 4v2h16v-2c0-2.66-5.33-4-8-4z"/>
              </svg>
            </div>
            <div class="image-overlay">
              <svg width="24" height="24" viewBox="0 0 24 24" fill="white">
                <path d="M3 4V1h2v3h3v2H5v3H3V6H0V4h3zm3 6V7h3V4h7l1.83 2H21c1.1 0 2 .9 2 2v12c0 1.1-.9 2-2 2H5c-1.1 0-2-.9-2-2V10h3zm7 9c2.76 0 5-2.24 5-5s-2.24-5-5-5-5 2.24-5 5 2.24 5 5 5zm-3.2-5c0 1.77 1.43 3.2 3.2 3.2s3.2-1.43 3.2-3.2-1.43-3.2-3.2-3.2-3.2 1.43-3.2 3.2z"/>
              </svg>
            </div>
          </div>
          <input 
            type="file" 
            ref="fileInput" 
            @change="handleImageUpload" 
            accept="image/*"
            style="display: none"
          />
          <p class="image-hint">Click to change profile photo</p>
        </div>
        
        <!-- Profile Form -->
        <form @submit.prevent="handleUpdate" class="profile-form">
          <div class="form-section">
            <h3>Basic info</h3>
            
            <div class="form-field">
              <label for="name">Name</label>
              <input 
                type="text" 
                id="name" 
                v-model="name" 
                :disabled="loading"
              />
            </div>
            
            <div class="form-field">
              <label for="email">Email</label>
              <input 
                type="email" 
                id="email" 
                :value="user?.email" 
                disabled
                class="disabled"
              />
              <span class="field-hint">Email cannot be changed</span>
            </div>
            
            <div class="form-field">
              <label for="university">University</label>
              <input 
                type="text" 
                id="university" 
                v-model="university" 
                :disabled="loading"
              />
            </div>
          </div>
          
          <p class="exam-settings-note">
            Face verification and stylometry are used only when your instructor has enabled them in the exam or assignment settings.
          </p>
          
          <!-- Face Registration Section -->
          <div class="form-section face-section">
            <h3>Face Registration</h3>
            
            <!-- Already Registered -->
            <div v-if="user?.face_baseline_uploaded || faceRegistered" class="face-status registered">
              <svg width="24" height="24" viewBox="0 0 24 24" fill="currentColor">
                <path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm-2 15l-5-5 1.41-1.41L10 14.17l7.59-7.59L19 8l-9 9z"/>
              </svg>
              <div class="status-info">
                <strong>Face Registered</strong>
                <p>Your face baseline is set up. Face verification will use this to confirm your identity during assignments.</p>
              </div>
            </div>
            
            <!-- Not Registered -->
            <div v-else class="face-enrollment">
              <p class="section-description">
                Some assignments require face verification. Register your face now so you can start those assignments without delay.
              </p>
              
              <!-- Webcam area -->
              <div class="face-webcam-area">
                <div class="webcam-container" v-if="showFaceWebcam">
                  <video ref="faceVideoElement" autoplay playsinline class="face-webcam-feed"></video>
                  <div class="face-webcam-overlay" v-if="faceCapturing">
                    <div class="face-scanning-anim"></div>
                    <span>Registering...</span>
                  </div>
                  <div class="face-webcam-overlay success" v-if="faceRegistered">
                    <svg width="48" height="48" viewBox="0 0 24 24" fill="currentColor">
                      <path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm-2 15l-5-5 1.41-1.41L10 14.17l7.59-7.59L19 8l-9 9z"/>
                    </svg>
                    <span>Registered!</span>
                  </div>
                  <div class="face-webcam-overlay error" v-if="faceError && !faceCapturing">
                    <svg width="48" height="48" viewBox="0 0 24 24" fill="currentColor">
                      <path d="M12 2C6.47 2 2 6.47 2 12s4.47 10 10 10 10-4.47 10-10S17.53 2 12 2zm5 13.59L15.59 17 12 13.41 8.41 17 7 15.59 10.59 12 7 8.41 8.41 7 12 10.59 15.59 7 17 8.41 13.41 12 17 15.59z"/>
                    </svg>
                    <span>{{ faceError }}</span>
                  </div>
                </div>
                
                <!-- Placeholder before webcam starts -->
                <div class="face-placeholder" v-if="!showFaceWebcam">
                  <svg width="64" height="64" viewBox="0 0 24 24" fill="#9aa0a6">
                    <path d="M9 11.75c-.69 0-1.25.56-1.25 1.25s.56 1.25 1.25 1.25 1.25-.56 1.25-1.25-.56-1.25-1.25-1.25zm6 0c-.69 0-1.25.56-1.25 1.25s.56 1.25 1.25 1.25 1.25-.56 1.25-1.25-.56-1.25-1.25-1.25zM12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm0 18c-4.41 0-8-3.59-8-8 0-.29.02-.58.05-.86 2.36-1.05 4.23-2.98 5.21-5.37C11.07 8.33 14.05 10 17.42 10c.78 0 1.53-.09 2.25-.26.21.71.33 1.47.33 2.26 0 4.41-3.59 8-8 8z"/>
                  </svg>
                  <p>Click the button below to start camera and register your face</p>
                </div>
              </div>
              
              <!-- Instructions when webcam is active -->
              <div class="face-instructions" v-if="showFaceWebcam && !faceCapturing && !faceRegistered && !faceError">
                <ul>
                  <li>Ensure good lighting on your face</li>
                  <li>Face the camera directly</li>
                  <li>Remove any face coverings</li>
                </ul>
              </div>
              
              <!-- Action Buttons -->
              <div class="face-actions">
                <button 
                  v-if="!showFaceWebcam"
                  type="button"
                  class="face-start-btn" 
                  @click="startFaceWebcam"
                >
                  <svg width="20" height="20" viewBox="0 0 24 24" fill="currentColor">
                    <path d="M17 10.5V7c0-.55-.45-1-1-1H4c-.55 0-1 .45-1 1v10c0 .55.45 1 1 1h12c.55 0 1-.45 1-1v-3.5l4 4v-11l-4 4z"/>
                  </svg>
                  Start Camera
                </button>
                
                <button 
                  v-if="showFaceWebcam && faceWebcamReady && !faceRegistered"
                  type="button"
                  class="face-capture-btn" 
                  @click="captureFaceBaseline"
                  :disabled="faceCapturing"
                >
                  <span v-if="faceCapturing" class="spinner"></span>
                  <span v-else>{{ faceError ? 'Try Again' : 'Register My Face' }}</span>
                </button>
                
                <button
                  v-if="showFaceWebcam && !faceWebcamReady && !faceCapturing"
                  type="button"
                  class="face-retry-btn"
                  @click="retryFaceWebcam"
                >
                  <svg width="18" height="18" viewBox="0 0 24 24" fill="currentColor">
                    <path d="M17.65 6.35C16.2 4.9 14.21 4 12 4c-4.42 0-7.99 3.58-7.99 8s3.57 8 7.99 8c3.73 0 6.84-2.55 7.73-6h-2.08c-.82 2.33-3.04 4-5.65 4-3.31 0-6-2.69-6-6s2.69-6 6-6c1.66 0 3.14.69 4.22 1.78L13 11h7V4l-2.35 2.35z"/>
                  </svg>
                  Retry Camera Access
                </button>
                
                <button 
                  v-if="showFaceWebcam && !faceRegistered"
                  type="button"
                  class="face-cancel-btn" 
                  @click="stopFaceWebcam"
                >
                  Cancel
                </button>
              </div>
            </div>
          </div>
          
          
          <div v-if="successMessage" class="success-msg">
            <svg width="20" height="20" viewBox="0 0 24 24" fill="currentColor">
              <path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm-2 15l-5-5 1.41-1.41L10 14.17l7.59-7.59L19 8l-9 9z"/>
            </svg>
            {{ successMessage }}
          </div>
          
          <div v-if="errorMessage" class="error-msg">
            {{ errorMessage }}
          </div>
          
          <div class="form-actions">
            <button type="button" class="logout-btn" @click="handleLogout">
              Sign out
            </button>
            <button type="submit" class="save-btn" :disabled="loading">
              <span v-if="loading" class="spinner"></span>
              <span v-else>Save</span>
            </button>
          </div>
        </form>
      </div>
    </main>
  </div>
</template>

<script setup>
import { ref, onMounted, onBeforeUnmount } from 'vue'
import { useRouter } from 'vue-router'
import { useAuth } from '@/composables/auth'
import axios from 'axios'
import { getApiUrl } from '@/utils/api-url'

const router = useRouter()
const { user, loading, updateProfile, uploadProfileImage, logout, initAuth } = useAuth()

const name = ref('')
const university = ref('')
const errorMessage = ref('')
const successMessage = ref('')
const fileInput = ref(null)

// Face registration state
const showFaceWebcam = ref(false)
const faceWebcamReady = ref(false)
const faceCapturing = ref(false)
const faceRegistered = ref(false)
const faceError = ref('')
const faceVideoElement = ref(null)
let faceMediaStream = null



onMounted(async () => {
  console.log('🔄 Profile page loading...')
  const isAuth = await initAuth()
  if (!isAuth) {
    console.log('❌ Not authenticated, redirecting to login')
    router.push('/login')
    return
  }
  
  console.log('✅ User loaded:', {
    name: user.value?.name,
    email: user.value?.email,
    stylometry_enrolled: user.value?.stylometry_enrolled,
    stylometry_samples: user.value?.stylometry_baseline_samples,
    has_profile_image: !!user.value?.profile_image
  })
  
  name.value = user.value?.name || ''
  university.value = user.value?.university || ''
  
})

function goToDashboard() {
  router.push('/dashboard')
}

function triggerImageUpload() {
  fileInput.value?.click()
}

function handleImageError(e) {
  console.error('❌ Profile image failed to load:', e)
  console.error('Image src:', user.value?.profile_image?.substring(0, 100))
}

async function handleImageUpload(event) {
  const file = event.target.files[0]
  if (!file) return
  
  errorMessage.value = ''
  successMessage.value = ''
  
  if (!file.type.startsWith('image/')) {
    errorMessage.value = 'Please select an image file (JPG, PNG, GIF)'
    return
  }
  
  if (file.size > 5 * 1024 * 1024) {
    errorMessage.value = 'Image must be less than 5MB'
    return
  }
  
  console.log('📸 Uploading profile image:', file.name, file.size, 'bytes')
  
  const result = await uploadProfileImage(file)
  
  console.log('Upload result:', result)
  
  if (result.success) {
    successMessage.value = '✅ Profile photo updated successfully!'
    
    // Force a small delay to ensure state updates
    setTimeout(() => {
      console.log('Updated user image:', user.value?.profile_image?.substring(0, 50))
    }, 100)
    
    setTimeout(() => successMessage.value = '', 3000)
  } else {
    errorMessage.value = result.error || 'Upload failed. Please try again.'
    
    // If not authenticated, redirect to login
    if (result.error && result.error.includes('authenticated')) {
      setTimeout(() => router.push('/login'), 2000)
    }
  }
  
  // Clear file input
  event.target.value = ''
}

async function handleUpdate() {
  errorMessage.value = ''
  successMessage.value = ''
  
  if (!name.value || !university.value) {
    errorMessage.value = 'Please fill in all fields'
    return
  }
  
  const result = await updateProfile(name.value, university.value)
  
  if (result.success) {
    successMessage.value = 'Profile updated successfully'
    setTimeout(() => successMessage.value = '', 3000)
  } else {
    errorMessage.value = result.error || 'Update failed'
    
    // If not authenticated, redirect to login
    if (result.error && result.error.includes('authenticated')) {
      setTimeout(() => router.push('/login'), 2000)
    }
  }
}

// Face Registration functions
async function startFaceWebcam() {
  showFaceWebcam.value = true
  faceError.value = ''
  faceRegistered.value = false
  
  // Wait for the video element to render
  await nextTick()
  
  try {
    faceMediaStream = await navigator.mediaDevices.getUserMedia({
      video: { facingMode: 'user', width: 640, height: 480 }
    })
    
    if (faceVideoElement.value) {
      faceVideoElement.value.srcObject = faceMediaStream
      faceWebcamReady.value = true
    }
  } catch (e) {
    console.error('Webcam access failed:', e)
    faceError.value = 'Could not access webcam. Please check permissions.'
    faceWebcamReady.value = false
  }
}

async function retryFaceWebcam() {
  stopFaceWebcamStream()
  faceError.value = ''
  
  await nextTick()
  
  try {
    faceMediaStream = await navigator.mediaDevices.getUserMedia({
      video: { facingMode: 'user', width: 640, height: 480 }
    })
    
    if (faceVideoElement.value) {
      faceVideoElement.value.srcObject = faceMediaStream
      faceWebcamReady.value = true
    }
  } catch (e) {
    console.error('Webcam retry failed:', e)
    faceError.value = 'Could not access webcam. Please check permissions.'
    faceWebcamReady.value = false
  }
}

function stopFaceWebcamStream() {
  if (faceMediaStream) {
    faceMediaStream.getTracks().forEach(track => track.stop())
    faceMediaStream = null
  }
  faceWebcamReady.value = false
}

function stopFaceWebcam() {
  stopFaceWebcamStream()
  showFaceWebcam.value = false
  faceError.value = ''
}

function captureFaceFrame() {
  if (!faceVideoElement.value) return null
  
  const canvas = document.createElement('canvas')
  canvas.width = faceVideoElement.value.videoWidth
  canvas.height = faceVideoElement.value.videoHeight
  
  const ctx = canvas.getContext('2d')
  ctx.drawImage(faceVideoElement.value, 0, 0)
  
  return canvas.toDataURL('image/jpeg', 0.9)
}

async function captureFaceBaseline() {
  faceCapturing.value = true
  faceError.value = ''
  
  try {
    const token = localStorage.getItem('auth_token')
    const imageBase64 = captureFaceFrame()
    
    if (!imageBase64) {
      throw new Error('Failed to capture image from webcam')
    }
    
    const AUTH_API = getApiUrl()
    
    const response = await axios.post(
      `${AUTH_API}/api/auth/face/upload-baseline-base64`,
      { image_base64: imageBase64 },
      { headers: { Authorization: `Bearer ${token}` } }
    )
    
    if (response.data.success) {
      faceRegistered.value = true
      
      // Update user state
      if (user.value) {
        user.value.face_biometric_enabled = true
        user.value.face_baseline_uploaded = true
      }
      
      successMessage.value = 'Face registered successfully!'
      setTimeout(() => successMessage.value = '', 4000)
      
      // Stop webcam after brief success display
      setTimeout(() => {
        stopFaceWebcamStream()
      }, 1500)
    } else {
      faceError.value = response.data.message || 'Failed to register face'
    }
  } catch (e) {
    console.error('Face registration error:', e)
    const detail = e.response?.data?.detail
    faceError.value = (typeof detail === 'string' ? detail : null) || 'Could not register face. Ensure good lighting and try again.'
  } finally {
    faceCapturing.value = false
  }
}

// Cleanup webcam on unmount
onBeforeUnmount(() => {
  stopFaceWebcamStream()
})

async function handleLogout() {
  await logout()
  router.push('/login')
}
</script>

<style scoped>
.profile-page {
  min-height: 100vh;
  background: #f8f9fa;
  font-family: 'Google Sans', 'Roboto', -apple-system, BlinkMacSystemFont, sans-serif;
  display: flex;
  flex-direction: column;
  overflow-y: auto;
}

/* Header */
.profile-header {
  display: flex;
  align-items: center;
  height: 64px;
  min-height: 64px;
  padding: 0 16px;
  background: white;
  border-bottom: 1px solid #e0e0e0;
  flex-shrink: 0;
}

.header-left {
  display: flex;
  align-items: center;
  gap: 16px;
}

.back-btn {
  width: 48px;
  height: 48px;
  border: none;
  background: transparent;
  border-radius: 50%;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  color: #5f6368;
  transition: background 0.2s;
}

.back-btn:hover {
  background: rgba(0, 0, 0, 0.04);
}

.header-title {
  font-size: 18px;
  font-weight: 400;
  color: #202124;
}

/* Main */
.profile-main {
  flex: 1;
  overflow-y: auto;
  padding: 32px 24px 100px 24px;
}

.profile-main > * {
  max-width: 840px;
  margin-left: auto;
  margin-right: auto;
}

/* Warning Banner */
.warning-banner {
  display: flex;
  align-items: flex-start;
  gap: 12px;
  background: #fff3cd;
  border: 1px solid #ffc107;
  border-radius: 8px;
  padding: 16px 20px;
  margin-bottom: 24px;
  color: #856404;
}

.warning-banner svg {
  flex-shrink: 0;
  margin-top: 2px;
}

.profile-card {
  background: white;
  border-radius: 8px;
  border: 1px solid #dadce0;
  overflow: visible;
  margin-bottom: 40px;
}

/* Image Section */
.profile-image-section {
  display: flex;
  flex-direction: column;
  align-items: center;
  padding: 32px;
  border-bottom: 1px solid #e0e0e0;
  background: #f8f9fa;
}

.image-wrapper {
  position: relative;
  width: 128px;
  height: 128px;
  border-radius: 50%;
  cursor: pointer;
  overflow: hidden;
}

.profile-image {
  width: 100%;
  height: 100%;
  object-fit: cover;
}

.profile-placeholder {
  width: 100%;
  height: 100%;
  background: #e8eaed;
  display: flex;
  align-items: center;
  justify-content: center;
}

.image-overlay {
  position: absolute;
  inset: 0;
  background: rgba(0, 0, 0, 0.5);
  display: flex;
  align-items: center;
  justify-content: center;
  opacity: 0;
  transition: opacity 0.2s;
}

.image-wrapper:hover .image-overlay {
  opacity: 1;
}

.image-hint {
  margin: 16px 0 0 0;
  font-size: 14px;
  color: #5f6368;
}

/* Form */
.profile-form {
  padding: 32px;
  padding-bottom: 48px;
}

.form-section h3 {
  font-size: 14px;
  font-weight: 500;
  color: #202124;
  margin: 0 0 24px 0;
  text-transform: uppercase;
  letter-spacing: 0.5px;
}

.section-description {
  font-size: 14px;
  color: #5f6368;
  margin: -16px 0 20px 0;
  line-height: 1.5;
}

.exam-settings-note {
  font-size: 13px;
  color: #5f6368;
  line-height: 1.5;
  margin: 8px 0 16px 0;
  padding: 12px 16px;
  background: #f0f7ff;
  border-left: 4px solid #1a73e8;
  border-radius: 4px;
}


.form-field {
  margin-bottom: 24px;
}

.form-field label {
  display: block;
  font-size: 14px;
  font-weight: 500;
  color: #5f6368;
  margin-bottom: 8px;
}

.form-field input {
  width: 100%;
  padding: 12px 16px;
  border: 1px solid #dadce0;
  border-radius: 4px;
  font-size: 16px;
  color: #202124;
  transition: border-color 0.2s, box-shadow 0.2s;
  box-sizing: border-box;
}

.form-field input:focus {
  outline: none;
  border-color: #1a73e8;
  box-shadow: 0 0 0 2px rgba(26, 115, 232, 0.2);
}

.form-field input.disabled {
  background: #f8f9fa;
  color: #5f6368;
  cursor: not-allowed;
}

.form-field textarea {
  width: 100%;
  padding: 12px 16px;
  border: 1px solid #dadce0;
  border-radius: 4px;
  font-size: 15px;
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
  color: #202124;
  line-height: 1.6;
  resize: vertical;
  min-height: 200px;
  transition: border-color 0.2s, box-shadow 0.2s;
  box-sizing: border-box;
}

.form-field textarea:focus {
  outline: none;
  border-color: #1a73e8;
  box-shadow: 0 0 0 2px rgba(26, 115, 232, 0.2);
}

.form-field textarea:disabled {
  background: #f8f9fa;
  color: #5f6368;
  cursor: not-allowed;
}

.field-hint {
  display: block;
  margin-top: 4px;
  font-size: 12px;
  color: #5f6368;
}

.success-msg {
  display: flex;
  align-items: center;
  gap: 8px;
  background: #e6f4ea;
  color: #137333;
  padding: 12px 16px;
  border-radius: 4px;
  font-size: 14px;
  margin-bottom: 24px;
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
  padding-top: 16px;
  border-top: 1px solid #e0e0e0;
  margin-top: 8px;
}

.logout-btn {
  padding: 10px 24px;
  background: transparent;
  color: #5f6368;
  border: 1px solid #dadce0;
  border-radius: 4px;
  font-size: 14px;
  font-weight: 500;
  cursor: pointer;
  transition: background 0.2s, border-color 0.2s;
}

.logout-btn:hover {
  background: #f8f9fa;
  border-color: #5f6368;
}

.save-btn {
  padding: 10px 24px;
  background: #1a73e8;
  color: white;
  border: none;
  border-radius: 4px;
  font-size: 14px;
  font-weight: 500;
  cursor: pointer;
  min-width: 80px;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: background 0.2s, box-shadow 0.2s;
}

.save-btn:hover:not(:disabled) {
  background: #1557b0;
  box-shadow: 0 1px 2px rgba(0, 0, 0, 0.3);
}

.save-btn:disabled {
  opacity: 0.7;
  cursor: not-allowed;
}


.profile-image {
  width: 100%;
  height: 100%;
  object-fit: cover;
  display: block;
}

.profile-image[src=""],
.profile-image:not([src]) {
  display: none;
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

/* Face Registration Section */
.face-section {
  padding-top: 24px;
  margin-top: 24px;
  border-top: 1px solid #e0e0e0;
}

.face-status.registered {
  display: flex;
  align-items: flex-start;
  gap: 12px;
  padding: 16px;
  border-radius: 8px;
  background: #e6f4ea;
  color: #137333;
  margin-bottom: 20px;
}

.face-status.registered svg {
  flex-shrink: 0;
  margin-top: 2px;
}

.face-enrollment .section-description {
  font-size: 14px;
  color: #5f6368;
  margin: 0 0 20px 0;
  line-height: 1.5;
}

.face-webcam-area {
  margin-bottom: 16px;
}

.webcam-container {
  position: relative;
  width: 100%;
  max-width: 400px;
  margin: 0 auto;
  border-radius: 12px;
  overflow: hidden;
  background: #000;
  aspect-ratio: 4/3;
}

.face-webcam-feed {
  width: 100%;
  height: 100%;
  object-fit: cover;
  display: block;
  transform: scaleX(-1);
}

.face-webcam-overlay {
  position: absolute;
  inset: 0;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 12px;
  background: rgba(0, 0, 0, 0.6);
  color: white;
  font-weight: 600;
  font-size: 16px;
}

.face-webcam-overlay.success {
  background: rgba(52, 168, 83, 0.85);
}

.face-webcam-overlay.error {
  background: rgba(197, 34, 31, 0.85);
}

.face-scanning-anim {
  width: 64px;
  height: 64px;
  border: 4px solid rgba(255, 255, 255, 0.3);
  border-top-color: white;
  border-radius: 50%;
  animation: spin 0.8s linear infinite;
}

.face-placeholder {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 12px;
  padding: 40px 20px;
  background: #f8f9fa;
  border: 2px dashed #dadce0;
  border-radius: 12px;
  max-width: 400px;
  margin: 0 auto;
}

.face-placeholder p {
  font-size: 14px;
  color: #5f6368;
  margin: 0;
  text-align: center;
}

.face-instructions {
  max-width: 400px;
  margin: 0 auto;
}

.face-instructions ul {
  list-style: none;
  padding: 0;
  margin: 0;
}

.face-instructions li {
  padding: 6px 0;
  font-size: 14px;
  color: #5f6368;
  display: flex;
  align-items: center;
  gap: 8px;
}

.face-instructions li::before {
  content: '✓';
  color: #34a853;
  font-weight: bold;
}

.face-actions {
  display: flex;
  gap: 12px;
  justify-content: center;
  flex-wrap: wrap;
  margin-top: 16px;
  max-width: 400px;
  margin-left: auto;
  margin-right: auto;
}

.face-start-btn {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 12px 24px;
  background: #1a73e8;
  color: white;
  border: none;
  border-radius: 8px;
  font-size: 15px;
  font-weight: 500;
  cursor: pointer;
  transition: all 0.2s;
}

.face-start-btn:hover {
  background: #1557b0;
  box-shadow: 0 2px 4px rgba(0, 0, 0, 0.2);
  transform: translateY(-1px);
}

.face-capture-btn {
  flex: 1;
  padding: 12px 24px;
  background: #34a853;
  color: white;
  border: none;
  border-radius: 8px;
  font-size: 15px;
  font-weight: 500;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  transition: all 0.2s;
  min-width: 160px;
}

.face-capture-btn:hover:not(:disabled) {
  background: #2d8e47;
  box-shadow: 0 2px 4px rgba(0, 0, 0, 0.2);
}

.face-capture-btn:disabled {
  opacity: 0.7;
  cursor: not-allowed;
}

.face-retry-btn {
  flex: 1;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  padding: 12px 24px;
  background: #f9ab00;
  color: white;
  border: none;
  border-radius: 8px;
  font-size: 15px;
  font-weight: 500;
  cursor: pointer;
  transition: all 0.2s;
}

.face-retry-btn:hover {
  background: #f29900;
}

.face-cancel-btn {
  padding: 12px 24px;
  background: transparent;
  color: #5f6368;
  border: 1px solid #dadce0;
  border-radius: 8px;
  font-size: 15px;
  font-weight: 500;
  cursor: pointer;
  transition: all 0.2s;
}

.face-cancel-btn:hover {
  background: #f8f9fa;
  border-color: #5f6368;
}

@media (max-width: 480px) {
  .profile-main {
    padding: 16px;
  }
  
  .profile-form {
    padding: 24px 16px;
  }
  
  .form-actions {
    flex-direction: column-reverse;
    gap: 16px;
  }
  
  .logout-btn,
  .save-btn {
    width: 100%;
  }
}
</style>
