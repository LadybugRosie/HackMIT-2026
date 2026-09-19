/**
 * Classroom Composable
 * Handles API calls for classes, assignments, and submissions
 */
import { ref, computed } from 'vue'
import axios from 'axios'
import { getApiUrl } from '@/utils/api-url'

const API = getApiUrl()

// Auth token is now sent via Authorization header (axios interceptor in axios-auth.js).
// getToken() kept only for the rare cases that still need the raw token value.
function getToken() {
  return localStorage.getItem('auth_token')
}

// Extract readable error message from API responses
// FastAPI returns validation errors as an array of objects with {loc, msg, type}
function extractError(e, fallback = 'Something went wrong') {
  const detail = e.response?.data?.detail
  if (!detail) return e.response?.data?.message || fallback
  if (typeof detail === 'string') return detail
  if (Array.isArray(detail)) {
    return detail
      .map(err => {
        const field = err.loc ? err.loc[err.loc.length - 1] : ''
        const msg = err.msg || 'Validation error'
        return field ? `${field}: ${msg}` : msg
      })
      .join('; ')
  }
  if (typeof detail === 'object') return detail.msg || detail.message || JSON.stringify(detail)
  return fallback
}

// ============================================================================
// CLASSES - Global shared state so classes persist across navigation
// ============================================================================
const _sharedClasses = ref([])
const _sharedCurrentClass = ref(null)

export function useClasses() {
  const classes = _sharedClasses
  const currentClass = _sharedCurrentClass
  const loading = ref(false)
  const error = ref(null)

  async function fetchClasses(archived = false) {
    loading.value = true
    error.value = null

    try {
      const response = await axios.get(`${API}/api/classes`, {
        params: { archived }
      })
      // Merge instead of overwrite: replace classes matching the archived flag,
      // keep classes from the other category intact.
      const incoming = response.data
      const kept = classes.value.filter(c => !!c.archived !== archived)
      classes.value = [...kept, ...incoming]
      return { success: true, data: response.data }
    } catch (e) {
      error.value = extractError(e, 'Failed to fetch classes')
      return { success: false, error: error.value }
    } finally {
      loading.value = false
    }
  }

  async function fetchClass(classId) {
    loading.value = true
    error.value = null
    // Reset if switching to a different class to prevent stale flash
    if (currentClass.value?.class_id !== classId) {
      currentClass.value = null
    }
    
    try {
      const response = await axios.get(`${API}/api/classes/${classId}`)
      currentClass.value = response.data
      return { success: true, data: response.data }
    } catch (e) {
      error.value = extractError(e, 'Failed to fetch class')
      return { success: false, error: error.value }
    } finally {
      loading.value = false
    }
  }

  async function createClass(classData) {
    loading.value = true
    error.value = null
    
    try {
      const response = await axios.post(`${API}/api/classes`, classData)
      classes.value.unshift(response.data)
      return { success: true, data: response.data }
    } catch (e) {
      error.value = extractError(e, 'Failed to create class')
      return { success: false, error: error.value }
    } finally {
      loading.value = false
    }
  }

  async function updateClass(classId, classData) {
    loading.value = true
    error.value = null
    
    try {
      const response = await axios.put(`${API}/api/classes/${classId}`, classData)
      const idx = classes.value.findIndex(c => c.class_id === classId)
      if (idx !== -1) classes.value[idx] = response.data
      return { success: true, data: response.data }
    } catch (e) {
      error.value = extractError(e, 'Failed to update class')
      return { success: false, error: error.value }
    } finally {
      loading.value = false
    }
  }

  async function joinClass(classCode) {
    loading.value = true
    error.value = null
    
    try {
      const response = await axios.post(`${API}/api/classes/join`,
        { class_code: classCode }
      )
      // Refresh classes list
      await fetchClasses()
      return { success: true, data: response.data }
    } catch (e) {
      error.value = extractError(e, 'Failed to join class')
      return { success: false, error: error.value }
    } finally {
      loading.value = false
    }
  }

  async function archiveClass(classId) {
    loading.value = true
    try {
      await axios.put(`${API}/api/classes/${classId}/archive`, {})
      classes.value = classes.value.filter(c => c.class_id !== classId)
      return { success: true }
    } catch (e) {
      error.value = extractError(e, 'Failed to archive class')
      return { success: false, error: error.value }
    } finally {
      loading.value = false
    }
  }

  async function getClassMembers(classId, role = null) {
    try {
      const response = await axios.get(`${API}/api/classes/${classId}/members`, {
        params: { role }
      })
      return { success: true, data: response.data }
    } catch (e) {
      return { success: false, error: extractError(e, 'Failed to fetch members') }
    }
  }

  async function removeStudent(classId, userId) {
    try {
      await axios.delete(`${API}/api/classes/${classId}/members/${userId}`)
      return { success: true }
    } catch (e) {
      return { success: false, error: extractError(e, 'Failed to remove student') }
    }
  }

  async function regenerateClassCode(classId) {
    try {
      const response = await axios.post(`${API}/api/classes/${classId}/regenerate-code`, {})
      return { success: true, data: response.data }
    } catch (e) {
      return { success: false, error: extractError(e, 'Failed to regenerate code') }
    }
  }

  async function fetchDashboardStats() {
    try {
      const response = await axios.get(`${API}/api/classes/dashboard-stats`)
      return { success: true, data: response.data }
    } catch (e) {
      return { success: false, error: extractError(e, 'Failed to fetch dashboard stats') }
    }
  }

  return {
    classes,
    currentClass,
    loading,
    error,
    fetchClasses,
    fetchClass,
    createClass,
    updateClass,
    joinClass,
    archiveClass,
    getClassMembers,
    removeStudent,
    regenerateClassCode,
    fetchDashboardStats
  }
}

