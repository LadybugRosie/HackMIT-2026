<template>
  <div class="draft-forensics">
    <!-- Loading -->
    <div v-if="loading" class="forensics-state">
      <div class="spinner"></div>
      <p>Analyzing writing process...</p>
    </div>

    <!-- Error -->
    <div v-else-if="error" class="forensics-state">
      <svg width="48" height="48" viewBox="0 0 24 24" fill="#9ca3af"><path d="M14 2H6c-1.1 0-2 .9-2 2v16c0 1.1.9 2 2 2h12c1.1 0 2-.9 2-2V8l-6-6zm-1 9V3.5L18.5 9H13zM12 17c-.55 0-1-.45-1-1s.45-1 1-1 1 .45 1 1-.45 1-1 1zm1-4h-2v-3h2v3z"/></svg>
      <p>{{ error }}</p>
    </div>

    <!-- Results -->
    <div v-else-if="data" class="forensics-results">
      <!-- Overall Verdict Banner -->
      <div class="overall-banner" :class="'verdict-' + data.overall_verdict">
        <div class="overall-left">
          <span class="overall-pill" :class="'pill-' + data.overall_verdict">
            {{ verdictLabel(data.overall_verdict) }}
          </span>
          <span class="overall-meta">
            {{ formatDuration(data.session_duration_ms) }} session
            · {{ data.snapshot_count }} snapshots
            <template v-if="data.prior_submissions_count > 0">
              · {{ data.prior_submissions_count }} prior submission(s) for baseline
            </template>
          </span>
        </div>
      </div>

      <!-- Teacher Override Banner (if teacher already reviewed) -->
      <div v-if="data.teacher_override" class="override-banner" :class="'override-' + data.teacher_override.verdict">
        <strong>Teacher Review:</strong>
        {{ data.teacher_override.verdict === 'cleared' ? 'Cleared — no concerns' :
           data.teacher_override.verdict === 'flagged' ? 'Flagged for follow-up' : 'Under review' }}
        <span v-if="data.teacher_override.notes" class="override-notes">— {{ data.teacher_override.notes }}</span>
      </div>

      <!-- Student Context (if student provided explanation) -->
      <div v-if="data.student_context" class="student-context-banner">
        <strong>Student explanation:</strong> "{{ data.student_context.text }}"
        <span class="context-date">{{ new Date(data.student_context.submitted_at).toLocaleDateString() }}</span>
      </div>

      <!-- Context Flags (auto-detected innocent explanations) -->
      <div v-if="activeContextFlags.length > 0" class="context-flags">
        <div v-for="ctx in activeContextFlags" :key="ctx.key" class="context-flag">
          <svg width="14" height="14" viewBox="0 0 24 24" fill="#6b7280"><path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm1 15h-2v-2h2v2zm0-4h-2V7h2v6z"/></svg>
          {{ ctx.label }}
        </div>
      </div>

      <!-- Disclaimer -->
      <div class="forensics-disclaimer">
        This analysis identifies unusual patterns but cannot determine intent. Multiple innocent explanations exist for each signal (e.g., outlining in advance, using grammar tools, switching devices, writing about a new topic). Use this as one input among many — not as evidence of misconduct.
      </div>

      <!-- Teacher Actions -->
      <div v-if="!data.teacher_override" class="teacher-actions">
        <button class="action-btn action-clear" @click="submitOverride('cleared')">
          Mark as Cleared
        </button>
        <button class="action-btn action-review" @click="submitOverride('review')">
          Keep Under Review
        </button>
        <button class="action-btn action-flag" @click="submitOverride('flagged')">
          Flag for Follow-up
        </button>
      </div>

      <!-- TIER 1: Process Signals -->
      <div class="tier-section">
        <h3 class="tier-title">Process Analysis</h3>
        <p class="tier-desc">How the document was composed — typing patterns, edit behavior, and document evolution.</p>

        <div class="signal-grid">
          <!-- Signal 1: Effort Ratio -->
          <SignalCard
            title="Writing Effort"
            :signal="data.tier1_process.effort_ratio"
            description="Ratio of total keystrokes to final document length. Genuine writing involves revision and produces 2-5x more keystrokes than the final text."
          >
            <template #viz>
              <div class="bar-viz" v-if="data.tier1_process.effort_ratio.ratio !== undefined">
                <div class="bar-track">
                  <div class="bar-fill" :class="'fill-' + data.tier1_process.effort_ratio.verdict"
                    :style="{ width: Math.min(100, data.tier1_process.effort_ratio.ratio / 5 * 100) + '%' }">
                  </div>
                  <div class="bar-markers">
                    <span class="bar-mark" style="left:20%">1x</span>
                    <span class="bar-mark" style="left:40%">2x</span>
                    <span class="bar-mark" style="left:60%">3x</span>
                    <span class="bar-mark" style="left:80%">4x</span>
                  </div>
                </div>
                <div class="bar-labels">
                  <span>Low effort</span>
                  <span class="bar-value">{{ data.tier1_process.effort_ratio.ratio }}x</span>
                  <span>High effort</span>
                </div>
              </div>
            </template>
          </SignalCard>

          <!-- Signal 2: Content Arrival -->
          <SignalCard
            title="Content Arrival"
            :signal="data.tier1_process.content_arrival"
            description="Words added per minute over the session. Red spikes indicate paste-speed content bursts above 80 WPM."
          >
            <template #viz>
              <AreaChart
                v-if="data.tier1_process.content_arrival.timeline?.length"
                :data="data.tier1_process.content_arrival.timeline"
              />
            </template>
          </SignalCard>

          <!-- Signal 3: Pause Patterns -->
          <SignalCard
            title="Thinking Pauses"
            :signal="data.tier1_process.pause_patterns"
            description="Distribution of pauses between edits. Real writers have 20-40% of pauses in the 3-8 second 'thinking' range."
          >
            <template #viz>
              <PauseBars
                v-if="data.tier1_process.pause_patterns.buckets"
                :buckets="data.tier1_process.pause_patterns.buckets"
              />
            </template>
          </SignalCard>

          <!-- Signal 4: Edit Direction -->
          <SignalCard
            title="Edit Direction"
            :signal="data.tier1_process.edit_direction"
            description="Forward vs backward edits. Genuine writers revisit earlier sections 25-50% of the time as their understanding evolves."
          >
            <template #viz>
              <DonutChart
                v-if="data.tier1_process.edit_direction.backward_ratio !== undefined"
                :ratio="data.tier1_process.edit_direction.backward_ratio"
                label="backward"
                :verdict="data.tier1_process.edit_direction.verdict"
              />
            </template>
          </SignalCard>

          <!-- Signal 5: Edit Depth -->
          <SignalCard
            title="Edit Depth"
            :signal="data.tier1_process.edit_depth"
            description="Types of edits made. Genuine writing includes surface (word swaps), structural (sentence changes), and semantic (new ideas)."
          >
            <template #viz>
              <StackedBars
                v-if="data.tier1_process.edit_depth.surface !== undefined"
                :surface="data.tier1_process.edit_depth.surface"
                :structural="data.tier1_process.edit_depth.structural"
                :semantic="data.tier1_process.edit_depth.semantic"
              />
            </template>
          </SignalCard>

          <!-- Signal 6: Structure Evolution -->
          <SignalCard
            title="Structure Evolution"
            :signal="data.tier1_process.structure_evolution"
            description="How the document's paragraph structure changed over time. Genuine writing starts fragmented and converges."
          >
            <template #viz>
              <Sparkline
                v-if="data.tier1_process.structure_evolution.timeline?.length"
                :data="data.tier1_process.structure_evolution.timeline"
                field="paras"
                label="paragraphs"
              />
            </template>
          </SignalCard>

          <!-- Signal 7b: Document Birth (bulk paste detection) -->
          <SignalCard
            v-if="data.tier1_process.document_birth"
            title="Bulk Insertions"
            :signal="data.tier1_process.document_birth"
            description="Detects when large blocks of text appeared instantly via paste. Small pastes of notes or draft restores are noted but not flagged."
          >
            <template #viz>
              <div v-if="data.tier1_process.document_birth.events?.length" class="bulk-events">
                <div v-for="(ev, i) in data.tier1_process.document_birth.events" :key="i" class="bulk-event">
                  <span class="bulk-words">+{{ ev.words_added }} words</span>
                  <span class="bulk-time">in {{ ev.time_gap_s }}s</span>
                  <span class="bulk-pos">at {{ ev.at_pct }}% through session</span>
                </div>
              </div>
            </template>
          </SignalCard>

          <!-- Signal 7c: Delete-Then-Paste (session manipulation) -->
          <SignalCard
            v-if="data.tier1_process.delete_then_paste"
            title="Session Integrity"
            :signal="data.tier1_process.delete_then_paste"
            description="Checks for manipulation patterns where content is deleted and replaced via paste — a technique to inflate typing statistics."
          />
        </div>
      </div>

      <!-- TIER 2: Baseline Signals -->
      <div class="tier-section">
        <h3 class="tier-title">Baseline Comparison</h3>
        <p class="tier-desc">Compared against this student's prior writing sessions and submissions.</p>

        <div class="signal-grid">
          <!-- Signal 7: Cognitive Rhythm -->
          <SignalCard
            title="Cognitive Rhythm"
            :signal="data.tier2_baseline.cognitive_rhythm"
            description="Compares this session's typing rhythm (pause durations, burst patterns, speed) against the student's established pattern."
          >
            <template #viz>
              <div class="bar-viz" v-if="data.tier2_baseline.cognitive_rhythm.similarity !== undefined">
                <div class="bar-track">
                  <div class="bar-fill" :class="'fill-' + data.tier2_baseline.cognitive_rhythm.verdict"
                    :style="{ width: (data.tier2_baseline.cognitive_rhythm.similarity * 100) + '%' }">
                  </div>
                </div>
                <div class="bar-labels">
                  <span>No match</span>
                  <span class="bar-value">{{ Math.round(data.tier2_baseline.cognitive_rhythm.similarity * 100) }}% match</span>
                  <span>Perfect match</span>
                </div>
              </div>
            </template>
          </SignalCard>

          <!-- Signal 8: Vocabulary Drift -->
          <SignalCard
            title="Vocabulary Profile"
            :signal="data.tier2_baseline.vocabulary_drift"
            description="Checks for sudden appearance of words never used in prior submissions. AI text often introduces vocabulary the student has never demonstrated."
          >
            <template #viz>
              <div class="metrics-row" v-if="data.tier2_baseline.vocabulary_drift.richness !== undefined">
                <div class="metric-box">
                  <div class="metric-val">{{ data.tier2_baseline.vocabulary_drift.novel_words }}</div>
                  <div class="metric-label">New words</div>
                  <div class="metric-sub">{{ Math.round((data.tier2_baseline.vocabulary_drift.novel_pct || 0) * 100) }}% of vocabulary</div>
                </div>
                <div class="metric-box">
                  <div class="metric-val">{{ data.tier2_baseline.vocabulary_drift.richness }}</div>
                  <div class="metric-label">Vocab richness</div>
                  <div class="metric-sub" v-if="data.tier2_baseline.vocabulary_drift.baseline_richness">avg: {{ data.tier2_baseline.vocabulary_drift.baseline_richness }}</div>
                </div>
                <div class="metric-box">
                  <div class="metric-val">{{ data.tier2_baseline.vocabulary_drift.avg_sentence_len }}</div>
                  <div class="metric-label">Avg sentence</div>
                  <div class="metric-sub" v-if="data.tier2_baseline.vocabulary_drift.baseline_avg_sentence_len">avg: {{ data.tier2_baseline.vocabulary_drift.baseline_avg_sentence_len }} words</div>
                </div>
              </div>
            </template>
          </SignalCard>
        </div>
      </div>

      <!-- TIER 3: Linguistic Signal -->
      <div class="tier-section">
        <h3 class="tier-title">Linguistic Fingerprint</h3>
        <p class="tier-desc">Analyzes characteristic writing errors and patterns unique to this student.</p>

        <div class="signal-grid">
          <!-- Signal 9: Error DNA -->
          <SignalCard
            title="Error DNA"
            :signal="data.tier3_linguistic.error_dna"
            description="Every writer has characteristic mistakes. AI-generated or ghostwritten text is suspiciously clean — lacking the student's usual error patterns."
          >
            <template #viz>
              <div class="error-dna-viz" v-if="data.tier3_linguistic.error_dna.current_rate !== undefined">
                <div class="error-comparison">
                  <div class="error-col">
                    <div class="error-rate" :class="'rate-' + data.tier3_linguistic.error_dna.verdict">
                      {{ data.tier3_linguistic.error_dna.current_rate }}
                    </div>
                    <div class="error-label">This submission<br><small>errors per 500 words</small></div>
                  </div>
                  <div class="error-vs">vs</div>
                  <div class="error-col">
                    <div class="error-rate rate-baseline">
                      {{ data.tier3_linguistic.error_dna.baseline_rate || '—' }}
                    </div>
                    <div class="error-label">Student average<br><small>errors per 500 words</small></div>
                  </div>
                </div>
              </div>
            </template>
          </SignalCard>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import axios from 'axios'
