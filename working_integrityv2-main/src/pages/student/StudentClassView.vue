<template>
  <div class="student-class-view">
    <!-- Header -->
    <header class="class-header" :style="{ '--class-color': classColor }">
      <div class="header-content">
        <button @click="goBack" class="back-btn">
          <svg width="24" height="24" viewBox="0 0 24 24" fill="currentColor">
            <path d="M20 11H7.83l5.59-5.59L12 4l-8 8 8 8 1.41-1.41L7.83 13H20v-2z"/>
          </svg>
        </button>
        <div class="class-info">
          <h1>{{ classData?.name || 'Loading...' }}</h1>
          <span class="section">{{ classData?.section }}</span>
        </div>
      </div>
      <div class="class-meta">
        <span class="subject">{{ classData?.subject }}</span>
        <span class="teacher">{{ classData?.teacher_name }}</span>
      </div>
    </header>

    <!-- Tabs -->
    <nav class="tabs-nav">
      <button 
        :class="['tab', { active: activeTab === 'stream' }]"
        @click="activeTab = 'stream'"
      >
        Stream
      </button>
      <button 
        :class="['tab', { active: activeTab === 'assignments' }]"
        @click="activeTab = 'assignments'"
      >
        Assignments
        <span v-if="pendingCount > 0" class="tab-badge">{{ pendingCount }}</span>
      </button>
      <button 
        :class="['tab', { active: activeTab === 'grades' }]"
        @click="activeTab = 'grades'"
      >
        Grades
      </button>
    </nav>

    <!-- Content -->
    <main class="page-content">
      <!-- Stylometry Enrollment Banner -->
      <div v-if="!styloEnrolled && styloChecked" class="enrollment-banner" @click="goToEnrollment">
        <div class="banner-icon">
          <svg width="32" height="32" viewBox="0 0 24 24" fill="white">
            <path d="M12 1L3 5v6c0 5.55 3.84 10.74 9 12 5.16-1.26 9-6.45 9-12V5l-9-4z"/>
          </svg>
        </div>
        <div class="banner-content">
          <strong>Writing Profile Assessment Required</strong>
          <p>Complete your writing profile before accessing assignments. This is a one-time setup for this course.</p>
        </div>
        <svg width="24" height="24" viewBox="0 0 24 24" fill="white" class="banner-arrow">
          <path d="M10 6L8.59 7.41 13.17 12l-4.58 4.59L10 18l6-6z"/>
        </svg>
      </div>

      <!-- Stream Tab -->
      <div v-if="activeTab === 'stream'" class="tab-content">
        <div class="class-description" v-if="classData?.description">
          <p>{{ classData.description }}</p>
        </div>

        <div class="announcements-section">
          <h3>Recent Activity</h3>
          <div v-if="recentAssignments.length === 0" class="empty-state">
            <p>No recent activity</p>
          </div>
          <div v-else class="activity-list">
            <div 
              v-for="assignment in recentAssignments" 
              :key="assignment.assignment_id"
              class="activity-card"
              @click="goToAssignment(assignment)"
            >
              <div class="activity-icon">
                <svg width="24" height="24" viewBox="0 0 24 24" fill="currentColor">
                  <path d="M14 2H6c-1.1 0-1.99.9-1.99 2L4 20c0 1.1.89 2 1.99 2H18c1.1 0 2-.9 2-2V8l-6-6zm2 16H8v-2h8v2zm0-4H8v-2h8v2zm-3-5V3.5L18.5 9H13z"/>
                </svg>
              </div>
              <div class="activity-info">
                <span class="activity-type">New Assignment</span>
                <span class="activity-title">{{ assignment.title }}</span>
                <span class="activity-date">Due {{ formatDate(assignment.due_date) }}</span>
              </div>
              <div class="activity-status">
                <span v-if="assignment.grade !== null && assignment.grade !== undefined" class="status-badge graded">
                  {{ assignment.grade }}/{{ assignment.points }}
                </span>
                <span v-else-if="assignment.submitted || assignment.status === 'submitted'" class="status-badge submitted">Submitted</span>
                <span v-else-if="assignment.status === 'draft'" class="status-badge draft">In Progress</span>
                <span v-else-if="isPastDue(assignment.due_date)" class="status-badge late">Past Due</span>
                <span v-else class="status-badge pending">Pending</span>
              </div>
            </div>
          </div>
        </div>
      </div>

      <!-- Assignments Tab -->
      <div v-if="activeTab === 'assignments'" class="tab-content">
        <div class="filter-bar">
          <button 
            :class="['filter-btn', { active: filter === 'all' }]"
            @click="filter = 'all'"
          >
            All
          </button>
          <button 
            :class="['filter-btn', { active: filter === 'pending' }]"
            @click="filter = 'pending'"
          >
            Pending
          </button>
          <button 
            :class="['filter-btn', { active: filter === 'submitted' }]"
            @click="filter = 'submitted'"
          >
            Submitted
          </button>
          <button 
            :class="['filter-btn', { active: filter === 'graded' }]"
            @click="filter = 'graded'"
          >
            Graded
          </button>
        </div>

        <div v-if="filteredAssignments.length === 0" class="empty-state">
          <svg width="80" height="80" viewBox="0 0 24 24" fill="#dadce0">
            <path d="M14 2H6c-1.1 0-1.99.9-1.99 2L4 20c0 1.1.89 2 1.99 2H18c1.1 0 2-.9 2-2V8l-6-6zM6 20V4h7v5h5v11H6z"/>
          </svg>
          <p>No assignments found</p>
        </div>

        <div v-else class="assignments-list">
          <div 
            v-for="assignment in filteredAssignments" 
            :key="assignment.assignment_id"
            class="assignment-card"
            @click="goToAssignment(assignment)"
          >
            <div class="assignment-main">
              <div class="assignment-icon" :style="{ background: classColor }">
                <svg width="24" height="24" viewBox="0 0 24 24" fill="white">
                  <path d="M14 2H6c-1.1 0-1.99.9-1.99 2L4 20c0 1.1.89 2 1.99 2H18c1.1 0 2-.9 2-2V8l-6-6zm2 16H8v-2h8v2zm0-4H8v-2h8v2zm-3-5V3.5L18.5 9H13z"/>
                </svg>
              </div>
              <div class="assignment-info">
                <h4>{{ assignment.title }}</h4>
                <div class="assignment-meta">
                  <span class="due-date" :class="{ urgent: isUrgent(assignment.due_date), past: isPastDue(assignment.due_date) }">
                    {{ isPastDue(assignment.due_date) ? 'Past due' : 'Due' }} {{ formatDate(assignment.due_date) }}
                  </span>
                  <span class="points">{{ assignment.points }} pts</span>
                </div>
              </div>
            </div>
            <div class="assignment-status">
              <span v-if="assignment.grade !== null && assignment.grade !== undefined" class="grade">
                {{ assignment.grade }}/{{ assignment.points }}
              </span>
              <span v-else-if="assignment.status === 'returned'" class="status-badge graded">Graded</span>
              <span v-else-if="assignment.submitted || assignment.status === 'submitted' || assignment.status === 'graded'" class="status-badge submitted">
                {{ assignment.status === 'graded' ? 'Grading Done' : 'Submitted' }}
              </span>
              <span v-else-if="assignment.status === 'draft'" class="status-badge draft">Draft</span>
              <span v-else-if="isPastDue(assignment.due_date)" class="status-badge late">Missing</span>
              <span v-else class="status-badge pending">Not Started</span>
            </div>
          </div>
        </div>
      </div>

      <!-- Grades Tab -->
      <div v-if="activeTab === 'grades'" class="tab-content">
        <div class="grades-overview">
          <div class="overall-grade">
            <span class="grade-label">Cumulative Grade</span>
            <span class="grade-value" :class="overallGrade !== '-' ? getGradeClass(earnedPoints, totalPoints) : ''">{{ overallGrade }}%</span>
          </div>
          <div class="grade-breakdown">
            <div class="breakdown-item">
              <span class="breakdown-label">Graded</span>
              <span class="breakdown-value">{{ gradedCount }}/{{ totalCount }}</span>
            </div>
            <div class="breakdown-item">
              <span class="breakdown-label">Points Earned</span>
              <span class="breakdown-value">{{ earnedPoints }}/{{ totalPoints }}</span>
            </div>
            <div class="breakdown-item">
              <span class="breakdown-label">Pending</span>
              <span class="breakdown-value">{{ pendingGradeCount }}</span>
            </div>
          </div>
        </div>

        <!-- Grade Progress Bar -->
        <div class="grade-progress-card" v-if="gradedCount > 0">
          <div class="grade-progress-bar">
            <div 
              class="grade-progress-fill" 
              :style="{ width: overallGrade + '%' }"
              :class="overallGrade !== '-' ? getGradeClass(earnedPoints, totalPoints) : ''"
            ></div>
          </div>
          <div class="grade-legend">
            <span>0%</span>
            <span>{{ overallGrade }}% earned</span>
            <span>100%</span>
          </div>
        </div>

        <!-- No grades yet message -->
        <div v-if="gradedAssignments.length === 0" class="empty-state">
          <svg width="80" height="80" viewBox="0 0 24 24" fill="#dadce0">
            <path d="M19 3H5c-1.1 0-2 .9-2 2v14c0 1.1.9 2 2 2h14c1.1 0 2-.9 2-2V5c0-1.1-.9-2-2-2zM9 17H7v-7h2v7zm4 0h-2V7h2v10zm4 0h-2v-4h2v4z"/>
          </svg>
          <p>No grades yet. Complete and submit assignments to see your grades here.</p>
        </div>

        <div v-else class="grades-list">
          <div 
            v-for="assignment in gradedAssignments" 
            :key="assignment.assignment_id"
            class="grade-item"
            @click="goToAssignment(assignment)"
          >
            <div class="grade-info">
              <span class="assignment-title">{{ assignment.title }}</span>
              <span class="graded-date">Graded {{ formatDate(assignment.graded_at) }}</span>
            </div>
            <div class="grade-score">
              <span class="score">{{ assignment.grade }}/{{ assignment.points }}</span>
              <span class="percentage" :class="getGradeClass(assignment.grade, assignment.points)">
                {{ Math.round((assignment.grade / assignment.points) * 100) }}%
              </span>
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
import { useClasses, useAssignments, useStylometryV3 } from '@/composables/classroom'

