<template>
  <div class="plagiarism-viewer">
    <!-- ─── Overview Banner ─── -->
    <div class="pv-overview">
      <div class="pv-score-ring-wrap">
        <svg class="pv-ring" viewBox="0 0 120 120">
          <circle cx="60" cy="60" r="50" stroke="#e5e7eb" stroke-width="8" fill="none"/>
          <circle cx="60" cy="60" r="50" :stroke="ringColor" stroke-width="8" fill="none"
            stroke-linecap="round" :stroke-dasharray="314.16" :stroke-dashoffset="ringOffset"
            transform="rotate(-90 60 60)" style="transition:stroke-dashoffset .6s ease"/>
          <text x="60" y="54" text-anchor="middle" :fill="ringColor" class="ring-number">{{ overallScore }}%</text>
          <text x="60" y="70" text-anchor="middle" class="ring-label">similarity</text>
        </svg>
        <div class="pv-score-verdict" :style="{ color: ringColor }">{{ verdictText }}</div>
      </div>

      <div class="pv-overview-stats">
        <div class="pv-ostat" v-if="scholarlyMatches.length" @click="setFilter('scholarly')" :class="{ dim: activeFilter && activeFilter !== 'scholarly' }">
          <span class="pv-ostat-icon scholarly">
            <svg width="18" height="18" viewBox="0 0 24 24" fill="currentColor"><path d="M12 3L1 9l4 2.18v6L12 21l7-3.82v-6l2-1.09V17h2V9L12 3zm6.82 6L12 12.72 5.18 9 12 5.28 18.82 9zM17 15.99l-5 2.73-5-2.73v-3.72L12 15l5-2.73v3.72z"/></svg>
          </span>
          <span class="pv-ostat-num">{{ scholarlyMatches.length }}</span>
          <span class="pv-ostat-label">Scholarly</span>
        </div>
        <div class="pv-ostat" v-if="webMatches.length" @click="setFilter('web')" :class="{ dim: activeFilter && activeFilter !== 'web' }">
          <span class="pv-ostat-icon web">
            <svg width="18" height="18" viewBox="0 0 24 24" fill="currentColor"><path d="M11.99 2C6.47 2 2 6.48 2 12s4.47 10 9.99 10C17.52 22 22 17.52 22 12S17.52 2 11.99 2zm6.93 6h-2.95c-.32-1.25-.78-2.45-1.38-3.56 1.84.63 3.37 1.91 4.33 3.56zM12 4.04c.83 1.2 1.48 2.53 1.91 3.96h-3.82c.43-1.43 1.08-2.76 1.91-3.96zM4.26 14C4.1 13.36 4 12.69 4 12s.1-1.36.26-2h3.38c-.08.66-.14 1.32-.14 2 0 .68.06 1.34.14 2H4.26zm.82 2h2.95c.32 1.25.78 2.45 1.38 3.56-1.84-.63-3.37-1.9-4.33-3.56zm2.95-8H5.08c.96-1.66 2.49-2.93 4.33-3.56C8.81 5.55 8.35 6.75 8.03 8zM12 19.96c-.83-1.2-1.48-2.53-1.91-3.96h3.82c-.43 1.43-1.08 2.76-1.91 3.96zM14.34 14H9.66c-.09-.66-.16-1.32-.16-2 0-.68.07-1.35.16-2h4.68c.09.65.16 1.32.16 2 0 .68-.07 1.34-.16 2zm.25 5.56c.6-1.11 1.06-2.31 1.38-3.56h2.95c-.96 1.65-2.49 2.93-4.33 3.56zM16.36 14c.08-.66.14-1.32.14-2 0-.68-.06-1.34-.14-2h3.38c.16.64.26 1.31.26 2s-.1 1.36-.26 2h-3.38z"/></svg>
          </span>
          <span class="pv-ostat-num">{{ webMatches.length }}</span>
          <span class="pv-ostat-label">Internet</span>
        </div>
        <div class="pv-ostat" v-if="peerMatches.length" @click="setFilter('peer')" :class="{ dim: activeFilter && activeFilter !== 'peer' }">
          <span class="pv-ostat-icon peer">
            <svg width="18" height="18" viewBox="0 0 24 24" fill="currentColor"><path d="M16 11c1.66 0 2.99-1.34 2.99-3S17.66 5 16 5c-1.66 0-3 1.34-3 3s1.34 3 3 3zm-8 0c1.66 0 2.99-1.34 2.99-3S9.66 5 8 5C6.34 5 5 6.34 5 8s1.34 3 3 3zm0 2c-2.33 0-7 1.17-7 3.5V19h14v-2.5c0-2.33-4.67-3.5-7-3.5zm8 0c-.29 0-.62.02-.97.05 1.16.84 1.97 1.97 1.97 3.45V19h6v-2.5c0-2.33-4.67-3.5-7-3.5z"/></svg>
          </span>
          <span class="pv-ostat-num">{{ peerMatches.length }}</span>
          <span class="pv-ostat-label">Peer</span>
        </div>
      </div>

      <div class="pv-overview-right">
        <!-- Match type breakdown -->
        <div class="pv-match-breakdown" v-if="allSources.length">
          <div class="pv-mb-row">
            <span class="pv-mb-dot exact"></span>
            <span class="pv-mb-count">{{ matchTypeCounts.exact }}</span>
            <span class="pv-mb-label">Exact Copy</span>
          </div>
          <div class="pv-mb-row">
            <span class="pv-mb-dot minor"></span>
            <span class="pv-mb-count">{{ matchTypeCounts.minor }}</span>
            <span class="pv-mb-label">Minor Changes</span>
          </div>
          <div class="pv-mb-row">
            <span class="pv-mb-dot paraphrased"></span>
            <span class="pv-mb-count">{{ matchTypeCounts.paraphrased }}</span>
            <span class="pv-mb-label">Paraphrased</span>
          </div>
        </div>
        <button v-if="activeFilter" class="pv-clear-filter" @click="activeFilter = null">
          Clear Filter ✕
        </button>
      </div>
    </div>

    <!-- ─── Body: Text + Sources ─── -->
    <div class="pv-body">
      <!-- Left: Highlighted text -->
      <div class="pv-text-panel">
        <div class="pv-text-header">
          <h3>Submitted Text</h3>
          <span class="pv-text-hint" v-if="activeSource === null">Select a source to see matched passages</span>
          <button v-else class="pv-clear-btn" @click="activeSource = null">Show All ✕</button>
        </div>
        <div class="pv-text-content" v-html="highlightedContent"></div>
      </div>

      <!-- Right: Sources list -->
      <div class="pv-sources-panel">
        <div class="pv-sources-header">
          <h3>Sources ({{ filteredSources.length }})</h3>
          <select v-model="sortBy" class="pv-sort-select">
            <option value="score">Sort by Score</option>
            <option value="type">Sort by Type</option>
          </select>
        </div>

        <div class="pv-source-list">
          <div
            v-for="(source, idx) in filteredSources"
            :key="idx"
            :class="['pv-source-card', { active: activeSource === source._origIdx }]"
            @click="selectSource(source._origIdx)"
          >
            <!-- Source header bar -->
            <div class="pv-source-head">
              <div class="pv-source-num" :class="source._matchType">{{ idx + 1 }}</div>
              <span class="pv-source-badge" :class="source._sourceType">{{ sourceLabel(source) }}</span>
              <span class="pv-source-pct" :class="scoreClassFor(source.similarity_score)">{{ source.similarity_score }}%</span>
            </div>

            <!-- Score bar -->
            <div class="pv-score-bar">
              <div class="pv-score-bar-fill" :class="scoreClassFor(source.similarity_score)"
                :style="{ width: Math.min(100, source.similarity_score) + '%' }"></div>
            </div>

            <!-- Scholarly source -->
            <template v-if="source._sourceType === 'scholarly'">
              <div class="pv-source-title">{{ source.title }}</div>
              <div class="pv-source-meta" v-if="source.authors?.length">
                {{ source.authors.slice(0, 3).join(', ') }}
                <span v-if="source.year"> · {{ source.year }}</span>
              </div>
              <div class="pv-source-meta" v-if="source.journal">
                <em>{{ source.journal }}</em>
              </div>
              <div class="pv-source-meta small" v-if="source.doi">DOI: {{ source.doi }}</div>
              <a v-if="source.url" :href="source.url" target="_blank" rel="noopener" class="pv-source-link" @click.stop>
                View Source →
              </a>
              <div v-if="source.citation" class="pv-citation">{{ source.citation }}</div>
            </template>

            <!-- Web source -->
            <template v-else-if="source._sourceType === 'web'">
              <div class="pv-source-title">{{ source.title }}</div>
              <a v-if="source.url" :href="source.url" target="_blank" rel="noopener" class="pv-source-link" @click.stop>
                {{ truncateUrl(source.url) }} →
              </a>
            </template>

            <!-- Peer / Internal source -->
            <template v-else>
              <div class="pv-source-title">
                {{ source.source_type === 'self-plagiarism' ? 'Self-Plagiarism' : 'Peer Submission' }}
              </div>
              <div class="pv-source-meta">{{ source.matched_student_name || 'Another student' }}</div>
              <div class="pv-source-meta small">ID: {{ (source.matched_submission_id || '').substring(0, 8) }}…</div>
            </template>

            <!-- Passages preview (expanded) -->
            <div v-if="activeSource === source._origIdx && sourcePassages(source).length" class="pv-passages">
              <div class="pv-passages-title">
                <svg width="14" height="14" viewBox="0 0 24 24" fill="#6b7280"><path d="M3 18h18v-2H3v2zm0-5h18v-2H3v2zm0-7v2h18V6H3z"/></svg>
                Matching Passages ({{ sourcePassages(source).length }})
              </div>
              <div
                v-for="(passage, pidx) in sourcePassages(source).slice(0, 8)"
                :key="pidx"
                class="pv-passage"
              >
                <div class="pv-passage-text">"{{ truncate(passage.text || passage.source_sentence || '', 150) }}"</div>
                <div class="pv-passage-info" v-if="passage.similarity">
                  {{ Math.round((typeof passage.similarity === 'number' && passage.similarity <= 1 ? passage.similarity * 100 : passage.similarity)) }}% match
                  <span v-if="passage.length"> · {{ passage.length }} words</span>
                </div>
              </div>
            </div>
          </div>

          <!-- No sources state -->
          <div v-if="filteredSources.length === 0 && !activeFilter" class="pv-no-sources">
            <svg width="48" height="48" viewBox="0 0 24 24" fill="#16a34a">
              <path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm-2 15l-5-5 1.41-1.41L10 14.17l7.59-7.59L19 8l-9 9z"/>
            </svg>
            <p>No matching sources found</p>
            <span>Content appears to be original</span>
          </div>
          <div v-else-if="filteredSources.length === 0 && activeFilter" class="pv-no-sources">
            <p>No {{ activeFilter }} sources</p>
            <button class="pv-clear-filter" @click="activeFilter = null">Show all sources</button>
          </div>
        </div>
      </div>
    </div>

    <!-- ─── Footer: Databases searched ─── -->
    <div class="pv-footer">
      <span>Checked against:</span>
      <span class="pv-db-tag">OpenAlex 240M+</span>
      <span class="pv-db-tag">Crossref 150M+</span>
      <span class="pv-db-tag">Semantic Scholar 200M+</span>
      <span class="pv-db-tag">Web Search</span>
      <span class="pv-db-tag">Internal Corpus</span>
    </div>
  </div>
