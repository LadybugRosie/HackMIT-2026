/**
 * ProvenanceTracker - Segment-level provenance tracking for document integrity
 * 
 * Tracks the origin of every character in the document:
 * - SELF_TYPED: User typed this content
 * - SELF_PASTE: User pasted their own previously typed content
 * - EXTERNAL_PASTE: User pasted content from external source
 * - DERIVED_FROM_EXTERNAL: User retyped content that matches previously pasted external content
 * - UNKNOWN: Origin cannot be determined
 */

export const SEGMENT_ORIGIN = {
  SELF_TYPED: 'SELF_TYPED',
  SELF_PASTE: 'SELF_PASTE', 
  EXTERNAL_PASTE: 'EXTERNAL_PASTE',
  DERIVED_FROM_EXTERNAL: 'DERIVED_FROM_EXTERNAL',
  UNKNOWN: 'UNKNOWN'
}

/**
 * Generate n-gram fingerprints for text similarity matching
 */
function generateNGrams(text, n = 5) {
  const normalized = text.toLowerCase().replace(/[^a-z0-9\s]/g, '').replace(/\s+/g, ' ').trim()
  const ngrams = new Set()
  for (let i = 0; i <= normalized.length - n; i++) {
    ngrams.add(normalized.substring(i, i + n))
  }
  return ngrams
}

/**
 * Calculate Jaccard similarity between two sets of n-grams
 */
function jaccardSimilarity(set1, set2) {
  if (set1.size === 0 || set2.size === 0) return 0
  
  let intersection = 0
  for (const item of set1) {
    if (set2.has(item)) intersection++
  }
  
  const union = set1.size + set2.size - intersection
  return union > 0 ? intersection / union : 0
}

/**
 * Simple hash function for text
 */
function hashString(str) {
  let hash = 0
  for (let i = 0; i < str.length; i++) {
    const char = str.charCodeAt(i)
    hash = ((hash << 5) - hash) + char
    hash = hash & hash // Convert to 32bit integer
  }
  return hash.toString(16)
}

export class ProvenanceTracker {
  constructor() {
    // Document segments with provenance
    this.segments = []
    
    // Cache of external paste fingerprints (persists even after deletion)
    this.externalPasteCache = new Map() // hash -> { text, fingerprints, timestamp }
    
    // Cache of self-typed content fingerprints
    this.selfCorpusCache = new Map() // hash -> { text, fingerprints, timestamp }
    
    // Session metadata
    this.sessionStart = Date.now()
    this.lastInputTime = Date.now()
    
    // Composition tracking (for IME)
    this.compositionActive = false
    this.compositionText = ''
    
    // Input event tracking
    this.inputEventCounts = {
      insertText: 0,
      insertFromPaste: 0,
      insertFromDrop: 0,
      insertCompositionText: 0,
      deleteContentBackward: 0,
      deleteContentForward: 0,
      historyUndo: 0,
      historyRedo: 0,
      other: 0
    }
    
    console.log('✅ ProvenanceTracker initialized')
  }
  
  /**
   * Add a segment with provenance
   */
  addSegment(start, end, text, origin, inputType, sourceHash = null) {
    const segment = {
      start,
      end,
      text,
      origin,
      inputType,
      sourceHash,
      timestamp: Date.now(),
      fingerprints: text.length >= 20 ? generateNGrams(text) : null
    }
    
    // Insert in sorted order by start position
    let inserted = false
    for (let i = 0; i < this.segments.length; i++) {
      if (start < this.segments[i].start) {
        // Adjust positions of following segments
        for (let j = i; j < this.segments.length; j++) {
          this.segments[j].start += text.length
          this.segments[j].end += text.length
        }
        this.segments.splice(i, 0, segment)
        inserted = true
        break
      }
    }
    
    if (!inserted) {
      this.segments.push(segment)
    }
    
    this.lastInputTime = Date.now()
    
    console.log(`📝 Segment added: [${start}-${end}] ${origin} "${text.substring(0, 30)}..."`)
    
    return segment
  }
  
