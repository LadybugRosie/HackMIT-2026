<template>
  <div class="teacher-dashboard">
    <!-- Header -->
    <header class="dashboard-header">
      <div class="header-left">
        <button class="menu-btn" @click="showSidebar = !showSidebar">
          <svg width="24" height="24" viewBox="0 0 24 24" fill="currentColor">
            <path d="M3 18h18v-2H3v2zm0-5h18v-2H3v2zm0-7v2h18V6H3z"/>
          </svg>
        </button>
        <div class="logo">
          <svg width="40" height="40" viewBox="0 0 48 48" class="logo-icon">
            <path fill="#1a73e8" d="M42,37c0,2.762-2.238,5-5,5H11c-2.761,0-5-2.238-5-5V11c0-2.762,2.239-5,5-5h26c2.762,0,5,2.238,5,5V37z"/>
            <path fill="#FFFFFF" d="M24 16A5 5 0 1 0 24 26A5 5 0 1 0 24 16Z"/>
            <path fill="#FFFFFF" d="M33,30c0-3.5-3.5-5-9-5s-9,1.5-9,5v2h18V30z"/>
          </svg>
          <span class="logo-text">Editorrah</span>
          <span class="role-badge">Teacher</span>
        </div>
      </div>
      
      <nav class="header-nav">
        <router-link to="/teacher/dashboard" class="nav-link active">Dashboard</router-link>
        <router-link to="/teacher/classes" class="nav-link">Classes</router-link>
      </nav>
      
      <div class="header-right">
        <div class="profile" @click="showProfileMenu = !showProfileMenu">
          <img v-if="user?.profile_image" :src="user.profile_image" :alt="user?.name" class="avatar" />
          <div v-else class="avatar avatar-placeholder">
            {{ user?.name?.[0]?.toUpperCase() || 'T' }}
          </div>
          
          <div v-if="showProfileMenu" class="dropdown" @click.stop>
            <div class="dropdown-header">
              <img v-if="user?.profile_image" :src="user.profile_image" class="dropdown-avatar" />
              <div v-else class="dropdown-avatar avatar-placeholder">{{ user?.name?.[0]?.toUpperCase() || 'T' }}</div>
              <div class="dropdown-info">
                <div class="dropdown-name">{{ user?.name }}</div>
                <div class="dropdown-email">{{ user?.email }}</div>
              </div>
            </div>
            <div class="dropdown-divider"></div>
            <router-link to="/profile" class="dropdown-item">
              <svg width="20" height="20" viewBox="0 0 24 24" fill="currentColor"><path d="M12 12c2.21 0 4-1.79 4-4s-1.79-4-4-4-4 1.79-4 4 1.79 4 4 4zm0 2c-2.67 0-8 1.34-8 4v2h16v-2c0-2.66-5.33-4-8-4z"/></svg>
              Profile Settings
            </router-link>
            <div class="dropdown-divider"></div>
            <button @click="handleLogout" class="dropdown-item dropdown-signout">
              <svg width="20" height="20" viewBox="0 0 24 24" fill="currentColor"><path d="M17 7l-1.41 1.41L18.17 11H8v2h10.17l-2.58 2.58L17 17l5-5zM4 5h8V3H4c-1.1 0-2 .9-2 2v14c0 1.1.9 2 2 2h8v-2H4V5z"/></svg>
              Sign out
            </button>
          </div>
        </div>
      </div>
    </header>

    <!-- Main Content -->
    <main class="dashboard-main">
      <!-- Loading gate: prevent flicker while auth + data load -->
      <div v-if="pageLoading" style="display:flex;align-items:center;justify-content:center;min-height:400px;color:#5f6368;font-size:16px;">
        Loading dashboard...
      </div>
      <div v-else class="dashboard-container">
        <!-- Welcome Section -->
        <section class="welcome-section">
          <h1>Welcome back, {{ user?.name?.split(' ')[0] || 'Teacher' }}</h1>
          <p>Here's what's happening in your classes</p>
        </section>

        <!-- Stats Cards -->
        <section class="stats-section">
          <div class="stat-card">
            <div class="stat-icon blue">
              <svg width="24" height="24" viewBox="0 0 24 24" fill="currentColor">
                <path d="M16 11c1.66 0 2.99-1.34 2.99-3S17.66 5 16 5c-1.66 0-3 1.34-3 3s1.34 3 3 3zm-8 0c1.66 0 2.99-1.34 2.99-3S9.66 5 8 5C6.34 5 5 6.34 5 8s1.34 3 3 3zm0 2c-2.33 0-7 1.17-7 3.5V19h14v-2.5c0-2.33-4.67-3.5-7-3.5zm8 0c-.29 0-.62.02-.97.05 1.16.84 1.97 1.97 1.97 3.45V19h6v-2.5c0-2.33-4.67-3.5-7-3.5z"/>
              </svg>
            </div>
            <div class="stat-content">
              <span class="stat-value">{{ totalStudents }}</span>
              <span class="stat-label">Total Students</span>
            </div>
          </div>
          
          <div class="stat-card">
            <div class="stat-icon orange">
              <svg width="24" height="24" viewBox="0 0 24 24" fill="currentColor">
                <path d="M19 3H5c-1.1 0-2 .9-2 2v14c0 1.1.9 2 2 2h14c1.1 0 2-.9 2-2V5c0-1.1-.9-2-2-2zm-5 14H7v-2h7v2zm3-4H7v-2h10v2zm0-4H7V7h10v2z"/>
              </svg>
            </div>
            <div class="stat-content">
              <span class="stat-value">{{ pendingSubmissions }}</span>
              <span class="stat-label">Pending Review</span>
            </div>
          </div>
          
          <div class="stat-card">
            <div class="stat-icon green">
              <svg width="24" height="24" viewBox="0 0 24 24" fill="currentColor">
                <path d="M9 16.17L4.83 12l-1.42 1.41L9 19 21 7l-1.41-1.41z"/>
              </svg>
            </div>
            <div class="stat-content">
              <span class="stat-value">{{ averageTrust }}%</span>
              <span class="stat-label">Avg Trust Score</span>
            </div>
          </div>
          
          <div class="stat-card">
            <div class="stat-icon purple">
              <svg width="24" height="24" viewBox="0 0 24 24" fill="currentColor">
                <path d="M12 2l-5.5 9h11z"/><circle cx="17.5" cy="17.5" r="4.5"/><path d="M3 13.5h8v8H3z"/>
              </svg>
            </div>
            <div class="stat-content">
              <span class="stat-value">{{ classes.length }}</span>
              <span class="stat-label">Active Classes</span>
            </div>
          </div>
        </section>

        <!-- Alerts Section -->
        <section class="alerts-section" v-if="flaggedSubmissions.length > 0">
          <h2 class="section-title">
            <svg width="20" height="20" viewBox="0 0 24 24" fill="currentColor">
              <path d="M1 21h22L12 2 1 21zm12-3h-2v-2h2v2zm0-4h-2v-4h2v4z"/>
            </svg>
            Needs Attention
          </h2>
          <div class="alert-cards">
            <div 
              v-for="alert in flaggedSubmissions" 
              :key="alert.id"
              class="alert-card"
              :class="alert.type"
              @click="handleAlertClick(alert)"
            >
              <div class="alert-icon">
                <svg v-if="alert.type === 'plagiarism'" width="20" height="20" viewBox="0 0 24 24" fill="currentColor">
                  <path d="M16 1H4c-1.1 0-2 .9-2 2v14h2V3h12V1zm-1 4l6 6v10c0 1.1-.9 2-2 2H7.99C6.89 23 6 22.1 6 21l.01-14c0-1.1.89-2 1.99-2h7zm-1 7h5.5L14 6.5V12z"/>
                </svg>
                <svg v-else-if="alert.type === 'trust'" width="20" height="20" viewBox="0 0 24 24" fill="currentColor">
                  <path d="M12 1L3 5v6c0 5.55 3.84 10.74 9 12 5.16-1.26 9-6.45 9-12V5l-9-4z"/>
                </svg>
                <svg v-else width="20" height="20" viewBox="0 0 24 24" fill="currentColor">
                  <path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm1 15h-2v-2h2v2zm0-4h-2V7h2v6z"/>
                </svg>
              </div>
              <div class="alert-content">
                <span class="alert-title">{{ alert.title }}</span>
                <span class="alert-desc">{{ alert.description }}</span>
              </div>
              <svg class="alert-arrow" width="20" height="20" viewBox="0 0 24 24" fill="currentColor">
                <path d="M8.59 16.59L13.17 12 8.59 7.41 10 6l6 6-6 6-1.41-1.41z"/>
              </svg>
            </div>
          </div>
        </section>

        <!-- Classes Section -->
        <section class="classes-section">
          <div class="section-header">
            <h2 class="section-title">My Classes</h2>
            <button class="create-btn" @click="showCreateModal = true">
              <svg width="20" height="20" viewBox="0 0 24 24" fill="currentColor">
                <path d="M19 13h-6v6h-2v-6H5v-2h6V5h2v6h6v2z"/>
              </svg>
              Create Class
            </button>
          </div>
          
          <div class="classes-grid" v-if="classes.length > 0">
            <div 
              v-for="cls in classes" 
              :key="cls.class_id"
              class="class-card"
              @click="goToClass(cls)"
            >
              <div class="class-header" :style="{ background: cls.color }">
                <h3 class="class-name">{{ cls.name }}</h3>
                <p class="class-section" v-if="cls.section">{{ cls.section }}</p>
                <div class="class-code">
                  <span>Code: {{ cls.class_code }}</span>
                </div>
              </div>
              <div class="class-body">
                <p class="class-subject">{{ cls.subject }}</p>
              </div>
              <div class="class-footer">
                <div class="class-stats">
                  <span class="class-stat">
                    <svg width="16" height="16" viewBox="0 0 24 24" fill="currentColor">
                      <path d="M16 11c1.66 0 2.99-1.34 2.99-3S17.66 5 16 5c-1.66 0-3 1.34-3 3s1.34 3 3 3zm-8 0c1.66 0 2.99-1.34 2.99-3S9.66 5 8 5C6.34 5 5 6.34 5 8s1.34 3 3 3z"/>
                    </svg>
                    {{ cls.student_count }} students
                  </span>
                  <span class="class-stat">
                    <svg width="16" height="16" viewBox="0 0 24 24" fill="currentColor">
                      <path d="M19 3H5c-1.1 0-2 .9-2 2v14c0 1.1.9 2 2 2h14c1.1 0 2-.9 2-2V5c0-1.1-.9-2-2-2z"/>
                    </svg>
                    {{ cls.assignment_count }} assignments
                  </span>
                </div>
              </div>
            </div>
          </div>
          
          <div class="empty-state" v-else>
            <svg width="80" height="80" viewBox="0 0 24 24" fill="#dadce0">
              <path d="M12 3L1 9l11 6 9-4.91V17h2V9M5 13.18v4L12 21l7-3.82v-4L12 17l-7-3.82z"/>
            </svg>
            <h3>No classes yet</h3>
            <p>Create your first class to get started</p>
            <button class="create-btn primary" @click="showCreateModal = true">
              Create Class
            </button>
          </div>
        </section>
      </div>
    </main>

    <!-- Create Class Modal -->
    <div v-if="showCreateModal" class="modal-overlay" @click.self="showCreateModal = false">
      <div class="modal">
        <div class="modal-header">
          <h2>Create a new class</h2>
          <button class="modal-close" @click="showCreateModal = false">
            <svg width="24" height="24" viewBox="0 0 24 24" fill="currentColor">
              <path d="M19 6.41L17.59 5 12 10.59 6.41 5 5 6.41 10.59 12 5 17.59 6.41 19 12 13.41 17.59 19 19 17.59 13.41 12z"/>
            </svg>
          </button>
        </div>
        
        <form @submit.prevent="handleCreateClass" class="modal-body">
          <div class="form-group">
            <label>Class name *</label>
            <input 
              v-model="newClass.name" 
              type="text" 
              placeholder="e.g., CS 301 - Data Structures"
              required 
              autofocus
            />
          </div>
          
          <div class="form-row">
            <div class="form-group">
              <label>Subject *</label>
              <input 
                v-model="newClass.subject" 
                type="text" 
                placeholder="e.g., Computer Science"
                required
              />
            </div>
            <div class="form-group">
              <label>Section</label>
              <input 
                v-model="newClass.section" 
                type="text" 
                placeholder="e.g., Section A"
              />
            </div>
          </div>
          
          <div class="form-group">
            <label>Description *</label>
            <textarea 
              v-model="newClass.description" 
              placeholder="Describe the course topics and what students will learn. This helps generate relevant writing prompts for the authorship verification profile."
              rows="3"
              required
            ></textarea>
            <span style="font-size: 12px; color: #5f6368; margin-top: 4px; display: block;">A Writing Profile Assessment will be auto-created for this course using AI-generated prompts based on the description above.</span>
          </div>
          
          <div class="form-group">
            <label>Theme Color</label>
            <div class="color-picker">
              <button 
                v-for="color in colors" 
                :key="color"
                type="button"
                class="color-option"
                :class="{ selected: newClass.color === color }"
                :style="{ background: color }"
                @click="newClass.color = color"
              ></button>
            </div>
          </div>
          
          <div class="modal-footer">
            <button type="button" class="btn-text" @click="showCreateModal = false">Cancel</button>
            <button type="submit" class="btn-primary" :disabled="creating">
              {{ creating ? 'Creating...' : 'Create' }}
            </button>
          </div>
        </form>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { useRouter } from 'vue-router'
