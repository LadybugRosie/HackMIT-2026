<template>
  <div class="class-detail-page">
    <!-- Header -->
    <header class="page-header" :style="{ background: currentClass?.color || '#1a73e8' }">
      <div class="header-content">
        <router-link to="/teacher/classes" class="back-btn">
          <svg width="24" height="24" viewBox="0 0 24 24" fill="white">
            <path d="M20 11H7.83l5.59-5.59L12 4l-8 8 8 8 1.41-1.41L7.83 13H20v-2z"/>
          </svg>
        </router-link>
        <div class="class-info">
          <h1>{{ currentClass?.name }}</h1>
          <p v-if="currentClass?.section">{{ currentClass?.section }}</p>
        </div>
        <div class="class-code-badge">
          <span>Class Code:</span>
          <code>{{ currentClass?.class_code }}</code>
          <button @click="copyCode" class="copy-btn">
            <svg width="16" height="16" viewBox="0 0 24 24" fill="white">
              <path d="M16 1H4c-1.1 0-2 .9-2 2v14h2V3h12V1zm3 4H8c-1.1 0-2 .9-2 2v14c0 1.1.9 2 2 2h11c1.1 0 2-.9 2-2V7c0-1.1-.9-2-2-2zm0 16H8V7h11v14z"/>
            </svg>
          </button>
        </div>
      </div>
    </header>

    <!-- Tabs -->
    <nav class="tabs-nav">
      <button :class="['tab', activeTab === 'stream' && 'active']" @click="activeTab = 'stream'">
        Stream
      </button>
      <button :class="['tab', activeTab === 'assignments' && 'active']" @click="activeTab = 'assignments'">
        Assignments
      </button>
      <button :class="['tab', activeTab === 'students' && 'active']" @click="activeTab = 'students'">
        Students
      </button>
      <button :class="['tab', activeTab === 'settings' && 'active']" @click="activeTab = 'settings'">
        Settings
      </button>
    </nav>

    <!-- Content -->
    <main class="page-content">
      <!-- Stream Tab -->
      <div v-if="activeTab === 'stream'" class="stream-tab">
        <div class="stream-banner" :style="{ background: currentClass?.color || '#1a73e8' }">
          <h2>{{ currentClass?.subject }}</h2>
          <p>{{ currentClass?.description || 'No description' }}</p>
        </div>
        
        <div class="stream-content">
          <div class="quick-actions">
            <button class="action-card" @click="createAssignment">
              <svg width="24" height="24" viewBox="0 0 24 24" fill="currentColor">
                <path d="M19 3H5c-1.1 0-2 .9-2 2v14c0 1.1.9 2 2 2h14c1.1 0 2-.9 2-2V5c0-1.1-.9-2-2-2zm-5 14H7v-2h7v2zm3-4H7v-2h10v2zm0-4H7V7h10v2z"/>
              </svg>
              <span>Create Assignment</span>
            </button>
          </div>
          
          <div class="recent-activity">
            <h3>Recent Activity</h3>
            <div v-if="assignments.length > 0">
              <div v-for="assignment in assignments.slice(0, 5)" :key="assignment.assignment_id" class="activity-item">
                <div class="activity-icon">
                  <svg width="20" height="20" viewBox="0 0 24 24" fill="currentColor">
                    <path d="M19 3H5c-1.1 0-2 .9-2 2v14c0 1.1.9 2 2 2h14c1.1 0 2-.9 2-2V5c0-1.1-.9-2-2-2z"/>
                  </svg>
                </div>
                <div class="activity-content">
                  <span class="activity-title">{{ assignment.title }}</span>
                  <span class="activity-date">Due {{ formatDate(assignment.due_date) }}</span>
                </div>
                <router-link :to="`/teacher/assignment/${assignment.assignment_id}`" class="view-link">
                  View
                </router-link>
              </div>
            </div>
            <p v-else class="no-activity">No assignments yet</p>
          </div>
        </div>
      </div>

      <!-- Assignments Tab -->
      <div v-if="activeTab === 'assignments'" class="assignments-tab">
        <div class="tab-header">
          <h2>Assignments</h2>
          <button class="create-btn" @click="createAssignment">
            <svg width="20" height="20" viewBox="0 0 24 24" fill="currentColor">
              <path d="M19 13h-6v6h-2v-6H5v-2h6V5h2v6h6v2z"/>
            </svg>
            Create
          </button>
        </div>
        
        <div v-if="assignments.length > 0" class="assignments-list">
          <div v-for="assignment in assignments" :key="assignment.assignment_id" class="assignment-card">
            <div class="assignment-icon">
              <svg width="24" height="24" viewBox="0 0 24 24" fill="currentColor">
                <path d="M19 3H5c-1.1 0-2 .9-2 2v14c0 1.1.9 2 2 2h14c1.1 0 2-.9 2-2V5c0-1.1-.9-2-2-2zm-5 14H7v-2h7v2zm3-4H7v-2h10v2zm0-4H7V7h10v2z"/>
              </svg>
            </div>
            <div class="assignment-info">
              <h4>{{ assignment.title }}</h4>
              <p>Due {{ formatDate(assignment.due_date) }} • {{ assignment.points }} points</p>
            </div>
            <div class="assignment-stats">
              <span class="stat">{{ assignment.submission_count || 0 }} submitted</span>
              <span class="stat">{{ assignment.graded_count || 0 }} graded</span>
            </div>
            <div class="assignment-status">
              <span v-if="assignment.published" class="badge published">Published</span>
              <span v-else class="badge draft">Draft</span>
            </div>
            <router-link :to="`/teacher/assignment/${assignment.assignment_id}`" class="view-btn">
              View
            </router-link>
          </div>
        </div>
        
        <div v-else class="empty-state">
          <svg width="64" height="64" viewBox="0 0 24 24" fill="#dadce0">
            <path d="M19 3H5c-1.1 0-2 .9-2 2v14c0 1.1.9 2 2 2h14c1.1 0 2-.9 2-2V5c0-1.1-.9-2-2-2z"/>
          </svg>
          <h3>No assignments yet</h3>
          <p>Create your first assignment for this class</p>
          <button class="create-btn primary" @click="createAssignment">Create Assignment</button>
        </div>
      </div>

      <!-- Students Tab -->
      <div v-if="activeTab === 'students'" class="students-tab">
        <div class="tab-header">
          <h2>Students ({{ students.length }})</h2>
          <div class="invite-section">
            <span>Invite students with code:</span>
            <code>{{ currentClass?.class_code }}</code>
          </div>
        </div>
        
        <div v-if="students.length > 0" class="students-list">
          <div v-for="student in students" :key="student.user_id" class="student-row">
            <div class="student-avatar">
              {{ student.name?.[0]?.toUpperCase() || 'S' }}
            </div>
            <div class="student-info">
              <span class="student-name">{{ student.name }}</span>
              <span class="student-email">{{ student.email }}</span>
            </div>
            <span class="student-joined">Joined {{ formatDate(student.joined_at) }}</span>
            <button class="remove-btn" @click="removeStudent(student)">
              <svg width="20" height="20" viewBox="0 0 24 24" fill="currentColor">
                <path d="M6 19c0 1.1.9 2 2 2h8c1.1 0 2-.9 2-2V7H6v12zM19 4h-3.5l-1-1h-5l-1 1H5v2h14V4z"/>
              </svg>
            </button>
          </div>
        </div>
        
        <div v-else class="empty-state">
          <svg width="64" height="64" viewBox="0 0 24 24" fill="#dadce0">
            <path d="M16 11c1.66 0 2.99-1.34 2.99-3S17.66 5 16 5c-1.66 0-3 1.34-3 3s1.34 3 3 3zm-8 0c1.66 0 2.99-1.34 2.99-3S9.66 5 8 5C6.34 5 5 6.34 5 8s1.34 3 3 3z"/>
          </svg>
          <h3>No students yet</h3>
          <p>Share the class code <code>{{ currentClass?.class_code }}</code> with your students</p>
        </div>
      </div>

      <!-- Settings Tab -->
      <div v-if="activeTab === 'settings'" class="settings-tab">
        <div class="settings-section">
          <h3>Class Details</h3>
          <div class="form-group">
            <label>Class Name</label>
            <input v-model="editForm.name" type="text" />
          </div>
          <div class="form-group">
            <label>Subject</label>
            <input v-model="editForm.subject" type="text" />
          </div>
          <div class="form-group">
            <label>Section</label>
            <input v-model="editForm.section" type="text" />
          </div>
          <div class="form-group">
            <label>Description</label>
            <textarea v-model="editForm.description" rows="3"></textarea>
          </div>
          <button class="save-btn" @click="saveSettings">Save Changes</button>
        </div>
        
        <div class="settings-section danger">
          <h3>Danger Zone</h3>
          <p>Archive this class to hide it from the active list.</p>
          <button class="archive-btn" @click="handleArchive">Archive Class</button>
        </div>
      </div>
    </main>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, watch } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { useClasses, useAssignments } from '@/composables/classroom'

