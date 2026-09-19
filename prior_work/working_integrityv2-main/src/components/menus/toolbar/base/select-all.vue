<template>
  <menus-button
    ico="select-all"
    :text="t('base.selectAll')"
    shortcut="Ctrl+A"
    hide-text
    @menu-click="handleSelectAll"
  />
</template>

<script setup>
const { editor } = useStore()

// Reliable select all handler that works across all systems
const handleSelectAll = () => {
  if (!editor.value || !editor.value.view) {
    console.warn('Editor not available for select all operation')
    return
  }
  
  try {
    // Use TipTap's built-in selectAll command with focus options to prevent scrolling
    editor.value.chain().focus(undefined, { scrollIntoView: false }).selectAll().run()
    
    // Simple accessibility announcement without complex DOM manipulation
    const announcement = t('base.selectAll')
    if (window.speechSynthesis && window.speechSynthesis.speak) {
      const utterance = new SpeechSynthesisUtterance(announcement)
      utterance.volume = 0.1
      utterance.rate = 1.2
      window.speechSynthesis.speak(utterance)
    }
  } catch (error) {
    console.warn('Error in select all handler:', error)
    // Fallback: let the browser handle Ctrl+A naturally
    return false
  }
}
</script>
