<template>
  <div
    class="ai-calculator-btn"
    @click="openAICalculator"
    @mouseenter="aiCalculatorTooltipVisible = true"
    @mouseleave="aiCalculatorTooltipVisible = false"
    :style="{
      position: 'relative',
      display: 'inline-flex',
      alignItems: 'center',
      justifyContent: 'center',
      width: '24px',
      height: '24px',
      border: '1px solid #ccc',
      background: 'white',
      cursor: 'pointer',
      borderRadius: '4px',
      fontSize: '12px',
      fontWeight: 'bold',
      marginRight: '5px'
    }"
    :title="'AI Calculator'"
  >
    <!-- Simple spinner animation -->
    <span v-if="isAICalculatorLoading" style="animation: spin 1s linear infinite; display: inline-block;">⟳</span>
    <span v-else>🧮</span>

    <!-- Tooltip -->
    <div
      v-if="aiCalculatorTooltipVisible"
      :style="{
        position: 'absolute',
        top: '-2.2rem',
        left: '50%',
        transform: 'translateX(-50%)',
        background: 'rgba(255, 255, 255, 0.95)',
        color: 'black',
        border: '1px solid rgba(0, 0, 0, 0.1)',
        boxShadow: '0 2px 8px rgba(0, 0, 0, 0.15)',
        padding: '4px 8px',
        borderRadius: '4px',
        fontSize: '12px',
        whiteSpace: 'nowrap',
        zIndex: 1001
      }"
    >
      AI Calculator
    </div>
  </div>

  <!-- Modal for AI Calculator Input -->
  <div v-if="showAICalculatorModal" class="modal-overlay" @click.self="closeModal">
    <div class="modal-content">
      <h3>AI Calculator</h3>
      <p>Describe what calculation you want to perform on the table:</p>
      <textarea
        v-model="suggestionInput"
        placeholder="E.g., Calculate total sales by month, find average expenses, etc."
        rows="4"
      ></textarea>
      <div class="modal-buttons">
        <button @click="closeModal">Cancel</button>
        <button @click="runAICalculation" :disabled="!suggestionInput.trim() || isAICalculatorLoading">
          <span v-if="isAICalculatorLoading">Calculating...</span>
          <span v-else>Calculate</span>
        </button>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref } from 'vue'
import { useStore } from '@/composables/store.js'
import axios from 'axios'

const { editor } = useStore()

const isAICalculatorLoading = ref(false)
const aiCalculatorTooltipVisible = ref(false)
const showAICalculatorModal = ref(false)
const suggestionInput = ref('')
const aiCalculatorAbortController = ref(null)

// Backend URL for AI calculator
const AI_CALCULATOR_URL = 'https://jfv6blghbfv5lr3wt6sho4kewe0mrifm.lambda-url.us-east-1.on.aws'

const openAICalculator = () => {
  if (!editor.value.isActive('table')) {
    showNotification('Please place your cursor inside a table to use the AI Calculator.', 'info')
    return
  }
  showAICalculatorModal.value = true
}

const closeModal = () => {
  showAICalculatorModal.value = false
  suggestionInput.value = ''
}

const runAICalculation = async () => {
  if (!editor.value || !suggestionInput.value.trim()) return

  // The new function will get data from the entire table the cursor is in.
  const tableData = extractTableData()
  if (!tableData || tableData.length === 0) {
    showNotification('Could not find a valid table or the table is empty.', 'error')
    closeModal()
    return
  }

  if (aiCalculatorAbortController.value) {
    aiCalculatorAbortController.value.abort()
  }

  aiCalculatorAbortController.value = new AbortController()
  isAICalculatorLoading.value = true

  try {
    const payload = {
      content: tableData,
      suggestion: {
        id: "table_calculation_" + Date.now(),
        title: "Table Analysis",
        description: suggestionInput.value.trim(),
        fields: Object.keys(tableData[0] || {}), // Get headers from the first row
        analysis_type: "custom_analysis",
        details: {
          user_request: suggestionInput.value.trim(),
          table_columns: Object.keys(tableData[0] || {})
        }
      },
      as_table: true
    }

    const response = await axios.post(
      `${AI_CALCULATOR_URL}/ai-calculate`,
      payload,
      {
        signal: aiCalculatorAbortController.value.signal,
        headers: { 'Content-Type': 'application/json' }
      }
    )

    insertResultsBelowTable(response.data)
    closeModal()
    showNotification('AI calculation completed successfully!', 'success')

  } catch (error) {
    if (axios.isCancel(error)) {
      showNotification('AI Calculation Aborted', 'info')
    } else {
      console.error("Error in AI calculation:", error)
      showNotification('Failed to perform calculation. Check the console for details.', 'error')
    }
  } finally {
    isAICalculatorLoading.value = false
  }
}

/**
 * Extracts data from the table currently selected or containing the cursor.
 * This function is more robust as it traverses the editor's document model
 * instead of relying on inconsistent plain text conversion.
 */