const props = defineProps(['id'])
const router = useRouter()
const route = useRoute()

// Route passes 'id' from /teacher/class/:id
const classId = computed(() => props.id || route.params.id)

const { currentClass, fetchClass, updateClass, getClassMembers, removeStudent: doRemove, archiveClass } = useClasses()
const { assignments: _allAssignments, fetchAssignments } = useAssignments()

// Filter to only this class's assignments — prevents cross-class state bleed
const assignments = computed(() =>
  _allAssignments.value.filter(a => a.class_id === classId.value)
)

const activeTab = ref('stream')
const students = ref([])
const editForm = ref({ name: '', subject: '', section: '', description: '' })

// Watch for class changes to update form
watch(currentClass, (cls) => {
  if (cls) {
    editForm.value = {
      name: cls.name,
      subject: cls.subject,
      section: cls.section || '',
      description: cls.description || ''
    }
  }
})

function formatDate(dateStr) {
  if (!dateStr) return ''
  const date = new Date(dateStr)
  return date.toLocaleDateString('en-US', { month: 'short', day: 'numeric' })
}

function copyCode() {
  navigator.clipboard.writeText(currentClass.value?.class_code)
  alert('Class code copied!')
}

function createAssignment() {
  router.push(`/teacher/class/${classId.value}/assignment/new`)
}

