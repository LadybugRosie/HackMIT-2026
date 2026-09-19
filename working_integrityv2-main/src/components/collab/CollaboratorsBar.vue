<template>
  <div v-if="users.length" class="collab-bar">
    <span class="collab-live"><span class="live-dot"></span> Live</span>
    <div class="collab-avatars">
      <span
        v-for="u in users"
        :key="u.uid || u.name"
        class="collab-avatar"
        :style="{ backgroundColor: u.color || '#7c3aed' }"
        :title="u.name"
      >{{ initials(u.name) }}</span>
    </div>
    <span class="collab-count">{{ users.length }} {{ users.length === 1 ? 'person' : 'people' }} editing</span>
  </div>
</template>

<script setup>
import { ref, onMounted, onBeforeUnmount } from 'vue'

// The editor (src/components/editor/index.vue) emits `collab-presence` on the
// window with { detail: { users: [{ uid, name, color }] } } whenever awareness
// changes. We just render it — no extra wiring needed.
const users = ref([])

function onPresence(e) {
  const list = e?.detail?.users || []
  // de-dup by uid (a user may have multiple awareness states briefly)
  const seen = new Set()
  users.value = list.filter((u) => {
    const k = u.uid || u.name
    if (seen.has(k)) return false
    seen.add(k)
    return true
  })
}

function initials(name) {
  if (!name) return '?'
  return name.trim().split(/\s+/).slice(0, 2).map((w) => w[0]).join('').toUpperCase()
}

onMounted(() => window.addEventListener('collab-presence', onPresence))
onBeforeUnmount(() => window.removeEventListener('collab-presence', onPresence))
</script>

<style scoped>
.collab-bar {
  display: inline-flex;
  align-items: center;
  gap: 10px;
  padding: 5px 12px;
  background: #fff;
  border: 1px solid #e5e7eb;
  border-radius: 20px;
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.06);
}
.collab-live {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  font-size: 12px;
  font-weight: 600;
  color: #137333;
}
.live-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: #34a853;
  box-shadow: 0 0 0 0 rgba(52, 168, 83, 0.5);
  animation: pulse 1.8s infinite;
}
@keyframes pulse {
  0% { box-shadow: 0 0 0 0 rgba(52, 168, 83, 0.5); }
  70% { box-shadow: 0 0 0 6px rgba(52, 168, 83, 0); }
  100% { box-shadow: 0 0 0 0 rgba(52, 168, 83, 0); }
}
.collab-avatars { display: inline-flex; }
.collab-avatar {
  width: 26px;
  height: 26px;
  border-radius: 50%;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  color: #fff;
  font-size: 11px;
  font-weight: 700;
  border: 2px solid #fff;
  margin-left: -8px;
}
.collab-avatar:first-child { margin-left: 0; }
.collab-count { font-size: 12.5px; color: #5f6368; }
</style>
