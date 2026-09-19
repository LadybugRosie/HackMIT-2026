<script setup>
import { computed } from 'vue'

const props = defineProps({ integrity: { type: Object, required: true } })

const pct = (x) => `${Math.round(x * 100)}%`
const verdictCls = { genuine: 'good', review: 'warn', suspicious: 'bad', insufficient_data: 'muted' }
const cadence = computed(() => props.integrity.signals.find((s) => s.name === 'transcription_cadence'))
const needle = computed(() => {
  const r = cadence.value?.data?.boundary_ratio
  return r === undefined ? null : Math.round(r * 100)
})
</script>

<template>
  <section class="integrity">
    <h3>
      Process
      <span class="pill" :class="verdictCls[integrity.verdict]">{{ integrity.verdict.replace('_', ' ') }}</span>
      <small class="muted">{{ integrity.coverage.measured_signals }}/{{ integrity.coverage.total_signals }} signals measured</small>
    </h3>

    <div class="scores">
      <div><span class="big">{{ integrity.scores.trust }}</span><span class="muted"> trust</span></div>
      <div><span class="big">{{ integrity.scores.composition }}</span><span class="muted"> typed</span></div>
    </div>

    <div class="mixbar" :title="`typed ${pct(integrity.mix.typed)} · internal ${pct(integrity.mix.internal)} · external ${pct(integrity.mix.external)}`">
      <span class="t" :style="{ width: pct(integrity.mix.typed) }"></span>
      <span class="i" :style="{ width: pct(integrity.mix.internal) }"></span>
      <span class="e" :style="{ width: pct(integrity.mix.external) }"></span>
    </div>
    <div class="legend muted">
      <span><i class="sw t"></i>typed {{ pct(integrity.mix.typed) }}</span>
      <span><i class="sw i"></i>internal {{ pct(integrity.mix.internal) }}</span>
      <span><i class="sw e"></i>external {{ pct(integrity.mix.external) }}</span>
    </div>

    <div class="meter" v-if="cadence">
      <div class="meter-labels muted"><span>transcribing</span><span>composing</span></div>
      <div class="track" :class="{ idle: needle === null }">
        <span v-if="needle !== null" class="needle" :style="{ left: `${needle}%` }"></span>
      </div>
      <div class="tiny muted">
        {{ needle !== null ? `${needle}% of pauses at word/clause boundaries` : cadence.label }}
      </div>
    </div>

    <ul class="signals">
      <li v-for="s in integrity.signals" :key="s.name" :class="verdictCls[s.verdict]">
        <span class="dot"></span>
        <div>
          <div class="name">{{ s.name.replaceAll('_', ' ') }} <small class="muted">{{ s.verdict.replace('_', ' ') }}</small></div>
          <div class="label muted">{{ s.label }}</div>
        </div>
      </li>
    </ul>

    <ul v-if="integrity.warnings.length" class="warnings">
      <li v-for="w in integrity.warnings" :key="w.code" :class="w.severity">
        <b>{{ w.severity }}</b> {{ w.reason }}
      </li>
    </ul>
  </section>
</template>

<style scoped>
.integrity { border-top: 1px solid var(--border); margin-top: 14px; padding-top: 14px; }
h3 { margin: 0 0 10px; font-size: 15px; display: flex; align-items: center; gap: 8px; flex-wrap: wrap; }
h3 small { font-weight: 400; font-size: 11px; margin-left: auto; }
.pill { font-size: 11px; padding: 2px 8px; border-radius: 999px; border: 1px solid currentColor; font-weight: 600; text-transform: capitalize; }
.good { color: var(--good); } .bad { color: var(--bad); } .warn { color: var(--warn); } .muted { color: var(--muted); }
.scores { display: flex; gap: 18px; margin-bottom: 8px; }
.big { font-size: 22px; font-weight: 600; }
.mixbar { display: flex; height: 10px; border-radius: 5px; overflow: hidden; background: var(--surface-2); }
.mixbar span { display: block; height: 100%; }
.t, .sw.t { background: var(--good); } .i, .sw.i { background: var(--accent); } .e, .sw.e { background: var(--bad); }
.legend { display: flex; gap: 12px; font-size: 11px; margin: 6px 0 12px; }
.sw { display: inline-block; width: 8px; height: 8px; border-radius: 2px; margin-right: 4px; }
.meter { margin: 6px 0 12px; }
.meter-labels { display: flex; justify-content: space-between; font-size: 11px; }
.track { position: relative; height: 8px; border-radius: 4px; background: linear-gradient(90deg, var(--bad), var(--warn) 45%, var(--good)); margin: 4px 0; }
.track.idle { opacity: 0.35; }
.needle { position: absolute; top: -4px; width: 3px; height: 16px; background: var(--text); border-radius: 2px; transform: translateX(-50%); }
.tiny { font-size: 11px; }
.signals { list-style: none; padding: 0; margin: 0; display: grid; gap: 8px; }
.signals li { display: flex; gap: 8px; align-items: flex-start; }
.dot { width: 8px; height: 8px; border-radius: 50%; background: currentColor; margin-top: 5px; flex: none; }
.name { font-weight: 600; text-transform: capitalize; color: var(--text); }
.label { font-size: 12px; }
.warnings { list-style: none; padding: 0; margin: 12px 0 0; display: grid; gap: 6px; font-size: 12.5px; }
.warnings li { padding: 6px 8px; border-radius: 6px; background: var(--surface-2); border-left: 3px solid var(--warn); }
.warnings li.high { border-left-color: var(--bad); } .warnings li.low { border-left-color: var(--muted); }
.warnings b { text-transform: uppercase; font-size: 10px; margin-right: 6px; }
</style>