import { useAuth } from '@/composables/auth'
import { useClasses, useAssignments } from '@/composables/classroom'

const router = useRouter()
const { user, logout, initAuth } = useAuth()
const { classes, fetchClasses, createClass, fetchDashboardStats, loading: classesLoading } = useClasses()
const { assignments, fetchAssignments } = useAssignments()

const pageLoading = ref(true)
const showSidebar = ref(false)
const showProfileMenu = ref(false)
const showCreateModal = ref(false)
const creating = ref(false)

// Theme colors
const colors = [
  '#1a73e8', '#137333', '#c5221f', '#f9ab00',
  '#9334e6', '#188038', '#e37400', '#1557b0'
]

const newClass = ref({
  name: '',
  subject: '',
  section: '',
  description: '',
  color: '#1a73e8'
})

// Dashboard stats from backend
const dashboardStats = ref({
  total_students: 0,
  pending_submissions: 0,
  average_trust_score: 0,
  active_classes: 0,
  flagged_submissions: []
})

// Computed stats
const totalStudents = computed(() => {
  return dashboardStats.value.total_students
})

const pendingSubmissions = computed(() => {
  return dashboardStats.value.pending_submissions
})

const averageTrust = computed(() => {
  return dashboardStats.value.average_trust_score
})

const flaggedSubmissions = computed(() => {
  return dashboardStats.value.flagged_submissions || []
})

