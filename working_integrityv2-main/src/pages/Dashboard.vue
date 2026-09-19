<template>
  <div class="gc-container">
    <!-- Top Navigation Bar (Google Classroom style) -->
    <header class="gc-header">
      <div class="gc-header-left">
        <button class="gc-menu-btn" @click="showSidebar = !showSidebar">
          <svg width="24" height="24" viewBox="0 0 24 24" fill="currentColor">
            <path d="M3 18h18v-2H3v2zm0-5h18v-2H3v2zm0-7v2h18V6H3z"/>
          </svg>
        </button>
        <div class="gc-logo">
          <svg width="40" height="40" viewBox="0 0 48 48" class="gc-logo-icon">
            <path fill="#0F9D58" d="M42,37c0,2.762-2.238,5-5,5H11c-2.761,0-5-2.238-5-5V11c0-2.762,2.239-5,5-5h26c2.762,0,5,2.238,5,5V37z"/>
            <path fill="#FFFFFF" d="M24 16A5 5 0 1 0 24 26A5 5 0 1 0 24 16Z"/>
            <path fill="#FFFFFF" d="M33,30c0-3.5-3.5-5-9-5s-9,1.5-9,5v2h18V30z"/>
          </svg>
          <span class="gc-logo-text">Editorrah</span>
        </div>
      </div>
      
      <div class="gc-header-right">
        <button class="gc-icon-btn" title="Create">
          <svg width="24" height="24" viewBox="0 0 24 24" fill="currentColor">
            <path d="M19 13h-6v6h-2v-6H5v-2h6V5h2v6h6v2z"/>
          </svg>
        </button>
        <button class="gc-icon-btn" title="Apps">
          <svg width="24" height="24" viewBox="0 0 24 24" fill="currentColor">
            <path d="M4 8h4V4H4v4zm6 12h4v-4h-4v4zm-6 0h4v-4H4v4zm0-6h4v-4H4v4zm6 0h4v-4h-4v4zm6-10v4h4V4h-4zm-6 4h4V4h-4v4zm6 6h4v-4h-4v4zm0 6h4v-4h-4v4z"/>
          </svg>
        </button>
        
        <!-- Profile -->
        <div class="gc-profile" @click="showProfileMenu = !showProfileMenu">
          <img v-if="user?.profile_image" :src="user.profile_image" :alt="user?.name" class="gc-avatar" />
          <div v-else class="gc-avatar gc-avatar-placeholder">
            {{ user?.name?.[0]?.toUpperCase() || 'U' }}
          </div>
          
          <!-- Dropdown -->
          <div v-if="showProfileMenu" class="gc-dropdown" @click.stop>
            <div class="gc-dropdown-header">
              <img v-if="user?.profile_image" :src="user.profile_image" class="gc-dropdown-avatar" />
              <div v-else class="gc-dropdown-avatar gc-avatar-placeholder">{{ user?.name?.[0]?.toUpperCase() || 'U' }}</div>
              <div class="gc-dropdown-info">
                <div class="gc-dropdown-name">{{ user?.name }}</div>
                <div class="gc-dropdown-email">{{ user?.email }}</div>
              </div>
            </div>
            <div class="gc-dropdown-divider"></div>
            <router-link to="/profile" class="gc-dropdown-item">
              <svg width="20" height="20" viewBox="0 0 24 24" fill="currentColor"><path d="M12 12c2.21 0 4-1.79 4-4s-1.79-4-4-4-4 1.79-4 4 1.79 4 4 4zm0 2c-2.67 0-8 1.34-8 4v2h16v-2c0-2.66-5.33-4-8-4z"/></svg>
              Manage your Account
            </router-link>
            <div class="gc-dropdown-divider"></div>
            <button @click="handleLogout" class="gc-dropdown-item gc-dropdown-signout">
              <svg width="20" height="20" viewBox="0 0 24 24" fill="currentColor"><path d="M17 7l-1.41 1.41L18.17 11H8v2h10.17l-2.58 2.58L17 17l5-5zM4 5h8V3H4c-1.1 0-2 .9-2 2v14c0 1.1.9 2 2 2h8v-2H4V5z"/></svg>
              Sign out
            </button>
          </div>
        </div>
      </div>
    </header>
    
    <!-- Main Content Area -->
    <main class="gc-main">
      <!-- Tab Navigation -->
      <div class="gc-tabs">
        <button 
          :class="['gc-tab', activeTab === 'classes' && 'active']"
          @click="activeTab = 'classes'"
        >
          Assignments
        </button>
        <button 
          :class="['gc-tab', activeTab === 'calendar' && 'active']"
          @click="activeTab = 'calendar'"
        >
          To-do
        </button>
      </div>
      
      <!-- Classes Grid (Google Classroom style) -->
      <div class="gc-content">
        <!-- Create/Join buttons -->
        <div class="gc-actions-bar">
          <button class="gc-create-btn" @click="showCreateModal = true">
            <svg width="20" height="20" viewBox="0 0 24 24" fill="currentColor">
              <path d="M19 13h-6v6h-2v-6H5v-2h6V5h2v6h6v2z"/>
            </svg>
            Create
          </button>
        </div>
        
        <!-- Assignment Cards Grid -->
        <div class="gc-cards-grid">
          <div 
            v-for="assignment in assignments" 
            :key="assignment.id"
            class="gc-card"
          >
            <!-- Card Header with gradient -->
            <div class="gc-card-header" :style="{ background: assignment.color }">
              <div class="gc-card-header-content">
                <h3 class="gc-card-title">{{ assignment.title }}</h3>
                <p class="gc-card-section">{{ assignment.course }}</p>
              </div>
              <div class="gc-card-avatar">
                <img v-if="user?.profile_image" :src="user.profile_image" />
                <span v-else>{{ user?.name?.[0]?.toUpperCase() || 'U' }}</span>
              </div>
              <button class="gc-card-menu">
                <svg width="24" height="24" viewBox="0 0 24 24" fill="white">
                  <path d="M12 8c1.1 0 2-.9 2-2s-.9-2-2-2-2 .9-2 2 .9 2 2 2zm0 2c-1.1 0-2 .9-2 2s.9 2 2 2 2-.9 2-2-.9-2-2-2zm0 6c-1.1 0-2 .9-2 2s.9 2 2 2 2-.9 2-2-.9-2-2-2z"/>
                </svg>
              </button>
            </div>
            
            <!-- Card Body -->
            <div class="gc-card-body">
              <p class="gc-card-description">{{ assignment.description }}</p>
            </div>
            
            <!-- Card Footer -->
            <div class="gc-card-footer">
              <div class="gc-card-meta">
                <span class="gc-card-due" v-if="assignment.dueDate">
                  Due {{ formatDate(assignment.dueDate) }}
                </span>
                <span 
                  v-if="assignment.trustScore !== null" 
                  :class="['gc-trust-badge', getTrustClass(assignment.trustScore)]"
                >
                  {{ assignment.trustScore }}% Trust
                </span>
              </div>
              <div class="gc-card-actions">
                <button class="gc-open-btn" @click="openEditor(assignment)">
                  Open
                </button>
              </div>
            </div>
          </div>
          
          <!-- Empty State -->
          <div v-if="assignments.length === 0" class="gc-empty">
            <svg width="120" height="120" viewBox="0 0 24 24" fill="#dadce0">
              <path d="M19 3H5c-1.1 0-2 .9-2 2v14c0 1.1.9 2 2 2h14c1.1 0 2-.9 2-2V5c0-1.1-.9-2-2-2zm-5 14H7v-2h7v2zm3-4H7v-2h10v2zm0-4H7V7h10v2z"/>
            </svg>
            <h3>No assignments yet</h3>
            <p>Click the + button to create your first assignment</p>
          </div>
        </div>
      </div>
    </main>
    
    <!-- Create Assignment Modal -->
    <div v-if="showCreateModal" class="gc-modal-overlay" @click.self="showCreateModal = false">
      <div class="gc-modal">
        <div class="gc-modal-header">
          <h2>Create assignment</h2>
          <button class="gc-modal-close" @click="showCreateModal = false">
            <svg width="24" height="24" viewBox="0 0 24 24" fill="currentColor">
              <path d="M19 6.41L17.59 5 12 10.59 6.41 5 5 6.41 10.59 12 5 17.59 6.41 19 12 13.41 17.59 19 19 17.59 13.41 12z"/>
            </svg>
          </button>
        </div>
        
        <form @submit.prevent="createAssignment" class="gc-modal-body">
          <div class="gc-form-group">
            <label>Assignment name (required)</label>
            <input 
              v-model="newAssignment.title" 
              type="text" 
              placeholder="Assignment name"
              required 
              autofocus
            />
          </div>
          
          <div class="gc-form-group">
            <label>Subject</label>
            <input 
              v-model="newAssignment.course" 
              type="text" 
              placeholder="Subject"
            />
          </div>
          
          <div class="gc-form-group">
            <label>Description</label>
            <textarea 
              v-model="newAssignment.description" 
              placeholder="Description (optional)"
              rows="2"
            ></textarea>
          </div>
          
          <div class="gc-form-row">
            <div class="gc-form-group">
              <label>Due date</label>
              <input 
                v-model="newAssignment.dueDate" 
                type="date"
              />
            </div>
          </div>
          
          <div class="gc-form-group">
            <label>Theme</label>
            <div class="gc-theme-picker">
              <button 
                v-for="(color, index) in colors" 
                :key="index"
                type="button"
                :class="['gc-theme-option', newAssignment.color === color && 'selected']"
                :style="{ background: color }"
                @click="newAssignment.color = color"
              ></button>
            </div>
          </div>
          
          <div class="gc-modal-footer">
            <button type="button" class="gc-btn-text" @click="showCreateModal = false">Cancel</button>
            <button type="submit" class="gc-btn-primary">Create</button>
          </div>
        </form>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted, onUnmounted } from 'vue'
