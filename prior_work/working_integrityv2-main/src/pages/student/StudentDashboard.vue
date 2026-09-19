<template>
  <div class="student-dashboard">
    <!-- Header -->
    <header class="dashboard-header">
      <div class="header-left">
        <h1>My Classes</h1>
      </div>
      <div class="header-right">
        <button class="btn-secondary" @click="showJoinModal = true">
          <svg width="20" height="20" viewBox="0 0 24 24" fill="currentColor">
            <path d="M19 13h-6v6h-2v-6H5v-2h6V5h2v6h6v2z"/>
          </svg>
          Join Class
        </button>
        <div class="user-menu">
          <button class="user-btn" @click="toggleUserMenu">
            <div class="avatar">{{ userInitials }}</div>
            <span>{{ user?.email }}</span>
          </button>
          <div v-if="showUserMenu" class="dropdown-menu">
            <router-link to="/profile" class="menu-item">Profile</router-link>
            <button class="menu-item" @click="handleLogout">Logout</button>
          </div>
        </div>
      </div>
    </header>

    <!-- Main Content -->
    <main class="dashboard-content">
      <!-- Upcoming Due -->
      <section v-if="upcomingAssignments.length > 0" class="upcoming-section">
        <h2>Due Soon</h2>
        <div class="upcoming-list">
          <div 
            v-for="assignment in upcomingAssignments" 
            :key="assignment.assignment_id"
            class="upcoming-card"
            @click="goToAssignment(assignment)"
          >
            <div class="assignment-icon" :style="{ background: getClassColor(assignment.class_id) }">
              <svg width="24" height="24" viewBox="0 0 24 24" fill="white">
                <path d="M14 2H6c-1.1 0-1.99.9-1.99 2L4 20c0 1.1.89 2 1.99 2H18c1.1 0 2-.9 2-2V8l-6-6zm2 16H8v-2h8v2zm0-4H8v-2h8v2zm-3-5V3.5L18.5 9H13z"/>
              </svg>
            </div>
            <div class="assignment-info">
              <span class="assignment-title">{{ assignment.title }}</span>
              <span class="class-name">{{ assignment.class_name }}</span>
            </div>
            <div class="due-info">
              <span class="due-label">Due</span>
              <span class="due-date" :class="{ urgent: isUrgent(assignment.due_date) }">
                {{ formatDueDate(assignment.due_date) }}
              </span>
            </div>
          </div>
        </div>
      </section>

      <!-- Classes Grid -->
      <section class="classes-section">
        <h2>My Classes</h2>
        <div v-if="loading" class="loading">
          <div class="spinner"></div>
          <span>Loading classes...</span>
        </div>
        <div v-else-if="classes.length === 0" class="empty-state">
          <svg width="120" height="120" viewBox="0 0 24 24" fill="#dadce0">
            <path d="M12 3L1 9l4 2.18v6L12 21l7-3.82v-6l2-1.09V17h2V9L12 3zm6.82 6L12 12.72 5.18 9 12 5.28 18.82 9zM17 15.99l-5 2.73-5-2.73v-3.72L12 15l5-2.73v3.72z"/>
          </svg>
          <h3>No Classes Yet</h3>
          <p>Join a class to get started with your assignments</p>
          <button class="btn-primary" @click="showJoinModal = true">
            Join Your First Class
          </button>
        </div>
        <div v-else class="classes-grid">
          <div 
            v-for="cls in classes" 
            :key="cls.class_id"
            class="class-card"
            @click="goToClass(cls)"
            :style="{ '--class-color': getClassColor(cls.class_id) }"
          >
            <div class="card-header">
              <h3>{{ cls.name }}</h3>
              <span class="section">{{ cls.section }}</span>
            </div>
            <div class="card-body">
              <span class="subject">{{ cls.subject }}</span>
              <span class="teacher">{{ cls.teacher_name }}</span>
            </div>
            <div class="card-footer">
              <div class="stat">
                <span class="stat-value">{{ getClassAssignments(cls.class_id).length }}</span>
                <span class="stat-label">Assignments</span>
              </div>
              <div v-if="getPendingCount(cls.class_id) > 0" class="pending-badge">
                {{ getPendingCount(cls.class_id) }} pending
              </div>
            </div>
          </div>
        </div>
      </section>

      <!-- Cumulative Grades Per Course -->
      <section v-if="courseGrades.length > 0" class="activity-section">
        <h2>Course Grades</h2>
        <div class="course-grades-list">
          <div 
            v-for="course in courseGrades" 
            :key="course.class_id"
            class="course-grade-card"
            @click="goToClass(course)"
          >
            <div class="course-grade-left">
              <div class="course-color-dot" :style="{ background: getClassColor(course.class_id) }"></div>
              <div class="course-grade-info">
                <span class="course-name">{{ course.class_name }}</span>
                <span class="course-detail">{{ course.graded_count }}/{{ course.total_count }} graded</span>
              </div>
            </div>
            <div class="course-grade-right">
              <span class="course-percentage" :class="getGradeClassFromPercent(course.percentage)">
                {{ course.percentage }}%
              </span>
              <span class="course-points">{{ course.earned_points }}/{{ course.total_points }} pts</span>
            </div>
          </div>
        </div>
      </section>

      <!-- Recent Activity -->
      <section v-if="recentGrades.length > 0" class="activity-section">
        <h2>Recent Grades</h2>
        <div class="grades-list">
          <div 
            v-for="grade in recentGrades" 
            :key="grade.submission_id"
            class="grade-card"
            @click="viewSubmission(grade)"
          >
            <div class="grade-info">
              <span class="assignment-name">{{ grade.assignment_title }}</span>
              <span class="class-name">{{ grade.class_name }}</span>
            </div>
            <div class="grade-score">
              <span class="score">{{ grade.grade }}/{{ grade.max_points }}</span>
              <span class="percentage">{{ Math.round((grade.grade / grade.max_points) * 100) }}%</span>
            </div>
          </div>
        </div>
      </section>
    </main>

    <!-- Join Class Modal -->
    <div v-if="showJoinModal" class="modal-overlay" @click.self="showJoinModal = false">
      <div class="modal">
        <div class="modal-header">
          <h2>Join Class</h2>
          <button class="close-btn" @click="showJoinModal = false">
            <svg width="24" height="24" viewBox="0 0 24 24" fill="currentColor">
              <path d="M19 6.41L17.59 5 12 10.59 6.41 5 5 6.41 10.59 12 5 17.59 6.41 19 12 13.41 17.59 19 19 17.59 13.41 12z"/>
            </svg>
          </button>
        </div>
        <div class="modal-body">
          <p>Ask your teacher for the class code, then enter it here.</p>
          <div class="form-group">
            <label>Class Code</label>
            <input 
              v-model="joinCode" 
              type="text" 
              placeholder="e.g., ABC123"
              class="code-input"
              @keyup.enter="joinClass"
            />
          </div>
          <p v-if="joinError" class="error-text">{{ joinError }}</p>
        </div>
        <div class="modal-footer">
          <button class="btn-text" @click="showJoinModal = false">Cancel</button>
          <button class="btn-primary" @click="joinClass" :disabled="joining || !joinCode.trim()">
            {{ joining ? 'Joining...' : 'Join' }}
          </button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { useAuth } from '@/composables/auth'
