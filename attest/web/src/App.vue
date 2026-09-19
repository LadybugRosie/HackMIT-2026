<script setup>
import { useRoute } from 'vue-router'
import NavBar from './components/NavBar.vue'

const route = useRoute()
</script>

<template>
  <NavBar />
  <div :class="route.meta.wide ? 'container wide' : 'container'">
    <RouterView />
  </div>
</template>