import { getApiUrl } from '@/utils/api-url'

// ─── Sub-components (inline) ────────────────────────────────────────────

const SignalCard = {
  props: { title: String, signal: Object, description: String },
  template: `
    <div class="signal-card" :class="signal?.verdict ? 'has-verdict-' + signal.verdict : ''">
      <div class="signal-header">
        <h4 class="signal-title">{{ title }}</h4>
        <span v-if="signal?.verdict && signal.verdict !== 'insufficient_data' && signal.verdict !== 'no_baseline' && signal.verdict !== 'error'"
          class="verdict-pill" :class="'pill-' + signal.verdict">
          {{ signal.verdict === 'genuine' ? 'Typical' : signal.verdict === 'review' ? 'Review' : 'Unusual' }}
        </span>
        <span v-else-if="signal?.verdict === 'no_baseline'" class="verdict-pill pill-neutral">No Baseline</span>
        <span v-else-if="signal?.verdict === 'insufficient_data'" class="verdict-pill pill-neutral">Limited Data</span>
      </div>
      <p class="signal-label">{{ signal?.label || '' }}</p>
      <div class="signal-viz" v-if="signal?.verdict !== 'insufficient_data' && signal?.verdict !== 'error'">
        <slot name="viz" />
      </div>
      <details class="signal-details" v-if="signal?.verdict !== 'insufficient_data'">
        <summary>About this signal</summary>
        <p>{{ description }}</p>
      </details>
    </div>
  `
}

