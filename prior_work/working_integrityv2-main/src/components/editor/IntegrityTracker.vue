<template>
  <div style="display: none"></div>
</template>

<script setup>
import { onMounted, onUnmounted, watch } from 'vue'
import { useStore } from '@/composables/store'
import { getApiUrl } from '@/utils/api-url'
import axios from 'axios'

const { integrity, editor } = useStore()
const INTEGRITY_API = getApiUrl()

// ============================================================================
// ROBUST INTEGRITY TRACKING v3
// ============================================================================
// 
// FIXES:
// 1. Small text accuracy - Use multiple matching strategies
// 2. Mixed content - Track typed vs external separately
// 3. Proper calculation when both typed AND external content exist
//
// ALGORITHM:
// - For each character position in document, determine if it's "typed" or "external"
// - Use word-level matching for better accuracy at any size
// - Trust = typed_chars_in_doc / doc_length
//
// ============================================================================

// Generate word-based fingerprints (more robust for any text size)
function generateWordFingerprints(text) {
  const normalized = text.toLowerCase().replace(/[^a-z0-9\s]/g, ' ').replace(/\s+/g, ' ').trim()
  const words = normalized.split(' ').filter(w => w.length >= 3)
  
  const fingerprints = {
    words: new Set(words),
    bigrams: new Set(),   // 2-word phrases
    trigrams: new Set(),  // 3-word phrases
    // NEW: Character n-grams for continuous text
    charGrams: new Set()
  }
  
  // Generate bigrams
  for (let i = 0; i < words.length - 1; i++) {
    fingerprints.bigrams.add(words[i] + ' ' + words[i + 1])
  }
  
  // Generate trigrams
  for (let i = 0; i < words.length - 2; i++) {
    fingerprints.trigrams.add(words[i] + ' ' + words[i + 1] + ' ' + words[i + 2])
  }
  
  // NEW: Generate character 6-grams for continuous text matching
  const cleanText = text.toLowerCase().replace(/\s+/g, '')
  for (let i = 0; i <= cleanText.length - 6; i++) {
    fingerprints.charGrams.add(cleanText.substring(i, i + 6))
  }
  
  return fingerprints
}

// Safely convert a value to a Set (handles deserialized plain objects from localStorage)
function asSet(val) {
  if (val instanceof Set) return val
  if (Array.isArray(val)) return new Set(val)
  return new Set()
}

// Calculate match score between two fingerprint sets
function calculateMatchScore(sourceFingerprints, targetFingerprints) {
  if (!sourceFingerprints || !targetFingerprints) return 0
  
  // Ensure all fingerprint fields are real Sets (they may have been
  // deserialized from JSON where Sets become empty objects {})
  const srcWords = asSet(sourceFingerprints.words)
  const srcBigrams = asSet(sourceFingerprints.bigrams)
  const srcTrigrams = asSet(sourceFingerprints.trigrams)
  const srcCharGrams = asSet(sourceFingerprints.charGrams)
  const tgtWords = asSet(targetFingerprints.words)
  const tgtBigrams = asSet(targetFingerprints.bigrams)
  const tgtTrigrams = asSet(targetFingerprints.trigrams)
  const tgtCharGrams = asSet(targetFingerprints.charGrams)
  
  let wordMatch = 0
  let bigramMatch = 0
  let trigramMatch = 0
  let charGramMatch = 0
  
  // Word matching
  if (srcWords.size > 0) {
    for (const word of srcWords) {
      if (tgtWords.has(word)) wordMatch++
    }
    wordMatch = wordMatch / srcWords.size
  }
  
  // Bigram matching (more specific)
  if (srcBigrams.size > 0) {
    for (const bigram of srcBigrams) {
      if (tgtBigrams.has(bigram)) bigramMatch++
    }
    bigramMatch = bigramMatch / srcBigrams.size
  }
  
  // Trigram matching (most specific)
  if (srcTrigrams.size > 0) {
    for (const trigram of srcTrigrams) {
      if (tgtTrigrams.has(trigram)) trigramMatch++
    }
    trigramMatch = trigramMatch / srcTrigrams.size
  }
  
  // Character n-gram matching (handles continuous text)
  if (srcCharGrams.size > 0 && tgtCharGrams.size > 0) {
    for (const gram of srcCharGrams) {
      if (tgtCharGrams.has(gram)) charGramMatch++
    }
    charGramMatch = charGramMatch / srcCharGrams.size
  }
  
  // Weighted score - use best available method
  // If word-based matching works, prefer it
  // If not (continuous text), use character n-grams
  const wordBasedScore = (wordMatch * 0.2) + (bigramMatch * 0.3) + (trigramMatch * 0.5)
  
  // If no words or very few words, rely on character matching
  if (srcWords.size < 3 || wordBasedScore < 0.1) {
    return Math.max(wordBasedScore, charGramMatch)
  }
  
  // If no trigrams, rely more on bigrams
  if (srcTrigrams.size === 0) {
    return Math.max((wordMatch * 0.3) + (bigramMatch * 0.7), charGramMatch)
  }
  
  return Math.max(wordBasedScore, charGramMatch)
}