  /**
   * Remove a segment (or part of it) when text is deleted
   */
  removeSegment(start, end) {
    const deleteLength = end - start
    if (deleteLength <= 0) return
    
    const newSegments = []
    
    for (const seg of this.segments) {
      if (seg.end <= start) {
        // Segment is entirely before deletion - keep as is
        newSegments.push(seg)
      } else if (seg.start >= end) {
        // Segment is entirely after deletion - adjust position
        newSegments.push({
          ...seg,
          start: seg.start - deleteLength,
          end: seg.end - deleteLength
        })
      } else if (seg.start >= start && seg.end <= end) {
        // Segment is entirely within deletion - remove it
        // (don't add to newSegments)
      } else if (seg.start < start && seg.end > end) {
        // Deletion is entirely within segment - split it
        const before = {
          ...seg,
          end: start,
          text: seg.text.substring(0, start - seg.start)
        }
        const after = {
          ...seg,
          start: start,
          end: seg.end - deleteLength,
          text: seg.text.substring(end - seg.start)
        }
        if (before.text.length > 0) newSegments.push(before)
        if (after.text.length > 0) newSegments.push(after)
      } else if (seg.start < start && seg.end <= end) {
        // Deletion overlaps end of segment
        newSegments.push({
          ...seg,
          end: start,
          text: seg.text.substring(0, start - seg.start)
        })
      } else if (seg.start >= start && seg.end > end) {
        // Deletion overlaps start of segment
        newSegments.push({
          ...seg,
          start: start,
          end: seg.end - deleteLength,
          text: seg.text.substring(end - seg.start)
        })
      }
    }
    
    this.segments = newSegments.filter(s => s.text.length > 0)
    
    console.log(`🗑️ Deleted [${start}-${end}], ${this.segments.length} segments remaining`)
  }
  
  /**
   * Add text to external paste cache (for later laundering detection)
   */
  addToExternalCache(text, fingerprints, hash) {
    this.externalPasteCache.set(hash, {
      text,
      fingerprints,
      timestamp: Date.now()
    })
    console.log(`🔒 External paste cached: ${hash.substring(0, 8)}... (${text.length} chars)`)
  }
  
  /**
   * Add text to self corpus cache
   */
  addToSelfCorpus(text, fingerprints, hash) {
    this.selfCorpusCache.set(hash, {
      text,
      fingerprints,
      timestamp: Date.now()
    })
    console.log(`✅ Self corpus cached: ${hash.substring(0, 8)}... (${text.length} chars)`)
  }
  
  /**
   * Check if text matches external paste cache (laundering detection)
   * Returns { isLaundering: boolean, matchScore: number, matchedHash: string }
   */
  detectLaundering(text) {
    if (text.length < 20) return null // Too short to detect
    
    const fingerprints = generateNGrams(text)
    let bestMatch = { isLaundering: false, matchScore: 0, matchedHash: null }
    
    // Check against external paste cache
    for (const [hash, cached] of this.externalPasteCache) {
      if (!cached.fingerprints) continue
      
      const similarity = jaccardSimilarity(fingerprints, cached.fingerprints)
      
      if (similarity > bestMatch.matchScore) {
        bestMatch = {
          isLaundering: similarity > 0.35, // Threshold for laundering detection
          matchScore: similarity,
          matchedHash: hash,
          origin: SEGMENT_ORIGIN.DERIVED_FROM_EXTERNAL
        }
      }
    }
    
    // If matches external, also check if it matches self corpus (user's own work)
    if (bestMatch.isLaundering) {
      for (const [hash, cached] of this.selfCorpusCache) {
        if (!cached.fingerprints) continue
        
        const selfSimilarity = jaccardSimilarity(fingerprints, cached.fingerprints)
        
        if (selfSimilarity > bestMatch.matchScore) {
          // Matches self corpus more than external - not laundering
          return {
            isLaundering: false,
            matchScore: selfSimilarity,
            matchedHash: hash,
            origin: SEGMENT_ORIGIN.SELF_TYPED
          }
        }
      }
    }
    
    return bestMatch.isLaundering ? bestMatch : null
  }
  
