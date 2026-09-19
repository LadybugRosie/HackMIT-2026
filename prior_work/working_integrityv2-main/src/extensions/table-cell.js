import TableCell from '@tiptap/extension-table-cell'
import { getId } from './page/core'

export default TableCell.extend({
  addAttributes() {
    return {
      ...this.parent?.(),
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
      align: {
        default: null,
        parseHTML: (element) => element.getAttribute('data-align'),
        renderHTML: ({ align }) => ({ 'data-align': align }),
      },
      backgroundColor: {
        default: null,
        parseHTML: (element) => element.getAttribute('data-bg-color'),
        renderHTML: ({ backgroundColor }) => {
          const attrs = {
            'data-bg-color': backgroundColor,
          }
          if (backgroundColor) {
            attrs.style = `background-color: ${backgroundColor}`
          }
          return attrs
        },
      },
    }
  },
  
  onCreate() {
    if (!this.options.id) {
      this.options.id = getId()
    }
  },
})