// Methods
async function handleCreateClass() {
  creating.value = true
  const result = await createClass(newClass.value)
  creating.value = false
  
  if (result.success) {
    showCreateModal.value = false
    newClass.value = { name: '', subject: '', section: '', description: '', color: '#1a73e8' }
    // Re-fetch classes and stats to ensure they reflect the new class
    await fetchClasses()
    await loadDashboardStats()
  } else {
    alert(result.error)
  }
}

async function loadDashboardStats() {
  const result = await fetchDashboardStats()
  if (result.success) {
    dashboardStats.value = result.data
  }
}

function goToClass(cls) {
  router.push(`/teacher/class/${cls.class_id}`)
}

function handleAlertClick(alert) {
  if (alert.submissionId) {
    router.push(`/teacher/submission/${alert.submissionId}/grade`)
  } else if (alert.assignmentId) {
    router.push(`/teacher/assignment/${alert.assignmentId}`)
  }
}

async function handleLogout() {
  await logout()
  router.push('/login')
}

function handleClickOutside(e) {
  if (!e.target.closest('.profile')) {
    showProfileMenu.value = false
  }
}

onMounted(async () => {
  const isAuth = await initAuth()
  if (!isAuth) {
    router.push('/login')
    return
  }

  // Check role
  if (user.value?.role !== 'teacher') {
    router.push('/student/dashboard')
    return
  }

  await Promise.all([fetchClasses(), fetchAssignments(), loadDashboardStats()])
  pageLoading.value = false

  document.addEventListener('click', handleClickOutside)
})

