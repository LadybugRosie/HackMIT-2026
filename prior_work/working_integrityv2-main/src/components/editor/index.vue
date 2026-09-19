<template>
  <editor-content
    :spellcheck="options.document.enableSpellcheck && $document.spellcheck"
    class="editor-container"
    :class="{
      'show-line-number': page.showLineNumber,
      'format-painter': painter.enabled,
    }"
    :style="{ lineHeight: defaultLineHeight }"
    :editor="editor"
  />
  <!-- Bubble menu is disabled in collab mode: Tiptap's Collaboration extensions
       break its tippy show/position logic (it floats / never hides). Collaborators
       use the full top toolbar. Non-collab editing is unchanged. -->
  <template v-if="editor && !editorDestroyed && !collabEnabled">
    <bubble-menu
      v-show="!blockMenu && !painter.enabled"
      class="umo-editor-bubble-menu"
      :class="{ assistant }"
      :editor="editor"
      :tippy-options="tippyOpitons"
    >
      <menus-bubble v-if="options.document.enableBubbleMenu && !assistant">
        <template #bubble_menu="props">
          <slot name="bubble_menu" v-bind="props" />
        </template>
      </menus-bubble>
      <assistant-input v-if="options.assistant.enabled && assistant" />
    </bubble-menu>
  </template>
  <template
    v-if="options.document.enableBlockMenu && editor && !editorDestroyed"
  >
    <menus-context-block />
  </template>
</template>

<script setup>
import { Editor, EditorContent, BubbleMenu } from '@tiptap/vue-3'
import { nextTick } from 'vue'
import StarterKit from '@tiptap/starter-kit'
import Focus from '@tiptap/extension-focus'

// 基本
import FormatPainter from '@/extensions/format-painter'
import FontFamily from '@tiptap/extension-font-family'
import FontSize from '@/extensions/font-size'
import Bold from '@tiptap/extension-bold'
import Underline from '@tiptap/extension-underline'
import Subscript from '@tiptap/extension-subscript'
import Superscript from '@tiptap/extension-superscript'
import Color from '@tiptap/extension-color'
import TextColor from '@tiptap/extension-text-style'
import Highlight from '@tiptap/extension-highlight'
import BulletList from '@/extensions/bullet-list'
import OrderedList from '@/extensions/ordered-list'
import Indent from '@/extensions/indent'
import TextAlign from '@/extensions/text-align'
import NodeAlign from '@/extensions/node-align'
import TaskItem from '@tiptap/extension-task-item'
import TaskList from '@/extensions/list/tasklist'
import LineHeight from '@/extensions/line-height'
import Margin from '@/extensions/margin'
import SearchReplace from '@sereneinserenade/tiptap-search-and-replace'

// 插入
import Link from '@tiptap/extension-link'
import Image from '@/extensions/image'
import Video from '@/extensions/video'
import Audio from '@/extensions/audio'
import File from '@/extensions/file'
import CodeBlock from '@/extensions/code-block'
import TextBox from '@/extensions/text-box'
import hr from '@/extensions/hr'
import Iframe from '@/extensions/iframe'

// 表格
import Table from '@/extensions/list/table'
import TableCell from '@/extensions/table-cell'
import TableHeader from '@/extensions/table-header'
import TableRow from '@tiptap/extension-table-row'

// 页面 (Only Toc remains)
import Toc from '@/extensions/toc'

// 其他
import Selection from '@/extensions/selection'
import Typography from '@tiptap/extension-typography'
import CharacterCount from '@tiptap/extension-character-count'
import FileHandler from '@/extensions/file-handler'
import Dropcursor from '@tiptap/extension-dropcursor'

import "katex/dist/katex.min.css";
import { Mathematics, migrateMathStrings } from '@tiptap/extension-mathematics'

// 协作 — real-time collaboration (researcher collaborative topics)
import * as Y from 'yjs'
import { HocuspocusProvider } from '@hocuspocus/provider'
import Collaboration from '@tiptap/extension-collaboration'
import CollaborationCursor from '@tiptap/extension-collaboration-cursor'
import Authorship from '@/extensions/authorship'
import { useAuth } from '@/composables/auth'

const {
  options,
  container,
  editor,
  page, // Note: You might want to simplify this in your store later
  painter,
  blockMenu,
  assistant,
  setEditor,
  editorDestroyed,
  integrity,
} = useStore()
const $document = useState('document')

