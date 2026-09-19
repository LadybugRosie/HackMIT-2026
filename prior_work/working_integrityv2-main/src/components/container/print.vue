<template>
  <!-- Loading Overlay -->
  <div v-if="isGeneratingPDF" class="print-loading-overlay">
    <div class="print-loading-content">
      <div class="print-spinner"></div>
      <h3>{{ loadingMessage }}</h3>
      <p>{{ loadingSubMessage }}</p>
      <div class="print-progress-bar">
        <div class="print-progress-fill" :style="{ width: loadingProgress + '%' }"></div>
      </div>
      <div class="print-steps">
        <div v-if="assignmentToolSettings.analyze_integrity_enabled" :class="['print-step', loadingStep >= 1 ? 'active' : '', loadingStep > 1 ? 'done' : '']">
          <span class="step-icon">{{ loadingStep > 1 ? '✓' : '1' }}</span>
          <span>Analyzing content</span>
        </div>
        <div v-if="assignmentToolSettings.stylometry_enabled" :class="['print-step', loadingStep >= 2 ? 'active' : '', loadingStep > 2 ? 'done' : '']">
          <span class="step-icon">{{ loadingStep > 2 ? '✓' : '2' }}</span>
          <span>Verifying authorship</span>
        </div>
        <div v-if="assignmentToolSettings.gptzero_enabled" :class="['print-step', loadingStep >= 3 ? 'active' : '', loadingStep > 3 ? 'done' : '']">
          <span class="step-icon">{{ loadingStep > 3 ? '✓' : '3' }}</span>
          <span>True AI detection</span>
        </div>
        <div :class="['print-step', loadingStep >= 4 ? 'active' : '', loadingStep > 4 ? 'done' : '']">
          <span class="step-icon">{{ loadingStep > 4 ? '✓' : '4' }}</span>
          <span>Generating PDF</span>
        </div>
      </div>
    </div>
  </div>
  
  <iframe ref="iframeRef" class="umo-print-iframe" :srcdoc="iframeCode" />
</template>

<script setup>
import { getApiUrl } from '@/utils/api-url'
import { integrityLegacyMode } from '@/composables/feature-flags'

const { container, options, editor, printing, exportPDF, assignmentToolSettings } = useStore()
const { isStudent } = useAuth()

// A student's OWN print/export in new mode = clean content only (no integrity
// highlighting/reports). The submit-time report build (when the assignment submit
// callback is set) and the teacher path always stay full; legacy mode is unchanged.
function _cleanStudentOutput() {
  return isStudent.value && !integrityLegacyMode.value && !window._assignmentSubmitCallback
}

let iframeRef = $ref()
let iframeCode = $ref('')

// Loading state for PDF generation
let isGeneratingPDF = $ref(false)
let loadingMessage = $ref('Generating PDF...')
let loadingSubMessage = $ref('Please wait while we analyze your document')
let loadingProgress = $ref(0)
let loadingStep = $ref(0)

const getStylesHtml = () => {
  let styles = ''
  document
    .querySelectorAll('link, style')
    .forEach((style) => (styles += style.outerHTML + '\n'))
  return styles
}

const getPlyrSprite = () => {
  return document.querySelector('#sprite-plyr')?.innerHTML || ''
}

// Filter external pastes to only those whose text is present in the editor RIGHT NOW.
// Simple normalized text matching — no chunk/fragment matching.
// Called at submit time so editor content = what the student is submitting.
const filterPastesByEditorContent = (pastes) => {
  if (!pastes || pastes.length === 0) return []

  // Get current editor plain text
  const editorText = editor.value?.getText() || ''
  if (!editorText) return []

  // Normalize: lowercase, collapse whitespace, strip special chars
  const normalize = (str) => (str || '').toLowerCase().replace(/\s+/g, ' ').replace(/[^\w\s]/g, '').trim()
  const editorNorm = normalize(editorText)

  return pastes.filter(paste => {
    const pasteText = paste.text || ''
    if (pasteText.length < 20) return false

    const pasteNorm = normalize(pasteText)
    if (!pasteNorm) return false

    // Check if a substantial portion of the paste is in the editor.
    // Use sliding window: check if any 80-char contiguous block from the paste
    // appears in the editor text. This handles minor edits while rejecting deleted pastes.
    const WINDOW = Math.min(80, Math.floor(pasteNorm.length * 0.5))
    if (WINDOW < 15) return false

    // Check first window, middle window, and last window
    const checkPoints = [
      0,
      Math.floor(pasteNorm.length / 2) - Math.floor(WINDOW / 2),
      Math.max(0, pasteNorm.length - WINDOW)
    ]

    let matchCount = 0
    for (const start of checkPoints) {
      const snippet = pasteNorm.substring(start, start + WINDOW)
      if (snippet.length >= 15 && editorNorm.includes(snippet)) {
        matchCount++
      }
    }

    // At least 2 of 3 checkpoints must match (paste is substantially present)
    return matchCount >= 2
  })
}

