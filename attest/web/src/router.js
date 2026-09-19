import { createRouter, createWebHistory } from 'vue-router'
import { useAuth } from './composables/useAuth.js'

const routes = [
  { path: '/', component: () => import('./pages/Landing.vue'), meta: { public: true } },
  { path: '/login', component: () => import('./pages/Login.vue'), meta: { public: true } },
  { path: '/signup', component: () => import('./pages/Signup.vue'), meta: { public: true } },
  { path: '/attest', component: () => import('./pages/AttestDemo.vue'), meta: { public: true, wide: true } },

  { path: '/student', component: () => import('./pages/student/Dashboard.vue'), meta: { role: 'student' } },
  { path: '/student/classes/:classId', component: () => import('./pages/student/ClassView.vue'), meta: { role: 'student' } },
  { path: '/student/assignments/:assignmentId', component: () => import('./pages/student/AssignmentDetail.vue'), meta: { role: 'student' } },
  { path: '/write/:submissionId', component: () => import('./pages/student/Write.vue'), meta: { role: 'student', wide: true } },
  { path: '/student/submissions/:submissionId', component: () => import('./pages/student/SubmissionView.vue'), meta: { role: 'student', wide: true } },

  { path: '/teacher', component: () => import('./pages/teacher/Dashboard.vue'), meta: { role: 'teacher' } },
  { path: '/teacher/classes/:classId', component: () => import('./pages/teacher/ClassDetail.vue'), meta: { role: 'teacher' } },
  { path: '/teacher/classes/:classId/assignments/new', component: () => import('./pages/teacher/AssignmentForm.vue'), meta: { role: 'teacher' } },
  { path: '/teacher/assignments/:assignmentId/edit', component: () => import('./pages/teacher/AssignmentForm.vue'), meta: { role: 'teacher' } },
  { path: '/teacher/assignments/:assignmentId', component: () => import('./pages/teacher/AssignmentDetail.vue'), meta: { role: 'teacher' } },
  { path: '/teacher/submissions/:submissionId', component: () => import('./pages/teacher/GradeSubmission.vue'), meta: { role: 'teacher', wide: true } },

  { path: '/:pathMatch(.*)*', redirect: '/' },
]

export const router = createRouter({ history: createWebHistory(), routes })

router.beforeEach(async (to) => {
  const auth = useAuth()
  const user = await auth.load()
  if (to.meta.public) {
    // Signed-in users skip the marketing/login pages (but may still open the engine demo).
    if (user && (to.path === '/' || to.path === '/login' || to.path === '/signup')) return auth.home(user)
    return true
  }
  if (!user) return { path: '/login', query: { next: to.fullPath } }
  if (to.meta.role && to.meta.role !== user.role) return auth.home(user)
  return true
})