let enableRules = true
if (!options.value.document.enableMarkdown || !$document.value.markdown) {
  enableRules = [Image, Typography]
}

const defaultLineHeight = $computed(() => {
  return options.value.dicts.lineHeights.find((item) => item.default).value
})

// ============================================================================
// REAL-TIME COLLABORATION (Yjs / Hocuspocus)
// Activated only for researcher collaborative topics via ?collab=1 in the URL.
// Stylometry-only mode: the IntegrityTracker does not run for these sessions.
// ============================================================================
const _params = new URLSearchParams(window.location.search)
const _collabAssignmentId = _params.get('assignment_id')
const collabEnabled = _params.get('collab') === '1' && !!_collabAssignmentId

let ydoc = null
let collabProvider = null

// Deterministic per-user cursor color from user_id hash
const _collabColorFromId = (id) => {
  const str = String(id || 'anonymous')
  let hash = 0
  for (let i = 0; i < str.length; i++) {
    hash = ((hash << 5) - hash + str.charCodeAt(i)) | 0
  }
  return `hsl(${Math.abs(hash) % 360}, 70%, 45%)`
}

// Local user identity with safe fallbacks — updated once initAuth resolves.
// IMPORTANT: this object is mutated in place; the Authorship mark reads it
// lazily through its `user` getter, so updates apply to subsequent typing.
const collabUser = {
  uid: 'anonymous',
  name: 'Anonymous',
  color: _collabColorFromId('anonymous'),
}

const { user: collabAuthUser, initAuth: collabInitAuth } = useAuth()

const _emitCollabPresence = () => {
  if (!collabProvider) return
  try {
    const states = Array.from(
      collabProvider.awareness?.getStates?.()?.values?.() || [],
    )
    const users = states
      .map((s) => s?.user)
      .filter(Boolean)
      .map((u) => ({ name: u.name || 'Anonymous', color: u.color || '#888' }))
    window.dispatchEvent(
      new CustomEvent('collab-presence', {
        detail: { count: users.length, users },
      }),
    )
  } catch (e) {
    console.warn('collab presence emit failed:', e)
  }
}

if (collabEnabled) {
  ydoc = new Y.Doc()
  collabProvider = new HocuspocusProvider({
    url: import.meta.env.VITE_COLLAB_WS_URL || 'ws://localhost:1235',
    name: `topic:${_collabAssignmentId}`,
    token: localStorage.getItem('auth_token') || '',
    document: ydoc,
  })

  // Presence: re-emit on every awareness change so EditorPage can render
  // the live presence strip without coupling to the provider.
  try {
    collabProvider.awareness?.on('change', _emitCollabPresence)
  } catch (e) {
    console.warn('collab awareness listener failed:', e)
  }

  // Subtle visuals: authorship marks stay invisible (pure attribution data);
  // only the collaboration cursors get distinct colors.
  if (!document.querySelector('#collab-cursor-style')) {
    const style = document.createElement('style')
    style.id = 'collab-cursor-style'
    style.textContent = `
      .authorship { background: transparent; }
      .collaboration-cursor__caret {
        border-left: 1px solid;
        border-right: 1px solid;
        margin-left: -1px;
        margin-right: -1px;
        pointer-events: none;
        position: relative;
        word-break: normal;
      }
      .collaboration-cursor__label {
        border-radius: 3px 3px 3px 0;
        color: #fff;
        font-size: 11px;
        font-style: normal;
        font-weight: 600;
        left: -1px;
        line-height: normal;
        padding: 0.1rem 0.3rem;
        position: absolute;
        top: -1.3em;
        user-select: none;
        white-space: nowrap;
      }
    `
    document.head.append(style)
  }
}

