<script setup>
import { computed } from 'vue'

const props = defineProps({
  status: { type: String, required: true },      // none | pending | done | error | skipped
  result: { type: Object, default: null },
  canRerun: { type: Boolean, default: false },
})
const emit = defineEmits(['rerun'])

const cls = { valid: 'good', not_found: 'bad', invalid: 'bad', unreachable: 'warn', unverifiable: 'muted' }
const label = { valid: 'valid', not_found: 'not found', invalid: 'invalid', unreachable: 'unreachable', unverifiable: 'unverifiable' }
const identified = computed(() => (props.result?.references ?? []).filter((r) => r.kind !== 'author_year'))
const cites = computed(() => (props.result?.references ?? []).filter((r) => r.kind === 'author_year'))
const issues = computed(() => props.result ? props.result.summary.not_found + props.result.summary.invalid : 0)
</script>

<template>
  <section class="card">
    <h3>
      Citations &amp; links
      <span v-if="status === 'done' && result" class="pill" :class="issues ? 'bad' : 'good'">{{ issues ? `${issues} issue${issues === 1 ? '' : 's'}` : 'no issues' }}</span>
      <span v-else class="pill muted">{{ status === 'pending' ? 'checking…' : status }}</span>
      <button v-if="canRerun && status !== 'pending'" class="tiny" @click="emit('rerun')">Re-run</button>
    </h3>

    <p v-if="status === 'skipped'" class="muted small">Not enabled for this assignment.</p>
    <p v-else-if="status === 'error'" class="muted small">The check failed to run; try again.</p>
    <p v-else-if="status === 'pending'" class="muted small">Resolving DOIs against Crossref and checking links…</p>
    <template v-else-if="result">
      <p class="muted small summary">
        {{ result.summary.total }} references · {{ result.summary.valid }} valid · {{ result.summary.not_found }} not found ·
        {{ result.summary.invalid }} invalid · {{ result.summary.unreachable }} unreachable · {{ result.summary.unverifiable }} unverifiable
        <template v-if="result.has_reference_list"> · {{ result.summary.orphan_cites }} orphan cites · {{ result.summary.uncited_entries }} uncited entries</template>
      </p>
      <p v-if="!result.summary.total" class="muted small">No DOIs, links or author-year citations found in the text.</p>

      <ul v-if="identified.length" class="refs">
        <li v-for="r in identified" :key="r.raw">
          <span class="pill" :class="cls[r.status]">{{ label[r.status] }}</span>
          <div>
            <div class="mono raw">{{ r.kind === 'doi' ? 'doi:' : '' }}{{ r.raw }}</div>
            <div v-if="r.metadata?.title" class="meta"><b>{{ r.metadata.title }}</b><span class="muted"> — {{ r.metadata.authors?.slice(0, 2).join('; ') }}{{ r.metadata.authors?.length > 2 ? ' et al.' : '' }}<template v-if="r.metadata.year">, {{ r.metadata.year }}</template><template v-if="r.metadata.venue">, {{ r.metadata.venue }}</template></span></div>
            <div class="muted tiny">{{ r.detail }}</div>
            <div v-for="f in r.flags" :key="f" class="warn tiny">⚠ {{ f.replaceAll('_', ' ') }}</div>
          </div>
        </li>
      </ul>

      <details v-if="cites.length" class="cites">
        <summary class="muted small">{{ cites.length }} author-year citation{{ cites.length === 1 ? '' : 's' }} (not verifiable without an identifier)</summary>
        <ul class="refs">
          <li v-for="r in cites" :key="r.raw">
            <span class="pill" :class="r.flags.includes('orphan') ? 'warn' : 'muted'">{{ r.flags.includes('orphan') ? 'orphan' : 'cite' }}</span>
            <div><div>{{ r.raw }}</div><div class="muted tiny">{{ r.detail }}</div></div>
          </li>
        </ul>
      </details>
      <p class="muted tiny">“Unverifiable” means we could not check — never that a source is fabricated.</p>
    </template>
  </section>
</template>

<style scoped>
h3 { margin: 0 0 8px; font-size: 15px; display: flex; align-items: center; gap: 8px; }
.tiny.pill, .tiny { font-size: 11.5px; }
button.tiny { margin-left: auto; padding: 3px 8px; font-size: 12px; }
.small { font-size: 13px; }
.summary { margin: 0 0 10px; line-height: 1.5; }
.refs { list-style: none; padding: 0; margin: 0; display: grid; gap: 8px; }
.refs li { display: grid; grid-template-columns: auto 1fr; gap: 10px; align-items: start; font-size: 13px; }
.refs .pill { margin-top: 2px; }
.raw { word-break: break-all; }
.meta { margin-top: 2px; }
.cites { margin-top: 10px; } .cites summary { cursor: pointer; } .cites ul { margin-top: 8px; }
</style>