import { useClasses, useAssignments } from '@/composables/classroom'

const router = useRouter()
const { user, logout } = useAuth()
const { classes, fetchClasses, joinClass: join } = useClasses()
const { assignments, fetchAssignments } = useAssignments()

const loading = ref(false)
const showJoinModal = ref(false)
const showUserMenu = ref(false)
const joinCode = ref('')
const joinError = ref('')
const joining = ref(false)

const userInitials = computed(() => {
  if (!user.value?.email) return '?'
  return user.value.email.charAt(0).toUpperCase()
})

const upcomingAssignments = computed(() => {
  const now = new Date()
  const weekFromNow = new Date(now.getTime() + 7 * 24 * 60 * 60 * 1000)
  
  return assignments.value
    .filter(a => {
      const due = new Date(a.due_date)
      return due > now && due < weekFromNow && !a.submitted
    })
    .sort((a, b) => new Date(a.due_date) - new Date(b.due_date))
    .slice(0, 5)
})

const recentGrades = computed(() => {
  return assignments.value
    .filter(a => a.grade !== null && a.grade !== undefined)
    .sort((a, b) => new Date(b.graded_at) - new Date(a.graded_at))
    .slice(0, 5)
})

// Cumulative grades per course
const courseGrades = computed(() => {
  const courseMap = {}
  
  for (const a of assignments.value) {
    if (!courseMap[a.class_id]) {
      courseMap[a.class_id] = {
        class_id: a.class_id,
        class_name: a.class_name || 'Unknown Class',
        earned_points: 0,
        total_points: 0,
        graded_count: 0,
        total_count: 0
      }
    }
    courseMap[a.class_id].total_count++
    
    if (a.grade !== null && a.grade !== undefined) {
      courseMap[a.class_id].earned_points += a.grade
      courseMap[a.class_id].total_points += a.points || a.max_points || 0
      courseMap[a.class_id].graded_count++
    }
  }
  
  return Object.values(courseMap)
    .filter(c => c.graded_count > 0)
    .map(c => ({
      ...c,
      percentage: c.total_points > 0 ? Math.round((c.earned_points / c.total_points) * 100) : 0
    }))
    .sort((a, b) => a.class_name.localeCompare(b.class_name))
})

