// FILE: src/extensions/paste‑enhance.js
import { Extension } from '@tiptap/core'
import { Plugin, PluginKey } from '@tiptap/pm/state'
import { Slice, Fragment } from '@tiptap/pm/model'
import { getId } from './page/core'
import DOMPurify from 'dompurify'
import debounce from 'lodash.debounce'

// Helper function to find optimal start position for cursor
function findOptimalStartPosition(doc) {
  if (!doc || doc.content.size === 0) {
    return 1
  }
  
  // For page-based documents
  if (doc.firstChild && doc.firstChild.type.name === 'page') {
    const firstPage = doc.firstChild
    if (firstPage.content && firstPage.content.size > 0) {
      // Find first editable position in the page
      let pos = 2 // Start after page opening
      for (let i = 0; i < firstPage.content.childCount; i++) {
        const child = firstPage.content.child(i)
        if (child.isTextblock && child.type.name !== 'codeBlock') {
          return pos + 1 // Position inside the text block
        }
        pos += child.nodeSize
      }
      return 2 // Default to start of page if no text blocks found
    }
    return 2 // Empty page
  }
  
  // For regular documents, find first text block
  for (let i = 0; i < doc.childCount; i++) {
    const child = doc.child(i)
    if (child.isTextblock && child.type.name !== 'codeBlock') {
      return Math.max(1, i + 1)
    }
  }
  
  return 1 // Fallback
}




function removeExtraPageBreaks(content, schema) {
  const nodes = []
  content.forEach(node => {
    if (node.type.name === 'pagination') return
    if (node.content && node.content.size) {
      nodes.push(node.copy(removeExtraPageBreaks(node.content, schema)))
    } else {
      nodes.push(node)
    }
  })
  return Fragment.from(nodes)
}

function transformHorizontalRules(content, schema) {
  const pageBreakType = schema.nodes.pagination
  if (!pageBreakType) return content
  const cleaned = removeExtraPageBreaks(content, schema)
  return Fragment.from(
    cleaned.map(node => {
      if (
        node.type.name === 'horizontalRule' ||
        (node.type.name === 'paragraph' && /^---+\s*$/.test(node.textContent))
      ) {
        return pageBreakType.create({ id: getId() })
      }
      if (node.content && node.content.size) {
        return node.copy(transformHorizontalRules(node.content, schema))
      }
      return node
    })
  )
}

function preserveListStructure(content, schema) {
  const nodes = []
  content.forEach(node => {
    if (node.type.name === 'bulletList' || node.type.name === 'orderedList') {
      const items = []
      node.content.forEach(item => {
        if (item.type.name === 'listItem') {
          items.push(item.copy(item.content))
        }
      })
      nodes.push(node.copy(Fragment.from(items)))
    } else if (node.content && node.content.size) {
      nodes.push(node.copy(preserveListStructure(node.content, schema)))
    } else {
      nodes.push(node)
    }
  })
  return Fragment.from(nodes)
}

function preserveTableStructure(content, schema) {
  const nodes = []
  content.forEach(node => {
    if (node.type.name === 'table') {
      // Ensure table has proper structure
      const rows = []
      node.content.forEach(row => {
        if (row.type.name === 'tableRow') {
          const cells = []
          row.content.forEach(cell => {
            if (cell.type.name === 'tableCell' || cell.type.name === 'tableHeader') {
              // Ensure cell has content, add empty paragraph if needed
              const cellContent = cell.content.size > 0 ? cell.content : 
                Fragment.from([schema.nodes.paragraph.create()])
              cells.push(cell.copy(cellContent))
            }
          })
          if (cells.length > 0) {
            rows.push(row.copy(Fragment.from(cells)))
          }
        }
      })
      if (rows.length > 0) {
        nodes.push(node.copy(Fragment.from(rows)))
      }
    } else if (node.content && node.content.size) {
      nodes.push(node.copy(preserveTableStructure(node.content, schema)))
    } else {
      nodes.push(node)
    }
  })
  return Fragment.from(nodes)
}

function preserveCodeWhitespace(content) {
  const nodes = []
  content.forEach(node => {
    if (node.type.name === 'codeBlock' || node.type.name === 'paragraph') {
      nodes.push(node.copy(node.content))
    } else if (node.content && node.content.size) {
      nodes.push(node.copy(preserveCodeWhitespace(node.content)))
    } else {
      nodes.push(node)
    }
  })
  return Fragment.from(nodes)
}

