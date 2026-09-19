import { createRouter, createWebHistory } from 'vue-router'
import EditorPage from '@/components/EditorPage.vue'
import IntegritySessionStart from '@/components/IntegritySessionStart.vue'
import Login from '@/pages/Login.vue'
import Signup from '@/pages/Signup.vue'
import Profile from '@/pages/Profile.vue'
import Dashboard from '@/pages/Dashboard.vue'
import { getApiUrl } from '@/utils/api-url'

// Lazy load teacher pages
const TeacherDashboard = () => import('@/pages/teacher/TeacherDashboard.vue')
const TeacherClasses = () => import('@/pages/teacher/ClassList.vue')
const TeacherClassDetail = () => import('@/pages/teacher/ClassDetail.vue')
const CreateAssignment = () => import('@/pages/teacher/CreateAssignment.vue')
const AssignmentDetail = () => import('@/pages/teacher/AssignmentDetail.vue')
const GradeSubmission = () => import('@/pages/teacher/GradeSubmission.vue')
const SessionPlayback = () => import('@/pages/teacher/SessionPlayback.vue')

// Lazy load student pages
const StudentDashboard = () => import('@/pages/student/StudentDashboard.vue')
const StudentClassView = () => import('@/pages/student/StudentClassView.vue')
const StudentAssignment = () => import('@/pages/student/StudentAssignment.vue')
const StylometryEnrollment = () => import('@/pages/student/StylometryEnrollment.vue')
const SubmissionView = () => import('@/pages/student/SubmissionView.vue')

// Lazy load researcher pages
const ResearcherDashboard = () => import('@/pages/researcher/ResearcherDashboard.vue')
const NewTopic = () => import('@/pages/researcher/NewTopic.vue')
const LabView = () => import('@/pages/researcher/LabView.vue')
const ResearcherSubmissionView = () => import('@/pages/researcher/ResearcherSubmissionView.vue')
const HallucinationCheck = () => import('@/pages/researcher/HallucinationCheck.vue')

// Shared pages
const JoinClass = () => import('@/pages/JoinClass.vue')
const SharedSubmission = () => import('@/pages/SharedSubmission.vue')

// FIX #7: Auth check uses Authorization header instead of token in URL
async function checkAuth() {
  const token = localStorage.getItem('auth_token')
  if (!token) return { isAuth: false, user: null }
  
  try {
    const API = getApiUrl()
    const response = await fetch(`${API}/api/auth/verify`, {
      headers: { 'Authorization': `Bearer ${token}` }
    })
    const data = await response.json()
    return { 
      isAuth: data.valid === true, 
      user: data.user || null 
    }
  } catch (e) {
    console.error('Auth check failed:', e)
    return { isAuth: false, user: null }
  }
}

