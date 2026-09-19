<template>
  <div class="class-list-page">
    <!-- Header -->
    <header class="page-header">
      <div class="header-left">
        <router-link to="/teacher/dashboard" class="back-btn">
          <svg width="24" height="24" viewBox="0 0 24 24" fill="currentColor">
            <path d="M20 11H7.83l5.59-5.59L12 4l-8 8 8 8 1.41-1.41L7.83 13H20v-2z"/>
          </svg>
        </router-link>
        <h1>My Classes</h1>
      </div>
      <button class="create-btn" @click="showCreateModal = true">
        <svg width="20" height="20" viewBox="0 0 24 24" fill="currentColor">
          <path d="M19 13h-6v6h-2v-6H5v-2h6V5h2v6h6v2z"/>
        </svg>
        Create Class
      </button>
    </header>

    <!-- Content -->
    <main class="page-content">
      <div v-if="pageLoading" style="text-align:center;padding:60px 20px;color:#5f6368;">Loading classes...</div>
      <template v-else>
      <div class="tabs">
        <button 
          :class="['tab', activeTab === 'active' && 'active']"
          @click="activeTab = 'active'"
        >
          Active ({{ activeClasses.length }})
        </button>
        <button 
          :class="['tab', activeTab === 'archived' && 'active']"
          @click="activeTab = 'archived'"
        >
          Archived ({{ archivedClasses.length }})
        </button>
      </div>

      <div class="classes-grid" v-if="displayedClasses.length > 0">
        <div 
          v-for="cls in displayedClasses" 
          :key="cls.class_id"
          class="class-card"
        >
          <div class="class-header" :style="{ background: cls.color }">
            <div class="class-actions">
              <button class="action-btn" @click.stop="toggleMenu(cls.class_id)">
                <svg width="20" height="20" viewBox="0 0 24 24" fill="white">
                  <path d="M12 8c1.1 0 2-.9 2-2s-.9-2-2-2-2 .9-2 2 .9 2 2 2zm0 2c-1.1 0-2 .9-2 2s.9 2 2 2 2-.9 2-2-.9-2-2-2zm0 6c-1.1 0-2 .9-2 2s.9 2 2 2 2-.9 2-2-.9-2-2-2z"/>
                </svg>
              </button>
              <div v-if="openMenu === cls.class_id" class="menu-dropdown">
                <button @click="editClass(cls)">Edit</button>
                <button @click="archiveClass(cls)" v-if="!cls.archived">Archive</button>
                <button @click="unarchiveClass(cls)" v-else>Unarchive</button>
              </div>
            </div>
            <h3 class="class-name" @click="goToClass(cls)">{{ cls.name }}</h3>
            <p class="class-section" v-if="cls.section">{{ cls.section }}</p>
          </div>
          <div class="class-body" @click="goToClass(cls)">
            <p class="class-subject">{{ cls.subject }}</p>
            <div class="class-code-display">
              <span>Class Code:</span>
              <code>{{ cls.class_code }}</code>
              <button class="copy-btn" @click.stop="copyCode(cls.class_code)">
                <svg width="16" height="16" viewBox="0 0 24 24" fill="currentColor">
                  <path d="M16 1H4c-1.1 0-2 .9-2 2v14h2V3h12V1zm3 4H8c-1.1 0-2 .9-2 2v14c0 1.1.9 2 2 2h11c1.1 0 2-.9 2-2V7c0-1.1-.9-2-2-2zm0 16H8V7h11v14z"/>
                </svg>
              </button>
            </div>
          </div>
          <div class="class-footer" @click="goToClass(cls)">
            <span class="stat">{{ cls.student_count }} students</span>
            <span class="stat">{{ cls.assignment_count }} assignments</span>
          </div>
        </div>
      </div>

      <div class="empty-state" v-else>
        <svg width="80" height="80" viewBox="0 0 24 24" fill="#dadce0">
          <path d="M12 3L1 9l11 6 9-4.91V17h2V9M5 13.18v4L12 21l7-3.82v-4L12 17l-7-3.82z"/>
        </svg>
        <h3>{{ activeTab === 'active' ? 'No active classes' : 'No archived classes' }}</h3>
        <p v-if="activeTab === 'active'">Create your first class to get started</p>
      </div>
      </template>
    </main>

    <!-- Create Modal (reuse from dashboard) -->
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
            <input v-model="newClass.name" type="text" placeholder="e.g., CS 301" required autofocus />
          </div>
          <div class="form-row">
            <div class="form-group">
              <label>Subject *</label>
              <input v-model="newClass.subject" type="text" placeholder="e.g., Computer Science" required />
            </div>
            <div class="form-group">
              <label>Section</label>
              <input v-model="newClass.section" type="text" placeholder="e.g., Section A" />
            </div>
          </div>
          <div class="form-group">
            <label>Description *</label>
            <textarea v-model="newClass.description" placeholder="Describe the course topics and what students will learn. This helps generate relevant writing prompts for the authorship verification profile." rows="3" required></textarea>
            <span style="font-size: 12px; color: #5f6368; margin-top: 4px; display: block;">A Writing Profile Assessment will be auto-created for this course.</span>
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
import { ref, computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { useClasses } from '@/composables/classroom'

const router = useRouter()
const { classes, fetchClasses, createClass, archiveClass: doArchive } = useClasses()

const activeTab = ref('active')
const showCreateModal = ref(false)
const creating = ref(false)
const openMenu = ref(null)
const pageLoading = ref(true)

const colors = ['#1a73e8', '#137333', '#c5221f', '#f9ab00', '#9334e6', '#188038', '#e37400', '#1557b0']

const newClass = ref({
  name: '', subject: '', section: '', description: '', color: '#1a73e8'
})

const activeClasses = computed(() => classes.value.filter(c => !c.archived))
const archivedClasses = computed(() => classes.value.filter(c => c.archived))
const displayedClasses = computed(() => activeTab.value === 'active' ? activeClasses.value : archivedClasses.value)

function goToClass(cls) {
  router.push(`/teacher/class/${cls.class_id}`)
}

async function handleCreateClass() {
  creating.value = true
  const result = await createClass(newClass.value)
  creating.value = false
  if (result.success) {
    showCreateModal.value = false
    newClass.value = { name: '', subject: '', section: '', description: '', color: '#1a73e8' }
  }
}

function toggleMenu(id) {
  openMenu.value = openMenu.value === id ? null : id
}

function copyCode(code) {
  navigator.clipboard.writeText(code)
  alert('Class code copied!')
}

function editClass(cls) {
  openMenu.value = null
  // TODO: Open edit modal
}

async function archiveClass(cls) {
  openMenu.value = null
  await doArchive(cls.class_id)
}

onMounted(async () => {
  await Promise.all([fetchClasses(), fetchClasses(true)])
  pageLoading.value = false
})
</script>

<style scoped>
.class-list-page {
  min-height: 100vh;
  background: #f8f9fa;
}

.page-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 16px 24px;
  background: white;
  border-bottom: 1px solid #e0e0e0;
}

