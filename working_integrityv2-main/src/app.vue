<template>
  <router-view />
</template>

<script setup>
// Root shell for router
</script>

<style>
.box {
  margin: 20px;
  height: calc(100vh - 40px);
  border: solid 1px #ddd;
  box-sizing: border-box;
  position: relative;
}
html,
body {
  margin: 0;
  padding: 0;
  min-height: 100vh;
  /* Do NOT set overflow: hidden here — it kills scrolling on every page.
     The editor page sets its own overflow: hidden via EditorPage.vue scoped styles. */
}
</style>