import { useRouter } from 'vue-router'
import { useAuth } from '@/composables/auth'

const router = useRouter()
const { user, logout, initAuth } = useAuth()

const showSidebar = ref(false)
const showProfileMenu = ref(false)
const showCreateModal = ref(false)
const activeTab = ref('classes')

// Google Classroom-like colors
const colors = [
  '#1967d2',  // Blue
  '#137333',  // Green
  '#c5221f',  // Red
  '#f9ab00',  // Yellow
  '#9334e6',  // Purple
  '#188038',  // Teal
  '#e37400',  // Orange
  '#1a73e8',  // Light blue
]

const newAssignment = ref({
  title: '',
  course: '',
  description: '',
  dueDate: '',
  color: colors[0]
})

// Sample assignments
const assignments = ref([
  {
    id: 1,
    title: 'Essay: Climate Change Impact',
    course: 'Environmental Science',
    description: 'Write a 2000-word essay on climate change effects on biodiversity',
    dueDate: '2026-01-20',
    status: 'pending',
    trustScore: null,
    color: colors[0]
  },
  {
    id: 2,
    title: 'Research Paper: AI Ethics',
    course: 'Computer Science 301',
    description: 'Analyze ethical implications of AI in healthcare',
    dueDate: '2026-01-25',
    status: 'pending',
    trustScore: 85,
    color: colors[1]
  },
  {
    id: 3,
    title: 'Literature Review',
    course: 'English Literature',
    description: 'Review three contemporary novels from the syllabus',
    dueDate: '2026-01-18',
    status: 'completed',
    trustScore: 92,
    color: colors[4]
  }
])