const AreaChart = {
  props: { data: Array },
  computed: {
    svgPath() {
      if (!this.data?.length) return ''
      const w = 560, h = 140, pad = 4
      const maxWpm = Math.max(10, ...this.data.map(d => d.wpm))
      const points = this.data.map((d, i) => ({
        x: pad + (i / Math.max(1, this.data.length - 1)) * (w - pad * 2),
        y: h - pad - (d.wpm / maxWpm) * (h - pad * 2),
        spike: d.spike,
      }))
      // Area path
      let path = `M${points[0].x},${h - pad}`
      for (const p of points) path += ` L${p.x},${p.y}`
      path += ` L${points[points.length - 1].x},${h - pad} Z`
      return path
    },
    spikeRects() {
      if (!this.data?.length) return []
      const w = 560, h = 140, pad = 4
      const rects = []
      const barW = (w - pad * 2) / this.data.length
      this.data.forEach((d, i) => {
        if (d.spike) {
          rects.push({ x: pad + i * barW, y: 0, width: barW, height: h })
        }
      })
      return rects
    }
  },
  template: `
    <svg class="area-chart" viewBox="0 0 560 140" preserveAspectRatio="none">
      <rect v-for="(r, i) in spikeRects" :key="'s'+i" :x="r.x" :y="r.y" :width="r.width" :height="r.height" fill="rgba(239,68,68,0.1)" />
      <path :d="svgPath" fill="rgba(59,130,246,0.15)" stroke="#3b82f6" stroke-width="2" />
    </svg>
  `
}