const routes = [
  // Public routes
  {
    path: '/login',
    name: 'Login',
    component: Login,
    meta: { public: true }
  },
  {
    path: '/signup',
    name: 'Signup',
    component: Signup,
    meta: { public: true }
  },
  {
    path: '/reset-password',
    name: 'ResetPassword',
    component: () => import('@/pages/ResetPassword.vue'),
    meta: { public: true }
  },
  {
    path: '/share/:token',
    name: 'SharedSubmission',
    component: SharedSubmission,
    props: route => ({ token: route.params.token }),
    meta: { public: true }
  },
  {
    // Co-author invite link — public landing; the page routes to auth /
    // stylometry enrollment / the collaborative editor as needed.
    path: '/join/:token',
    name: 'JoinReport',
    component: () => import('@/pages/researcher/JoinReport.vue'),
    meta: { public: true }
  },
  
  // ============================================================
  // TEACHER ROUTES
  // ============================================================
  {
    path: '/teacher',
    redirect: '/teacher/dashboard'
  },
  {
    path: '/teacher/dashboard',
    name: 'TeacherDashboard',
    component: TeacherDashboard,
    meta: { requiresAuth: true, requiresRole: 'teacher' }
  },
  {
    path: '/teacher/classes',
    name: 'TeacherClasses',
    component: TeacherClasses,
    meta: { requiresAuth: true, requiresRole: 'teacher' }
  },
  {
    path: '/teacher/class/:id',
    name: 'TeacherClassDetail',
    component: TeacherClassDetail,
    props: true,
    meta: { requiresAuth: true, requiresRole: 'teacher' }
  },
  {
    path: '/teacher/class/:classId/assignment/new',
    name: 'CreateAssignment',
    component: CreateAssignment,
    props: true,
    meta: { requiresAuth: true, requiresRole: 'teacher' }
  },
  {
    path: '/teacher/assignment/:id',
    name: 'TeacherAssignmentDetail',
    component: AssignmentDetail,
    props: true,
    meta: { requiresAuth: true, requiresRole: 'teacher' }
  },
  {
    path: '/teacher/assignment/:id/edit',
    name: 'EditAssignment',
    component: CreateAssignment,
    props: route => ({ assignmentId: route.params.id, isEdit: true }),
    meta: { requiresAuth: true, requiresRole: 'teacher' }
  },
  {
    path: '/teacher/submission/:id',
    name: 'GradeSubmission',
    component: GradeSubmission,
    props: true,
    meta: { requiresAuth: true, requiresRole: 'teacher' }
  },
  {
    path: '/teacher/submission/:id/playback',
    name: 'SessionPlayback',
    component: SessionPlayback,
    props: true,
    meta: { requiresAuth: true, requiresRole: 'teacher' }
  },
  
  // ============================================================
  // STUDENT ROUTES
  // ============================================================
  {
    path: '/student',
    redirect: '/student/dashboard'
  },
  {
    path: '/student/dashboard',
    name: 'StudentDashboard',
    component: StudentDashboard,
    meta: { requiresAuth: true, requiresRole: 'student' }
  },
  {
    path: '/student/class/:id',
    name: 'StudentClassView',
    component: StudentClassView,
    props: true,
    meta: { requiresAuth: true, requiresRole: 'student' }
  },
  {
    path: '/student/assignment/:id',
    name: 'StudentAssignment',
    component: StudentAssignment,
    props: true,
    meta: { requiresAuth: true, requiresRole: 'student' }
  },
  {
    path: '/student/stylometry-enrollment/:classId',
    name: 'StylometryEnrollment',
    component: StylometryEnrollment,
    props: true,
    meta: { requiresAuth: true, requiresRole: 'student' }
  },
  {
    path: '/student/submission/:id',
    name: 'StudentSubmissionView',
    component: SubmissionView,
    props: true,
    meta: { requiresAuth: true }
  },
  {
    path: '/join',
    name: 'JoinClass',
    component: JoinClass,
    meta: { requiresAuth: true, requiresRole: 'student' }
  },

  // ============================================================
  // RESEARCHER ROUTES
  // ============================================================
  {
    path: '/researcher',
    redirect: '/researcher/dashboard'
  },
  {
    path: '/researcher/dashboard',
    name: 'ResearcherDashboard',
    component: ResearcherDashboard,
    meta: { requiresAuth: true, requiresRole: 'researcher' }
  },
  {
    path: '/researcher/topic/new',
    name: 'NewTopic',
    component: NewTopic,
    meta: { requiresAuth: true, requiresRole: 'researcher' }
  },
  {
    path: '/researcher/lab/:id',
    name: 'LabView',
    component: LabView,
    props: true,
    meta: { requiresAuth: true, requiresRole: 'researcher' }
  },
  {
    path: '/researcher/submission/:id',
    name: 'ResearcherSubmissionView',
    component: ResearcherSubmissionView,
    props: true,
    meta: { requiresAuth: true, requiresRole: 'researcher' }
  },
  {
    path: '/researcher/hallucination-check',
    name: 'HallucinationCheck',
    component: HallucinationCheck,
    meta: { requiresAuth: true, requiresRole: 'researcher' }
  },
  {
    path: '/researcher/stylometry-enrollment/:classId',
    name: 'ResearcherStylometryEnrollment',
    component: StylometryEnrollment,
    props: true,
    meta: { requiresAuth: true, requiresRole: 'researcher' }
  },

  // ============================================================
  // SHARED / LEGACY ROUTES
  // ============================================================
  {
    path: '/dashboard',
    name: 'Dashboard',
    component: Dashboard,
    meta: { requiresAuth: true }
  },
  {
    path: '/profile',
    name: 'Profile',
    component: Profile,
    meta: { requiresAuth: true }
  },
  {
    path: '/integrity/start',
    name: 'IntegrityStart',
    component: IntegritySessionStart,
    meta: { requiresAuth: true }
  },
  {
    path: '/editor/:id',
    name: 'Editor',
    component: EditorPage,
    props: true,
    meta: { requiresAuth: true, requiresStylometry: true }
  },
  { 
    path: '/editor', 
    redirect: '/dashboard' 
  },
  { 
    path: '/',
    beforeEnter() {
      // Show landing page
      window.location.href = '/landing.html';
    }
  },
  { 
    path: '/:pathMatch(.*)*',
    redirect: '/login' 
  }
]