const editorInstance = new Editor({
  editable: !options.value.document.readOnly,
  autofocus: options.value.document.autofocus,
  // In collab mode Yjs owns the document — setting initial content here
  // would duplicate it on every join.
  content: collabEnabled ? undefined : options.value.document.content,
  enableInputRules: enableRules,
  enablePasteRules: enableRules,
  editorProps: {
    attributes: {
      class: 'umo-editor',
    },
    ...options.value.document.editorProps,
  },
  parseOptions: options.value.document.parseOptions,
  extensions: [
    // StarterKit now manages the document, creating the infinite canvas.
    StarterKit.configure({
      bold: false,
      bulletList: false,
      orderedList: false,
      codeBlock: false,
      horizontalRule: false,
      gapcursor: true,
      dropcursor: false,
      // `document: false` has been REMOVED. This is the key change.
      // Collab: Yjs provides its own undo/redo — local history must be off.
      ...(collabEnabled ? { history: false } : {}),
    }),
    
    // All page-related extensions (Document.extend, Page, PageBreak, PasteFix) have been removed.

    Focus.configure({
      className: 'node-focused',
      mode: 'all',
    }),
    FormatPainter,
    FontFamily,
    FontSize,
    Bold.extend({
      renderHTML: ({ HTMLAttributes }) => ['b', HTMLAttributes, 0],
    }),
    Underline,
    Subscript,
    Superscript,
    Color,
    TextColor,
    Highlight.configure({
      multicolor: true,
    }),
    BulletList,
    OrderedList,
    Indent,
    TextAlign,
    NodeAlign,
    TaskItem.configure({ nested: true }),
    TaskList.configure({
      HTMLAttributes: {
        class: 'task-list',
      },
    }),
    LineHeight.configure({
      types: ['heading', 'paragraph'],
      defaultLineHeight,
    }),
    Margin,
    SearchReplace,
    Link,
    Image,
    Video,
    Audio,
    File,
    TextBox,
    CodeBlock,
    hr,
    Iframe,
    Mathematics.configure({}),
    Table.configure({
      allowTableNodeSelection: true,
    }),
    TableRow,
    TableHeader,
    TableCell,
    Toc,
    Selection,
    Typography.configure(options.value.document.typographyRules),
    CharacterCount.configure({
      limit:
        options.value.document.characterLimit !== 0
          ? options.value.document.characterLimit
          : undefined,
    }),
    FileHandler.configure({
      allowedMimeTypes: options.value.file.allowedMimeTypes,
      onPaste(editor, files, html) {
        files.forEach((file) => editor.commands.insertFile({ file }))
      },
      onDrop: (editor, files, pos) => {
        files.forEach((file) => editor.commands.insertFile({ file, pos }))
      },
    }),
    Dropcursor.configure({
      color: 'var(--umo-primary-color)',
    }),
    // Collab-only extensions: Yjs binding, remote cursors and per-character
    // authorship attribution. Registered ONLY in collab mode so student
    // (non-collab) flows are completely unaffected.
    ...(collabEnabled
      ? [
          Collaboration.configure({
            document: ydoc,
          }),
          CollaborationCursor.configure({
            provider: collabProvider,
            user: {
              name: collabUser.name,
              color: collabUser.color,
            },
          }),
          Authorship.configure({
            user: () => ({ uid: collabUser.uid, name: collabUser.name }),
          }),
        ]
      : []),
    ...options.value.extensions,
  ],
  onCreate({ editor }) {
    migrateMathStrings(editor)
  },
  onUpdate({ editor }) {
    $document.value.content = editor.getHTML()
  },
})
setEditor(editorInstance)

