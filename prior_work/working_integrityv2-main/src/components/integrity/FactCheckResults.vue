<template>
  <div class="fcr" :class="{ light }">
    <!-- ── Engine failure: loud, never a false-clean "no issues" ── -->
    <div v-if="engineError" class="fcr-error">
      <span class="fcr-error-icon">⚠️</span>
      <div>
        <div class="fcr-error-title">Fact-check could not run</div>
        <div class="fcr-error-detail">{{ warnings[0] || 'The fact-check engine was unreachable. No claims were analyzed — this is not a clean result.' }}</div>
      </div>
    </div>

    <!-- ── Overall result ─────────────────────────────────────── -->
    <div v-if="!engineError" class="fcr-overview">
      <div class="ov-head">
        <span class="ov-verdict" :class="verdictTone">{{ verdictLabel }}</span>
        <span class="ov-sub">{{ checksLine }}</span>
      </div>
      <div class="ov-pills">
        <span class="pill good" :class="{ muted: counts.supported === 0 }">{{ counts.supported }} Supported</span>
        <span class="pill warn" :class="{ muted: counts.unsupported === 0 }">{{ counts.unsupported }} Unsupported</span>
        <span v-if="counts.overstated" class="pill warn">{{ counts.overstated }} Overstated</span>
        <span v-if="counts.needs_review" class="pill warn">{{ counts.needs_review }} Needs review</span>
        <span class="pill bad" :class="{ muted: counts.contradicted === 0 }">{{ counts.contradicted }} Contradicted</span>
        <span v-if="counts.author_claim" class="pill gray">{{ counts.author_claim }} Author claims</span>
        <span class="pill gray" :class="{ muted: counts.unknown === 0 }">{{ counts.unknown }} Unknown</span>
        <span v-if="dois.length" class="pill" :class="validDois === dois.length ? 'good' : 'warn'">DOIs {{ validDois }}/{{ dois.length }} valid</span>
        <span v-if="urls.length" class="pill" :class="brokenUrls ? 'bad' : 'good'">Links {{ urls.length - brokenUrls }}/{{ urls.length }} reachable</span>
      </div>
    </div>

    <!-- ── Tabs ───────────────────────────────────────────────── -->
    <div v-if="!engineError" class="fcr-tabs">
      <button
        v-for="tab in tabs"
        :key="tab.key"
        class="tab"
        :class="{ active: activeTab === tab.key }"
        @click="activeTab = tab.key"
      >
        {{ tab.label }}
        <span v-if="tab.count" class="tab-count" :class="{ alert: tab.key === 'issues' && tab.count }">{{ tab.count }}</span>
      </button>
    </div>

    <!-- ── Claims filter pills ────────────────────────────────── -->
    <div v-if="activeTab === 'claims'" class="claim-filter">
      <button v-for="f in claimFilters" :key="f.key"
        class="cf" :class="{ active: claimFilter === f.key, muted: f.count === 0 }"
        @click="claimFilter = f.key">{{ f.label }} <span v-if="f.count">{{ f.count }}</span></button>
    </div>

    <!-- ── Citation Support Matrix (published-paper audit) ────── -->
    <div v-if="activeTab === 'matrix'" class="matrix-wrap">
      <!-- Reference Integrity — always shown in published-paper mode -->
      <div class="ref-integrity">
        <div class="ri-title">Reference Integrity</div>
        <div class="ri-cards">
          <div class="ri-card"><span class="ri-n">{{ refIntegrity.refsParsed }}</span><span class="ri-l">References parsed</span></div>
          <div class="ri-card"><span class="ri-n">{{ refIntegrity.doisFound }}</span><span class="ri-l">DOIs found</span></div>
          <div class="ri-card good"><span class="ri-n">{{ refIntegrity.doiValid }}</span><span class="ri-l">DOI valid</span></div>
          <div class="ri-card" :class="{ bad: refIntegrity.doiNotFound }"><span class="ri-n">{{ refIntegrity.doiNotFound }}</span><span class="ri-l">DOI not found</span></div>
          <div class="ri-card" :class="{ warn: refIntegrity.doiMismatch }"><span class="ri-n">{{ refIntegrity.doiMismatch }}</span><span class="ri-l">DOI mismatch</span></div>
          <div class="ri-card"><span class="ri-n">{{ refIntegrity.linksFound }}</span><span class="ri-l">Links found</span></div>
          <div class="ri-card good"><span class="ri-n">{{ refIntegrity.linksReachable }}</span><span class="ri-l">Links reachable</span></div>
          <div class="ri-card" :class="{ bad: refIntegrity.linksBroken }"><span class="ri-n">{{ refIntegrity.linksBroken }}</span><span class="ri-l">Links broken</span></div>
          <div class="ri-card" :class="{ warn: refIntegrity.linksBlocked }"><span class="ri-n">{{ refIntegrity.linksBlocked }}</span><span class="ri-l">Links blocked</span></div>
        </div>
      </div>
      <div v-if="!matrixRows.length" class="fcr-empty small"><p>No in-text citations could be mapped to the reference list for this document.</p></div>
      <table v-else class="matrix">
        <thead>
          <tr>
            <th>Citation</th>
            <th>Reference &amp; claim</th>
            <th>Evidence checked</th>
            <th>Supports claim</th>
            <th>Verdict</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="(row, i) in matrixRows" :key="i">
            <td class="mono cit">{{ row.citation }}</td>
            <td class="ref-cell">
              <span class="ref-title">{{ row.reference || '—' }}</span>
              <span v-if="row.is_retracted" class="retracted">RETRACTED</span>
              <a v-if="row.doi" :href="`https://doi.org/${row.doi}`" target="_blank" rel="noopener" class="ref-doi">doi.org/{{ row.doi }}</a>
              <span v-if="row.claim_snippet" class="snippet">“{{ row.claim_snippet }}”</span>
            </td>
            <td><span class="cell-sub" :class="scopeTone(row.evidence_scope)">{{ scopeLabel(row.evidence_scope) }}</span></td>
            <td>{{ row.supports_claim ? cap(row.supports_claim) : '—' }}</td>
            <td><span class="verdict-badge" :class="row.tone">{{ prettyStatus(row.verdict) }}</span></td>
          </tr>
        </tbody>
      </table>
      <p class="matrix-foot">Reference integrity ≠ claim integrity — a valid DOI does not mean the cited source supports the sentence.</p>
    </div>

    <!-- Internal consistency — same-quantity numeric disagreements inside the doc -->
    <div v-else-if="activeTab === 'consistency'" class="consistency-wrap">
      <div class="ic-head">
        <span class="verdict-badge bad">INTERNAL MISMATCH</span>
        <p class="ic-sub">The document reports different values for what appears to be the same quantity. These are flagged for review — they do not change any claim verdict.</p>
      </div>
      <div v-for="(m, i) in internalMismatches" :key="i" class="ic-card">
        <div class="ic-metric">
          <span class="ic-name">{{ m.metric || 'Numeric figure' }}</span>
          <span class="ic-vs"><b>{{ m.value_a }}</b> vs <b>{{ m.value_b }}</b></span>
        </div>
        <p v-if="m.note" class="ic-note">{{ m.note }}</p>
        <div class="ic-snips">
          <p class="ic-snip">“{{ m.snippet_a }}”</p>
          <p class="ic-snip">“{{ m.snippet_b }}”</p>
        </div>
      </div>
    </div>

    <!-- ── Body: list + sticky detail panel ───────────────────── -->
    <div v-else class="results-body">
      <div class="issue-list">
        <!-- Empty states -->
        <div v-if="activeTab === 'issues' && problemCount === 0" class="fcr-empty">
          <span class="empty-glyph">✓</span>
          <p>No issues to fix. Everything checked out.</p>
        </div>
        <div v-else-if="activeTab === 'claims' && visibleClaimRows.length === 0" class="fcr-empty small">
          <p>No {{ claimFilter }} claims.</p>
        </div>

        <!-- ISSUES tab: severity groups -->
        <template v-if="activeTab === 'issues'">
          <template v-for="group in issueGroups" :key="group.key">
            <div v-if="group.rows.length" class="group-head" :class="group.tone">
              {{ group.label }} ({{ group.rows.length }})
            </div>
            <div
              v-for="row in group.rows"
              :key="row.id"
              class="issue-row"
              :class="[row.tone, { selected: selectedId === row.id }]"
              role="button"
              tabindex="0"
              @click="selectedId = row.id"
              @keydown.enter="selectedId = row.id"
            >
              <div class="issue-main">
                <div class="issue-meta">
                  <span class="status-badge" :class="row.tone">{{ row.tag }}</span>
                  <span class="type-label">{{ row.group }}</span>
                </div>
                <div class="issue-title">{{ row.text }}</div>
                <div v-if="row.reason" class="issue-reason">Reason: {{ row.reason }}</div>
              </div>
            </div>
          </template>

          <button v-if="laterRows.length" class="group-toggle" @click="showLater = !showLater">
            <span class="chev" :class="{ open: showLater }">›</span>
            Review Later — {{ laterRows.length }} low-priority claim{{ laterRows.length === 1 ? '' : 's' }}
          </button>
          <template v-if="showLater">
            <div
              v-for="row in laterRows"
              :key="row.id"
              class="issue-row"
              :class="[row.tone, { selected: selectedId === row.id }]"
              role="button"
              tabindex="0"
              @click="selectedId = row.id"
              @keydown.enter="selectedId = row.id"
            >
              <div class="issue-main">
                <div class="issue-meta">
                  <span class="status-badge" :class="row.tone">{{ row.tag }}</span>
                  <span class="type-label">{{ row.group }}</span>
                </div>
                <div class="issue-title">{{ row.text }}</div>
                <div v-if="row.reason" class="issue-reason">Reason: {{ row.reason }}</div>
              </div>
            </div>
          </template>

          <button v-if="warnings.length" class="group-toggle" @click="showNotices = !showNotices">
            <span class="chev" :class="{ open: showNotices }">›</span>
            Notices ({{ warnings.length }})
          </button>
          <div v-if="showNotices" class="notices">
            <div v-for="(w, i) in warnings" :key="i" class="notice">{{ w }}</div>
          </div>
        </template>

        <!-- CLAIMS / REFERENCES / LINKS tabs: flat row list -->
        <template v-else>
          <div
            v-for="row in currentRows"
            :key="row.id"
            class="issue-row"
            :class="[row.tone, { selected: selectedId === row.id }]"
            role="button"
            tabindex="0"
            @click="selectedId = row.id"
            @keydown.enter="selectedId = row.id"
          >
            <div class="issue-main">
              <div class="issue-meta">
                <span class="status-badge" :class="row.tone">{{ row.tag }}</span>
                <span class="type-label">{{ row.group }}</span>
              </div>
              <div class="issue-title" :class="{ mono: row.mono }">{{ row.text }}</div>
              <div v-if="row.reason" class="issue-reason">{{ row.reasonPrefix !== false ? 'Reason: ' : '' }}{{ row.reason }}</div>
            </div>
          </div>
        </template>
      </div>

      <!-- Sticky detail panel -->
      <aside class="details-panel">
        <div v-if="!selectedRow" class="detail-empty">
          <p>Select an item to see details</p>
        </div>
        <template v-else>
          <div class="detail-head">
            <span class="status-badge" :class="selectedRow.tone">{{ selectedRow.tag }}</span>
          </div>
          <div class="detail-type">Type: {{ selectedRow.group }}</div>
          <p class="detail-claim" :class="{ mono: selectedRow.mono }">{{ selectedRow.text }}</p>

          <div v-if="selectedRow.reason" class="detail-sec">
            <span class="sec-label">Reason</span>
            <p class="sec-body">{{ selectedRow.reason }}</p>
          </div>

          <div v-if="selectedRow.meta" class="detail-sec">
            <span class="sec-label">Resolved record</span>
            <p class="sec-body strong">{{ selectedRow.meta.title }}</p>
            <p v-if="selectedRow.meta.authors" class="sec-body">{{ selectedRow.meta.authors }}</p>
            <p v-if="selectedRow.meta.line" class="sec-body">{{ selectedRow.meta.line }}</p>
          </div>

          <div v-if="selectedRow.source" class="detail-sec">
            <span class="sec-label">Source</span>
            <p class="sec-body mono">{{ selectedRow.source }}</p>
          </div>

          <div v-if="selectedRow.evidence?.length" class="detail-sec">
            <span class="sec-label">Evidence checked</span>
            <div class="ev-block">
              <div v-for="(ev, i) in selectedRow.evidence" :key="i" class="ev">
                <span v-if="ev.source" class="ev-source">{{ ev.source }}</span>
                <span v-if="ev.snippet" class="ev-snippet">{{ ev.snippet }}</span>
                <a v-if="ev.url" :href="ev.url" target="_blank" rel="noopener" class="ev-link">View source →</a>
              </div>
            </div>
          </div>

          <div v-if="selectedRow.fix" class="detail-sec fix-sec">
            <span class="sec-label">Suggested fix</span>
            <p class="sec-body">{{ selectedRow.fix }}</p>
          </div>

          <div class="detail-actions">
            <a v-if="selectedRow.url" :href="selectedRow.url" target="_blank" rel="noopener" class="act-btn">Open source ↗</a>
            <button class="act-btn" @click="copy(selectedRow.copyText, selectedRow.id)">{{ copiedId === selectedRow.id ? 'Copied ✓' : 'Copy' }}</button>
            <button v-if="activeTab === 'issues'" class="act-btn quiet" @click="ignoreRow(selectedRow.id)">Ignore</button>
          </div>
        </template>
      </aside>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, watch } from 'vue'