const PauseBars = {
  props: { buckets: Object },
  computed: {
    bars() {
      if (!this.buckets) return []
      const labels = { under_1s: '<1s', '1_3s': '1-3s', '3_8s': '3-8s', '8_30s': '8-30s', over_30s: '>30s' }
      const colors = { under_1s: '#94a3b8', '1_3s': '#60a5fa', '3_8s': '#34d399', '8_30s': '#fbbf24', over_30s: '#f87171' }
      const max = Math.max(1, ...Object.values(this.buckets))
      return Object.entries(labels).map(([key, label]) => ({
        label, value: this.buckets[key] || 0,
        pct: ((this.buckets[key] || 0) / max) * 100,
        color: colors[key],
        isThinking: key === '3_8s',
      }))
    }
  },
  template: `
    <div class="pause-bars">
      <div v-for="b in bars" :key="b.label" class="pause-row" :class="{ thinking: b.isThinking }">
        <span class="pause-label">{{ b.label }}</span>
        <div class="pause-track">
          <div class="pause-fill" :style="{ width: b.pct + '%', background: b.color }"></div>
        </div>
        <span class="pause-count">{{ b.value }}</span>
      </div>
    </div>
  `
}

const DonutChart = {
  props: { ratio: Number, label: String, verdict: String },
  computed: {
    dashArray() {
      const pct = Math.max(0, Math.min(1, this.ratio))
      const circ = 2 * Math.PI * 40
      return `${pct * circ} ${circ}`
    },
    dashArrayBg() {
      return `${2 * Math.PI * 40} 0`
    },
    pctText() {
      return Math.round(this.ratio * 100) + '%'
    }
  },
  template: `
    <div class="donut-container">
      <svg viewBox="0 0 100 100" class="donut-svg">
        <circle cx="50" cy="50" r="40" fill="none" stroke="#e5e7eb" stroke-width="8" />
        <circle cx="50" cy="50" r="40" fill="none"
          :stroke="verdict === 'genuine' ? '#34d399' : verdict === 'suspicious' ? '#f87171' : '#fbbf24'"
          stroke-width="8" stroke-linecap="round"
          :stroke-dasharray="dashArray"
          transform="rotate(-90 50 50)" />
      </svg>
      <div class="donut-center">
        <span class="donut-pct">{{ pctText }}</span>
        <span class="donut-label">{{ label }}</span>
      </div>
    </div>
  `
}