// ============================================================================
// ASSIGNMENTS - Global shared state so data persists across navigation
// ============================================================================
const _sharedAssignments = ref([])
const _sharedCurrentAssignment = ref(null)

export function useAssignments() {
  const assignments = _sharedAssignments
  const currentAssignment = _sharedCurrentAssignment
  const loading = ref(false)
  const error = ref(null)

  async function fetchAssignments(options = {}) {
    loading.value = true
    error.value = null
    
    try {
      const params = {}
      let classIdFilter = null
      if (typeof options === 'string') {
        params.class_id = options
        classIdFilter = options
      } else if (options) {
        if (options.class_id) { params.class_id = options.class_id; classIdFilter = options.class_id }
        if (options.published_only) params.published_only = true
      }
      
      const response = await axios.get(`${API}/api/assignments`, { params })

      if (classIdFilter) {
        // Merge: replace entries for this class only, preserve others
        const kept = assignments.value.filter(a => a.class_id !== classIdFilter)
        assignments.value = [...kept, ...response.data]
      } else {
        assignments.value = response.data
      }
      return { success: true, data: response.data }
    } catch (e) {
      error.value = extractError(e, 'Failed to fetch assignments')
      return { success: false, error: error.value }
    } finally {
      loading.value = false
    }
  }

  async function fetchAssignment(assignmentId) {
    loading.value = true
    error.value = null
    // Reset if switching to a different assignment to prevent stale flash
    if (currentAssignment.value?.assignment_id !== assignmentId) {
      currentAssignment.value = null
    }
    
    try {
      const response = await axios.get(`${API}/api/assignments/${assignmentId}`)
      currentAssignment.value = response.data
      return { success: true, data: response.data }
    } catch (e) {
      error.value = extractError(e, 'Failed to fetch assignment')
      return { success: false, error: error.value }
    } finally {
      loading.value = false
    }
  }

  async function createAssignment(assignmentData) {
    loading.value = true
    error.value = null
    
    try {
      const response = await axios.post(`${API}/api/assignments`, assignmentData)
      // Prevent duplicates: remove any existing entry with the same id, then prepend
      const newId = response.data.assignment_id
      assignments.value = [response.data, ...assignments.value.filter(a => a.assignment_id !== newId)]
      return { success: true, data: response.data }
    } catch (e) {
      error.value = extractError(e, 'Failed to create assignment')
      return { success: false, error: error.value }
    } finally {
      loading.value = false
    }
  }

  async function updateAssignment(assignmentId, assignmentData) {
    loading.value = true
    error.value = null
    
    try {
      const response = await axios.put(`${API}/api/assignments/${assignmentId}`, assignmentData)
      assignments.value = assignments.value.map(a =>
        a.assignment_id === assignmentId ? response.data : a
      )
      currentAssignment.value = response.data
      return { success: true, data: response.data }
    } catch (e) {
      error.value = extractError(e, 'Failed to update assignment')
      return { success: false, error: error.value }
    } finally {
      loading.value = false
    }
  }

  async function deleteAssignment(assignmentId) {
    loading.value = true
    try {
      await axios.delete(`${API}/api/assignments/${assignmentId}`)
      assignments.value = assignments.value.filter(a => a.assignment_id !== assignmentId)
      return { success: true }
    } catch (e) {
      error.value = extractError(e, 'Failed to delete assignment')
      return { success: false, error: error.value }
    } finally {
      loading.value = false
    }
  }

  async function publishAssignment(assignmentId) {
    try {
      await axios.post(`${API}/api/assignments/${assignmentId}/publish`, {})
      assignments.value = assignments.value.map(a =>
        a.assignment_id === assignmentId ? { ...a, published: true } : a
      )
      if (currentAssignment.value?.assignment_id === assignmentId) {
        currentAssignment.value = { ...currentAssignment.value, published: true }
      }
      return { success: true }
    } catch (e) {
      return { success: false, error: extractError(e, 'Failed to publish') }
    }
  }

  async function unpublishAssignment(assignmentId) {
    try {
      await axios.post(`${API}/api/assignments/${assignmentId}/unpublish`, {})
      assignments.value = assignments.value.map(a =>
        a.assignment_id === assignmentId ? { ...a, published: false } : a
      )
      if (currentAssignment.value?.assignment_id === assignmentId) {
        currentAssignment.value = { ...currentAssignment.value, published: false }
      }
      return { success: true }
    } catch (e) {
      return { success: false, error: extractError(e, 'Failed to unpublish') }
    }
  }

  async function getMySubmission(assignmentId) {
    try {
      const response = await axios.get(`${API}/api/assignments/${assignmentId}/my-submission`)
      return { success: true, data: response.data.submission }
    } catch (e) {
      return { success: false, error: extractError(e, 'Failed to get submission') }
    }
  }

  async function getAssignmentSubmissions(assignmentId, status = null) {
    try {
      const params = {}
      if (status) params.status = status
      
      const response = await axios.get(`${API}/api/assignments/${assignmentId}/submissions`, { params })
      return { success: true, data: response.data }
    } catch (e) {
      return { success: false, error: extractError(e, 'Failed to get submissions') }
    }
  }

  async function parseRubricWithAI(fileContent, fileName, totalPoints = 100) {
    loading.value = true
    try {
      const response = await axios.post(`${API}/api/assignments/parse-rubric-ai-content`, {
        file_content: fileContent,
        file_name: fileName,
        total_points: totalPoints
      })
      return { success: true, data: response.data }
    } catch (e) {
      return { success: false, error: extractError(e, 'AI rubric parsing failed') }
    } finally {
      loading.value = false
    }
  }

  return {
    assignments,
    currentAssignment,
    loading,
    error,
    fetchAssignments,
    fetchAssignment,
    createAssignment,
    updateAssignment,
    deleteAssignment,
    publishAssignment,
    unpublishAssignment,
    getMySubmission,
    getAssignmentSubmissions,
    parseRubricWithAI
  }
}

