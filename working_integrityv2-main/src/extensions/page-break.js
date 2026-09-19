import { Node, mergeAttributes } from '@tiptap/core'
import { getId } from './page/core'

export default Node.create({
  name: 'pagination',
  group: 'block',
  
  addOptions() {
    return {
      HTMLAttributes: {
        class: 'page-break',
        'data-line-number': false,
        'data-content': 'Page Break',
      },
    }
  },
  
  addAttributes() {
    return {
      id: {
        default: null,
        parseHTML: element => element.getAttribute('id'),
        renderHTML: attributes => {
          if (!attributes.id) {
            return {}
          }
          return {
            id: attributes.id,
          }
        },
      },
    }
  },
  
  parseHTML() {
    return [
      { tag: 'div[class*="page-break"]' },
      { 
        tag: 'hr',
        getAttrs: (element) => {
          // Accept any HR tag as a potential page break
          return {}
        }
      },
      { tag: 'div[style*="page-break"]' },
      { tag: 'div[data-type="page-break"]' },
      // Handle various page break formats
      {
        tag: 'p',
        getAttrs: (element) => {
          const text = element.textContent || ''
          // Match markdown-style separators
          if (text.match(/^---+\s*$/) || text.match(/^\*\*\*+\s*$/) || text.match(/^___+\s*$/)) {
            return {}
          }
          return false
        }
      }
    ]
  },
  
  renderHTML({ HTMLAttributes }) {
    return ['div', mergeAttributes(this.options.HTMLAttributes, HTMLAttributes)]
  },
  
  addCommands() {
    return {
      setPageBreak:
        () =>
        ({ commands }) =>
          commands.insertContent({
            type: this.name,
            attrs: { id: getId() },
          }),
    }
  },
  
  addKeyboardShortcuts() {
    return {
      'Mod-Enter': () => this.editor.commands.setPageBreak(),
    }
  },
  
  addPasteRules() {
    return [
      // Convert pasted HR elements to page breaks
      {
        find: /<hr[^>]*>/gi,
        handler: ({ state, range, match }) => {
          const { tr } = state
          const start = range.from
          const end = range.to
          
          tr.replaceWith(start, end, this.type.create({ id: getId() }))
        }
      },
      // Convert markdown-style separators
      {
        find: /^(---+|___+|\*\*\*+)\s*$/gm,
        handler: ({ state, range, match }) => {
          const { tr } = state
          const start = range.from
          const end = range.to
          
          tr.replaceWith(start, end, this.type.create({ id: getId() }))
        }
      }
    ]
  }
})