// Simple substring matching for small texts
function calculateSubstringMatch(sourceText, targetText) {
  const source = sourceText.toLowerCase().replace(/\s+/g, ' ').trim()
  const target = targetText.toLowerCase().replace(/\s+/g, ' ').trim()
  
  if (target.includes(source)) return 1.0
  if (source.includes(target)) return target.length / source.length
  
  // NEW: Also check without spaces (for continuous text)
  const sourceNoSpaces = source.replace(/\s/g, '')
  const targetNoSpaces = target.replace(/\s/g, '')
  
  if (targetNoSpaces.includes(sourceNoSpaces)) return 1.0
  if (sourceNoSpaces.includes(targetNoSpaces)) return targetNoSpaces.length / sourceNoSpaces.length
  
  // Check overlapping character sequences (better for continuous text)
  let matchedChars = 0
  const chunkSize = 10 // Look for 10-char chunks
  
  for (let i = 0; i <= sourceNoSpaces.length - chunkSize; i += 5) {
    const chunk = sourceNoSpaces.substring(i, i + chunkSize)
    if (targetNoSpaces.includes(chunk)) {
      matchedChars += chunkSize
    }
  }
  
  const charMatch = sourceNoSpaces.length > 0 ? Math.min(1, matchedChars / sourceNoSpaces.length) : 0
  
  // Check overlapping word phrases
  const sourceWords = source.split(' ')
  let matchedPhraseLength = 0
  
  for (let len = Math.min(5, sourceWords.length); len >= 2; len--) {
    for (let i = 0; i <= sourceWords.length - len; i++) {
      const phrase = sourceWords.slice(i, i + len).join(' ')
      if (target.includes(phrase)) {
        matchedPhraseLength += phrase.length
      }
    }
  }
  
  const phraseMatch = source.length > 0 ? Math.min(1, matchedPhraseLength / source.length) : 0
  
  // Return the best match method
  return Math.max(charMatch, phraseMatch)
}

// Initialize databases
if (!window.TYPED_DB) {
  window.TYPED_DB = {
    allTypedChars: '',
    totalTypedCount: 0,
    fingerprints: null,
    sessionStart: Date.now()
  }
  console.log('✅ TYPED_DB initialized')
}

if (!window.EXTERNAL_DB) {
  window.EXTERNAL_DB = {
    pastes: [],
    totalPastedChars: 0,
    sessionStart: Date.now()
  }
  console.log('✅ EXTERNAL_DB initialized')
}

if (!window.INTERNAL_DB) {
  window.INTERNAL_DB = {
    pastes: [],
    totalChars: 0,
    copyBuffer: []
  }
}

if (!window.TIMELINE_DB) {
  window.TIMELINE_DB = {
    segments: [],
    deletions: 0,
    additions: 0,
    currentTypingStart: null,
    currentTypingText: '',
    lastKeystroke: Date.now()
  }
}

// Autotyper / bot detection database
if (!window.AUTOTYPER_DB) {
  window.AUTOTYPER_DB = {
    ikiBuffer: [],          // circular buffer of inter-keystroke intervals (ms)
    maxBufferSize: 200,
    lastKeystrokeTime: 0,
    untrustedEventCount: 0, // events with isTrusted === false
    totalEventCount: 0,
    analysisResult: null    // { isRobotic, isSuspicious, cv, mean, stddev, untrustedRatio, flags }
  }
}

// ============================================================================
// SESSION PERSISTENCE: Restore integrity state across refresh/navigation
// Keyed by assignment_id so each assignment has its own integrity session.
// ============================================================================
const _assignmentId = new URLSearchParams(window.location.search).get('assignment_id')
const _persistKey = _assignmentId ? `integrity_session_${_assignmentId}` : null

function _saveIntegrityState() {
  if (!_persistKey) return
  try {
    const state = {
      TYPED_DB: { allTypedChars: window.TYPED_DB.allTypedChars, totalTypedCount: window.TYPED_DB.totalTypedCount },
      EXTERNAL_DB: { pastes: window.EXTERNAL_DB.pastes, totalPastedChars: window.EXTERNAL_DB.totalPastedChars },
      INTERNAL_DB: { pastes: window.INTERNAL_DB.pastes, totalChars: window.INTERNAL_DB.totalChars, copyBuffer: window.INTERNAL_DB.copyBuffer },
      TIMELINE_DB: { segments: window.TIMELINE_DB.segments, deletions: window.TIMELINE_DB.deletions, additions: window.TIMELINE_DB.additions },
      ts: Date.now()
    }
    localStorage.setItem(_persistKey, JSON.stringify(state))
  } catch { /* storage full or private mode */ }
}

function _restoreIntegrityState() {
  if (!_persistKey) return false
  try {
    const raw = localStorage.getItem(_persistKey)
    if (!raw) return false
    const state = JSON.parse(raw)
    if (Date.now() - state.ts > 24 * 60 * 60 * 1000) {
      localStorage.removeItem(_persistKey)
      return false
    }
    // Only restore if databases are currently EMPTY (avoids duplicates on re-mount)
    if (state.TYPED_DB && window.TYPED_DB.totalTypedCount === 0) {
      window.TYPED_DB.allTypedChars = state.TYPED_DB.allTypedChars || ''
      window.TYPED_DB.totalTypedCount = state.TYPED_DB.totalTypedCount || 0
    }
    if (state.EXTERNAL_DB && window.EXTERNAL_DB.pastes.length === 0) {
      const restoredPastes = state.EXTERNAL_DB.pastes || []
      // Sets don't survive JSON.stringify — regenerate fingerprints for each paste
      for (const paste of restoredPastes) {
        if (paste.text) {
          paste.fingerprints = generateWordFingerprints(paste.text)
        }
      }
      window.EXTERNAL_DB.pastes.push(...restoredPastes)
      window.EXTERNAL_DB.totalPastedChars = state.EXTERNAL_DB.totalPastedChars || 0
    }
    if (state.INTERNAL_DB && window.INTERNAL_DB.pastes.length === 0) {
      window.INTERNAL_DB.pastes.push(...(state.INTERNAL_DB.pastes || []))
      window.INTERNAL_DB.totalChars = state.INTERNAL_DB.totalChars || 0
      window.INTERNAL_DB.copyBuffer.push(...(state.INTERNAL_DB.copyBuffer || []))
    }
    if (state.TIMELINE_DB && window.TIMELINE_DB.segments.length === 0) {
      window.TIMELINE_DB.segments.push(...(state.TIMELINE_DB.segments || []))
      window.TIMELINE_DB.deletions = state.TIMELINE_DB.deletions || 0
      window.TIMELINE_DB.additions = state.TIMELINE_DB.additions || 0
    }
    console.log('✅ Integrity state restored from previous session — typed:', window.TYPED_DB.totalTypedCount, 'external pastes:', window.EXTERNAL_DB.pastes.length, 'timeline segments:', window.TIMELINE_DB.segments.length)
    return true
  } catch { return false }
}