const StackedBars = {
  props: { surface: Number, structural: Number, semantic: Number },
  computed: {
    total() { return (this.surface || 0) + (this.structural || 0) + (this.semantic || 0) },
    pcts() {
      const t = this.total || 1
      return {
        surface: Math.round(this.surface / t * 100),
        structural: Math.round(this.structural / t * 100),
        semantic: Math.round(this.semantic / t * 100),
      }
    }
  },
  template: `
    <div class="stacked-bars">
      <div class="stacked-track">
        <div class="stacked-seg seg-surface" :style="{ width: pcts.surface + '%' }"></div>
        <div class="stacked-seg seg-structural" :style="{ width: pcts.structural + '%' }"></div>
        <div class="stacked-seg seg-semantic" :style="{ width: pcts.semantic + '%' }"></div>
      </div>
      <div class="stacked-legend">
        <span class="leg-item"><span class="leg-dot dot-surface"></span>Surface {{ pcts.surface }}%</span>
        <span class="leg-item"><span class="leg-dot dot-structural"></span>Structural {{ pcts.structural }}%</span>
        <span class="leg-item"><span class="leg-dot dot-semantic"></span>Semantic {{ pcts.semantic }}%</span>
      </div>
    </div>
  `
}

const Sparkline = {
  props: { data: Array, field: String, label: String },
  computed: {
    pathD() {
      if (!this.data?.length) return ''
      const vals = this.data.map(d => d[this.field] || 0)
      const max = Math.max(1, ...vals)
      const w = 560, h = 60, pad = 2
      return vals.map((v, i) => {
        const x = pad + (i / Math.max(1, vals.length - 1)) * (w - pad * 2)
        const y = h - pad - (v / max) * (h - pad * 2)
        return (i === 0 ? 'M' : 'L') + `${x},${y}`
      }).join(' ')
    }
  },
  template: `
    <svg class="sparkline" viewBox="0 0 560 60" preserveAspectRatio="none">
      <path :d="pathD" fill="none" stroke="#3b82f6" stroke-width="2" />
    </svg>
  `
}