function formatDate(dateStr) {
  const date = new Date(dateStr)
  const today = new Date()
  const tomorrow = new Date(today)
  tomorrow.setDate(tomorrow.getDate() + 1)
  
  if (date.toDateString() === today.toDateString()) {
    return 'Today'
  } else if (date.toDateString() === tomorrow.toDateString()) {
    return 'Tomorrow'
  }
  return date.toLocaleDateString('en-US', { month: 'short', day: 'numeric' })
}

function getTrustClass(score) {
  if (score >= 80) return 'high'
  if (score >= 50) return 'medium'
  return 'low'
}

function openEditor(assignment) {
  // Check if user is enrolled in stylometry
  if (!user.value?.stylometry_enrolled) {
    alert('⚠️ Please complete stylometry enrollment in your profile before accessing the editor.')
    router.push('/profile')
    return
  }
  
  localStorage.setItem('current_assignment', JSON.stringify(assignment))
  router.push(`/editor/${assignment.id}`)
}

function createAssignment() {
  const id = Date.now()
  const assignment = {
    id,
    ...newAssignment.value,
    status: 'pending',
    trustScore: null
  }
  assignments.value.unshift(assignment)
  showCreateModal.value = false
  
  newAssignment.value = {
    title: '',
    course: '',
    description: '',
    dueDate: '',
    color: colors[0]
  }
  
  openEditor(assignment)
}

