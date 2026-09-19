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
    this.editor.view.dom.addEventListener('copy', () => {
      this.storage.lastCopied = window.getSelection()?.toString() ?? null
    })
    this.editor.view.dom.addEventListener('cut', () => {
      this.storage.lastCopied = window.getSelection()?.toString() ?? null
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
