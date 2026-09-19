<script setup>
defineProps({ trust: Number, verdict: String, level: String })
const cls = { genuine: 'good', review: 'warn', suspicious: 'bad', insufficient_data: 'muted' }
</script>

<template>
  <span v-if="trust === null || trust === undefined" class="muted">—</span>
  <span v-else class="chip" :class="cls[verdict] || 'muted'" :title="`verdict: ${verdict}`">
    <b>{{ trust }}</b><small>{{ level || '' }}</small>
  </span>
</template>

<style scoped>
.chip { display: inline-flex; align-items: baseline; gap: 4px; padding: 2px 8px; border-radius: 999px; border: 1px solid currentColor; font-size: 12px; }
.chip small { font-size: 10px; opacity: 0.8; }
</style>
