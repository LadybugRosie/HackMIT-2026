<template>
  <div class="student-class-view">
    <!-- Header -->
    <header class="page-header">
      <div class="header-left">
        <button @click="goBack" class="back-btn">
          <svg width="24" height="24" viewBox="0 0 24 24" fill="currentColor">
            <path d="M20 11H7.83l5.59-5.59L12 4l-8 8 8 8 1.41-1.41L7.83 13H20v-2z"/>
          </svg>
        </button>
        <div class="header-info" v-if="classData">
          <h1>{{ classData.name }}</h1>
          <span class="section">{{ classData.section }}</span>
        </div>
      </div>
    </header>

    <!-- Loading -->
    <div v-if="loading" class="loading-state">
      <div class="spinner"></div>
      <p>Loading class...</p>
    </div>

    <!-- Main Content -->
    <main v-else-if="classData" class="page-content">
      <!-- Class Banner -->
      <div class="class-banner" :style="{ backgroundColor: classColor }">
        <div class="banner-content">
          <h2>{{ classData.name }}</h2>
          <p v-if="classData.section">{{ classData.section }}</p>
          <span class="teacher-name">{{ classData.teacher_name }}</span>
        </div>
      </div>

      <div class="content-layout">
        <!-- Sidebar -->
        <aside class="sidebar">
          <!-- Class Info -->
          <div class="sidebar-card">
            <h3>Class Info</h3>
            <div class="info-item" v-if="classData.subject">
              <span class="label">Subject</span>
              <span class="value">{{ classData.subject }}</span>
            </div>
            <div class="info-item" v-if="classData.description">
              <span class="label">Description</span>
              <span class="value">{{ classData.description }}</span>
            </div>
            <div class="info-item">
              <span class="label">Teacher</span>
              <span class="value">{{ classData.teacher_name }}</span>
            </div>
          </div>

          <!-- Quick Actions -->
          <div class="sidebar-card">
            <h3>Quick Actions</h3>
            <button class="action-btn danger" @click="leaveClass">
              <svg width="20" height="20" viewBox="0 0 24 24" fill="currentColor">
                <path d="M10.09 15.59L11.5 17l5-5-5-5-1.41 1.41L12.67 11H3v2h9.67l-2.58 2.59zM19 3H5c-1.11 0-2 .9-2 2v4h2V5h14v14H5v-4H3v4c0 1.1.89 2 2 2h14c1.1 0 2-.9 2-2V5c0-1.1-.9-2-2-2z"/>
              </svg>
              Leave Class
            </button>
          </div>
        </aside>

        <!-- Main Area -->
        <div class="main-area">
          <!-- Tabs -->
          <div class="tabs">
            <button 
              class="tab" 
              :class="{ active: activeTab === 'assignments' }"
              @click="activeTab = 'assignments'"
            >
              Assignments
            </button>
            <button 
              class="tab" 
              :class="{ active: activeTab === 'classmates' }"
              @click="activeTab = 'classmates'"
            >
              Classmates
            </button>
          </div>

          <!-- Assignments Tab -->
          <div v-if="activeTab === 'assignments'" class="tab-content">
            <div v-if="assignmentsLoading" class="loading-state small">
              <div class="spinner"></div>
            </div>
            
            <div v-else-if="assignments.length === 0" class="empty-state">
              <svg width="64" height="64" viewBox="0 0 24 24" fill="#dadce0">
                <path d="M19 3H5c-1.1 0-2 .9-2 2v14c0 1.1.9 2 2 2h14c1.1 0 2-.9 2-2V5c0-1.1-.9-2-2-2zm-5 14H7v-2h7v2zm3-4H7v-2h10v2zm0-4H7V7h10v2z"/>
              </svg>
              <p>No assignments yet</p>
              <span>Your teacher hasn't posted any assignments.</span>
            </div>
            
            <div v-else class="assignments-list">
              <div 
                v-for="assignment in sortedAssignments" 
                :key="assignment.assignment_id"
                class="assignment-item"
                @click="openAssignment(assignment)"
              >
                <div class="assignment-icon" :class="getAssignmentIconClass(assignment)">
                  <svg width="24" height="24" viewBox="0 0 24 24" fill="currentColor">
                    <path d="M19 3H5c-1.1 0-2 .9-2 2v14c0 1.1.9 2 2 2h14c1.1 0 2-.9 2-2V5c0-1.1-.9-2-2-2zm-5 14H7v-2h7v2zm3-4H7v-2h10v2zm0-4H7V7h10v2z"/>
                  </svg>
                </div>
                
                <div class="assignment-content">
                  <h4>{{ assignment.title }}</h4>
                  <div class="assignment-meta">
                    <span class="due-date" :class="getDueClass(assignment)">
                      {{ formatDueDate(assignment.due_date) }}
                    </span>
                    <span class="points">{{ assignment.points }} points</span>
                  </div>
                </div>
                
                <div class="assignment-status">
                  <span v-if="assignment.my_submission" class="status-badge" :class="assignment.my_submission.status">
                    {{ formatStatus(assignment.my_submission.status) }}
                  </span>
                  <span v-else class="status-badge not-started">Not Started</span>
                  
                  <span v-if="assignment.my_submission?.grade !== null" class="grade">
                    {{ assignment.my_submission.grade }}/{{ assignment.points }}
                  </span>
                </div>
                
                <svg class="chevron" width="24" height="24" viewBox="0 0 24 24" fill="#5f6368">
                  <path d="M8.59 16.59L13.17 12 8.59 7.41 10 6l6 6-6 6-1.41-1.41z"/>
                </svg>
              </div>
            </div>
          </div>

          <!-- Classmates Tab -->
          <div v-if="activeTab === 'classmates'" class="tab-content">
            <div v-if="membersLoading" class="loading-state small">
              <div class="spinner"></div>
            </div>
            
            <div v-else class="members-list">
              <!-- Teacher -->
              <div class="member-section">
                <h4>Teacher</h4>
                <div class="member-item teacher">
                  <div class="avatar teacher-avatar">{{ getInitials(classData.teacher_name) }}</div>
                  <span class="name">{{ classData.teacher_name }}</span>
                </div>
              </div>
              
              <!-- Students -->
              <div class="member-section">
                <h4>Classmates ({{ members.length }})</h4>
                <div v-for="member in members" :key="member.user_id" class="member-item">
                  <div class="avatar">{{ getInitials(member.name) }}</div>
                  <span class="name">{{ member.name }}</span>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </main>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { useClasses, useAssignments } from '@/composables/classroom'