// Collab: hydrate the local user identity (useAuth user may be null on hard
// reload — initAuth() resolves it). Once known, update provider awareness and
// the collaboration cursor; the Authorship mark reads collabUser lazily.
if (collabEnabled) {
  const syncCollabUser = () => {
    const u = collabAuthUser.value
    if (!u) return
    collabUser.uid = u.user_id || collabUser.uid
    collabUser.name = u.name || collabUser.name
    collabUser.color = _collabColorFromId(u.user_id || u.name)
    try {
      collabProvider?.setAwarenessField('user', {
        name: collabUser.name,
        color: collabUser.color,
        uid: collabUser.uid,
      })
    } catch (e) {
      console.warn('collab awareness user update failed:', e)
    }
    try {
      if (!editorInstance.isDestroyed) {
        editorInstance.commands.updateUser({
          name: collabUser.name,
          color: collabUser.color,
        })
      }
    } catch (e) {
      console.warn('collab cursor user update failed:', e)
    }
    _emitCollabPresence()
  }

  if (collabAuthUser.value) {
    syncCollabUser()
  } else {
    collabInitAuth()
      .then(() => syncCollabUser())
      .catch(() => {})
  }
  // Keep identity in sync if auth state changes later
  watch(collabAuthUser, () => syncCollabUser())

  // Recovery net: after Yjs syncs the server's persisted state, if the shared
  // document is STILL empty (persistence loss / fresh reconnect race), seed it
  // once from the last saved draft snapshot (window.editorContentFromDatabase,
  // set by EditorPage). Guarded on "editor is empty", so it can never overwrite
  // a live document — it only fills a genuinely-blank one.
  let _draftSeeded = false
  collabProvider?.on('synced', () => {
    let tries = 0
    const attempt = () => {
      if (_draftSeeded || editorInstance.isDestroyed) return
      if ((editorInstance.getText() || '').trim().length > 0) { _draftSeeded = true; return }
      const draft = window.editorContentFromDatabase
      if (draft && draft.replace(/<[^>]*>/g, '').trim()) {
        try { editorInstance.commands.setContent(draft, false) } catch (e) { /* ignore */ }
        _draftSeeded = true
        return
      }
      if (tries++ < 20) setTimeout(attempt, 400) // wait for the draft snapshot to load
    }
    setTimeout(attempt, 900) // let the sync apply to the editor first
  })

  // --- TEMP collab diagnostics: confirm typing -> Yjs sync and restore on return ---
  try {
    collabProvider?.on('status', (e) => console.log('[collab-dbg] status:', e && e.status))
    collabProvider?.on('synced', () => console.log(
      '[collab-dbg] SYNCED — editor chars:', (editorInstance.getText() || '').length,
      '| draft-snapshot chars:', String(window.editorContentFromDatabase || '').replace(/<[^>]*>/g, '').length,
    ))
    let _dbgT = null
    editorInstance.on('update', () => {
      clearTimeout(_dbgT)
      _dbgT = setTimeout(() => console.log('[collab-dbg] editor content chars:', (editorInstance.getText() || '').length), 400)
    })
  } catch (e) { /* ignore */ }
}

// Integrity event capture
import axios from 'axios'
import { getApiUrl } from '@/utils/api-url'

const INTEGRITY_API = getApiUrl()
let integrityEvents = []
let lastCursorPos = 0
let eventBatchTimer = null
let periodicUpdateTimer = null
let lastServerSignature = null // Store server signature
let lastChainHead = null // Store chain head hash

const captureIntegrityEvent = (event) => {
  console.log('🎯 captureIntegrityEvent called with:', event)
  
  if (!integrity?.value?.active) {
    console.error('❌❌❌ Event NOT captured - integrity not active!')
    console.log('Current integrity state:', integrity.value)
    return
  }
  
  const ts = Date.now() / 1000
  const eventWithTs = { ...event, ts }
  integrityEvents.push(eventWithTs)
  
  console.log('✅✅✅ Event SUCCESSFULLY captured:', event.t, '| Total events:', integrityEvents.length)
  console.log('Event details:', eventWithTs)
  
  // Don't send on every event - let periodic updates handle it
  // Only send if we have a LOT of events
  if (integrityEvents.length >= 50) {
    console.log('📤 Sending immediately (50 events reached)')
    sendIntegrityEvents()
  }
}

// ENABLED: Periodic updates for server sync (Phase 2)
const startPeriodicUpdates = () => {
  // Clear any existing timer
  if (periodicUpdateTimer) {
    clearInterval(periodicUpdateTimer)
  }
  
  // Send events to server every 10 seconds for real-time sync
  periodicUpdateTimer = setInterval(() => {
    if (integrity?.value?.active && integrityEvents.length > 0) {
      console.log('⏰ Periodic sync - sending events to server...')
      sendIntegrityEvents()
    }
  }, 10000) // 10 seconds
  
  console.log('✅ Periodic server sync ENABLED')
}