async function loadStudents() {
  const result = await getClassMembers(classId.value, 'student')
  if (result.success) {
    students.value = result.data.members
  }
}

async function removeStudent(student) {
  if (!confirm(`Remove ${student.name} from this class?`)) return
  await doRemove(classId.value, student.user_id)
  await loadStudents()
}

async function saveSettings() {
  const result = await updateClass(classId.value, editForm.value)
  if (result.success) {
    alert('Settings saved!')
  }
}

async function handleArchive() {
  if (!confirm('Archive this class? Students will no longer see it.')) return
  await archiveClass(classId.value)
  router.push('/teacher/classes')
}

onMounted(async () => {
  await Promise.all([
    fetchClass(classId.value),
    fetchAssignments(classId.value),
    loadStudents()
  ])
})
</script>

<style scoped>
.class-detail-page {
  min-height: 100vh;
  background: #f8f9fa;
}

.page-header {
  padding: 20px 24px;
  color: white;
}

.header-content {
  max-width: 1200px;
  margin: 0 auto;
  display: flex;
  align-items: center;
  gap: 20px;
}

.back-btn {
  width: 40px;
  height: 40px;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: 50%;
  text-decoration: none;
}

.back-btn:hover {
  background: rgba(255,255,255,0.1);
}

.class-info {
  flex: 1;
}

.class-info h1 {
  font-size: 24px;
  font-weight: 400;
  margin: 0;
}

.class-info p {
  font-size: 14px;
  opacity: 0.9;
  margin: 4px 0 0;
}

.class-code-badge {
  display: flex;
  align-items: center;
  gap: 8px;
  background: rgba(255,255,255,0.2);
  padding: 8px 16px;
  border-radius: 20px;
  font-size: 14px;
}

.class-code-badge code {
  font-weight: 600;
}

.copy-btn {
  width: 28px;
  height: 28px;
  border: none;
  background: transparent;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: 50%;
}

.copy-btn:hover {
  background: rgba(255,255,255,0.2);
}

/* Tabs */
.tabs-nav {
  background: white;
  border-bottom: 1px solid #e0e0e0;
  display: flex;
  justify-content: center;
  gap: 8px;
  padding: 0 24px;
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
}

/* Content */
.page-content {
  max-width: 1200px;
  margin: 0 auto;
  padding: 24px;
}

/* Stream Tab */
.stream-banner {
  padding: 40px;
  border-radius: 12px;
  color: white;
  margin-bottom: 24px;
}

.stream-banner h2 {
  font-size: 32px;
  font-weight: 400;
  margin: 0 0 8px;
}

.stream-banner p {
  font-size: 16px;
  opacity: 0.9;
  margin: 0;
}

.quick-actions {
  margin-bottom: 24px;
}

.action-card {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 16px 24px;
  background: white;
  border: 1px solid #e0e0e0;
  border-radius: 8px;
  font-size: 14px;
  font-weight: 500;
  color: #1a73e8;
  cursor: pointer;
}

.action-card:hover {
  background: #f8f9fa;
}

.recent-activity {
  background: white;
  border-radius: 12px;
  padding: 20px;
}

.recent-activity h3 {
  font-size: 16px;
  font-weight: 500;
  margin: 0 0 16px;
  color: #202124;
}

.activity-item {
  display: flex;
  align-items: center;
  gap: 16px;
  padding: 12px 0;
  border-bottom: 1px solid #f1f3f4;
}

.activity-icon {
  width: 40px;
  height: 40px;
  background: #e8f0fe;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  color: #1a73e8;
}

.activity-content {
  flex: 1;
  display: flex;
  flex-direction: column;
}

.activity-title {
  font-weight: 500;
  color: #202124;
}