const router = useRouter()
const route = useRoute()
const classId = route.params.id

const { fetchClass, currentClass: classData } = useClasses()
const { fetchAssignments, assignments } = useAssignments()
const { getCourseEnrollmentStatus } = useStylometryV3()

const activeTab = ref('assignments')
const filter = ref('all')
const styloEnrolled = ref(false)
const styloChecked = ref(false)

const classColors = ['#1a73e8', '#0d652d', '#c5221f', '#8430ce', '#e37400', '#137333', '#185abc', '#9334e6']

const classColor = computed(() => {
  if (!classId) return classColors[0]
  return classColors[classId.charCodeAt(0) % classColors.length]
})

const classAssignments = computed(() => {
  return assignments.value.filter(a => a.class_id === classId && a.type !== 'stylometry_enrollment')
})

const recentAssignments = computed(() => {
  return [...classAssignments.value]
    .sort((a, b) => new Date(b.created_at) - new Date(a.created_at))
    .slice(0, 5)
})

const filteredAssignments = computed(() => {
  let result = classAssignments.value
  
  switch (filter.value) {
    case 'pending':
      // Not yet submitted: no status, or status is draft, or status is null
      result = result.filter(a => !a.submitted && a.status !== 'submitted' && a.status !== 'graded' && a.status !== 'returned')
      break
    case 'submitted':
      // Submitted but not yet graded/returned to student
      result = result.filter(a => {
        const status = a.status
        return (status === 'submitted' || status === 'graded') && (a.grade === null || a.grade === undefined)
      })
      break
    case 'graded':
      // Has a grade (returned or graded with grade value)
      result = result.filter(a => a.grade !== null && a.grade !== undefined)
      break
  }
  
  return result.sort((a, b) => new Date(a.due_date) - new Date(b.due_date))
})

