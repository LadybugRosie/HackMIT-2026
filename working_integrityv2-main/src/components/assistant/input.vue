<template>
  <div class="assistant-container">
    <div class="assistant-input">
      <div class="ai-icon">
        <icon name="assistant" />
      </div>
      <t-textarea
        ref="inputRef"
        class="input"
        v-model="command"
        :maxlength="options.assistant.maxlength"
        :readonly="generating"
        autocomplete="false"
        :placeholder="t('assistant.placeholder')"
        autosize
      />
      <div v-if="command !== ''" class="submit">
        <t-button
          theme="primary"
          :disabled="generating"
          :loading="generating"
          @click="send"
        >
          <span v-if="!generating" v-text="t('assistant.send')"></span>
        </t-button>
      </div>
    </div>
    <div class="assistant-result">
      <div class="close">
        <tooltip :content="t('assistant.exit')">
          <t-button
            v-if="!generating"
            size="small"
            variant="text"
            shape="square"
            theme="default"
            @click="exitAssistant"
          >
            <icon name="exit" size="14" />
          </t-button>
        </tooltip>
      </div>
      <div class="commands-container">
        <div class="title" v-text="t('assistant.commands')"></div>
        <div class="commands">
          <t-button
            v-for="(item, index) in options.assistant.commands"
            :key="index"
            size="small"
            variant="outline"
            theme="default"
            v-text="l(item.label)"
            @click="insertCommand(item)"
          />
        </div>
      </div>
      <div class="result-container" v-if="result.content !== ''">
        <div class="title" v-text="t('assistant.result')"></div>
        <div
          class="result editor-container"
          :class="{ error: result.error }"
          v-html="result.content"
        />
        <div class="actions">
          <div v-if="!result.error" class="main">
            <t-button theme="primary" @click="replaceContent">
              <icon name="check" />
              {{ t('assistant.replace') }}
            </t-button>
            <t-button variant="outline" theme="default" @click="insertContentAtAfter">
              <icon name="table-add-column-before" />
              {{ t('assistant.insertAfter') }}
            </t-button>
            <t-button variant="outline" theme="default" @click="insertContentAtBelow">
              <icon name="table-add-row-after" />
              {{ t('assistant.insertBelow') }}
            </t-button>
          </div>
          <div class="secondary">
            <tooltip v-if="!result.error" :content="t('assistant.copy')">
              <t-button variant="text" shape="square" theme="default" @click="copyResult">
                <icon name="copy" />
              </t-button>
            </tooltip>
            <tooltip :content="t('assistant.rewrite')">
              <t-button variant="text" shape="square" theme="default" @click="rewrite">
                <icon name="reload" />
              </t-button>
            </tooltip>
            <tooltip :content="t('assistant.delete')">
              <t-button variant="text" shape="square" theme="default" @click="deleteResult">
                <icon name="node-delete" />
              </t-button>
            </tooltip>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import i18n from '@/i18n'
const { options, editor, assistant } = useStore()

const inputRef = $ref(null)
let command = $ref('')
let result = $ref({ prompt: '', content: '', error: false })
let generating = $ref(false)
let lastUsed = 0

const blockedKeywords = ['kill', 'bomb', 'hate', 'suicide']

const isRateLimited = () => Date.now() - lastUsed < 5000
const isAbusive = (text) => blockedKeywords.some((word) => text.toLowerCase().includes(word))