const props = defineProps({
  results: { type: Object, required: true },
  light: { type: Boolean, default: false },
})

const activeTab = ref('issues')
const selectedId = ref(null)
const copiedId = ref(null)
const showNotices = ref(false)
const showLater = ref(false)
const claimFilter = ref('all')

async function copy(text, id) {
  try {
    await navigator.clipboard.writeText(text || '')
    copiedId.value = id
    setTimeout(() => { if (copiedId.value === id) copiedId.value = null }, 1500)
  } catch { /* clipboard blocked */ }
}

// ── Data slices ────────────────────────────────────────────────
// Successful reference checks sometimes arrive as claim rows
// ("Citation metadata matches DOI metadata for 10.x/..."). Those are not
// issues — they appear on the References tab as verified citations only.
const NOISE_RE = /citation metadata match|metadata matches doi/i
// Item 8: in Published Paper Audit only the four real claim zones are shown.
// The engine already excludes noise zones upstream, so this is defensive:
// keep claims with no zone (general mode sends zone=null) or a real zone; hide
// only explicitly-labelled noise zones.
const NOISE_CLAIM_ZONES = new Set([
  'EQUATION', 'FIGURE_EXAMPLE', 'TABLE_EXAMPLE', 'MODEL_OUTPUT', 'REFERENCE_ENTRY', 'HEADER_FOOTER',
])
function isRealClaimZone(c) {
  const z = c?.zone
  return !z || !NOISE_CLAIM_ZONES.has(z)
}
const rawClaims = computed(() => props.results?.claims || [])
const claims = computed(() => rawClaims.value.filter(c => !NOISE_RE.test(c.claim || '') && isRealClaimZone(c)))
const metadataNotes = computed(() => rawClaims.value.filter(c => NOISE_RE.test(c.claim || '')).map(c => c.claim))