onUnmounted(() => {
  document.removeEventListener('click', handleClickOutside)
})
</script>

<style scoped>
.teacher-dashboard {
  min-height: 100vh;
  background: #f8f9fa;
  font-family: 'Google Sans', 'Roboto', -apple-system, BlinkMacSystemFont, sans-serif;
}

/* Header Styles */
.dashboard-header {
  position: sticky;
  top: 0;
  z-index: 100;
  display: flex;
  align-items: center;
  justify-content: space-between;
  height: 64px;
  padding: 0 24px;
  background: #fff;
  border-bottom: 1px solid #e0e0e0;
}

.header-left {
  display: flex;
  align-items: center;
  gap: 16px;
}

.menu-btn {
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
}

.menu-btn:hover {
  background: rgba(0, 0, 0, 0.04);
}

.logo {
  display: flex;
  align-items: center;
  gap: 8px;
}

.logo-text {
  font-size: 20px;
  font-weight: 500;
  color: #5f6368;
}

.role-badge {
  background: #e8f0fe;
  color: #1a73e8;
  padding: 4px 12px;
  border-radius: 16px;
  font-size: 12px;
  font-weight: 500;
}

.header-nav {
  display: flex;
  gap: 8px;
}

.nav-link {
  padding: 8px 16px;
  color: #5f6368;
  text-decoration: none;
  border-radius: 20px;
  font-size: 14px;
  font-weight: 500;
  transition: all 0.2s;
}