_restoreIntegrityState()

// Save integrity state periodically and on page unload / tab switch
const _saveInterval = setInterval(_saveIntegrityState, 5000)
window.addEventListener('beforeunload', _saveIntegrityState)
window.addEventListener('pagehide', _saveIntegrityState)
document.addEventListener('visibilitychange', () => {
  if (document.visibilityState === 'hidden') _saveIntegrityState()
})

// ============================================================================
// LOOPHOLE #1 FIX: Freeze globals so they cannot be replaced from console
// The objects themselves are still mutable (our code needs to push to arrays),
// but a student cannot do `window.EXTERNAL_DB = { pastes: [] }` to replace them.
// ============================================================================
const _dbNames = ['TYPED_DB', 'EXTERNAL_DB', 'INTERNAL_DB', 'TIMELINE_DB', 'AUTOTYPER_DB']
for (const name of _dbNames) {
  try {
    Object.defineProperty(window, name, {
      value: window[name],
      writable: false,
      configurable: false
    })
  } catch (e) { /* already frozen from a previous mount */ }
}

// Tamper detection: track multiple independent signals so manipulation of one
// still gets caught by the others.
let _tamperDetected = false
let _lastPasteCount = 0
let _lastPasteChars = 0
let _lastTypedCount = 0
let _pasteTextsHash = 0

function _hashPasteTexts() {
  let h = 0
  for (const p of window.EXTERNAL_DB.pastes) {
    for (let i = 0; i < p.text.length; i++) {
      h = ((h << 5) - h + p.text.charCodeAt(i)) | 0
    }
  }
  return h
}

function _updateChecksum() {
  _lastPasteCount = window.EXTERNAL_DB.pastes.length
  _lastPasteChars = window.EXTERNAL_DB.totalPastedChars
  _lastTypedCount = window.TYPED_DB.totalTypedCount
  _pasteTextsHash = _hashPasteTexts()
}
_updateChecksum()

const _tamperInterval = setInterval(() => {
  // Paste count can only increase (append-only)
  if (window.EXTERNAL_DB.pastes.length < _lastPasteCount) {
    _tamperDetected = true
  }
  // Total pasted chars can only increase
  if (window.EXTERNAL_DB.totalPastedChars < _lastPasteChars) {
    _tamperDetected = true
  }
  // Typed count can only increase
  if (window.TYPED_DB.totalTypedCount < _lastTypedCount) {
    _tamperDetected = true
  }
  // Paste content hash must not change (text of existing pastes can't be edited)
  if (window.EXTERNAL_DB.pastes.length >= _lastPasteCount && _lastPasteCount > 0) {
    const currentHash = _hashPasteTexts()
    if (currentHash !== _pasteTextsHash && window.EXTERNAL_DB.pastes.length === _lastPasteCount) {
      _tamperDetected = true
    }
  }
  _updateChecksum()
}, 5000)

// ============================================================================
// LOOPHOLE #5 FIX: DevTools detection (non-blocking)
// Uses image-based detection instead of debugger trap to avoid freezing the
// page and clearing console, which made debugging impossible.
// ============================================================================
function _checkDevTools() {
  const threshold = 160
  const widthThreshold = window.outerWidth - window.innerWidth > threshold
  const heightThreshold = window.outerHeight - window.innerHeight > threshold
  if (widthThreshold || heightThreshold) {
    window.AUTOTYPER_DB.devtoolsDetected = true
    if (integrity.value) {
      integrity.value.devtoolsOpened = true
      integrity.value.devtoolsTimestamp = integrity.value.devtoolsTimestamp || Date.now()
    }
  }
}
const _devToolsInterval = setInterval(_checkDevTools, 10000)

// Watch for session changes — ONLY reset when switching between two REAL sessions.
// Going from null/undefined to a new session is INITIAL ASSIGNMENT, not a switch,
// and must NOT wipe the databases (which may have been restored from localStorage).
watch(() => integrity?.value?.sessionId, (newSessionId, oldSessionId) => {
  if (newSessionId && oldSessionId && newSessionId !== oldSessionId) {
    console.log('🔄 Session SWITCH detected:', oldSessionId, '->', newSessionId, '— resetting DBs')
    window.TYPED_DB.allTypedChars = ''; window.TYPED_DB.totalTypedCount = 0; window.TYPED_DB.fingerprints = null; window.TYPED_DB.sessionStart = Date.now()
    window.EXTERNAL_DB.pastes.length = 0; window.EXTERNAL_DB.totalPastedChars = 0; window.EXTERNAL_DB.sessionStart = Date.now()
    window.INTERNAL_DB.pastes.length = 0; window.INTERNAL_DB.totalChars = 0; window.INTERNAL_DB.copyBuffer.length = 0
    window.TIMELINE_DB.segments.length = 0; window.TIMELINE_DB.deletions = 0; window.TIMELINE_DB.additions = 0; window.TIMELINE_DB.currentTypingStart = null; window.TIMELINE_DB.currentTypingText = ''; window.TIMELINE_DB.lastKeystroke = Date.now()
    window.AUTOTYPER_DB.ikiBuffer.length = 0; window.AUTOTYPER_DB.lastKeystrokeTime = 0; window.AUTOTYPER_DB.untrustedEventCount = 0; window.AUTOTYPER_DB.totalEventCount = 0; window.AUTOTYPER_DB.analysisResult = null
    _tamperDetected = false
    _updateChecksum()
    if (_persistKey) localStorage.removeItem(_persistKey)
  }
})

// ============================================================================
// EVENT HANDLERS
// ============================================================================

