<script setup>
import { ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useAuth } from '../composables/useAuth.js'

const auth = useAuth()
const route = useRoute()
const router = useRouter()
const form = ref({
  name: '', email: '', password: '',
  role: route.query.role === 'teacher' ? 'teacher' : 'student',
  class_code: route.query.code || '',
})
const error = ref('')
const busy = ref(false)

async function submit() {
  busy.value = true
  error.value = ''
  try {
    const body = { ...form.value }
    if (!body.class_code) delete body.class_code
    const user = await auth.signup(body)
    router.push(auth.home(user))
  } catch (e) {
    error.value = e.status === 409 ? 'An account with this email already exists.'
      : e.status === 404 ? 'That class code was not found.'
      : Array.isArray(e.detail) ? e.detail.map((d) => d.msg).join(' ') : e.message
  } finally {
    busy.value = false
  }
}
</script>

<template>
  <form class="auth-card" @submit.prevent="submit">
    <h1>Create your account</h1>
    <div class="roles">
      <button type="button" :class="{ on: form.role === 'student' }" @click="form.role = 'student'">Student</button>
      <button type="button" :class="{ on: form.role === 'teacher' }" @click="form.role = 'teacher'">Teacher</button>
    </div>
    <label>Full name <input v-model="form.name" required autocomplete="name" /></label>
    <label>Email <input v-model="form.email" type="email" required autocomplete="email" /></label>
    <label>Password <input v-model="form.password" type="password" required minlength="8" autocomplete="new-password" /></label>
    <label v-if="form.role === 'student'">Class code <small class="muted">(optional)</small>
      <input v-model="form.class_code" placeholder="e.g. K7M2QX" maxlength="8" style="text-transform: uppercase" />
    </label>
    <p v-if="error" class="error">{{ error }}</p>
    <button class="primary" :disabled="busy">{{ busy ? 'Creating…' : `Sign up as ${form.role}` }}</button>
    <p class="muted alt">Already have an account? <RouterLink to="/login">Log in</RouterLink></p>
  </form>
</template>

<style scoped>
.roles { display: grid; grid-template-columns: 1fr 1fr; gap: 8px; margin-bottom: 4px; }
.roles button { padding: 8px; border-radius: 6px; border: 1px solid var(--border); background: var(--surface-2); color: var(--text); cursor: pointer; }
.roles button.on { border-color: var(--accent); color: var(--accent); font-weight: 600; }
</style>