.nav-link:hover {
  background: rgba(0, 0, 0, 0.04);
}

.nav-link.active {
  background: #e8f0fe;
  color: #1a73e8;
}

.header-right {
  display: flex;
  align-items: center;
}

.profile {
  position: relative;
  cursor: pointer;
}

.avatar {
  width: 36px;
  height: 36px;
  border-radius: 50%;
  object-fit: cover;
}

.avatar-placeholder {
  display: flex;
  align-items: center;
  justify-content: center;
  background: #1a73e8;
  color: white;
  font-size: 16px;
  font-weight: 500;
}

/* Dropdown */
.dropdown {
  position: absolute;
  top: calc(100% + 8px);
  right: 0;
  width: 300px;
  background: white;
  border-radius: 8px;
  box-shadow: 0 2px 10px rgba(0,0,0,0.2);
  overflow: hidden;
}

.dropdown-header {
  display: flex;
  align-items: center;
  gap: 16px;
  padding: 16px;
  background: #f8f9fa;
}

.dropdown-avatar {
  width: 48px;
  height: 48px;
  border-radius: 50%;
}

.dropdown-info {
  overflow: hidden;
}

.dropdown-name {
  font-weight: 500;
  color: #202124;
}

.dropdown-email {
  font-size: 13px;
  color: #5f6368;
  overflow: hidden;
  text-overflow: ellipsis;
}

.dropdown-divider {
  height: 1px;
  background: #e0e0e0;
}