const sendIntegrityEvents = async () => {
  if (!integrity?.value?.active) return
  
  // Even if no events, still send current state for analysis
  const events = [...integrityEvents]
  integrityEvents = [] // Clear after copying
  
  // If no events and no periodic update needed, skip
  if (events.length === 0) {
    console.log('   (No new events, sending current state only)')
  }
  
  try {
    // Get CURRENT editor content
    const contentText = editorInstance.getText()
    const contentLen = contentText.length
    const contentSha = await crypto.subtle.digest('SHA-256', 
      new TextEncoder().encode(contentText))
    const hashArray = Array.from(new Uint8Array(contentSha))
    const contentSha256 = hashArray.map(b => b.toString(16).padStart(2, '0')).join('')
    
    console.log('📤 Sending update to backend')
    console.log('   Events:', events.length)
    console.log('   Current text length:', contentLen)
    console.log('   Current text preview:', contentText.substring(0, 100))
    
    // Build client_state snapshot for cross-browser persistence
    const clientState = (window.TYPED_DB && window.EXTERNAL_DB) ? {
      TYPED_DB: {
        allTypedChars: (window.TYPED_DB.allTypedChars || '').slice(-10000),
        totalTypedCount: window.TYPED_DB.totalTypedCount || 0,
      },
      EXTERNAL_DB: {
        pastes: (window.EXTERNAL_DB.pastes || []).map(p => ({
          id: p.id, text: p.text, timestamp: p.timestamp
        })),
        totalPastedChars: window.EXTERNAL_DB.totalPastedChars || 0,
      },
      INTERNAL_DB: {
        pastes: (window.INTERNAL_DB?.pastes || []).slice(-100),
        totalChars: window.INTERNAL_DB?.totalChars || 0,
        copyBuffer: (window.INTERNAL_DB?.copyBuffer || []).slice(-50),
      },
      TIMELINE_DB: {
        segments: (window.TIMELINE_DB?.segments || []).slice(-1000),
        deletions: window.TIMELINE_DB?.deletions || 0,
        additions: window.TIMELINE_DB?.additions || 0,
      },
      ts: Date.now()
    } : null

    // Include chain head if we have one (for chain verification)
    const requestPayload = {
      session_id: integrity.value.sessionId,
      doc_id: integrity.value.docId,
      content_len: contentLen,
      content_sha256: contentSha256,
      current_text: contentText,
      events,
      last_chain_head: lastChainHead, // Send last known chain head
      device_fingerprint: integrity.value.deviceFingerprint || undefined,  // Loophole #6
      client_state: clientState  // Cross-browser persistence
    }
    
    const response = await axios.post(`${INTEGRITY_API}/api/integrity/ingest`, requestPayload)
    
    console.log('📊 Integrity response:', response.data)
    
    // Verify signature (Phase 2)
    if (response.data.signature) {
      const payload = { ...response.data }
      delete payload.signature
      delete payload.verified
      
      // Verify signature
      try {
        const verifyResponse = await axios.post(`${INTEGRITY_API}/api/integrity/verify`, {
          ...payload,
          signature: response.data.signature
        })
        
        if (!verifyResponse.data.verified) {
          console.error('🚨 SIGNATURE VERIFICATION FAILED - Possible tampering!')
          // Only add flag if it doesn't already exist (prevent duplicates)
          const currentFlags = integrity.value.flags || []
          if (!currentFlags.includes('signature_invalid')) {
            integrity.value.flags = [...currentFlags, 'signature_invalid']
          }
        } else {
          console.log('✅ Signature verified')
          lastServerSignature = response.data.signature
        }
      } catch (verifyError) {
        console.warn('⚠️ Could not verify signature:', verifyError)
      }
    }
    
    // Store chain head
    if (response.data.chain_head) {
      lastChainHead = response.data.chain_head
      console.log('🔗 Chain head updated:', lastChainHead?.substring(0, 16) + '...')
    }
    
    // CRITICAL FIX: Merge server response into CURRENT integrity state
    // instead of building a replacement object. This prevents race conditions
    // where a periodic ingest that started before updateStore() but finished
    // after it would overwrite the scores with stale null values.
    // Only add server-specific fields; NEVER touch scores/mix/flags/lastAnalyzed.
    const current = integrity.value || {}
    integrity.value = {
      ...current,
      active: true,
      serverSignature: lastServerSignature,
      chainHead: lastChainHead,
      chainValid: response.data.chain_valid,
      extSpans: current.extSpans || response.data.ext_spans || []
    }
    
    console.log('✅ Updated integrity state:', {
      trust: integrity.value?.scores?.trust,
      composition: integrity.value?.scores?.composition,
      mix: integrity.value?.mix,
      flags: integrity.value?.flags
    })
    
    // Force UI update with multiple methods
    // CRITICAL: Do NOT include scores in the event - scores should only come from Analyze button
    const safeEventData = { ...response.data }
    delete safeEventData.scores
    delete safeEventData.mix
    window.dispatchEvent(new CustomEvent('integrity-update', { detail: safeEventData }))
    
    // Trigger Vue reactivity
    nextTick(() => {
      console.log('🔄 Force re-render triggered')
    })
    
  } catch (error) {
    console.error('❌ Failed to send integrity events:', error)
    console.error('Error details:', error.response?.data)
  }
}