async function handleLogout() {
  await logout()
  router.push('/login')
}

function handleClickOutside(e) {
  if (!e.target.closest('.gc-profile')) {
    showProfileMenu.value = false
  }
}

onMounted(async () => {
  const isAuth = await initAuth()
  if (!isAuth) {
    router.push('/login')
    return
  }
  document.addEventListener('click', handleClickOutside)
})

onUnmounted(() => {
  document.removeEventListener('click', handleClickOutside)
})
</script>

<style scoped>
/* Google Classroom inspired design system */
.gc-container {
  min-height: 100vh;
  background: #f1f3f4;
  font-family: 'Google Sans', 'Roboto', -apple-system, BlinkMacSystemFont, sans-serif;
}

/* Header */
.gc-header {
  position: sticky;
  top: 0;
  z-index: 100;
  display: flex;
  align-items: center;
  justify-content: space-between;
  height: 64px;
  padding: 0 16px;
  background: #fff;
  border-bottom: 1px solid #e0e0e0;
}

.gc-header-left {
  display: flex;
  align-items: center;
  gap: 8px;
}

.gc-menu-btn {
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

.gc-menu-btn:hover {
  background: rgba(0, 0, 0, 0.04);
}

.gc-logo {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 0 8px;
}

.gc-logo-text {
  font-size: 22px;
  font-weight: 400;
  color: #5f6368;
  letter-spacing: -0.5px;
}

.gc-header-right {
  display: flex;
  align-items: center;
  gap: 4px;
}

.gc-icon-btn {
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

.gc-icon-btn:hover {
  background: rgba(0, 0, 0, 0.04);
}

/* Profile */
.gc-profile {
  position: relative;
  margin-left: 8px;
  cursor: pointer;
}

.gc-avatar {
  width: 32px;
  height: 32px;
  border-radius: 50%;
  object-fit: cover;
}

.gc-avatar-placeholder {
  display: flex;
  align-items: center;
  justify-content: center;
  background: #1a73e8;
  color: white;
  font-size: 14px;
  font-weight: 500;
}

/* Dropdown */
.gc-dropdown {
  position: absolute;
  top: calc(100% + 8px);
  right: 0;
  width: 320px;
  background: white;
  border-radius: 8px;
  box-shadow: 0 1px 2px 0 rgba(60,64,67,0.3), 0 2px 6px 2px rgba(60,64,67,0.15);
  overflow: hidden;
  animation: gcFadeIn 0.15s ease;
}

@keyframes gcFadeIn {
  from { opacity: 0; transform: scale(0.95); }
  to { opacity: 1; transform: scale(1); }
}

.gc-dropdown-header {
  display: flex;
  align-items: center;
  gap: 16px;
  padding: 16px 20px;
  background: #f8f9fa;
}

.gc-dropdown-avatar {
  width: 48px;
  height: 48px;
  border-radius: 50%;
  object-fit: cover;
}

.gc-dropdown-info {
  min-width: 0;
}

.gc-dropdown-name {
  font-size: 16px;
  font-weight: 500;
  color: #202124;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.gc-dropdown-email {
  font-size: 14px;
  color: #5f6368;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.gc-dropdown-divider {
  height: 1px;
  background: #e0e0e0;
}

.gc-dropdown-item {
  display: flex;
  align-items: center;
  gap: 16px;
  width: 100%;
  padding: 12px 20px;
  border: none;
  background: transparent;
  font-size: 14px;
  color: #3c4043;
  cursor: pointer;
  text-decoration: none;
  transition: background 0.1s;
}

.gc-dropdown-item:hover {
  background: #f1f3f4;
}

.gc-dropdown-item svg {
  color: #5f6368;
}

.gc-dropdown-signout {
  color: #5f6368;
}

/* Main Content */
.gc-main {
  max-width: 1400px;
  margin: 0 auto;
  padding: 0 24px;
}

/* Tabs */
.gc-tabs {
  display: flex;
  gap: 0;
  border-bottom: 1px solid #e0e0e0;
  background: #fff;
  margin: 0 -24px;
  padding: 0 24px;
}

.gc-tab {
  padding: 16px 24px;
  border: none;
  background: transparent;
  font-size: 14px;
  font-weight: 500;
  color: #5f6368;
  cursor: pointer;
  position: relative;
  transition: color 0.2s;
}

.gc-tab:hover {
  color: #1967d2;
}

.gc-tab.active {
  color: #1967d2;
}

.gc-tab.active::after {
  content: '';
  position: absolute;
  bottom: 0;
  left: 0;
  right: 0;
  height: 3px;
  background: #1967d2;
  border-radius: 3px 3px 0 0;
}

/* Content */
.gc-content {
  padding: 24px 0;
}

.gc-actions-bar {
  display: flex;
  justify-content: flex-end;
  margin-bottom: 24px;
}

.gc-create-btn {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 10px 24px;
  border: none;
  background: #1a73e8;
  color: white;
  font-size: 14px;
  font-weight: 500;
  border-radius: 4px;
  cursor: pointer;
  transition: background 0.2s, box-shadow 0.2s;
}

.gc-create-btn:hover {
  background: #1557b0;
  box-shadow: 0 1px 2px rgba(0,0,0,0.3);
}

/* Cards Grid */
.gc-cards-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(300px, 1fr));
  gap: 24px;
}