function getGradeClassFromPercent(percent) {
  if (percent >= 90) return 'excellent'
  if (percent >= 80) return 'good'
  if (percent >= 70) return 'average'
  return 'poor'
}

const classColors = ['#1a73e8', '#0d652d', '#c5221f', '#8430ce', '#e37400', '#137333', '#185abc', '#9334e6']

function getClassColor(classId) {
  const index = classId ? classId.charCodeAt(0) % classColors.length : 0
  return classColors[index]
}

function getClassAssignments(classId) {
  return assignments.value.filter(a => a.class_id === classId)
}

function getPendingCount(classId) {
  return getClassAssignments(classId).filter(a => !a.submitted && new Date(a.due_date) > new Date()).length
}

function isUrgent(dueDate) {
  const hours = (new Date(dueDate) - new Date()) / (1000 * 60 * 60)
  return hours < 24
}

function formatDueDate(date) {
  const due = new Date(date)
  const now = new Date()
  const diff = due - now
  const hours = diff / (1000 * 60 * 60)
  
  if (hours < 24) {
    return `${Math.round(hours)} hours`
  }
  const days = Math.floor(hours / 24)
  return `${days} day${days > 1 ? 's' : ''}`
}

function toggleUserMenu() {
  showUserMenu.value = !showUserMenu.value
}

function goToClass(cls) {
  router.push(`/student/class/${cls.class_id}`)
}

function goToAssignment(assignment) {
  router.push(`/student/assignment/${assignment.assignment_id}`)
}

function viewSubmission(grade) {
  router.push(`/student/submission/${grade.submission_id}`)
}

async function joinClass() {
  if (!joinCode.value.trim()) return
  
  joining.value = true
  joinError.value = ''
  
  const result = await join(joinCode.value.trim().toUpperCase())
  
  joining.value = false
  
  if (result.success) {
    showJoinModal.value = false
    joinCode.value = ''
    await loadData()
  } else {
    joinError.value = result.error || 'Failed to join class'
  }
}

async function handleLogout() {
  await logout()
  router.push('/login')
}

async function loadData() {
  loading.value = true
  await fetchClasses()
  await fetchAssignments()
  loading.value = false
}

onMounted(() => {
  loadData()
})
</script>

<style scoped>
.student-dashboard {
  min-height: 100vh;
  background: #f8f9fa;
}

.dashboard-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 16px 24px;
  background: white;
  border-bottom: 1px solid #e0e0e0;
  position: sticky;
  top: 0;
  z-index: 100;
}

.header-left h1 {
  font-size: 24px;
  font-weight: 500;
  margin: 0;
  color: #202124;
}

.header-right {
  display: flex;
  align-items: center;
  gap: 16px;
}

.btn-secondary {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 10px 20px;
  border: 1px solid #dadce0;
  background: white;
  border-radius: 8px;
  font-weight: 500;
  color: #5f6368;
  cursor: pointer;
}