onMounted(() => {
  console.log('🔥 INTEGRITY TRACKER v3 MOUNTED')
  document.addEventListener('keydown', handleKeydown, true)
  document.addEventListener('paste', handlePaste, true)
  document.addEventListener('copy', handleCopy, true)
  document.addEventListener('cut', handleCut, true)
  window.analyzeIntegrityNow = analyzeIntegrityNow

  // Auto-analyze if databases were restored from localStorage
  // so trust score reflects restored data instead of defaulting to 100%
  try {
    const hasRestoredData = window.TYPED_DB.totalTypedCount > 0 || window.EXTERNAL_DB.pastes.length > 0
    if (hasRestoredData && !integrity.value?.lastAnalyzed) {
      // If editor is already available (remount), analyze directly
      if (editor.value) {
        setTimeout(() => analyzeIntegrityNow(), 500)
      } else {
        // Wait for editor to become available
        const unwatch = watch(() => editor.value, (ed) => {
          if (ed) {
            unwatch()
            setTimeout(() => analyzeIntegrityNow(), 500)
          }
        })
      }
    }
  } catch (e) {
    console.warn('⚠️ Auto-analyze on restore skipped:', e)
  }
})

onUnmounted(() => {
  document.removeEventListener('keydown', handleKeydown, true)
  document.removeEventListener('paste', handlePaste, true)
  document.removeEventListener('copy', handleCopy, true)
  document.removeEventListener('cut', handleCut, true)
  clearInterval(_tamperInterval)
  clearInterval(_devToolsInterval)
  clearInterval(_saveInterval)
})

let isPasting = false
let lastPasteTime = 0

// ============================================================================
// AUTOTYPER DETECTION - Keystroke timing analysis
// Purely additive: does not modify any existing trust score calculation.
// Called periodically from handleKeydown every 50 keystrokes.
// ============================================================================
function analyzeKeystrokeTiming() {
  const db = window.AUTOTYPER_DB
  const buf = db.ikiBuffer
  const flags = []
  let isRobotic = false
  let isSuspicious = false

  // Need minimum data to analyze
  if (buf.length < 30) {
    return { isRobotic: false, isSuspicious: false, cv: -1, mean: -1, stddev: -1, untrustedRatio: 0, flags: [], sampleSize: buf.length }
  }

  // --- Compute mean ---
  const sum = buf.reduce((a, b) => a + b, 0)
  const mean = sum / buf.length

  // --- Compute standard deviation ---
  const sqDiffs = buf.map(v => (v - mean) ** 2)
  const variance = sqDiffs.reduce((a, b) => a + b, 0) / buf.length
  const stddev = Math.sqrt(variance)

  // --- Coefficient of variation ---
  const cv = mean > 0 ? stddev / mean : 0

  // --- Untrusted event ratio ---
  const untrustedRatio = db.totalEventCount > 0 ? db.untrustedEventCount / db.totalEventCount : 0

  // --- Deletion ratio (from existing TIMELINE_DB) ---
  const additions = window.TIMELINE_DB?.additions || 0
  const deletions = window.TIMELINE_DB?.deletions || 0
  const deletionRatio = additions > 0 ? deletions / additions : -1
  const zeroDeletions = additions > 200 && deletions === 0

  // =====================================================================
  // SIGNAL 1: Synthetic/untrusted input (JS-dispatched events)
  // =====================================================================
  if (untrustedRatio > 0.1 && db.totalEventCount >= 20) {
    flags.push('synthetic_input_detected')
    isRobotic = true
  }

  // =====================================================================
  // SIGNAL 2: Uniform timing (CV too low = robotic)
  // Human CV is typically 0.3-0.7. Autotypers are < 0.15.
  // =====================================================================
  if (buf.length >= 50 && cv < 0.15) {
    flags.push('robotic_timing_detected')
    isRobotic = true
  }

  // =====================================================================
  // SIGNAL 3: Missing extremes (no fast or slow keystrokes)
  // Real humans always have some very fast pairs (< 30ms, e.g. "th")
  // and some slow pairs (> 400ms, thinking or awkward reaches).
  // An autotyper configured with e.g. 40-120ms range will have neither.
  // =====================================================================
  if (buf.length >= 100) {
    const hasFast = buf.some(v => v < 30)
    const hasSlow = buf.some(v => v > 400)
    if (!hasFast && !hasSlow) {
      flags.push('missing_timing_extremes')
      isSuspicious = true
    }
  }

  // =====================================================================
  // SIGNAL 4: Zero deletions as amplifier
  // Not a standalone flag, but if combined with another signal, escalate
  // =====================================================================
  if (zeroDeletions && isSuspicious) {
    flags.push('zero_corrections')
    isRobotic = true // upgrade from suspicious to robotic
  }
  if (zeroDeletions && !isSuspicious && !isRobotic && buf.length >= 100) {
    // Standalone zero-deletions is just a note, not a flag
    flags.push('no_corrections_noted')
  }

  return {
    isRobotic,
    isSuspicious,
    cv: Math.round(cv * 1000) / 1000,
    mean: Math.round(mean),
    stddev: Math.round(stddev),
    untrustedRatio: Math.round(untrustedRatio * 1000) / 1000,
    deletionRatio: deletionRatio >= 0 ? Math.round(deletionRatio * 1000) / 1000 : -1,
    sampleSize: buf.length,
    totalEvents: db.totalEventCount,
    flags
  }
}

