<template>
  <menus-button
    ico="format"
    text="Templates"
    menu-type="dropdown"
    :huge="huge"
    :select-options="templates"
    @click="generateLatex"
    class="latex-button"
  />
</template>

<script setup>
defineProps({
  huge: {
    type: Boolean,
    default: true,
  },
})
const { editor } = useStore()

const templates = [
  { content: 'IEEE', value: 'ieee' },
  { content: 'ACM', value: 'acm' },
  { content: 'APA Thesis', value: 'apa_thesis' },
  { content: 'Nature', value: 'nature' },
  { content: 'Springer', value: 'springer' },
]

const generateLatex = async ({ content, value }) => {
  if (!content || !value) {
    return
  }

  try {
    // Get HTML content from editor
    const htmlContent = editor.value?.getHTML()
    if (!htmlContent) {
      const dialog = useAlert({
        theme: 'warning',
        header: 'Error',
        body: 'No content found in the editor.',
        confirmBtn: 'OK',
        onConfirm() {
          dialog.destroy()
        },
      })
      return
    }

    // Show loading state
    const loadingDialog = useAlert({
      theme: 'info',
      header: 'Generating LaTeX',
      body: 'Processing your document, please wait...',
      confirmBtn: null,
      closeBtn: false,
    })

    // Prepare payload for the API
    const payload = {
      content_html: htmlContent,
      template: value
    }

    // Call the LaTeX generation API
    const response = await fetch('https://latexify-production.up.railway.app/api/one-click-latexify', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(payload)
    })

    if (!response.ok) {
      throw new Error(`HTTP error! status: ${response.status}`)
    }

    // Handle zip file download
    const blob = await response.blob()
    const url = window.URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.style.display = 'none'
    a.href = url
    a.download = `latex_document_${value}.zip`
    document.body.appendChild(a)
    a.click()
    window.URL.revokeObjectURL(url)
    document.body.removeChild(a)

    loadingDialog.destroy()

    // Show success message
    const successDialog = useAlert({
      theme: 'success',
      header: 'Success',
      body: 'LaTeX document generated and downloaded successfully!',
      confirmBtn: 'OK',
      onConfirm() {
        successDialog.destroy()
      },
    })

  } catch (error) {
    // Hide loading dialog if it exists
    if (loadingDialog) {
      loadingDialog.destroy()
    }

    console.error('LaTeX generation error:', error)
    const dialog = useAlert({
      theme: 'error',
      header: 'Generation Failed',
      body: 'Failed to generate LaTeX document. Please try again or check your internet connection.',
      confirmBtn: 'OK',
      onConfirm() {
        dialog.destroy()
      },
    })
  }
}
</script>

<style lang="less" scoped>
.latex-button {
  :deep(.menu-button) {
    background: linear-gradient(135deg, rgba(99, 179, 237, 0.8) 0%, rgba(162, 155, 254, 0.8) 50%, rgba(251, 191, 36, 0.8) 100%);
    color: white;
    border-radius: 8px;
    border: none;
    transition: all 0.3s ease;
    position: relative;
    overflow: hidden;
    height: auto !important;
    min-height: 32px;
    padding: 8px 12px;
    
    
    &:hover {
      background: linear-gradient(135deg, rgba(99, 179, 237, 0.9) 0%, rgba(162, 155, 254, 0.9) 50%, rgba(251, 191, 36, 0.9) 100%);
      transform: translateY(-1px);
      box-shadow: 0 4px 12px rgba(99, 179, 237, 0.4);
    }
    
    &:active {
      transform: translateY(0px);
    }
    
    .umo-button__text {
      font-weight: 600;
    }
    
    // Fix text alignment in huge buttons
    &.huge .button-content {
      .icon {
        margin-top: 0 !important;
        margin-bottom: 2px;
      }
      .icon-svg {
        margin-top: 0 !important;
        margin-bottom: 2px;
      }
      .text {
        margin-top: 0;
        line-height: 1.2;
      }
    }
  }
  
  // Ensure proper display in the latex group
  display: flex;
  align-items: center;
  height: 100%;
  
}
</style>