const router = useRouter()
const route = useRoute()
const classId = computed(() => route.params.classId)

const { fetchClass, currentClass: classData, getClassMembers, leaveClass: leave, loading } = useClasses()
const { fetchAssignments, assignments, loading: assignmentsLoading } = useAssignments()

const members = ref([])
const membersLoading = ref(false)
const activeTab = ref('assignments')

const classColors = ['#1a73e8', '#e8710a', '#1e8e3e', '#9334e6', '#e91e63', '#00acc1']

const classColor = computed(() => {
  if (!classId.value) return classColors[0]
  const hash = classId.value.split('').reduce((a, b) => a + b.charCodeAt(0), 0)
  return classColors[hash % classColors.length]
})

const sortedAssignments = computed(() => {
  return [...assignments.value].sort((a, b) => {
    // Sort by due date, most recent first
    return new Date(a.due_date) - new Date(b.due_date)
  })
})

function goBack() {
  router.push('/student/dashboard')
}

function openAssignment(assignment) {
  router.push(`/student/assignment/${assignment.assignment_id}`)
}

function formatDueDate(date) {
  const due = new Date(date)
  const now = new Date()
  const diff = due - now
  
  if (diff < 0) {
    return 'Past due'
  }
  
  return `Due ${due.toLocaleDateString('en-US', {
    month: 'short',
    day: 'numeric',
    hour: 'numeric',
    minute: '2-digit'
  })}`
}

