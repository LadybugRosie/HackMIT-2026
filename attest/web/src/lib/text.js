/** Code-point helpers: the ledger counts positions in code points, JS strings in UTF-16 units. */
export const cps = (s) => [...s]
export const cpLen = (s) => cps(s).length
export const cpSlice = (s, start, end) => cps(s).slice(start, end).join('')

/**
 * Plain text -> Tiptap doc with one paragraph per line, so that
 * editor.getText({ blockSeparator: '\n' }) returns exactly the input again.
 */
export function textToTiptapDoc(text) {
  const lines = (text ?? '').split('\n')
  return {
    type: 'doc',
    content: lines.map((line) => (line ? { type: 'paragraph', content: [{ type: 'text', text: line }] } : { type: 'paragraph' })),
  }
}
