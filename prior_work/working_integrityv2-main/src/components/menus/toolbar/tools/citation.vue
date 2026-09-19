<template>
  <menus-button
    ico="citation"
    text="Citation"
    huge
    :loading="isLoading"
    @menu-click="checkCitations"
  />
</template>

<script setup>
import { ref } from 'vue'
import axios from 'axios'
import { useStore } from '@/composables/store'

const { editor } = useStore()
const isLoading = ref(false)

const LAMBDA_BACKEND_URL = import.meta.env.VITE_LAMBDA_BACKEND_URL || 'https://jfv6blghbfv5lr3wt6sho4kewe0mrifm.lambda-url.us-east-1.on.aws'

const showNotification = (message, type = 'info') => {
  console.log(`${type.toUpperCase()}: ${message}`)
  alert(`${type.toUpperCase()}: ${message}`)
}

const checkCitations = async () => {
  if (!editor.value) {
    showNotification('Editor not available', 'error')
    return
  }

  try {
    isLoading.value = true
    
    // Get current editor content
    const content = editor.value.getHTML()
    
    const response = await axios.post(
      `${LAMBDA_BACKEND_URL}/api/detect-missing-citations`,
      { 
        user_id: "2e9d0849",
        text: content 
      }
    )

    const { highlighted_sentences = [] } = response.data

    // Process highlighted sentences
    if (highlighted_sentences.length > 0) {
      // Start a transaction
      editor.value.chain().focus()
      
      highlighted_sentences.forEach(sentence => {
        const cleanText = sentence.highlighted_text.replace(/\u001b\[\d+m/g, '')
        
        // Find all matches in the document
        const { state } = editor.value
        let pos = 0
        let match
        
        // Create a regex pattern to find the text (case insensitive)
        const pattern = new RegExp(cleanText.replace(/[.*+?^${}()|[\]\\]/g, '\\$&'), 'gi')
        
        // Search through all text nodes
        state.doc.descendants((node, nodePos) => {
          if (node.isText) {
            const text = node.text
            while ((match = pattern.exec(text)) !== null) {
              const from = nodePos + match.index
              const to = from + match[0].length
              
              // Apply the color to each match
              editor.value.chain()
                .setTextSelection({ from, to })
                .setColor('#FF0000')
                .run()
            }
          }
        })
      })
    }

    showNotification(
      `Found ${highlighted_sentences.length} sentences needing citations`,
      'success'
    )
    
  } catch (error) {
    console.error('Error checking citations:', error)
    showNotification(
      error.response?.data?.message || 'Failed to check citations', 
      'error'
    )
  } finally {
    isLoading.value = false
  }
}
</script>