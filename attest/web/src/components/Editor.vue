<script setup>
import { onBeforeUnmount, onMounted, watch } from 'vue'
import { useEditor, EditorContent } from '@tiptap/vue-3'
import StarterKit from '@tiptap/starter-kit'
import Placeholder from '@tiptap/extension-placeholder'
import { Capture, docText } from '../extensions/capture.js'
import { LedgerSync } from '../lib/sync.js'
import { textToTiptapDoc } from '../lib/text.js'

const props = defineProps({
  /** Existing ledger session to continue ({session_id, genesis, chain_head, event_count, finalized}). Omit for a fresh demo session. */
  session: { type: Object, default: null },
  /** Text the server replayed for that session; the editor starts from it. */
  initialText: { type: String, default: '' },
  /** Object or function returning headers (Bearer token) for engine calls. */
  headers: { type: [Object, Function], default: () => ({}) },
  readonly: { type: Boolean, default: false },
  /** Paragraph-only schema so the plain-text artifact round-trips exactly. */
  plain: { type: Boolean, default: false },
  apiBase: { type: String, default: import.meta.env.VITE_ATTEST_API ?? '' },
  placeholder: { type: String, default: 'Start writing — every keystroke is chained as you go…' },
})
const emit = defineEmits(['ready'])

let ledger = null
const editor = useEditor({
  extensions: [
    StarterKit.configure(props.plain
      ? { heading: false, bulletList: false, orderedList: false, listItem: false, codeBlock: false, blockquote: false, horizontalRule: false }
      : {}),
    Placeholder.configure({ placeholder: props.placeholder }),
    Capture.configure({ onEvent: (raw) => ledger?.record(raw) }),
  ],
  content: props.initialText ? textToTiptapDoc(props.initialText) : '',
  editable: !props.readonly,
  editorProps: { attributes: { class: 'attest-editor', spellcheck: 'false' } },
})

watch(() => props.readonly, (ro) => editor.value?.setEditable(!ro))

onMounted(async () => {
  const getText = () => docText(editor.value)
  ledger = new LedgerSync({ apiBase: props.apiBase, getText, headers: props.headers })
  if (props.session) {
    await ledger.resume(props.session)
    // If what is on screen differs from what the server replayed, checkpoint it so the chain
    // stays bound to the visible text (the engine treats ckpt as an external reset).
    const now = getText()
    if (now !== (props.initialText ?? '') && !props.session.finalized) {
      ledger.record({ ts: Date.now(), p: 0, d: 0, i: now, k: 'ckpt', src: null })
    }
  } else {
    await ledger.start()
  }
  emit('ready', { ledger, getText, editor })
})

onBeforeUnmount(() => {
  ledger?.stop()
  editor.value?.destroy()
})
</script>

<template>
  <div class="editor-wrap" :class="{ readonly }">
    <EditorContent :editor="editor" />
  </div>
</template>

<style>
.editor-wrap { border: 1px solid var(--border); border-radius: 8px; background: var(--surface); min-height: 60vh; }
.editor-wrap.readonly { opacity: 0.8; }
.attest-editor { padding: 20px 24px; min-height: 60vh; outline: none; font-size: 16px; line-height: 1.6; }
.attest-editor p { margin: 0 0 0.6em; }
.attest-editor p.is-editor-empty:first-child::before { content: attr(data-placeholder); color: var(--muted); float: left; height: 0; pointer-events: none; }
</style>