const dois = computed(() => props.results?.reference_report?.dois || [])
const urls = computed(() => props.results?.reference_report?.urls || [])
const warnings = computed(() => props.results?.warnings || [])
// Engine failure flag from the backend — also recognize legacy error-shaped
// results (zero claims + an "API error"/"service error" warning, no error field).
const engineError = computed(() => {
  const r = props.results
  if (!r) return false
  if (r.error === true) return true
  const noClaims = !(r.claims || []).length
  return noClaims && (r.warnings || []).some(w => /api error|service error|rejected the request/i.test(String(w)))
})
const citationMatrix = computed(() => props.results?.citation_matrix || [])
// Internal numeric-consistency pass (additive — its own field, never mixed into claims).
const internalConsistency = computed(() => props.results?.internal_consistency || null)
const internalMismatches = computed(() =>
  internalConsistency.value?.status === 'internal_mismatch'
    ? (internalConsistency.value.findings || [])
    : []
)
const hasReferences = computed(() => dois.value.length > 0 || urls.value.length > 0)
const referencesParsed = computed(() => props.results?.references_parsed || 0)
// Published-paper mode: the engine parsed a reference list and/or built a matrix.
const isPublishedAudit = computed(() => referencesParsed.value > 0 || citationMatrix.value.length > 0)
// Coverage-aware verdict from the engine: "0 issues" is NOT "clean" when most
// cited sources could not be retrieved/content-checked (reference integrity != claim integrity).
const backendVerdict = computed(() => props.results?.verdict || null)
const citationCoverage = computed(() => props.results?.citation_coverage || null)
// Reference Integrity summary (always shown in published mode, even if all zero).
const refIntegrity = computed(() => {
  const d = dois.value, u = urls.value
  const n = (arr, ...st) => arr.filter(x => st.includes(x.status)).length
  return {
    refsParsed: referencesParsed.value,
    doisFound: d.length, doiValid: n(d, 'valid'), doiNotFound: n(d, 'not_found', 'invalid'), doiMismatch: n(d, 'mismatch'),
    linksFound: u.length, linksReachable: n(u, 'ok'), linksBroken: n(u, 'broken', 'error'), linksBlocked: n(u, 'blocked', 'timeout'),
  }
})

// An "overstated" claim comes back from the engine with verdict 'unsupported'
// (the source backs a weaker version), but a citation alignment marks it
// overstated. Surface that as a first-class label.
function claimIsOverstated(c) {
  return (c.citation_alignment || []).some(a => a.support === 'overstated')
}
function claimTag(c) {
  return claimIsOverstated(c) ? 'overstated' : c.verdict
}

const counts = computed(() => {
  const c = { supported: 0, unsupported: 0, overstated: 0, needs_review: 0, contradicted: 0, unknown: 0, author_claim: 0 }
  for (const cl of claims.value) { const t = claimTag(cl); if (c[t] != null) c[t]++ }
  return c
})

const validDois = computed(() => dois.value.filter(d => d.status === 'valid').length)
const brokenUrls = computed(() => urls.value.filter(u => u.status !== 'ok').length)

// ── Claim importance (mirrors the engine's intent; used to keep low-value,
// uncheckable statements out of the Issues view). If the engine ever sends an
// `importance` field on a claim, that wins.
const DOMAIN_TERMS = ['gravitational', 'quantum', 'boson', 'higgs', 'relativity', 'vaccine', 'crispr', 'protein', 'genome', 'climate', 'sea level', 'black hole', 'antibiotic', 'cancer', 'covid', 'pandemic', 'fda', 'nobel', 'galaxy', 'telescope', 'poverty', 'recession', 'inflation', 'transformer', 'alphafold', 'satellite', 'particle']
const HEDGE_RE = /\b(may|might|can|could|should|would|often|sometimes|generally|typically|usually)\b/i
const PROPER_RE = /\b(?!(?:The|This|That|These|Those|Some|Many|Most|It|In|A|An|However|Another)\b)[A-Z][a-z]{2,}/
function classifyImportance(text) {
  const t = (text || '').toLowerCase()
  const hasDoi = /10\.\d{4,9}\//.test(text) || t.includes('arxiv')
  const hasUrl = t.includes('http://') || t.includes('https://')
  const hasPercent = text.includes('%') || t.includes('percent')
  const hasYear = /\b(1[89]\d{2}|20\d{2})\b/.test(text)
  const hasNumber = /\d/.test(text)
  const hasProper = PROPER_RE.test(text)
  const hasDomain = DOMAIN_TERMS.some(d => t.includes(d))
  let imp
  if (hasDoi || hasUrl) imp = 'high'
  else if (hasPercent || (hasNumber && (hasYear || hasProper || hasDomain))) imp = 'high'
  else if (hasProper && hasYear) imp = 'high'
  else if (hasDomain) imp = 'medium'
  else if (hasProper) imp = 'medium'
  else imp = 'low'
  if (imp === 'medium' && HEDGE_RE.test(t) && !(hasProper || hasDomain)) imp = 'low'
  return imp
}
function claimImportance(c) {
  return c.importance || classifyImportance(c.claim)
}
function isLowImportance(c) {
  return claimImportance(c) === 'low' || c.verify === false
}