// Dynamically import KaTeX styles
onMounted(async () => {
  const katexStyleElement = document.querySelector('#katex-style')
  if (
    katexStyleElement === null &&
    !options.value.toolbar.disableMenuItems.includes('math')
  ) {
    const style = document.createElement('link')
    style.href = `${options.value.cdnUrl}/libs/katex/katex.min.css`
    style.rel = 'stylesheet'
    style.id = 'katex-style'
    document.querySelector('head').append(style)
  }
  
  // Set up integrity event listeners - check for session in URL OR auto-create
  const urlParams = new URLSearchParams(window.location.search)
  let sessionId = urlParams.get('session')
  
  console.log('🔍 URL params session:', sessionId)
  console.log('🔍 Current integrity state:', integrity.value)
  
  // --- Loophole #6 Fix: Compute lightweight device fingerprint ---
  function _computeDeviceFingerprint() {
    const parts = [
      screen.width + 'x' + screen.height,
      screen.colorDepth,
      Intl.DateTimeFormat().resolvedOptions().timeZone,
      navigator.language,
      navigator.platform,
      navigator.hardwareConcurrency || 'unknown'
    ]
    // Simple hash
    let hash = 0
    const str = parts.join('|')
    for (let i = 0; i < str.length; i++) {
      hash = ((hash << 5) - hash + str.charCodeAt(i)) | 0
    }
    return 'df-' + Math.abs(hash).toString(36)
  }
  const deviceFingerprint = _computeDeviceFingerprint()
  
  // ALWAYS ACTIVATE INTEGRITY TRACKING - auto-create session if needed
  if (!sessionId && !integrity.value?.sessionId) {
    // Auto-create a session for tracking
    console.log('🆕 No session found - auto-creating session for tracking')
    sessionId = 'auto-' + Date.now() + '-' + Math.random().toString(36).substr(2, 9)
    
    // Also start a backend session
    try {
      // Use assignment_id as stable doc_id (enables cross-browser session lookup)
      const _assignmentId = new URLSearchParams(window.location.search).get('assignment_id')
      const response = await axios.post(`${INTEGRITY_API}/api/integrity/session/start`, {
        strict_mode: false,
        doc_id: _assignmentId || integrity.value?.docId || 'doc-' + Date.now(),
        device_fingerprint: deviceFingerprint
      })
      if (response.data.session_id) {
        sessionId = response.data.session_id
        console.log('✅ Backend session created:', sessionId)
      }
    } catch (error) {
      console.warn('⚠️ Could not create backend session, using local tracking:', error)
    }
  }
  
  // Always initialize integrity tracking
  // CRITICAL: If integrity already has a sessionId (from a previous mount / restored state),
  // reuse it to avoid triggering the sessionId watcher which resets all databases.
  const effectiveSessionId = integrity.value?.sessionId || sessionId
  console.log('✅ Activating integrity tracking with session:', effectiveSessionId, '(url:', sessionId, ', existing:', integrity.value?.sessionId, ')')
  if (!integrity.value) integrity.value = {}
  integrity.value.active = true
  integrity.value.sessionId = effectiveSessionId
  integrity.value.deviceFingerprint = deviceFingerprint
  integrity.value.docId = integrity.value.docId || 'doc-' + Date.now()
  
  // CRITICAL FIX: Only initialize default values if they don't exist
  // This prevents resetting scores when component re-mounts
  if (!integrity.value.scores || !integrity.value.lastAnalyzed) {
    integrity.value.scores = integrity.value.scores || { trust: 100, composition: 100 }
    integrity.value.mix = integrity.value.mix || { typed: 1.0, internal: 0, external: 0 }
    integrity.value.flags = integrity.value.flags || []
    integrity.value.extSpans = integrity.value.extSpans || []
  }
  
  // CRITICAL: Preserve lastAnalyzed timestamp if it exists
  // This ensures scores don't get reset by sendPendingIntegrityEvents
  console.log('✅ Integrity initialized and ACTIVE:', integrity.value)
  console.log('   Last analyzed:', integrity.value.lastAnalyzed ? new Date(integrity.value.lastAnalyzed).toLocaleString() : 'Never')
  
  // Set up integrity event listeners if session is active
  if (integrity?.value?.active || sessionId) {
    console.log('🔒 Integrity tracking ACTIVE for session:', sessionId || integrity.value.sessionId)
    
    const editorElement = editorInstance.view.dom
    
    // Track current cursor position
    let currentCursorPos = 0
    
    // Keydown events - capture before the editor processes them
    editorElement.addEventListener('keydown', (e) => {
      console.log('🔑 Key pressed:', e.key, 'Ctrl:', e.ctrlKey, 'Meta:', e.metaKey)
      
      // Get cursor position BEFORE the key is processed
      const { from } = editorInstance.state.selection
      currentCursorPos = from
      
      if (e.key === 'Backspace') {
        console.log('⌫⌫⌫ BACKSPACE DETECTED at position:', from)
        captureIntegrityEvent({ t: 'backspace', from_pos: from })
      } else if (e.key === 'Delete') {
        console.log('⌦⌦⌦ DELETE DETECTED at position:', from)
        captureIntegrityEvent({ t: 'delete', from_pos: from })
      } else if (e.key === 'Enter') {
        console.log('↵ Enter at position:', from)
        captureIntegrityEvent({ t: 'enter', from_pos: from })
      } else if (e.key.length === 1 && !e.ctrlKey && !e.metaKey && !e.altKey) {
        // Regular character typed
        console.log('✏️ Typing character:', e.key)
        captureIntegrityEvent({ t: 'key', k: e.key, from_pos: from })
      }
    })
    
    // Paste event - CRITICAL: Must capture before TipTap processes it
    editorElement.addEventListener('paste', (e) => {
      console.log('📋📋📋 PASTE EVENT DETECTED!')
      const { from } = editorInstance.state.selection
      const text = e.clipboardData?.getData('text/plain') || ''
      const snippet = text.substring(0, 4096) // Cap at 4KB
      
      console.log('📋 Paste details:')
      console.log('   Length:', text.length)
      console.log('   From pos:', from)
      console.log('   Preview:', snippet.substring(0, 100))
      console.log('   Full text:', text)
      
      if (text.length > 0) {
        captureIntegrityEvent({ 
          t: 'paste', 
          len: text.length,
          snippet: snippet,
          from_pos: from
        })
        console.log('✅ Paste event captured and queued')
      } else {
        console.warn('⚠️ Paste event had no text!')
      }
    }, true)  // Use capture phase to ensure we get it first
    
    // Copy event
    editorElement.addEventListener('copy', () => {
      console.log('📄📄📄 COPY EVENT DETECTED!')
      const { from, to } = editorInstance.state.selection
      const selectedText = editorInstance.state.doc.textBetween(from, to, ' ')
      console.log('📄 Copy details:')
      console.log('   Length:', selectedText.length)
      console.log('   From:', from, 'To:', to)
      console.log('   Text:', selectedText.substring(0, 100))
      
      if (selectedText.length > 0) {
        captureIntegrityEvent({ 
          t: 'copy',
          from_pos: from,
          to_pos: to,
          snippet: selectedText.substring(0, 4096)
        })
        console.log('✅ Copy event captured')
      }
    }, true)
    
    // Cut event
    editorElement.addEventListener('cut', () => {
      console.log('✂️✂️✂️ CUT EVENT DETECTED!')
      const { from, to } = editorInstance.state.selection
      const selectedText = editorInstance.state.doc.textBetween(from, to, ' ')
      console.log('✂️ Cut details - From:', from, 'To:', to, 'Length:', selectedText.length)
      console.log('✂️ Text being cut:', selectedText.substring(0, 100))
      captureIntegrityEvent({ 
        t: 'cut',
        from_pos: from,
        to_pos: to,
        snippet: selectedText.substring(0, 4096)
      })
    })
    
    // Selection change - track cursor position
    editorInstance.on('selectionUpdate', ({ editor }) => {
      const { from, to } = editor.state.selection
      if (from !== lastCursorPos) {
        captureIntegrityEvent({ 
          t: 'sel',
          from_pos: from,
          to_pos: to
        })
        lastCursorPos = from
        currentCursorPos = from
      }
    })
    
    console.log('✅ Event listeners attached to editor')
    
    // Start periodic updates
    startPeriodicUpdates()
  }
})