const send = async () => {
  if (isRateLimited()) {
    result.error = true
    result.content = '[ERROR]: Too many requests. Please wait a moment.'
    return
  }

  if (isAbusive(command)) {
    result.error = true
    result.content = '[ERROR]: Inappropriate content detected.'
    return
  }

  generating = true
  result.error = false
  result.prompt = ''
  result.content = ''
  lastUsed = Date.now()

  const selectedText = editor.value.commands.getSelectionText()
  const promptText = command

  try {
    // Proxy through backend to keep API key secure (never expose in frontend)
    const { getApiUrl } = await import('@/utils/api-url')
    const apiUrl = getApiUrl()
    const authToken = localStorage.getItem('auth_token')

    const res = await fetch(
      `${apiUrl}/api/auth/assistant/chat`,
      {
        method: 'POST',
        headers: { 
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${authToken}`
        },
        body: JSON.stringify({
          prompt: promptText,
          selected_text: selectedText,
          max_tokens: 1000
        }),
      }
    )

    const json = await res.json()
    const reply = json?.content || json?.detail || 'No response from AI assistant.'

    result.content = reply
    result.command = command
    generating = false
  } catch (err) {
    console.error(err)
    generating = false
    result.error = true
    result.content = '[ERROR]: AI assistant call failed.'
  }
}

const insertCommand = ({ value, autoSend }) => {
  command = l(value)
  result.command = l(value)
  result.content = ''
  inputRef.focus()
  if (autoSend !== false) send()
}

const exitAssistant = () => {
  assistant.value = false
  editor.value.commands.focus()
}

const replaceContent = () => {
  const selectedText = editor.value.commands.getSelectionText()

  if (!selectedText) {
    useMessage('error', 'Please select text to replace.')
    return
  }

  editor.value.commands.insertContent(result.content)
  exitAssistant()
}


const insertContentAtAfter = () => {
  const { to } = editor.value.state.selection
  editor.value.chain().insertContentAt(to, result.content).focus().run()
  exitAssistant()
}

const insertContentAtBelow = () => {
  editor.value.commands.selectParentNode()
  const { to } = editor.value.state.selection
  editor.value.chain().insertContentAt(to, result.content).focus().run()
  exitAssistant()
}

const copyResult = () => {
  const { copy } = useClipboard({ source: ref(result.content) })
  copy()
  useMessage('success', t('assistant.copySuccess'))
}

const rewrite = () => {
  command = result.command
  send()
}

const deleteResult = () => {
  command = ''
  result.prompt = ''
  result.content = ''
}
</script>

<style lang="less" scoped>
.assistant-container {
  position: relative;
  z-index: 1000;
  background: var(--td-bg-color-container);
  border: 1px solid var(--td-border-level-1-color);
  border-radius: 8px;
  box-shadow: 0 4px 16px rgba(0, 0, 0, 0.3);
  width: 90vw;
  max-width: 600px;
  max-height: 80vh;
  overflow: hidden;
  display: flex;
  flex-direction: column;
}

.assistant-input {
  display: flex;
  align-items: flex-start;
  gap: 8px;
  padding: 16px;
  border-bottom: 1px solid var(--td-border-level-1-color);
  background: var(--td-bg-color-container);
}

.ai-icon {
  flex-shrink: 0;
  margin-top: 8px;
  color: var(--td-text-color-secondary);
}

.input {
  flex: 1;
  min-height: 80px;
  max-height: 200px;
  resize: none;
}

.submit {
  flex-shrink: 0;
  margin-top: 8px;
}

.assistant-result {
  flex: 1;
  overflow-y: auto;
  padding: 16px;
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.close {
  position: absolute;
  top: 8px;
  right: 8px;
  z-index: 1001;
}

.commands-container, .result-container {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.title {
  font-weight: 600;
  color: var(--td-text-color-primary);
  font-size: 14px;
}

.commands {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.result {
  background: var(--td-bg-color-component);
  border: 1px solid var(--td-border-level-1-color);
  border-radius: 6px;
  padding: 12px;
  font-family: var(--td-font-family-mono);
  font-size: 14px;
  line-height: 1.5;
  white-space: pre-wrap;
  word-break: break-word;
  max-height: 300px;
  overflow-y: auto;

  &.error {
    background: var(--td-error-color-1);
    border-color: var(--td-error-color-3);
    color: var(--td-error-color-7);
  }
}

.actions {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 8px;
  margin-top: 8px;
}

.main {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
}

.secondary {
  display: flex;
  gap: 4px;
}

@media (max-width: 768px) {
  .assistant-container {
    width: 95vw;
    max-height: 70vh;
  }
  
  .actions {
    flex-direction: column;
    align-items: stretch;
  }
  
  .main {
    justify-content: center;
  }
  
  .secondary {
    justify-content: center;
  }
}
</style>