// ── Status → tone (5 colors) ───────────────────────────────────
function verdictTone2(v) {
  return { supported: 'good', contradicted: 'bad', unsupported: 'warn', overstated: 'warn', needs_review: 'warn', unknown: 'gray', author_claim: 'gray' }[v] || 'gray'
}
// Evidence-scope label/tone (Published Paper Audit only checks abstracts).
function scopeLabel(s) {
  return { abstract: 'Abstract only', metadata_only: 'Metadata only', not_retrieved: 'Could not retrieve' }[s] || '—'
}
function scopeTone(s) {
  if (s === 'abstract') return 'warn'        // partial evidence — flag the limitation
  if (s === 'not_retrieved') return 'gray'
  return 'gray'
}
// Published-paper zone → friendly label.
const ZONE_LABELS = {
  RELATED_WORK_CLAIM: 'Related-work claim', METHOD_CLAIM: 'Method claim',
  RESULT_CLAIM: 'Result claim', AUTHOR_CLAIM: 'Author claim',
}
function zoneLabel(z) { return ZONE_LABELS[z] || null }
function cap(s) { return s ? s.charAt(0).toUpperCase() + s.slice(1).replace(/_/g, ' ') : s }
function metaLabel(m) { return m === true ? 'Match' : m === false ? 'Mismatch' : '—' }

// ── Citation Support Matrix rows (published-paper audit) ───────
function matrixTone(verdict) {
  if (verdict === 'supported') return 'good'
  if (verdict === 'contradicted' || verdict === 'not_found') return 'bad'
  // 'reference' = tool/dataset/method/background/example cite — not expected to
  // support the sentence, so it is neutral, not a warning.
  if (verdict === 'unknown' || verdict === 'could_not_retrieve' || verdict === 'reference') return 'gray'
  return 'warn'  // needs_review | partial | unrelated | mismatch | overstated
}
const matrixRows = computed(() => citationMatrix.value.map(r => ({ ...r, tone: matrixTone(r.verdict) })))
function doiTone(s) {
  if (s === 'valid') return 'good'
  if (s === 'mismatch') return 'warn'
  return 'bad'
}
function urlTone(s) {
  if (s === 'ok') return 'good'
  if (s === 'blocked' || s === 'timeout') return 'warn'  // reachable but refused — not dead
  return 'bad'  // broken / error → 404/5xx
}
function prettyStatus(s) {
  if (s === 'reference') return 'reference cite'
  if (s === 'could_not_retrieve') return 'not retrieved'
  if (s === 'full_text') return 'full text'
  return (s || '').replace(/_/g, ' ')
}

// ── Row builders (human-readable; no concatenated labels) ──────
// A citation was actually mapped to a reference AND checked (has alignment).
function citationChecked(c) {
  return c.citation_mapped === true && (c.citation_alignment?.length || c.evidence?.length)
}

function claimReason(c) {
  if (c.verdict === 'author_claim') return "Author's own claim about this work (self-reported) — not checked against external sources."
  if (c.verdict === 'needs_review') {
    return citationChecked(c)
      ? 'The cited source’s abstract does not clearly support this claim — verify against the full paper text.'
      : 'A citation was detected but its reference could not be mapped — verify manually.'
  }
  if (claimIsOverstated(c)) return 'The cited source supports a weaker claim — this statement overstates its scope or strength.'
  if (c.verdict === 'contradicted') return 'Evidence contradicts this claim.'
  if (c.verdict === 'unsupported') {
    return citationChecked(c)
      ? 'Cited source is valid but does not support this claim.'
      : 'No mapped citation/source was available for automatic verification.'
  }
  if (c.verdict === 'unknown') {
    return citationChecked(c)
      ? 'The cited source could not be retrieved for automatic verification.'
      : 'No mapped citation/source was available for automatic verification.'
  }
  return ''
}

function claimFix(c) {
  if (c.verdict === 'author_claim') return 'No action needed — this is the authors’ own claim about their work. Check it against the paper’s methods/results if you want to scrutinise it.'
  if (c.verdict === 'needs_review') return 'Only the cited source’s abstract was checked. Read the full source to confirm it supports the claim, or cite a more specific source.'
  if (claimIsOverstated(c)) return 'Soften the claim to match what the cited source actually shows, or cite stronger evidence for the broader statement.'
  if (c.verdict === 'contradicted') return 'Correct or remove this claim — the checked evidence contradicts it.'
  if (c.verdict === 'unsupported') {
    return citationChecked(c)
      ? 'Keep the source for what it actually shows, but add a citation that supports this specific claim — or soften the wording.'
      : 'Add a citation that can be resolved and checked, or rephrase as a hypothesis rather than a fact.'
  }
  if (c.verdict === 'unknown') return 'Verify this manually and consider adding a resolvable citation.'
  return ''
}

function doiFix(status) {
  if (status === 'mismatch') return 'The DOI points to a different work. Update the DOI or correct the citation it is attached to.'
  if (status === 'invalid') return 'Fix the DOI syntax (check for typos or truncation).'
  if (status !== 'valid') return 'Remove this citation or replace it with a verifiable DOI from the publisher or doi.org.'
  return ''
}

function claimRow(c, i) {
  const ev = (c.evidence || []).find(e => e.source || e.url)
  const tag = claimTag(c)
  return {
    id: 'c' + i,
    tone: verdictTone2(tag),
    tag: tag === 'author_claim' ? 'author claim' : tag === 'needs_review' ? 'needs review' : tag,
    group: zoneLabel(c.zone) || 'Claim issue',
    text: c.claim,
    reason: claimReason(c),
    source: ev ? (ev.source || ev.url) : null,
    url: (c.evidence || []).find(e => e.url)?.url || null,
    evidence: c.evidence || [],
    fix: claimFix(c),
    copyText: c.claim,
  }
}