function getDueClass(assignment) {
  const due = new Date(assignment.due_date)
  const now = new Date()
  const diff = due - now
  const days = Math.ceil(diff / (1000 * 60 * 60 * 24))
  
  if (diff < 0) return 'overdue'
  if (days <= 1) return 'urgent'
  if (days <= 3) return 'soon'
  return ''
}

function getAssignmentIconClass(assignment) {
  if (!assignment.my_submission) return 'pending'
  if (assignment.my_submission.status === 'returned') return 'returned'
  if (assignment.my_submission.status === 'graded') return 'graded'
  if (assignment.my_submission.status === 'submitted') return 'submitted'
  return 'in-progress'
}

function formatStatus(status) {
  const labels = {
    draft: 'In Progress',
    submitted: 'Submitted',
    graded: 'Graded',
    returned: 'Returned'
  }
  return labels[status] || status
}

function getInitials(name) {
  if (!name) return '?'
  return name.split(' ').map(n => n[0]).join('').toUpperCase().slice(0, 2)
}

async function leaveClass() {
  if (!confirm('Are you sure you want to leave this class?')) return
  
  const result = await leave(classId.value)
  if (result.success) {
    router.push('/student/dashboard')
  } else {
    alert(result.error || 'Failed to leave class')
  }
}

async function loadMembers() {
  membersLoading.value = true
  const result = await getClassMembers(classId.value)
  if (result.success) {
    members.value = result.data.filter(m => m.role === 'student')
  }
  membersLoading.value = false
}

async function loadData() {
  await fetchClass(classId.value)
  await fetchAssignments(classId.value)
  await loadMembers()
}

onMounted(loadData)
</script>

<style scoped>
.student-class-view {
  min-height: 100vh;
  background: #f8f9fa;
}

.page-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 12px 24px;
  background: white;
  border-bottom: 1px solid #e0e0e0;
  position: sticky;
  top: 0;
  z-index: 100;
}

.header-left {
  display: flex;
  align-items: center;
  gap: 16px;
}

.back-btn {
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

.back-btn:hover {
  background: #f1f3f4;
}

.header-info h1 {
  font-size: 18px;
  font-weight: 500;
  margin: 0;
  color: #202124;
}

.section {
  font-size: 13px;
  color: #5f6368;
}

.loading-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 80px;
  color: #5f6368;
}