/* Card */
.gc-card {
  background: white;
  border-radius: 8px;
  overflow: hidden;
  box-shadow: 0 1px 2px 0 rgba(60,64,67,0.3), 0 1px 3px 1px rgba(60,64,67,0.15);
  transition: box-shadow 0.2s;
}

.gc-card:hover {
  box-shadow: 0 1px 3px 0 rgba(60,64,67,0.3), 0 4px 8px 3px rgba(60,64,67,0.15);
}

.gc-card-header {
  position: relative;
  padding: 16px;
  min-height: 80px;
  color: white;
}

.gc-card-header-content {
  position: relative;
  z-index: 1;
}

.gc-card-title {
  font-size: 18px;
  font-weight: 400;
  margin: 0 0 4px 0;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  max-width: 200px;
}

.gc-card-section {
  font-size: 13px;
  opacity: 0.9;
  margin: 0;
}

.gc-card-avatar {
  position: absolute;
  right: 16px;
  bottom: -24px;
  width: 72px;
  height: 72px;
  border-radius: 50%;
  background: #5f6368;
  border: 3px solid white;
  display: flex;
  align-items: center;
  justify-content: center;
  overflow: hidden;
  z-index: 2;
}

.gc-card-avatar img {
  width: 100%;
  height: 100%;
  object-fit: cover;
}

.gc-card-avatar span {
  font-size: 28px;
  font-weight: 500;
  color: white;
}

.gc-card-menu {
  position: absolute;
  top: 8px;
  right: 8px;
  width: 40px;
  height: 40px;
  border: none;
  background: transparent;
  border-radius: 50%;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  opacity: 0;
  transition: opacity 0.2s, background 0.2s;
}

.gc-card:hover .gc-card-menu {
  opacity: 1;
}

.gc-card-menu:hover {
  background: rgba(255, 255, 255, 0.2);
}

.gc-card-body {
  padding: 32px 16px 16px;
  min-height: 48px;
  border-bottom: 1px solid #e0e0e0;
}

.gc-card-description {
  font-size: 13px;
  color: #5f6368;
  margin: 0;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}

.gc-card-footer {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 12px 16px;
}

.gc-card-meta {
  display: flex;
  align-items: center;
  gap: 12px;
}

.gc-card-due {
  font-size: 12px;
  color: #5f6368;
}

.gc-trust-badge {
  font-size: 11px;
  font-weight: 500;
  padding: 4px 8px;
  border-radius: 4px;
}

.gc-trust-badge.high {
  background: #e6f4ea;
  color: #137333;
}