.activity-date {
  font-size: 13px;
  color: #5f6368;
}

.view-link {
  color: #1a73e8;
  text-decoration: none;
  font-weight: 500;
  font-size: 14px;
}

.no-activity {
  color: #5f6368;
  text-align: center;
  padding: 20px;
}

/* Assignments Tab */
.tab-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 24px;
}

.tab-header h2 {
  font-size: 20px;
  font-weight: 500;
  margin: 0;
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
}

.create-btn:hover {
  background: #1557b0;
}

.assignments-list {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.assignment-card {
  display: flex;
  align-items: center;
  gap: 16px;
  padding: 16px 20px;
  background: white;
  border-radius: 8px;
  box-shadow: 0 1px 3px rgba(0,0,0,0.1);
}

.assignment-icon {
  width: 48px;
  height: 48px;
  background: #e8f0fe;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  color: #1a73e8;
}

.assignment-info {
  flex: 1;
}

.assignment-info h4 {
  margin: 0 0 4px;
  font-size: 15px;
  font-weight: 500;
}

.assignment-info p {
  margin: 0;
  font-size: 13px;
  color: #5f6368;
}

.assignment-stats {
  display: flex;
  gap: 16px;
}

.assignment-stats .stat {
  font-size: 13px;
  color: #5f6368;
}

.badge {
  padding: 4px 12px;
  border-radius: 12px;
  font-size: 12px;
  font-weight: 500;
}

.badge.published {
  background: #e6f4ea;
  color: #137333;
}

.badge.draft {
  background: #fef7e0;
  color: #b06000;
}

.view-btn {
  padding: 8px 16px;
  background: transparent;
  border: 1px solid #dadce0;
  border-radius: 20px;
  color: #1a73e8;
  font-size: 14px;
  font-weight: 500;
  text-decoration: none;
}

.view-btn:hover {
  background: #f8f9fa;
}

/* Students Tab */
.invite-section {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 14px;
  color: #5f6368;
}

.invite-section code {
  background: #e8f0fe;
  padding: 4px 12px;
  border-radius: 4px;
  color: #1a73e8;
  font-weight: 500;
}

.students-list {
  background: white;
  border-radius: 8px;
  overflow: hidden;
}

.student-row {
  display: flex;
  align-items: center;
  gap: 16px;
  padding: 16px 20px;
  border-bottom: 1px solid #f1f3f4;
}

.student-avatar {
  width: 40px;
  height: 40px;
  background: #1a73e8;
  color: white;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  font-weight: 500;
}

.student-info {
  flex: 1;
  display: flex;
  flex-direction: column;
}

.student-name {
  font-weight: 500;
  color: #202124;
}

.student-email {
  font-size: 13px;
  color: #5f6368;
}

.student-joined {
  font-size: 13px;
  color: #5f6368;
}

.remove-btn {
  width: 36px;
  height: 36px;
  border: none;
  background: transparent;
  cursor: pointer;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  color: #5f6368;
}

.remove-btn:hover {
  background: #fce8e6;
  color: #c5221f;
}

/* Settings Tab */
.settings-section {
  background: white;
  border-radius: 12px;
  padding: 24px;
  margin-bottom: 24px;
}

.settings-section h3 {
  font-size: 18px;
  font-weight: 500;
  margin: 0 0 20px;
}

.form-group {
  margin-bottom: 20px;
}

.form-group label {
  display: block;
  font-size: 14px;
  font-weight: 500;
  margin-bottom: 8px;
  color: #202124;
}

.form-group input,
.form-group textarea {
  width: 100%;
  padding: 12px;
  border: 1px solid #dadce0;
  border-radius: 8px;
  font-size: 14px;
  box-sizing: border-box;
}

.save-btn {
  padding: 10px 24px;
  background: #1a73e8;
  color: white;
  border: none;
  border-radius: 8px;
  font-weight: 500;
  cursor: pointer;
}

.settings-section.danger {
  border: 1px solid #fce8e6;
}

.settings-section.danger h3 {
  color: #c5221f;
}

.archive-btn {
  padding: 10px 24px;
  background: #c5221f;
  color: white;
  border: none;
  border-radius: 8px;
  font-weight: 500;
  cursor: pointer;
}

/* Empty State */
.empty-state {
  text-align: center;
  padding: 60px 20px;
}

.empty-state h3 {
  margin: 16px 0 8px;
  color: #202124;
}

.empty-state p {
  color: #5f6368;
  margin: 0 0 24px;
}

.empty-state code {
  background: #e8f0fe;
  padding: 4px 12px;
  border-radius: 4px;
  color: #1a73e8;
}

.create-btn.primary {
  display: inline-flex;
}
</style>