function handleKeydown(e) {
  if (!e.target.closest('.ProseMirror')) return
  
  const now = Date.now()
  if (isPasting || (now - lastPasteTime) < 1000) return
  
  if (e.key.length === 1 && !e.ctrlKey && !e.metaKey && !e.altKey) {
    // --- Autotyper detection (additive - does not modify existing logic) ---
    window.AUTOTYPER_DB.totalEventCount++
    if (!e.isTrusted) window.AUTOTYPER_DB.untrustedEventCount++
    if (window.AUTOTYPER_DB.lastKeystrokeTime > 0) {
      const iki = now - window.AUTOTYPER_DB.lastKeystrokeTime
      if (iki < 5000) { // ignore thinking pauses > 5s
        if (window.AUTOTYPER_DB.ikiBuffer.length >= window.AUTOTYPER_DB.maxBufferSize) {
          window.AUTOTYPER_DB.ikiBuffer.shift()
        }
        window.AUTOTYPER_DB.ikiBuffer.push(iki)
      }
    }
    window.AUTOTYPER_DB.lastKeystrokeTime = now
    if (window.AUTOTYPER_DB.totalEventCount % 50 === 0) {
      window.AUTOTYPER_DB.analysisResult = analyzeKeystrokeTiming()
    }
    // --- End autotyper detection ---

    window.TYPED_DB.allTypedChars += e.key
    window.TYPED_DB.totalTypedCount++
    
    // Update fingerprints every 30 chars
    if (window.TYPED_DB.totalTypedCount % 30 === 0) {
      window.TYPED_DB.fingerprints = generateWordFingerprints(window.TYPED_DB.allTypedChars)
    }
    
    // Timeline
    const pause = now - window.TIMELINE_DB.lastKeystroke
    if (pause > 3000 || !window.TIMELINE_DB.currentTypingStart) {
      if (window.TIMELINE_DB.currentTypingText.length > 0) {
        const duration = window.TIMELINE_DB.lastKeystroke - window.TIMELINE_DB.currentTypingStart
        const wpm = duration > 0 ? (window.TIMELINE_DB.currentTypingText.length / 5) / (duration / 60000) : 0
        window.TIMELINE_DB.segments.push({
          text: window.TIMELINE_DB.currentTypingText,
          timestamp: window.TIMELINE_DB.currentTypingStart,
          duration, wpm: Math.round(wpm), type: 'typed'
        })
      }
      window.TIMELINE_DB.currentTypingStart = now
      window.TIMELINE_DB.currentTypingText = e.key
      } else {
      window.TIMELINE_DB.currentTypingText += e.key
    }
    window.TIMELINE_DB.lastKeystroke = now
    window.TIMELINE_DB.additions++
  } else if (e.key === 'Enter') {
    window.TYPED_DB.allTypedChars += '\n'
    window.TYPED_DB.totalTypedCount++
    window.TIMELINE_DB.currentTypingText += '\n'
    window.TIMELINE_DB.additions++
  } else if (e.key === 'Backspace' || e.key === 'Delete') {
    window.TIMELINE_DB.deletions++
  }
  _updateChecksum()
}

function handlePaste(e) {
  if (!e.target.closest('.ProseMirror')) return
  
  const pastedText = e.clipboardData?.getData('text/plain') || ''
  if (!pastedText) return
  
  isPasting = true
  lastPasteTime = Date.now()
  
  console.log('📋 PASTE:', pastedText.length, 'chars')
  
  const isInternal = checkIfInternal(pastedText)
  
  // Capture editor text BEFORE TipTap processes the paste
  const textBefore = editor?.value?.getText() || ''

  if (isInternal) {
    window.INTERNAL_DB.pastes.push({
      id: 'int_' + Date.now(),
      text: pastedText,
      timestamp: Date.now(),
      length: pastedText.length
    })
    window.INTERNAL_DB.totalChars += pastedText.length
    console.log('✅ INTERNAL (own content)')
  } else {
    const pasteId = 'ext_' + Date.now()
    const fingerprints = generateWordFingerprints(pastedText)
    window.EXTERNAL_DB.pastes.push({
      id: pasteId,
      text: pastedText,
      timestamp: Date.now(),
      length: pastedText.length,
      fingerprints: fingerprints
    })
    window.EXTERNAL_DB.totalPastedChars += pastedText.length
    console.log('❌ EXTERNAL stored:', fingerprints.words.size, 'words,', fingerprints.bigrams.size, 'bigrams,', fingerprints.trigrams.size, 'trigrams')

    // After TipTap renders the paste, check if the editor text differs from
    // the clipboard text (e.g., ChatGPT copy button sends HTML that TipTap
    // renders differently — strips list numbering, markdown formatting, etc.)
    setTimeout(() => {
      try {
        const textAfter = editor?.value?.getText() || ''
        const growth = textAfter.length - textBefore.length
        if (growth > 10) {
          const clipNorm = pastedText.toLowerCase().replace(/\s+/g, ' ').trim()
          const afterNorm = textAfter.toLowerCase().replace(/\s+/g, ' ').trim()
          // If clipboard text can't be found in the editor, TipTap modified it
          if (!afterNorm.includes(clipNorm)) {
            // Extract the rendered version by finding where before/after diverge
            let diffStart = 0
            const minLen = Math.min(textBefore.length, textAfter.length)
            while (diffStart < minLen && textBefore[diffStart] === textAfter[diffStart]) {
              diffStart++
            }
            const renderedText = textAfter.substring(diffStart, diffStart + growth).trim()
            if (renderedText.length > 10 && renderedText !== pastedText) {
              window.EXTERNAL_DB.pastes.push({
                id: pasteId + '_rendered',
                text: renderedText,
                timestamp: Date.now(),
                length: renderedText.length,
                fingerprints: generateWordFingerprints(renderedText)
              })
              console.log('📋 Also stored editor-rendered version:', renderedText.length, 'chars')
            }
          }
        }
      } catch (err) { /* ignore render capture errors */ }
    }, 300)
  }

  // Timeline
  if (window.TIMELINE_DB.currentTypingText.length > 0) {
    const duration = Date.now() - window.TIMELINE_DB.currentTypingStart
    const wpm = duration > 0 ? (window.TIMELINE_DB.currentTypingText.length / 5) / (duration / 60000) : 0
    window.TIMELINE_DB.segments.push({
      text: window.TIMELINE_DB.currentTypingText,
      timestamp: window.TIMELINE_DB.currentTypingStart,
      duration, wpm: Math.round(wpm), type: 'typed'
    })
    window.TIMELINE_DB.currentTypingText = ''
  }
  window.TIMELINE_DB.segments.push({
    text: pastedText, timestamp: Date.now(), duration: 0, wpm: 9999,
    type: isInternal ? 'internal_paste' : 'external_paste'
  })

  setTimeout(() => { isPasting = false }, 500)
  _updateChecksum()
}