const gradedAssignments = computed(() => {
  return classAssignments.value
    .filter(a => a.grade !== null)
    .sort((a, b) => new Date(b.graded_at) - new Date(a.graded_at))
})

const pendingCount = computed(() => {
  return classAssignments.value.filter(a => !a.submitted && !isPastDue(a.due_date)).length
})

const pendingGradeCount = computed(() => {
  return classAssignments.value.filter(a => a.submitted && (a.grade === null || a.grade === undefined)).length
})

const gradedCount = computed(() => gradedAssignments.value.length)
const totalCount = computed(() => classAssignments.value.length)

const earnedPoints = computed(() => {
  return gradedAssignments.value.reduce((sum, a) => sum + (a.grade || 0), 0)
})

const totalPoints = computed(() => {
  return gradedAssignments.value.reduce((sum, a) => sum + a.points, 0)
})

const overallGrade = computed(() => {
  if (totalPoints.value === 0) return '-'
  return Math.round((earnedPoints.value / totalPoints.value) * 100)
})

function isPastDue(dueDate) {
  return new Date(dueDate) < new Date()
}

function isUrgent(dueDate) {
  const hours = (new Date(dueDate) - new Date()) / (1000 * 60 * 60)
  return hours > 0 && hours < 24
}

function formatDate(date) {
  if (!date) return '-'
  const d = new Date(date)
  const now = new Date()
  const diff = d - now
  const days = Math.floor(diff / (1000 * 60 * 60 * 24))
  
  if (days === 0) {
    return d.toLocaleTimeString('en-US', { hour: 'numeric', minute: '2-digit' })
  } else if (days === 1) {
    return 'Tomorrow'
  } else if (days < 7 && days > 0) {
    return d.toLocaleDateString('en-US', { weekday: 'long' })
  }
  return d.toLocaleDateString('en-US', { month: 'short', day: 'numeric' })
}