.header-left {
  display: flex;
  align-items: center;
  gap: 16px;
}

.back-btn {
  width: 40px;
  height: 40px;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: 50%;
  color: #5f6368;
  text-decoration: none;
}

.back-btn:hover {
  background: #f1f3f4;
}

.page-header h1 {
  font-size: 22px;
  font-weight: 400;
  color: #202124;
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

.page-content {
  max-width: 1200px;
  margin: 0 auto;
  padding: 24px;
}

.tabs {
  display: flex;
  gap: 8px;
  margin-bottom: 24px;
}

.tab {
  padding: 10px 20px;
  border: none;
  background: transparent;
  font-size: 14px;
  font-weight: 500;
  color: #5f6368;
  cursor: pointer;
  border-radius: 20px;
}

.tab.active {
  background: #e8f0fe;
  color: #1a73e8;
}

.classes-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(320px, 1fr));
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
}

.class-header {
  padding: 20px;
  color: white;
  position: relative;
}

.class-actions {
  position: absolute;
  top: 12px;
  right: 12px;
}

.action-btn {
  width: 32px;
  height: 32px;
  border: none;
  background: rgba(255,255,255,0.2);
  border-radius: 50%;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
}

.menu-dropdown {
  position: absolute;
  top: 100%;
  right: 0;
  background: white;
  border-radius: 8px;
  box-shadow: 0 2px 10px rgba(0,0,0,0.2);
  overflow: hidden;
  z-index: 10;
}

.menu-dropdown button {
  display: block;
  width: 100%;
  padding: 12px 20px;
  border: none;
  background: transparent;
  text-align: left;
  font-size: 14px;
  color: #202124;
  cursor: pointer;
}

.menu-dropdown button:hover {
  background: #f1f3f4;
}

.class-name {
  font-size: 18px;
  font-weight: 500;
  margin: 0 0 4px;
}

.class-section {
  font-size: 14px;
  opacity: 0.9;
  margin: 0;
}

.class-body {
  padding: 16px 20px;
  border-bottom: 1px solid #e0e0e0;
}

.class-subject {
  font-size: 14px;
  color: #5f6368;
  margin: 0 0 12px;
}

.class-code-display {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 13px;
  color: #5f6368;
}

.class-code-display code {
  background: #f1f3f4;
  padding: 4px 8px;
  border-radius: 4px;
  font-family: monospace;
  font-weight: 500;
  color: #1a73e8;
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
  color: #5f6368;
}

.copy-btn:hover {
  background: #f1f3f4;
}

.class-footer {
  padding: 12px 20px;
  display: flex;
  gap: 16px;
}

.stat {
  font-size: 13px;
  color: #5f6368;
}

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
  margin: 0;
}

/* Modal styles - same as dashboard */
.modal-overlay {
  position: fixed;
  inset: 0;
  background: rgba(0,0,0,0.5);
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
  margin: 0;
  color: #202124;
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
  color: #202124;
  background: white;
}

.form-row {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 16px;
}

.color-picker {
  display: flex;
  gap: 8px;
}

.color-option {
  width: 36px;
  height: 36px;
  border-radius: 50%;
  border: 3px solid transparent;
  cursor: pointer;
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
  color: #1a73e8;
  font-weight: 500;
  cursor: pointer;
}

.btn-primary {
  padding: 10px 24px;
  border: none;
  background: #1a73e8;
  color: white;
  font-weight: 500;
  border-radius: 8px;
  cursor: pointer;
}

.btn-primary:disabled {
  opacity: 0.6;
}
</style>
