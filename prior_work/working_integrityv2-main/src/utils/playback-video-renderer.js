/**
 * playback-video-renderer.js — Renders a recorded writing session to a
 * shareable WebM video Blob.
 *
 * The whole session timeline is compressed so the resulting video lasts
 * ≈targetDurationMs (clamped to 20s..120s). Frames are drawn onto an
 * offscreen <canvas> by a requestAnimationFrame loop driven by a virtual
 * playback clock, and captured via canvas.captureStream + MediaRecorder.
 *
 * Note: MediaRecorder captures in real time, so producing an N-second
 * video takes ≈N seconds of wall-clock time. `onProgress` reports 0..1.
 */

import {
  materializeSnapshots,
  detectSnapshotEvent,
  applyDiffToTags,
  formatDuration,
} from '@/composables/playback-engine'

const MIN_VIDEO_MS = 20000
const MAX_VIDEO_MS = 120000
const BANNER_VIDEO_MS = 1200
// Cap how many snapshot transitions (diff + re-wrap) run in a single frame
const MAX_APPLY_PER_FRAME = 200

/**
 * Render a session to a WebM video.
 *
 * @param {Array} rawSnapshots — raw, possibly delta-compressed snapshots
 * @param {Object} opts
 * @param {number}   [opts.width=1280]
 * @param {number}   [opts.height=720]
 * @param {number}   [opts.fps=30]
 * @param {number}   [opts.targetDurationMs=75000] — clamped to 20s..120s
 * @param {string}   [opts.title='']
 * @param {string}   [opts.authorName='']
 * @param {Function} [opts.onProgress] — called with 0..1
 * @returns {Promise<Blob>} the finished WebM blob
 */