// Cleanup on unmount
onBeforeUnmount(() => {
  if (periodicUpdateTimer) {
    clearInterval(periodicUpdateTimer)
    console.log('🛑 Periodic updates stopped')
  }
})

// The pagePlugin registration has been completely removed.

// Bubble menu logic
let tippyInstance = $ref(null)
const tippyOpitons = $ref({
  appendTo: 'parent',
  maxWidth: 580,
  zIndex: 99,
  onShow(instance) {
    tippyInstance = instance
  },
  onHide() {
    assistant.value = false
  },
  onDestroy() {
    tippyInstance = null
  },
})

// AI Assistant logic
watch(
  () => assistant.value,
  (visible) => {
    tippyInstance?.setProps({
      placement: visible ? 'bottom' : 'top',
    })
  },
)

// Destroy editor instance (+ collab provider / Y.Doc when enabled)
onBeforeUnmount(() => {
  editorInstance.destroy()
  if (collabProvider) {
    try {
      collabProvider.awareness?.off('change', _emitCollabPresence)
    } catch (e) { /* ignore */ }
    try {
      collabProvider.destroy()
    } catch (e) {
      console.warn('collab provider destroy failed:', e)
    }
    collabProvider = null
  }
  if (ydoc) {
    try {
      ydoc.destroy()
    } catch (e) { /* ignore */ }
    ydoc = null
  }
})
</script>

