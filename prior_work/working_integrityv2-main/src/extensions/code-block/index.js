import { Node, mergeAttributes } from '@tiptap/core'
import { VueNodeViewRenderer } from '@tiptap/vue-3'
import NodeView from './node-view.vue'

export default Node.create({
  name: 'codeBlock',
  group: 'block',
  atom: true,
  addAttributes() {
    return {
      vnode: {
        default: true,
      },
      code: {
        default: '',
      },
      language: {
        default: 'plaintext',
      },
      theme: {
        default: 'light',
      },
      lineNumbers: {
        default: true,
      },
      wordWrap: {
        default: false,
      },
    }
  },
  parseHTML() {
    return [
      { 
        tag: 'pre',
        getAttrs: (element) => {
          // Extract code content from nested <code> tag if it exists
          const codeElement = element.querySelector('code')
          const codeContent = codeElement ? codeElement.textContent : element.textContent
          
          // Try to detect language from class attributes
          let language = 'plaintext'
          const classList = (codeElement?.className || element.className || '').split(' ')
          for (const className of classList) {
            if (className.startsWith('language-')) {
              language = className.replace('language-', '')
              break
            } else if (className.startsWith('lang-')) {
              language = className.replace('lang-', '')
              break
            }
          }
          
          return {
            code: codeContent || '',
            language: language
          }
        }
      }
    ]
  },
  renderHTML({ HTMLAttributes }) {
    return ['pre', mergeAttributes(this.options.HTMLAttributes, HTMLAttributes)]
  },
  addNodeView() {
    return VueNodeViewRenderer(NodeView)
  },
  addCommands() {
    return {
      setCodeBlock:
        (options) =>
        ({ commands }) => {
          return commands.insertContent({
            type: this.name,
            attrs: options,
          })
        },
    }
  },
  addKeyboardShortcuts() {
    return {
      'Mod-Alt-c': () => this.editor.commands.setCodeBlock(),
    }
  },
  addPasteRules() {
    return [
      // Handle pre+code blocks from ChatGPT and other sources
      {
        find: /<pre[^>]*>\s*<code[^>]*>([\s\S]*?)<\/code>\s*<\/pre>/gi,
        handler: ({ state, range, match }) => {
          const { tr } = state
          const start = range.from
          const end = range.to
          
          // Extract content and try to detect language
          const fullMatch = match[0]
          const codeContent = match[1]
          let language = 'plaintext'
          
          // Try to extract language from class attributes
          const codeMatch = fullMatch.match(/<code[^>]*class="[^"]*(?:language-|lang-)([^"\s]+)[^"]*"[^>]*>/)
          if (codeMatch) {
            language = codeMatch[1]
          } else {
            const preMatch = fullMatch.match(/<pre[^>]*class="[^"]*(?:language-|lang-)([^"\s]+)[^"]*"[^>]*>/)
            if (preMatch) {
              language = preMatch[1]
            }
          }
          
          // Create code block node
          const codeBlock = this.type.create({
            code: codeContent.trim(),
            language: language
          })
          
          tr.replaceWith(start, end, codeBlock)
        }
      },
      // Handle standalone pre blocks (fallback)
      {
        find: /<pre[^>]*>(?!.*<code)([\s\S]*?)<\/pre>/gi,
        handler: ({ state, range, match }) => {
          const { tr } = state
          const start = range.from
          const end = range.to
          
          const codeContent = match[1]
          let language = 'plaintext'
          
          // Try to extract language from pre class
          const preMatch = match[0].match(/<pre[^>]*class="[^"]*(?:language-|lang-)([^"\s]+)[^"]*"[^>]*>/)
          if (preMatch) {
            language = preMatch[1]
          }
          
          const codeBlock = this.type.create({
            code: codeContent.trim(),
            language: language
          })
          
          tr.replaceWith(start, end, codeBlock)
        }
      }
    ]
  },
})