  /**
   * Classify a paste event
   * Returns { origin: SEGMENT_ORIGIN, sourceHash: string }
   */
  classifyPaste(text, clipboardData = null) {
    const hash = hashString(text)
    const fingerprints = text.length >= 20 ? generateNGrams(text) : null
    
    // Check if matches self corpus first
    if (fingerprints) {
      for (const [selfHash, cached] of this.selfCorpusCache) {
        if (!cached.fingerprints) continue
        
        const similarity = jaccardSimilarity(fingerprints, cached.fingerprints)
        if (similarity > 0.7) {
          console.log(`✅ Paste matches self corpus (${Math.round(similarity * 100)}%)`)
          return { origin: SEGMENT_ORIGIN.SELF_PASTE, sourceHash: selfHash }
        }
      }
    }
    
    // Check if matches existing external cache
    if (fingerprints) {
      for (const [extHash, cached] of this.externalPasteCache) {
        if (!cached.fingerprints) continue
        
        const similarity = jaccardSimilarity(fingerprints, cached.fingerprints)
        if (similarity > 0.7) {
          console.log(`❌ Paste matches previous external paste (${Math.round(similarity * 100)}%)`)
          return { origin: SEGMENT_ORIGIN.EXTERNAL_PASTE, sourceHash: extHash }
        }
      }
    }
    
    // New external paste - add to cache
    this.addToExternalCache(text, fingerprints, hash)
    
    return { origin: SEGMENT_ORIGIN.EXTERNAL_PASTE, sourceHash: hash }
  }
  
  /**
   * Handle beforeinput event - primary source of input type detection
   */
  handleBeforeInput(event) {
    const inputType = event.inputType || 'unknown'
    
    // Track event counts
    if (this.inputEventCounts[inputType] !== undefined) {
      this.inputEventCounts[inputType]++
    } else {
      this.inputEventCounts.other++
    }
    
    // Determine origin based on inputType
    let origin = SEGMENT_ORIGIN.UNKNOWN
    let needsClassification = false
    
    switch (inputType) {
      case 'insertText':
      case 'insertCompositionText':
        origin = SEGMENT_ORIGIN.SELF_TYPED
        break
        
      case 'insertFromPaste':
      case 'insertFromDrop':
      case 'insertFromYank':
        origin = SEGMENT_ORIGIN.EXTERNAL_PASTE // Will be classified
        needsClassification = true
        break
        
      case 'historyUndo':
      case 'historyRedo':
        // Undo/redo should preserve original provenance
        // We'll handle this by not creating new segments
        origin = null
        break
        
      case 'deleteContentBackward':
      case 'deleteContentForward':
      case 'deleteByCut':
      case 'deleteByDrag':
        origin = null // Deletion, not insertion
        break
        
      default:
        origin = SEGMENT_ORIGIN.UNKNOWN
    }
    
    return { origin, needsClassification, inputType }
  }
  
