<template>
  <Teleport to="body">
    <div v-if="visible" class="graph-overlay" @click.self="close">
      <div class="graph-modal">
        <!-- Header -->
        <div class="graph-header">
          <div class="graph-header-left">
            <div class="graph-icon">
              <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="22,12 18,12 15,21 9,3 6,12 2,12"/></svg>
            </div>
            <div>
              <h3 class="graph-title">{{ title }}</h3>
              <p class="graph-subtitle" v-if="description">{{ description }}</p>
            </div>
          </div>
          <div class="graph-header-actions">
            <button class="action-btn" @click="zoomIn" title="Zoom In">
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/><line x1="11" y1="8" x2="11" y2="14"/><line x1="8" y1="11" x2="14" y2="11"/></svg>
            </button>
            <button class="action-btn" @click="zoomOut" title="Zoom Out">
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/><line x1="8" y1="11" x2="14" y2="11"/></svg>
            </button>
            <button class="action-btn" @click="resetView" title="Reset View">
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M3 12a9 9 0 1 0 9-9 9.75 9.75 0 0 0-6.74 2.74L3 8"/><path d="M3 3v5h5"/></svg>
            </button>
            <div class="action-divider"></div>
            <button class="action-btn insert-btn" @click="insertGraph" :disabled="isInserting">
              <span v-if="isInserting" style="animation: spin 1s linear infinite;">⟳</span>
              <svg v-else width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><path d="M12 5v14M5 12h14"/></svg>
              {{ isInserting ? 'Uploading...' : 'Insert' }}
            </button>
            <button class="action-btn close-btn" @click="close">
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></svg>
            </button>
          </div>
        </div>

        <!-- Graph area -->
        <div class="graph-body">
          <div class="graph-canvas-wrapper">
            <div ref="graphContainer" class="graph-container"></div>

            <!-- Coordinate display -->
            <div class="coord-display" v-if="cursorCoords">
              <span class="coord-label">x:</span> <span class="coord-val">{{ cursorCoords.x }}</span>
              <span class="coord-sep"></span>
              <span class="coord-label">y:</span> <span class="coord-val">{{ cursorCoords.y }}</span>
            </div>

            <!-- Axis labels overlay -->
            <div class="axis-label axis-label-x" v-if="xLabel">{{ xLabel }}</div>
            <div class="axis-label axis-label-y" v-if="yLabel">{{ yLabel }}</div>
          </div>

          <!-- Functions legend panel -->
          <div class="graph-panel" v-if="functions.length > 0">
            <div class="panel-section">
              <div class="panel-section-title">Functions</div>
              <div v-for="(fn, i) in functions" :key="i" class="fn-item">
                <span class="fn-color-dot" :style="{ background: fn.color || colors[i % colors.length] }"></span>
                <span class="fn-expression">{{ fn.label || fn.fn }}</span>
              </div>
            </div>

            <div class="panel-section" v-if="annotations.length > 0">
              <div class="panel-section-title">Key Points</div>
              <div v-for="(a, i) in annotations" :key="'a'+i" class="annotation-item">
                <span class="annotation-marker">{{ a.text }}</span>
                <span class="annotation-coord" v-if="a.x !== undefined">x = {{ a.x }}</span>
              </div>
            </div>

            <div class="panel-section domain-info">
              <div class="panel-section-title">View Range</div>
              <div class="domain-row">
                <span class="domain-label">X</span>
                <span class="domain-val">{{ currentXDomain[0].toFixed(1) }} to {{ currentXDomain[1].toFixed(1) }}</span>
              </div>
              <div class="domain-row">
                <span class="domain-label">Y</span>
                <span class="domain-val">{{ currentYDomain[0].toFixed(1) }} to {{ currentYDomain[1].toFixed(1) }}</span>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  </Teleport>
</template>

<script setup>
import { ref, reactive, watch, nextTick, onBeforeUnmount } from 'vue'
import axios from 'axios'
import { API_URL } from '@/utils/api-url.js'

const props = defineProps({
  visible: Boolean,
  config: Object,
})