.loading-state.small {
  padding: 40px;
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

.page-content {
  max-width: 1200px;
  margin: 0 auto;
}

/* Banner */
.class-banner {
  padding: 40px 24px;
  color: white;
}

.banner-content {
  max-width: 800px;
}

.banner-content h2 {
  font-size: 32px;
  font-weight: 400;
  margin: 0 0 8px;
}

.banner-content p {
  font-size: 18px;
  margin: 0 0 16px;
  opacity: 0.9;
}

.teacher-name {
  font-size: 14px;
  opacity: 0.8;
}

/* Layout */
.content-layout {
  display: grid;
  grid-template-columns: 280px 1fr;
  gap: 24px;
  padding: 24px;
}

/* Sidebar */
.sidebar {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.sidebar-card {
  background: white;
  border-radius: 12px;
  padding: 20px;
}

.sidebar-card h3 {
  font-size: 14px;
  font-weight: 500;
  color: #5f6368;
  text-transform: uppercase;
  margin: 0 0 16px;
}

.info-item {
  margin-bottom: 16px;
}

.info-item:last-child {
  margin-bottom: 0;
}

.info-item .label {
  display: block;
  font-size: 12px;
  color: #5f6368;
  margin-bottom: 4px;
}

.info-item .value {
  font-size: 14px;
  color: #202124;
}

.action-btn {
  display: flex;
  align-items: center;
  gap: 12px;
  width: 100%;
  padding: 12px 16px;
  border: none;
  background: transparent;
  border-radius: 8px;
  font-size: 14px;
  cursor: pointer;
  color: #5f6368;
}

.action-btn:hover {
  background: #f1f3f4;
}

.action-btn.danger {
  color: #c5221f;
}

.action-btn.danger:hover {
  background: #fce8e6;
}

/* Main Area */
.main-area {
  background: white;
  border-radius: 12px;
  overflow: hidden;
}

.tabs {
  display: flex;
  border-bottom: 1px solid #e0e0e0;
}

.tab {
  padding: 16px 24px;
  border: none;
  background: transparent;
  font-size: 14px;
  font-weight: 500;
  color: #5f6368;
  cursor: pointer;
  position: relative;
}

.tab:hover {
  color: #1a73e8;
}

.tab.active {
  color: #1a73e8;
}

.tab.active::after {
  content: '';
  position: absolute;
  bottom: 0;
  left: 0;
  right: 0;
  height: 3px;
  background: #1a73e8;
  border-radius: 3px 3px 0 0;
}

.tab-content {
  padding: 24px;
}

/* Empty State */
.empty-state {
  text-align: center;
  padding: 48px;
}

.empty-state p {
  font-size: 16px;
  color: #202124;
  margin: 16px 0 8px;
}

.empty-state span {
  font-size: 14px;
  color: #5f6368;
}

/* Assignments List */
.assignments-list {
  display: flex;
  flex-direction: column;
}

.assignment-item {
  display: flex;
  align-items: center;
  gap: 16px;
  padding: 16px;
  border-bottom: 1px solid #e0e0e0;
  cursor: pointer;
  transition: background 0.2s;
}

.assignment-item:last-child {
  border-bottom: none;
}

.assignment-item:hover {
  background: #f8f9fa;
}

.assignment-icon {
  width: 40px;
  height: 40px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  background: #e8f0fe;
  color: #1a73e8;
}

.assignment-icon.submitted {
  background: #e8f0fe;
  color: #1a73e8;
}

.assignment-icon.graded {
  background: #e6f4ea;
  color: #1e8e3e;
}

.assignment-icon.returned {
  background: #f1f3f4;
  color: #5f6368;
}

.assignment-icon.pending {
  background: #fef7e0;
  color: #f9ab00;
}

.assignment-content {
  flex: 1;
}

.assignment-content h4 {
  font-size: 15px;
  font-weight: 500;
  margin: 0 0 4px;
  color: #202124;
}

.assignment-meta {
  display: flex;
  gap: 16px;
  font-size: 13px;
}

.due-date {
  color: #5f6368;
}

.due-date.urgent {
  color: #c5221f;
  font-weight: 500;
}

.due-date.soon {
  color: #f9ab00;
}

.due-date.overdue {
  color: #c5221f;
}

.points {
  color: #5f6368;
}

.assignment-status {
  display: flex;
  flex-direction: column;
  align-items: flex-end;
  gap: 4px;
}

.status-badge {
  padding: 4px 10px;
  border-radius: 12px;
  font-size: 12px;
  font-weight: 500;
}

.status-badge.draft {
  background: #fef7e0;
  color: #f9ab00;
}

.status-badge.submitted {
  background: #e8f0fe;
  color: #1a73e8;
}

.status-badge.graded {
  background: #e6f4ea;
  color: #1e8e3e;
}

.status-badge.returned {
  background: #f1f3f4;
  color: #5f6368;
}

.status-badge.not-started {
  background: #f1f3f4;
  color: #5f6368;
}

.grade {
  font-size: 14px;
  font-weight: 500;
  color: #1e8e3e;
}

.chevron {
  flex-shrink: 0;
}

/* Members List */
.members-list {
  display: flex;
  flex-direction: column;
  gap: 24px;
}

.member-section h4 {
  font-size: 14px;
  font-weight: 500;
  color: #5f6368;
  margin: 0 0 12px;
}

.member-item {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 8px 0;
}

.avatar {
  width: 36px;
  height: 36px;
  border-radius: 50%;
  background: #1a73e8;
  color: white;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 14px;
  font-weight: 500;
}

.teacher-avatar {
  background: #e91e63;
}

.name {
  font-size: 14px;
  color: #202124;
}

.member-item.teacher .name {
  font-weight: 500;
}

@media (max-width: 900px) {
  .content-layout {
    grid-template-columns: 1fr;
  }
  
  .sidebar {
    display: none;
  }
}
</style>