// ============================================================================
// SUBMISSIONS
// ============================================================================

export function useSubmissions() {
  const submissions = ref([])
  const currentSubmission = ref(null)
  const loading = ref(false)
  const error = ref(null)

  async function saveDraft(assignmentId, content, contentHtml = null) {
    loading.value = true
    error.value = null
    
    try {
      const response = await axios.post(`${API}/api/submissions`, {
        assignment_id: assignmentId,
        content,
        content_html: contentHtml
      })
      return { success: true, data: response.data }
    } catch (e) {
      error.value = extractError(e, 'Failed to save draft')
      return { success: false, error: error.value }
    } finally {
      loading.value = false
    }
  }

  async function submitAssignment(submissionId, content, contentHtml, sessionId, integrityData = null) {
    loading.value = true
    error.value = null
    
    try {
      const response = await axios.post(`${API}/api/submissions/${submissionId}/submit`, {
        content,
        content_html: contentHtml,
        session_id: sessionId,
        integrity_data: integrityData
      })
      return { success: true, data: response.data }
    } catch (e) {
      error.value = extractError(e, 'Failed to submit')
      return { success: false, error: error.value }
    } finally {
      loading.value = false
    }
  }

  async function fetchSubmission(submissionId) {
    loading.value = true
    error.value = null
    // Reset if switching to a different submission to prevent stale flash
    if (currentSubmission.value?.submission_id !== submissionId) {
      currentSubmission.value = null
    }
    
    try {
      const response = await axios.get(`${API}/api/submissions/${submissionId}`)
      currentSubmission.value = response.data
      return { success: true, data: response.data }
    } catch (e) {
      error.value = extractError(e, 'Failed to fetch submission')
      return { success: false, error: error.value }
    } finally {
      loading.value = false
    }
  }

  async function gradeSubmission(submissionId, gradeData) {
    loading.value = true
    error.value = null
    
    try {
      // Handle both object and direct value
      const payload = typeof gradeData === 'object' ? gradeData : { grade: gradeData }
      
      const response = await axios.put(`${API}/api/submissions/${submissionId}/grade`, payload)
      // IMPORTANT: Don't overwrite currentSubmission with the grade response.
      // The grade response is {success, grade, message...} - NOT the full submission.
      // Only merge the grade fields into the existing submission object.
      if (currentSubmission.value && currentSubmission.value.submission_id === submissionId) {
        currentSubmission.value = {
          ...currentSubmission.value,
          grade: response.data.grade,
          status: 'graded',
          feedback: payload.feedback || currentSubmission.value.feedback
        }
      }
      return { success: true, data: response.data }
    } catch (e) {
      error.value = extractError(e, 'Failed to grade submission')
      return { success: false, error: error.value }
    } finally {
      loading.value = false
    }
  }

  async function returnSubmission(submissionId) {
    try {
      const response = await axios.post(`${API}/api/submissions/${submissionId}/return`, {})
      // Update status locally without overwriting the full submission
      if (currentSubmission.value && currentSubmission.value.submission_id === submissionId) {
        currentSubmission.value = { ...currentSubmission.value, status: 'returned' }
      }
      return { success: true, data: response.data }
    } catch (e) {
      return { success: false, error: extractError(e, 'Failed to return') }
    }
  }

  async function requestAutoGrade(submissionId) {
    loading.value = true
    try {
      const response = await axios.post(`${API}/api/submissions/${submissionId}/auto-grade`, {})
      return { success: true, data: response.data }
    } catch (e) {
      return { success: false, error: extractError(e, 'Auto-grading failed') }
    } finally {
      loading.value = false
    }
  }

  async function approveAutoGrade(submissionId) {
    try {
      const response = await axios.post(`${API}/api/submissions/${submissionId}/approve-auto-grade`, {})
      // Update status locally without overwriting the full submission
      if (currentSubmission.value && currentSubmission.value.submission_id === submissionId) {
        currentSubmission.value = {
          ...currentSubmission.value,
          grade: response.data.grade,
          feedback: response.data.feedback || currentSubmission.value.feedback,
          status: 'graded'
        }
      }
      return { success: true, data: response.data }
    } catch (e) {
      return { success: false, error: extractError(e, 'Failed to approve') }
    }
  }

  async function bulkReturnSubmissions(submissionIds) {
    try {
      const response = await axios.post(`${API}/api/submissions/bulk-return`, submissionIds)
      return { success: true, data: response.data }
    } catch (e) {
      return { success: false, error: extractError(e, 'Failed to return submissions') }
    }
  }

  return {
    submissions,
    currentSubmission,
    loading,
    error,
    saveDraft,
    submitAssignment,
    fetchSubmission,
    gradeSubmission,
    returnSubmission,
    requestAutoGrade,
    approveAutoGrade,
    bulkReturnSubmissions
  }
}