  /**
   * Get provenance summary for the current document
   * This is the source of truth for trust score calculation
   */
  getProvenanceSummary(currentDocText) {
    const docLength = currentDocText.length
    
    // Count characters by origin from segments that are still in the document
    const counts = {
      [SEGMENT_ORIGIN.SELF_TYPED]: 0,
      [SEGMENT_ORIGIN.SELF_PASTE]: 0,
      [SEGMENT_ORIGIN.EXTERNAL_PASTE]: 0,
      [SEGMENT_ORIGIN.DERIVED_FROM_EXTERNAL]: 0,
      [SEGMENT_ORIGIN.UNKNOWN]: 0
    }
    
    // Calculate based on current segments
    let totalChars = 0
    for (const seg of this.segments) {
      // Only count segments that are within document bounds
      if (seg.start >= 0 && seg.end <= docLength && seg.text) {
        const charCount = seg.text.length
        counts[seg.origin] = (counts[seg.origin] || 0) + charCount
        totalChars += charCount
      }
    }
    
    // ADDITIONAL CHECK: Verify external content actually exists in document
    // by checking against externalPasteCache
    let externalCharsActuallyPresent = 0
    if (this.externalPasteCache.size > 0) {
      const normalizedDoc = currentDocText.toLowerCase().replace(/\s+/g, ' ').trim()
      
      for (const [hash, cached] of this.externalPasteCache) {
        if (cached.text && cached.text.length > 10) {
          const normalizedPaste = cached.text.toLowerCase().replace(/\s+/g, ' ').trim()
          // Check for substantial overlap (at least 50% of paste text found)
          const words = normalizedPaste.split(/\s+/).filter(w => w.length > 3)
          let foundWords = 0
          for (const word of words) {
            if (normalizedDoc.includes(word)) foundWords++
          }
          const overlapRatio = words.length > 0 ? foundWords / words.length : 0
          
          if (overlapRatio > 0.5) {
            externalCharsActuallyPresent += cached.text.length
          }
        }
      }
    }
    
    // If segments show external but document check shows none, adjust
    if (counts[SEGMENT_ORIGIN.EXTERNAL_PASTE] > 0 && externalCharsActuallyPresent === 0 && this.externalPasteCache.size > 0) {
      console.log('🔄 External content was deleted from document')
      // Don't zero out - the segments might just be out of sync
    }
    
    // If we're missing characters (gaps in segment coverage), mark as unknown
    const missingChars = docLength - totalChars
    if (missingChars > 0) {
      counts[SEGMENT_ORIGIN.UNKNOWN] += missingChars
      totalChars = docLength
    }
    
    // Calculate ratios
    const denominator = Math.max(1, docLength)
    const selfChars = counts[SEGMENT_ORIGIN.SELF_TYPED] + counts[SEGMENT_ORIGIN.SELF_PASTE]
    const externalChars = counts[SEGMENT_ORIGIN.EXTERNAL_PASTE]
    const derivedChars = counts[SEGMENT_ORIGIN.DERIVED_FROM_EXTERNAL]
    const unknownChars = counts[SEGMENT_ORIGIN.UNKNOWN]
    
    const selfRatio = selfChars / denominator
    const externalRatio = externalChars / denominator
    const derivedRatio = derivedChars / denominator
    const unknownRatio = unknownChars / denominator
    
    // Trust = 100 * self / total
    let trustScore = Math.round(100 * selfRatio)
    
    // If document has content but no external found in document check, trust is high
    if (externalCharsActuallyPresent === 0 && this.externalPasteCache.size > 0 && docLength > 0) {
      // External was pasted then deleted - trust should recover
      trustScore = Math.max(trustScore, Math.round(100 * (1 - externalRatio)))
      console.log('✅ External content appears deleted - adjusting trust score:', trustScore)
    }
    
    // Ensure trust score is in valid range
    trustScore = Math.max(0, Math.min(100, trustScore))
    
    return {
      docLength,
      totalChars,
      counts,
      ratios: {
        self: selfRatio,
        external: externalRatio,
        derived: derivedRatio,
        unknown: unknownRatio
      },
      trustScore,
      segmentCount: this.segments.length,
      inputEventCounts: { ...this.inputEventCounts },
      externalCharsActuallyPresent
    }
  }
  
  /**
   * Generate fingerprints for external use
   */
  generateFingerprints(text) {
    return generateNGrams(text)
  }
  
  /**
   * Hash string for external use
   */
  hashString(text) {
    return hashString(text)
  }
  
  /**
   * Reset tracker for new session
   */
  reset() {
    this.segments = []
    this.externalPasteCache.clear()
    this.selfCorpusCache.clear()
    this.sessionStart = Date.now()
    this.lastInputTime = Date.now()
    this.compositionActive = false
    this.compositionText = ''
    this.inputEventCounts = {
      insertText: 0,
      insertFromPaste: 0,
      insertFromDrop: 0,
      insertCompositionText: 0,
      deleteContentBackward: 0,
      deleteContentForward: 0,
      historyUndo: 0,
      historyRedo: 0,
      other: 0
    }
    console.log('🔄 ProvenanceTracker reset')
  }
  
  /**
   * Debug: log current state
   */
  debugLog() {
    console.log('=== ProvenanceTracker State ===')
    console.log('Segments:', this.segments.length)
    console.log('External cache:', this.externalPasteCache.size)
    console.log('Self corpus:', this.selfCorpusCache.size)
    console.log('Input events:', this.inputEventCounts)
    
    if (this.segments.length > 0) {
      console.log('Segment breakdown:')
      const byOrigin = {}
      for (const seg of this.segments) {
        byOrigin[seg.origin] = (byOrigin[seg.origin] || 0) + seg.text.length
      }
      console.log(byOrigin)
    }
  }
}

export default ProvenanceTracker