function addNodeIds(content) {
  const nodes = []
  content.forEach(node => {
    const attrs = node.attrs && typeof node.attrs === 'object' ? node.attrs : {}
    if (attrs.id) {
      nodes.push(node.copy(node.content))
    } else if (node.attrs && typeof node.attrs === 'object') {
      const newAttrs = { ...attrs, id: getId() }
      nodes.push(node.type.create(newAttrs, node.content, node.marks))
    } else if (node.content && node.content.size) {
      nodes.push(node.copy(addNodeIds(node.content)))
    } else {
      nodes.push(node)
    }
  })
  return Fragment.from(nodes)
}


const PasteEnhancePlugin = ({ editor, options }) => {
  // a stable debounced insert so rapid pastes collapse into one
  const debouncedInsert = debounce((cleanHtml) => {
    editor.commands.insertContent(cleanHtml)
    // after insert, re-run pagination
    const tr = editor.state.tr.setMeta('runPaginationOnUpdate', true)
    editor.view.dispatch(tr)
  }, options.debounceMs)

  // Simple large content check
  const isLargeContent = (content) => {
    try {
      const text = typeof content === 'string' ? content : content.textContent || ''
      return text.length > 25000 // 25k character threshold
    } catch (error) {
      return false
    }
  }

  // Safe large content handler - much simpler approach
  const handleLargeContent = async (content, editor, position = null) => {
    try {
      const text = typeof content === 'string' ? content : content.textContent || ''
      
      // For very large content, truncate to prevent crashes
      if (text.length > 100000) {
        console.log('Content too large, truncating for safety')
        const safeContent = text.substring(0, 100000) + '\n\n[Content truncated due to size - original was ' + Math.round(text.length/1000) + 'k characters]'
        content = safeContent
      }

      // Insert with a small delay to prevent blocking
      setTimeout(() => {
        try {
          if (position !== null) {
            editor.commands.insertContentAt(position, content)
          } else {
            editor.commands.setContent(content)
          }
        } catch (error) {
          console.error('Error inserting large content:', error)
        }
      }, 50)
      
      return true
    } catch (error) {
      console.error('Error in handleLargeContent:', error)
      return false
    }
  }

  return new Plugin({
    key: new PluginKey('paste‑enhance'),
    props: {
      handleDOMEvents: {
        paste: (view, event) => {
          try {
            event.preventDefault()

            // Get clipboard data
            const html = event.clipboardData.getData('text/html')
            const text = event.clipboardData.getData('text/plain')
            
            if (!html && !text) {
              return true
            }

          // Get current selection
          const { from, to, empty } = view.state.selection
          const docSize = view.state.doc.content.size

          // Handle different paste scenarios
          if (!empty && from === 0 && to === docSize) {
            // Full document replacement (Ctrl+A then paste)
            const content = html ? DOMPurify.sanitize(html, options.sanitizeOptions) : text.trim()
            
            // Check if content is large and needs special handling
            if (isLargeContent(content)) {
              console.log('Large content detected, using safe handler')
              handleLargeContent(content, editor)
              
              // Position cursor at end
              setTimeout(() => {
                try {
                  const doc = editor.view.state.doc
                  const endPos = doc.content.size
                  if (endPos > 0) {
                    const targetPos = Math.max(1, endPos - 1)
                    editor.commands.setTextSelection(targetPos)
                  }
                } catch (error) {
                  console.warn('Error positioning cursor after paste:', error)
                }
              }, 300)
            } else {
              // Normal handling for smaller content
              editor.commands.setContent(content)
              
              // Force pagination immediately after content is set
              setTimeout(() => {
                const tr = view.state.tr.setMeta('runPaginationOnUpdate', true)
                tr.setMeta('forcePagination', true)
                tr.setMeta('inserting', true)
                view.dispatch(tr)
                
                // Simple cursor positioning at the end
                setTimeout(() => {
                  try {
                    const doc = editor.view.state.doc
                    const endPos = doc.content.size
                    if (endPos > 0) {
                      const targetPos = Math.max(1, endPos - 1)
                      editor.commands.setTextSelection(targetPos)
                    }
                  } catch (error) {
                    console.warn('Error positioning cursor after paste:', error)
                  }
                }, 50)
              }, 5)
            }
          } else {
            // Partial insertion
            const content = text || html
            
            if (isLargeContent(content)) {
              // Handle large content insertion
              const cleanContent = html ? DOMPurify.sanitize(html, options.sanitizeOptions) : text
              
              console.log('Large content insertion detected')
              
              // Delete selected content first if any
              if (!empty) {
                const tr = view.state.tr.delete(from, to)
                view.dispatch(tr)
                
                setTimeout(() => {
                  const currentPos = view.state.selection.from
                  handleLargeContent(cleanContent, editor, currentPos)
                }, 10)
              } else {
                handleLargeContent(cleanContent, editor, from)
              }
            } else {
              // Normal handling for smaller content - keep original fast logic
              const tr = view.state.tr
              
              if (text && !html) {
                // Plain text - insert directly
                if (!empty) {
                  tr.replaceWith(from, to, view.state.schema.text(text))
                } else {
                  tr.insertText(text, from)
                }
                view.dispatch(tr)
              } else if (html) {
                // HTML content
                const cleanHtml = DOMPurify.sanitize(html, options.sanitizeOptions)
                
                if (!empty) {
                  tr.delete(from, to)
                  view.dispatch(tr)
                }
                
                // Insert content with minimal delay
                setTimeout(() => {
                  const currentPos = view.state.selection.from
                  editor.commands.insertContentAt(currentPos, cleanHtml)
                  
                  // Trigger pagination
                  setTimeout(() => {
                    const tr = view.state.tr.setMeta('runPaginationOnUpdate', true)
                    if (cleanHtml.includes('<table')) {
                      tr.setMeta('forcePagination', true)
                    }
                    view.dispatch(tr)
                  }, 10)
                }, 1)
              }
            }
          }

          // Update pagination after paste (only for non-chunked content)
          if (!isLargeContent(text || html || '')) {
            setTimeout(() => {
              const hasTable = html && html.includes('<table')
              const tr = view.state.tr.setMeta('runPaginationOnUpdate', true)
              if (hasTable) {
                tr.setMeta('forcePagination', true)
                tr.setMeta('checkPagination', true)
                tr.setMeta('inserting', true)
              }
              view.dispatch(tr)
            }, html && html.includes('<table') ? 100 : 10)
          }

          return true
          } catch (error) {
            console.warn('Error in paste handler:', error)
            // Fallback to browser default paste
            return false
          }
        },

        // keep your existing cut handler
        cut: (view, event) => {
          setTimeout(() => {
            const tr = view.state.tr.setMeta('checkPagination', true)
            view.dispatch(tr)
          }, 50)
          return false
        },
      },

      // these still run for programmatic pastes / transformPasted scenarios
      transformPasted: (slice, view) => {
        let content = slice.content
        content = transformHorizontalRules(content, view.state.schema)
        content = preserveListStructure(content, view.state.schema)
        content = preserveTableStructure(content, view.state.schema)
        content = preserveCodeWhitespace(content)
        content = addNodeIds(content)
        return new Slice(content, slice.openStart, slice.openEnd)
      },

      handlePaste: (view, event, slice) => {
        // default handling will run transformPasted then insert
        const scrollPos = view.dom.scrollTop
        const hasTable = slice.content.toString().includes('table')
        setTimeout(() => {
          const tr = view.state.tr.setMeta('checkPagination', true)
          // Force pagination recalculation if slice contains tables
          if (hasTable) {
            tr.setMeta('forcePagination', true)
          }
          view.dispatch(tr)
          view.dom.scrollTop = scrollPos
        }, hasTable ? 100 : 50)
        return false
      },
    },
  })
}