function checkIfInternal(pastedText) {
  // Only trust the copy buffer — it tracks what was copied from within this editor
  // and whether the source content was itself external.
  for (const copy of window.INTERNAL_DB.copyBuffer) {
    if (copy.text === pastedText) return !copy.isExternal
  }
  // Do NOT fall back to allTypedChars.includes() — that enables laundering:
  // attacker retypes external content, then pastes it, and it would be marked internal.
  // Do NOT use fuzzy fingerprint matching — same laundering risk.
  return false
}

function handleCopy(e) {
  if (!e.target.closest('.ProseMirror')) return
  const copiedText = window.getSelection()?.toString() || ''
  if (!copiedText) return
  
  const isExternal = checkIfExternalContent(copiedText)
  window.INTERNAL_DB.copyBuffer.unshift({ text: copiedText, timestamp: Date.now(), isExternal })
  if (window.INTERNAL_DB.copyBuffer.length > 10) window.INTERNAL_DB.copyBuffer.pop()
}

function handleCut(e) { handleCopy(e) }

function checkIfExternalContent(text) {
  for (const paste of window.EXTERNAL_DB.pastes) {
    if (paste.text.includes(text) || text.includes(paste.text)) return true
  }
  return false
}

// ============================================================================
// ANALYZE - Accurate calculation for mixed content
// ============================================================================
async function analyzeIntegrityNow() {
  console.log('🔍 ANALYZING INTEGRITY v3')
  
  if (!editor?.value) {
    console.error('❌ Editor not ready - editor.value is', editor?.value)
    alert('Editor not ready!')
    return
  }
  
  let currentText = ''
  try {
    currentText = editor.value.getText() || ''
  } catch (getTextError) {
    console.error('❌ editor.getText() failed:', getTextError)
    // Fallback: try to get text from the ProseMirror DOM
    try {
      const proseMirror = document.querySelector('.ProseMirror')
      currentText = proseMirror?.innerText || proseMirror?.textContent || ''
      console.log('✅ Fallback: got text from DOM, length:', currentText.length)
    } catch (domError) {
      console.error('❌ DOM fallback also failed:', domError)
      window._lastIntegrityError = { phase: 'getText', error: getTextError.message, domError: domError.message }
      return
    }
  }
  const docLength = currentText.length
  
  if (docLength === 0) {
    updateStore(100, 1, 0, [])
    return { trustScore: 100 }
  }
  
  console.log('📊 Document:', docLength, 'chars')
  console.log('📊 Typed total:', window.TYPED_DB.totalTypedCount, 'chars')
  console.log('📊 External pastes:', window.EXTERNAL_DB.pastes.length)

  // =========================================================================
  // STEP 1: Detect external content in the document
  // Uses a position map to track exactly which characters are external.
  // Finds ALL occurrences (handles repeated pastes) and prevents double-counting.
  // =========================================================================
  const externalPastesFound = []
  // Strip LLM formatting (numbered lists, markdown bold, bullets, headers)
  // so clipboard text matches what TipTap actually renders in the editor.
  const stripFormatting = (t) => t
    .toLowerCase()
    .replace(/^\s*\d+\.\s+/gm, '')       // "1. item" → "item"
    .replace(/^\s*[-*•]\s+/gm, '')        // "- item" / "* item" → "item"
    .replace(/\*{1,3}([^*]+)\*{1,3}/g, '$1') // **bold** / *italic* → text
    .replace(/^#{1,6}\s+/gm, '')          // "## Header" → "Header"
    .replace(/\s+/g, ' ')
    .trim()
  const docNorm = stripFormatting(currentText)
  // Position map: 1 = external, 0 = not. Prevents double-counting overlapping pastes.
  const externalMap = new Uint8Array(docNorm.length)

  // De-duplicate identical paste texts (process once, but find ALL occurrences)
  const processedPasteTexts = new Set()

  for (const paste of window.EXTERNAL_DB.pastes) {
    const pasteNorm = stripFormatting(paste.text)
    if (pasteNorm.length < 10) continue
    if (processedPasteTexts.has(pasteNorm)) continue
    processedPasteTexts.add(pasteNorm)

    let pasteNewChars = 0

    // --- Method A: Find ALL exact occurrences of paste text in doc ---
    let searchPos = 0
    let found = false
    while ((searchPos = docNorm.indexOf(pasteNorm, searchPos)) !== -1) {
      found = true
      for (let j = searchPos; j < searchPos + pasteNorm.length && j < docNorm.length; j++) {
        if (!externalMap[j]) { externalMap[j] = 1; pasteNewChars++ }
      }
      searchPos += pasteNorm.length
    }

    // Check if entire doc is a subset of the paste
    if (!found && docNorm.length > 0 && pasteNorm.includes(docNorm)) {
      found = true
      for (let j = 0; j < docNorm.length; j++) {
        if (!externalMap[j]) { externalMap[j] = 1; pasteNewChars++ }
      }
    }

    // --- Method B: Chunk-level matching (fallback for partially modified pastes) ---
    if (!found) {
      const CHUNK_SIZE = 30
      for (let i = 0; i <= pasteNorm.length - CHUNK_SIZE; i += CHUNK_SIZE) {
        const chunk = pasteNorm.substring(i, i + CHUNK_SIZE)
        let chunkPos = 0
        while ((chunkPos = docNorm.indexOf(chunk, chunkPos)) !== -1) {
          for (let j = chunkPos; j < chunkPos + CHUNK_SIZE && j < docNorm.length; j++) {
            if (!externalMap[j]) { externalMap[j] = 1; pasteNewChars++ }
          }
          chunkPos += CHUNK_SIZE
        }
      }
    }

    if (pasteNewChars > 0) {
      externalPastesFound.push({
        id: paste.id, text: paste.text, preview: paste.text.substring(0, 50),
        matchPercent: Math.min(100, Math.round((pasteNewChars / pasteNorm.length) * 100)),
        charsEstimate: pasteNewChars
      })
      console.log(`   ❌ External [${paste.id}]: ${pasteNewChars} chars marked external`)
    } else {
      console.log(`   ✅ External [${paste.id}]: no match`)
    }
  }

  // =========================================================================
  // STEP 1.5: Method C - Retyped content detection (bigram-guarded matching)
  // Catches content pasted externally then retyped with minor edits/typos.
  // Uses BOTH individual word matching AND consecutive word pair (bigram)
  // matching to prevent false positives from common vocabulary overlap.
  // Sliding 10-word window: >=7 words AND >=3 bigrams must match a paste.
  // =========================================================================
  let retypedCharsCount = 0
  if (window.EXTERNAL_DB.pastes.length > 0) {
    // Build word list from normalized doc with character positions
    const wordListC = []
    const wordRe = /\S+/g
    let wm
    while ((wm = wordRe.exec(docNorm)) !== null) {
      if (wm[0].length >= 3) {
        wordListC.push({ word: wm[0], start: wm.index, end: wm.index + wm[0].length })
      }
    }

    const W_SIZE = 10
    const W_WORD_THRESHOLD = 7   // at least 7 of 10 individual words must match
    const W_BIGRAM_THRESHOLD = 3 // at least 3 of 9 consecutive word pairs must match

    for (const paste of window.EXTERNAL_DB.pastes) {
      const pcNorm = stripFormatting(paste.text)
      if (pcNorm.length < 30) continue
      const pcWordArr = pcNorm.split(/\s+/).filter(w => w.length >= 3)
      if (pcWordArr.length < 5) continue

      // Build word set AND bigram set from paste
      const pcWords = new Set(pcWordArr)
      const pcBigrams = new Set()
      for (let i = 0; i < pcWordArr.length - 1; i++) {
        pcBigrams.add(pcWordArr[i] + ' ' + pcWordArr[i + 1])
      }

      for (let wi = 0; wi <= wordListC.length - W_SIZE; wi++) {
        const win = wordListC.slice(wi, wi + W_SIZE)
        const wStart = win[0].start
        const wEnd = win[W_SIZE - 1].end

        // Skip windows already mostly marked as external
        let extCnt = 0
        for (let j = wStart; j < wEnd; j++) {
          if (externalMap[j]) extCnt++
        }
        if (extCnt / (wEnd - wStart) > 0.7) continue

        // Count individual word matches
        let wordMatchCnt = 0
        for (const { word } of win) {
          if (pcWords.has(word)) wordMatchCnt++
        }

        // Count bigram matches (consecutive word pairs preserve sequence)
        let bigramMatchCnt = 0
        for (let i = 0; i < win.length - 1; i++) {
          if (pcBigrams.has(win[i].word + ' ' + win[i + 1].word)) bigramMatchCnt++
        }

        // Require BOTH word overlap AND sequence preservation
        // This prevents false positives from common English vocabulary
        if (wordMatchCnt >= W_WORD_THRESHOLD && bigramMatchCnt >= W_BIGRAM_THRESHOLD) {
          for (let j = wStart; j < wEnd; j++) {
            if (!externalMap[j]) { externalMap[j] = 1; retypedCharsCount++ }
          }
        }
      }
    }

    if (retypedCharsCount > 0) {
      console.log(`   🔄 RETYPED CONTENT: ${retypedCharsCount} chars detected via bigram-guarded matching`)
    }
  }

  // Count total external chars from position map, scale to original doc length
  let externalInNorm = 0
  for (let i = 0; i < externalMap.length; i++) {
    if (externalMap[i]) externalInNorm++
  }
  let externalCharsInDoc = docNorm.length > 0
    ? Math.min(Math.round(docLength * (externalInNorm / docNorm.length)), docLength)
    : 0

  // =========================================================================
  // STEP 2: Calculate trust score
  // Trust = (doc - external) / doc. Typed is derived, not estimated.
  // No overlap resolution needed — eliminates the whack-a-mole bug chain.
  // =========================================================================
  const genuineTyped = Math.max(0, docLength - externalCharsInDoc)
  const adjustedTyped = genuineTyped
  const adjustedExternal = externalCharsInDoc
  const retypedChars = retypedCharsCount

  let trustScore = 0
  let typedRatio = 0
  let externalRatio = 0

  if (docLength > 0) {
    typedRatio = genuineTyped / docLength
    externalRatio = externalCharsInDoc / docLength
    trustScore = Math.round((genuineTyped / docLength) * 100)
  }

  trustScore = Math.max(0, Math.min(100, trustScore))
  
  console.log('═══════════════════════════════════════════════════════════')
  console.log('📊 ANALYSIS RESULTS:')
  console.log('   Document length:', docLength)
  console.log('   Typed chars in doc:', adjustedTyped, `(${Math.round(typedRatio * 100)}%)`)
  console.log('   External chars in doc:', adjustedExternal, `(${Math.round(externalRatio * 100)}%)`)
  console.log('   ')
  console.log('   🎯 TRUST SCORE:', trustScore + '%')
  console.log('═══════════════════════════════════════════════════════════')
  
  // Save timeline segment
  if (window.TIMELINE_DB.currentTypingText.length > 0) {
    const duration = Date.now() - window.TIMELINE_DB.currentTypingStart
    const wpm = duration > 0 ? (window.TIMELINE_DB.currentTypingText.length / 5) / (duration / 60000) : 0
    window.TIMELINE_DB.segments.push({
      text: window.TIMELINE_DB.currentTypingText,
      timestamp: window.TIMELINE_DB.currentTypingStart,
      duration, wpm: Math.round(wpm), type: 'typed'
    })
    window.TIMELINE_DB.currentTypingText = ''
    window.TIMELINE_DB.currentTypingStart = null
  }
  
  // Backend - fire and forget (don't let backend failures block score display)
  if (integrity.value?.sessionId) {
    axios.post(`${INTEGRITY_API}/api/integrity/analyze`, {
      session_id: integrity.value.sessionId,
      doc_id: integrity.value?.docId,
      current_text: currentText,
      paste_database: window.EXTERNAL_DB.pastes.map(p => p.text),
      analysis: {
        trust_score: trustScore,
        doc_length: docLength,
        typed_in_doc: adjustedTyped,
        external_in_doc: adjustedExternal,
        retyped_external_chars: retypedChars
      }
    }, { timeout: 10000 }).catch(() => { /* Backend unavailable */ })
  }
  
  try {
    updateStore(trustScore, typedRatio, externalRatio, externalPastesFound, retypedChars)
    console.log('✅ updateStore completed successfully, lastAnalyzed:', integrity.value?.lastAnalyzed)
  } catch (storeError) {
    console.error('❌ updateStore FAILED:', storeError)
    window._lastIntegrityError = { phase: 'updateStore', error: storeError.message, stack: storeError.stack }
    // Emergency fallback: set scores directly
    try {
      integrity.value = {
        ...integrity.value,
        scores: { trust: trustScore, composition: trustScore },
        lastAnalyzed: Date.now(),
        flags: []
      }
      console.log('✅ Emergency fallback applied, trust:', trustScore)
    } catch (e2) {
      console.error('❌ Emergency fallback also failed:', e2)
    }
  }
  
  window._lastAnalysisResult = { trustScore, typedRatio, externalRatio, timestamp: Date.now() }
  return { trustScore, typedRatio, externalRatio, externalPastesFound }
}

function updateStore(trustScore, typedRatio, externalRatio, externalPastesFound, retypedChars = 0) {
  // --- Build flags array ---
  const flags = externalRatio > 0.5 ? ['high_external_paste'] : []
  if (retypedChars > 0) flags.push('retyped_external_detected')

  // --- Autotyper detection penalty (additive layer) ---
  let autotyperResult = { isRobotic: false, isSuspicious: false, cv: -1, mean: -1, stddev: -1, untrustedRatio: 0, flags: [], sampleSize: 0 }
  try {
    autotyperResult = analyzeKeystrokeTiming()
    window.AUTOTYPER_DB.analysisResult = autotyperResult
  } catch (e) {
    console.warn('⚠️ analyzeKeystrokeTiming failed, using defaults:', e)
  }

  if (autotyperResult.sampleSize >= 30) {
    // Synthetic input (JS-dispatched events) = trust goes to 0
    if (autotyperResult.flags.includes('synthetic_input_detected')) {
      trustScore = 0
      flags.push('synthetic_input_detected')
    }
    // Robotic timing pattern = hard cap at 15%
    if (autotyperResult.flags.includes('robotic_timing_detected') || 
        (autotyperResult.isRobotic && !autotyperResult.flags.includes('synthetic_input_detected'))) {
      trustScore = Math.min(trustScore, 15)
      if (!flags.includes('robotic_typing_detected')) flags.push('robotic_typing_detected')
    }
    // Suspicious pattern (missing extremes) = halve the score
    if (autotyperResult.isSuspicious && !autotyperResult.isRobotic) {
      trustScore = Math.round(trustScore * 0.5)
      flags.push('suspicious_typing_pattern')
    }
    // Zero corrections amplifier flag (informational)
    if (autotyperResult.flags.includes('zero_corrections')) {
      flags.push('zero_corrections')
    }
  }

  // Loophole #1: Check tamper detection
  if (_tamperDetected) {
    flags.push('integrity_tamper_detected')
    trustScore = Math.min(trustScore, 10)
  }

  // Clamp trust score
  trustScore = Math.max(0, Math.min(100, trustScore))

  integrity.value = {
    ...integrity.value,
    scores: { 
      trust: trustScore, 
      composition: trustScore, 
      authenticity: trustScore,
      // Store typed/external ratios in scores too for print.vue compatibility
      typed: typedRatio,
      external: externalRatio,
      P_proc: typedRatio  // Process/typing ratio for display
    },
    mix: { typed: typedRatio, internal: 0, external: externalRatio },
    sessionMix: { typed: typedRatio, internal: 0, external: externalRatio },
    flags: flags,
    lastAnalyzed: Date.now(),
    externalPastesFound: externalPastesFound,
    retypedExternalDetected: retypedChars > 0 ? externalPastesFound : [],
    retypedExternalChars: retypedChars,
    autotyperAnalysis: autotyperResult,
    analysis: {
      typedTotal: window.TYPED_DB.totalTypedCount,
      externalTotal: window.EXTERNAL_DB.totalPastedChars,
      externalPastesCount: externalPastesFound.length,
      retypedChars: retypedChars
    }
  }
}

// Legacy compatibility (guarded — these get frozen with configurable:false,
// so on remount the assignment would crash; the first-mount objects use
// getters that delegate to the real globals, so they remain correct.)
if (!window.INTEGRITY_DATABASE) {
  window.INTEGRITY_DATABASE = {
    get externalPastes() { return window.EXTERNAL_DB?.pastes || [] },
    get totalExternalPastedChars() { return window.EXTERNAL_DB?.totalPastedChars || 0 },
    get totalTypedChars() { return window.TYPED_DB?.totalTypedCount || 0 },
    get allKeystrokes() { return window.TYPED_DB?.allTypedChars || '' }
  }
}

if (!window.INTEGRITY_TIMELINE) {
  window.INTEGRITY_TIMELINE = {
    get segments() { return window.TIMELINE_DB?.segments || [] },
    get deletions() { return window.TIMELINE_DB?.deletions || 0 },
    get additions() { return window.TIMELINE_DB?.additions || 0 },
    get typingPauses() { return [] },
    get burstLengths() { return [] },
    get autotyperAnalysis() { return window.AUTOTYPER_DB?.analysisResult || null }
  }
}

// Freeze legacy compat objects too
for (const name of ['INTEGRITY_DATABASE', 'INTEGRITY_TIMELINE']) {
  try {
    Object.defineProperty(window, name, { value: window[name], writable: false, configurable: false })
  } catch (e) { /* already frozen */ }
}
</script>