</template>

<script setup>
import { ref, computed } from 'vue'

const props = defineProps({
  content: { type: String, default: '' },
  plagiarismScore: { type: Number, default: 0 },
  plagiarismMatches: { type: Array, default: () => [] },
})

const activeSource = ref(null)
const activeFilter = ref(null)
const sortBy = ref('score')

const overallScore = computed(() => props.plagiarismScore || 0)

const ringColor = computed(() => {
  if (overallScore.value <= 15) return '#16a34a'
  if (overallScore.value <= 40) return '#d97706'
  return '#dc2626'
})

const ringOffset = computed(() => 314.16 * (1 - overallScore.value / 100))

const verdictText = computed(() => {
  if (overallScore.value <= 10) return 'Very Low Similarity'
  if (overallScore.value <= 20) return 'Low Similarity'
  if (overallScore.value <= 40) return 'Moderate Similarity'
  if (overallScore.value <= 60) return 'Significant Similarity'
  return 'High Similarity — Review Required'
})

function scoreClassFor(score) {
  if (score <= 15) return 'low'
  if (score <= 40) return 'medium'
  return 'high'
}

const scholarlyMatches = computed(() =>
  props.plagiarismMatches.filter(m => (m.source_type || m.type) === 'scholarly')
)
const webMatches = computed(() =>
  props.plagiarismMatches.filter(m => (m.source_type || m.type) === 'web')
)
const peerMatches = computed(() =>
  props.plagiarismMatches.filter(m => {
    const t = m.source_type || m.type || ''
    return t === 'internal' || t === 'peer' || t === 'intra-class' || t === 'self-plagiarism'
  })
)