const emit = defineEmits(['close', 'insert'])

const graphContainer = ref(null)
const title = ref('')
const description = ref('')
const xLabel = ref('')
const yLabel = ref('')
const functions = ref([])
const annotations = ref([])
const cursorCoords = ref(null)
const colors = ['#4F46E5', '#EC4899', '#10B981', '#F59E0B', '#EF4444', '#8B5CF6']

const currentXDomain = reactive([-10, 10])
const currentYDomain = reactive([-10, 10])
let plotInstance = null

const renderGraph = async () => {
  if (!graphContainer.value || !props.config) return

  const functionPlot = (await import('function-plot')).default

  title.value = props.config.title || 'Graph'
  description.value = props.config.description || ''
  xLabel.value = props.config.xLabel || 'x'
  yLabel.value = props.config.yLabel || 'f(x)'
  functions.value = props.config.functions || []
  annotations.value = props.config.annotations || []

  const xD = props.config.xDomain || [-10, 10]
  const yD = props.config.yDomain || [-10, 10]
  currentXDomain[0] = xD[0]
  currentXDomain[1] = xD[1]
  currentYDomain[0] = yD[0]
  currentYDomain[1] = yD[1]

  drawPlot(functionPlot)
}

const drawPlot = (functionPlot) => {
  graphContainer.value.innerHTML = ''

  const data = functions.value.map((fn, i) => ({
    fn: fn.fn,
    color: fn.color || colors[i % colors.length],
    sampler: 'builtIn',
    graphType: 'polyline',
    nSamples: 2000,
  }))

  try {
    plotInstance = functionPlot({
      target: graphContainer.value,
      width: graphContainer.value.clientWidth || 640,
      height: graphContainer.value.clientHeight || 460,
      xAxis: { domain: [currentXDomain[0], currentXDomain[1]] },
      yAxis: { domain: [currentYDomain[0], currentYDomain[1]] },
      grid: true,
      data,
      tip: {
        xLine: true,
        yLine: true,
      },
    })

    // Track mouse for coordinate display
    const svgEl = graphContainer.value.querySelector('svg')
    if (svgEl) {
      svgEl.addEventListener('mousemove', (e) => {
        const rect = svgEl.getBoundingClientRect()
        const xRange = currentXDomain[1] - currentXDomain[0]
        const yRange = currentYDomain[1] - currentYDomain[0]
        // Approximate margins from function-plot (left ~40px, top ~20px, right ~20px, bottom ~30px)
        const ml = 40, mt = 20, mr = 20, mb = 30
        const plotW = rect.width - ml - mr
        const plotH = rect.height - mt - mb
        const px = e.clientX - rect.left - ml
        const py = e.clientY - rect.top - mt
        if (px >= 0 && px <= plotW && py >= 0 && py <= plotH) {
          cursorCoords.value = {
            x: (currentXDomain[0] + (px / plotW) * xRange).toFixed(3),
            y: (currentYDomain[1] - (py / plotH) * yRange).toFixed(3),
          }
        } else {
          cursorCoords.value = null
        }
      })
      svgEl.addEventListener('mouseleave', () => {
        cursorCoords.value = null
      })
    }

    // Listen for function-plot's zoom/pan events to update domain state
    plotInstance.on('all:zoom', (d) => {
      if (d.xDomain) {
        currentXDomain[0] = d.xDomain[0]
        currentXDomain[1] = d.xDomain[1]
      }
      if (d.yDomain) {
        currentYDomain[0] = d.yDomain[0]
        currentYDomain[1] = d.yDomain[1]
      }
    })
  } catch (e) {
    console.error('function-plot render error:', e)
    graphContainer.value.innerHTML = `<div class="graph-error"><span>Could not render graph</span><p>${e.message}</p></div>`
  }
}

const zoomIn = async () => {
  const xR = (currentXDomain[1] - currentXDomain[0]) * 0.2
  const yR = (currentYDomain[1] - currentYDomain[0]) * 0.2
  currentXDomain[0] += xR
  currentXDomain[1] -= xR
  currentYDomain[0] += yR
  currentYDomain[1] -= yR
  const fp = (await import('function-plot')).default
  drawPlot(fp)
}