export default Extension.create({
  name: 'pasteEnhance',
  addOptions() {
    return {
      sanitizeOptions: {
        ALLOWED_TAGS: [
          'p','h1','h2','h3','h4','h5','h6',
          'strong','em','ul','ol','li','br','blockquote',
          'code','pre','a','img',
          'table','tbody','thead','tr','td','th',
          'div', 'span', 'b', 'i', 'u', 'sub', 'sup'
        ],
        ALLOWED_ATTR: [
          'href','src','alt','title','width','height','colspan','rowspan',
          'style','class','id','data-*','aria-*'
        ],
        ALLOW_DATA_ATTR: false,
        ALLOW_UNKNOWN_PROTOCOLS: false,
        ALLOWED_URI_REGEXP: /^(?:(?:(?:f|ht)tps?|mailto|tel|callto|cid|xmpp|xxx):|[^a-z]|[a-z+.\-]+(?:[^a-z+.\-:]|$))/i,
        FORBID_ATTR: ['onerror', 'onload', 'onclick', 'onmouseover'],
        FORBID_TAGS: ['script', 'object', 'embed', 'form', 'input', 'button'],
        KEEP_CONTENT: true,
        RETURN_DOM: false,
        RETURN_DOM_FRAGMENT: false,
        SANITIZE_DOM: true,
        WHOLE_DOCUMENT: false,
        FORCE_BODY: false,
      },
      debounceMs: 150,
    }
  },
  addProseMirrorPlugins() {
    return [PasteEnhancePlugin({ editor: this.editor, options: this.options })]
  },
  onUpdate() {
    if (this.editor.view) {
      const tr = this.editor.state.tr.setMeta('runPaginationOnUpdate', true)
      this.editor.view.dispatch(tr)
    }
  },
})