// ─── Main component ─────────────────────────────────────────────────────

const props = defineProps({ submissionId: { type: String, required: true } })

const API = getApiUrl()
const loading = ref(true)
const error = ref(null)
const data = ref(null)

const activeContextFlags = computed(() => {
  if (!data.value?.context_flags) return []
  return Object.entries(data.value.context_flags)
    .filter(([, ctx]) => ctx && ctx.detected)
    .map(([key, ctx]) => ({ key, ...ctx }))
})

function verdictLabel(v) {
  if (v === 'genuine') return 'Writing patterns consistent with typical composition'
  if (v === 'suspicious') return 'Unusual patterns detected — review recommended'
  if (v === 'review') return 'Some patterns warrant closer examination'
  return 'Insufficient data for analysis'
}

function formatDuration(ms) {
  if (!ms) return '0m'
  const m = Math.floor(ms / 60000)
  if (m >= 60) return `${Math.floor(m / 60)}h ${m % 60}m`
  return `${m}m`
}

async function submitOverride(verdict) {
  const notes = prompt(`Optional notes for "${verdict}" decision:`) || ''
  try {
    await axios.post(`${API}/api/session-playback/${props.submissionId}/forensics/teacher-override`, {
      verdict, notes
    })
    // Refresh data to show the override
    const res = await axios.get(`${API}/api/session-playback/${props.submissionId}/forensics`)
    data.value = res.data
  } catch (e) {
    alert('Failed to save override: ' + (e.response?.data?.detail || e.message))
  }
}

onMounted(async () => {
  try {
    const res = await axios.get(`${API}/api/session-playback/${props.submissionId}/forensics`)
    data.value = res.data
  } catch (e) {
    error.value = e.response?.status === 404
      ? 'No playback data available for this submission.'
      : 'Failed to load writing process analysis.'
  } finally {
    loading.value = false
  }
})
</script>

<style scoped>
.draft-forensics { padding: 16px 0; }