const zoomOut = async () => {
  const xR = (currentXDomain[1] - currentXDomain[0]) * 0.25
  const yR = (currentYDomain[1] - currentYDomain[0]) * 0.25
  currentXDomain[0] -= xR
  currentXDomain[1] += xR
  currentYDomain[0] -= yR
  currentYDomain[1] += yR
  const fp = (await import('function-plot')).default
  drawPlot(fp)
}

const resetView = async () => {
  const xD = props.config?.xDomain || [-10, 10]
  const yD = props.config?.yDomain || [-10, 10]
  currentXDomain[0] = xD[0]
  currentXDomain[1] = xD[1]
  currentYDomain[0] = yD[0]
  currentYDomain[1] = yD[1]
  const fp = (await import('function-plot')).default
  drawPlot(fp)
}

const isInserting = ref(false)

const insertGraph = () => {
  if (!graphContainer.value || isInserting.value) return
  const svg = graphContainer.value.querySelector('svg')
  if (!svg) return

  isInserting.value = true

  // Clone SVG and add axis labels + title for the exported image
  const clone = svg.cloneNode(true)
  const svgW = parseInt(clone.getAttribute('width') || 640)
  const svgH = parseInt(clone.getAttribute('height') || 460)

  // Add title text
  const titleEl = document.createElementNS('http://www.w3.org/2000/svg', 'text')
  titleEl.setAttribute('x', svgW / 2)
  titleEl.setAttribute('y', 16)
  titleEl.setAttribute('text-anchor', 'middle')
  titleEl.setAttribute('font-size', '14')
  titleEl.setAttribute('font-weight', '600')
  titleEl.setAttribute('fill', '#111827')
  titleEl.setAttribute('font-family', '-apple-system, BlinkMacSystemFont, sans-serif')
  titleEl.textContent = title.value
  clone.appendChild(titleEl)

  // Add x-axis label
  if (xLabel.value) {
    const xLabelEl = document.createElementNS('http://www.w3.org/2000/svg', 'text')
    xLabelEl.setAttribute('x', svgW / 2)
    xLabelEl.setAttribute('y', svgH - 4)
    xLabelEl.setAttribute('text-anchor', 'middle')
    xLabelEl.setAttribute('font-size', '12')
    xLabelEl.setAttribute('fill', '#4b5563')
    xLabelEl.setAttribute('font-family', '-apple-system, BlinkMacSystemFont, sans-serif')
    xLabelEl.textContent = xLabel.value
    clone.appendChild(xLabelEl)
  }

  // Add y-axis label
  if (yLabel.value) {
    const yLabelEl = document.createElementNS('http://www.w3.org/2000/svg', 'text')
    yLabelEl.setAttribute('x', 14)
    yLabelEl.setAttribute('y', svgH / 2)
    yLabelEl.setAttribute('text-anchor', 'middle')
    yLabelEl.setAttribute('font-size', '12')
    yLabelEl.setAttribute('fill', '#4b5563')
    yLabelEl.setAttribute('font-family', '-apple-system, BlinkMacSystemFont, sans-serif')
    yLabelEl.setAttribute('transform', `rotate(-90, 14, ${svgH / 2})`)
    yLabelEl.textContent = yLabel.value
    clone.appendChild(yLabelEl)
  }

  const svgData = new XMLSerializer().serializeToString(clone)
  const canvas = document.createElement('canvas')
  const ctx = canvas.getContext('2d')
  const img = new Image()

  img.onload = async () => {
    canvas.width = img.width * 2
    canvas.height = img.height * 2
    ctx.scale(2, 2)
    ctx.fillStyle = '#ffffff'
    ctx.fillRect(0, 0, img.width, img.height)
    ctx.drawImage(img, 0, 0)
    const dataUrl = canvas.toDataURL('image/png')

    // Upload to backend to get a permanent URL (base64 breaks on save/reload)
    try {
      const res = await axios.post(`${API_URL}/api/images/upload`, { data_url: dataUrl })
      const permanentUrl = `${API_URL}${res.data.url}`
      emit('insert', permanentUrl)
    } catch (err) {
      console.error('Image upload failed, using data URL fallback:', err)
      emit('insert', dataUrl)
    } finally {
      isInserting.value = false
    }
  }

  img.src = 'data:image/svg+xml;base64,' + btoa(unescape(encodeURIComponent(svgData)))
}