.gc-trust-badge.medium {
  background: #fef7e0;
  color: #b06000;
}

.gc-trust-badge.low {
  background: #fce8e6;
  color: #c5221f;
}

.gc-card-actions {
  display: flex;
  gap: 8px;
}

.gc-open-btn {
  padding: 8px 16px;
  border: none;
  background: #1a73e8;
  color: white;
  font-size: 14px;
  font-weight: 500;
  border-radius: 4px;
  cursor: pointer;
  transition: background 0.2s;
}

.gc-open-btn:hover {
  background: #1557b0;
}

/* Empty State */
.gc-empty {
  grid-column: 1 / -1;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 80px 20px;
  text-align: center;
}

.gc-empty h3 {
  font-size: 16px;
  font-weight: 500;
  color: #3c4043;
  margin: 16px 0 8px;
}

.gc-empty p {
  font-size: 14px;
  color: #5f6368;
  margin: 0;
}

/* Modal */
.gc-modal-overlay {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.6);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 1000;
  padding: 20px;
}

.gc-modal {
  background: white;
  border-radius: 8px;
  width: 100%;
  max-width: 512px;
  max-height: 90vh;
  overflow-y: auto;
  animation: gcModalIn 0.2s ease;
}

@keyframes gcModalIn {
  from { opacity: 0; transform: scale(0.95); }
  to { opacity: 1; transform: scale(1); }
}

.gc-modal-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 16px 24px;
  border-bottom: 1px solid #e0e0e0;
}

.gc-modal-header h2 {
  font-size: 18px;
  font-weight: 500;
  color: #202124;
  margin: 0;
}

.gc-modal-close {
  width: 40px;
  height: 40px;
  border: none;
  background: transparent;
  border-radius: 50%;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  color: #5f6368;
  transition: background 0.1s;
}

.gc-modal-close:hover {
  background: #f1f3f4;
}

.gc-modal-body {
  padding: 24px;
}

.gc-form-group {
  margin-bottom: 24px;
}

.gc-form-group label {
  display: block;
  font-size: 12px;
  font-weight: 500;
  color: #5f6368;
  margin-bottom: 8px;
  text-transform: uppercase;
  letter-spacing: 0.5px;
}

.gc-form-group input,
.gc-form-group textarea {
  width: 100%;
  padding: 12px;
  border: 1px solid #dadce0;
  border-radius: 4px;
  font-size: 14px;
  color: #202124;
  transition: border-color 0.2s, box-shadow 0.2s;
  box-sizing: border-box;
}

.gc-form-group input:focus,
.gc-form-group textarea:focus {
  outline: none;
  border-color: #1a73e8;
  box-shadow: 0 0 0 2px rgba(26, 115, 232, 0.2);
}

.gc-form-row {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 16px;
}

.gc-theme-picker {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
}

.gc-theme-option {
  width: 32px;
  height: 32px;
  border-radius: 50%;
  border: 2px solid transparent;
  cursor: pointer;
  transition: transform 0.1s, border-color 0.1s;
}

.gc-theme-option:hover {
  transform: scale(1.1);
}

.gc-theme-option.selected {
  border-color: #202124;
}

.gc-modal-footer {
  display: flex;
  justify-content: flex-end;
  gap: 8px;
  padding-top: 16px;
  margin-top: 8px;
  border-top: 1px solid #e0e0e0;
}

.gc-btn-text {
  padding: 8px 24px;
  border: none;
  background: transparent;
  font-size: 14px;
  font-weight: 500;
  color: #1a73e8;
  cursor: pointer;
  border-radius: 4px;
  transition: background 0.1s;
}

.gc-btn-text:hover {
  background: rgba(26, 115, 232, 0.04);
}

.gc-btn-primary {
  padding: 8px 24px;
  border: none;
  background: #1a73e8;
  font-size: 14px;
  font-weight: 500;
  color: white;
  cursor: pointer;
  border-radius: 4px;
  transition: background 0.2s;
}

.gc-btn-primary:hover {
  background: #1557b0;
}

/* Responsive */
@media (max-width: 768px) {
  .gc-cards-grid {
    grid-template-columns: 1fr;
  }
  
  .gc-form-row {
    grid-template-columns: 1fr;
  }
}
</style>