/* States */
.forensics-state { text-align: center; padding: 60px 20px; color: #6b7280; }
.forensics-state p { margin-top: 12px; font-size: 15px; }
.spinner { width: 32px; height: 32px; border: 3px solid #e5e7eb; border-top-color: #3b82f6; border-radius: 50%; animation: spin 0.8s linear infinite; margin: 0 auto; }
@keyframes spin { to { transform: rotate(360deg); } }

/* Overall Banner */
.overall-banner { padding: 16px 20px; border-radius: 12px; margin-bottom: 20px; display: flex; align-items: center; justify-content: space-between; }
.verdict-genuine { background: #ecfdf5; border: 1px solid #a7f3d0; }
.verdict-suspicious { background: #fef2f2; border: 1px solid #fecaca; }
.verdict-review { background: #fffbeb; border: 1px solid #fde68a; }
.verdict-insufficient_data { background: #f9fafb; border: 1px solid #e5e7eb; }
.overall-left { display: flex; align-items: center; gap: 12px; flex-wrap: wrap; }
.overall-pill { padding: 6px 16px; border-radius: 20px; font-weight: 600; font-size: 14px; }
.pill-genuine { background: #d1fae5; color: #065f46; }
.pill-suspicious { background: #fee2e2; color: #991b1b; }
.pill-review { background: #fef3c7; color: #92400e; }
.pill-neutral { background: #f3f4f6; color: #6b7280; }
.overall-meta { font-size: 13px; color: #6b7280; }

/* Override banner */
.override-banner { padding: 12px 16px; border-radius: 10px; margin-bottom: 12px; font-size: 13px; }
.override-cleared { background: #ecfdf5; border: 1px solid #a7f3d0; color: #065f46; }
.override-flagged { background: #fef2f2; border: 1px solid #fecaca; color: #991b1b; }
.override-review { background: #fffbeb; border: 1px solid #fde68a; color: #92400e; }
.override-notes { font-style: italic; opacity: 0.8; }

/* Student context */
.student-context-banner { padding: 12px 16px; background: #f0fdf4; border: 1px solid #bbf7d0; border-radius: 10px; margin-bottom: 12px; font-size: 13px; color: #166534; }
.context-date { font-size: 11px; color: #9ca3af; margin-left: 8px; }

/* Context flags */
.context-flags { display: flex; flex-wrap: wrap; gap: 8px; margin-bottom: 12px; }
.context-flag { display: flex; align-items: center; gap: 6px; padding: 6px 12px; background: #f9fafb; border: 1px solid #e5e7eb; border-radius: 8px; font-size: 12px; color: #6b7280; }

/* Teacher actions */
.teacher-actions { display: flex; gap: 8px; margin-bottom: 16px; }
.action-btn { padding: 8px 16px; border-radius: 8px; font-size: 13px; font-weight: 500; cursor: pointer; border: 1px solid; transition: all 0.2s; }
.action-clear { background: #ecfdf5; border-color: #a7f3d0; color: #065f46; }
.action-clear:hover { background: #d1fae5; }
.action-review { background: #fffbeb; border-color: #fde68a; color: #92400e; }
.action-review:hover { background: #fef3c7; }
.action-flag { background: #fef2f2; border-color: #fecaca; color: #991b1b; }
.action-flag:hover { background: #fee2e2; }

/* Disclaimer */
.forensics-disclaimer { padding: 12px 16px; background: #f0f4ff; border: 1px solid #dbeafe; border-radius: 8px; font-size: 12px; color: #4b5563; line-height: 1.6; margin-bottom: 16px; }

/* Tier sections */
.tier-section { margin-bottom: 28px; }
.tier-title { margin: 0 0 4px; font-size: 16px; font-weight: 600; color: #1f2937; }
.tier-desc { margin: 0 0 14px; font-size: 13px; color: #9ca3af; }

/* Signal grid */
.signal-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(320px, 1fr)); gap: 12px; }

/* Signal card */
.signal-card { background: #fff; border: 1px solid #e5e7eb; border-radius: 10px; padding: 16px; }
.signal-card.has-verdict-genuine { border-left: 3px solid #34d399; }
.signal-card.has-verdict-suspicious { border-left: 3px solid #f87171; }
.signal-card.has-verdict-review { border-left: 3px solid #fbbf24; }
.signal-header { display: flex; align-items: center; justify-content: space-between; margin-bottom: 6px; }
.signal-title { margin: 0; font-size: 14px; font-weight: 600; color: #374151; }
.verdict-pill { padding: 3px 10px; border-radius: 12px; font-size: 11px; font-weight: 600; }
.signal-label { margin: 0 0 12px; font-size: 13px; color: #6b7280; line-height: 1.5; }
.signal-viz { margin-bottom: 8px; }
.signal-details { font-size: 12px; color: #9ca3af; }
.signal-details summary { cursor: pointer; user-select: none; }
.signal-details p { margin: 6px 0 0; line-height: 1.5; }

/* Bar visualization */
.bar-viz { margin-top: 4px; }
.bar-track { position: relative; height: 10px; background: #f3f4f6; border-radius: 5px; overflow: visible; }
.bar-fill { height: 100%; border-radius: 5px; transition: width 0.6s ease; }
.fill-genuine { background: linear-gradient(90deg, #6ee7b7, #34d399); }
.fill-suspicious { background: linear-gradient(90deg, #fca5a5, #f87171); }
.fill-review { background: linear-gradient(90deg, #fde68a, #fbbf24); }
.fill-no_baseline, .fill-insufficient_data, .fill-neutral { background: #d1d5db; }
.bar-markers { position: absolute; top: 0; left: 0; right: 0; height: 100%; }
.bar-mark { position: absolute; top: -16px; font-size: 10px; color: #d1d5db; transform: translateX(-50%); }
.bar-labels { display: flex; justify-content: space-between; margin-top: 6px; font-size: 11px; color: #9ca3af; }
.bar-value { font-weight: 600; color: #374151; }

/* Area chart */
.area-chart { width: 100%; height: 140px; border-radius: 6px; background: #fafafa; }

/* Pause bars */
.pause-bars { display: flex; flex-direction: column; gap: 5px; }
.pause-row { display: flex; align-items: center; gap: 8px; }
.pause-row.thinking { font-weight: 600; }
.pause-label { width: 36px; font-size: 11px; color: #6b7280; text-align: right; }
.pause-track { flex: 1; height: 8px; background: #f3f4f6; border-radius: 4px; overflow: hidden; }
.pause-fill { height: 100%; border-radius: 4px; transition: width 0.5s ease; }
.pause-count { width: 30px; font-size: 11px; color: #9ca3af; }

/* Donut chart */
.donut-container { position: relative; width: 100px; height: 100px; margin: 0 auto; }
.donut-svg { width: 100%; height: 100%; }
.donut-center { position: absolute; inset: 0; display: flex; flex-direction: column; align-items: center; justify-content: center; }
.donut-pct { font-size: 18px; font-weight: 700; color: #1f2937; }
.donut-label { font-size: 10px; color: #9ca3af; }

/* Stacked bars */
.stacked-track { display: flex; height: 12px; border-radius: 6px; overflow: hidden; background: #f3f4f6; }
.stacked-seg { transition: width 0.5s ease; }
.seg-surface { background: #94a3b8; }
.seg-structural { background: #3b82f6; }
.seg-semantic { background: #22c55e; }
.stacked-legend { display: flex; gap: 14px; margin-top: 8px; font-size: 11px; color: #6b7280; }
.leg-item { display: flex; align-items: center; gap: 4px; }
.leg-dot { width: 8px; height: 8px; border-radius: 2px; display: inline-block; }
.dot-surface { background: #94a3b8; }
.dot-structural { background: #3b82f6; }
.dot-semantic { background: #22c55e; }

/* Sparkline */
.sparkline { width: 100%; height: 60px; border-radius: 6px; background: #fafafa; }

/* Metrics row */
.metrics-row { display: flex; gap: 10px; }
.metric-box { flex: 1; text-align: center; padding: 10px 8px; background: #f9fafb; border-radius: 8px; }
.metric-val { font-size: 20px; font-weight: 700; color: #1f2937; }
.metric-label { font-size: 11px; color: #6b7280; margin-top: 2px; }
.metric-sub { font-size: 10px; color: #d1d5db; margin-top: 2px; }

/* Error DNA */
.error-comparison { display: flex; align-items: center; gap: 16px; justify-content: center; }
.error-col { text-align: center; }
.error-rate { font-size: 28px; font-weight: 700; }
.rate-genuine { color: #059669; }
.rate-suspicious { color: #dc2626; }
.rate-review { color: #d97706; }
.rate-baseline { color: #6b7280; }
.error-vs { font-size: 14px; color: #d1d5db; font-weight: 500; }
.error-label { font-size: 12px; color: #6b7280; margin-top: 4px; }
.error-label small { font-size: 10px; color: #d1d5db; }

/* Bulk events */
.bulk-events { display: flex; flex-direction: column; gap: 6px; }
.bulk-event { display: flex; gap: 10px; font-size: 12px; padding: 6px 10px; background: #fef2f2; border-radius: 6px; color: #991b1b; }
.bulk-words { font-weight: 600; }
.bulk-time { color: #dc2626; }
.bulk-pos { color: #9ca3af; margin-left: auto; }

@media (max-width: 700px) {
  .signal-grid { grid-template-columns: 1fr; }
  .metrics-row { flex-direction: column; }
}
</style>
