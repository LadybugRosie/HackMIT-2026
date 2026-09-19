<script setup>
import { useRouter } from 'vue-router'
import { useAuth } from '../composables/useAuth.js'

const auth = useAuth()
const router = useRouter()

async function logout() {
  await auth.logout()
  router.push('/')
}
</script>

<template>
  <nav class="nav">
    <div class="container nav-inner">
      <RouterLink :to="auth.state.user ? auth.home() : '/'" class="brand">attest<span class="muted"> classroom</span></RouterLink>
      <div class="links">
        <RouterLink to="/attest" class="link">Engine demo</RouterLink>
        <template v-if="auth.state.user">
          <span class="who">{{ auth.state.user.name }} <small class="muted">· {{ auth.state.user.role }}</small></span>
          <button class="ghost" @click="logout">Log out</button>
        </template>
        <template v-else>
          <RouterLink to="/login" class="link">Log in</RouterLink>
          <RouterLink to="/signup" class="btn">Sign up</RouterLink>
        </template>
      </div>
    </div>
  </nav>
</template>

<style scoped>
.nav { border-bottom: 1px solid var(--border); background: var(--surface); position: sticky; top: 0; z-index: 10; }
.nav-inner { display: flex; align-items: center; justify-content: space-between; height: 52px; }
.brand { font-weight: 700; letter-spacing: -0.01em; color: var(--text); text-decoration: none; font-size: 17px; }
.links { display: flex; align-items: center; gap: 14px; font-size: 14px; }
.link { color: var(--muted); text-decoration: none; } .link:hover { color: var(--text); }
.who { color: var(--text); }
.btn { background: var(--accent); color: #fff; padding: 6px 12px; border-radius: 6px; text-decoration: none; font-weight: 600; }
.ghost { background: none; border: 1px solid var(--border); color: var(--text); padding: 5px 10px; border-radius: 6px; cursor: pointer; }
</style>