const close = () => emit('close')

watch(
  () => props.visible,
  async (val) => {
    if (val && props.config) {
      await nextTick()
      renderGraph()
    }
  }
)

onBeforeUnmount(() => { plotInstance = null })
</script>

<style scoped>
.graph-overlay {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.45);
  backdrop-filter: blur(6px);
  z-index: 10000;
  display: flex;
  align-items: center;
  justify-content: center;
  animation: overlayIn 0.15s ease-out;
}

@keyframes overlayIn { from { opacity: 0 } to { opacity: 1 } }

.graph-modal {
  background: #fff;
  border-radius: 20px;
  box-shadow: 0 32px 80px rgba(0,0,0,0.25), 0 0 0 1px rgba(0,0,0,0.05);
  width: 860px;
  max-width: 95vw;
  max-height: 92vh;
  overflow: hidden;
  display: flex;
  flex-direction: column;
  animation: modalIn 0.25s cubic-bezier(0.16, 1, 0.3, 1);
}

@keyframes modalIn {
  from { opacity: 0; transform: scale(0.96) translateY(8px); }
  to { opacity: 1; transform: scale(1) translateY(0); }
}

/* ── Header ── */
.graph-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 14px 20px;
  border-bottom: 1px solid #f0f0f0;
  background: #fafbfc;
}

.graph-header-left {
  display: flex;
  align-items: center;
  gap: 12px;
  min-width: 0;
}

