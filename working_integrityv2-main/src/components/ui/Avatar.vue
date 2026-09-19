<template>
  <div 
    :class="['ui-avatar', `ui-avatar--${size}`, { 'ui-avatar--clickable': clickable }]"
    :style="avatarStyle"
    @click="clickable && $emit('click', $event)"
  >
    <img v-if="src" :src="src" :alt="alt" class="ui-avatar__image" @error="handleImageError" />
    <span v-else class="ui-avatar__initials">{{ initials }}</span>
    <span v-if="status" :class="['ui-avatar__status', `ui-avatar__status--${status}`]"></span>
  </div>
</template>

<script setup>
import { computed, ref } from 'vue'

const props = defineProps({
  src: String,
  alt: String,
  name: String,
  size: {
    type: String,
    default: 'medium',
    validator: (v) => ['small', 'medium', 'large', 'xlarge'].includes(v)
  },
  status: {
    type: String,
    validator: (v) => ['online', 'offline', 'busy', 'away'].includes(v)
  },
  color: String,
  clickable: Boolean
})

defineEmits(['click'])

const imageError = ref(false)

const initials = computed(() => {
  if (!props.name) return '?'
  return props.name
    .split(' ')
    .map(n => n[0])
    .join('')
    .toUpperCase()
    .slice(0, 2)
})

const avatarStyle = computed(() => {
  if (props.color) {
    return { backgroundColor: props.color }
  }
  // Generate consistent color from name
  if (props.name) {
    const colors = [
      '#1a73e8', '#ea4335', '#fbbc04', '#34a853',
      '#673ab7', '#ff5722', '#00bcd4', '#e91e63'
    ]
    const index = props.name.charCodeAt(0) % colors.length
    return { backgroundColor: colors[index] }
  }
  return {}
})

function handleImageError() {
  imageError.value = true
}
</script>

<style scoped>
.ui-avatar {
  position: relative;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  border-radius: 50%;
  background: #1a73e8;
  color: white;
  font-weight: 500;
  overflow: hidden;
  flex-shrink: 0;
}

.ui-avatar--clickable {
  cursor: pointer;
  transition: transform 0.2s, box-shadow 0.2s;
}

.ui-avatar--clickable:hover {
  transform: scale(1.05);
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.15);
}

/* Sizes */
.ui-avatar--small {
  width: 32px;
  height: 32px;
  font-size: 12px;
}

.ui-avatar--medium {
  width: 40px;
  height: 40px;
  font-size: 14px;
}

.ui-avatar--large {
  width: 56px;
  height: 56px;
  font-size: 18px;
}

.ui-avatar--xlarge {
  width: 80px;
  height: 80px;
  font-size: 24px;
}

.ui-avatar__image {
  width: 100%;
  height: 100%;
  object-fit: cover;
}

.ui-avatar__initials {
  user-select: none;
}

/* Status indicator */
.ui-avatar__status {
  position: absolute;
  bottom: 2px;
  right: 2px;
  width: 12px;
  height: 12px;
  border-radius: 50%;
  border: 2px solid white;
}

.ui-avatar--small .ui-avatar__status {
  width: 10px;
  height: 10px;
  bottom: 0;
  right: 0;
}

.ui-avatar--large .ui-avatar__status,
.ui-avatar--xlarge .ui-avatar__status {
  width: 16px;
  height: 16px;
  bottom: 4px;
  right: 4px;
  border-width: 3px;
}

.ui-avatar__status--online {
  background: #1e8e3e;
}

.ui-avatar__status--offline {
  background: #9aa0a6;
}

.ui-avatar__status--busy {
  background: #d93025;
}

.ui-avatar__status--away {
  background: #f9ab00;
}
</style>
