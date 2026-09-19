<template>
  <transition name="ob-fade">
    <div v-if="visible" class="ob-overlay" @click.self="finish">
      <div class="ob-card">
        <button class="ob-skip" @click="finish">Skip</button>

        <div class="ob-stage">
          <transition :name="dir" mode="out-in">
            <div :key="step" class="ob-slide">
              <div class="ob-icon" :style="{ background: cards[step].grad }">{{ cards[step].icon }}</div>
              <div class="ob-kicker">{{ step + 1 }} / {{ cards.length }}</div>
              <h2 class="ob-title">{{ cards[step].title }}</h2>
              <p class="ob-body">{{ cards[step].body }}</p>
            </div>
          </transition>
        </div>

        <div class="ob-dots">
          <button
            v-for="(c, i) in cards" :key="i"
            class="ob-dot" :class="{ active: i === step, done: i < step }"
            :aria-label="`Go to step ${i + 1}`"
            @click="goTo(i)"
          ></button>
        </div>

        <div class="ob-actions">
          <button v-if="step > 0" class="ob-btn ghost" @click="prev">Back</button>
          <span v-else class="ob-spacer"></span>
          <button class="ob-btn primary" @click="next">
            {{ step === cards.length - 1 ? 'Get started →' : 'Next' }}
          </button>
        </div>
      </div>
    </div>
  </transition>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { useAuth } from '@/composables/auth'

const emit = defineEmits(['done'])
const { user } = useAuth()

const cards = [
  {
    icon: '🛡', grad: 'linear-gradient(135deg,#7c3aed,#a855f7)',
    title: 'Welcome to Editorrah',
    body: 'Editorrah proves who actually wrote your paper. Every writing session is recorded and verified against your own writing style — authorship you can demonstrate, not just claim.',
  },
  {
    icon: '✍️', grad: 'linear-gradient(135deg,#2563eb,#3b82f6)',
    title: 'First, teach us your style',
    body: 'Answer a few short prompts about your topic. We build a private stylometric profile — your authorship fingerprint — so we can tell your writing apart from anyone else’s, or an AI’s.',
  },
  {
    icon: '⌨️', grad: 'linear-gradient(135deg,#0891b2,#06b6d4)',
    title: 'Just write — we record the proof',
    body: 'Work in the editor exactly as you normally would. Editorrah captures the session keystroke-by-keystroke with full transparency: what was typed, pasted, and deleted, byte by byte.',
  },
  {
    icon: '👥', grad: 'linear-gradient(135deg,#059669,#10b981)',
    title: 'Co-author, judged separately',
    body: 'Invite collaborators with a link or from your lab. Everyone writes in one shared document — and each person is verified against their own style, so credit is never blurred.',
  },
  {
    icon: '📊', grad: 'linear-gradient(135deg,#d97706,#f59e0b)',
    title: 'See exactly who wrote what',
    body: 'A live contribution meter and a color-coded “Who Wrote What” show each author’s share — by words and by writing effort — passage by passage.',
  },
  {
    icon: '📤', grad: 'linear-gradient(135deg,#db2777,#ec4899)',
    title: 'Share proof, not promises',
    body: 'Every report gives you a session-replay video, the original PDF, and a shareable integrity report with per-author stylometry — all behind one public link.',
  },
]

const visible = ref(false)
const step = ref(0)
const dir = ref('ob-slide-next')

function storageKey() {
  return `editorrah_researcher_onboarding_${user.value?.user_id || 'anon'}`
}

function goTo(i) {
  dir.value = i > step.value ? 'ob-slide-next' : 'ob-slide-prev'
  step.value = i
}
function next() {
  if (step.value < cards.length - 1) {
    dir.value = 'ob-slide-next'
    step.value++
  } else {
    finish()
  }
}
function prev() {
  if (step.value > 0) {
    dir.value = 'ob-slide-prev'
    step.value--
  }
}
function finish() {
  try { localStorage.setItem(storageKey(), '1') } catch { /* ignore */ }
  visible.value = false
  emit('done')
}