.btn-secondary:hover {
  background: #f8f9fa;
}

.user-menu {
  position: relative;
}

.user-btn {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 12px;
  border: none;
  background: transparent;
  cursor: pointer;
  border-radius: 24px;
  color: #5f6368;
}

.user-btn:hover {
  background: #f1f3f4;
}

.avatar {
  width: 32px;
  height: 32px;
  border-radius: 50%;
  background: #1a73e8;
  color: white;
  display: flex;
  align-items: center;
  justify-content: center;
  font-weight: 500;
}

.dropdown-menu {
  position: absolute;
  top: 100%;
  right: 0;
  margin-top: 8px;
  background: white;
  border-radius: 8px;
  box-shadow: 0 4px 12px rgba(0,0,0,0.15);
  min-width: 160px;
  overflow: hidden;
}

.menu-item {
  display: block;
  width: 100%;
  padding: 12px 16px;
  border: none;
  background: transparent;
  text-align: left;
  cursor: pointer;
  color: #202124;
  text-decoration: none;
}

.menu-item:hover {
  background: #f8f9fa;
}

/* Main Content */
.dashboard-content {
  max-width: 1200px;
  margin: 0 auto;
  padding: 24px;
}

section {
  margin-bottom: 32px;
}

section h2 {
  font-size: 18px;
  font-weight: 500;
  color: #202124;
  margin: 0 0 16px;
}

/* Upcoming Assignments */
.upcoming-list {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.upcoming-card {
  display: flex;
  align-items: center;
  gap: 16px;
  background: white;
  border-radius: 12px;
  padding: 16px;
  cursor: pointer;
  transition: box-shadow 0.2s;
}

.upcoming-card:hover {
  box-shadow: 0 2px 8px rgba(0,0,0,0.1);
}

.assignment-icon {
  width: 48px;
  height: 48px;
  border-radius: 8px;
  display: flex;
  align-items: center;
  justify-content: center;
}

.assignment-info {
  flex: 1;
  display: flex;
  flex-direction: column;
}

.assignment-title {
  font-weight: 500;
  color: #202124;
}

.class-name {
  font-size: 13px;
  color: #5f6368;
}

.due-info {
  text-align: right;
}

.due-label {
  display: block;
  font-size: 12px;
  color: #5f6368;
}

.due-date {
  font-weight: 500;
  color: #202124;
}

.due-date.urgent {
  color: #d93025;
}

/* Classes Grid */
.classes-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
  gap: 20px;
}

.class-card {
  background: white;
  border-radius: 12px;
  overflow: hidden;
  cursor: pointer;
  transition: box-shadow 0.2s;
}

.class-card:hover {
  box-shadow: 0 4px 12px rgba(0,0,0,0.15);
}

.card-header {
  background: var(--class-color);
  padding: 24px 20px;
  color: white;
}

.card-header h3 {
  margin: 0 0 4px;
  font-size: 18px;
  font-weight: 500;
}

.section {
  font-size: 14px;
  opacity: 0.9;
}

