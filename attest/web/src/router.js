import { createRouter, createWebHistory } from 'vue-router'
import { useAuth } from './composables/useAuth.js'

const routes = [
  { path: '/', component: () => import('./pages/Landing.vue'), meta: { public: true } },
  { path: '/login', component: () => import('./pages/Login.vue'), meta: { public: true } },
  { path: '/signup', component: () => import('./pages/Signup.vue'), meta: { public: true } },
  { path: '/attest', component: () => import('./pages/AttestDemo.vue'), meta: { public: true, wide: true } },

  { path: '/student', component: () => import('./pages/student/Dashboard.vue'), meta: { role: 'student' } },
  { path: '/teacher', component: () => import('./pages/teacher/Dashboard.vue'), meta: { role: 'teacher' } },

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