onMounted(() => {
  let seen = false
  try { seen = localStorage.getItem(storageKey()) === '1' } catch { /* ignore */ }
  if (!seen) visible.value = true
})
</script>

<style scoped>
.ob-overlay {
  position: fixed; inset: 0; z-index: 1000;
  display: flex; align-items: center; justify-content: center; padding: 24px;
  background: rgba(23, 16, 48, 0.55); backdrop-filter: blur(6px);
}
.ob-card {
  position: relative; width: 100%; max-width: 460px; background: #fff;
  border-radius: 22px; padding: 38px 34px 26px;
  box-shadow: 0 30px 80px rgba(76, 29, 149, 0.35);
  text-align: center;
}
.ob-skip {
  position: absolute; top: 16px; right: 18px; background: none; border: none;
  color: #9aa0a6; font-size: 13px; font-weight: 600; cursor: pointer; padding: 4px 8px; border-radius: 6px;
}
.ob-skip:hover { background: #f5f3ff; color: #6d28d9; }

.ob-stage { min-height: 282px; display: flex; align-items: center; justify-content: center; }
.ob-slide { width: 100%; }
.ob-icon {
  width: 76px; height: 76px; margin: 0 auto 18px; border-radius: 22px;
  display: flex; align-items: center; justify-content: center; font-size: 34px;
  box-shadow: 0 12px 30px rgba(124, 58, 237, 0.28);
}
.ob-kicker { font-size: 11px; font-weight: 700; letter-spacing: 0.12em; color: #b39ddb; margin-bottom: 8px; }
.ob-title { font-size: 22px; font-weight: 800; color: #1a1a2e; margin: 0 0 12px; letter-spacing: -0.01em; }
.ob-body { font-size: 14.5px; line-height: 1.65; color: #5f6368; margin: 0; }

.ob-dots { display: flex; justify-content: center; gap: 8px; margin: 22px 0 20px; }
.ob-dot {
  width: 8px; height: 8px; border-radius: 50%; border: none; padding: 0; cursor: pointer;
  background: #e5e0f5; transition: all 0.25s ease;
}
.ob-dot.done { background: #c4b5fd; }
.ob-dot.active { width: 24px; border-radius: 4px; background: linear-gradient(90deg, #7c3aed, #a855f7); }

.ob-actions { display: flex; align-items: center; justify-content: space-between; gap: 12px; }
.ob-spacer { flex: 0 0 64px; }
.ob-btn {
  border: none; cursor: pointer; font-size: 14.5px; font-weight: 600;
  padding: 12px 22px; border-radius: 12px; transition: opacity 0.15s, background 0.15s;
}
.ob-btn.ghost { background: #f5f3ff; color: #6d28d9; }
.ob-btn.ghost:hover { background: #ede9fe; }
.ob-btn.primary { flex: 1; background: linear-gradient(135deg, #7c3aed, #6d28d9); color: #fff; }
.ob-btn.primary:hover { opacity: 0.93; }

/* slide transitions */
.ob-slide-next-enter-active, .ob-slide-next-leave-active,
.ob-slide-prev-enter-active, .ob-slide-prev-leave-active { transition: all 0.28s cubic-bezier(0.22, 1, 0.36, 1); }
.ob-slide-next-enter-from { opacity: 0; transform: translateX(28px); }
.ob-slide-next-leave-to { opacity: 0; transform: translateX(-28px); }
.ob-slide-prev-enter-from { opacity: 0; transform: translateX(-28px); }
.ob-slide-prev-leave-to { opacity: 0; transform: translateX(28px); }

.ob-fade-enter-active, .ob-fade-leave-active { transition: opacity 0.25s ease; }
.ob-fade-enter-from, .ob-fade-leave-to { opacity: 0; }
</style>