const allSources = computed(() => {
  return props.plagiarismMatches
    .map((m, i) => {
      const st = m.source_type || m.type || 'peer'
      const mt = m.match_type || (m.similarity_score >= 60 ? 'exact' : m.similarity_score >= 30 ? 'minor' : 'paraphrased')
      return { ...m, _sourceType: st, _matchType: mt, _origIdx: i }
    })
    .sort((a, b) => (b.similarity_score || 0) - (a.similarity_score || 0))
})

const filteredSources = computed(() => {
  let sources = allSources.value
  if (activeFilter.value) {
    if (activeFilter.value === 'scholarly') sources = sources.filter(s => s._sourceType === 'scholarly')
    else if (activeFilter.value === 'web') sources = sources.filter(s => s._sourceType === 'web')
    else if (activeFilter.value === 'peer') sources = sources.filter(s => !['scholarly', 'web'].includes(s._sourceType))
  }
  if (sortBy.value === 'type') {
    const order = { scholarly: 0, web: 1 }
    sources = [...sources].sort((a, b) => (order[a._sourceType] ?? 2) - (order[b._sourceType] ?? 2))
  }
  return sources
})

const matchTypeCounts = computed(() => {
  const counts = { exact: 0, minor: 0, paraphrased: 0 }
  for (const s of allSources.value) {
    if (s._matchType === 'exact') counts.exact++
    else if (s._matchType === 'minor' || s._matchType === 'minor_changes') counts.minor++
    else counts.paraphrased++
  }
  return counts
})