function getGradeClass(grade, maxPoints) {
  const percent = (grade / maxPoints) * 100
  if (percent >= 90) return 'excellent'
  if (percent >= 80) return 'good'
  if (percent >= 70) return 'average'
  return 'poor'
}

function goBack() {
  router.push('/student/dashboard')
}

function goToAssignment(assignment) {
  router.push(`/student/assignment/${assignment.assignment_id}`)
}

function goToEnrollment() {
  router.push(`/student/stylometry-enrollment/${classId}`)
}

onMounted(async () => {
  await fetchClass(classId)
  await fetchAssignments({ class_id: classId })

  const statusResult = await getCourseEnrollmentStatus(classId)
  if (statusResult.success) {
    styloEnrolled.value = statusResult.data.enrolled === true
  }
  styloChecked.value = true
})
</script>

<style scoped>
.student-class-view {
  min-height: 100vh;
  background: #f8f9fa;
}

.class-header {
  background: var(--class-color);
  padding: 24px;
  color: white;
}

.header-content {
  display: flex;
  align-items: center;
  gap: 16px;
  margin-bottom: 16px;
}

.back-btn {
  width: 40px;
  height: 40px;
  border: none;
  background: rgba(255,255,255,0.2);
  border-radius: 50%;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  color: white;
}

.back-btn:hover {
  background: rgba(255,255,255,0.3);
}

.class-info h1 {
  margin: 0;
  font-size: 28px;
  font-weight: 500;
}