function doiRow(d, i) {
  const tone = doiTone(d.status)
  return {
    id: 'd' + i,
    tone,
    tag: prettyStatus(d.status),
    group: 'Reference issue',
    mono: true,
    text: d.doi,
    reason: d.note || (
      tone === 'good' ? '' :
      d.status === 'mismatch'
        ? 'The DOI resolves, but its record does not match the citation.'
        : 'This DOI could not be resolved to a real record — possibly fabricated.'
    ),
    meta: d.metadata ? {
      title: d.metadata.title,
      authors: d.metadata.authors?.join(', '),
      line: [d.metadata.year, d.metadata.venue].filter(Boolean).join(' · '),
    } : null,
    source: d.doi,
    url: d.doi ? `https://doi.org/${d.doi}` : null,
    fix: doiFix(d.status),
    copyText: d.doi,
  }
}

function urlRow(u, i) {
  const blocked = u.status === 'blocked' || u.status === 'timeout'
  return {
    id: 'u' + i,
    tone: urlTone(u.status),
    tag: blocked ? 'blocked' : prettyStatus(u.status),
    group: 'Link issue',
    mono: true,
    text: u.url,
    reason: u.note || (
      u.status === 'ok' ? '' :
      blocked ? 'The link is reachable but blocks automated checks — verify it opens in a browser.'
              : 'This link returned a 404 or server error and appears dead.'
    ),
    source: u.url,
    url: u.url,
    fix: u.status === 'ok' ? '' : (
      blocked ? 'Likely fine — confirm it opens in a browser. No change needed if it loads.'
              : 'Replace with a working link, or cite an archived copy (web.archive.org).'
    ),
    copyText: u.url,
  }
}

// ── Issues tab: severity groups (problems only) ────────────────
// V1 (locked): Critical = not-found/invalid DOI, metadata mismatch, broken URL,
// contradicted claim. Needs Evidence = unsupported claim. Review Later = unknown.
const ignoredIds = ref(new Set())
function ignoreRow(id) {
  const s = new Set(ignoredIds.value)
  s.add(id)
  ignoredIds.value = s
}

// Low-importance claims (generic/uncheckable) are kept out of Issues by
// default — contradicted claims and reference failures are ALWAYS shown
// regardless of importance (see isLowImportance above).
const issueGroups = computed(() => {
  const critical = []
  const needsEvidence = []
  const needsReview = []
  claims.value.forEach((c, i) => {
    if (c.verdict === 'contradicted') critical.push(claimRow(c, i))
    else if (claimIsOverstated(c)) needsEvidence.push(claimRow(c, i))  // always surface, regardless of importance
    else if (c.verdict === 'unsupported' && !isLowImportance(c)) needsEvidence.push(claimRow(c, i))
    else if (c.verdict === 'needs_review') needsReview.push(claimRow(c, i))  // abstract-only / unmapped citation
  })
  dois.value.forEach((d, i) => {
    if (d.status !== 'valid') critical.push(doiRow(d, i))
  })
  urls.value.forEach((u, i) => {
    // Dead links (404/5xx) are critical; blocked/timeout (reachable but
    // refused) is only a "needs evidence" nudge, not a fabricated reference.
    if (u.status === 'broken' || u.status === 'error') critical.push(urlRow(u, i))
    else if (u.status !== 'ok') needsEvidence.push(urlRow(u, i))
  })
  const visible = rows => rows.filter(r => !ignoredIds.value.has(r.id))
  return [
    { key: 'critical', label: 'Critical Issues', tone: 'bad', rows: visible(critical) },
    { key: 'evidence', label: 'Needs Evidence', tone: 'warn', rows: visible(needsEvidence) },
    { key: 'review', label: 'Needs Review — abstract only / citation not mapped', tone: 'warn', rows: visible(needsReview) },
  ]
})

// Review Later = genuinely unverifiable (unknown) claims + low-importance
// uncited "unsupported" sentences (item 7: treat these as low-priority, not as
// problems to fix). Collapsed by default so they don't clutter Issues.
const laterRows = computed(() =>
  claims.value.map((c, i) => ({ c, i }))
    .filter(({ c }) =>
      c.verdict === 'unknown' ||
      (c.verdict === 'unsupported' && isLowImportance(c) && !(c.evidence && c.evidence.length))
    )
    .map(({ c, i }) => claimRow(c, i))
    .filter(r => !ignoredIds.value.has(r.id))
)

const problemCount = computed(() => issueGroups.value.reduce((n, g) => n + g.rows.length, 0))

// ── Claims tab rows ────────────────────────────────────────────
const SORT = { contradicted: 0, overstated: 1, unsupported: 2, 'needs review': 3, unknown: 4, supported: 5, 'author claim': 6 }
const claimRowsAll = computed(() =>
  claims.value.map((c, i) => claimRow(c, i)).sort((a, b) => (SORT[a.tag] ?? 4) - (SORT[b.tag] ?? 4))
)
const visibleClaimRows = computed(() => {
  if (claimFilter.value === 'all') return claimRowsAll.value
  return claimRowsAll.value.filter(r => r.tag === claimFilter.value)
})

// ── References / Links tab rows ────────────────────────────────
const refRows = computed(() => {
  const rows = dois.value.map((d, i) => {
    const r = doiRow(d, i)
    if (r.tone === 'good') { r.group = 'Reference'; r.reason = r.meta?.title || '' ; r.reasonPrefix = false }
    return r
  })
  metadataNotes.value.forEach((note, i) => {
    rows.push({
      id: 'm' + i, tone: 'good', tag: 'verified', group: 'Reference',
      text: note, reason: '', copyText: note, reasonPrefix: false,
    })
  })
  return rows
})
const linkRows = computed(() => urls.value.map((u, i) => {
  const r = urlRow(u, i)
  if (r.tone === 'good') { r.group = 'Link'; r.reasonPrefix = false }
  return r
}))

// ── Current visible flat list + auto-select first ──────────────
const currentRows = computed(() => {
  if (activeTab.value === 'claims') return visibleClaimRows.value
  if (activeTab.value === 'refs') return refRows.value
  if (activeTab.value === 'urls') return linkRows.value
  // issues tab: flattened (groups + expanded later rows)
  return [...issueGroups.value.flatMap(g => g.rows), ...(showLater.value ? laterRows.value : [])]
})

const selectedRow = computed(() => {
  const all = [
    ...issueGroups.value.flatMap(g => g.rows),
    ...laterRows.value,
    ...claimRowsAll.value,
    ...refRows.value,
    ...linkRows.value,
  ]
  return all.find(r => r.id === selectedId.value) || null
})

// Rule 7: auto-select the first visible item in the active tab/filter
watch(currentRows, (rows) => {
  if (!rows.some(r => r.id === selectedId.value)) {
    selectedId.value = rows[0]?.id || null
  }
}, { immediate: true })