.graph-icon {
  width: 36px;
  height: 36px;
  border-radius: 10px;
  background: linear-gradient(135deg, #4F46E5, #7C3AED);
  color: #fff;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}

.graph-title {
  margin: 0;
  font-size: 15px;
  font-weight: 650;
  color: #111827;
  line-height: 1.2;
}

.graph-subtitle {
  margin: 2px 0 0;
  font-size: 12px;
  color: #6b7280;
  line-height: 1.3;
  max-width: 360px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.graph-header-actions {
  display: flex;
  align-items: center;
  gap: 4px;
  flex-shrink: 0;
}

.action-divider {
  width: 1px;
  height: 20px;
  background: #e5e7eb;
  margin: 0 4px;
}

.action-btn {
  border: 1px solid #e5e7eb;
  background: #fff;
  border-radius: 8px;
  height: 32px;
  min-width: 32px;
  padding: 0 8px;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 5px;
  transition: all 0.12s;
  color: #4b5563;
  font-size: 12px;
  font-weight: 500;
}

.action-btn:hover { background: #f3f4f6; border-color: #d1d5db; }
.action-btn:active { transform: scale(0.96); }

.insert-btn {
  background: #4F46E5;
  color: #fff;
  border-color: #4F46E5;
  padding: 0 14px;
  font-weight: 600;
}
.insert-btn:hover { background: #4338CA; border-color: #4338CA; }

.close-btn:hover { background: #fef2f2; color: #ef4444; border-color: #fecaca; }

/* ── Body ── */
.graph-body {
  display: flex;
  flex: 1;
  min-height: 0;
  overflow: hidden;
}

/* ── Canvas area ── */
.graph-canvas-wrapper {
  flex: 1;
  position: relative;
  min-width: 0;
  background: #fcfcfd;
}

.graph-container {
  width: 100%;
  height: 480px;
}

.graph-container :deep(svg) {
  font-family: -apple-system, BlinkMacSystemFont, 'Inter', 'Segoe UI', sans-serif !important;
}

.graph-container :deep(.x.axis path),
.graph-container :deep(.y.axis path) {
  stroke: #9ca3af;
  stroke-width: 1.5;
}

.graph-container :deep(.x.axis .tick line),
.graph-container :deep(.y.axis .tick line) {
  stroke: #e5e7eb;
}

.graph-container :deep(.tick text) {
  fill: #6b7280;
  font-size: 10px;
  font-family: 'SF Mono', 'Fira Code', 'Cascadia Code', monospace;
}

/* Thicker function lines */
.graph-container :deep(.line) {
  stroke-width: 2.5 !important;
}

/* Coordinate display */
.coord-display {
  position: absolute;
  top: 12px;
  right: 12px;
  background: rgba(17, 24, 39, 0.85);
  backdrop-filter: blur(8px);
  color: #f9fafb;
  padding: 6px 12px;
  border-radius: 8px;
  font-size: 11px;
  font-family: 'SF Mono', 'Fira Code', monospace;
  display: flex;
  align-items: center;
  gap: 4px;
  pointer-events: none;
}

.coord-label { color: #9ca3af; }
.coord-val { color: #fff; font-weight: 600; }
.coord-sep {
  width: 1px;
  height: 12px;
  background: rgba(255,255,255,0.2);
  margin: 0 4px;
}

/* Axis labels */
.axis-label {
  position: absolute;
  font-size: 12px;
  font-weight: 600;
  color: #4b5563;
  pointer-events: none;
  letter-spacing: 0.02em;
}

.axis-label-x {
  bottom: 8px;
  left: 50%;
  transform: translateX(-50%);
  background: rgba(255,255,255,0.9);
  padding: 2px 10px;
  border-radius: 6px;
}

.axis-label-y {
  top: 50%;
  left: 8px;
  transform: translateY(-50%) rotate(-90deg);
  background: rgba(255,255,255,0.9);
  padding: 2px 10px;
  border-radius: 6px;
  white-space: nowrap;
}

/* ── Side panel ── */
.graph-panel {
  width: 210px;
  flex-shrink: 0;
  border-left: 1px solid #f0f0f0;
  background: #fafbfc;
  padding: 16px;
  display: flex;
  flex-direction: column;
  gap: 16px;
  overflow-y: auto;
}

.panel-section-title {
  font-size: 10px;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.08em;
  color: #9ca3af;
  margin-bottom: 8px;
}

.fn-item {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 6px 8px;
  border-radius: 8px;
  background: #fff;
  border: 1px solid #f0f0f0;
  margin-bottom: 4px;
}

.fn-color-dot {
  width: 10px;
  height: 10px;
  border-radius: 50%;
  flex-shrink: 0;
  box-shadow: 0 0 0 2px rgba(0,0,0,0.06);
}

.fn-expression {
  font-size: 12px;
  font-family: 'SF Mono', 'Fira Code', 'Cascadia Code', monospace;
  color: #1f2937;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.annotation-item {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 4px 8px;
  font-size: 11px;
  color: #4b5563;
  border-radius: 6px;
  background: #fff;
  border: 1px solid #f0f0f0;
  margin-bottom: 3px;
}

.annotation-marker { font-weight: 600; color: #374151; }
.annotation-coord {
  font-family: 'SF Mono', 'Fira Code', monospace;
  font-size: 10px;
  color: #9ca3af;
}

.domain-info { margin-top: auto; }

.domain-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 3px 0;
  font-size: 11px;
}

.domain-label {
  font-weight: 700;
  color: #6b7280;
  font-family: 'SF Mono', monospace;
}

.domain-val {
  font-family: 'SF Mono', monospace;
  color: #374151;
  font-size: 10px;
}

.graph-error {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  height: 100%;
  color: #ef4444;
  gap: 8px;
  padding: 40px;
  text-align: center;
}

.graph-error span { font-weight: 600; font-size: 15px; }
.graph-error p { font-size: 12px; color: #9ca3af; margin: 0; }

/* ── Responsive ── */
@media (max-width: 720px) {
  .graph-modal { width: 98vw; }
  .graph-panel { display: none; }
  .graph-subtitle { display: none; }
}
</style>