const extractTableData = () => {
  if (!editor.value.isActive('table')) {
    console.warn('AI Calculator: No active table selection.')
    return null
  }

  const { state } = editor.value
  const { selection } = state
  let tableNode = null

  // Find the parent table node from the current selection
  for (let i = selection.$from.depth; i > 0; i--) {
    const node = selection.$from.node(i)
    if (node.type.name === 'table') {
      tableNode = node
      break
    }
  }

  if (!tableNode) {
    console.error('AI Calculator: Could not find the table node.')
    return null
  }

  const tableRows = []
  let tableHeaders = []

  // Iterate over each row in the table node
  tableNode.forEach((rowNode, _, rowIndex) => {
    // The first row is assumed to be the header
    if (rowIndex === 0) {
      rowNode.forEach(cellNode => {
        tableHeaders.push(cellNode.textContent.trim())
      })
    } else { // Subsequent rows are data
      const rowData = {}
      rowNode.forEach((cellNode, __, cellIndex) => {
        // Use the header as a key, or a fallback like 'col_0'
        const key = tableHeaders[cellIndex] || `col_${cellIndex}`
        rowData[key] = cellNode.textContent.trim()
      })
      // Only add row if it contains data
      if (Object.keys(rowData).length > 0) {
        tableRows.push(rowData)
      }
    }
  })

  console.log('Successfully parsed table data:', tableRows)
  return tableRows
}


const insertResultsBelowTable = (resultData) => {
  if (!editor.value || !resultData) return

  const { state, view } = editor.value
  const { selection } = state

  // Find the position right after the table
  let tableEndPos = -1
  for (let i = selection.$from.depth; i > 0; i--) {
    const node = selection.$from.node(i)
    if (node.type.name === 'table') {
      // .after() gives the position after the node at a certain depth
      tableEndPos = selection.$from.after(i)
      break
    }
  }
  
  if (tableEndPos === -1) {
    console.error("Could not determine table end position to insert results.")
    return
  }

  // Build the results content to be inserted
  let content = ''

  // if (resultData.markdown) {
  //   let tableMarkdown = resultData.markdown.trim()
  //   // Clean up potential code block formatting from the response
  //   tableMarkdown = tableMarkdown.replace(/^```(markdown)?\n?/, '').replace(/\n?```$/, '').trim()
  //   // This part is tricky as direct markdown insertion might not work.
  //   // For TipTap, you might need a markdown extension or insert it as HTML.
  //   // For now, let's assume inserting it as a preformatted block is safe.
  //   content += `<p>${tableMarkdown.replace(/\n/g, '<br>')}</p>` // A simple way to preserve lines
  // }

  if (resultData.result && Object.keys(resultData.result).length > 0) {
    content += '<h4>Summary:</h4><ul>'
    Object.entries(resultData.result).forEach(([metric, value]) => {
      const prettyMetric = metric.replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase())
      content += `<li><strong>${prettyMetric}</strong>: ${value}</li>`
    })
    content += '</ul>'
  }

  // Insert the HTML content at the calculated position?
  
  editor.value
    .chain()
    .focus()
    .insertContentAt(tableEndPos, content, { parseOptions: { preserveWhitespace: false } })
    .run()
}

// A simple, non-blocking notification function
const showNotification = (message, type = 'info') => {
  // In a real app, you would plug this into a toast/notification library
  console.log(`[${type.toUpperCase()}] ${message}`)
}

</script>

<style scoped>
@keyframes spin {
  from { transform: rotate(0deg); }
  to { transform: rotate(360deg); }
}

.modal-overlay {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background-color: rgba(0, 0, 0, 0.6);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 10000;
}

.modal-content {
  background: white;
  padding: 25px;
  border-radius: 8px;
  width: 450px;
  max-width: 90vw;
  box-shadow: 0 5px 15px rgba(0,0,0,0.3);
}

.modal-content h3 {
  margin-top: 0;
  font-family: sans-serif;
  color: #333;
}

.modal-content p {
  font-family: sans-serif;
  color: #555;
}

.modal-content textarea {
  width: 100%;
  box-sizing: border-box;
  margin: 10px 0;
  padding: 10px;
  border: 1px solid #ccc;
  border-radius: 4px;
  resize: vertical;
  font-family: sans-serif;
}

.modal-buttons {
  display: flex;
  justify-content: flex-end;
  gap: 10px;
  margin-top: 15px;
}

.modal-buttons button {
  padding: 10px 20px;
  border: none;
  border-radius: 4px;
  cursor: pointer;
  font-weight: bold;
  transition: background-color 0.2s;
}

.modal-buttons button:first-child {
  background: #e9ecef;
  color: #495057;
}

.modal-buttons button:first-child:hover {
  background: #dee2e6;
}

.modal-buttons button:last-child {
  background: #007bff;
  color: white;
}

.modal-buttons button:last-child:hover {
  background: #0056b3;
}

.modal-buttons button:disabled {
  opacity: 0.5;
  cursor: not-allowed;
  background: #007bff;
}
</style>