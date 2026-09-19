import { Extension } from '@tiptap/core'

/** The document string the ledger replays. Same call everywhere or hashes will not bind. */
export function docText(editor) {
  return editor.getText({ blockSeparator: '\n' })
}

/**
 * Single contiguous diff between two code-point arrays → { p, d, i }.
 * Multiple simultaneous changes collapse into one wider replace, which replays identically.
 */
export function diffOnce(oldCps, newCps) {
  let start = 0
  const max = Math.min(oldCps.length, newCps.length)
  while (start < max && oldCps[start] === newCps[start]) start++
  let oldEnd = oldCps.length, newEnd = newCps.length
  while (oldEnd > start && newEnd > start && oldCps[oldEnd - 1] === newCps[newEnd - 1]) { oldEnd--; newEnd-- }
  return { p: start, d: oldEnd - start, i: newCps.slice(start, newEnd).join('') }
}

/**
 * Tiptap extension: turns every local document change into one raw ledger event and hands it
 * to `onEvent`. Paste vs type comes from ProseMirror's uiEvent meta; the internal/external hint
 * compares the pasted text with what was last copied from this editor (server re-checks).
 */
export const Capture = Extension.create({
  name: 'attestCapture',

  addOptions() {
    return { onEvent: () => {} }
  },

  addStorage() {
    return { prev: [], lastCopied: null }
  },

  onCreate() {
    this.storage.prev = [...docText(this.editor)]
    const dom = this.editor.view.dom
    const onCopy = () => {
      const text = window.getSelection()?.toString() ?? ''
      this.storage.lastCopied = text
      // Recorded in the ledger so the server can re-derive internal vs external pastes itself.
      if (text) this.options.onEvent({ ts: Date.now(), p: 0, d: 0, i: text, k: 'copy', src: null })
    }
    dom.addEventListener('copy', onCopy)
    dom.addEventListener('cut', onCopy)
    // Timing-only events: no key identity, just when a physical key went down/up.
    const timingKey = (e) => e.key.length === 1 || ['Backspace', 'Enter', 'Delete', 'Tab'].includes(e.key)
    // `e.repeat` is the OS auto-repeating a held key: one physical key-down, many DOM events. The
    // hardware witness (L3) sees one, so the ledger must count one too.
    dom.addEventListener('keydown', (e) => {
      if (e.repeat) return
      if (timingKey(e) && !e.metaKey && !e.ctrlKey) this.options.onEvent({ ts: Date.now(), p: 0, d: 0, i: '', k: 'kd', src: null })
    })
    dom.addEventListener('keyup', (e) => {
      if (timingKey(e) && !e.metaKey && !e.ctrlKey) this.options.onEvent({ ts: Date.now(), p: 0, d: 0, i: '', k: 'ku', src: null })
    })
  },

  onUpdate({ transaction }) {
    const next = [...docText(this.editor)]
    const { p, d, i } = diffOnce(this.storage.prev, next)
    this.storage.prev = next
    if (d === 0 && i.length === 0) return
    const ui = transaction.getMeta('uiEvent')
    const isPaste = ui === 'paste' || ui === 'drop'
    const raw = { ts: Date.now(), p, d, i, k: isPaste ? 'paste' : 'type', src: null }
    if (isPaste) raw.src = this.storage.lastCopied !== null && i.trim() === this.storage.lastCopied.trim() ? 'int' : 'ext'
    this.options.onEvent(raw)
  },
})