<style lang="less">
@import '@/assets/styles/editor.less';
@import '@/assets/styles/drager.less';

/* New CSS for the 'Infinite Canvas' look */
/* CORRECT SELECTOR - No space means an element with BOTH classes */
.umo-editor.ProseMirror {
  max-width: 680px;
  margin: 2rem auto;
  padding: 4rem;
  background: white; /* This should now apply correctly */
  box-shadow: 0 0 10px rgba(0, 0, 0, 0.1);
  border-radius: 8px;
  height: auto;
  min-height: 1122px;
}

/* Glassmorphism bubble menu styles */
.umo-editor-bubble-menu {
  border-radius: 18px;
  display: flex;
  align-items: center;
  flex-wrap: wrap;

  &:not(.assistant) {
    padding: 10px 14px;
    background: rgba(255, 255, 255, 0.12);
    backdrop-filter: blur(18px) saturate(160%);
    -webkit-backdrop-filter: blur(18px) saturate(160%);
    border: 1px solid rgba(255, 255, 255, 0.35);
    box-shadow: 0 10px 30px rgba(0, 0, 0, 0.12);
    transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
    
    &:hover {
      background: rgba(255, 255, 255, 0.18);
      box-shadow: 0 15px 40px rgba(0, 0, 0, 0.15);
      transform: translateY(-2px);
    }
  }

  &:empty {
    display: none;
  }

  .menu-button {
    position: relative;
    transition: all 0.2s cubic-bezier(0.4, 0, 0.2, 1);
    border-radius: 12px;
    overflow: hidden;
    
    /* Light mode styling for regular menu buttons (not custom bubble buttons) */
    &:not(.bubble-btn) {
      background: rgba(255, 255, 255, 0.9) !important;
      color: black !important;
      border: 1px solid rgba(0, 0, 0, 0.1) !important;
      
      .button-content {
        color: black !important;
        
        .text {
          color: black !important;
        }
        
        .icon {
          color: black !important;
        }
      }
    }
    
    &:hover {
      transform: scale(1.05);
      
      &:not(.bubble-btn) {
        background: rgba(255, 255, 255, 1) !important;
      }
      
      &.bubble-btn {
        background: rgba(255, 255, 255, 0.35);
      }
    }
    
    &:active {
      transform: scale(0.98);
    }
    
    &.show-text .button-content .text {
      display: none !important;
    }
    
    &.huge {
      height: var(--td-comp-size-xs);
      min-width: unset;

      .button-content {
        min-width: unset !important;

        .icon {
          font-size: 16px;
          margin-top: 0;
        }
      }
    }
  }
}

.umo-editor-block-menu {
  .menu-button {
    color: var(--umo-text-color-light) !important;
  }
}


</style>