const getContentHtml = () => {
  const { integrity } = useStore()
  
  // Get the base HTML
  let contentHtml = ''
  const editorElement = document.querySelector(`${container} .tiptap.umo-editor`)
  if (editorElement) {
    contentHtml = editorElement.innerHTML
  } else if (editor.value) {
    contentHtml = editor.value.getHTML()
  }
  
  if (!contentHtml) return ''

  // New mode: a student printing/exporting their own document gets clean content
  // only — no external-paste highlighting. (Submit artifact + teacher stay full.)
  if (_cleanStudentOutput()) return contentHtml

  // HIGHLIGHT EXTERNAL PASTED CONTENT IN RED FOR PRINT
  // Only highlight if content authenticity tool is enabled by teacher
  const _toolSettings = assignmentToolSettings?.value || {}
  const _integrityToolOn = _toolSettings.analyze_integrity_enabled !== false

  // Only show pastes that are present in the editor at submit time
  let externalPastes = _integrityToolOn ? filterPastesByEditorContent(integrity?.value?.externalPastesFound || []) : []
  let retypedExternal = _integrityToolOn ? (integrity?.value?.retypedExternalDetected || []) : []
  
  // FALLBACK: Only use INTEGRITY_DATABASE if IntegrityTracker hasn't analyzed yet
  // AND the submit pipeline hasn't started computing trust.
  // If analysis WAS run and externalPastesFound is empty, that means pastes were
  // deleted from the editor — respect that instead of showing stale session data.
  const _analysisCompleted = integrity?.value?.lastAnalyzed || integrity?.value?.scores?.trust != null
  if (externalPastes.length === 0 && !_analysisCompleted && window.INTEGRITY_DATABASE?.externalPastes?.length > 0) {
    console.log('🔄 Using INTEGRITY_DATABASE fallback for highlighting (no analysis yet)')
    externalPastes = window.INTEGRITY_DATABASE.externalPastes.map(p => ({
      text: p.text,
      id: p.id,
      preview: (p.text || '').substring(0, 50)
    }))
  }

  // ALSO try ProvenanceTracker segments (same guard)
  if (externalPastes.length === 0 && !_analysisCompleted && window.PROVENANCE_TRACKER?.segments?.length > 0) {
    console.log('🔄 Using PROVENANCE_TRACKER fallback for highlighting (no analysis yet)')
    const externalSegs = window.PROVENANCE_TRACKER.segments.filter(
      s => s.origin === 'EXTERNAL_PASTE' || s.origin === 'DERIVED_FROM_EXTERNAL'
    )
    externalPastes = externalSegs.map(seg => ({
      text: seg.text,
      id: seg.sourceHash || 'seg_' + seg.start,
      preview: (seg.text || '').substring(0, 50),
      origin: seg.origin
    }))
  }
  
  console.log('🖨️ Preparing content for print...')
  console.log('   External pastes to highlight:', externalPastes.length)
  console.log('   Retyped external to highlight:', retypedExternal.length)
  if (externalPastes.length > 0) {
    console.log('   First paste preview:', externalPastes[0]?.preview || 'N/A')
  }
  
  if (externalPastes.length > 0 || retypedExternal.length > 0) {
    // Combine all external content
    // Classify per-paste: matchPercent >= 90% = exact paste (EXTERNAL), < 90% = student modified (RETYPED)
    // Don't use retypedExternalDetected array — IntegrityTracker sets it to ALL pastes when any retyped exists
    const allExternal = externalPastes.map(p => {
      const isRetyped = p.matchPercent != null && p.matchPercent > 0 && p.matchPercent < 90
      return { text: p.text, type: isRetyped ? 'retyped' : 'paste', matchPercent: p.matchPercent }
    })
    
    // Sort by length (longest first to avoid partial replacements)
    allExternal.sort((a, b) => b.text.length - a.text.length)
    
    console.log('🔍 Highlighting', allExternal.length, 'segments in print output')
    
    // Get plain text version for better matching
    const tempDiv = document.createElement('div')
    tempDiv.innerHTML = contentHtml
    const plainText = tempDiv.textContent || tempDiv.innerText || ''
    
    console.log('📄 Plain text length:', plainText.length)
    console.log('📄 HTML length:', contentHtml.length)
    console.log('📄 Sample plain text:', plainText.substring(0, 200) + '...')
    console.log('📄 Sample HTML:', contentHtml.substring(0, 300) + '...')
    
    // Use multiple approaches to find and highlight external content
    for (const item of allExternal) {
      const searchText = item.text.trim()
      if (!searchText) continue

      console.log(`🔍 Looking for: "${searchText.substring(0, 60)}..."`)

      // Get normalized versions for comparison
      const normalizeText = (text) => {
        return text
          .toLowerCase()
          .replace(/<[^>]*>/g, '')  // Remove HTML tags
          .replace(/&[a-zA-Z0-9#]+;/g, ' ')  // Remove HTML entities
          .replace(/[^\w\s]/g, ' ')  // Keep only letters, numbers, spaces
          .replace(/\s+/g, ' ')
          .trim()
      }

      const searchNormalized = normalizeText(searchText)
      const contentNormalized = normalizeText(plainText)

      console.log(`   Search length: ${searchText.length}, Content length: ${plainText.length}`)
      console.log(`   Normalized match? ${contentNormalized.includes(searchNormalized) ? 'YES ✅' : 'NO ❌'}`)

      if (!contentNormalized.includes(searchNormalized)) {
        console.log(`   ⚠️ No normalized match, trying word-based approach...`)

        // Try word overlap analysis (like the main system)
        const searchWords = normalizeText(searchText).split(/\s+/).filter(w => w.length > 2)
        const contentWords = normalizeText(plainText).split(/\s+/).filter(w => w.length > 2)

        if (searchWords.length > 5 && contentWords.length > 0) {
          const matchingWords = searchWords.filter(w => contentWords.includes(w))
          const matchRatio = (matchingWords.length / searchWords.length) * 100

          console.log(`   Word overlap: ${matchRatio.toFixed(1)}% (${matchingWords.length}/${searchWords.length})`)

          if (matchRatio > 70) {
            console.log(`   ✅ High word overlap, highlighting common phrases...`)

            // Find 3-5 word phrases that exist in both
            const foundPhrases = []
            for (let i = 0; i < searchWords.length - 2; i++) {
              const phrase = searchWords.slice(i, i + 3).join(' ')
              if (contentNormalized.includes(phrase)) {
                foundPhrases.push(phrase)
              }
            }

            // Highlight the longest phrases first (up to 3)
            const phrasesToHighlight = foundPhrases
              .sort((a, b) => b.length - a.length)
              .slice(0, 3)

            for (const phrase of phrasesToHighlight) {
              // Find this phrase in the original HTML (case-insensitive)
              const phraseRegex = new RegExp(`(${phrase.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')})`, 'gi')

              // Create highlight HTML
              const bgColor = item.type === 'retyped' ? '#fff3e0' : '#ffcccc'
              const borderColor = item.type === 'retyped' ? '#ff9800' : '#f44336'
              const label = item.type === 'retyped' ? 'RETYPED' : 'EXTERNAL'

              const highlightHtml = `<mark style="background-color: ${bgColor}; color: #000; padding: 2px 3px; border-radius: 2px; border-bottom: 2px solid ${borderColor}; font-weight: 500;" data-integrity="${item.type}">$1<sup style="color: ${borderColor}; font-size: 8px; font-weight: 700; margin-left: 1px;">[${label}]</sup></mark>`

              // Apply highlighting
              const beforeReplace = contentHtml
              contentHtml = contentHtml.replace(phraseRegex, highlightHtml)

              if (contentHtml !== beforeReplace) {
                console.log(`   ✅ Highlighted phrase: "${phrase}"`)
              }
            }

            continue // Skip to next item
          }
        }

        console.log(`   ❌ Could not match content, skipping`)
        continue
      }

      // We have a normalized match — this paste IS in the document.
      // Highlight all paragraphs/elements whose normalized text overlaps with the paste.
      const bgColor = item.type === 'retyped' ? '#fff3e0' : '#ffcccc'
      const borderColor = item.type === 'retyped' ? '#ff9800' : '#f44336'
      const label = item.type === 'retyped' ? 'RETYPED' : 'EXTERNAL'

      console.log(`   ✅ Normalized match found, highlighting matching paragraphs...`)

      const highlightContainer = document.createElement('div')
      highlightContainer.innerHTML = contentHtml

      // Build a set of normalized 8-word sequences from the paste for matching
      const pasteWords = searchNormalized.split(/\s+/).filter(w => w.length > 1)
      const pasteSequences = new Set()
      for (let i = 0; i <= pasteWords.length - 6; i++) {
        pasteSequences.add(pasteWords.slice(i, i + 6).join(' '))
      }

      let highlighted = false

      // Walk text nodes and find the exact range that matches the paste
      const walker = document.createTreeWalker(highlightContainer, NodeFilter.SHOW_TEXT, null, false)
      let textNode
      // Collect all text nodes with their normalized text
      const textNodes = []
      while (textNode = walker.nextNode()) {
        if (textNode.textContent.trim().length > 0) {
          textNodes.push(textNode)
        }
      }

      // Build a concatenated normalized text and map character positions to nodes
      let concatNorm = ''
      const nodeMap = [] // [{node, startIdx, endIdx}]
      for (const tn of textNodes) {
        const tnNorm = normalizeText(tn.textContent)
        const startIdx = concatNorm.length
        concatNorm += tnNorm + ' '
        nodeMap.push({ node: tn, startIdx, endIdx: concatNorm.length - 1 })
      }

      // Find paste text in the RAW (non-normalized) content using the original search text
      // We need to find the actual character position in the original text node
      const pasteStart = concatNorm.indexOf(searchNormalized)
      if (pasteStart !== -1) {
        const pasteEnd = pasteStart + searchNormalized.length

        for (const nm of nodeMap) {
          if (nm.endIdx <= pasteStart || nm.startIdx >= pasteEnd) continue
          if (nm.node.parentNode.closest && nm.node.parentNode.closest('mark[data-integrity]')) continue

          const nodeText = nm.node.textContent
          const nodeNorm = normalizeText(nodeText)

          // If the paste starts INSIDE this node (not at the beginning),
          // we need to split the node and only highlight the paste portion
          const pasteOffsetInNode = Math.max(0, pasteStart - nm.startIdx)
          const pasteEndInNode = Math.min(nodeNorm.length, pasteEnd - nm.startIdx)

          // Map normalized offset back to original text position (approximate)
          // Use the ratio of normalized position to normalized length
          const origStart = Math.round((pasteOffsetInNode / Math.max(1, nodeNorm.length)) * nodeText.length)
          const origEnd = Math.round((pasteEndInNode / Math.max(1, nodeNorm.length)) * nodeText.length)

          const beforeText = nodeText.substring(0, origStart)
          const matchText = nodeText.substring(origStart, origEnd)
          const afterText = nodeText.substring(origEnd)

          const fragment = document.createDocumentFragment()

          if (beforeText) {
            fragment.appendChild(document.createTextNode(beforeText))
          }

          if (matchText) {
            const mark = document.createElement('mark')
            mark.setAttribute('data-integrity', item.type)
            mark.style.cssText = `background-color:${bgColor};color:#000;padding:2px 4px;border-radius:3px;border-bottom:3px solid ${borderColor};font-weight:500;display:inline;`
            mark.textContent = matchText
            fragment.appendChild(mark)
            highlighted = true
          }

          if (afterText) {
            fragment.appendChild(document.createTextNode(afterText))
          }

          nm.node.parentNode.replaceChild(fragment, nm.node)
        }

        // Add [EXTERNAL] label after last highlighted mark
        if (highlighted) {
          const allMarks = highlightContainer.querySelectorAll('mark[data-integrity]')
          const lastMark = allMarks[allMarks.length - 1]
          if (lastMark) {
            const sup = document.createElement('sup')
            sup.style.cssText = `color:${borderColor};font-size:9px;font-weight:700;margin-left:2px;`
            sup.textContent = `[${label}]`
            lastMark.appendChild(sup)
          }
        }
      }

      // Fallback: if exact normalized substring not found, try block-level matching
      if (!highlighted) {
        const blocks = highlightContainer.querySelectorAll('p, h1, h2, h3, h4, h5, h6, li')
        for (const block of blocks) {
          const blockText = block.textContent || ''
          if (blockText.trim().length < 10) continue

          const blockNorm = normalizeText(blockText)
          const blockWords = blockNorm.split(/\s+/).filter(w => w.length > 1)

          let matchCount = 0
          for (let i = 0; i <= blockWords.length - 6; i++) {
            const seq = blockWords.slice(i, i + 6).join(' ')
            if (pasteSequences.has(seq)) matchCount++
          }

          // Only highlight if >80% of block matches AND block is predominantly paste content
          const blockSequenceCount = Math.max(1, blockWords.length - 5)
          const matchRatio = matchCount / blockSequenceCount
          if (matchRatio > 0.8 && matchCount >= 5) {
            if (block.closest('mark[data-integrity]')) continue

            const mark = document.createElement('mark')
            mark.setAttribute('data-integrity', item.type)
            mark.style.cssText = `background-color:${bgColor};color:#000;padding:3px 5px;border-radius:3px;border-bottom:3px solid ${borderColor};font-weight:500;display:inline;`

            while (block.firstChild) mark.appendChild(block.firstChild)

            const sup = document.createElement('sup')
            sup.style.cssText = `color:${borderColor};font-size:9px;font-weight:700;margin-left:2px;`
            sup.textContent = `[${label}]`
            mark.appendChild(sup)

            block.appendChild(mark)
            highlighted = true
          }
        }
      }

      if (!highlighted) {
        console.log(`   ⚠️ No paragraphs matched, trying text node fallback...`)

        // Fallback: find text nodes with normalized match on first 5 significant words
        const firstWords = pasteWords.slice(0, 5).join(' ')
        const walker = document.createTreeWalker(highlightContainer, NodeFilter.SHOW_TEXT, null, false)
        let node
        while (node = walker.nextNode()) {
          if (normalizeText(node.textContent).includes(firstWords) && node.textContent.trim().length > 20) {
            const mark = document.createElement('mark')
            mark.setAttribute('data-integrity', item.type)
            mark.style.cssText = `background-color:${bgColor};color:#000;padding:2px 3px;border-radius:2px;border-bottom:2px solid ${borderColor};font-weight:500;`
            mark.textContent = node.textContent
            const sup = document.createElement('sup')
            sup.style.cssText = `color:${borderColor};font-size:8px;font-weight:700;margin-left:1px;`
            sup.textContent = `[${label}]`
            mark.appendChild(sup)
            node.parentNode.replaceChild(mark, node)
            highlighted = true
            break
          }
        }
      }

      if (!highlighted) {
        console.log(`   ❌ Could not highlight ${item.type} - trying paragraph-level fallback...`)

        const firstWord = pasteWords[0]
        const secondWord = pasteWords[1]

        if (firstWord && secondWord) {
          const walker4 = document.createTreeWalker(
            highlightContainer,
            NodeFilter.SHOW_ELEMENT,
            null,
            false
          )

          let element
          while (element = walker4.nextNode()) {
            if (element.tagName === 'P' || element.tagName === 'DIV' || element.tagName === 'H1' || element.tagName === 'H2') {
              const elementText = element.textContent || ''
              if (normalizeText(elementText).includes(firstWord) && normalizeText(elementText).includes(secondWord)) {
                const wrapper = document.createElement('div')
                wrapper.style.borderLeft = `4px solid ${borderColor}`
                wrapper.style.padding = '10px'
                wrapper.style.margin = '5px 0'
                wrapper.style.backgroundColor = item.type === 'retyped' ? 'rgba(255, 243, 224, 0.3)' : 'rgba(255, 204, 204, 0.3)'

                // Add label at the top
                const labelDiv = document.createElement('div')
                labelDiv.style.fontSize = '10px'
                labelDiv.style.fontWeight = '700'
                labelDiv.style.color = borderColor
                labelDiv.style.marginBottom = '5px'
                labelDiv.style.textTransform = 'uppercase'
                labelDiv.textContent = `${label} CONTENT DETECTED`

                wrapper.appendChild(labelDiv)

                // Move all children to wrapper
                while (element.firstChild) {
                  wrapper.appendChild(element.firstChild)
                }

                element.parentNode.replaceChild(wrapper, element)
                highlighted = true
                console.log(`   ✅ Successfully highlighted paragraph as ${item.type}`)
                break
              }
            }
          }
        }
      }

      if (!highlighted) {
        console.log(`   ❌ FINAL: Could not highlight ${item.type} - text not found in any form`)
        console.log(`   📝 This content will only appear in the integrity report`)
      }

      if (highlighted) {
        console.log(`   ✅ Successfully highlighted ${item.type}`)
      } else {
        console.log(`   ❌ Could not highlight ${item.type} - text not found in rendered HTML`)
      }

      // Convert back to HTML string
      contentHtml = highlightContainer.innerHTML
    }
    
    console.log('✅ Print content highlighting complete')

    // Verify highlighting worked
    const finalDiv = document.createElement('div')
    finalDiv.innerHTML = contentHtml
    const highlightedElements = finalDiv.querySelectorAll('mark[data-integrity]')
    console.log(`🎯 Final result: ${highlightedElements.length} elements highlighted in print output`)

    if (highlightedElements.length > 0) {
      console.log('🎉 SUCCESS: External content will be highlighted in PDF!')
      highlightedElements.forEach((el, i) => {
        console.log(`   ${i + 1}. ${(el.getAttribute('data-integrity') || '').toUpperCase()}: "${(el.textContent || '').substring(0, 50)}..."`)
      })
    } else {
      console.log('⚠️ WARNING: No content was highlighted in print output')
      console.log('📄 Final HTML sample:', (contentHtml || '').substring(0, 500) + '...')
    }
  }

  return contentHtml
}

const defaultLineHeight = $computed(() => {
  return options.value.dicts.lineHeights.find((item) => item.default).value
})

// Helper to get trust score from IntegrityTracker (current document state)
const getLegendTrustScore = () => {
  const { integrity, editor } = useStore()
  
  // Typing-provenance trust score (individual signal; no composite exists)
  let trustScore = integrity.value.scores?.trust

  // Fallback 1: PROVENANCE_TRACKER (only if no score calculated yet)
  if ((trustScore === undefined || trustScore === null) && window.PROVENANCE_TRACKER?.segments?.length > 0) {
    const currentText = editor.value?.getText() || ''
    const provenance = window.PROVENANCE_TRACKER.getProvenanceSummary(currentText)
    if (provenance.counts.EXTERNAL_PASTE > 0 || provenance.counts.DERIVED_FROM_EXTERNAL > 0) {
      trustScore = provenance.trustScore
    }
  }
  
  // Fallback 2: INTEGRITY_DATABASE session totals (last resort only)
  if ((trustScore === undefined || trustScore === null) && window.INTEGRITY_DATABASE) {
    const totalTyped = window.INTEGRITY_DATABASE.totalTypedChars || 0
    const totalExternal = window.INTEGRITY_DATABASE.totalExternalPastedChars || 0
    const total = totalTyped + totalExternal
    if (total > 0 && totalExternal > 0) {
      trustScore = Math.round((totalTyped / total) * 100)
    }
  }
  
  return trustScore ?? 0
}

// Get stylometry section for PDF report
const getStylometrySection = () => {
  console.log('═══════════════════════════════════════════════════════════')
  console.log('📊 BUILDING STYLOMETRY SECTION FOR PDF')
  console.log('   stylometryResult exists:', !!stylometryResult)
  console.log('   stylometryResult value:', JSON.stringify(stylometryResult))
  console.log('═══════════════════════════════════════════════════════════')

  // CHUNK OVERRIDE: When chunk analysis detected mixed content, replace entire card
  if (chunkAnalysisResult?.any_flagged) {
    const flagged = chunkAnalysisResult.chunks.filter(c => c.flagged)
    const clean = chunkAnalysisResult.chunks.filter(c => !c.flagged)
    const total = chunkAnalysisResult.chunks.length
    const worstAi = Math.max(...flagged.map(c => c.ai_probability || 0))
    const wholeDocAi = Math.round((aiDetectionResult?.ai_probability || 0) * 100)
    // Only treat AI as a factor when a chunk was actually flagged for AI (or has a non-zero score).
    // Showing "AI Prob 0%" on a style-only flag is misleading.
    const anyAiFlag = flagged.some(c => c.flag_reasons?.includes('ai_detected') || (c.ai_probability || 0) > 0)

    // Git-diff style: full text on left with red highlight, scores column on right
    const flaggedRows = flagged.map((c, idx) => {
      const aiPct = Math.round((c.ai_probability || 0) * 100)
      const showAi = c.flag_reasons?.includes('ai_detected') || aiPct > 0
      const styloLabel = c.stylo_verdict === 'flagged' ? 'Mismatch' : (c.stylo_verdict || 'N/A')
      const cosineVal = c.stylo_cosine != null ? c.stylo_cosine.toFixed(2) : '—'
      const aiColor = aiPct > 70 ? '#dc2626' : aiPct > 30 ? '#f59e0b' : '#10b981'
      const styloColor = c.stylo_verdict === 'flagged' ? '#dc2626' : '#10b981'
      // Get full chunk text from flagged_chunks_text array
      const fullText = chunkAnalysisResult.flagged_chunks_text?.[idx] || c.text_preview || ''
      // Escape HTML in the text
      const escapedText = fullText.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
      return `<div style="border-radius:10px;margin-bottom:10px;border:2px solid #fca5a5;overflow:hidden;">
        <div style="display:flex;min-height:80px;">
          <div style="flex:1;padding:14px 16px;background:linear-gradient(135deg, #fff5f5, #fef2f2);border-right:2px solid #fca5a5;">
            <div style="font-size:11px;font-weight:700;color:#dc2626;margin-bottom:8px;text-transform:uppercase;letter-spacing:0.5px;">⚠️ Flagged · ${c.word_count} words</div>
            <div style="font-size:12px;color:#374151;line-height:1.6;font-family:Georgia,serif;background:rgba(239,68,68,0.06);padding:10px 12px;border-radius:6px;border-left:3px solid #ef4444;max-height:200px;overflow-y:auto;">${escapedText}</div>
          </div>
          <div style="width:120px;padding:12px 10px;display:flex;flex-direction:column;justify-content:center;gap:6px;background:#fef2f2;">
            ${showAi ? `<div style="text-align:center;">
              <div style="font-size:9px;color:#6b7280;text-transform:uppercase;letter-spacing:0.5px;margin-bottom:2px;">AI Prob</div>
              <div style="font-size:28px;font-weight:800;color:${aiColor};line-height:1;">${aiPct}%</div>
            </div>` : ''}
            <div style="${showAi ? 'border-top:1px solid #fca5a5;padding-top:6px;' : ''}text-align:center;">
              <div style="font-size:9px;color:#6b7280;text-transform:uppercase;letter-spacing:0.5px;margin-bottom:2px;">Style</div>
              <div style="font-size:15px;font-weight:700;color:${styloColor};">${styloLabel}</div>
              <div style="font-size:10px;color:#9ca3af;">${cosineVal}</div>
            </div>
          </div>
        </div>
      </div>`
    }).join('')

    return `
      <div style="background: white; border-radius: 20px; padding: 30px; margin-bottom: 30px; box-shadow: 0 10px 40px rgba(0,0,0,0.08); border: 2px solid #fca5a5;">
        <h3 style="margin: 0 0 20px 0; color: #1f2937; font-size: 18px; font-weight: 600; display: flex; align-items: center;">
          <span style="display: inline-block; width: 4px; height: 24px; background: #ef4444; margin-right: 12px; border-radius: 2px;"></span>
          Authorship &amp; AI Analysis (Per-Section)
        </h3>
        <div style="background: #fef2f2; border: 1px solid #fca5a5; border-radius: 12px; padding: 16px; margin-bottom: 16px;">
          <div style="display: flex; align-items: center; gap: 10px; margin-bottom: 8px;">
            <span style="font-size: 24px;">⚠️</span>
            <div>
              <div style="font-size: 16px; font-weight: 700; color: #dc2626;">${anyAiFlag ? 'Mixed Content Detected' : 'Writing-Style Mismatch'}</div>
              <div style="font-size: 13px; color: #991b1b;">${flagged.length} of ${total} sections flagged for ${anyAiFlag ? 'AI content or style mismatch' : 'writing-style mismatch'}</div>
            </div>
          </div>
        </div>

        ${clean.length > 0 ? `
          <div style="background:#f0fdf4;padding:10px 14px;border-radius:10px;margin-bottom:12px;border-left:3px solid #10b981;font-size:13px;color:#065f46;">
            ✓ ${clean.length} section${clean.length > 1 ? 's' : ''} verified clean (human-written, style matches student)
          </div>
        ` : ''}

        ${flaggedRows}

        ${anyAiFlag ? `<div style="margin-top: 14px; padding: 12px; background: #f9fafb; border-radius: 8px; font-size: 12px; color: #6b7280;">
          <strong>Why the score difference:</strong> Whole-doc AI shows ${wholeDocAi}% because human text dilutes the signal. Per-section analysis catches what whole-doc misses.
        </div>` : ''}
      </div>
    `
  }

  // Check if API was skipped (100% external paste)
  if (stylometryResult?.skipped) {
    console.log('⚠️ Stylometry SKIPPED - external paste detected')
    return `
      <div style="background: white; border-radius: 20px; padding: 30px; margin-bottom: 30px; box-shadow: 0 10px 40px rgba(0,0,0,0.08);">
        <h3 style="margin: 0 0 25px 0; color: #1f2937; font-size: 18px; font-weight: 600; display: flex; align-items: center;">
          <span style="display: inline-block; width: 4px; height: 24px; background: #8b5cf6; margin-right: 12px; border-radius: 2px;"></span>
          Authorship Check
        </h3>
        <div style="background: linear-gradient(135deg, #fef2f2, #fee2e2); border: 2px solid #fca5a5; border-radius: 16px; padding: 25px; text-align: center;">
          <div style="font-size: 48px; margin-bottom: 15px;">⏭️</div>
          <div style="font-size: 18px; font-weight: 700; color: #dc2626; margin-bottom: 8px;">Verification Skipped</div>
          <div style="font-size: 14px; color: #6b7280; margin-bottom: 15px;">${stylometryResult.message || 'No original content to verify'}</div>
          <div style="background: white; border-radius: 10px; padding: 15px; text-align: left;">
            <div style="font-size: 12px; color: #374151;">
              <strong>💡 Why was this skipped?</strong><br>
              <span style="color: #6b7280;">The document contains 98%+ externally pasted content. Stylometry requires original typed content to analyze writing style patterns.</span>
            </div>
          </div>
        </div>
      </div>
    `
  }
  
  // Always show stylometry section - even if verification failed, show why
  if (!stylometryResult) {
    console.log('⚠️ stylometryResult is NULL - showing pending message')
    // Show that stylometry wasn't run
    return `
      <div style="background: white; border-radius: 20px; padding: 30px; margin-bottom: 30px; box-shadow: 0 10px 40px rgba(0,0,0,0.08);">
        <h3 style="margin: 0 0 25px 0; color: #1f2937; font-size: 18px; font-weight: 600; display: flex; align-items: center;">
          <span style="display: inline-block; width: 4px; height: 24px; background: #8b5cf6; margin-right: 12px; border-radius: 2px;"></span>
          Authorship Check
        </h3>
        <div style="background: #f3f4f6; border-radius: 16px; padding: 25px; text-align: center;">
          <div style="font-size: 48px; margin-bottom: 15px;">⏳</div>
          <div style="font-size: 18px; font-weight: 600; color: #374151; margin-bottom: 8px;">Verification Pending</div>
          <div style="font-size: 14px; color: #6b7280;">Stylometry verification was not performed for this document</div>
        </div>
      </div>
    `
  }
  
  // V3 fields — cosine_score is the real similarity metric
  const isV3 = stylometryResult.version === 'v3' || stylometryResult.cosine_score !== undefined
  const cosineScore = stylometryResult.cosine_score ?? stylometryResult.score ?? stylometryResult.similarity ?? 0
  const cosinePercent = Math.round(cosineScore * 100)
  const confidence = stylometryResult.confidence || null
  const profileStrength = stylometryResult.profile_strength || null
  const baselineWords = stylometryResult.baseline_words || stylometryResult.submission_word_count || 0
  const baselineSamples = stylometryResult.baseline_samples || stylometryResult.n_profile_essays || 0
  const flags = stylometryResult.flags || []
  const verdict = stylometryResult.verdict
  const status = stylometryResult.status || stylometryResult.reason || 'unknown'
  const verified = verdict === 'verified' || stylometryResult.verified === true
  
  let statusColor, statusBg, statusIcon, statusText, statusDescription

  if (verdict === 'verified' || verified === true) {
    statusColor = '#10b981'
    statusBg = 'linear-gradient(135deg, #10b981 0%, #059669 100%)'
    statusIcon = '✓'
    statusText = 'Written by This Student'
    statusDescription = `Writing style matches the student's profile${confidence ? ` (${confidence} confidence)` : ''}`
  } else if (verdict === 'flagged' || stylometryResult.verified === false) {
    statusColor = '#ef4444'
    statusBg = 'linear-gradient(135deg, #ef4444 0%, #dc2626 100%)'
    statusIcon = '⚠'
    statusText = 'May Not Be This Student\'s Writing'
    statusDescription = `Writing style does not match the student's profile${confidence ? ` (${confidence} confidence)` : ''}`
  } else if (verdict === 'review_required') {
    statusColor = '#f59e0b'
    statusBg = 'linear-gradient(135deg, #f59e0b 0%, #d97706 100%)'
    statusIcon = '?'
    statusText = 'Needs Review'
    statusDescription = `Writing style is a borderline match${confidence ? ` (${confidence} confidence)` : ''} — manual review recommended`
  } else if (verdict === 'inconclusive' || status === 'uncertain') {
    statusColor = '#f59e0b'
    statusBg = 'linear-gradient(135deg, #f59e0b 0%, #d97706 100%)'
    statusIcon = '?'
    statusText = 'Not Enough Data'
    statusDescription = 'Not enough writing samples to determine authorship'
  } else if (status === 'not_enrolled') {
    statusColor = '#6b7280'
    statusBg = 'linear-gradient(135deg, #6b7280 0%, #4b5563 100%)'
    statusIcon = '○'
    statusText = 'Not Enrolled'
    statusDescription = 'Student has not completed stylometry enrollment for this course'
  } else if (status === 'v3_error' || status === 'api_error' || status === 'network_error') {
    statusColor = '#6b7280'
    statusBg = 'linear-gradient(135deg, #6b7280 0%, #4b5563 100%)'
    statusIcon = '⚡'
    statusText = 'Service Unavailable'
    statusDescription = 'Stylometry service temporarily unavailable'
  } else if (status === 'document_too_short' || stylometryResult.reason === 'document_too_short') {
    statusColor = '#f59e0b'
    statusBg = 'linear-gradient(135deg, #f59e0b 0%, #d97706 100%)'
    statusIcon = '📝'
    statusText = 'Document Too Short'
    statusDescription = `Need at least 50 words for verification (currently ${stylometryResult.wordCount || 0} words)`
  } else {
    statusColor = '#6b7280'
    statusBg = 'linear-gradient(135deg, #6b7280 0%, #4b5563 100%)'
    statusIcon = '–'
    statusText = 'Unavailable'
    statusDescription = 'Stylometry verification could not be performed'
  }
  
  return `
    <div style="background: white; border-radius: 20px; padding: 30px; margin-bottom: 30px; box-shadow: 0 10px 40px rgba(0,0,0,0.08); page-break-inside: avoid;">
      <h3 style="margin: 0 0 25px 0; color: #1f2937; font-size: 18px; font-weight: 600;">
        <span style="display: inline-block; width: 4px; height: 24px; background: #8b5cf6; margin-right: 12px; border-radius: 2px; vertical-align: middle;"></span>
        Authorship Check
      </h3>
      
      <!-- Stack layout for better print compatibility -->
      <div style="display: block;">
        <!-- Main Status Card -->
        <div style="background: ${statusBg}; border-radius: 16px; padding: 25px; color: white; position: relative; overflow: visible; margin-bottom: 20px;">
          <div style="display: block;">
            <div style="display: inline-block; width: 50px; height: 50px; background: rgba(255,255,255,0.2); border-radius: 50%; text-align: center; line-height: 50px; font-size: 24px; font-weight: bold; vertical-align: middle; margin-right: 15px;">
              ${statusIcon}
            </div>
            <div style="display: inline-block; vertical-align: middle; max-width: calc(100% - 80px);">
              <div style="font-size: 22px; font-weight: 700; white-space: nowrap;">${statusText}</div>
              <div style="font-size: 13px; opacity: 0.9; margin-top: 4px;">${statusDescription}</div>
            </div>
          </div>
          
          ${verified !== null ? `
            <div style="background: rgba(255,255,255,0.15); border-radius: 10px; padding: 15px; margin-top: 20px; text-align: center;">
              <div style="font-size: 13px; opacity: 0.8; margin-bottom: 5px;">Style Similarity</div>
              <div style="font-size: 48px; font-weight: 800;">${cosinePercent}%</div>
            </div>
          ` : ''}
        </div>
        
        <!-- Details Panel -->
        <div style="background: #f9fafb; border-radius: 16px; padding: 25px;">
          <div style="margin-bottom: 20px;">
            <div style="font-size: 13px; color: #6b7280; text-transform: uppercase; letter-spacing: 1px; margin-bottom: 12px; font-weight: 600;">Student's Writing Profile</div>
            <table style="width: 100%; border-collapse: separate; border-spacing: 15px 0;">
              <tr>
                <td style="width: 33%; background: white; border-radius: 10px; padding: 20px; text-align: center; border: 1px solid #e5e7eb;">
                  <div style="font-size: 32px; font-weight: 700; color: #8b5cf6;">${baselineSamples}</div>
                  <div style="font-size: 13px; color: #6b7280; margin-top: 5px;">Writing Samples</div>
                </td>
                <td style="width: 33%; background: white; border-radius: 10px; padding: 20px; text-align: center; border: 1px solid #e5e7eb;">
                  <div style="font-size: 32px; font-weight: 700; color: #8b5cf6;">${baselineWords.toLocaleString()}</div>
                  <div style="font-size: 13px; color: #6b7280; margin-top: 5px;">Words Analyzed</div>
                </td>
                <td style="width: 33%; background: white; border-radius: 10px; padding: 20px; text-align: center; border: 1px solid #e5e7eb;">
                  <div style="font-size: 16px; font-weight: 700; color: #8b5cf6; text-transform: capitalize;">${profileStrength || 'N/A'}</div>
                  <div style="font-size: 13px; color: #6b7280; margin-top: 5px;">Profile Strength</div>
                </td>
              </tr>
            </table>
          </div>
          
          ${verified !== null ? `
            <div style="margin-bottom: 20px;">
              <div style="font-size: 13px; color: #6b7280; text-transform: uppercase; letter-spacing: 1px; margin-bottom: 12px; font-weight: 600;">Style Similarity</div>
              <div style="background: white; border-radius: 10px; padding: 20px; border: 1px solid #e5e7eb;">
                <div style="margin-bottom: 12px;">
                  <span style="font-size: 14px; color: #374151;">How closely does this match the student's writing?</span>
                  <span style="font-size: 16px; font-weight: 700; color: ${statusColor}; float: right;">${cosinePercent}%</span>
                </div>
                <div style="background: #e5e7eb; height: 12px; border-radius: 6px; overflow: hidden;">
                  <div style="background: ${statusColor}; width: ${cosinePercent}%; height: 100%; border-radius: 6px;"></div>
                </div>
                <div style="margin-top: 10px; font-size: 11px; color: #9ca3af;">
                  <span style="float: left;">0% - Different author</span>
                  <span style="float: right;">100% - Same author</span>
                </div>
              </div>
            </div>
          ` : ''}
          
          ${flags.length > 0 ? `
            <div>
              <div style="font-size: 13px; color: #6b7280; text-transform: uppercase; letter-spacing: 1px; margin-bottom: 12px; font-weight: 600;">Analysis Flags</div>
              <div>
                ${flags.map(flag => `
                  <span style="display: inline-block; background: #fef3c7; color: #92400e; padding: 6px 14px; border-radius: 12px; font-size: 12px; font-weight: 500; margin: 4px;">
                    ${flag}
                  </span>
                `).join('')}
              </div>
            </div>
          ` : ''}
        </div>
      </div>
      
      <div style="margin-top: 20px; padding: 15px 20px; background: #f0f9ff; border-radius: 10px; border-left: 4px solid #0ea5e9;">
        <div style="font-size: 14px; font-weight: 600; color: #0369a1; margin-bottom: 5px;">How does this work?</div>
        <div style="font-size: 12px; color: #0c4a6e; line-height: 1.5;">
          We compare this submission's writing style against ${baselineSamples} previous writing samples from this student.
          The style similarity score (${cosinePercent}%) measures how closely this text matches the student's known writing patterns.
          ${verified === true ? ' This submission is consistent with how this student normally writes.' : ''}
          ${verified === false ? ' This submission differs from how this student normally writes.' : ''}
        </div>
      </div>
    </div>
  `
}

// Get AI Detection section for PDF report
const getAIDetectionSection = () => {
  console.log('═══════════════════════════════════════════════════════════')
  console.log('🤖 BUILDING AI DETECTION SECTION FOR PDF')
  console.log('   aiDetectionResult exists:', !!aiDetectionResult)
  console.log('   aiDetectionResult value:', JSON.stringify(aiDetectionResult))
  console.log('═══════════════════════════════════════════════════════════')

  // CHUNK OVERRIDE: When chunk analysis detected AI in sections, show per-section AI results
  const chunkAiFlagged = chunkAnalysisResult?.any_flagged && chunkAnalysisResult.chunks?.some(c => c.flag_reasons?.includes('ai_detected'))
  if (chunkAiFlagged) {
    const flaggedAi = chunkAnalysisResult.chunks.filter(c => c.flag_reasons?.includes('ai_detected'))
    const worstAi = Math.max(...flaggedAi.map(c => c.ai_probability || 0))
    const wholeDocAi = Math.round((aiDetectionResult?.ai_probability || 0) * 100)
    return `
      <div style="background: white; border-radius: 20px; padding: 30px; margin-bottom: 30px; box-shadow: 0 10px 40px rgba(0,0,0,0.08); border: 2px solid #fca5a5;">
        <h3 style="margin: 0 0 20px 0; color: #1f2937; font-size: 18px; font-weight: 600; display: flex; align-items: center;">
          <span style="display: inline-block; width: 4px; height: 24px; background: #ef4444; margin-right: 12px; border-radius: 2px;"></span>
          AI Content Detection
        </h3>
        <div style="background: #fef2f2; border: 1px solid #fca5a5; border-radius: 12px; padding: 16px; margin-bottom: 16px;">
          <div style="display: flex; align-items: center; gap: 10px;">
            <span style="font-size: 24px;">⚠️</span>
            <div>
              <div style="font-size: 16px; font-weight: 700; color: #dc2626;">AI Content Detected in ${flaggedAi.length} Section(s)</div>
              <div style="font-size: 13px; color: #991b1b;">Worst section: ${Math.round(worstAi * 100)}% AI probability</div>
            </div>
          </div>
        </div>
        <div style="display: flex; gap: 16px; margin-bottom: 16px;">
          <div style="flex: 1; background: #f9fafb; border-radius: 10px; padding: 14px; text-align: center;">
            <div style="font-size: 12px; color: #6b7280; margin-bottom: 4px;">Whole-Doc AI</div>
            <div style="font-size: 24px; font-weight: 700; color: #10b981;">${wholeDocAi}%</div>
            <div style="font-size: 11px; color: #9ca3af;">diluted</div>
          </div>
          <div style="flex: 1; background: #fef2f2; border-radius: 10px; padding: 14px; text-align: center;">
            <div style="font-size: 12px; color: #6b7280; margin-bottom: 4px;">Worst Section AI</div>
            <div style="font-size: 24px; font-weight: 700; color: #dc2626;">${Math.round(worstAi * 100)}%</div>
            <div style="font-size: 11px; color: #dc2626;">per-section</div>
          </div>
        </div>
        <div style="font-size: 12px; color: #6b7280; background: #f9fafb; border-radius: 8px; padding: 12px;">
          <strong>Why the difference?</strong> When AI and human text are mixed in one document, whole-document AI detection averages the signals, producing a misleadingly low score. Per-section analysis catches what whole-doc misses.
        </div>
      </div>
    `
  }

  // Check if API was skipped (100% external paste)
  if (aiDetectionResult?.skipped) {
    console.log('⚠️ AI Detection SKIPPED - external paste detected')
    return `
      <div style="background: white; border-radius: 20px; padding: 30px; margin-bottom: 30px; box-shadow: 0 10px 40px rgba(0,0,0,0.08); page-break-inside: avoid;">
        <h3 style="margin: 0 0 25px 0; color: #1f2937; font-size: 18px; font-weight: 600;">
          <span style="display: inline-block; width: 4px; height: 24px; background: #0ea5e9; margin-right: 12px; border-radius: 2px; vertical-align: middle;"></span>
          AI Content Detection
        </h3>
        <div style="background: linear-gradient(135deg, #fef2f2, #fee2e2); border: 2px solid #fca5a5; border-radius: 16px; padding: 25px; text-align: center;">
          <div style="font-size: 48px; margin-bottom: 15px;">⏭️</div>
          <div style="font-size: 18px; font-weight: 700; color: #dc2626; margin-bottom: 8px;">Detection Skipped</div>
          <div style="font-size: 14px; color: #6b7280; margin-bottom: 15px;">${aiDetectionResult.message || 'No original content to analyze'}</div>
          <div style="background: white; border-radius: 10px; padding: 15px; text-align: left;">
            <div style="font-size: 12px; color: #374151;">
              <strong>💡 Why was this skipped?</strong><br>
              <span style="color: #6b7280;">The document contains 98%+ externally pasted content. AI detection analyzes whether content was generated by AI - but since it's all pasted from external sources anyway, this check adds no value.</span>
            </div>
          </div>
        </div>
      </div>
    `
  }
  
  // If AI detection wasn't run or failed
  if (!aiDetectionResult || aiDetectionResult.status !== 'success') {
    let reason = 'AI detection was not performed'
    let icon = '⏳'
    
    if (aiDetectionResult?.status === 'document_too_short') {
      reason = `Document has ${aiDetectionResult.wordCount || 0} words (minimum 100 required)`
      icon = '📝'
    } else if (aiDetectionResult?.status === 'api_key_missing') {
      reason = 'AI detection service not configured'
      icon = '⚙️'
    } else if (aiDetectionResult?.status === 'not_authenticated') {
      reason = 'Please log in to verify AI content'
      icon = '🔒'
    } else if (aiDetectionResult?.status === 'api_error' || aiDetectionResult?.status === 'network_error') {
      reason = 'AI detection service temporarily unavailable'
      icon = '⚡'
    }
    
    return `
      <div style="background: white; border-radius: 20px; padding: 30px; margin-bottom: 30px; box-shadow: 0 10px 40px rgba(0,0,0,0.08); page-break-inside: avoid;">
        <h3 style="margin: 0 0 25px 0; color: #1f2937; font-size: 18px; font-weight: 600;">
          <span style="display: inline-block; width: 4px; height: 24px; background: #f59e0b; margin-right: 12px; border-radius: 2px; vertical-align: middle;"></span>
          AI Content Detection
        </h3>
        <div style="background: #f3f4f6; border-radius: 16px; padding: 25px; text-align: center;">
          <div style="font-size: 48px; margin-bottom: 15px;">${icon}</div>
          <div style="font-size: 18px; font-weight: 600; color: #374151; margin-bottom: 8px;">Not Available</div>
          <div style="font-size: 14px; color: #6b7280;">${reason}</div>
        </div>
      </div>
    `
  }
  
  const aiPercent = Math.round((aiDetectionResult.ai_probability || 0) * 100)
  const humanPercent = Math.round((aiDetectionResult.human_probability || 0) * 100)
  const predictedClass = aiDetectionResult.predicted_class || 'unknown'
  const confidence = aiDetectionResult.confidence || 'unknown'
  
  // Calculate penalty (with 10% safe harbor)
  const penalty = Math.max(0, aiPercent - 10)
  
  // Determine status colors
  let statusColor, statusBg, statusIcon, statusText, statusDescription
  
  if (aiPercent <= 10) {
    statusColor = '#10b981'
    statusBg = 'linear-gradient(135deg, #10b981 0%, #059669 100%)'
    statusIcon = '✓'
    statusText = 'Human Written'
    statusDescription = 'Content appears to be authentically human-written'
  } else if (aiPercent <= 30) {
    statusColor = '#10b981'
    statusBg = 'linear-gradient(135deg, #10b981 0%, #059669 100%)'
    statusIcon = '✓'
    statusText = 'Mostly Human'
    statusDescription = 'Minor AI traces detected, likely acceptable AI assistance'
  } else if (aiPercent <= 50) {
    statusColor = '#f59e0b'
    statusBg = 'linear-gradient(135deg, #f59e0b 0%, #d97706 100%)'
    statusIcon = '?'
    statusText = 'Mixed Content'
    statusDescription = 'Document contains both human and AI-generated content'
  } else if (aiPercent <= 75) {
    statusColor = '#ef4444'
    statusBg = 'linear-gradient(135deg, #ef4444 0%, #dc2626 100%)'
    statusIcon = '⚠'
    statusText = 'Likely AI'
    statusDescription = 'Significant AI-generated content detected'
  } else {
    statusColor = '#ef4444'
    statusBg = 'linear-gradient(135deg, #dc2626 0%, #991b1b 100%)'
    statusIcon = '✗'
    statusText = 'AI Generated'
    statusDescription = 'Document appears to be primarily AI-generated'
  }
  
  return `
    <div style="background: white; border-radius: 20px; padding: 30px; margin-bottom: 30px; box-shadow: 0 10px 40px rgba(0,0,0,0.08); page-break-inside: avoid;">
      <h3 style="margin: 0 0 25px 0; color: #1f2937; font-size: 18px; font-weight: 600;">
        <span style="display: inline-block; width: 4px; height: 24px; background: #f59e0b; margin-right: 12px; border-radius: 2px; vertical-align: middle;"></span>
        AI Content Detection
      </h3>
      
      <!-- Stack layout for print compatibility -->
      <div style="display: block;">
        <!-- Main Status Card -->
        <div style="background: ${statusBg}; border-radius: 16px; padding: 25px; color: white; margin-bottom: 20px;">
          <div style="display: block;">
            <div style="display: inline-block; width: 50px; height: 50px; background: rgba(255,255,255,0.2); border-radius: 50%; text-align: center; line-height: 50px; font-size: 24px; font-weight: bold; vertical-align: middle; margin-right: 15px;">
              ${statusIcon}
            </div>
            <div style="display: inline-block; vertical-align: middle; max-width: calc(100% - 80px);">
              <div style="font-size: 22px; font-weight: 700; white-space: nowrap;">${statusText}</div>
              <div style="font-size: 13px; opacity: 0.9; margin-top: 4px;">${statusDescription}</div>
            </div>
          </div>
          
          <div style="background: rgba(255,255,255,0.15); border-radius: 10px; padding: 15px; margin-top: 20px; text-align: center;">
            <div style="font-size: 13px; opacity: 0.8; margin-bottom: 5px;">AI Probability</div>
            <div style="font-size: 48px; font-weight: 800;">${aiPercent}%</div>
          </div>
        </div>
        
        <!-- Details Panel -->
        <div style="background: #f9fafb; border-radius: 16px; padding: 25px;">
          <div style="margin-bottom: 20px;">
            <div style="font-size: 13px; color: #6b7280; text-transform: uppercase; letter-spacing: 1px; margin-bottom: 12px; font-weight: 600;">Detection Results</div>
            <table style="width: 100%; border-collapse: separate; border-spacing: 15px 0;">
              <tr>
                <td style="width: 33%; background: white; border-radius: 10px; padding: 15px; text-align: center; border: 1px solid #e5e7eb;">
                  <div style="font-size: 24px; font-weight: 700; color: #10b981;">${humanPercent}%</div>
                  <div style="font-size: 11px; color: #6b7280; margin-top: 5px;">Human</div>
                </td>
                <td style="width: 33%; background: white; border-radius: 10px; padding: 15px; text-align: center; border: 1px solid #e5e7eb;">
                  <div style="font-size: 24px; font-weight: 700; color: #f59e0b;">${100 - humanPercent - aiPercent}%</div>
                  <div style="font-size: 11px; color: #6b7280; margin-top: 5px;">Mixed</div>
                </td>
                <td style="width: 33%; background: white; border-radius: 10px; padding: 15px; text-align: center; border: 1px solid #e5e7eb;">
                  <div style="font-size: 24px; font-weight: 700; color: #ef4444;">${aiPercent}%</div>
                  <div style="font-size: 11px; color: #6b7280; margin-top: 5px;">AI</div>
                </td>
              </tr>
            </table>
          </div>
          
          <div style="background: white; border-radius: 10px; padding: 15px; border: 1px solid #e5e7eb;">
            <div style="margin-bottom: 10px;">
              <span style="font-size: 13px; color: #374151;">AI Content Level:</span>
              <span style="font-size: 14px; font-weight: 700; color: ${statusColor}; float: right;">${aiPercent}%</span>
            </div>
            <div style="background: #e5e7eb; height: 12px; border-radius: 6px; overflow: hidden;">
              <div style="background: ${aiPercent <= 10 ? '#10b981' : aiPercent <= 50 ? '#f59e0b' : '#ef4444'}; width: ${aiPercent}%; height: 100%; border-radius: 6px;"></div>
            </div>
            <div style="margin-top: 8px; font-size: 10px; color: #9ca3af;">
              <span style="float: left;">0% Human</span>
              <span style="float: right;">100% AI</span>
              <span style="display: block; text-align: center;">10% safe harbor</span>
            </div>
          </div>
          
          <div style="margin-top: 15px; font-size: 11px; color: #6b7280; text-align: center;">
            Confidence: ${confidence} • Class: ${predictedClass} • Words analyzed: ${aiDetectionResult.word_count || 'N/A'}
          </div>
        </div>
      </div>
      
      <div style="margin-top: 20px; padding: 15px 20px; background: #fef3c7; border-radius: 10px; border-left: 4px solid #f59e0b;">
        <div style="font-size: 14px; font-weight: 600; color: #92400e; margin-bottom: 5px;">🤖 About AI Detection</div>
        <div style="font-size: 12px; color: #78350f; line-height: 1.5;">
          This analysis uses advanced AI detection technology to identify AI-generated content including ChatGPT, Claude, and other LLMs. 
          A 10% safe harbor is applied to account for common phrases and minor AI assistance.
          ${aiPercent > 50 ? ' High AI probability suggests content may have been generated by AI tools.' : ''}
        </div>
      </div>
    </div>
  `
}

// Get stylometry status indicator for legend
const getStylometryIndicator = () => {
  if (!stylometryResult || stylometryResult.verified === null) {
    if (stylometryResult?.status === 'not_enrolled') {
      return `<div style="display: flex; align-items: center; gap: 8px; background: rgba(255,255,255,0.1); padding: 8px 12px; border-radius: 6px;">
        <span style="font-size: 13px;">⚠️ Authorship: Not enrolled</span>
      </div>`
    }
    return ''
  }
  
  // Override header when chunk analysis detected mixed content
  if (chunkAnalysisResult?.any_flagged) {
    const flagged = chunkAnalysisResult.chunks?.filter(c => c.flagged).length || 0
    const total = chunkAnalysisResult.chunks?.length || 0
    return `<div style="display: flex; align-items: center; gap: 8px; background: rgba(239,68,68,0.3); padding: 8px 12px; border-radius: 6px;">
      <span style="font-size: 13px;">⚠️ Mixed Content (${flagged} of ${total} sections flagged)</span>
    </div>`
  }

  const cosineMatchPct = Math.round((stylometryResult.cosine_score ?? stylometryResult.score ?? stylometryResult.similarity ?? 0) * 100)

  if (stylometryResult.verified === true) {
    return `<div style="display: flex; align-items: center; gap: 8px; background: rgba(16,185,129,0.3); padding: 8px 12px; border-radius: 6px;">
      <span style="font-size: 13px;">Written by This Student (${cosineMatchPct}% style match)</span>
    </div>`
  } else if (stylometryResult.verified === false) {
    return `<div style="display: flex; align-items: center; gap: 8px; background: rgba(239,68,68,0.3); padding: 8px 12px; border-radius: 6px;">
      <span style="font-size: 13px;">May Not Be This Student's Writing (${cosineMatchPct}% style match)</span>
    </div>`
  } else {
    return `<div style="display: flex; align-items: center; gap: 8px; background: rgba(245,158,11,0.3); padding: 8px 12px; border-radius: 6px;">
      <span style="font-size: 13px;">Authorship Uncertain (${cosineMatchPct}% style match)</span>
    </div>`
  }
}

// Get highlight legend for printed document
const getHighlightLegend = () => {
  const { integrity, assignmentToolSettings: _ats } = useStore()
  const _legendToolOn = _ats?.value?.analyze_integrity_enabled !== false

  // Filter to only show pastes/retyped that are CURRENTLY in the editor
  let externalPastes = _legendToolOn ? filterPastesByEditorContent(integrity?.value?.externalPastesFound || []) : []
  let retypedExternal = _legendToolOn ? filterPastesByEditorContent(integrity?.value?.retypedExternalDetected || []) : []

  // FALLBACK: Only if analysis hasn't run yet (same guard as getContentHtml)
  const _legendAnalysisCompleted = integrity?.value?.lastAnalyzed || integrity?.value?.scores?.trust != null
  if (externalPastes.length === 0 && !_legendAnalysisCompleted && window.INTEGRITY_DATABASE?.externalPastes?.length > 0) {
    externalPastes = filterPastesByEditorContent(window.INTEGRITY_DATABASE.externalPastes)
  }

  if (externalPastes.length === 0 && !_legendAnalysisCompleted && window.PROVENANCE_TRACKER?.externalPasteCache?.size > 0) {
    externalPastes = filterPastesByEditorContent(Array.from(window.PROVENANCE_TRACKER.externalPasteCache.entries()).map(([hash, data]) => ({
      text: data.text,
      id: hash
    })))
  }

  console.log('🏷️ Building legend:', { externalPastes: externalPastes.length, retypedExternal: retypedExternal.length, stylometry: stylometryResult })

  // ALWAYS show legend - include stylometry status
  const hasExternalData = externalPastes.length > 0 || retypedExternal.length > 0 || 
                          (window.INTEGRITY_DATABASE?.totalExternalPastedChars > 0)
  const hasStylometry = stylometryResult && stylometryResult.verified !== undefined
  
  if (!hasExternalData && !hasStylometry) {
    return '' // No data at all
  }
  
  return `
    <div style="background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); padding: 20px; margin-bottom: 20px; border-radius: 10px; color: white; page-break-inside: avoid;">
      <div style="display: flex; justify-content: space-between; align-items: center;">
        <div>
          <h3 style="margin: 0 0 10px 0; font-size: 16px; font-weight: 700;">Editorrah Integrity Analysis</h3>
          <p style="margin: 0; font-size: 12px; opacity: 0.9;">Content verified for authenticity and authorship</p>
        </div>
        ${_legendToolOn ? `<div style="background: white; padding: 10px 20px; border-radius: 8px;">
          <div style="color: #667eea; font-weight: 600; font-size: 14px;">Typing Trust: ${getLegendTrustScore()}%</div>
        </div>` : ''}
      </div>
      <div style="display: flex; gap: 20px; margin-top: 15px; flex-wrap: wrap;">
        ${(_ats?.value?.stylometry_enabled !== false) ? getStylometryIndicator() : ''}
        ${externalPastes.length > 0 ? `
          <div style="display: flex; align-items: center; gap: 8px; background: rgba(255,255,255,0.2); padding: 8px 12px; border-radius: 6px;">
            <span style="display: inline-block; width: 16px; height: 16px; background: #ffcccc; border-radius: 2px; border-bottom: 2px solid #f44336;"></span>
            <span style="font-size: 13px; font-weight: 500;">External Paste (${externalPastes.length})</span>
          </div>
        ` : ''}
        ${retypedExternal.length > 0 ? `
          <div style="display: flex; align-items: center; gap: 8px; background: rgba(255,255,255,0.2); padding: 8px 12px; border-radius: 6px;">
            <span style="display: inline-block; width: 16px; height: 16px; background: #fff3e0; border-radius: 2px; border-bottom: 2px solid #ff9800;"></span>
            <span style="font-size: 13px; font-weight: 500;">Retyped External (${retypedExternal.length})</span>
          </div>
        ` : ''}
        ${externalPastes.length === 0 && retypedExternal.length === 0 && !hasStylometry ? `
          <div style="display: flex; align-items: center; gap: 8px; background: rgba(255,255,255,0.2); padding: 8px 12px; border-radius: 6px;">
            <span style="display: inline-block; width: 20px; height: 20px; background: #10b981; border-radius: 3px;"></span>
            <span style="font-size: 13px; font-weight: 500;">Original Content (100%)</span>
          </div>
        ` : ''}
      </div>
    </div>
  `
}

// ============================================================================
// PDF HELPER FUNCTIONS - Self-explanatory sections for millions of students
// ============================================================================

// AT A GLANCE - Risk Fusion Model Display
const getAtAGlanceSection = (trustScore, scoreColor, composition, externalPastes) => {
  const { integrity } = useStore()
  const _ts = assignmentToolSettings?.value || {}
  const caOn = _ts.analyze_integrity_enabled !== false
  const aiOn = _ts.gptzero_enabled !== false
  const styOn = _ts.stylometry_enabled !== false

  // If no trust-relevant tools are enabled, show info message
  if (!caOn && !aiOn && !styOn) {
    return `
      <div style="background: white; border-radius: 20px; padding: 30px; margin-bottom: 25px; box-shadow: 0 10px 40px rgba(0,0,0,0.08); text-align: center;">
        <div style="font-size: 24px; margin-bottom: 12px;">ℹ️</div>
        <div style="font-size: 16px; font-weight: 600; color: #6b7280;">No integrity analysis tools are enabled for this assignment.</div>
      </div>
    `
  }

  // Get signals
  const P_proc = integrity?.value?.scores?.P_proc ?? composition.typed
  const S_style = integrity?.value?.scores?.S_style ?? 0.5
  const P_ai = integrity?.value?.scores?.P_ai ?? 0
  const apiSkipped = integrity?.value?.scores?.api_skipped ?? false
  const styloVerdict = integrity?.value?.stylometry?.verdict

  const typingPercent = Math.round(P_proc * 100)
  const aiPercent = Math.round(P_ai * 100)

  // Matrix thresholds
  const CA_AUTHENTIC = 70, CA_UNCERTAIN = 40
  const AI_AUTHENTIC = 20, AI_UNCERTAIN = 50

  // Build matrix rows — only for enabled tools
  const rows = []
  if (caOn) {
    const state = typingPercent >= CA_AUTHENTIC ? 'authentic' : typingPercent >= CA_UNCERTAIN ? 'uncertain' : 'flagged'
    rows.push({ tool: 'Content Authenticity', state, detail: `${typingPercent}% typed` })
  }
  if (aiOn) {
    // Check if AI detection actually ran (not just skipped or doc too short)
    const _aiActuallyRan = aiDetectionResult && aiDetectionResult.status === 'success'
    const aiNotRun = !_aiActuallyRan || apiSkipped
    // When chunk analysis found AI, override the diluted whole-doc signal
    const chunkAiFlagged = chunkAnalysisResult?.any_flagged && chunkAnalysisResult.chunks?.some(c => c.flag_reasons?.includes('ai_detected'))
    if (chunkAiFlagged) {
      const worstAi = Math.max(...chunkAnalysisResult.chunks.map(c => c.ai_probability || 0))
      rows.push({ tool: 'True AI Detector', state: 'flagged', detail: `${Math.round(worstAi * 100)}% AI (worst section)` })
    } else {
      const state = aiNotRun ? 'uncertain' : aiPercent <= AI_AUTHENTIC ? 'authentic' : aiPercent <= AI_UNCERTAIN ? 'uncertain' : 'flagged'
      const detail = aiNotRun
        ? (aiDetectionResult?.status === 'document_too_short' ? `Insufficient text (${aiDetectionResult.wordCount || 0} words)` : 'Not checked')
        : `${aiPercent}% AI probability`
      rows.push({ tool: 'True AI Detector', state, detail, notRun: aiNotRun })
    }
  }
  if (styOn) {
    // When chunk analysis found style mismatch, override whole-doc "verified"
    const chunkStyloFlagged = chunkAnalysisResult?.any_flagged && chunkAnalysisResult.chunks?.some(c => c.flag_reasons?.includes('style_mismatch'))
    if (chunkStyloFlagged) {
      rows.push({ tool: 'Authorship Verification', state: 'flagged', detail: 'flagged (per-section)' })
    } else {
      const state = apiSkipped ? 'uncertain' :
        styloVerdict === 'verified' ? 'authentic' :
        (styloVerdict === 'review_required' || styloVerdict === 'inconclusive') ? 'uncertain' :
        styloVerdict === 'flagged' ? 'flagged' : 'uncertain'
      rows.push({ tool: 'Authorship Verification', state, detail: apiSkipped ? 'Skipped' : (styloVerdict || 'Not checked'), notRun: apiSkipped || !styloVerdict })
    }
  }

  // Consensus — only tools that actually RAN vote; not-run tools are named separately.
  const ranRows = rows.filter(r => !r.notRun)
  const notRunRows = rows.filter(r => r.notRun)
  const authenticCount = ranRows.filter(r => r.state === 'authentic').length
  const flaggedCount = ranRows.filter(r => r.state === 'flagged').length
  const total = ranRows.length
  const notRunSuffix = notRunRows.length ? ` ${notRunRows.map(r => r.tool).join(', ')} did not run.` : ''
  let consensusText = ''
  let consensusBg = '#f0fdf4'
  let consensusBorder = '#10b981'

  // Check if chunk-level analysis found mixed content that whole-doc missed
  const chunkOverride = !!chunkAnalysisResult?.any_flagged

  if (chunkOverride) {
    // Chunk analysis detected mixed content — override consensus regardless of whole-doc signals
    const flaggedChunks = chunkAnalysisResult.chunks?.filter(c => c.flagged) || []
    const chunkCount = chunkAnalysisResult.chunks?.length || 0
    consensusText = `Chunk-level analysis detected mixed content: ${flaggedChunks.length} of ${chunkCount} section(s) flagged for AI content or style mismatch. Whole-document signals may be diluted — review the flagged sections below.`
    consensusBg = '#fef2f2'
    consensusBorder = '#ef4444'
  } else if (total === 0) {
    consensusText = `No integrity tool was able to run.${notRunSuffix}`
    consensusBg = '#fffbeb'
    consensusBorder = '#f59e0b'
  } else if (authenticCount === total) {
    consensusText = (total === rows.length)
      ? 'All tools indicate authentic work.'
      : `All ${total} tool(s) that ran indicate authentic work.${notRunSuffix}`
  } else if (flaggedCount === total) {
    consensusText = `All tools that ran indicate significant concerns.${notRunSuffix}`
    consensusBg = '#fef2f2'
    consensusBorder = '#ef4444'
  } else {
    const dissenters = ranRows.filter(r => r.state === 'flagged').map(r => r.tool)
    const uncertainTools = ranRows.filter(r => r.state === 'uncertain').map(r => r.tool)
    if (dissenters.length > 0) {
      consensusText = `${authenticCount} of ${total} tool(s) that ran indicate authentic work. ${dissenters.join(', ')} dissent${dissenters.length === 1 ? 's' : ''} — review recommended.${notRunSuffix}`
      consensusBg = '#fffbeb'
      consensusBorder = '#f59e0b'
    } else {
      consensusText = `${authenticCount} of ${total} tool(s) that ran indicate authentic work. ${uncertainTools.join(', ')}: uncertain — review recommended.${notRunSuffix}`
      consensusBg = '#fffbeb'
      consensusBorder = '#f59e0b'
    }
  }

  // State styling
  const stateStyles = {
    authentic: { color: '#10b981', bg: '#ecfdf5', dot: '#10b981' },
    uncertain: { color: '#f59e0b', bg: '#fffbeb', dot: '#f59e0b' },
    flagged: { color: '#ef4444', bg: '#fef2f2', dot: '#ef4444' }
  }

  // Build matrix HTML
  const matrixRows = rows.map(r => {
    const s = stateStyles[r.state]
    return `
      <tr>
        <td style="padding: 10px 12px; font-size: 13px; font-weight: 600; color: #374151; border-bottom: 1px solid #f3f4f6;">${r.tool}</td>
        <td style="padding: 10px 8px; text-align: center; border-bottom: 1px solid #f3f4f6;">
          ${r.state === 'authentic' ? `<span style="display: inline-block; width: 14px; height: 14px; background: ${s.dot}; border-radius: 50%;"></span>` : ''}
        </td>
        <td style="padding: 10px 8px; text-align: center; border-bottom: 1px solid #f3f4f6;">
          ${r.state === 'uncertain' ? `<span style="display: inline-block; width: 14px; height: 14px; background: ${s.dot}; border-radius: 50%;"></span>` : ''}
        </td>
        <td style="padding: 10px 8px; text-align: center; border-bottom: 1px solid #f3f4f6;">
          ${r.state === 'flagged' ? `<span style="display: inline-block; width: 14px; height: 14px; background: ${s.dot}; border-radius: 50%;"></span>` : ''}
        </td>
        <td style="padding: 10px 12px; font-size: 11px; color: ${s.color}; font-weight: 500; border-bottom: 1px solid #f3f4f6;">${r.detail}</td>
      </tr>
    `
  }).join('')

  // Explanation text — signals are independent, nothing is averaged
  const toolNames = []
  if (caOn) toolNames.push('typing provenance')
  if (aiOn) toolNames.push('AI detection')
  if (styOn) toolNames.push('authorship verification')
  const howItWorks = `Each tool (${toolNames.join(', ')}) reports its own independent finding. There is no combined score — review where the signals agree or conflict.`

  return `
    <div style="background: white; border-radius: 20px; padding: 25px; margin-bottom: 25px; box-shadow: 0 10px 40px rgba(0,0,0,0.08);">
      <h3 style="margin: 0 0 20px 0; color: #1f2937; font-size: 16px; font-weight: 600; text-align: center; text-transform: uppercase; letter-spacing: 2px;">
        📊 Signal Summary
      </h3>

      <!-- Signal Agreement Matrix -->
      <div style="margin-bottom: 15px;">
        <table style="width: 100%; border-collapse: collapse; font-family: inherit;">
          <thead>
            <tr>
              <th style="padding: 8px 12px; text-align: left; font-size: 10px; color: #6b7280; text-transform: uppercase; letter-spacing: 1px; border-bottom: 2px solid #e5e7eb;"></th>
              <th style="padding: 8px 8px; text-align: center; font-size: 10px; color: #10b981; text-transform: uppercase; letter-spacing: 1px; border-bottom: 2px solid #e5e7eb; font-weight: 700;">Authentic</th>
              <th style="padding: 8px 8px; text-align: center; font-size: 10px; color: #f59e0b; text-transform: uppercase; letter-spacing: 1px; border-bottom: 2px solid #e5e7eb; font-weight: 700;">Uncertain</th>
              <th style="padding: 8px 8px; text-align: center; font-size: 10px; color: #ef4444; text-transform: uppercase; letter-spacing: 1px; border-bottom: 2px solid #e5e7eb; font-weight: 700;">Flagged</th>
              <th style="padding: 8px 12px; text-align: left; font-size: 10px; color: #6b7280; text-transform: uppercase; letter-spacing: 1px; border-bottom: 2px solid #e5e7eb;">Detail</th>
            </tr>
          </thead>
          <tbody>
            ${matrixRows}
          </tbody>
        </table>
      </div>

      <!-- Consensus -->
      <div style="background: ${consensusBg}; border-radius: 10px; padding: 12px; border-left: 4px solid ${consensusBorder}; margin-bottom: 15px;">
        <div style="font-size: 13px; color: #374151; font-weight: 500;">
          <strong>Consensus:</strong> ${consensusText}
        </div>
      </div>

      <!-- How To Read This -->
      <div style="background: #f8fafc; border-radius: 10px; padding: 12px; border: 1px solid #e2e8f0;">
        <div style="font-size: 11px; color: #475569; text-align: center;">
          <strong>How To Read This:</strong> ${howItWorks}
        </div>
      </div>
    </div>
  `
}

// FOR EVALUATORS - Concise key findings
const getForEvaluatorsSection = (trustScore, composition, externalPastes) => {
  const _ts = assignmentToolSettings?.value || {}
  const caOn = _ts.analyze_integrity_enabled !== false
  const aiOn = _ts.gptzero_enabled !== false
  const styOn = _ts.stylometry_enabled !== false

  const { integrity: _evalIntegrity } = useStore()
  const timeline = window.INTEGRITY_TIMELINE || {}

  // Use current editor state (from IntegrityTracker analysis), not session totals
  const mix = _evalIntegrity?.value?.mix || { typed: 1, internal: 0, external: 0 }
  const currentText = editor?.value?.getText() || ''
  const totalChars = currentText.length || 1
  const typedChars = Math.round(mix.typed * totalChars)
  const externalPastes_count = externalPastes.length

  // Session duration — always shown
  const segments = timeline.segments || []
  const sessionMs = segments.length > 1 ?
    segments[segments.length - 1].timestamp - segments[0].timestamp : 0
  const sessionMins = Math.round(sessionMs / 60000)

  // Stylometry info
  const similarity = stylometryResult?.cosine_score != null ? Math.round(stylometryResult.cosine_score * 100) :
                     stylometryResult?.score != null ? Math.round(stylometryResult.score * 100) :
                     (stylometryResult?.similarity ? Math.round(stylometryResult.similarity * 100) : null)
  const authStatus = stylometryResult?.verdict === 'verified' ? 'MATCH' :
                     stylometryResult?.verdict === 'flagged' ? 'FLAGGED' :
                     stylometryResult?.verdict === 'review_required' ? 'REVIEW' :
                     stylometryResult?.verified === true ? 'MATCH' :
                     stylometryResult?.verified === false ? 'FLAGGED' : 'Not checked'

  // AI detection info
  const aiPercent = aiDetectionResult?.status === 'success' ? Math.round((aiDetectionResult.ai_probability || 0) * 100) : null
  const aiStatus = aiPercent !== null ? (aiPercent <= 10 ? 'Human' : aiPercent <= 50 ? 'Mixed' : 'AI-Generated') : 'Not checked'

  // Build key findings — gated by tool settings
  const findings = []

  if (caOn) {
    findings.push(`${typedChars.toLocaleString()} of ${totalChars.toLocaleString()} characters typed (${Math.round(composition.typed * 100)}%)`)
    if (externalPastes_count > 0) {
      findings.push(`${externalPastes_count} external source(s) detected and highlighted`)
    } else {
      findings.push(`No external content detected`)
    }
  }

  // When chunks are flagged, override stylo/AI findings with chunk truth
  if (chunkAnalysisResult?.any_flagged) {
    const flaggedChunks = chunkAnalysisResult.chunks?.filter(c => c.flagged) || []
    const cleanChunks = chunkAnalysisResult.chunks?.filter(c => !c.flagged) || []
    const chunkCount = chunkAnalysisResult.chunks?.length || 0
    const worstAi = Math.max(...flaggedChunks.map(c => c.ai_probability || 0))

    if (styOn) {
      findings.push(`Writing style: MIXED (${flaggedChunks.length} of ${chunkCount} sections flagged)`)
    }
    if (aiOn) {
      findings.push(`AI content: Detected in ${flaggedChunks.length} sections (worst: ${Math.round(worstAi * 100)}%)`)
    }
  } else {
    if (styOn && similarity !== null) {
      findings.push(`Writing style: ${authStatus} (${similarity}% style similarity)`)
    }
    if (aiOn && aiPercent !== null) {
      findings.push(`AI content: ${aiStatus} (${aiPercent}% AI probability)`)
    }
  }

  if (sessionMins > 0) {
    findings.push(`Document created over ${sessionMins} minute${sessionMins > 1 ? 's' : ''}`)
  }

  // Flags — gated by tool settings
  const flags = []
  if (caOn && composition.typed < 0.5) flags.push('Less than 50% typed')
  if (caOn && typedChars === 0) flags.push('No typing detected')
  if (styOn && (stylometryResult?.verdict === 'flagged' || stylometryResult?.verified === false)) flags.push('Authorship mismatch')
  if (aiOn && aiPercent !== null && aiPercent > 50) flags.push(`High AI probability (${aiPercent}%)`)
  if (chunkAnalysisResult?.any_flagged) flags.push(`Mixed content: ${chunkAnalysisResult.summary}`)
  if (_evalIntegrity?.value?.flags?.includes('ghost_writing_suspected')) flags.push('Ghost-writing suspected: typed content with high AI probability and style mismatch')
  
  return `
    <div style="background: white; border-radius: 16px; padding: 25px; margin-top: 30px; border: 2px solid #667eea;">
      <div style="display: flex; align-items: center; gap: 10px; margin-bottom: 15px;">
        <span style="font-size: 20px;">👨‍🏫</span>
        <div style="font-size: 16px; font-weight: 700; color: #374151;">For Evaluators</div>
      </div>
      
      <div style="background: #f9fafb; border-radius: 12px; padding: 15px; margin-bottom: 15px;">
        <div style="font-size: 12px; font-weight: 600; color: #6b7280; text-transform: uppercase; letter-spacing: 1px; margin-bottom: 10px;">Key Findings</div>
        <ul style="margin: 0; padding-left: 20px; font-size: 13px; color: #374151; line-height: 1.8;">
          ${findings.map(f => `<li>${f}</li>`).join('')}
        </ul>
      </div>
      
      ${flags.length > 0 ? `
        <div style="background: #fef2f2; border-radius: 12px; padding: 15px; border-left: 4px solid #ef4444;">
          <div style="font-size: 12px; font-weight: 600; color: #dc2626; margin-bottom: 8px;">⚠️ Flags Requiring Attention</div>
          <ul style="margin: 0; padding-left: 20px; font-size: 13px; color: #991b1b; line-height: 1.6;">
            ${flags.map(f => `<li>${f}</li>`).join('')}
          </ul>
        </div>
      ` : `
        <div style="background: #ecfdf5; border-radius: 12px; padding: 15px; border-left: 4px solid #10b981;">
          <div style="font-size: 13px; color: #065f46;">✅ No significant flags detected</div>
        </div>
      `}
    </div>
  `
}

// PLAIN ENGLISH VERDICT - Human-readable summary
// CRITICAL: Typing percentage is the primary indicator, not other signals
const getVerdictSection = (trustScore, composition, externalPastes) => {
  const _ts = assignmentToolSettings?.value || {}
  const caOn = _ts.analyze_integrity_enabled !== false
  const aiOn = _ts.gptzero_enabled !== false
  const styOn = _ts.stylometry_enabled !== false

  let verdictText = ''
  let verdictIcon = ''
  let verdictBg = ''
  let verdictBorder = ''

  const typedPercent = Math.round(composition.typed * 100)
  const externalPercent = Math.round(composition.external * 100)
  const authVerified = stylometryResult?.verdict === 'verified' || stylometryResult?.verified === true
  const authMismatch = stylometryResult?.verdict === 'flagged' || stylometryResult?.verified === false
  const similarity = stylometryResult?.cosine_score != null ? Math.round(stylometryResult.cosine_score * 100) :
                     stylometryResult?.score != null ? Math.round(stylometryResult.score * 100) :
                     (stylometryResult?.similarity ? Math.round(stylometryResult.similarity * 100) : 0)
  const aiPercent = Math.round((aiDetectionResult?.ai_probability ?? 0) * 100)
  const apiSkipped = aiDetectionResult?.skipped || stylometryResult?.skipped

  if (!caOn && !aiOn && !styOn) {
    // No analysis tools enabled
    verdictIcon = 'ℹ️'
    verdictBg = '#f3f4f6'
    verdictBorder = '#6b7280'
    verdictText = 'No analysis tools are enabled for this assignment.'

  } else if (caOn) {
    // CA is ON: use typing percentage as primary signal (existing logic)
    if (typedPercent < 10) {
      verdictIcon = '🚨'
      verdictBg = '#fef2f2'
      verdictBorder = '#dc2626'
      verdictText = `<strong>Critical:</strong> Only ${typedPercent}% of content was typed by the student.`
      verdictText += ` The remaining ${externalPercent}% was pasted from external sources.`
      if (externalPastes.length > 0) {
        verdictText += ` ${externalPastes.length} external source(s) highlighted below.`
      }
      verdictText += ` <strong>This document requires immediate review.</strong>`

    } else if (typedPercent < 50) {
      verdictIcon = '⚠️'
      verdictBg = '#fef2f2'
      verdictBorder = '#ef4444'
      verdictText = `<strong>Attention Required:</strong> Only ${typedPercent}% of content was typed.`
      verdictText += ` ${externalPercent}% was pasted from external sources.`
      if (styOn && authMismatch) {
        verdictText += ` Writing style <strong>does not match</strong> the student's baseline (${similarity}% similarity).`
      }
      if (externalPastes.length > 0) {
        verdictText += ` ${externalPastes.length} external source(s) are highlighted for review.`
      }
      verdictText += ` <strong>Evaluator should verify authenticity.</strong>`

    } else if (typedPercent >= 80 && !authMismatch) {
      verdictIcon = '✅'
      verdictBg = '#ecfdf5'
      verdictBorder = '#10b981'
      verdictText = `This document appears to be <strong>original work</strong> (${typedPercent}% typed by the student).`
      if (styOn && authVerified) {
        verdictText += ` The writing style <strong>matches</strong> the student's enrolled baseline (${similarity}% similarity).`
      }
      if (aiOn && !apiSkipped && aiPercent > 20) {
        verdictText += ` Note: True AI Detector flagged ${aiPercent}% AI probability.`
      }
      if (externalPastes.length > 0) {
        verdictText += ` ${externalPastes.length} external source(s) detected and highlighted below.`
      } else {
        verdictText += ` No external content detected.`
      }

    } else {
      verdictIcon = '🔶'
      verdictBg = '#fffbeb'
      verdictBorder = '#f59e0b'
      verdictText = `This document contains a <strong>mix of original and external content</strong>. ${typedPercent}% was typed, ${externalPercent}% was pasted from external sources.`
      if (styOn && authMismatch) {
        verdictText += ` Writing style <strong>does not match</strong> the student's baseline (${similarity}% similarity).`
      } else if (styOn && authVerified) {
        verdictText += ` Writing style matches the enrolled baseline.`
      }
      if (aiOn && !apiSkipped && aiPercent > 50) {
        verdictText += ` True AI Detector flagged ${aiPercent}% AI probability.`
      }
      if (externalPastes.length > 0) {
        verdictText += ` ${externalPastes.length} external source(s) are highlighted for review.`
      }
      verdictText += ` <strong>Manual review recommended.</strong>`
    }

  } else {
    // CA is OFF — build verdict from AI + Stylometry only
    // NEVER mention typing percentage, external paste, or pasted from external sources
    if (aiOn && styOn) {
      // Both AI + Stylometry enabled
      if (aiPercent > 70 && authMismatch) {
        verdictIcon = '🚨'
        verdictBg = '#fef2f2'
        verdictBorder = '#dc2626'
        verdictText = `<strong>Critical:</strong> True AI Detector flagged ${aiPercent}% AI probability and writing style does not match the student's baseline (${similarity}% similarity). <strong>This document requires immediate review.</strong>`
      } else if (aiPercent > 70 && authVerified) {
        // Contradictory: AI says generated, but style matches student
        verdictIcon = '🔶'
        verdictBg = '#fffbeb'
        verdictBorder = '#f59e0b'
        verdictText = `Authorship style <strong>matches</strong> the student's profile (${similarity}% similarity), but content shows <strong>signs of AI generation</strong> (${aiPercent}% AI probability). The student may have used AI assistance while maintaining their writing style. <strong>Manual review recommended.</strong>`
      } else if (aiPercent <= 20 && authMismatch) {
        // Contradictory: AI says human, but style doesn't match
        verdictIcon = '🔶'
        verdictBg = '#fffbeb'
        verdictBorder = '#f59e0b'
        verdictText = `Content appears <strong>human-written</strong> (${aiPercent}% AI probability), but writing style <strong>does not match</strong> the student's baseline (${similarity}% similarity). This may indicate the work was written by someone else. <strong>Manual review recommended.</strong>`
      } else if (aiPercent <= 20 && authVerified) {
        verdictIcon = '✅'
        verdictBg = '#ecfdf5'
        verdictBorder = '#10b981'
        verdictText = `Content appears <strong>human-written</strong> (${aiPercent}% AI probability) and writing style <strong>matches</strong> the student's baseline (${similarity}% similarity). This document appears to be authentic.`
      } else {
        verdictIcon = '🔶'
        verdictBg = '#fffbeb'
        verdictBorder = '#f59e0b'
        verdictText = `True AI Detector shows ${aiPercent}% AI probability. Authorship verification: ${stylometryResult?.verdict || 'not checked'} (${similarity}% similarity). <strong>Manual review recommended.</strong>`
      }
    } else if (aiOn) {
      // AI only
      if (aiPercent > 70) {
        verdictIcon = '🚨'
        verdictBg = '#fef2f2'
        verdictBorder = '#dc2626'
        verdictText = `<strong>Critical:</strong> True AI Detector flagged ${aiPercent}% AI probability. <strong>This document requires review.</strong>`
      } else if (aiPercent > 30) {
        verdictIcon = '🔶'
        verdictBg = '#fffbeb'
        verdictBorder = '#f59e0b'
        verdictText = `True AI Detector shows ${aiPercent}% AI probability. Some AI-generated content may be present. <strong>Manual review recommended.</strong>`
      } else {
        verdictIcon = '✅'
        verdictBg = '#ecfdf5'
        verdictBorder = '#10b981'
        verdictText = `Content appears <strong>human-written</strong> (${aiPercent}% AI probability).`
      }
    } else if (styOn) {
      // Stylometry only
      if (authMismatch) {
        verdictIcon = '🚨'
        verdictBg = '#fef2f2'
        verdictBorder = '#dc2626'
        verdictText = `<strong>Critical:</strong> Writing style <strong>does not match</strong> the student's enrolled baseline (${similarity}% similarity). <strong>This document requires review.</strong>`
      } else if (stylometryResult?.verdict === 'review_required') {
        verdictIcon = '🔶'
        verdictBg = '#fffbeb'
        verdictBorder = '#f59e0b'
        verdictText = `Authorship verification requires review (${similarity}% similarity). <strong>Manual review recommended.</strong>`
      } else if (authVerified) {
        verdictIcon = '✅'
        verdictBg = '#ecfdf5'
        verdictBorder = '#10b981'
        verdictText = `Writing style <strong>matches</strong> the student's enrolled baseline (${similarity}% similarity). This document appears authentic.`
      } else {
        verdictIcon = '🔶'
        verdictBg = '#fffbeb'
        verdictBorder = '#f59e0b'
        verdictText = `Authorship verification: ${stylometryResult?.verdict || 'inconclusive'} (${similarity}% similarity). <strong>Manual review recommended.</strong>`
      }
    }
  }

  // CHUNK ANALYSIS OVERRIDE: When chunk-level analysis found mixed content,
  // override the verdict regardless of what whole-doc signals said.
  if (chunkAnalysisResult?.any_flagged) {
    const flaggedChunks = chunkAnalysisResult.chunks?.filter(c => c.flagged) || []
    const chunkCount = chunkAnalysisResult.chunks?.length || 0
    const chunkReasons = new Set()
    flaggedChunks.forEach(c => (c.flag_reasons || []).forEach(r => chunkReasons.add(r)))
    const reasonStr = [...chunkReasons].map(r => r === 'ai_detected' ? 'AI-generated content' : 'writing style mismatch').join(' and ')

    verdictIcon = '🚨'
    verdictBg = '#fef2f2'
    verdictBorder = '#dc2626'
    verdictText = `<strong>Mixed Content Detected:</strong> Chunk-level analysis found ${flaggedChunks.length} of ${chunkCount} section(s) containing ${reasonStr}. While the overall document may appear authentic, individual sections show clear signs of non-original content. <strong>Review the flagged sections carefully.</strong>`
  }

  return `
    <div style="background: ${verdictBg}; border-radius: 16px; padding: 20px; margin-bottom: 25px; border-left: 5px solid ${verdictBorder};">
      <div style="display: flex; align-items: start; gap: 15px;">
        <div style="font-size: 32px;">${verdictIcon}</div>
        <div>
          <div style="font-size: 14px; font-weight: 700; color: #374151; margin-bottom: 8px; text-transform: uppercase; letter-spacing: 1px;">
            Summary
          </div>
          <div style="font-size: 14px; color: #374151; line-height: 1.6;">
            ${verdictText}
          </div>
        </div>
      </div>
    </div>
  `
}

// Get integrity report HTML with sophisticated Editorrah branding
const getIntegrityReport = () => {
  const { integrity } = useStore()
  
  // Show the report when integrity tracking is active AND any tool is enabled.
  // The old guard (!active || !lastAnalyzed) hid the entire report when CA was
  // off because lastAnalyzed is only set by IntegrityTracker's analysis.
  // Now we keep the `active` check (prevents non-assignment mode from showing a
  // bogus 0% report) but drop the `lastAnalyzed` requirement.
  const _rts = assignmentToolSettings?.value || {}
  const _anyToolOn = _rts.analyze_integrity_enabled !== false ||
                     _rts.gptzero_enabled !== false ||
                     _rts.stylometry_enabled !== false
  // Render the report whenever there is real analysis context: an active
  // session, a completed analysis, or an assignment submit in progress.
  // `active` is a transient flag (re-set by ingest responses) — it must not
  // be able to silently kill the teacher-facing report at print time.
  const _hasAnalysisContext = integrity?.value?.active
    || integrity?.value?.lastAnalyzed
    || integrity?.value?.scores?.trust != null
    || !!window._assignmentSubmitCallback
  if (!_hasAnalysisContext || !_anyToolOn) {
    console.error('🚫 Integrity report page suppressed:', {
      active: integrity?.value?.active,
      lastAnalyzed: integrity?.value?.lastAnalyzed,
      trust: integrity?.value?.scores?.trust,
      submitting: !!window._assignmentSubmitCallback,
      anyToolOn: _anyToolOn,
    })
    return ''
  }
  
  // Typing-provenance trust score (individual signal; no composite exists)
  let trustScore = integrity.value.scores?.trust
  
  // Fallback 1: Try to calculate from PROVENANCE_TRACKER if available (only if no score yet)
  if ((trustScore === undefined || trustScore === null) && window.PROVENANCE_TRACKER?.segments?.length > 0) {
    const currentText = editor.value?.getText() || ''
    const provenance = window.PROVENANCE_TRACKER.getProvenanceSummary(currentText)
    if (provenance.counts.EXTERNAL_PASTE > 0 || provenance.counts.DERIVED_FROM_EXTERNAL > 0) {
      trustScore = provenance.trustScore
      console.log('🔄 Using PROVENANCE_TRACKER trust score for print:', trustScore)
    }
  }
  
  // Fallback 2: Calculate from session totals (only if still no score)
  // NOTE: This is session-based, not current-document-based. Only use as last resort.
  if ((trustScore === undefined || trustScore === null) && window.INTEGRITY_DATABASE) {
    const totalTyped = window.INTEGRITY_DATABASE.totalTypedChars || 0
    const totalExternal = window.INTEGRITY_DATABASE.totalExternalPastedChars || 0
    const total = totalTyped + totalExternal
    if (total > 0 && totalExternal > 0) {
      trustScore = Math.round((totalTyped / total) * 100)
      console.log('🔄 Using INTEGRITY_DATABASE trust score for print (session-based fallback):', trustScore)
    }
  }
  
  // Final fallback
  trustScore = trustScore ?? 0
  
  console.log('🖨️ Final trust score for PDF:', trustScore)
  
  const composition = integrity.value.mix || { typed: 1, internal: 0, external: 0 }
  let externalPastes = filterPastesByEditorContent(integrity.value.externalPastesFound || [])

  // Fallback for external pastes — only if analysis hasn't run yet
  const _reportAnalysisCompleted = integrity.value.lastAnalyzed || integrity.value.scores?.trust != null
  if (externalPastes.length === 0 && !_reportAnalysisCompleted && window.INTEGRITY_DATABASE?.externalPastes?.length > 0) {
    externalPastes = window.INTEGRITY_DATABASE.externalPastes
  }
  
  // NEW: Security verification status (Phase 1 + 2 + 3)
  const devtoolsOpened = integrity.value.devtoolsOpened || false
  const devtoolsTimestamp = integrity.value.devtoolsTimestamp
  const serverSignature = integrity.value.serverSignature
  const chainHead = integrity.value.chainHead
  const chainValid = integrity.value.chainValid !== false
  const signatureValid = !integrity.value.flags?.includes('signature_invalid')

  // Header badge is an overall review status: any flagged individual signal
  // forces "Review Required" so the header can never contradict the report body.
  const _styloFlagged = integrity.value.stylometry?.verdict === 'flagged' || stylometryResult?.verdict === 'flagged' || stylometryResult?.verified === false
  const _lowTyped = assignmentToolSettings?.value?.analyze_integrity_enabled !== false && (integrity.value.mix?.typed ?? 1) < 0.5
  const _ghostFlagged = integrity.value.flags?.includes('ghost_writing_suspected')
  const _aiHigh = aiDetectionResult?.status === 'success' && (aiDetectionResult.ai_probability || 0) > 0.5
  const _needsReview = !!chunkAnalysisResult?.any_flagged || _styloFlagged || _lowTyped || _ghostFlagged || _aiHigh
  
  // Determine status based on the typing trust score (individual signal).
  // Stylometry and AI detection are reported in their own sections below.
  let scoreStatus = 'Excellent'
  let scoreColor = '#10b981'
  let scoreBg = 'linear-gradient(135deg, #10b981 0%, #059669 100%)'

  if (trustScore === null || trustScore === undefined) {
    scoreStatus = 'N/A'
    scoreColor = '#6b7280'
    scoreBg = 'linear-gradient(135deg, #6b7280 0%, #4b5563 100%)'
  } else if (trustScore < 50) {
    scoreStatus = 'Needs Review'
    scoreColor = '#ef4444'
    scoreBg = 'linear-gradient(135deg, #ef4444 0%, #dc2626 100%)'
  } else if (trustScore < 80) {
    scoreStatus = 'Fair'
    scoreColor = '#f59e0b'
    scoreBg = 'linear-gradient(135deg, #f59e0b 0%, #d97706 100%)'
  }
  
  // Individual-signal blocks: Signal Summary (matrix + consensus), plain-English
  // Verdict, and the Typing Trust ring (typing provenance only — no composite).
  const _ghostWriting = integrity.value.flags?.includes('ghost_writing_suspected')
  const _ghostBanner = _ghostWriting
    ? `
      <div style="background: #fef2f2; border: 3px solid #dc2626; border-radius: 16px; padding: 20px 25px; margin-bottom: 25px; display: flex; align-items: center; gap: 15px;">
        <div style="font-size: 32px;">🚨</div>
        <div>
          <div style="font-size: 16px; font-weight: 800; color: #dc2626; text-transform: uppercase; letter-spacing: 1px;">Ghost-Writing Suspected</div>
          <div style="font-size: 13px; color: #7f1d1d; margin-top: 4px;">Content was typed (&gt;80%) but AI detection is above 80% and the writing style does not match the student's enrolled baseline. Review all three signals below.</div>
        </div>
      </div>`
    : ''
  const _caEnabled = assignmentToolSettings?.value?.analyze_integrity_enabled !== false
  const _typingCard = (_caEnabled && trustScore !== null && trustScore !== undefined)
    ? `
      <div style="background: white; border-radius: 20px; padding: 40px; margin-bottom: 30px; box-shadow: 0 10px 40px rgba(0,0,0,0.08); position: relative;">
        <div style="display: flex; align-items: center; justify-content: space-between;">
          <div>
            <h2 style="margin: 0 0 10px 0; color: #1f2937; font-size: 18px; text-transform: uppercase; letter-spacing: 1px; font-weight: 600;">
              Typing Trust — Provenance
            </h2>
            <div style="display: flex; align-items: baseline; gap: 20px;">
              <div style="font-size: 86px; font-weight: 800; color: ${scoreColor}; line-height: 1;">${trustScore}</div>
              <div style="font-size: 36px; color: #9ca3af;">%</div>
            </div>
            <div style="margin-top: 15px; display: inline-block; padding: 8px 20px; background: ${scoreBg}; color: white; border-radius: 50px; font-weight: 600; font-size: 14px; text-transform: uppercase; letter-spacing: 1px;">${scoreStatus}</div>
            <div style="margin-top: 12px; font-size: 11px; color: #9ca3af;">Share of the document typed by the student. Stylometry and AI detection are reported separately below.</div>
          </div>
          <div style="position: relative; width: 180px; height: 180px;">
            <svg viewBox="0 0 200 200" style="transform: rotate(-90deg);">
              <circle cx="100" cy="100" r="90" fill="none" stroke="#e5e7eb" stroke-width="20"/>
              <circle cx="100" cy="100" r="90" fill="none" stroke="${scoreColor}" stroke-width="20" stroke-dasharray="${trustScore * 5.65} 565" stroke-linecap="round"/>
            </svg>
            <div style="position: absolute; top: 50%; left: 50%; transform: translate(-50%, -50%); text-align: center;">
              <div style="font-size: 14px; color: #9ca3af; font-weight: 600;">TYPING</div>
              <div style="font-size: 32px; font-weight: 800; color: ${scoreColor};">${trustScore}%</div>
            </div>
          </div>
        </div>
      </div>`
    : ''
  const _signalBlocks = `
      ${_ghostBanner}
      ${getAtAGlanceSection(trustScore, scoreColor, composition, externalPastes)}
      ${getVerdictSection(trustScore, composition, externalPastes)}
      ${_typingCard}`

  // Build HTML for integrity report page
  let reportHtml = `
    <div class="integrity-report-page" style="page-break-before: always; padding: 0; margin: 0; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;">
      
      <!-- Header with Editorrah Branding -->
      <div style="background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); padding: 60px 40px 40px; position: relative; overflow: hidden;">
        <div style="position: absolute; top: 0; right: 0; width: 300px; height: 300px; background: rgba(255,255,255,0.1); border-radius: 50%; transform: translate(100px, -100px);"></div>
        <div style="position: absolute; bottom: 0; left: 0; width: 200px; height: 200px; background: rgba(255,255,255,0.05); border-radius: 50%; transform: translate(-50px, 50px);"></div>
        
        <div style="position: relative; z-index: 1;">
          <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 30px;">
            <div>
              <h1 style="color: white; margin: 0; font-size: 36px; font-weight: 700; letter-spacing: -1px;">Editorrah</h1>
              <p style="color: rgba(255,255,255,0.8); margin: 5px 0 0 0; font-size: 14px; text-transform: uppercase; letter-spacing: 2px;">Integrity Report</p>
            </div>
            <div style="text-align: right;">
              ${devtoolsOpened ? `
                <div style="background: #fef2f2; border: 2px solid #ef4444; border-radius: 10px; padding: 8px 16px; display: inline-block; margin-bottom: 10px;">
                  <span style="color: #dc2626; font-weight: 700; font-size: 14px;">⚠️ DevTools Detected</span>
                </div>
              ` : ''}
              <div style="background: white; border-radius: 10px; padding: 8px 16px; display: inline-block;">
                ${_needsReview ? `
                  <span style="color: #dc2626; font-weight: 600; font-size: 14px;">⚠️ Review Required</span>
                ` : signatureValid && chainValid ? `
                  <span style="color: #10b981; font-weight: 600; font-size: 14px;">✓ Verified Document</span>
                ` : `
                  <span style="color: #f59e0b; font-weight: 600; font-size: 14px;">⚠️ Verification Incomplete</span>
                `}
              </div>
            </div>
          </div>
        </div>
      </div>
      
      <!-- Main Content Container -->
      <div style="padding: 40px; background: #f8f9fa;">
        
        <!-- Individual signal blocks: Signal Summary / Verdict / Typing Trust ring -->
        ${_signalBlocks}
        
        <!-- Authorship Verification Section (Stylometry) -->
        ${assignmentToolSettings?.value?.stylometry_enabled !== false ? getStylometrySection() : ''}

        <!-- AI Detection Section -->
        ${assignmentToolSettings?.value?.gptzero_enabled !== false && !chunkAnalysisResult?.any_flagged ? getAIDetectionSection() : ''}

        ${assignmentToolSettings?.value?.analyze_integrity_enabled !== false ? `
        <!-- Composition Analysis -->
        <div style="background: white; border-radius: 20px; padding: 30px; margin-bottom: 30px; box-shadow: 0 10px 40px rgba(0,0,0,0.08);">
          <h3 style="margin: 0 0 25px 0; color: #1f2937; font-size: 18px; font-weight: 600; display: flex; align-items: center;">
            <span style="display: inline-block; width: 4px; height: 24px; background: #667eea; margin-right: 12px; border-radius: 2px;"></span>
            Content Composition Analysis
          </h3>

          <!-- Progress Bar -->
          <div style="background: #f3f4f6; height: 50px; border-radius: 25px; overflow: hidden; display: flex; margin-bottom: 30px; box-shadow: inset 0 2px 4px rgba(0,0,0,0.06);">
            ${composition.typed * 100 > 0 ? `
              <div style="background: linear-gradient(135deg, #10b981 0%, #059669 100%); width: ${composition.typed * 100}%; display: flex; align-items: center; justify-content: center; color: white; font-weight: 600; font-size: 14px; position: relative; overflow: hidden;">
                <div style="position: absolute; top: 0; left: 0; width: 100%; height: 100%; background: rgba(255,255,255,0.1); animation: shimmer 2s infinite;"></div>
                ${Math.round(composition.typed * 100) > 5 ? Math.round(composition.typed * 100) + '%' : ''}
              </div>
            ` : ''}
            ${composition.internal * 100 > 0 ? `
              <div style="background: linear-gradient(135deg, #3b82f6 0%, #2563eb 100%); width: ${composition.internal * 100}%; display: flex; align-items: center; justify-content: center; color: white; font-weight: 600; font-size: 14px;">
                ${Math.round(composition.internal * 100) > 5 ? Math.round(composition.internal * 100) + '%' : ''}
              </div>
            ` : ''}
            ${composition.external * 100 > 0 ? `
              <div style="background: linear-gradient(135deg, #ef4444 0%, #dc2626 100%); width: ${composition.external * 100}%; display: flex; align-items: center; justify-content: center; color: white; font-weight: 600; font-size: 14px;">
                ${Math.round(composition.external * 100) > 5 ? Math.round(composition.external * 100) + '%' : ''}
              </div>
            ` : ''}
          </div>

          <!-- Legend -->
          <div style="display: grid; grid-template-columns: repeat(3, 1fr); gap: 20px;">
            <div style="text-align: center; padding: 15px; background: #f9fafb; border-radius: 12px;">
              <div style="width: 40px; height: 40px; background: linear-gradient(135deg, #10b981 0%, #059669 100%); border-radius: 10px; margin: 0 auto 10px; display: flex; align-items: center; justify-content: center;">
                <span style="color: white; font-size: 20px;">✍️</span>
              </div>
              <div style="font-size: 24px; font-weight: 700; color: #10b981; margin-bottom: 5px;">${Math.round(composition.typed * 100)}%</div>
              <div style="font-size: 13px; color: #6b7280; font-weight: 500;">Original Typed</div>
            </div>

            <div style="text-align: center; padding: 15px; background: #f9fafb; border-radius: 12px;">
              <div style="width: 40px; height: 40px; background: linear-gradient(135deg, #3b82f6 0%, #2563eb 100%); border-radius: 10px; margin: 0 auto 10px; display: flex; align-items: center; justify-content: center;">
                <span style="color: white; font-size: 20px;">🔄</span>
              </div>
              <div style="font-size: 24px; font-weight: 700; color: #3b82f6; margin-bottom: 5px;">${Math.round(composition.internal * 100)}%</div>
              <div style="font-size: 13px; color: #6b7280; font-weight: 500;">Own Work</div>
            </div>

            <div style="text-align: center; padding: 15px; background: #f9fafb; border-radius: 12px;">
              <div style="width: 40px; height: 40px; background: linear-gradient(135deg, #ef4444 0%, #dc2626 100%); border-radius: 10px; margin: 0 auto 10px; display: flex; align-items: center; justify-content: center;">
                <span style="color: white; font-size: 20px;">📋</span>
              </div>
              <div style="font-size: 24px; font-weight: 700; color: #ef4444; margin-bottom: 5px;">${Math.round(composition.external * 100)}%</div>
              <div style="font-size: 13px; color: #6b7280; font-weight: 500;">External Source</div>
            </div>
          </div>
        </div>

        <!-- External Content Details -->
        ${externalPastes.length > 0 ? `
          <div style="background: white; border-radius: 20px; padding: 30px; margin-bottom: 30px; box-shadow: 0 10px 40px rgba(0,0,0,0.08);">
            <div style="display: flex; align-items: center; justify-content: space-between; margin-bottom: 25px;">
              <h3 style="margin: 0; color: #1f2937; font-size: 18px; font-weight: 600; display: flex; align-items: center;">
                <span style="display: inline-block; width: 4px; height: 24px; background: #ef4444; margin-right: 12px; border-radius: 2px;"></span>
                External Content Detected
              </h3>
              <div style="background: #fef2f2; color: #991b1b; padding: 6px 12px; border-radius: 20px; font-size: 13px; font-weight: 600;">
                ${externalPastes.length} Instance${externalPastes.length > 1 ? 's' : ''}
              </div>
            </div>

            ${externalPastes.map((paste, index) => {
              const pasteText = (paste.text || '').replace(/\*\*/g, '').replace(/###?\s*/g, '').replace(/[*_~`]/g, '')
              const sentences = pasteText.split(/(?<=[.!?])\s+/).filter(s => s.trim().length > 0)
              const wordCount = pasteText.trim().split(/\s+/).length
              return '<div style="border: 1px solid #fee2e2; border-radius: 12px; padding: 20px; margin-bottom: 15px; background: #fef2f2;">' +
                '<div style="display: flex; justify-content: space-between; align-items: start; margin-bottom: 12px;">' +
                  '<div style="display: flex; align-items: center;">' +
                    '<div style="width: 32px; height: 32px; background: #ef4444; color: white; border-radius: 8px; display: flex; align-items: center; justify-content: center; font-weight: 700; font-size: 14px; margin-right: 12px;">' + (index + 1) + '</div>' +
                    '<div>' +
                      '<div style="font-weight: 600; color: #991b1b; font-size: 14px;">External Paste</div>' +
                      '<div style="color: #dc2626; font-size: 12px; margin-top: 2px;">' + pasteText.length + ' characters &middot; ' + wordCount + ' words &middot; ' + sentences.length + ' sentences</div>' +
                    '</div>' +
                  '</div>' +
                  (paste.fuzzy ? '<div style="background: #fbbf24; color: #78350f; padding: 4px 10px; border-radius: 12px; font-size: 11px; font-weight: 600;">FUZZY MATCH</div>' : '') +
                '</div>' +
                '<div style="background: #1e1e1e; padding: 16px; border-radius: 8px; margin-top: 12px; overflow-x: auto;">' +
                  '<div style="font-family: \'Courier New\', \'Consolas\', monospace; font-size: 12px; line-height: 1.8;">' +
                    sentences.map((sentence, si) =>
                      '<div style="display: flex; border-bottom: 1px solid #333; padding: 4px 0;">' +
                        '<span style="color: #6b7280; min-width: 32px; text-align: right; padding-right: 12px; user-select: none; border-right: 1px solid #444; margin-right: 12px;">' + (si + 1) + '</span>' +
                        '<span style="color: #f87171;">+ </span>' +
                        '<span style="color: #fca5a5;">' + sentence.replace(/</g, '&lt;').replace(/>/g, '&gt;') + '</span>' +
                      '</div>'
                    ).join('') +
                  '</div>' +
                '</div>' +
              '</div>'
            }).join('')}
          </div>
        ` : `
          <div style="background: white; border-radius: 20px; padding: 30px; margin-bottom: 30px; box-shadow: 0 10px 40px rgba(0,0,0,0.08); text-align: center;">
            <div style="width: 60px; height: 60px; background: linear-gradient(135deg, #10b981 0%, #059669 100%); border-radius: 50%; margin: 0 auto 20px; display: flex; align-items: center; justify-content: center;">
              <span style="color: white; font-size: 28px;">✓</span>
            </div>
            <h3 style="color: #10b981; margin: 0 0 10px 0; font-size: 20px;">No External Content Detected</h3>
            <p style="color: #6b7280; margin: 0; font-size: 14px;">All content appears to be original or properly cited</p>
          </div>
        `}
        ` : ''}
        
        <!-- Security Verification Section (Phase 1+2+3) -->
        <div style="background: white; border-radius: 20px; padding: 30px; margin-bottom: 30px; box-shadow: 0 10px 40px rgba(0,0,0,0.08);">
          <h3 style="margin: 0 0 25px 0; color: #1f2937; font-size: 18px; font-weight: 600; display: flex; align-items: center;">
            <span style="display: inline-block; width: 4px; height: 24px; background: #667eea; margin-right: 12px; border-radius: 2px;"></span>
            Security Verification
          </h3>
          
          <div style="display: grid; grid-template-columns: repeat(3, 1fr); gap: 20px; margin-bottom: 20px;">
            <!-- DevTools Detection -->
            <div style="padding: 20px; background: ${devtoolsOpened ? '#fef2f2' : '#f0fdf4'}; border-radius: 12px; border: 2px solid ${devtoolsOpened ? '#ef4444' : '#10b981'};">
              <div style="display: flex; align-items: center; margin-bottom: 10px;">
                <span style="font-size: 24px; margin-right: 10px;">${devtoolsOpened ? '⚠️' : '✓'}</span>
                <div style="font-weight: 600; color: ${devtoolsOpened ? '#dc2626' : '#059669'}; font-size: 14px;">
                  ${devtoolsOpened ? 'DevTools Detected' : 'No DevTools'}
                </div>
              </div>
              ${devtoolsOpened ? `
                <div style="color: #991b1b; font-size: 12px; margin-top: 5px;">
                  Opened at: ${devtoolsTimestamp ? new Date(devtoolsTimestamp).toLocaleString() : 'Unknown'}
                </div>
              ` : `
                <div style="color: #047857; font-size: 12px; margin-top: 5px;">No browser tools accessed</div>
              `}
            </div>
            
            <!-- Server Signature (attests the record only, not the content) -->
            <div style="padding: 20px; background: ${serverSignature && signatureValid ? '#f0fdf4' : serverSignature ? '#fef2f2' : '#fffbeb'}; border-radius: 12px; border: 2px solid ${serverSignature && signatureValid ? '#10b981' : serverSignature ? '#ef4444' : '#f59e0b'};">
              <div style="display: flex; align-items: center; margin-bottom: 10px;">
                <span style="font-size: 24px; margin-right: 10px;">${serverSignature && signatureValid ? '✓' : '⚠️'}</span>
                <div style="font-weight: 600; color: ${serverSignature && signatureValid ? '#059669' : serverSignature ? '#dc2626' : '#b45309'}; font-size: 14px;">
                  ${serverSignature ? (signatureValid ? 'Signature Intact' : 'Signature Invalid') : 'No Signature'}
                </div>
              </div>
              ${serverSignature ? `
                <div style="color: #047857; font-size: 11px; font-family: 'Courier New', monospace; margin-top: 5px; word-break: break-all;">
                  ${serverSignature.substring(0, 32)}...
                </div>
              ` : `
                <div style="color: #991b1b; font-size: 12px; margin-top: 5px;">No server signature</div>
              `}
            </div>
            
            <!-- Event Chain -->
            <div style="padding: 20px; background: ${chainValid ? '#f0fdf4' : '#fef2f2'}; border-radius: 12px; border: 2px solid ${chainValid ? '#10b981' : '#ef4444'};">
              <div style="display: flex; align-items: center; margin-bottom: 10px;">
                <span style="font-size: 24px; margin-right: 10px;">${chainValid ? '✓' : '⚠️'}</span>
                <div style="font-weight: 600; color: ${chainValid ? '#059669' : '#dc2626'}; font-size: 14px;">
                  ${chainValid ? 'Chain Valid' : 'Chain Invalid'}
                </div>
              </div>
              ${chainHead ? `
                <div style="color: #047857; font-size: 11px; font-family: 'Courier New', monospace; margin-top: 5px; word-break: break-all;">
                  ${chainHead.substring(0, 32)}...
                </div>
              ` : `
                <div style="color: #991b1b; font-size: 12px; margin-top: 5px;">No chain data</div>
              `}
            </div>
          </div>
          
          ${devtoolsOpened || !signatureValid || !chainValid ? `
            <div style="background: #fef2f2; border-left: 4px solid #ef4444; padding: 15px; border-radius: 8px; margin-top: 20px;">
              <div style="color: #991b1b; font-weight: 600; font-size: 13px; margin-bottom: 5px;">⚠️ Security Warning</div>
              <div style="color: #7f1d1d; font-size: 12px; line-height: 1.5;">
                ${devtoolsOpened ? '• Browser developer tools were opened during this session<br>' : ''}
                ${!signatureValid ? '• Server signature verification failed - possible tampering detected<br>' : ''}
                ${!chainValid ? '• Event chain verification failed - integrity may be compromised' : ''}
              </div>
            </div>
          ` : `
            <div style="background: #f0fdf4; border-left: 4px solid #10b981; padding: 15px; border-radius: 8px; margin-top: 20px;">
              <div style="color: #047857; font-weight: 600; font-size: 13px; margin-bottom: 5px;">✓ Tamper-Proof Record Intact</div>
              <div style="color: #065f46; font-size: 12px;">Cryptographic signature and event chain are intact — the writing session record was not altered. This attests the record, not the content; see the signal sections above for the integrity verdict.</div>
            </div>
          `}
        </div>
        
        <!-- Footer -->
        <div style="background: white; border-radius: 20px; padding: 25px; box-shadow: 0 10px 40px rgba(0,0,0,0.08); text-align: center;">
          <div style="display: flex; justify-content: space-between; align-items: center;">
            <div style="text-align: left;">
              <div style="color: #6b7280; font-size: 11px; text-transform: uppercase; letter-spacing: 1px; margin-bottom: 5px;">Document ID</div>
              <div style="color: #374151; font-size: 13px; font-family: 'Courier New', monospace;">${(integrity.value.sessionId || 'unknown').substring(0, 16)}...</div>
            </div>
            <div style="text-align: center;">
              <div style="font-size: 20px; font-weight: 700; color: #667eea; margin-bottom: 5px;">Editorrah</div>
              <div style="color: #9ca3af; font-size: 11px;">Academic Integrity System</div>
            </div>
            <div style="text-align: right;">
              <div style="color: #6b7280; font-size: 11px; text-transform: uppercase; letter-spacing: 1px; margin-bottom: 5px;">Generated</div>
              <div style="color: #374151; font-size: 13px;">${new Date().toLocaleDateString()}</div>
              <div style="color: #9ca3af; font-size: 11px;">${new Date().toLocaleTimeString()}</div>
            </div>
          </div>
        </div>
        
        <!-- FOR EVALUATORS - Key findings summary -->
        ${getForEvaluatorsSection(trustScore, composition, externalPastes)}
        
        <!-- Understanding This Report -->
        <div style="background: #f0f9ff; border-radius: 16px; padding: 20px; margin-top: 30px; border: 1px solid #bae6fd;">
          <div style="font-size: 14px; font-weight: 700; color: #0369a1; margin-bottom: 12px;">📖 Understanding This Report</div>
          <div style="display: grid; grid-template-columns: repeat(2, 1fr); gap: 15px; font-size: 12px; color: #0c4a6e;">
            ${assignmentToolSettings?.value?.analyze_integrity_enabled !== false ? `<div>
              <strong>Typing Percentage</strong> = How much content the student typed themselves (vs pasted from other sources)
            </div>` : ''}
            ${assignmentToolSettings?.value?.stylometry_enabled !== false ? `<div>
              <strong>Authorship Verification</strong> = Compares writing style to the student's enrolled writing samples
            </div>` : ''}
            ${assignmentToolSettings?.value?.analyze_integrity_enabled !== false ? `<div>
              <strong>External Content</strong> = Text pasted from outside sources (highlighted in red in the document)
            </div>` : ''}
            ${assignmentToolSettings?.value?.analyze_integrity_enabled !== false ? `<div>
              <strong>Timeline</strong> = Shows when and how content was added (typing vs pasting patterns)
            </div>` : ''}
            ${assignmentToolSettings?.value?.gptzero_enabled !== false ? `<div>
              <strong>True AI Detector</strong> = Analyzes content for signs of AI generation
            </div>` : ''}
          </div>
        </div>
        
        <!-- Disclaimer -->
        <div style="text-align: center; margin-top: 30px; padding: 0 40px;">
          <p style="color: #9ca3af; font-size: 11px; line-height: 1.6;">
            This report is generated by Editorrah's Academic Integrity System. The analysis is based on text matching algorithms and should be used as a guide alongside manual review. 
            For questions or disputes, please contact support@editorrah.com
          </p>
        </div>
      </div>
    </div>
  `
  
  return reportHtml
}

// Build the Keystroke Authenticity section for the timeline report
function buildKeystrokeAuthSection() {
  const ata = window.AUTOTYPER_DB?.analysisResult
  if (!ata || ata.sampleSize < 30) return ''
  
  const statusColor = ata.isRobotic ? '#dc2626' : ata.isSuspicious ? '#d97706' : '#16a34a'
  const statusBg = ata.isRobotic ? '#fef2f2' : ata.isSuspicious ? '#fffbeb' : '#f0fdf4'
  const statusBorder = ata.isRobotic ? '#fca5a5' : ata.isSuspicious ? '#fcd34d' : '#86efac'
  const statusLabel = ata.isRobotic ? 'ROBOTIC' : ata.isSuspicious ? 'SUSPICIOUS' : 'NATURAL'
  const statusIcon = ata.isRobotic ? '🤖' : ata.isSuspicious ? '⚠️' : '✅'
  const trustedPct = ata.untrustedRatio !== undefined ? Math.round((1 - ata.untrustedRatio) * 100) : 100
  const cvBad = ata.cv < 0.15 && ata.sampleSize >= 50
  const cvColor = cvBad ? '#dc2626' : '#16a34a'
  const cvBg = cvBad ? '#fef2f2' : '#f0fdf4'
  const cvBorder = cvBad ? '#fca5a5' : '#86efac'
  const trustBad = trustedPct < 90
  const trustColor = trustBad ? '#dc2626' : '#16a34a'
  const trustBg = trustBad ? '#fef2f2' : '#f0fdf4'
  const trustBorder = trustBad ? '#fca5a5' : '#86efac'

  let flagsHtml = ''
  if (ata.flags.length > 0) {
    const alertBg = ata.isRobotic ? '#fef2f2' : '#fffbeb'
    const alertBorder = ata.isRobotic ? '#fca5a5' : '#fcd34d'
    const alertTitle = ata.isRobotic ? '🚨 Automated Input Detected' : '⚠️ Typing Pattern Anomalies'
    const alertTitleColor = ata.isRobotic ? '#991b1b' : '#92400e'
    const alertTextColor = ata.isRobotic ? '#dc2626' : '#b45309'
    const flagsList = ata.flags.map(f => '&bull; ' + f.replace(/_/g, ' ')).join('<br>')
    flagsHtml = '<div style="background: ' + alertBg + '; border: 1px solid ' + alertBorder + '; border-radius: 12px; padding: 15px;">' +
      '<div style="font-weight: 600; color: ' + alertTitleColor + '; font-size: 13px; margin-bottom: 8px;">' + alertTitle + '</div>' +
      '<div style="color: ' + alertTextColor + '; font-size: 12px; line-height: 1.6;">' + flagsList + '</div>' +
      '</div>'
  } else {
    flagsHtml = '<div style="background: #f0fdf4; border: 1px solid #86efac; border-radius: 12px; padding: 15px; text-align: center;">' +
      '<div style="color: #16a34a; font-size: 13px; font-weight: 500;">✅ Keystroke patterns are consistent with natural human typing</div>' +
      '</div>'
  }

  return '<div style="background: white; border-radius: 20px; padding: 30px; margin-bottom: 30px; box-shadow: 0 10px 40px rgba(0,0,0,0.08);">' +
    '<h3 style="margin: 0 0 25px 0; color: #1f2937; font-size: 18px; font-weight: 600; display: flex; align-items: center;">' +
      '<span style="display: inline-block; width: 4px; height: 24px; background: ' + statusColor + '; margin-right: 12px; border-radius: 2px;"></span>' +
      'Keystroke Authenticity' +
    '</h3>' +
    '<div style="display: grid; grid-template-columns: repeat(4, 1fr); gap: 15px; margin-bottom: 20px;">' +
      // Card 1: Status
      '<div style="text-align: center; padding: 20px; background: ' + statusBg + '; border-radius: 12px; border: 2px solid ' + statusBorder + ';">' +
        '<div style="font-size: 28px; margin-bottom: 5px;">' + statusIcon + '</div>' +
        '<div style="font-size: 18px; font-weight: 700; color: ' + statusColor + '; margin-bottom: 3px;">' + statusLabel + '</div>' +
        '<div style="font-size: 11px; color: #6b7280;">Typing Pattern</div>' +
      '</div>' +
      // Card 2: CV
      '<div style="text-align: center; padding: 20px; background: ' + cvBg + '; border-radius: 12px; border: 2px solid ' + cvBorder + ';">' +
        '<div style="font-size: 28px; font-weight: 700; color: ' + cvColor + '; margin-bottom: 5px;">' + ata.cv + '</div>' +
        '<div style="font-size: 11px; color: #6b7280; font-weight: 500;">Rhythm Variance (CV)</div>' +
        '<div style="font-size: 10px; color: #9ca3af; margin-top: 3px;">Human: 0.3-0.7</div>' +
      '</div>' +
      // Card 3: Trusted input
      '<div style="text-align: center; padding: 20px; background: ' + trustBg + '; border-radius: 12px; border: 2px solid ' + trustBorder + ';">' +
        '<div style="font-size: 28px; font-weight: 700; color: ' + trustColor + '; margin-bottom: 5px;">' + trustedPct + '%</div>' +
        '<div style="font-size: 11px; color: #6b7280; font-weight: 500;">Non-Scripted Input</div>' +
        '<div style="font-size: 10px; color: #9ca3af; margin-top: 3px;">' + (trustedPct >= 100 ? 'no automation detected in ' + ata.totalEvents + ' events' : ata.totalEvents + ' events sampled') + '</div>' +
      '</div>' +
      // Card 4: Avg gap
      '<div style="text-align: center; padding: 20px; background: #f8fafc; border-radius: 12px; border: 2px solid #e2e8f0;">' +
        '<div style="font-size: 28px; font-weight: 700; color: #475569; margin-bottom: 5px;">' + ata.mean + 'ms</div>' +
        '<div style="font-size: 11px; color: #6b7280; font-weight: 500;">Avg Keystroke Gap</div>' +
        '<div style="font-size: 10px; color: #9ca3af; margin-top: 3px;">' + ata.stddev + 'ms std dev</div>' +
      '</div>' +
    '</div>' +
    flagsHtml +
  '</div>'
}

// NEW: Get Timeline & Evolution Analysis Report
const getTimelineReport = () => {
  const { integrity } = useStore()
  
  // CRITICAL: Save any pending typing segment before generating report
  if (window.INTEGRITY_TIMELINE?.currentSegmentText && window.INTEGRITY_TIMELINE?.currentSegmentStart) {
    const now = Date.now()
    const duration = now - window.INTEGRITY_TIMELINE.currentSegmentStart
    const wpm = duration > 0 ? (window.INTEGRITY_TIMELINE.currentSegmentText.length / 5) / (duration / 60000) : 0
    
    if (window.INTEGRITY_TIMELINE.currentSegmentText.length > 0) {
      window.INTEGRITY_TIMELINE.segments.push({
        text: window.INTEGRITY_TIMELINE.currentSegmentText,
        timestamp: window.INTEGRITY_TIMELINE.currentSegmentStart,
        duration: duration,
        wpm: Math.round(wpm),
        type: 'typed'
      })
      console.log('💾 Saved pending typing segment for print:', window.INTEGRITY_TIMELINE.currentSegmentText.length, 'chars')
      
      // Clear after saving
      window.INTEGRITY_TIMELINE.currentSegmentText = ''
      window.INTEGRITY_TIMELINE.currentSegmentStart = null
    }
  }
  
  if (!window.INTEGRITY_TIMELINE || window.INTEGRITY_TIMELINE.segments.length === 0) {
    // Even if no timeline, show a warning report
    return getNoTimelineWarning()
  }
  
  const timeline = window.INTEGRITY_TIMELINE

  // =========================================================================
  // FILTER SEGMENTS: Only keep events whose content is in the SUBMITTED document
  // This removes deleted pastes, error messages, and session noise
  // =========================================================================
  const _currentText = editor?.value?.getText() || ''
  const _normForMatch = t => t.toLowerCase().replace(/[^a-z0-9\s]/g, '').replace(/\s+/g, ' ').trim()
  const _currentNorm = _normForMatch(_currentText)

  const relevantSegments = timeline.segments.filter(seg => {
    if (!seg.text || seg.text.trim().length < 3) return false
    // ALWAYS keep typed segments — they represent the writing process
    // (text may differ from editor due to typo corrections, but the event is real)
    if (seg.type === 'typed') return true
    // For paste segments: only keep if paste content is still in the editor
    const segWords = _normForMatch(seg.text).split(' ').slice(0, 8).join(' ')
    if (segWords.length < 5) return false
    return _currentNorm.includes(segWords)
  })

  // Compute stats from FILTERED segments only
  const typedSegments = relevantSegments.filter(s => s.type === 'typed')
  const pasteSegments = relevantSegments.filter(s => s.type.includes('paste'))

  const hasTyping = typedSegments.length > 0
  const avgWPM = hasTyping ?
    typedSegments.reduce((sum, s) => sum + (s.wpm || 0), 0) / typedSegments.length : -1

  const deletionRatio = timeline.additions > 0 ?
    (timeline.deletions / timeline.additions * 100) : -1

  // Active writing time = sum of typed segment durations (not wall-clock session time)
  const activeWritingMs = typedSegments.reduce((sum, s) => sum + (s.duration || 0), 0)

  // Use CURRENT editor state for composition stats
  const _timelineMix = integrity?.value?.mix || { typed: 1, internal: 0, external: 0 }
  const _timelineTotalChars = _currentText.length || 1
  const totalTypedChars = Math.round(_timelineMix.typed * _timelineTotalChars)
  const totalExternalPasted = Math.round(_timelineMix.external * _timelineTotalChars)
  const totalInternalPasted = Math.round(_timelineMix.internal * _timelineTotalChars)
  const totalCharsAll = totalTypedChars + totalExternalPasted + totalInternalPasted || 1

  // Typed word count (from current editor, not session)
  const typedWordCount = Math.round((_timelineMix.typed) * (_currentText.trim().split(/\s+/).length || 0))

  const formatDuration = (ms) => {
    if (ms < 60000) return Math.round(ms / 1000) + 's'
    if (ms < 3600000) return Math.round(ms / 60000) + 'm'
    return Math.round(ms / 3600000) + 'h ' + Math.round((ms % 3600000) / 60000) + 'm'
  }

  // Read integrity signals for Process Consistency (must match Integrity Report)
  const typedPercent = Math.round((_timelineMix.typed || 0) * 100)
  const _aiResult = typeof aiDetectionResult !== 'undefined' ? aiDetectionResult : null
  const _aiRan = _aiResult && _aiResult.status === 'success'
  const _aiProb = _aiRan ? Math.round((_aiResult.ai_probability || 0) * 100) : null
  
  return `
    <div class="timeline-report-page" style="page-break-before: always; padding: 0; margin: 0; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;">

      <!-- Header -->
      <div style="background: linear-gradient(135deg, #06b6d4 0%, #0891b2 100%); padding: 60px 40px 40px; position: relative; overflow: hidden;">
        <div style="position: absolute; top: 0; right: 0; width: 300px; height: 300px; background: rgba(255,255,255,0.1); border-radius: 50%; transform: translate(100px, -100px);"></div>
        <div style="position: relative; z-index: 1;">
          <div style="display: flex; justify-content: space-between; align-items: center;">
            <div>
              <h1 style="color: white; margin: 0; font-size: 36px; font-weight: 700; letter-spacing: -1px;">Editorrah</h1>
              <p style="color: rgba(255,255,255,0.9); margin: 5px 0 0 0; font-size: 14px; text-transform: uppercase; letter-spacing: 2px;">Document Forensics</p>
            </div>
            <div style="background: white; border-radius: 10px; padding: 8px 16px; display: inline-block;">
              <span style="color: #06b6d4; font-weight: 600; font-size: 14px;">📊 Process Report</span>
            </div>
          </div>
        </div>
      </div>

      <div style="padding: 40px; background: #f8f9fa;">

        <!-- Section 1: Document Composition -->
        <div style="background: white; border-radius: 20px; padding: 30px; margin-bottom: 30px; box-shadow: 0 10px 40px rgba(0,0,0,0.08);">
          <h3 style="margin: 0 0 25px 0; color: #1f2937; font-size: 18px; font-weight: 600; display: flex; align-items: center;">
            <span style="display: inline-block; width: 4px; height: 24px; background: #8b5cf6; margin-right: 12px; border-radius: 2px;"></span>
            Document Composition
          </h3>

          <div style="display: grid; grid-template-columns: repeat(4, 1fr); gap: 15px;">
            <div style="text-align: center; padding: 15px; background: #f0fdf4; border-radius: 12px; border: 2px solid #86efac;">
              <div style="font-size: 24px; font-weight: 700; color: #16a34a; margin-bottom: 5px;">
                ${totalTypedChars.toLocaleString()}
              </div>
              <div style="font-size: 11px; color: #6b7280; font-weight: 500;">Chars Typed</div>
              <div style="font-size: 10px; color: #16a34a; margin-top: 3px;">${Math.round(totalTypedChars / totalCharsAll * 100)}%</div>
            </div>

            <div style="text-align: center; padding: 15px; background: ${totalExternalPasted > 0 ? '#fef2f2' : '#f9fafb'}; border-radius: 12px; border: 2px solid ${totalExternalPasted > 0 ? '#fca5a5' : '#e5e7eb'};">
              <div style="font-size: 24px; font-weight: 700; color: ${totalExternalPasted > 0 ? '#dc2626' : '#9ca3af'}; margin-bottom: 5px;">
                ${totalExternalPasted.toLocaleString()}
              </div>
              <div style="font-size: 11px; color: #6b7280; font-weight: 500;">External Paste</div>
              <div style="font-size: 10px; color: ${totalExternalPasted > 0 ? '#dc2626' : '#9ca3af'}; margin-top: 3px;">${Math.round(totalExternalPasted / totalCharsAll * 100)}%</div>
            </div>

            <div style="text-align: center; padding: 15px; background: ${totalInternalPasted > 0 ? '#fffbeb' : '#f9fafb'}; border-radius: 12px; border: 2px solid ${totalInternalPasted > 0 ? '#fcd34d' : '#e5e7eb'};">
              <div style="font-size: 24px; font-weight: 700; color: ${totalInternalPasted > 0 ? '#d97706' : '#9ca3af'}; margin-bottom: 5px;">
                ${totalInternalPasted.toLocaleString()}
              </div>
              <div style="font-size: 11px; color: #6b7280; font-weight: 500;">Own Reuse</div>
              <div style="font-size: 10px; color: ${totalInternalPasted > 0 ? '#d97706' : '#9ca3af'}; margin-top: 3px;">${Math.round(totalInternalPasted / totalCharsAll * 100)}%</div>
            </div>

            <div style="text-align: center; padding: 15px; background: #ecfeff; border-radius: 12px; border: 2px solid #67e8f9;">
              <div style="font-size: 24px; font-weight: 700; color: #0891b2; margin-bottom: 5px;">
                ${formatDuration(activeWritingMs)}
              </div>
              <div style="font-size: 11px; color: #6b7280; font-weight: 500;">Active Writing</div>
              <div style="font-size: 10px; color: #9ca3af; margin-top: 3px;">Time spent typing</div>
            </div>
          </div>

          <!-- Content Ratio Bar -->
          <div style="margin-top: 20px;">
            <div style="font-size: 12px; color: #6b7280; margin-bottom: 8px;">Content Origin Distribution</div>
            <div style="height: 24px; background: #e5e7eb; border-radius: 12px; overflow: hidden; display: flex;">
              ${totalTypedChars > 0 ? '<div style="width: ' + Math.round(totalTypedChars / totalCharsAll * 100) + '%; background: #16a34a; display: flex; align-items: center; justify-content: center; color: white; font-size: 10px; font-weight: 600;">' + Math.round(totalTypedChars / totalCharsAll * 100) + '% Typed</div>' : ''}
              ${totalInternalPasted > 0 ? '<div style="width: ' + Math.round(totalInternalPasted / totalCharsAll * 100) + '%; background: #d97706; display: flex; align-items: center; justify-content: center; color: white; font-size: 10px; font-weight: 600;">' + Math.round(totalInternalPasted / totalCharsAll * 100) + '% Own</div>' : ''}
              ${totalExternalPasted > 0 ? '<div style="width: ' + Math.round(totalExternalPasted / totalCharsAll * 100) + '%; background: #dc2626; display: flex; align-items: center; justify-content: center; color: white; font-size: 10px; font-weight: 600;">' + Math.round(totalExternalPasted / totalCharsAll * 100) + '% External</div>' : ''}
              ${totalCharsAll <= 1 ? '<div style="width: 100%; background: #9ca3af; display: flex; align-items: center; justify-content: center; color: white; font-size: 10px; font-weight: 600;">No data</div>' : ''}
            </div>
          </div>
        </div>

        <!-- Section 2: Writing Behavior -->
        <div style="background: white; border-radius: 20px; padding: 30px; margin-bottom: 30px; box-shadow: 0 10px 40px rgba(0,0,0,0.08);">
          <h3 style="margin: 0 0 25px 0; color: #1f2937; font-size: 18px; font-weight: 600; display: flex; align-items: center;">
            <span style="display: inline-block; width: 4px; height: 24px; background: #06b6d4; margin-right: 12px; border-radius: 2px;"></span>
            Writing Behavior
          </h3>

          <div style="display: grid; grid-template-columns: repeat(3, 1fr); gap: 20px;">
            <div style="text-align: center; padding: 20px; background: ${avgWPM === -1 ? '#f9fafb' : '#f0fdfa'}; border-radius: 12px; border: 2px solid ${avgWPM === -1 ? '#e5e7eb' : '#5eead4'};">
              <div style="font-size: 32px; font-weight: 700; color: ${avgWPM === -1 ? '#9ca3af' : '#0891b2'}; margin-bottom: 5px;">
                ${avgWPM === -1 ? 'N/A' : Math.round(avgWPM)}
              </div>
              <div style="font-size: 13px; color: #6b7280; font-weight: 500;">Avg. WPM</div>
              <div style="font-size: 11px; color: #9ca3af; margin-top: 5px;">
                ${avgWPM === -1 ? 'No typed content' : avgWPM > 80 ? 'Above normal range' : avgWPM < 20 ? 'Below normal range' : 'Normal range (20-80)'}
              </div>
            </div>

            <div style="text-align: center; padding: 20px; background: ${deletionRatio === -1 ? '#f9fafb' : deletionRatio >= 10 ? '#f0fdf4' : '#fffbeb'}; border-radius: 12px; border: 2px solid ${deletionRatio === -1 ? '#e5e7eb' : deletionRatio >= 10 ? '#86efac' : '#fcd34d'};">
              <div style="font-size: 32px; font-weight: 700; color: ${deletionRatio === -1 ? '#9ca3af' : deletionRatio >= 10 ? '#16a34a' : '#d97706'}; margin-bottom: 5px;">
                ${deletionRatio === -1 ? 'N/A' : Math.round(deletionRatio) + '%'}
              </div>
              <div style="font-size: 13px; color: #6b7280; font-weight: 500;">Deletion Rate</div>
              <div style="font-size: 11px; color: #9ca3af; margin-top: 5px;">
                ${deletionRatio === -1 ? 'No edits recorded' : deletionRatio >= 10 ? 'Healthy editing (10-30%)' : 'Minimal revisions'}
              </div>
            </div>

            <div style="text-align: center; padding: 20px; background: #f0f9ff; border-radius: 12px; border: 2px solid #93c5fd;">
              <div style="font-size: 32px; font-weight: 700; color: #2563eb; margin-bottom: 5px;">
                ${typedWordCount}
              </div>
              <div style="font-size: 13px; color: #6b7280; font-weight: 500;">Words Typed</div>
              <div style="font-size: 11px; color: #9ca3af; margin-top: 5px;">
                Original content
              </div>
            </div>
          </div>
        </div>

        <!-- Section 3: Content Timeline (FILTERED — only submitted content) -->
        <div style="background: white; border-radius: 20px; padding: 30px; margin-bottom: 30px; box-shadow: 0 10px 40px rgba(0,0,0,0.08);">
          <h3 style="margin: 0 0 5px 0; color: #1f2937; font-size: 18px; font-weight: 600; display: flex; align-items: center;">
            <span style="display: inline-block; width: 4px; height: 24px; background: #06b6d4; margin-right: 12px; border-radius: 2px;"></span>
            Content Timeline
          </h3>
          <p style="margin: 0 0 25px 16px; font-size: 12px; color: #9ca3af;">Only events present in the submitted document are shown</p>

          <div style="margin: 20px 0;">
            ${relevantSegments.length > 0 ? relevantSegments.slice(0, 20).map(segment => {
              const barColor = segment.type === 'typed' ?
                (segment.wpm < 100 ? '#10b981' : '#fbbf24') : '#ef4444'
              const barWidth = Math.min(segment.text.length / 10, 100)
              const timeStr = new Date(segment.timestamp).toLocaleTimeString()
              return '<div style="display: flex; align-items: center; margin-bottom: 12px;">' +
                '<div style="width: 80px; font-size: 11px; color: #9ca3af; text-align: right; padding-right: 10px;">' + timeStr + '</div>' +
                '<div style="flex: 1; position: relative;">' +
                  '<div style="background: ' + barColor + '; height: 30px; width: ' + barWidth + '%; border-radius: 5px; position: relative; min-width: 60px;">' +
                    '<div style="position: absolute; left: 10px; top: 50%; transform: translateY(-50%); color: white; font-size: 11px; font-weight: 600;">' +
                      (segment.type === 'typed' ? segment.wpm + ' WPM' :
                        segment.type === 'external_paste' ? 'PASTE' : 'REUSE') +
                    '</div>' +
                  '</div>' +
                  '<div style="font-size: 10px; color: #6b7280; margin-top: 4px; margin-left: 10px;">' +
                    (segment.text || '').substring(0, 50) + ((segment.text || '').length > 50 ? '...' : '') +
                    (segment.duration > 0 ? ' (' + Math.round(segment.duration / 1000) + 's)' : ' (instant)') +
                  '</div>' +
                '</div>' +
              '</div>'
            }).join('') : '<div style="text-align: center; color: #9ca3af; padding: 20px;">' +
              '<div style="font-size: 14px; margin-bottom: 10px;">No writing activity in submitted document</div>' +
            '</div>'}
            ${relevantSegments.length > 20 ? '<div style="text-align: center; color: #9ca3af; font-size: 12px; margin-top: 15px;">... and ' + (relevantSegments.length - 20) + ' more events</div>' : ''}
          </div>

          <!-- Legend -->
          <div style="display: flex; justify-content: center; gap: 20px; margin-top: 20px; padding-top: 20px; border-top: 1px solid #e5e7eb;">
            <span style="font-size: 12px;"><span style="display: inline-block; width: 12px; height: 12px; background: #10b981; border-radius: 2px;"></span> Typed (10-80 WPM)</span>
            <span style="font-size: 12px;"><span style="display: inline-block; width: 12px; height: 12px; background: #fbbf24; border-radius: 2px;"></span> Fast (>80 WPM)</span>
            <span style="font-size: 12px;"><span style="display: inline-block; width: 12px; height: 12px; background: #ef4444; border-radius: 2px;"></span> Pasted</span>
          </div>
        </div>

        <!-- Section 4: Process Consistency (aligned with Integrity Report) -->
        <div style="background: white; border-radius: 20px; padding: 30px; box-shadow: 0 10px 40px rgba(0,0,0,0.08);">
          <h3 style="margin: 0 0 20px 0; color: #1f2937; font-size: 18px; font-weight: 600; display: flex; align-items: center;">
            <span style="display: inline-block; width: 4px; height: 24px; background: #06b6d4; margin-right: 12px; border-radius: 2px;"></span>
            Process Consistency
          </h3>

          <div style="background: #f9fafb; border-radius: 12px; padding: 20px;">
            ${typedPercent < 50 ? '<div style="display: flex; align-items: start; margin-bottom: 15px;">' +
              '<span style="color: #ef4444; font-size: 20px; margin-right: 10px;">⚠️</span>' +
              '<div>' +
                '<div style="font-weight: 600; color: #dc2626; margin-bottom: 5px;">Significant External Content</div>' +
                '<div style="color: #6b7280; font-size: 13px;">Only ' + typedPercent + '% of the submitted document was typed by the student. ' + (100 - typedPercent) + '% was pasted from external sources.</div>' +
              '</div>' +
            '</div>' : ''}

            ${_aiProb !== null && _aiProb > 50 ? '<div style="display: flex; align-items: start; margin-bottom: 15px;">' +
              '<span style="color: #f59e0b; font-size: 20px; margin-right: 10px;">⚠️</span>' +
              '<div>' +
                '<div style="font-weight: 600; color: #d97706; margin-bottom: 5px;">AI Content Detected</div>' +
                '<div style="color: #6b7280; font-size: 13px;">AI detection indicates ' + _aiProb + '% probability of AI-generated content in this submission.</div>' +
              '</div>' +
            '</div>' : ''}

            ${avgWPM !== -1 && (avgWPM < 20 || avgWPM > 100) ? '<div style="display: flex; align-items: start; margin-bottom: 15px;">' +
              '<span style="color: #f59e0b; font-size: 20px; margin-right: 10px;">⚠️</span>' +
              '<div>' +
                '<div style="font-weight: 600; color: #d97706; margin-bottom: 5px;">Unusual Typing Speed</div>' +
                '<div style="color: #6b7280; font-size: 13px;">Average typing speed of ' + Math.round(avgWPM) + ' WPM is ' + (avgWPM > 100 ? 'above' : 'below') + ' the normal range (20-80 WPM).</div>' +
              '</div>' +
            '</div>' : ''}

            ${typedPercent >= 80 && (_aiProb === null || _aiProb <= 20) && (avgWPM === -1 || (avgWPM >= 20 && avgWPM <= 80)) ? '<div style="display: flex; align-items: start;">' +
              '<span style="color: #10b981; font-size: 20px; margin-right: 10px;">✅</span>' +
              '<div>' +
                '<div style="font-weight: 600; color: #059669; margin-bottom: 5px;">Authentic Writing Process</div>' +
                '<div style="color: #6b7280; font-size: 13px;">' + typedPercent + '% of content was typed by the student with natural editing patterns.</div>' +
              '</div>' +
            '</div>' : ''}

            ${typedPercent >= 50 && typedPercent < 80 && (_aiProb === null || _aiProb <= 50) ? '<div style="display: flex; align-items: start;">' +
              '<span style="color: #f59e0b; font-size: 20px; margin-right: 10px;">📝</span>' +
              '<div>' +
                '<div style="font-weight: 600; color: #d97706; margin-bottom: 5px;">Mixed Content</div>' +
                '<div style="color: #6b7280; font-size: 13px;">' + typedPercent + '% of content was typed. Some external content was incorporated. Manual review recommended.</div>' +
              '</div>' +
            '</div>' : ''}
          </div>
        </div>

        <!-- Footer -->
        <div style="text-align: center; margin-top: 30px; padding: 0 40px;">
          <p style="color: #9ca3af; font-size: 11px; line-height: 1.6;">
            This forensic analysis reflects the state of the document at submission time.
            Only events whose content is present in the submitted document are shown.
          </p>
        </div>
      </div>
    </div>
  `
}

// Helper function when no timeline data exists
const getNoTimelineWarning = () => {
  const { integrity } = useStore()
  const trustScore = integrity?.value?.scores?.trust ?? 0
  const externalPastes = window.INTEGRITY_DATABASE?.externalPastes?.length || 0
  
  return `
    <div class="timeline-report-page" style="page-break-before: always; padding: 0; margin: 0; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;">
      <div style="background: linear-gradient(135deg, #ef4444 0%, #dc2626 100%); padding: 60px 40px 40px; position: relative; overflow: hidden;">
        <div style="position: relative; z-index: 1;">
          <div style="display: flex; justify-content: space-between; align-items: center;">
            <div>
              <h1 style="color: white; margin: 0; font-size: 36px; font-weight: 700;">Editorrah</h1>
              <p style="color: rgba(255,255,255,0.9); margin: 5px 0 0 0; font-size: 14px; text-transform: uppercase; letter-spacing: 2px;">Writing Process Analysis</p>
            </div>
            <div style="background: white; border-radius: 10px; padding: 8px 16px;">
              <span style="color: #ef4444; font-weight: 600; font-size: 14px;">🚨 Warning</span>
            </div>
          </div>
        </div>
      </div>
      
      <div style="padding: 40px; background: #f8f9fa;">
        <div style="background: white; border-radius: 20px; padding: 40px; box-shadow: 0 10px 40px rgba(0,0,0,0.08); text-align: center;">
          <div style="font-size: 60px; margin-bottom: 20px;">🚨</div>
          <h2 style="color: #dc2626; margin: 0 0 15px 0; font-size: 24px;">No Writing Activity Recorded</h2>
          <p style="color: #6b7280; font-size: 14px; max-width: 500px; margin: 0 auto 30px;">
            The system did not detect any keyboard typing during this session. 
            All content appears to have been pasted from external sources.
          </p>
          
          <div style="display: grid; grid-template-columns: repeat(3, 1fr); gap: 20px; margin-top: 30px;">
            <div style="background: #fee2e2; padding: 20px; border-radius: 12px;">
              <div style="font-size: 28px; font-weight: 700; color: #dc2626;">${trustScore}%</div>
              <div style="font-size: 12px; color: #6b7280;">Typing Trust</div>
            </div>
            <div style="background: #fee2e2; padding: 20px; border-radius: 12px;">
              <div style="font-size: 28px; font-weight: 700; color: #dc2626;">0</div>
              <div style="font-size: 12px; color: #6b7280;">Typing Segments</div>
            </div>
            <div style="background: #fee2e2; padding: 20px; border-radius: 12px;">
              <div style="font-size: 28px; font-weight: 700; color: #dc2626;">${externalPastes}</div>
              <div style="font-size: 12px; color: #6b7280;">External Pastes</div>
            </div>
          </div>
          
          <div style="margin-top: 30px; padding: 20px; background: #fef2f2; border-radius: 12px; border: 2px solid #fca5a5;">
            <div style="font-weight: 600; color: #dc2626; margin-bottom: 10px;">⚠️ Authenticity Concern</div>
            <div style="color: #6b7280; font-size: 13px;">
              Documents created without typing activity may indicate content was copied from external sources. 
              Manual review is strongly recommended.
            </div>
          </div>
        </div>
      </div>
    </div>
  `
}

const getIframeCode = () => {
  // For infinite canvas, use A4 as default print size
  const printSize = {
    width: 21, // A4 width in cm
    height: 29.7 // A4 height in cm
  }
  
  return `
    <!DOCTYPE html>
    <html lang="hi-IN" theme-mode="${options.value.theme}">
    <head>
      <meta charset="UTF-8">
      <meta name="viewport" content="width=device-width, initial-scale=1.0">
      ${getStylesHtml()}
      <style>
      @page {
        size: ${printSize.width}cm ${printSize.height}cm;
        margin: 2cm 1.5cm;
        background: white;
      }
      
      body {
        margin: 0;
        padding: 0;
        font-family: inherit;
        line-height: ${defaultLineHeight};
      }
      
      .editor-container {
        width: 100%;
        max-width: none;
        margin: 0;
        padding: 0;
      }
      
      .tiptap {
        outline: none;
        border: none;
        padding: 0;
        margin: 0;
        width: 100%;
        min-height: auto;
      }
      
      /* Hide any canvas-specific UI elements */
      .canvas-controls,
      .zoom-controls,
      .toolbar,
      .floating-menu {
        display: none !important;
      }
      
      /* Ensure content flows properly for print */
      .ProseMirror {
        page-break-inside: avoid;
        break-inside: avoid;
      }
      
      /* Handle images and media for print */
      img, video, audio {
        max-width: 100%;
        height: auto;
        page-break-inside: avoid;
      }
      
      /* Table print styles */
      table {
        border-collapse: collapse;
        width: 100%;
        page-break-inside: avoid;
      }
      
      /* Heading break styles */
      h1, h2, h3, h4, h5, h6 {
        page-break-after: avoid;
        break-after: avoid;
      }
      
      /* Paragraph orphan/widow control */
      p {
        orphans: 2;
        widows: 2;
      }
      
      /* INTEGRITY HIGHLIGHTING - Show external pasted content in red */
      mark[data-integrity="paste"],
      mark[data-integrity="retyped"] {
        print-color-adjust: exact !important;
        -webkit-print-color-adjust: exact !important;
        color-adjust: exact !important;
        display: inline-block !important;
      }

      mark[data-integrity="paste"] {
        background-color: #ffcccc !important;
        color: #000 !important;
        padding: 3px 5px !important;
        border-radius: 3px !important;
        border-bottom: 3px solid #f44336 !important;
        font-weight: 500 !important;
      }

      mark[data-integrity="retyped"] {
        background-color: #fff3e0 !important;
        color: #000 !important;
        padding: 3px 5px !important;
        border-radius: 3px !important;
        border-bottom: 3px solid #ff9800 !important;
        font-weight: 500 !important;
      }

      mark[data-integrity] sup {
        font-size: 9px !important;
        font-weight: 700 !important;
        margin-left: 2px !important;
        print-color-adjust: exact !important;
        -webkit-print-color-adjust: exact !important;
        color-adjust: exact !important;
      }

      /* Ensure marks work well in print */
      @media print {
        mark[data-integrity] {
          break-inside: avoid;
        }
      }
      </style>
    </head>
    <body class="umo-editor-container is-print">
      <div id="sprite-plyr" style="display: none;">
        ${getPlyrSprite()}
      </div>
      <div class="editor-container" style="line-height: ${defaultLineHeight};">
        ${_cleanStudentOutput() ? '' : getHighlightLegend()}
        <div class="tiptap umo-editor" translate="no">
          ${getContentHtml()}
        </div>
      </div>
      ${_cleanStudentOutput() ? '' : getIntegrityReport()}
      ${(!_cleanStudentOutput() && assignmentToolSettings?.value?.analyze_integrity_enabled !== false) ? getTimelineReport() : ''}
    </body>
    </html>`
}

// Store verification results globally for PDF inclusion
// Using plain variables (not $ref) to avoid reactivity issues with closures
let stylometryResult = null
let aiDetectionResult = null
let chunkAnalysisResult = null

const printPage = async () => {
  const { integrity } = useStore()
  
  // Show loading overlay immediately
  isGeneratingPDF = true
  loadingStep = 1
  loadingProgress = 5
  loadingMessage = 'Preparing your document...'
  loadingSubMessage = 'Analyzing content integrity'
  
  // ALWAYS re-run analysis before generating the report. A stale lastAnalyzed
  // (restored session, analysis from minutes ago) would otherwise freeze the
  // score, desync content_hash (false content_mismatch flags for honest
  // students), and keep stale ghost-writing flags alive.
  if (integrity?.value?.active || assignmentToolSettings?.value) {
    console.log('🖨️ Running fresh integrity analysis before print...')
    loadingSubMessage = 'Running integrity analysis...'

    // Auto-run analysis without confirm dialog for better UX
    if (window.analyzeIntegrityNow) {
      console.log('🔍 Running integrity analysis before print...')
      loadingProgress = 15
      // Server-set security flags must survive the analysis (the analyze
      // store-write replaces the flags array with fresh client flags only).
      const _preservedFlags = (integrity?.value?.flags || []).filter(f =>
        f === 'signature_invalid' || String(f).startsWith('SESSION_OWNER_MISMATCH'))
      try {
        await window.analyzeIntegrityNow()
        // Wait for state to update
        await new Promise(resolve => setTimeout(resolve, 500))
      } catch (e) {
        console.warn('⚠️ Pre-print analysis failed (continuing with last state):', e)
      }
      if (_preservedFlags.length && integrity?.value && Array.isArray(integrity.value.flags)) {
        for (const f of _preservedFlags) {
          if (!integrity.value.flags.includes(f)) integrity.value.flags.push(f)
        }
      }
      console.log('✅ Analysis complete, proceeding with print')
    }
  }
  
  loadingProgress = 25
  loadingStep = 1
  
  // =========================================================================
  // EARLY EXIT: Skip expensive API calls if ≥98% external paste
  // This is clearly a cheating case - no need to waste API tokens
  // =========================================================================
  // FIX: Read from mix (where IntegrityTracker stores the values), not scores
  const externalPasteRatio = integrity?.value?.mix?.external ?? integrity?.value?.scores?.external ?? 0
  const typedRatio = integrity?.value?.mix?.typed ?? integrity?.value?.scores?.typed ?? 0
  const baseTrust = integrity?.value?.scores?.trust ?? 0

  // Read teacher tool settings
  const _ts = assignmentToolSettings?.value || {}
  const caOn  = _ts.analyze_integrity_enabled !== false
  const aiOn  = _ts.gptzero_enabled !== false
  const styOn = _ts.stylometry_enabled !== false

  // Track if we skipped API calls
  let apiCallsSkipped = false
  chunkAnalysisResult = null  // reset for this run (declared at script level)

  console.log('═══════════════════════════════════════════════════════════')
  console.log('🔍 CHECKING EXTERNAL PASTE RATIO...')
  console.log(`   External paste: ${Math.round(externalPasteRatio * 100)}%`)
  console.log(`   Typed: ${Math.round(typedRatio * 100)}%`)
  console.log(`   Tools: CA=${caOn} AI=${aiOn} Stylo=${styOn}`)
  console.log('═══════════════════════════════════════════════════════════')

  if (caOn && externalPasteRatio >= 0.98) {
    // =====================================================================
    // FAST PATH: 98%+ external paste = obvious cheating
    // Skip Stylometry & AI Detection API calls to save tokens/time
    // =====================================================================
    console.log('🚨 EARLY EXIT: ≥98% external paste detected!')
    console.log('   → Skipping Stylometry API (saves tokens)')
    console.log('   → Skipping AI Detection API (saves tokens)')
    console.log('   → Trust Score = 0% (no original content)')
    
    apiCallsSkipped = true
    
    // Set results to indicate skipped
    stylometryResult = {
      verified: null,
      score: 0,
      similarity: 0,
      verdict: null,
      skipped: true,
      reason: 'external_paste_detected',
      message: 'Skipped - No original content to verify'
    }
    
    aiDetectionResult = {
      ai_probability: 0,
      predicted_class: 'skipped',
      skipped: true,
      reason: 'external_paste_detected',
      message: 'Skipped - No original content to analyze'
    }
    
    // Update loading to show completion
    loadingStep = 4
    loadingProgress = 80
    loadingMessage = 'Analysis complete'
    loadingSubMessage = 'External content detected - generating report'
    
    // Update integrity store — `trust` stays the typing-provenance score (≈0 here).
    if (integrity.value) {
      integrity.value = {
        ...integrity.value,
        scores: {
          ...integrity.value.scores,
          base_trust: baseTrust,
          api_skipped: true
        },
        stylometry: stylometryResult,
        aiDetection: aiDetectionResult,
        lastAnalyzed: integrity.value.lastAnalyzed || Date.now()
      }
    }
    
    console.log('═══════════════════════════════════════════════════════════')
    console.log('📊 FINAL: Trust = 0% (100% external paste)')
    console.log('═══════════════════════════════════════════════════════════')
    
  } else {
    // =====================================================================
    // NORMAL PATH: Run full analysis with API calls
    // =====================================================================
    
    // =========================================================================
    // STYLOMETRY VERIFICATION - Run BEFORE generating PDF
    // =========================================================================
    console.log('═══════════════════════════════════════════════════════════')
    console.log('🔍 STYLOMETRY VERIFICATION STARTING...')
    console.log('═══════════════════════════════════════════════════════════')
    
    loadingStep = 2
    loadingProgress = 35
    loadingMessage = 'Verifying authorship...'
    loadingSubMessage = 'Analyzing writing style against your baseline'
    
    stylometryResult = null

    if (styOn) {
      try {
        const verifyResult = await verifyStylometry()
        stylometryResult = verifyResult
        console.log('✅ STYLOMETRY COMPLETE:', JSON.stringify(stylometryResult, null, 2))
        loadingProgress = 50
      } catch (e) {
        console.error('❌ STYLOMETRY FAILED:', e)
        stylometryResult = { verified: null, reason: 'error', error: e.message }
      }
    } else {
      console.log('⏭️ Stylometry skipped (disabled by teacher)')
      stylometryResult = { verified: null, reason: 'disabled_by_teacher', skipped: true }
      loadingProgress = 50
    }
    
    console.log('📊 stylometryResult:', stylometryResult?.verified, stylometryResult?.similarity)
    
    // =========================================================================
    // AI DETECTION - Run BEFORE generating PDF
    // =========================================================================
    console.log('═══════════════════════════════════════════════════════════')
    console.log('🤖 AI DETECTION STARTING...')
    console.log('═══════════════════════════════════════════════════════════')
    
    loadingStep = 3
    loadingProgress = 55
    loadingMessage = 'Checking for AI content...'
    loadingSubMessage = 'Running AI analysis'
    
    aiDetectionResult = null

    if (aiOn) {
      try {
        const aiResult = await verifyAI()
        aiDetectionResult = aiResult
        console.log('✅ AI DETECTION COMPLETE:', JSON.stringify(aiDetectionResult, null, 2))
        loadingProgress = 75
      } catch (e) {
        console.error('❌ AI DETECTION FAILED:', e)
        aiDetectionResult = { ai_probability: 0, status: 'error', error: e.message }
      }
    } else {
      console.log('⏭️ AI detection skipped (disabled by teacher)')
      aiDetectionResult = { ai_probability: 0, status: 'skipped', reason: 'disabled_by_teacher' }
      loadingProgress = 75
    }
    
    console.log('📊 aiDetectionResult:', aiDetectionResult?.ai_probability, aiDetectionResult?.predicted_class)

    // =========================================================================
    // CHUNK-LEVEL ANALYSIS — mixed content detection
    // Uses external pastes (CA on) or blind windows (CA off) as chunks.
    // Runs GPTZero + stylometry per-chunk to catch dilution attacks.
    // =========================================================================
    function buildChunks(caIsOn) {
      const fullText = editor.value?.getText() || ''
      const words = fullText.split(/\s+/).filter(w => w)

      // ALWAYS blind-window the full document — catches typed AI regardless of CA
      const chunks = []
      if (words.length >= 200) {
        const WINDOW = 300, OVERLAP = 150
        for (let i = 0; i < words.length; i += (WINDOW - OVERLAP)) {
          const slice = words.slice(i, i + WINDOW)
          if (slice.length < 100) break
          chunks.push({ text: slice.join(' '), source: 'window', word_count: slice.length })
        }
      }

      // When CA is on, also add paste-aligned chunks (deduped against windows)
      if (caIsOn) {
        const pastes = filterPastesByEditorContent(integrity?.value?.externalPastesFound || [])
        for (const paste of pastes) {
          const text = (paste.text || '').trim()
          const wc = text.split(/\s+/).filter(w => w).length
          if (wc < 50) continue
          // Dedupe: skip if >70% of paste words already appear in an existing window chunk
          const pasteWords = new Set(text.toLowerCase().split(/\s+/))
          const isDuplicate = chunks.some(c => {
            if (c.source !== 'window') return false
            const cWords = c.text.toLowerCase().split(/\s+/)
            const overlap = cWords.filter(w => pasteWords.has(w)).length
            return overlap / pasteWords.size > 0.7
          })
          if (!isDuplicate) {
            chunks.push({ text, source: 'paste', word_count: wc })
          }
        }
      }

      // Cap at 20 chunks (backend limit) — prioritize windows, then pastes
      if (chunks.length > 20) {
        const windows = chunks.filter(c => c.source === 'window')
        const pastes = chunks.filter(c => c.source === 'paste')
        return [...windows, ...pastes].slice(0, 20)
      }

      return chunks
    }

    const chunks = buildChunks(caOn)
    if (chunks.length > 0 && (aiOn || styOn)) {
      try {
        console.log(`🔍 CHUNK ANALYSIS: ${chunks.length} chunks to analyze...`)
        loadingSubMessage = 'Analyzing content chunks...'
        const chunkApiUrl = getApiUrl()
        const chunkToken = localStorage.getItem('auth_token')
        const urlParams = new URLSearchParams(window.location.search)
        const classId = urlParams.get('class_id')
        const chunkResp = await fetch(`${chunkApiUrl}/api/chunk-analyze`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json', 'Authorization': `Bearer ${chunkToken}` },
          body: JSON.stringify({ class_id: classId, chunks, ai_enabled: aiOn, stylo_enabled: styOn })
        })
        if (chunkResp.ok) {
          chunkAnalysisResult = await chunkResp.json()
          console.log('✅ CHUNK ANALYSIS:', chunkAnalysisResult?.summary)
        } else {
          console.warn('⚠️ Chunk analysis returned:', chunkResp.status)
        }
      } catch (e) {
        console.error('❌ Chunk analysis failed (non-blocking):', e)
      }
    } else {
      console.log('⏭️ Chunk analysis skipped (no chunks or no tools)')
    }

    // =========================================================================
    // INDIVIDUAL INTEGRITY SIGNALS — no composite/weighted rollup.
    // Typing trust, stylometry verdict, and AI probability are reported side
    // by side; nothing is multiplied or averaged.
    // =========================================================================
    console.log('═══════════════════════════════════════════════════════════')
    console.log('📊 COLLECTING INDIVIDUAL INTEGRITY SIGNALS...')
    console.log(`   Tools: CA=${caOn} AI=${aiOn} Stylo=${styOn}`)
    console.log('═══════════════════════════════════════════════════════════')

    // Extract signals (normalized 0-1)
    const P_proc = typedRatio
    const S_style = stylometryResult?.cosine_score ?? stylometryResult?.score ?? stylometryResult?.similarity ?? 0.5
    const P_ai = aiDetectionResult?.ai_probability ?? 0

    const styloVerdict = stylometryResult?.verdict

    // Ghost-writing flag (display-only): high typed % but AI-flagged + style mismatch.
    if (caOn && aiOn && styOn
        && P_proc > 0.8 && P_ai > 0.8
        && styloVerdict === 'flagged'
        && integrity.value && Array.isArray(integrity.value.flags)
        && !integrity.value.flags.includes('ghost_writing_suspected')) {
      integrity.value.flags.push('ghost_writing_suspected')
      console.log('   🚩 Ghost-writing suspected: typed>80%, AI>80%, stylometry flagged')
    }

    console.log(`   ✅ SIGNALS: typing=${Math.round(P_proc * 100)}% | stylometry=${styloVerdict ?? 'n/a'} | AI=${Math.round(P_ai * 100)}%`)

    // Update integrity store — `trust` stays the typing-provenance score.
    if (integrity.value) {
      integrity.value = {
        ...integrity.value,
        scores: {
          ...integrity.value.scores,
          base_trust: baseTrust,
          P_proc: P_proc,
          S_style: S_style,
          P_ai: P_ai,
          api_skipped: false,
          caOn, aiOn, styOn
        },
        stylometry: stylometryResult,
        aiDetection: aiDetectionResult,
        lastAnalyzed: integrity.value.lastAnalyzed || Date.now()
      }
    }
  }
  
  console.log('🖨️ Starting print with integrity data:', {
    externalPastes: integrity?.value?.externalPastesFound?.length || 0,
    retypedExternal: integrity?.value?.retypedExternalDetected?.length || 0,
    trustScore: integrity?.value?.scores?.trust || 'N/A',
    stylometry: stylometryResult
  })
  
  // Update loading state for PDF generation
  loadingStep = 4
  loadingProgress = 85
  loadingMessage = 'Generating PDF...'
  loadingSubMessage = 'Building your integrity report'
  
  editor.value.commands.blur()
  
  try {
    iframeCode = getIframeCode()
  } catch (iframeError) {
    console.error('Failed to generate report HTML:', iframeError)
    // CRITICAL: If we have an assignment submit callback, fire it with an error
    // so the spinner in EditorPage stops and the student sees a real error message.
    if (window._assignmentSubmitCallback) {
      isGeneratingPDF = false
      window._assignmentSubmitCallback({
        error: true,
        errorMessage: 'Failed to generate integrity report: ' + (iframeError.message || 'Unknown error'),
        reportHtml: '',
        trustScore: integrity?.value?.scores?.trust,  // typing provenance
        baseTrustScore: baseTrust,
        contentMix: integrity?.value?.mix ?? { typed: 1.0, internal: 0, external: 0 },
        flags: [...(integrity?.value?.flags ?? []), 'report_generation_failed'],
        analysis: integrity?.value?.analysis ?? null,
        externalPastesFound: integrity?.value?.externalPastesFound ?? [],
        stylometry: stylometryResult,
        aiDetection: aiDetectionResult
      })
      printing.value = false
      exportPDF.value = false
      return
    }
    // Non-assignment mode: just alert and stop
    isGeneratingPDF = false
    alert('Failed to generate report. Please try again.')
    return
  }
  
  // Final loading state
  loadingProgress = 95
  loadingSubMessage = 'Almost done...'
  
  // Append to stylometry baseline after successful document generation
  const appendToStylometry = async () => {
    try {
      const token = localStorage.getItem('auth_token')
      if (!token) return
      
      // Get document text
      const docText = editor.value.getText()
      const wordCount = docText.trim().split(/\s+/).filter(w => w.length > 0).length
      
      // V3: Baseline absorption is handled server-side by the /course/verify flywheel.
      // No client-side append needed. The server auto-absorbs verified submissions.
      console.log(`V3 flywheel: baseline absorption handled server-side (words=${wordCount})`)
    } catch (error) {
      console.error('Stylometry append error (non-critical):', error)
    }
  }
  
  // Hide loading overlay - PDF is ready!
  loadingProgress = 100
  loadingMessage = 'PDF Ready!'
  loadingSubMessage = 'Opening print dialog...'
  
  // Small delay to show 100% before hiding
  await new Promise(resolve => setTimeout(resolve, 500))
  isGeneratingPDF = false
  
  // =========================================================================
  // ASSIGNMENT MODE: Auto-submit the generated report instead of printing
  // =========================================================================
  if (window._assignmentSubmitCallback) {
    // Capture the full report HTML from the iframe
    const reportHtml = iframeCode
    
    // Fire the callback with report HTML and integrity data
    window._assignmentSubmitCallback({
      reportHtml,
      trustScore: integrity?.value?.scores?.trust,  // null when no tools enabled (don't coalesce to 0)
      baseTrustScore: baseTrust,  // Raw typing-based trust (auth_factor only) for server comparison
      contentMix: integrity?.value?.mix ?? { typed: 1.0, internal: 0, external: 0 },
      flags: integrity?.value?.flags ?? [],
      analysis: integrity?.value?.analysis ?? null,
      externalPastesFound: integrity?.value?.externalPastesFound ?? [],
      stylometry: stylometryResult,
      aiDetection: aiDetectionResult,
      chunkAnalysis: chunkAnalysisResult
    })
    
    // Reset print state
    printing.value = false
    exportPDF.value = false
    
    // Still append to stylometry baseline
    appendToStylometry()
    return
  }
  
  const dialog = useConfirm({
    theme: 'info',
    header: printing.value ? t('print.title') : t('export.pdf.title'),
    body: printing.value ? t('print.message') : t('export.pdf.message'),
    confirmBtn: printing.value ? t('print.confirm') : t('export.pdf.confirm'),
    onConfirm() {
      dialog.destroy()
      setTimeout(() => {
        iframeRef.contentWindow.print()
        // Append to stylometry baseline after print
        appendToStylometry()
      }, 300)
    },
    onClosed() {
      printing.value = false
      exportPDF.value = false
    },
  })
}

// Verify document against user's stylometry baseline
async function verifyStylometry() {
  console.log('🔍 Starting stylometry verification...')
  
  try {
    const token = localStorage.getItem('auth_token')
    if (!token) {
      return { verified: null, reason: 'not_authenticated' }
    }
    
    // Get document text
    const docText = editor.value?.getText() || ''
    const wordCount = docText.trim().split(/\s+/).filter(w => w.length > 0).length
    console.log(`📄 Document: ${wordCount} words`)
    
    if (wordCount < 50) {
      console.log('⚠️ Document too short for stylometry verification')
      return { verified: null, reason: 'document_too_short', wordCount }
    }
    
    const API = getApiUrl()
    
    // V3: Use per-course verification if class_id is available
    const urlParams = new URLSearchParams(window.location.search)
    const classId = urlParams.get('class_id')
    
    if (classId) {
      console.log(`🌐 V3 stylometry verify for class: ${classId}`)
      const response = await fetch(`${API}/api/stylometry/v3/verify`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', 'Authorization': `Bearer ${token}` },
        body: JSON.stringify({ class_id: classId, submission_text: docText })
      })
      
      if (response.ok) {
        const v3Result = await response.json()
        console.log('V3 stylometry result:', v3Result)

        return {
          verified: v3Result.verdict === 'verified',
          score: v3Result.probability,
          similarity: v3Result.cosine_score,
          verdict: v3Result.verdict,
          confidence: v3Result.confidence,
          probability: v3Result.probability,
          cosine_score: v3Result.cosine_score,
          z_score: v3Result.z_score,
          profile_strength: v3Result.profile_strength,
          profile_absorbed: v3Result.profile_absorbed,
          n_profile_essays: v3Result.n_profile_essays,
          submission_word_count: v3Result.submission_word_count,
          explanation: v3Result.explanation,
          timestamp: new Date().toISOString(),
          version: 'v3'
        }
      }
      const errorText = await response.text()
      console.log('V3 stylometry error:', errorText)
      return { verified: null, reason: 'v3_error', error: errorText }
    }
    
    // No class_id — not in assignment mode, skip stylometry
    console.log('No class_id in URL — skipping stylometry (not in assignment mode)')
    return {
      verified: null,
      verdict: 'inconclusive',
      reason: 'no_class_context',
      message: 'Stylometry requires assignment context (class enrollment)',
      timestamp: new Date().toISOString()
    }
  } catch (error) {
    console.error('❌ Stylometry verification error:', error)
    return { verified: null, reason: 'network_error', error: error.message }
  }
}

// Verify document for AI-generated content
async function verifyAI() {
  try {
    const token = localStorage.getItem('auth_token')
    if (!token) {
      return { ai_probability: 0, status: 'not_authenticated' }
    }
    
    // Get document text
    const docText = editor.value?.getText() || ''
    const wordCount = docText.trim().split(/\s+/).filter(w => w.length > 0).length
    
    if (wordCount < 100) {
      return { ai_probability: 0, status: 'document_too_short', wordCount }
    }
    
    const API = getApiUrl()
    
    // Call AI detection endpoint
    // FIX #7: Use Authorization header, not query param
    const response = await fetch(`${API}/api/auth/ai-detection/verify`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', 'Authorization': `Bearer ${token}` },
      body: JSON.stringify({ text: docText })
    })
    
    console.log(`📡 Response status: ${response.status}`)
    
    if (!response.ok) {
      const errorText = await response.text()
      console.log('⚠️ AI detection error:', errorText)
      return { ai_probability: 0, status: 'api_error', error: errorText }
    }
    
    const result = await response.json()
    console.log('✅ AI detection result:', result)
    
    return {
      ai_probability: result.ai_probability || 0,
      human_probability: result.human_probability || 0,
      mixed_probability: result.mixed_probability || 0,
      // A failed run must not carry a fabricated class — 'unknown' defeats the
      // "did it actually run" guards downstream in the teacher UI.
      predicted_class: (result.status && result.status !== 'success') ? null : (result.predicted_class || 'unknown'),
      confidence: result.confidence || 'unknown',
      status: result.status || 'success',
      word_count: result.word_count || wordCount,
      timestamp: new Date().toISOString()
    }
  } catch (error) {
    console.error('❌ AI detection error:', error)
    return { ai_probability: 0, status: 'network_error', error: error.message }
  }
}

watch(
  () => [printing.value, exportPDF.value],
  (value) => {
    if (value[0] || value[1]) {
      printPage()
    }
  },
)
</script>

<style lang="less" scoped>
.umo-print-iframe {
  position: absolute;
  width: 0;
  height: 0;
  border: none;
  overflow: auto;
}

// Loading overlay styles
.print-loading-overlay {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background: rgba(0, 0, 0, 0.85);
  backdrop-filter: blur(8px);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 99999;
  animation: fadeIn 0.3s ease;
}

@keyframes fadeIn {
  from { opacity: 0; }
  to { opacity: 1; }
}

.print-loading-content {
  background: white;
  border-radius: 20px;
  padding: 40px 50px;
  text-align: center;
  max-width: 420px;
  width: 90%;
  box-shadow: 0 25px 60px rgba(0, 0, 0, 0.3);
  animation: slideUp 0.4s ease;
}

@keyframes slideUp {
  from { 
    opacity: 0;
    transform: translateY(30px);
  }
  to { 
    opacity: 1;
    transform: translateY(0);
  }
}

.print-loading-content h3 {
  margin: 20px 0 8px 0;
  font-size: 22px;
  font-weight: 700;
  color: #1f2937;
}

.print-loading-content p {
  margin: 0 0 25px 0;
  font-size: 14px;
  color: #6b7280;
}

.print-spinner {
  width: 60px;
  height: 60px;
  margin: 0 auto;
  border: 4px solid #e5e7eb;
  border-top-color: #667eea;
  border-radius: 50%;
  animation: spin 1s linear infinite;
}

@keyframes spin {
  to { transform: rotate(360deg); }
}

.print-progress-bar {
  height: 8px;
  background: #e5e7eb;
  border-radius: 4px;
  overflow: hidden;
  margin-bottom: 25px;
}

.print-progress-fill {
  height: 100%;
  background: linear-gradient(90deg, #667eea 0%, #764ba2 100%);
  border-radius: 4px;
  transition: width 0.4s ease;
}

.print-steps {
  display: flex;
  flex-direction: column;
  gap: 12px;
  text-align: left;
}

.print-step {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 10px 15px;
  background: #f3f4f6;
  border-radius: 10px;
  font-size: 14px;
  color: #9ca3af;
  transition: all 0.3s ease;
}

.print-step.active {
  background: #eef2ff;
  color: #4f46e5;
  font-weight: 500;
}

.print-step.done {
  background: #ecfdf5;
  color: #059669;
}

.step-icon {
  width: 24px;
  height: 24px;
  display: flex;
  align-items: center;
  justify-content: center;
  background: currentColor;
  color: white;
  border-radius: 50%;
  font-size: 12px;
  font-weight: 700;
  flex-shrink: 0;
}

.print-step.active .step-icon {
  background: #4f46e5;
  animation: pulse 1.5s infinite;
}

.print-step.done .step-icon {
  background: #059669;
}

@keyframes pulse {
  0%, 100% { transform: scale(1); }
  50% { transform: scale(1.1); }
}
</style>