const router = createRouter({
  history: createWebHistory(import.meta.env.BASE_URL),
  routes
})

// Navigation guard with role-based routing
router.beforeEach(async (to, from, next) => {
  // Landing page - let it through
  if (to.path === '/') {
    next()
    return
  }
  
  // Public routes don't need auth
  if (to.meta.public) {
    // If already logged in and going to login/signup, redirect to role-based dashboard
    const { isAuth, user } = await checkAuth()
    if (isAuth && (to.path === '/login' || to.path === '/signup')) {
      // Redirect based on role
      if (user?.role === 'teacher') {
        next('/teacher/dashboard')
      } else if (user?.role === 'researcher') {
        next('/researcher/dashboard')
      } else {
        next('/student/dashboard')
      }
      return
    }
    next()
    return
  }
  
  // Protected routes need auth
  if (to.meta.requiresAuth) {
    const { isAuth, user } = await checkAuth()
    if (!isAuth) {
      next('/login')
      return
    }
    
    // Check role requirements
    if (to.meta.requiresRole) {
      const userRole = user?.role || 'student'
      if (to.meta.requiresRole !== userRole) {
        // Redirect to correct dashboard
        if (userRole === 'teacher') {
          next('/teacher/dashboard')
        } else if (userRole === 'researcher') {
          next('/researcher/dashboard')
        } else {
          next('/student/dashboard')
        }
        return
      }
    }
    
    // Legacy dashboard redirect to role-based dashboard
    if (to.path === '/dashboard') {
      if (user?.role === 'teacher') {
        next('/teacher/dashboard')
      } else if (user?.role === 'researcher') {
        next('/researcher/dashboard')
      } else {
        next('/student/dashboard')
      }
      return
    }
    
    // Per-course stylometry enrollment is now checked by the assignment page itself,
    // not by the global router guard. The editor route keeps requiresStylometry for
    // backward compatibility but it's no longer enforced globally — the per-course
    // gate in StudentAssignment.vue handles this before navigating to the editor.
  }
  
  next()
})

// Reset theme-mode to light when navigating away from the editor.
// The UMO editor sets theme-mode="dark" on <html> based on OS preference,
// which activates TDesign's dark CSS variables globally (white text).
// Non-editor pages need light mode to render correctly.
router.afterEach((to) => {
  if (to.name !== 'Editor') {
    document.documentElement.setAttribute('theme-mode', 'light')
  }
})

export default router
// Build trigger: 1768347915
// Build timestamp: 1768400016