export async function renderSessionToWebM(rawSnapshots, opts = {}) {
  const {
    width = 1280,
    height = 720,
    fps = 30,
    targetDurationMs = 75000,
    title = '',
    authorName = '',
    onProgress = () => {},
  } = opts

  if (typeof document === 'undefined' || typeof window === 'undefined') {
    throw new Error('renderSessionToWebM requires a browser environment')
  }
  if (typeof window.MediaRecorder === 'undefined') {
    throw new Error('MediaRecorder is not supported in this browser')
  }

  // ─── Materialize the session (same carry-forward as playback) ──
  let snapshots = materializeSnapshots(rawSnapshots)
  if (snapshots.length === 0) {
    // Degenerate input — render a short empty-document video rather than throw
    snapshots = [{ timestamp: 0, plaintext: '', wordCount: 0, typedCount: 0, pasteCount: 0 }]
  }

  const videoDurationMs = Math.min(MAX_VIDEO_MS, Math.max(MIN_VIDEO_MS, Number(targetDurationMs) || 75000))
  const sessionStart = snapshots[0].timestamp
  const sessionEnd = snapshots[snapshots.length - 1].timestamp
  const sessionDurationMs = Math.max(0, sessionEnd - sessionStart)

  // Map each snapshot onto the compressed video timeline
  const snapshotVideoTimes = snapshots.map((s, i) => {
    if (snapshots.length < 2) return 0
    if (sessionDurationMs <= 0) return (i / (snapshots.length - 1)) * videoDurationMs
    return ((s.timestamp - sessionStart) / sessionDurationMs) * videoDurationMs
  })

  // ─── Canvas + layout ────────────────────────────────────────
  const canvas = document.createElement('canvas')
  canvas.width = width
  canvas.height = height
  const ctx = canvas.getContext('2d')
  if (!ctx) throw new Error('Canvas 2D context unavailable')

  const HEADER_H = 64
  const PAD_X = 56
  const PAD_TOP = 24
  const BODY_FONT = '20px Georgia, "Times New Roman", serif'
  const UI_FONT = '-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif'
  const LINE_H = 32
  const docTop = HEADER_H + PAD_TOP
  const docBottom = height - 20
  const maxTextWidth = width - PAD_X * 2
  const visibleLineCount = Math.max(1, Math.floor((docBottom - docTop) / LINE_H))

  // ─── Document state ─────────────────────────────────────────
  let charTags = []        // [{ ch, origin }]
  let text = ''            // mirror of charTags text
  let lines = []           // [{ start, end }] char offsets into `text`
  let appliedIdx = -1      // last snapshot index applied
  let liveWordCount = 0
  let banner = null        // { type, label, detail, icon, untilMs }

  // ─── Word-wrap (cached; only the changed tail is re-wrapped) ──
  const charWidthCache = new Map()
  function charWidth(ch) {
    let w = charWidthCache.get(ch)
    if (w === undefined) {
      w = ctx.measureText(ch).width
      charWidthCache.set(ch, w)
    }
    return w
  }

  function wrapAppend(fromPos) {
    ctx.font = BODY_FONT
    let lineStart = fromPos
    let lineWidth = 0
    let lastBreak = -1
    let widthAtBreak = 0

    for (let i = fromPos; i < text.length; i++) {
      const ch = text[i]
      if (ch === '\n') {
        lines.push({ start: lineStart, end: i })
        lineStart = i + 1
        lineWidth = 0
        lastBreak = -1
        widthAtBreak = 0
        continue
      }
      const w = charWidth(ch)
      lineWidth += w
      if (ch === ' ' || ch === '\t') {
        lastBreak = i + 1
        widthAtBreak = lineWidth
      }
      if (lineWidth > maxTextWidth && i > lineStart) {
        if (lastBreak > lineStart) {
          lines.push({ start: lineStart, end: lastBreak })
          lineStart = lastBreak
          lineWidth -= widthAtBreak
        } else {
          lines.push({ start: lineStart, end: i })
          lineStart = i
          lineWidth = w
        }
        lastBreak = -1
        widthAtBreak = 0
      }
    }
    lines.push({ start: lineStart, end: text.length })
  }

  /** Re-wrap only from the line containing the first changed char. */
  function rewrapFrom(changePos) {
    let keep = 0
    while (keep < lines.length && lines[keep].end < changePos) keep++
    keep = Math.max(0, keep - 1) // back up one line for word merges at the seam
    lines.length = keep
    const wrapStart = keep > 0 ? lines[keep - 1].end : 0
    wrapAppend(wrapStart)
  }

  function firstDiffPos(a, b) {
    const n = Math.min(a.length, b.length)
    let i = 0
    while (i < n && a[i] === b[i]) i++
    return i
  }

  // ─── Apply snapshots up to the virtual clock ────────────────
  function applyUpTo(videoMs) {
    let budget = MAX_APPLY_PER_FRAME
    while (
      appliedIdx + 1 < snapshots.length &&
      snapshotVideoTimes[appliedIdx + 1] <= videoMs &&
      budget-- > 0
    ) {
      const idx = ++appliedIdx
      const snap = snapshots[idx]
      const prev = idx > 0 ? snapshots[idx - 1] : null
      const event = detectSnapshotEvent(prev, snap)
      const newText = snap.plaintext || ''

      if (newText !== text) {
        const changePos = firstDiffPos(text, newText)
        charTags = applyDiffToTags(charTags, newText, event === 'paste' ? 'pasted' : 'typed')
        text = newText
        rewrapFrom(changePos)
      }
      if (typeof snap.wordCount === 'number') liveWordCount = snap.wordCount

      if (event === 'paste') {
        const added = Math.max(0, newText.length - (prev?.plaintext || '').length)
        banner = {
          type: 'paste', icon: '📋',
          label: 'CONTENT PASTED',
          detail: `${added} characters from clipboard`,
          untilMs: snapshotVideoTimes[idx] + BANNER_VIDEO_MS,
        }
      } else if (event === 'delete') {
        const removed = Math.max(0, (prev?.plaintext || '').length - newText.length)
        banner = {
          type: 'delete', icon: '⌫',
          label: 'CONTENT DELETED',
          detail: `${removed} characters removed`,
          untilMs: snapshotVideoTimes[idx] + BANNER_VIDEO_MS,
        }
      }
    }
  }

  // ─── Drawing ────────────────────────────────────────────────
  function pathRoundRect(x, y, w, h, r) {
    ctx.beginPath()
    if (typeof ctx.roundRect === 'function') {
      ctx.roundRect(x, y, w, h, r)
      return
    }
    ctx.moveTo(x + r, y)
    ctx.arcTo(x + w, y, x + w, y + h, r)
    ctx.arcTo(x + w, y + h, x, y + h, r)
    ctx.arcTo(x, y + h, x, y, r)
    ctx.arcTo(x, y, x + w, y, r)
    ctx.closePath()
  }

  function truncate(str, max) {
    const s = String(str || '')
    return s.length > max ? s.slice(0, max - 1) + '…' : s
  }

  function drawHeader(videoMs) {
    ctx.fillStyle = '#111827'
    ctx.fillRect(0, 0, width, HEADER_H)

    ctx.textAlign = 'left'
    ctx.textBaseline = 'middle'
    ctx.fillStyle = '#ffffff'
    ctx.font = `600 22px ${UI_FONT}`
    ctx.fillText(truncate(title || 'Writing Session', 56), 24, HEADER_H / 2 - 11)
    ctx.fillStyle = '#9ca3af'
    ctx.font = `14px ${UI_FONT}`
    ctx.fillText(truncate(authorName, 56), 24, HEADER_H / 2 + 14)

    // Verified tag (right-aligned pill)
    const tagText = 'Editorrah verified session replay'
    ctx.font = `600 13px ${UI_FONT}`
    const tagW = ctx.measureText(tagText).width + 28
    const tagH = 26
    const tagX = width - tagW - 24
    const tagY = (HEADER_H - tagH) / 2
    ctx.fillStyle = 'rgba(16, 185, 129, 0.15)'
    pathRoundRect(tagX, tagY, tagW, tagH, 13)
    ctx.fill()
    ctx.strokeStyle = '#10b981'
    ctx.lineWidth = 1
    pathRoundRect(tagX, tagY, tagW, tagH, 13)
    ctx.stroke()
    ctx.fillStyle = '#6ee7b7'
    ctx.textAlign = 'center'
    ctx.fillText(tagText, tagX + tagW / 2, tagY + tagH / 2 + 1)

    // Elapsed session time + live word count, left of the tag
    const progress = videoDurationMs > 0 ? Math.min(1, videoMs / videoDurationMs) : 1
    const sessionElapsed = Math.round(sessionDurationMs * progress)
    ctx.fillStyle = '#d1d5db'
    ctx.font = `500 15px ${UI_FONT}`
    ctx.textAlign = 'right'
    ctx.fillText(`${formatDuration(sessionElapsed)} · ${liveWordCount} words`, tagX - 18, HEADER_H / 2)
    ctx.textAlign = 'left'
  }

  function drawBody() {
    ctx.font = BODY_FONT
    ctx.textBaseline = 'alphabetic'
    // Auto-scroll: draw only the visible tail of lines
    const firstLine = Math.max(0, lines.length - visibleLineCount)

    for (let li = firstLine; li < lines.length; li++) {
      const line = lines[li]
      const lineTop = docTop + (li - firstLine) * LINE_H
      const baseline = lineTop + LINE_H - 9
      let x = PAD_X
      let i = line.start

      while (i < line.end) {
        const origin = charTags[i]?.origin || 'typed'
        let j = i + 1
        while (j < line.end && (charTags[j]?.origin || 'typed') === origin) j++
        const run = text.slice(i, j)
        let runW = 0
        for (let k = 0; k < run.length; k++) runW += charWidth(run[k])

        if (origin === 'pasted') {
          ctx.fillStyle = '#fecaca'
          ctx.fillRect(x, lineTop + 4, runW, LINE_H - 8)
          ctx.fillStyle = '#ef4444'
          ctx.fillRect(x, lineTop + LINE_H - 6, runW, 2)
        }
        ctx.fillStyle = '#1a1a1a'
        ctx.fillText(run, x, baseline)
        x += runW
        i = j
      }
    }
  }

  function drawBanner(videoMs) {
    if (!banner) return
    if (videoMs > banner.untilMs) { banner = null; return }

    const isPaste = banner.type === 'paste'
    const bw = 560
    const bh = 116
    const bx = (width - bw) / 2
    const by = HEADER_H + (height - HEADER_H - bh) / 2

    ctx.fillStyle = isPaste ? 'rgba(254, 202, 202, 0.96)' : 'rgba(254, 243, 199, 0.96)'
    pathRoundRect(bx, by, bw, bh, 16)
    ctx.fill()
    ctx.strokeStyle = isPaste ? '#ef4444' : '#f59e0b'
    ctx.lineWidth = 3
    pathRoundRect(bx, by, bw, bh, 16)
    ctx.stroke()

    ctx.textAlign = 'center'
    ctx.textBaseline = 'middle'
    ctx.fillStyle = isPaste ? '#991b1b' : '#92400e'
    ctx.font = `800 26px ${UI_FONT}`
    ctx.fillText(`${banner.icon}  ${banner.label}`, width / 2, by + 46)
    ctx.font = `500 15px ${UI_FONT}`
    ctx.fillText(banner.detail || '', width / 2, by + 82)
    ctx.textAlign = 'left'
  }

  function drawFrame(videoMs) {
    // White doc background
    ctx.fillStyle = '#ffffff'
    ctx.fillRect(0, 0, width, height)
    drawBody()
    drawHeader(videoMs)
    drawBanner(videoMs)
  }

  // ─── Capture + render loop ──────────────────────────────────
  const stream = canvas.captureStream(fps)
  const mimeCandidates = ['video/webm;codecs=vp9', 'video/webm;codecs=vp8', 'video/webm']
  let mimeType = ''
  if (typeof MediaRecorder.isTypeSupported === 'function') {
    mimeType = mimeCandidates.find(m => MediaRecorder.isTypeSupported(m)) || ''
  }
  const recorder = mimeType
    ? new MediaRecorder(stream, { mimeType })
    : new MediaRecorder(stream)

  return await new Promise((resolve, reject) => {
    const chunks = []
    let rafId = null
    let stopped = false
    let startWall = 0
    const HOLD_TAIL_MS = 600 // hold the final frame briefly before stopping

    function cleanup() {
      if (rafId !== null) {
        cancelAnimationFrame(rafId)
        rafId = null
      }
      try { stream.getTracks().forEach(t => t.stop()) } catch { /* best effort */ }
    }

    recorder.ondataavailable = (e) => {
      if (e.data && e.data.size > 0) chunks.push(e.data)
    }
    recorder.onerror = (e) => {
      stopped = true
      cleanup()
      reject((e && e.error) || new Error('MediaRecorder failed'))
    }
    recorder.onstop = () => {
      cleanup()
      try { onProgress(1) } catch { /* user callback */ }
      resolve(new Blob(chunks, { type: recorder.mimeType || 'video/webm' }))
    }

    function frame(now) {
      if (stopped) return
      const clock = Math.min(Math.max(0, now - startWall), videoDurationMs)
      try {
        applyUpTo(clock)
        drawFrame(clock)
      } catch { /* never abort the loop on a single bad frame */ }
      try { onProgress(Math.min(1, Math.max(0, clock / videoDurationMs))) } catch { /* user callback */ }

      if (now - startWall >= videoDurationMs + HOLD_TAIL_MS) {
        stopped = true
        try {
          recorder.stop()
        } catch (err) {
          cleanup()
          reject(err)
        }
        return
      }
      rafId = requestAnimationFrame(frame)
    }

    // Prime the first frame before starting the recorder so the video
    // doesn't open on a blank/black frame.
    try {
      applyUpTo(0)
      drawFrame(0)
    } catch { /* defensive */ }

    try {
      recorder.start(1000) // collect chunks every second
    } catch (err) {
      cleanup()
      reject(err)
      return
    }

    rafId = requestAnimationFrame((t) => {
      startWall = t
      frame(t)
    })
  })
}