.section {
  opacity: 0.9;
  font-size: 16px;
}

.class-meta {
  display: flex;
  gap: 16px;
  opacity: 0.9;
}

/* Tabs */
.tabs-nav {
  display: flex;
  gap: 8px;
  padding: 0 24px;
  background: white;
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
  display: flex;
  align-items: center;
  gap: 8px;
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

.tab-badge {
  background: #1a73e8;
  color: white;
  padding: 2px 8px;
  border-radius: 12px;
  font-size: 12px;
}

/* Content */
.page-content {
  max-width: 900px;
  margin: 0 auto;
  padding: 24px;
}

.tab-content {
  display: flex;
  flex-direction: column;
  gap: 20px;
}

/* Stream */
.class-description {
  background: white;
  border-radius: 12px;
  padding: 20px;
}

.class-description p {
  margin: 0;
  color: #3c4043;
  line-height: 1.6;
}

.announcements-section h3 {
  margin: 0 0 16px;
  font-size: 16px;
  color: #202124;
}

.activity-list {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.activity-card {
  display: flex;
  align-items: center;
  gap: 16px;
  background: white;
  border-radius: 12px;
  padding: 16px;
  cursor: pointer;
  transition: box-shadow 0.2s;
}

.activity-card:hover {
  box-shadow: 0 2px 8px rgba(0,0,0,0.1);
}

.activity-icon {
  width: 48px;
  height: 48px;
  border-radius: 50%;
  background: #e8f0fe;
  color: #1a73e8;
  display: flex;
  align-items: center;
  justify-content: center;
}

.activity-info {
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.activity-type {
  font-size: 12px;
  color: #5f6368;
}

.activity-title {
  font-weight: 500;
  color: #202124;
}

.activity-date {
  font-size: 13px;
  color: #5f6368;
}

/* Filter Bar */
.filter-bar {
  display: flex;
  gap: 8px;
  margin-bottom: 8px;
}

.filter-btn {
  padding: 8px 16px;
  border: 1px solid #dadce0;
  background: white;
  border-radius: 20px;
  font-size: 14px;
  color: #5f6368;
  cursor: pointer;
}

.filter-btn:hover {
  background: #f8f9fa;
}

.filter-btn.active {
  background: #e8f0fe;
  border-color: #1a73e8;
  color: #1a73e8;
}

/* Assignments List */
.assignments-list {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.assignment-card {
  display: flex;
  justify-content: space-between;
  align-items: center;
  background: white;
  border-radius: 12px;
  padding: 16px 20px;
  cursor: pointer;
  transition: box-shadow 0.2s;
}

.assignment-card:hover {
  box-shadow: 0 2px 8px rgba(0,0,0,0.1);
}

.assignment-main {
  display: flex;
  align-items: center;
  gap: 16px;
}

.assignment-icon {
  width: 48px;
  height: 48px;
  border-radius: 8px;
  display: flex;
  align-items: center;
  justify-content: center;
}

.assignment-info h4 {
  margin: 0 0 4px;
  font-size: 16px;
  color: #202124;
}

.assignment-meta {
  display: flex;
  gap: 16px;
  font-size: 13px;
  color: #5f6368;
}

.due-date.urgent {
  color: #f9ab00;
}

.due-date.past {
  color: #d93025;
}

.assignment-status .grade {
  font-size: 18px;
  font-weight: 600;
  color: #202124;
}

.status-badge {
  padding: 6px 12px;
  border-radius: 16px;
  font-size: 13px;
  font-weight: 500;
}

.status-badge.submitted {
  background: #e6f4ea;
  color: #1e8e3e;
}

.status-badge.pending {
  background: #fef7e0;
  color: #f9ab00;
}

.status-badge.late {
  background: #fce8e6;
  color: #d93025;
}

.status-badge.graded {
  background: #e0f2fe;
  color: #0369a1;
}

.status-badge.draft {
  background: #f3e8ff;
  color: #7c3aed;
}

/* Grades Tab */
.grades-overview {
  background: white;
  border-radius: 12px;
  padding: 24px;
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.overall-grade {
  display: flex;
  flex-direction: column;
}

.grade-label {
  font-size: 14px;
  color: #5f6368;
}

.grade-value {
  font-size: 48px;
  font-weight: 600;
  color: #202124;
}

.grade-breakdown {
  display: flex;
  gap: 40px;
}

.breakdown-item {
  display: flex;
  flex-direction: column;
  text-align: right;
}

.breakdown-label {
  font-size: 13px;
  color: #5f6368;
}

.breakdown-value {
  font-size: 20px;
  font-weight: 500;
  color: #202124;
}

.grades-list {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.grade-item {
  display: flex;
  justify-content: space-between;
  align-items: center;
  background: white;
  border-radius: 12px;
  padding: 16px 20px;
  cursor: pointer;
}

.grade-item:hover {
  box-shadow: 0 2px 8px rgba(0,0,0,0.1);
}

.grade-info {
  display: flex;
  flex-direction: column;
}

.assignment-title {
  font-weight: 500;
  color: #202124;
}

.graded-date {
  font-size: 13px;
  color: #5f6368;
}

.grade-score {
  text-align: right;
}

.score {
  display: block;
  font-size: 18px;
  font-weight: 600;
  color: #202124;
}

.percentage {
  font-size: 14px;
  font-weight: 500;
}

.percentage.excellent {
  color: #1e8e3e;
}

.percentage.good {
  color: #1a73e8;
}

.percentage.average {
  color: #f9ab00;
}

.percentage.poor {
  color: #d93025;
}

/* Grade Progress Card */
.grade-progress-card {
  background: white;
  border-radius: 12px;
  padding: 20px;
}

.grade-progress-bar {
  height: 12px;
  background: #e8eaed;
  border-radius: 6px;
  overflow: hidden;
  margin-bottom: 8px;
}

.grade-progress-fill {
  height: 100%;
  border-radius: 6px;
  transition: width 0.5s ease;
}

.grade-progress-fill.excellent {
  background: linear-gradient(90deg, #34a853, #1e8e3e);
}

.grade-progress-fill.good {
  background: linear-gradient(90deg, #4285f4, #1a73e8);
}

.grade-progress-fill.average {
  background: linear-gradient(90deg, #fbbc04, #f9ab00);
}

.grade-progress-fill.poor {
  background: linear-gradient(90deg, #ea4335, #d93025);
}

.grade-legend {
  display: flex;
  justify-content: space-between;
  font-size: 12px;
  color: #5f6368;
}

/* Empty State */
.empty-state {
  text-align: center;
  padding: 60px 20px;
  background: white;
  border-radius: 12px;
}

.empty-state p {
  color: #5f6368;
  margin: 16px 0 0;
}

/* Enrollment Banner */
.enrollment-banner {
  display: flex;
  align-items: center;
  gap: 16px;
  padding: 20px 24px;
  background: linear-gradient(135deg, #1a73e8, #1557b0);
  border-radius: 12px;
  cursor: pointer;
  margin-bottom: 20px;
  transition: transform 0.2s, box-shadow 0.2s;
  color: white;
}

.enrollment-banner:hover {
  transform: translateY(-2px);
  box-shadow: 0 4px 16px rgba(26, 115, 232, 0.3);
}

.banner-icon {
  width: 56px;
  height: 56px;
  border-radius: 12px;
  background: rgba(255,255,255,0.2);
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}

.banner-content {
  flex: 1;
}

.banner-content strong {
  font-size: 16px;
  display: block;
  margin-bottom: 4px;
}

.banner-content p {
  margin: 0;
  font-size: 14px;
  opacity: 0.9;
}

.banner-arrow {
  flex-shrink: 0;
  opacity: 0.8;
}
</style>