function setFilter(type) {
  activeFilter.value = activeFilter.value === type ? null : type
  activeSource.value = null
}

function sourceLabel(source) {
  const t = source._sourceType
  if (t === 'scholarly') return 'Scholarly'
  if (t === 'web') return 'Internet'
  if (t === 'self-plagiarism') return 'Self-Plagiarism'
  return 'Peer'
}

function sourcePassages(source) {
  const segs = source.matching_segments || source.details?.matching_passages || []
  const sents = source.details?.sentence_matches || []
  const combined = [...segs]
  for (const s of sents) {
    const txt = s.source_sentence || s.text || ''
    if (txt && !combined.some(c => (c.text || '').includes(txt.slice(0, 20)))) {
      combined.push(s)
    }
  }
  return combined
}

function selectSource(idx) {
  activeSource.value = activeSource.value === idx ? null : idx
}

const plainText = computed(() => {
  if (!props.content) return ''
  let t = props.content
  t = t.replace(/<script[^>]*>[\s\S]*?<\/script>/gi, '')
  t = t.replace(/<style[^>]*>[\s\S]*?<\/style>/gi, '')
  for (const tag of ['</p>', '</div>', '</h1>', '</h2>', '</h3>', '</h4>', '<br>', '<br/>', '<br />']) {
    t = t.split(tag).join('\n')
  }
  t = t.replace(/<[^>]+>/g, '')
  t = t.replace(/&amp;/g, '&').replace(/&lt;/g, '<').replace(/&gt;/g, '>').replace(/&quot;/g, '"').replace(/&#x27;/g, "'")
  return t.trim()
})

function normalizeForMatch(t) {
  return t.toLowerCase().replace(/[^\w\s]/g, '').replace(/\s+/g, ' ').trim()
}

function findPassageInText(text, passageText) {
  if (!passageText || passageText.length < 8) return null

  const normPassage = normalizeForMatch(passageText)
  const normWords = normPassage.split(' ').filter(w => w.length > 0)
  if (normWords.length < 3) return null

  const textLower = text.toLowerCase()

  for (let grab = Math.min(5, normWords.length); grab >= 2; grab--) {
    const anchor = normWords.slice(0, grab)
    let searchPos = 0

    while (searchPos < textLower.length) {
      const anchorIdx = findWordsInText(textLower, anchor, searchPos)
      if (anchorIdx === -1) break

      let ti = anchorIdx
      let matched = 0
      let endPos = anchorIdx
      let piWord = 0
      let gapRun = 0

      while (piWord < normWords.length && ti < text.length) {
        while (ti < text.length && /[^\w]/.test(text[ti])) ti++
        const wordStart = ti
        while (ti < text.length && /[\w]/.test(text[ti])) ti++
        if (wordStart === ti) break
        const origWord = text.slice(wordStart, ti).toLowerCase()

        if (piWord < normWords.length && origWord === normWords[piWord]) {
          matched++
          endPos = ti
          piWord++
          gapRun = 0
        } else {
          gapRun++
          if (gapRun > 2 && matched > grab) break
          if (gapRun > 3) break
          piWord++
        }
      }

      const threshold = normWords.length <= 6 ? 0.7 : 0.5
      if (matched >= normWords.length * threshold && matched >= 3) {
        return { start: anchorIdx, end: endPos }
      }

      searchPos = anchorIdx + 1
    }
  }

  const normText = normalizeForMatch(text)
  if (normPassage.length > 15) {
    const subIdx = normText.indexOf(normPassage.slice(0, Math.min(60, normPassage.length)))
    if (subIdx !== -1) {
      const charRatio = text.length / (normText.length || 1)
      const approxStart = Math.max(0, Math.floor(subIdx * charRatio) - 5)
      const approxEnd = Math.min(text.length, Math.ceil((subIdx + normPassage.length) * charRatio) + 5)
      return { start: approxStart, end: approxEnd }
    }
  }

  return null
}

function findWordsInText(textLower, words, startFrom) {
  let pos = startFrom
  const first = words[0]

  while (pos < textLower.length) {
    const wordBoundary = textLower.indexOf(first, pos)
    if (wordBoundary === -1) return -1

    if (wordBoundary > 0 && /\w/.test(textLower[wordBoundary - 1])) {
      pos = wordBoundary + 1
      continue
    }

    let ti = wordBoundary
    let allFound = true
    for (const w of words) {
      while (ti < textLower.length && /[^\w]/.test(textLower[ti])) ti++
      const ws = ti
      while (ti < textLower.length && /[\w]/.test(textLower[ti])) ti++
      const origWord = textLower.slice(ws, ti)
      if (origWord !== w) { allFound = false; break }
    }

    if (allFound) return wordBoundary
    pos = wordBoundary + 1
  }
  return -1
}

function collectHighlightsForSource(text, source) {
  const passages = sourcePassages(source)
  const mt = source._matchType || 'paraphrased'
  const highlights = []

  for (const p of passages) {
    const pText = p.text || p.source_sentence || ''
    const found = findPassageInText(text, pText)
    if (found) {
      highlights.push({ ...found, type: mt })
    }
  }

  const coveredChars = highlights.reduce((s, h) => s + (h.end - h.start), 0)
  const simScore = source.similarity_score || 0
  const expectedCoverage = (simScore / 100) * text.length * 0.5

  if (coveredChars < expectedCoverage && simScore >= 20) {
    const sentences = splitIntoSentences(text)
    const sentMatches = source.details?.sentence_matches || []

    for (const sm of sentMatches) {
      const sentText = sm.source_sentence || sm.text || ''
      if (!sentText || sentText.length < 10) continue
      if ((sm.similarity || 0) < 0.5) continue
      const found = findPassageInText(text, sentText)
      if (found && !highlights.some(h => h.start <= found.start && h.end >= found.end)) {
        highlights.push({ ...found, type: mt })
      }
    }

    if (highlights.length < 2 && simScore >= 40) {
      for (const sent of sentences) {
        if (sent.text.length < 20) continue
        for (const p of passages) {
          const pText = p.text || p.source_sentence || ''
          if (!pText) continue
          const overlap = sentenceWordOverlap(sent.text, pText)
          if (overlap >= 0.5) {
            if (!highlights.some(h => h.start <= sent.start && h.end >= sent.end)) {
              highlights.push({ start: sent.start, end: sent.end, type: mt })
            }
            break
          }
        }
      }
    }
  }

  return highlights
}

function splitIntoSentences(text) {
  const result = []
  const regex = /[^.!?\n]+[.!?\n]*/g
  let m
  while ((m = regex.exec(text)) !== null) {
    result.push({ text: m[0].trim(), start: m.index, end: m.index + m[0].length })
  }
  return result
}

function sentenceWordOverlap(sentA, sentB) {
  const wordsA = new Set(normalizeForMatch(sentA).split(' ').filter(w => w.length > 2))
  const wordsB = new Set(normalizeForMatch(sentB).split(' ').filter(w => w.length > 2))
  if (wordsA.size === 0) return 0
  let overlap = 0
  for (const w of wordsA) {
    if (wordsB.has(w)) overlap++
  }
  return overlap / wordsA.size
}

const highlightedContent = computed(() => {
  const text = plainText.value
  if (!text) return '<p class="pv-empty">No content</p>'

  if (activeSource.value === null) {
    const allHighlights = []
    for (const source of allSources.value) {
      const hs = collectHighlightsForSource(text, source)
      allHighlights.push(...hs)
    }
    if (allHighlights.length === 0) return escapeAndFormat(text)

    allHighlights.sort((a, b) => a.start - b.start)
    const merged = mergeHighlights(allHighlights)
    return renderHighlights(text, merged)
  }

  const source = allSources.value.find(s => s._origIdx === activeSource.value)
  if (!source) return escapeAndFormat(text)

  const highlights = collectHighlightsForSource(text, source)
  if (!highlights.length) return escapeAndFormat(text)

  highlights.sort((a, b) => a.start - b.start)
  const merged = mergeHighlights(highlights)
  return renderHighlights(text, merged)
})

function mergeHighlights(highlights) {
  const merged = []
  for (const h of highlights) {
    if (merged.length && h.start <= merged[merged.length - 1].end + 5) {
      merged[merged.length - 1].end = Math.max(merged[merged.length - 1].end, h.end)
    } else {
      merged.push({ ...h })
    }
  }
  return merged
}

function renderHighlights(text, highlights) {
  let html = ''
  let pos = 0
  for (const h of highlights) {
    if (h.start > pos) html += escapeHtml(text.slice(pos, h.start))
    const cls = h.type === 'exact' ? 'hl-exact' : h.type === 'minor_changes' ? 'hl-minor' : 'hl-paraphrased'
    html += `<mark class="pv-highlight ${cls}">${escapeHtml(text.slice(h.start, h.end))}</mark>`
    pos = h.end
  }
  if (pos < text.length) html += escapeHtml(text.slice(pos))
  return html.replace(/\n/g, '<br/>')
}

function escapeHtml(t) {
  return t.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;')
}

function escapeAndFormat(t) {
  return escapeHtml(t).replace(/\n/g, '<br/>')
}

function truncate(t, len) {
  return t.length > len ? t.substring(0, len) + '...' : t
}

function truncateUrl(url) {
  try {
    const u = new URL(url)
    return u.hostname + (u.pathname.length > 30 ? u.pathname.substring(0, 30) + '...' : u.pathname)
  } catch {
    return url.substring(0, 50) + '...'
  }
}
</script>

<style scoped>
.plagiarism-viewer {
  display: flex;
  flex-direction: column;
  height: 100%;
  background: #fff;
  border-radius: 12px;
  border: 1px solid #e2e8f0;
  overflow: hidden;
}

/* ─── Overview Banner ─── */
.pv-overview {
  display: flex;
  align-items: center;
  gap: 28px;
  padding: 20px 24px;
  background: linear-gradient(135deg, #f8fafc 0%, #f1f5f9 100%);
  border-bottom: 1px solid #e2e8f0;
  flex-wrap: wrap;
}

.pv-score-ring-wrap {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 4px;
}
.pv-ring { width: 100px; height: 100px; }
.ring-number { font-size: 26px; font-weight: 800; }
.ring-label { font-size: 10px; fill: #6b7280; text-transform: uppercase; letter-spacing: 1px; }
.pv-score-verdict { font-size: 11px; font-weight: 600; text-align: center; max-width: 120px; line-height: 1.3; }

/* Stats */
.pv-overview-stats {
  display: flex;
  gap: 8px;
  flex: 1;
}
.pv-ostat {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 4px;
  padding: 12px 20px;
  background: #fff;
  border: 1px solid #e2e8f0;
  border-radius: 10px;
  cursor: pointer;
  transition: all .15s;
  min-width: 90px;
}
.pv-ostat:hover { border-color: #94a3b8; box-shadow: 0 2px 8px rgba(0,0,0,.06); }
.pv-ostat.dim { opacity: 0.4; }
.pv-ostat-icon {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 32px; height: 32px;
  border-radius: 8px;
}
.pv-ostat-icon.scholarly { background: #ede9fe; color: #7c3aed; }
.pv-ostat-icon.web { background: #dbeafe; color: #2563eb; }
.pv-ostat-icon.peer { background: #fce8e6; color: #dc2626; }
.pv-ostat-num { font-size: 22px; font-weight: 800; color: #1e293b; }
.pv-ostat-label { font-size: 11px; color: #64748b; font-weight: 500; text-transform: uppercase; letter-spacing: .5px; }

/* Overview right */
.pv-overview-right {
  display: flex;
  flex-direction: column;
  gap: 8px;
  margin-left: auto;
}
.pv-match-breakdown {
  display: flex;
  flex-direction: column;
  gap: 4px;
}
.pv-mb-row {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 12px;
}
.pv-mb-dot {
  width: 10px; height: 10px; border-radius: 2px;
}
.pv-mb-dot.exact { background: #fca5a5; }
.pv-mb-dot.minor { background: #fcd34d; }
.pv-mb-dot.paraphrased { background: #93c5fd; }
.pv-mb-count { font-weight: 700; color: #1e293b; min-width: 14px; }
.pv-mb-label { color: #64748b; }

.pv-clear-filter {
  padding: 4px 12px;
  border: 1px solid #d1d5db;
  background: #fff;
  border-radius: 6px;
  font-size: 11px;
  color: #6b7280;
  cursor: pointer;
}
.pv-clear-filter:hover { background: #f1f5f9; }

/* ─── Body ─── */
.pv-body {
  display: grid;
  grid-template-columns: 1fr 380px;
  flex: 1;
  overflow: hidden;
  min-height: 0;
}

/* Text Panel */
.pv-text-panel {
  display: flex;
  flex-direction: column;
  overflow: hidden;
  border-right: 1px solid #e2e8f0;
}
.pv-text-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 10px 20px;
  border-bottom: 1px solid #f1f5f9;
  background: #fafbfc;
}
.pv-text-header h3 { margin: 0; font-size: 13px; color: #374151; font-weight: 600; }
.pv-text-hint { font-size: 11px; color: #9ca3af; }
.pv-clear-btn {
  padding: 3px 10px;
  border: 1px solid #d1d5db;
  background: white;
  border-radius: 5px;
  font-size: 11px;
  color: #6b7280;
  cursor: pointer;
}
.pv-clear-btn:hover { background: #f1f5f9; }

.pv-text-content {
  flex: 1;
  padding: 20px;
  overflow-y: auto;
  font-size: 14px;
  line-height: 1.85;
  color: #1e293b;
}

.pv-highlight { padding: 1px 0; border-radius: 2px; cursor: pointer; transition: all .15s; }
.pv-highlight:hover { filter: brightness(0.92); }
.hl-exact { background: rgba(252,165,165,.5); border-bottom: 2px solid #dc2626; }
.hl-minor { background: rgba(252,211,77,.4); border-bottom: 2px solid #d97706; }
.hl-paraphrased { background: rgba(147,197,253,.4); border-bottom: 2px solid #3b82f6; }
.pv-empty { color: #9ca3af; font-style: italic; text-align: center; padding: 40px; }

/* ─── Sources Panel ─── */
.pv-sources-panel {
  display: flex;
  flex-direction: column;
  overflow: hidden;
  background: #f8f9fa;
}
.pv-sources-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 10px 16px;
  border-bottom: 1px solid #e2e8f0;
  background: #fff;
}
.pv-sources-header h3 { margin: 0; font-size: 13px; color: #374151; font-weight: 600; }
.pv-sort-select {
  padding: 3px 8px;
  border: 1px solid #d1d5db;
  border-radius: 5px;
  font-size: 11px;
  color: #6b7280;
  background: #fff;
}

.pv-source-list {
  flex: 1;
  overflow-y: auto;
  padding: 10px;
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.pv-source-card {
  background: #fff;
  border: 1px solid #e2e8f0;
  border-radius: 10px;
  padding: 12px 14px;
  cursor: pointer;
  transition: all .15s;
}
.pv-source-card:hover { border-color: #94a3b8; box-shadow: 0 2px 8px rgba(0,0,0,.05); }
.pv-source-card.active { border-color: #3b82f6; box-shadow: 0 0 0 2px rgba(59,130,246,.2); }

/* Source header */
.pv-source-head {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 8px;
}
.pv-source-num {
  width: 22px; height: 22px;
  border-radius: 6px;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 11px;
  font-weight: 800;
  color: #fff;
  flex-shrink: 0;
}
.pv-source-num.exact { background: #dc2626; }
.pv-source-num.minor, .pv-source-num.minor_changes { background: #d97706; }
.pv-source-num.paraphrased { background: #3b82f6; }
.pv-source-badge {
  padding: 2px 7px;
  border-radius: 4px;
  font-size: 9px;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: .5px;
}
.pv-source-badge.scholarly { background: #ede9fe; color: #7c3aed; }
.pv-source-badge.web { background: #dbeafe; color: #2563eb; }
.pv-source-badge.internal,
.pv-source-badge.peer,
.pv-source-badge.intra-class { background: #fce8e6; color: #dc2626; }
.pv-source-badge.self-plagiarism { background: #fef3c7; color: #d97706; }
.pv-source-pct {
  margin-left: auto;
  font-size: 16px;
  font-weight: 800;
}
.pv-source-pct.low { color: #16a34a; }
.pv-source-pct.medium { color: #d97706; }
.pv-source-pct.high { color: #dc2626; }

/* Score bar */
.pv-score-bar {
  height: 4px;
  background: #f1f5f9;
  border-radius: 4px;
  margin-bottom: 10px;
  overflow: hidden;
}
.pv-score-bar-fill {
  height: 100%;
  border-radius: 4px;
  transition: width .3s ease;
}
.pv-score-bar-fill.low { background: #16a34a; }
.pv-score-bar-fill.medium { background: #d97706; }
.pv-score-bar-fill.high { background: #dc2626; }

/* Source content */
.pv-source-title {
  font-size: 13px;
  font-weight: 600;
  color: #1e293b;
  margin-bottom: 3px;
  line-height: 1.3;
}
.pv-source-meta { font-size: 12px; color: #64748b; margin-bottom: 2px; }
.pv-source-meta.small { font-size: 11px; color: #94a3b8; }
.pv-source-link {
  display: inline-block;
  font-size: 12px;
  color: #2563eb;
  text-decoration: none;
  margin-top: 4px;
}
.pv-source-link:hover { text-decoration: underline; }
.pv-citation {
  margin-top: 8px;
  padding: 8px 10px;
  background: #f8fafc;
  border-radius: 6px;
  font-size: 11px;
  color: #475569;
  font-style: italic;
  line-height: 1.4;
  border-left: 3px solid #c7d2fe;
}

/* Passages (expanded) */
.pv-passages {
  margin-top: 10px;
  padding-top: 10px;
  border-top: 1px solid #f1f5f9;
}
.pv-passages-title {
  display: flex;
  align-items: center;
  gap: 5px;
  font-size: 11px;
  font-weight: 600;
  color: #6b7280;
  text-transform: uppercase;
  letter-spacing: .5px;
  margin-bottom: 8px;
}
.pv-passage {
  background: #f8f9fa;
  border-radius: 6px;
  padding: 8px 10px;
  margin-bottom: 5px;
  border-left: 3px solid #d1d5db;
}
.pv-passage-text { font-size: 12px; color: #374151; line-height: 1.4; font-style: italic; }
.pv-passage-info { font-size: 11px; color: #9ca3af; margin-top: 3px; }

/* No sources */
.pv-no-sources {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 48px 20px;
  text-align: center;
  gap: 8px;
}
.pv-no-sources p { margin: 0; font-weight: 600; color: #16a34a; font-size: 15px; }
.pv-no-sources span { font-size: 13px; color: #9ca3af; }

/* ─── Footer ─── */
.pv-footer {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 10px 20px;
  border-top: 1px solid #e2e8f0;
  background: #fafbfc;
  font-size: 11px;
  color: #94a3b8;
  flex-wrap: wrap;
}
.pv-db-tag {
  padding: 2px 8px;
  background: #f1f5f9;
  border-radius: 4px;
  color: #64748b;
  font-size: 10px;
  font-weight: 500;
}

/* ─── Responsive ─── */
@media (max-width: 1024px) {
  .pv-body { grid-template-columns: 1fr; }
  .pv-text-panel { border-right: none; border-bottom: 1px solid #e2e8f0; max-height: 400px; }
  .pv-overview { gap: 16px; }
  .pv-overview-stats { flex-wrap: wrap; }
}
@media (max-width: 640px) {
  .pv-overview { padding: 16px; }
  .pv-ring { width: 80px; height: 80px; }
  .ring-number { font-size: 20px; }
  .pv-ostat { padding: 8px 12px; min-width: 70px; }
  .pv-ostat-num { font-size: 18px; }
}
</style>
