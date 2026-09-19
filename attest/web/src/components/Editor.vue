<script setup>
import { onBeforeUnmount, onMounted } from 'vue'
import { useEditor, EditorContent } from '@tiptap/vue-3'
import StarterKit from '@tiptap/starter-kit'
import Placeholder from '@tiptap/extension-placeholder'
import { Capture, docText } from '../extensions/capture.js'
import { LedgerSync } from '../lib/sync.js'

const API = import.meta.env.VITE_ATTEST_API ?? 'http://localhost:8090'

const emit = defineEmits(['ready'])

let ledger = null
const editor = useEditor({
  extensions: [
    StarterKit,
    Placeholder.configure({ placeholder: 'Start writing — every keystroke is chained as you go…' }),
    Capture.configure({ onEvent: (raw) => ledger?.record(raw) }),
  ],
  content: '',
  editorProps: { attributes: { class: 'attest-editor', spellcheck: 'false' } },
})

onMounted(async () => {
  ledger = new LedgerSync({ apiBase: API, getText: () => docText(editor.value) })
  await ledger.start()
  emit('ready', { ledger, getText: () => docText(editor.value), editor })
})

onBeforeUnmount(() => editor.value?.destroy())
</script>

<template>
  <div class="editor-wrap">
    <EditorContent :editor="editor" />
  </div>
</template>

<style>
.editor-wrap { border: 1px solid var(--border); border-radius: 8px; background: var(--surface); min-height: 60vh; }
.attest-editor { padding: 20px 24px; min-height: 60vh; outline: none; font-size: 16px; line-height: 1.6; }
.attest-editor p { margin: 0 0 0.6em; }
.attest-editor p.is-editor-empty:first-child::before { content: attr(data-placeholder); color: var(--muted); float: left; height: 0; pointer-events: none; }
</style>