// ============================================================================
// STYLOMETRY V3 — Per-course enrollment & verification
// ============================================================================

export function useStylometryV3() {
  const loading = ref(false)
  const error = ref(null)

  async function getCourseEnrollmentStatus(classId) {
    try {
      const response = await axios.get(`${API}/api/stylometry/v3/course-status/${classId}`)
      return { success: true, data: response.data }
    } catch (e) {
      return { success: false, error: extractError(e, 'Failed to check enrollment status') }
    }
  }

  async function enrollInCourse(classId, samples) {
    loading.value = true
    error.value = null
    try {
      const response = await axios.post(`${API}/api/stylometry/v3/enroll`, {
        class_id: classId,
        samples
      })
      return { success: true, data: response.data }
    } catch (e) {
      error.value = extractError(e, 'Enrollment failed')
      return { success: false, error: error.value }
    } finally {
      loading.value = false
    }
  }

  async function verifyCourseSubmission(classId, submissionText) {
    try {
      const response = await axios.post(`${API}/api/stylometry/v3/verify`, {
        class_id: classId,
        submission_text: submissionText
      })
      return { success: true, data: response.data }
    } catch (e) {
      return { success: false, error: extractError(e, 'Verification failed') }
    }
  }

  async function getCourseProfile(studentId) {
    try {
      const response = await axios.get(`${API}/api/stylometry/v3/profile/${studentId}`)
      return { success: true, data: response.data }
    } catch (e) {
      return { success: false, error: extractError(e, 'Failed to fetch profile') }
    }
  }

  return {
    loading,
    error,
    getCourseEnrollmentStatus,
    enrollInCourse,
    verifyCourseSubmission,
    getCourseProfile
  }
}
