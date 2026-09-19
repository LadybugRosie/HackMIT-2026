<script setup>
import { ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useAuth } from '../composables/useAuth.js'

const auth = useAuth()
const route = useRoute()
const router = useRouter()
const email = ref('')
const password = ref('')
const error = ref('')
const busy = ref(false)

async function submit() {
  busy.value = true
  error.value = ''
  try {
    const user = await auth.login(email.value, password.value)
    router.push(route.query.next || auth.home(user))
  } catch (e) {
    error.value = e.status === 401 ? 'Incorrect email or password.' : e.message
  } finally {
    busy.value = false
  }
}
</script>

<template>
  <form class="auth-card" @submit.prevent="submit">
    <h1>Log in</h1>
    <label>Email <input v-model="email" type="email" required autocomplete="email" /></label>
    <label>Password <input v-model="password" type="password" required autocomplete="current-password" /></label>
    <p v-if="error" class="error">{{ error }}</p>
    <button class="primary" :disabled="busy">{{ busy ? 'Signing in…' : 'Log in' }}</button>
    <p class="muted alt">No account? <RouterLink to="/signup">Sign up</RouterLink></p>
  </form>
</template>
