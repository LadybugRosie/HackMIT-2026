<script setup>
import { useAuth } from '../../composables/useAuth.js'
const auth = useAuth()
</script>

<template>
  <h1>Welcome, {{ auth.state.user?.name }}</h1>
  <p class="muted">Teacher dashboard — classes and assignments arrive in the next stage.</p>
</template>
