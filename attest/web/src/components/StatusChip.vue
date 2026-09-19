<script setup>
import { STATUS_LABEL } from '../lib/format.js'
defineProps({ status: { type: String, required: true } })
const cls = { not_started: 'muted', draft: 'warn', submitted: 'accent', graded: 'good', returned: 'good' }
</script>

<template>
  <span class="pill" :class="cls[status] || 'muted'">{{ STATUS_LABEL[status] || status }}</span>
</template>

<style scoped>
.accent { color: var(--accent); }
</style>