// ── Overall verdict ────────────────────────────────────────────
const verdictTone = computed(() => {
  // Low coverage (most cited sources unverifiable) is never a clean pass.
  if (backendVerdict.value?.is_low_coverage) return 'warn'
  if (issueGroups.value[0].rows.length) return 'bad'
  // any "needs evidence" or "needs review" item -> not a clean pass
  if (issueGroups.value.slice(1).some(g => g.rows.length)) return 'warn'
  return claims.value.length || hasReferences.value ? 'good' : 'gray'
})
const verdictLabel = computed(() => {
  if (!claims.value.length && !hasReferences.value) return 'No claims detected'
  // Prefer the engine's coverage-aware verdict so we never claim "Looks Good"
  // when the document could not actually be verified.
  const s = backendVerdict.value?.status
  if (s === 'limited_verification') return 'Limited Verification'
  if (s === 'needs_review') return 'Needs Review'
  if (s === 'looks_good') return 'Looks Good'
  if (verdictTone.value === 'good') return 'Looks Good'
  return 'Needs Review'
})
const checksLine = computed(() => {
  const parts = []
  if (claims.value.length) parts.push(`${claims.value.length} claim${claims.value.length === 1 ? '' : 's'}`)
  if (dois.value.length) parts.push(`${dois.value.length} DOI${dois.value.length === 1 ? '' : 's'}`)
  if (urls.value.length) parts.push(`${urls.value.length} link${urls.value.length === 1 ? '' : 's'}`)
  const checked = parts.join(' · ') || 'nothing'
  // When cited sources could not all be content-checked, report coverage HONESTLY
  // instead of "0 issues found" (which reads as "clean" but means "couldn't check").
  const cov = citationCoverage.value
  if (cov && cov.cited) {
    const unver = cov.cited - cov.content_checked
    if (unver > 0) {
      return `${checked} · ${cov.content_checked}/${cov.cited} cited sources content-checked · ${unver} unverifiable`
    }
  }
  return `${checked} checked · ${problemCount.value} issue${problemCount.value === 1 ? '' : 's'} found`
})

// ── Tabs ───────────────────────────────────────────────────────
const tabs = computed(() => {
  const t = [{ key: 'issues', label: 'Issues', count: problemCount.value }]
  if (isPublishedAudit.value) t.push({ key: 'matrix', label: 'Citation Matrix', count: citationMatrix.value.length })
  if (internalMismatches.value.length) t.push({ key: 'consistency', label: 'Consistency', count: internalMismatches.value.length })
  if (claims.value.length) t.push({ key: 'claims', label: 'Claims', count: claims.value.length })
  if (refRows.value.length) t.push({ key: 'refs', label: 'References', count: refRows.value.length })
  if (urls.value.length) t.push({ key: 'urls', label: 'Links', count: urls.value.length })
  return t
})
watch(tabs, (t) => { if (!t.some(x => x.key === activeTab.value)) activeTab.value = 'issues' })

const claimFilters = computed(() => [
  { key: 'all', label: 'All', count: claims.value.length },
  { key: 'unsupported', label: 'Unsupported', count: counts.value.unsupported },
  { key: 'overstated', label: 'Overstated', count: counts.value.overstated },
  { key: 'needs review', label: 'Needs review', count: counts.value.needs_review },
  { key: 'contradicted', label: 'Contradicted', count: counts.value.contradicted },
  { key: 'supported', label: 'Supported', count: counts.value.supported },
  { key: 'author claim', label: 'Author claims', count: counts.value.author_claim },
  { key: 'unknown', label: 'Unknown', count: counts.value.unknown },
])
</script>

<style scoped>
/* Palette — light surface (researcher page) and dark (editor panel) */
.fcr {
  --card: #ffffff;
  --card-hover: #fafafa;
  --card-selected: #fbf8ff;
  --border: #e5e7eb;
  --border-strong: #d1d5db;
  --text: #111827;
  --text-sub: #6b7280;
  --text-mute: #9ca3af;
  --good: #1e8e3e;
  --bad: #ef4444;
  --warn: #f97316;
  --gray: #6b7280;
  --good-bg: #e6f4ea;
  --bad-bg: #fce8e6;
  --warn-bg: #fff3e8;
  --gray-bg: #f1f3f4;
  --accent: #8b5cf6;
  font-size: 13px;
  color: var(--text);
  text-align: left;
}
.fcr:not(.light) {
  --card: rgba(255,255,255,0.03);
  --card-hover: rgba(255,255,255,0.06);
  --card-selected: rgba(139,92,246,0.10);
  --border: rgba(255,255,255,0.10);
  --border-strong: rgba(255,255,255,0.18);
  --text: rgba(255,255,255,0.92);
  --text-sub: rgba(255,255,255,0.62);
  --text-mute: rgba(255,255,255,0.42);
  --good: #34d399;
  --bad: #f87171;
  --warn: #fb923c;
  --gray: #9ca3af;
  --good-bg: rgba(16,185,129,0.14);
  --bad-bg: rgba(244,63,94,0.14);
  --warn-bg: rgba(249,115,22,0.14);
  --gray-bg: rgba(156,163,175,0.14);
  --accent: #a78bfa;
}

/* ── Overview ── */
.fcr-overview { margin-bottom: 14px; }

