<script setup>
const props = defineProps({
  status: { type: String, required: true },      // none | pending | done | error | skipped
  result: { type: Object, default: null },
  canRecompute: { type: Boolean, default: false },
})
const emit = defineEmits(['recompute'])
const cls = (score) => (score >= 40 ? 'bad' : score >= 15 ? 'warn' : 'good')
</script>

<template>
  <section class="card">
    <h3>
      Similarity in class
      <span v-if="status === 'done' && result" class="pill" :class="cls(result.max_score)">{{ result.max_score }}% max</span>
      <span v-else class="pill muted">{{ status === 'pending' ? 'comparing…' : status }}</span>
      <button v-if="canRecompute && status !== 'pending'" class="tiny" @click="emit('recompute')">Recompute class</button>
    </h3>

    <p v-if="status === 'skipped'" class="muted small">Not enabled for this assignment.</p>
    <p v-else-if="status === 'error'" class="muted small">The comparison failed to run; try recomputing.</p>
    <p v-else-if="status === 'pending'" class="muted small">Fingerprinting and comparing with other submissions…</p>
    <template v-else-if="result">
      <p class="muted small">
        Compared with {{ result.compared }} other submission{{ result.compared === 1 ? '' : 's' }} ·
        {{ result.params.k }}-word fingerprints, {{ result.params.prompt_grams_excluded }} prompt phrases excluded.
        Score = share of this text's fingerprints also found in the other text.
      </p>
      <p v-if="!result.matches.length" class="muted small">No overlapping passages with any classmate.</p>
      <ul class="matches">
        <li v-for="m in result.matches" :key="m.submission_id">
          <div class="row">
            <span class="pill" :class="cls(m.score)">{{ m.score }}%</span>
            <RouterLink :to="`/teacher/submissions/${m.submission_id}`"><b>{{ m.student_name }}</b></RouterLink>
            <span class="muted small">{{ m.shared_grams }} shared phrase{{ m.shared_grams === 1 ? '' : 's' }}</span>
          </div>
          <blockquote v-for="(s, i) in m.segments.slice(0, 3)" :key="i">“{{ s.text }}”</blockquote>
          <p v-if="m.segments.length > 3" class="muted tiny">+{{ m.segments.length - 3 }} more passage{{ m.segments.length - 3 === 1 ? '' : 's' }}</p>
        </li>
      </ul>
      <p class="muted tiny">Overlap is shown, not judged — shared quotes, prompts and common phrasing all look alike to a fingerprint.</p>
    </template>
  </section>
</template>

<style scoped>
h3 { margin: 0 0 8px; font-size: 15px; display: flex; align-items: center; gap: 8px; }
button.tiny { margin-left: auto; padding: 3px 8px; font-size: 12px; }
.small { font-size: 13px; } .tiny { font-size: 11.5px; }
.matches { list-style: none; padding: 0; margin: 8px 0 0; display: grid; gap: 12px; }
.row { display: flex; align-items: center; gap: 10px; }
blockquote { margin: 6px 0 0; padding: 6px 10px; border-left: 3px solid var(--warn); background: var(--surface-2); border-radius: 4px; font-size: 13px; line-height: 1.5; }
</style>