.dropdown-item {
  display: flex;
  align-items: center;
  gap: 12px;
  width: 100%;
  padding: 12px 16px;
  border: none;
  background: transparent;
  font-size: 14px;
  color: #3c4043;
  text-decoration: none;
  cursor: pointer;
}

.dropdown-item:hover {
  background: #f1f3f4;
}

.dropdown-signout {
  color: #5f6368;
}

/* Main Content */
.dashboard-main {
  padding: 24px;
}

.dashboard-container {
  max-width: 1400px;
  margin: 0 auto;
}

/* Welcome Section */
.welcome-section {
  margin-bottom: 32px;
}

.welcome-section h1 {
  font-size: 28px;
  font-weight: 400;
  color: #202124;
  margin: 0 0 8px;
}

.welcome-section p {
  font-size: 16px;
  color: #5f6368;
  margin: 0;
}

/* Stats Section */
.stats-section {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
  gap: 16px;
  margin-bottom: 32px;
}

.stat-card {
  display: flex;
  align-items: center;
  gap: 16px;
  padding: 20px;
  background: white;
  border-radius: 12px;
  box-shadow: 0 1px 3px rgba(0,0,0,0.1);
}

.stat-icon {
  width: 48px;
  height: 48px;
  border-radius: 12px;
  display: flex;
  align-items: center;
  justify-content: center;
  color: white;
}

.stat-icon.blue { background: #1a73e8; }
.stat-icon.orange { background: #f9ab00; }
.stat-icon.green { background: #34a853; }
.stat-icon.purple { background: #9334e6; }

.stat-content {
  display: flex;
  flex-direction: column;
}

.stat-value {
  font-size: 28px;
  font-weight: 500;
  color: #202124;
}

.stat-label {
  font-size: 14px;
  color: #5f6368;
}

/* Alerts Section */
.alerts-section {
  margin-bottom: 32px;
}

.section-title {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 18px;
  font-weight: 500;
  color: #202124;
  margin: 0 0 16px;
}

.alert-cards {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.alert-card {
  display: flex;
  align-items: center;
  gap: 16px;
  padding: 16px;
  background: white;
  border-radius: 8px;
  border-left: 4px solid;
  cursor: pointer;
  transition: all 0.2s;
}

.alert-card:hover {
  box-shadow: 0 2px 8px rgba(0,0,0,0.1);
}

.alert-card.plagiarism {
  border-color: #ea4335;
}

.alert-card.trust {
  border-color: #f9ab00;
}

.alert-card.flag {
  border-color: #ea4335;
}

.alert-icon {
  width: 40px;
  height: 40px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  background: #fce8e6;
  color: #ea4335;
}

.alert-card.trust .alert-icon {
  background: #fef7e0;
  color: #f9ab00;
}

.alert-content {
  flex: 1;
  display: flex;
  flex-direction: column;
}

.alert-title {
  font-weight: 500;
  color: #202124;
}

.alert-desc {
  font-size: 13px;
  color: #5f6368;
}

.alert-arrow {
  color: #5f6368;
}

/* Classes Section */
.classes-section {
  margin-bottom: 32px;
}

.section-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 16px;
}

.create-btn {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 10px 20px;
  background: #1a73e8;
  color: white;
  border: none;
  border-radius: 24px;
  font-size: 14px;
  font-weight: 500;
  cursor: pointer;
  transition: all 0.2s;
}

.create-btn:hover {
  background: #1557b0;
  box-shadow: 0 2px 8px rgba(26, 115, 232, 0.3);
}

.classes-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(300px, 1fr));
  gap: 20px;
}

.class-card {
  background: white;
  border-radius: 12px;
  overflow: hidden;
  box-shadow: 0 1px 3px rgba(0,0,0,0.1);
  cursor: pointer;
  transition: all 0.2s;
}

.class-card:hover {
  box-shadow: 0 4px 12px rgba(0,0,0,0.15);
  transform: translateY(-2px);
}

.class-header {
  padding: 20px;
  color: white;
  min-height: 100px;
}

.class-name {
  font-size: 18px;
  font-weight: 500;
  margin: 0 0 4px;
}

.class-section {
  font-size: 14px;
  opacity: 0.9;
  margin: 0 0 12px;
}

.class-code {
  font-size: 12px;
  opacity: 0.8;
  background: rgba(255,255,255,0.2);
  padding: 4px 8px;
  border-radius: 4px;
  display: inline-block;
}

.class-body {
  padding: 16px 20px;
  border-bottom: 1px solid #e0e0e0;
}

.class-subject {
  font-size: 14px;
  color: #5f6368;
  margin: 0;
}

.class-footer {
  padding: 12px 20px;
}

.class-stats {
  display: flex;
  gap: 16px;
}

.class-stat {
  display: flex;
  align-items: center;
  gap: 4px;
  font-size: 13px;
  color: #5f6368;
}

/* Empty State */
.empty-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  padding: 60px 20px;
  text-align: center;
}

.empty-state h3 {
  font-size: 18px;
  color: #202124;
  margin: 16px 0 8px;
}

.empty-state p {
  font-size: 14px;
  color: #5f6368;
  margin: 0 0 24px;
}

/* Modal */
.modal-overlay {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.5);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 1000;
  padding: 20px;
}

