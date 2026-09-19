<script setup>
import { onBeforeUnmount, ref } from 'vue'
import { PlaybackEngine, fmtClock } from '../lib/playback.js'

const props = defineProps({ payload: { type: Object, required: true } })
const engine = new PlaybackEngine(props.payload)
const st = engine.state
const bar = ref(null)
engine.seek(0)

function seekFromClick(e) {
  const r = bar.value.getBoundingClientRect()
  engine.pause()
  engine.seek(((e.clientX - r.left) / r.width) * engine.n)
}
const pct = (i) => `${(i / Math.max(1, engine.n)) * 100}%`
onBeforeUnmount(() => engine.destroy())
</script>

<template>
  <div class="pb">
    <div class="pb-head">
      <span class="pill good">⚡ exact replay · {{ engine.n }} events</span>
      <span class="muted small">
        {{ payload.summary.keystroke_events }} keystrokes · {{ payload.summary.paste_events }} pastes
        ({{ payload.summary.internal_paste_events }} internal) · {{ payload.summary.deletion_events }} deletions ·
        {{ payload.summary.pauses }} pauses · {{ fmtClock(payload.duration_ms) }} of writing
      </span>
      <span class="legend muted small"><i class="sw T"></i>typed <i class="sw INT"></i>internal paste <i class="sw EXT"></i>external</span>
    </div>

    <div class="doc">
      <template v-if="st.runs.length"><span v-for="(r, i) in st.runs" :key="i" :class="['run', r.origin]">{{ r.text }}</span></template>
      <span v-else class="muted">(empty document)</span><span class="caret" :class="{ on: st.playing }"></span>
    </div>

    <div ref="bar" class="timeline" @click="seekFromClick" title="Click to seek">
      <span v-for="(m, i) in st.markers" :key="i" :class="['mark', m.kind]" :style="{ left: pct(m.i) }"
            :title="m.kind === 'pause' ? `pause ${fmtClock(m.ms)}` : m.kind"></span>
      <span class="head" :style="{ left: pct(st.index) }"></span>
    </div>

    <div class="controls">
      <button @click="engine.toStart()" title="Start">⏮</button>
      <button class="primary" @click="st.playing ? engine.pause() : engine.play()">{{ st.playing ? 'Pause' : st.index >= engine.n ? 'Replay' : 'Play' }}</button>
      <button @click="engine.pause(); engine.step()" title="One event">›</button>
      <button @click="engine.nextMarker()" title="Jump to next paste / deletion / pause">⏭ marker</button>
      <button @click="engine.toEnd()" title="End">⏭</button>
      <label class="inline">Speed
        <select v-model.number="st.speed"><option v-for="s in [1, 2, 4, 8, 16]" :key="s" :value="s">{{ s }}×</option></select>
      </label>
      <label class="inline check"><input v-model="st.realtime" type="checkbox" /> real time <small class="muted">(pauses as they happened, capped at 30 s)</small></label>
      <span class="clock mono">{{ fmtClock(st.elapsedMs) }} / {{ fmtClock(st.durationMs) }} · event {{ st.index }}/{{ engine.n }}</span>
    </div>
  </div>
</template>

<style scoped>
.pb { display: grid; gap: 10px; }
.pb-head { display: flex; flex-wrap: wrap; gap: 10px 14px; align-items: center; }
.small { font-size: 12.5px; }
.legend { display: inline-flex; align-items: center; gap: 4px; margin-left: auto; }
.sw { display: inline-block; width: 10px; height: 10px; border-radius: 2px; margin: 0 2px 0 8px; }
.sw.T, .run.T { background: color-mix(in srgb, var(--good) 22%, transparent); }
.sw.INT, .run.INT { background: color-mix(in srgb, var(--accent) 28%, transparent); }
.sw.EXT, .run.EXT { background: color-mix(in srgb, var(--bad) 30%, transparent); }
.doc { background: var(--surface); border: 1px solid var(--border); border-radius: 8px; padding: 18px 20px; min-height: 240px; white-space: pre-wrap; line-height: 1.7; font-size: 15px; }
.run { border-radius: 2px; }
.caret { display: inline-block; width: 2px; height: 1.1em; background: var(--text); vertical-align: text-bottom; margin-left: 1px; opacity: 0.6; }
.caret.on { animation: blink 0.8s steps(1) infinite; }
@keyframes blink { 50% { opacity: 0; } }
.timeline { position: relative; height: 14px; background: var(--surface-2); border-radius: 7px; cursor: pointer; border: 1px solid var(--border); }
.mark { position: absolute; top: 2px; width: 3px; height: 8px; border-radius: 1px; transform: translateX(-50%); }
.mark.paste { background: var(--bad); } .mark.internal { background: var(--accent); } .mark.delete { background: var(--warn); }
.mark.pause { background: var(--muted); top: 9px; height: 4px; opacity: 0.6; }
.head { position: absolute; top: -3px; width: 3px; height: 18px; background: var(--text); border-radius: 2px; transform: translateX(-50%); }
.controls { display: flex; flex-wrap: wrap; align-items: center; gap: 8px; font-size: 13px; }
.inline { display: inline-flex; align-items: center; gap: 6px; color: var(--muted); }
.inline select { padding: 4px 6px; }
.check input { width: auto; }
.clock { margin-left: auto; color: var(--muted); }
</style>