.card-body {
  padding: 16px 20px;
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.subject {
  font-weight: 500;
  color: #202124;
}

.teacher {
  font-size: 14px;
  color: #5f6368;
}

.card-footer {
  padding: 12px 20px;
  border-top: 1px solid #e0e0e0;
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.stat {
  display: flex;
  flex-direction: column;
}

.stat-value {
  font-weight: 600;
  color: #202124;
}

.stat-label {
  font-size: 12px;
  color: #5f6368;
}

.pending-badge {
  background: #fef7e0;
  color: #f9ab00;
  padding: 4px 12px;
  border-radius: 12px;
  font-size: 13px;
  font-weight: 500;
}

/* Course Grades */
.course-grades-list {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.course-grade-card {
  display: flex;
  justify-content: space-between;
  align-items: center;
  background: white;
  border-radius: 12px;
  padding: 16px 20px;
  cursor: pointer;
  transition: box-shadow 0.2s;
}

.course-grade-card:hover {
  box-shadow: 0 2px 8px rgba(0,0,0,0.1);
}

.course-grade-left {
  display: flex;
  align-items: center;
  gap: 14px;
}

.course-color-dot {
  width: 12px;
  height: 12px;
  border-radius: 50%;
  flex-shrink: 0;
}

.course-grade-info {
  display: flex;
  flex-direction: column;
}

.course-name {
  font-weight: 500;
  color: #202124;
  font-size: 15px;
}

.course-detail {
  font-size: 13px;
  color: #5f6368;
}

.course-grade-right {
  text-align: right;
  display: flex;
  flex-direction: column;
}

.course-percentage {
  font-size: 22px;
  font-weight: 600;
}

.course-percentage.excellent { color: #1e8e3e; }
.course-percentage.good { color: #1a73e8; }
.course-percentage.average { color: #f9ab00; }
.course-percentage.poor { color: #d93025; }

.course-points {
  font-size: 13px;
  color: #5f6368;
}

/* Recent Grades */
.grades-list {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.grade-card {
  display: flex;
  justify-content: space-between;
  align-items: center;
  background: white;
  border-radius: 12px;
  padding: 16px 20px;
  cursor: pointer;
}

.grade-card:hover {
  box-shadow: 0 2px 8px rgba(0,0,0,0.1);
}

.grade-info {
  display: flex;
  flex-direction: column;
}

.assignment-name {
  font-weight: 500;
  color: #202124;
}

.grade-score {
  text-align: right;
}

.score {
  display: block;
  font-weight: 600;
  color: #202124;
}

.percentage {
  font-size: 13px;
  color: #5f6368;
}

/* Empty State */
.empty-state {
  text-align: center;
  padding: 60px 20px;
  background: white;
  border-radius: 12px;
}

.empty-state h3 {
  margin: 20px 0 8px;
  color: #202124;
}

.empty-state p {
  color: #5f6368;
  margin-bottom: 20px;
}

.btn-primary {
  padding: 12px 24px;
  border: none;
  background: #1a73e8;
  color: white;
  font-weight: 500;
  border-radius: 8px;
  cursor: pointer;
}

.btn-primary:hover:not(:disabled) {
  background: #1557b0;
}

.btn-primary:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

/* Loading */
.loading {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 12px;
  padding: 60px;
  color: #5f6368;
}

.spinner {
  width: 40px;
  height: 40px;
  border: 3px solid #e0e0e0;
  border-top-color: #1a73e8;
  border-radius: 50%;
  animation: spin 1s linear infinite;
}

@keyframes spin {
  to { transform: rotate(360deg); }
}

/* Modal */
.modal-overlay {
  position: fixed;
  inset: 0;
  background: rgba(0,0,0,0.5);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 1000;
}

.modal {
  background: white;
  border-radius: 16px;
  width: 100%;
  max-width: 400px;
  overflow: hidden;
}

.modal-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 20px 24px;
  border-bottom: 1px solid #e0e0e0;
}

.modal-header h2 {
  margin: 0;
  font-size: 20px;
  color: #202124;
}

.close-btn {
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

.close-btn:hover {
  background: #f1f3f4;
}

.modal-body {
  padding: 24px;
}

.modal-body p {
  margin: 0 0 20px;
  color: #5f6368;
}

.form-group {
  margin-bottom: 16px;
}

.form-group label {
  display: block;
  font-weight: 500;
  margin-bottom: 8px;
  color: #202124;
}

.code-input {
  width: 100%;
  padding: 16px;
  border: 2px solid #dadce0;
  border-radius: 8px;
  font-size: 18px;
  text-align: center;
  text-transform: uppercase;
  letter-spacing: 4px;
  box-sizing: border-box;
  color: #202124 !important;
  background: #fff !important;
}

.code-input:focus {
  outline: none;
  border-color: #1a73e8;
}

.error-text {
  color: #d93025 !important;
  font-size: 14px;
}

.modal-footer {
  display: flex;
  justify-content: flex-end;
  gap: 12px;
  padding: 16px 24px;
  border-top: 1px solid #e0e0e0;
}

.btn-text {
  padding: 10px 20px;
  border: none;
  background: transparent;
  color: #5f6368;
  font-weight: 500;
  cursor: pointer;
  border-radius: 8px;
}

.btn-text:hover {
  background: #f1f3f4;
}
</style>