.modal {
  background: white;
  border-radius: 12px;
  width: 100%;
  max-width: 500px;
  max-height: 90vh;
  overflow-y: auto;
}

.modal-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 20px 24px;
  border-bottom: 1px solid #e0e0e0;
}

.modal-header h2 {
  font-size: 20px;
  font-weight: 500;
  color: #202124;
  margin: 0;
}

.modal-close {
  width: 36px;
  height: 36px;
  border: none;
  background: transparent;
  border-radius: 50%;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  color: #5f6368;
}

.modal-close:hover {
  background: #f1f3f4;
}

.modal-body {
  padding: 24px;
}

.form-group {
  margin-bottom: 20px;
}

.form-group label {
  display: block;
  font-size: 14px;
  font-weight: 500;
  color: #202124;
  margin-bottom: 8px;
}

.form-group input,
.form-group textarea {
  width: 100%;
  padding: 12px;
  border: 1px solid #dadce0;
  border-radius: 8px;
  font-size: 14px;
  transition: border-color 0.2s;
  box-sizing: border-box;
  color: #202124;
  background: white;
}

.form-group input:focus,
.form-group textarea:focus {
  outline: none;
  border-color: #1a73e8;
}

.form-row {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 16px;
}

.color-picker {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
}

.color-option {
  width: 36px;
  height: 36px;
  border-radius: 50%;
  border: 3px solid transparent;
  cursor: pointer;
  transition: transform 0.2s;
}

.color-option:hover {
  transform: scale(1.1);
}

.color-option.selected {
  border-color: #202124;
}

.modal-footer {
  display: flex;
  justify-content: flex-end;
  gap: 12px;
  padding-top: 16px;
  border-top: 1px solid #e0e0e0;
}

.btn-text {
  padding: 10px 20px;
  border: none;
  background: transparent;
  font-size: 14px;
  font-weight: 500;
  color: #1a73e8;
  cursor: pointer;
  border-radius: 8px;
}

.btn-text:hover {
  background: rgba(26, 115, 232, 0.04);
}

.btn-primary {
  padding: 10px 24px;
  border: none;
  background: #1a73e8;
  color: white;
  font-size: 14px;
  font-weight: 500;
  border-radius: 8px;
  cursor: pointer;
}

.btn-primary:hover:not(:disabled) {
  background: #1557b0;
}

.btn-primary:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}

@media (max-width: 768px) {
  .header-nav {
    display: none;
  }
  
  .stats-section {
    grid-template-columns: 1fr 1fr;
  }
  
  .form-row {
    grid-template-columns: 1fr;
  }
}
</style>
