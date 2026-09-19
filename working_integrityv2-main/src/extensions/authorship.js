/**
 * Authorship Mark — invisible per-character attribution for collaborative
 * (researcher) topics. Every locally-typed/pasted character gets marked with
 * the current user's {uid, name} so stylometry can later be run per author.
 *
 * The mark renders as a plain <span class="authorship" data-author-id ...>
 * with NO visual styling — it is purely attribution data. Distinct colors are
 * only shown on the collaboration cursors (CollaborationCursor), not on text.
 */
import { Mark } from '@tiptap/core'
import { Plugin, PluginKey } from '@tiptap/pm/state'

const authorshipPluginKey = new PluginKey('authorshipTracker')

/**
 * True when a transaction originated from the Yjs sync plugin (remote edit)
 * rather than local typing/paste. Remote edits must NOT be re-attributed to
 * the local user. Exported so SessionRecorder's event stream applies the
 * exact same rule — each collab participant records only their OWN edits.
 */
export function isRemoteTransaction(tr) {
  try {
    if (tr.getMeta('y-sync$')) return true
    // Defensive: y-sync's meta key is the plugin instance key, whose string
    // name contains 'y-sync' (e.g. 'y-sync$'). Scan all meta keys.
    const meta = tr.meta || {}
    for (const key of Object.keys(meta)) {
      if (typeof key === 'string' && key.includes('y-sync')) return true
    }
  } catch (e) {
    // If meta inspection fails, treat as remote (safer: don't mis-attribute)
    return true
  }
  return false
}

const Authorship = Mark.create({
  name: 'authorship',

  // Typing right after an authored range continues that range
  inclusive: true,

  addOptions() {
    return {
      // Getter for the current local user — configured by the editor at
      // setup time. Must return { uid, name } (or null when unknown).
      user: () => null,
    }
  },

  addAttributes() {
    return {
      uid: {
        default: null,
        keepOnSplit: true,
        parseHTML: (element) => element.getAttribute('data-author-id'),
      },
      name: {
        default: null,
        keepOnSplit: true,
        parseHTML: (element) => element.getAttribute('data-author-name'),
      },
    }
  },

  parseHTML() {
    return [{ tag: 'span[data-author-id]' }]
  },

  renderHTML({ mark }) {
    return [
      'span',
      {
        'data-author-id': mark.attrs.uid,
        'data-author-name': mark.attrs.name,
        class: 'authorship',
      },
      0,
    ]
  },

  addProseMirrorPlugins() {
    const getUser = () => {
      try {
        const u =
          typeof this.options.user === 'function' ? this.options.user() : null
        if (u && u.uid) return u
      } catch (e) {
        /* never throw from the plugin */
      }
      return null
    }

    return [
      new Plugin({
        key: authorshipPluginKey,
        appendTransaction: (transactions, _oldState, newState) => {
          try {
            if (!transactions.some((tr) => tr.docChanged)) return null

            const user = getUser()
            if (!user) return null

            const markType = newState.schema.marks.authorship
            if (!markType) return null

            // Collect inserted ranges from local transactions only
            const ranges = []
            for (const tr of transactions) {
              if (!tr.docChanged) continue
              if (tr.getMeta('authorship-skip')) continue
              if (isRemoteTransaction(tr)) continue

              const maps = tr.mapping.maps
              maps.forEach((stepMap, index) => {
                stepMap.forEach((_fromA, _toA, fromB, toB) => {
                  if (toB <= fromB) return
                  let from = fromB
                  let to = toB
                  // Map the inserted range through the remaining steps of
                  // this transaction so positions are valid in its final doc.
                  for (let i = index + 1; i < maps.length; i += 1) {
                    from = maps[i].map(from, 1)
                    to = maps[i].map(to, -1)
                  }
                  if (to > from) ranges.push({ from, to })
                })
              })
            }

            if (!ranges.length) return null

            const tr = newState.tr
            const maxPos = newState.doc.content.size
            let changed = false

            for (const range of ranges) {
              const from = Math.max(0, Math.min(range.from, maxPos))
              const to = Math.max(0, Math.min(range.to, maxPos))
              if (to <= from) continue
              tr.addMark(
                from,
                to,
                markType.create({ uid: user.uid, name: user.name }),
              )
              changed = true
            }

            if (!changed) return null

            // Don't pollute undo history / don't re-trigger ourselves
            tr.setMeta('addToHistory', false)
            tr.setMeta('authorship-skip', true)
            return tr
          } catch (e) {
            // The attribution layer must never break editing
            console.warn('[authorship] appendTransaction failed:', e)
            return null
          }
        },
      }),
    ]
  },
})

/**
 * Walk the document and group text by authorship uid.
 * Unmarked text is attributed to uid 'unknown'.
 *
 * @param {import('@tiptap/core').Editor} editor
 * @returns {Array<{uid: string, name: string, text: string}>}
 *   One entry per uid; consecutive same-author runs are concatenated,
 *   separate runs of the same author are joined with '\n'.
 */
export function getAuthorSegments(editor) {
  try {
    const doc = editor?.state?.doc
    if (!doc) return []

    // uid -> { name, chunks: string[] }
    const byUid = new Map()
    let lastUid = null
    let buffer = ''

    const flush = () => {
      if (lastUid === null || !buffer) {
        buffer = ''
        return
      }
      const entry = byUid.get(lastUid)
      if (entry) {
        entry.chunks.push(buffer)
      }
      buffer = ''
    }

    doc.descendants((node) => {
      if (!node.isText || !node.text) return true

      const mark = node.marks.find((m) => m.type.name === 'authorship')
      const uid = mark?.attrs?.uid || 'unknown'
      const name =
        mark?.attrs?.name || (uid === 'unknown' ? 'Unknown' : String(uid))

      if (!byUid.has(uid)) {
        byUid.set(uid, { name, chunks: [] })
      }

      if (uid !== lastUid) {
        flush()
        lastUid = uid
      }
      buffer += node.text
      return true
    })
    flush()

    const segments = []
    for (const [uid, entry] of byUid.entries()) {
      const text = entry.chunks.join('\n')
      if (!text) continue
      segments.push({ uid, name: entry.name, text })
    }
    return segments
  } catch (e) {
    console.warn('[authorship] getAuthorSegments failed:', e)
    return []
  }
}

export default Authorship