/* Engine failure banner */
.fcr-error {
  display: flex;
  gap: 12px;
  align-items: flex-start;
  background: #fef2f2;
  border: 2px solid #ef4444;
  border-radius: 10px;
  padding: 14px 16px;
  margin-bottom: 14px;
}
.fcr-error-icon { font-size: 22px; line-height: 1; }
.fcr-error-title { font-weight: 700; color: #dc2626; font-size: 14px; margin-bottom: 3px; }
.fcr-error-detail { font-size: 13px; color: #7f1d1d; line-height: 1.5; }
.ov-head { display: flex; align-items: baseline; gap: 12px; flex-wrap: wrap; margin-bottom: 12px; }
.ov-verdict { font-size: 19px; font-weight: 700; letter-spacing: -0.01em; }
.ov-verdict.good { color: var(--good); }
.ov-verdict.warn { color: var(--warn); }
.ov-verdict.bad { color: var(--bad); }
.ov-verdict.gray { color: var(--text-sub); }
.ov-sub { font-size: 12.5px; color: var(--text-sub); }

.ov-pills { display: flex; flex-wrap: wrap; gap: 6px; }
.pill {
  font-size: 11.5px; font-weight: 600; padding: 3px 10px; border-radius: 999px;
  border: 1px solid transparent;
}
.pill.good { background: var(--good-bg); color: var(--good); }
.pill.warn { background: var(--warn-bg); color: var(--warn); }
.pill.bad { background: var(--bad-bg); color: var(--bad); }
.pill.gray { background: var(--gray-bg); color: var(--gray); }
.pill.muted { background: transparent; color: var(--text-mute); border-color: var(--border); }

/* ── Tabs ── */
.fcr-tabs { display: flex; gap: 4px; border-bottom: 1px solid var(--border); margin-bottom: 12px; }
.tab {
  background: none; border: none; cursor: pointer;
  padding: 8px 12px; font-size: 13px; font-weight: 600; color: var(--text-sub);
  border-bottom: 2px solid transparent; margin-bottom: -1px;
  display: inline-flex; align-items: center; gap: 6px;
}
.tab:hover { color: var(--text); }
.tab.active { color: var(--accent); border-bottom-color: var(--accent); }
.tab-count {
  font-size: 11px; font-weight: 700; min-width: 18px; height: 18px; padding: 0 5px;
  border-radius: 9px; background: var(--gray-bg); color: var(--text-sub);
  display: inline-flex; align-items: center; justify-content: center;
}
.tab-count.alert { background: var(--bad-bg); color: var(--bad); }

/* ── Claims filter ── */
.claim-filter { display: flex; flex-wrap: wrap; gap: 6px; margin-bottom: 12px; }
.cf {
  background: var(--card); border: 1px solid var(--border); cursor: pointer;
  font-size: 11.5px; font-weight: 600; color: var(--text-sub);
  padding: 4px 11px; border-radius: 14px;
}
.cf:hover { color: var(--text); }
.cf.active { background: var(--accent); color: #fff; border-color: var(--accent); }
.cf.muted { opacity: 0.45; }

/* ── Body: list + detail ── */
.results-body {
  display: grid;
  grid-template-columns: minmax(0, 1fr) 420px;
  gap: 24px;
  align-items: start;
}
@media (max-width: 900px) {
  .results-body { grid-template-columns: 1fr; }
  .details-panel { position: static; }
}

.issue-list { display: flex; flex-direction: column; gap: 8px; min-width: 0; }

/* ── Severity group headers ── */
.group-head {
  font-size: 11px; font-weight: 700; text-transform: uppercase; letter-spacing: 0.06em;
  color: var(--text-sub); margin: 8px 0 0; padding-left: 2px;
}
.group-head:first-child { margin-top: 0; }
.group-head.bad { color: var(--bad); }
.group-head.warn { color: var(--warn); }
.group-head.good { color: var(--good); }

.group-toggle {
  margin-top: 6px; background: none; border: none; cursor: pointer; text-align: left;
  font-size: 12px; font-weight: 600; color: var(--text-sub);
  display: flex; align-items: center; gap: 6px; padding: 6px 0;
}
.group-toggle:hover { color: var(--text); }
.chev {
  color: var(--text-mute); font-size: 16px; line-height: 1;
  transition: transform 0.15s ease; transform: rotate(0deg); display: inline-block;
}
.chev.open { transform: rotate(90deg); }

/* ── Issue rows (compact, left-aligned, 2-line clamp) ── */
.issue-row {
  width: 100%;
  min-height: 72px;
  padding: 12px 14px;
  border: 1px solid var(--border);
  border-left: 4px solid var(--border-strong);
  border-radius: 10px;
  background: var(--card);
  text-align: left;
  display: grid;
  grid-template-columns: 1fr auto;
  gap: 12px;
  cursor: pointer;
}
.issue-row:hover { background: var(--card-hover); }
.issue-row:focus-visible { outline: 2px solid var(--accent); outline-offset: 1px; }
.issue-row.selected {
  border-color: var(--accent);
  border-left-color: var(--accent);
  background: var(--card-selected);
}
.issue-row.warn { border-left-color: var(--warn); }
.issue-row.bad { border-left-color: var(--bad); }
.issue-row.gray { border-left-color: var(--gray); }
.issue-row.good { border-left-color: var(--good); }
.issue-row.selected.warn, .issue-row.selected.bad,
.issue-row.selected.gray, .issue-row.selected.good { border-left-color: var(--accent); }

.issue-main { min-width: 0; }

.issue-meta {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 6px;
}

.status-badge {
  font-size: 11px;
  font-weight: 700;
  letter-spacing: 0.04em;
  text-transform: uppercase;
  padding: 3px 8px;
  border-radius: 999px;
  flex-shrink: 0;
}
.status-badge.good { background: var(--good-bg); color: var(--good); }
.status-badge.bad { background: var(--bad-bg); color: var(--bad); }
.status-badge.warn { background: var(--warn-bg); color: var(--warn); }
.status-badge.gray { background: var(--gray-bg); color: var(--gray); }

.type-label {
  font-size: 12px;
  color: var(--text-sub);
  font-weight: 600;
}

.issue-title {
  font-size: 14px;
  line-height: 1.35;
  color: var(--text);
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
  overflow-wrap: anywhere;
}
.issue-title.mono { font-family: ui-monospace, 'SF Mono', Menlo, monospace; font-size: 13px; }

.issue-reason {
  margin-top: 4px;
  font-size: 12px;
  line-height: 1.35;
  color: var(--text-sub);
  display: -webkit-box;
  -webkit-line-clamp: 1;
  -webkit-box-orient: vertical;
  overflow: hidden;
}

/* ── Detail panel ── */
.details-panel {
  position: sticky;
  top: 24px;
  min-height: 220px;
  border: 1px solid var(--border);
  border-radius: 14px;
  background: var(--card);
  padding: 20px;
  display: flex;
  flex-direction: column;
  gap: 12px;
  min-width: 0;
}
.detail-empty { color: var(--text-mute); font-size: 13px; text-align: center; padding: 60px 0; }
.detail-empty p { margin: 0; }
.detail-head { display: flex; align-items: center; gap: 8px; }
.detail-type { font-size: 12px; font-weight: 600; color: var(--text-sub); }
.detail-claim {
  margin: 0; font-size: 14.5px; font-weight: 600; color: var(--text);
  line-height: 1.5; overflow-wrap: anywhere;
}
.detail-claim.mono { font-family: ui-monospace, 'SF Mono', Menlo, monospace; font-size: 13px; }

.detail-sec { display: flex; flex-direction: column; gap: 4px; }
.sec-label {
  font-size: 10.5px; font-weight: 700; text-transform: uppercase; letter-spacing: 0.06em;
  color: var(--text-mute);
}
.sec-body { margin: 0; font-size: 12.5px; color: var(--text-sub); line-height: 1.5; }
.sec-body.strong { color: var(--text); font-weight: 600; }
.sec-body.mono { font-family: ui-monospace, 'SF Mono', Menlo, monospace; font-size: 12px; overflow-wrap: anywhere; }

.ev-block { display: flex; flex-direction: column; gap: 8px; }
.ev {
  background: var(--gray-bg); border-radius: 6px; padding: 8px 10px;
  font-size: 12px; display: flex; flex-direction: column; gap: 4px;
}
.ev-source { font-weight: 600; color: var(--accent); font-size: 11px; }
.ev-snippet { color: var(--text-sub); font-style: italic; line-height: 1.45; }
.ev-link { color: var(--accent); font-weight: 600; text-decoration: none; align-self: flex-start; }
.ev-link:hover { text-decoration: underline; }

.detail-actions { display: flex; gap: 10px; margin-top: 4px; }
.act-btn {
  background: none; border: 1px solid var(--border); cursor: pointer;
  font-size: 12px; font-weight: 600; color: var(--accent);
  padding: 6px 14px; border-radius: 8px; text-decoration: none;
}
.act-btn:hover { border-color: var(--accent); background: var(--card-selected); }
.act-btn.quiet { color: var(--text-sub); }
.act-btn.quiet:hover { border-color: var(--text-mute); background: var(--card-hover); }

.fix-sec {
  background: var(--card-selected);
  border: 1px solid var(--border);
  border-radius: 8px;
  padding: 10px 12px;
}

/* ── Empty + notices ── */
.fcr-empty {
  display: flex; flex-direction: column; align-items: center; gap: 8px;
  padding: 40px 20px; text-align: center; color: var(--text-sub);
}
.fcr-empty.small { padding: 24px; }
.empty-glyph {
  width: 40px; height: 40px; border-radius: 50%; background: var(--good-bg);
  color: var(--good); display: flex; align-items: center; justify-content: center;
  font-size: 20px; font-weight: 700;
}
.fcr-empty p { margin: 0; font-size: 13px; }

.notices { display: flex; flex-direction: column; gap: 4px; padding-left: 18px; }
.notice {
  font-size: 12px; color: var(--text-sub); line-height: 1.5;
  padding: 7px 10px; background: var(--gray-bg); border-radius: 6px;
  overflow-wrap: anywhere;
}

/* ── Reference Integrity cards (published-paper audit) ── */
.ref-integrity { margin-bottom: 16px; }
.ri-title { font-size: 11px; font-weight: 700; text-transform: uppercase; letter-spacing: 0.06em; color: var(--text-sub); margin-bottom: 8px; }
.ri-cards { display: grid; grid-template-columns: repeat(auto-fill, minmax(108px, 1fr)); gap: 8px; }
.ri-card { display: flex; flex-direction: column; gap: 2px; padding: 8px 10px; border: 1px solid var(--border); border-radius: 8px; background: var(--card); }
.ri-card.good { border-color: var(--good); }
.ri-card.warn { border-color: var(--warn); }
.ri-card.bad { border-color: var(--bad); }
.ri-n { font-size: 18px; font-weight: 700; color: var(--text); }
.ri-card.good .ri-n { color: var(--good); }
.ri-card.warn .ri-n { color: var(--warn); }
.ri-card.bad .ri-n { color: var(--bad); }
.ri-l { font-size: 10.5px; color: var(--text-sub); }

/* ── Citation Support Matrix ── */
.matrix-wrap { overflow-x: auto; }
.matrix {
  width: 100%; border-collapse: collapse; font-size: 12.5px;
  border: 1px solid var(--border); border-radius: 10px; overflow: hidden;
}
.matrix th {
  text-align: left; font-size: 10.5px; font-weight: 700; text-transform: uppercase;
  letter-spacing: 0.05em; color: var(--text-mute);
  padding: 10px 12px; background: var(--gray-bg); border-bottom: 1px solid var(--border);
}
.matrix td {
  padding: 10px 12px; border-bottom: 1px solid var(--border);
  color: var(--text); vertical-align: top; line-height: 1.4;
}
.matrix tbody tr:last-child td { border-bottom: none; }
.matrix td.mono { font-family: ui-monospace, 'SF Mono', Menlo, monospace; font-size: 11.5px; }
.matrix td.cit { font-weight: 700; white-space: nowrap; }
.matrix td.ref-cell { max-width: 360px; overflow-wrap: anywhere; }
.matrix .ref-title { font-weight: 600; }
.matrix .ref-doi { display: block; margin-top: 2px; font-family: ui-monospace, 'SF Mono', Menlo, monospace; font-size: 10.5px; color: var(--accent); text-decoration: none; }
.matrix .ref-doi:hover { text-decoration: underline; }
.matrix .snippet { display: block; margin-top: 4px; font-size: 11px; font-style: italic; color: var(--text-sub); line-height: 1.4; }
.matrix td.doi-cell { max-width: 220px; overflow-wrap: anywhere; }
.matrix td.doi-cell a { color: var(--accent); text-decoration: none; }
.matrix td.doi-cell a:hover { text-decoration: underline; }
.cell-sub { display: block; margin-top: 3px; font-size: 10.5px; font-weight: 600; text-transform: capitalize; }
.cell-sub.good { color: var(--good); }
.cell-sub.warn { color: var(--warn); }
.cell-sub.bad { color: var(--bad); }
.retracted {
  display: inline-block; margin-left: 6px; font-size: 9.5px; font-weight: 800;
  letter-spacing: 0.05em; color: var(--bad); background: var(--bad-bg);
  padding: 1px 6px; border-radius: 4px; vertical-align: middle;
}
.verdict-badge {
  font-size: 10.5px; font-weight: 700; text-transform: capitalize;
  padding: 3px 9px; border-radius: 999px; white-space: nowrap;
}
.verdict-badge.good { background: var(--good-bg); color: var(--good); }
.verdict-badge.bad { background: var(--bad-bg); color: var(--bad); }
.verdict-badge.warn { background: var(--warn-bg); color: var(--warn); }
.verdict-badge.gray { background: var(--gray-bg); color: var(--gray); }
.matrix-foot {
  margin: 12px 2px 0; font-size: 11.5px; font-style: italic; color: var(--text-mute); line-height: 1.5;
}

/* Internal consistency (additive section) */
.consistency-wrap { padding: 4px 2px; }
.ic-head { display: flex; align-items: flex-start; gap: 10px; margin-bottom: 14px; }
.ic-sub { margin: 2px 0 0; font-size: 12px; color: var(--text-sub); line-height: 1.5; }
.ic-card { border: 1px solid var(--border); border-left: 3px solid #d9534f; border-radius: 8px; padding: 12px 14px; margin-bottom: 10px; background: var(--surface, #fff); }
.ic-metric { display: flex; align-items: baseline; gap: 10px; flex-wrap: wrap; }
.ic-name { font-weight: 600; font-size: 13.5px; text-transform: capitalize; }
.ic-vs { font-size: 13px; color: var(--text-sub); }
.ic-vs b { color: #c0392b; }
.ic-note { margin: 6px 0 8px; font-size: 12.5px; color: var(--text); line-height: 1.5; }
.ic-snips { display: flex; flex-direction: column; gap: 4px; }
.ic-snip { margin: 0; font-size: 11.5px; font-style: italic; color: var(--text-sub); line-height: 1.45; }
</style>
