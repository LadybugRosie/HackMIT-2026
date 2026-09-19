import { Table } from '@tiptap/extension-table'
import { getId } from '../page/core'

export default Table.extend({
  content: 'tableRow*',
  
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
    }
  },

  addCommands() {
    return {
      ...this.parent?.(),
      insertTable: ({ rows, cols, withHeaderRow }) => ({ commands, state, tr }) => {
        // Create table with proper IDs and structure
        const tableRows = []
        
        for (let rowIndex = 0; rowIndex < rows; rowIndex++) {
          const cells = []
          const isHeaderRow = withHeaderRow && rowIndex === 0
          
          for (let colIndex = 0; colIndex < cols; colIndex++) {
            const cellType = isHeaderRow ? 'tableHeader' : 'tableCell'
            const cellNode = state.schema.nodes[cellType].create(
              { id: getId() },
              state.schema.nodes.paragraph.create({ id: getId() })
            )
            cells.push(cellNode)
          }
          
          const rowNode = state.schema.nodes.tableRow.create({ id: getId() }, cells)
          tableRows.push(rowNode)
        }
        
        const tableNode = state.schema.nodes.table.create(
          { id: getId() },
          tableRows
        )
        
        return commands.insertContent(tableNode)
      },
    }
  },

  addPasteRules() {
    return [
      {
        find: /<table[^>]*>([\s\S]*?)<\/table>/gi,
        handler: ({ state, range, match }) => {
          const { tr, schema } = state
          const [, tableContent] = match
          
          // Parse table rows from HTML
          const tempDiv = document.createElement('div')
          tempDiv.innerHTML = `<table>${tableContent}</table>`
          const table = tempDiv.querySelector('table')
          
          if (!table) return
          
          const rows = Array.from(table.querySelectorAll('tr'))
          const tableRows = []
          
          rows.forEach((row, rowIndex) => {
            const cells = Array.from(row.querySelectorAll('td, th'))
            const tableCells = []
            
            cells.forEach((cell, cellIndex) => {
              const isHeader = cell.tagName.toLowerCase() === 'th'
              const cellType = isHeader ? 'tableHeader' : 'tableCell'
              
              // Create paragraph with cell content
              const cellText = cell.textContent || ''
              const paragraphNode = cellText.trim() 
                ? schema.nodes.paragraph.create(
                    { id: getId() },
                    cellText ? schema.text(cellText) : undefined
                  )
                : schema.nodes.paragraph.create({ id: getId() })
              
              const cellNode = schema.nodes[cellType].create(
                { 
                  id: getId(),
                  colspan: cell.getAttribute('colspan') ? parseInt(cell.getAttribute('colspan')) : null,
                  rowspan: cell.getAttribute('rowspan') ? parseInt(cell.getAttribute('rowspan')) : null
                },
                paragraphNode
              )
              
              tableCells.push(cellNode)
            })
            
            if (tableCells.length > 0) {
              const rowNode = schema.nodes.tableRow.create({ id: getId() }, tableCells)
              tableRows.push(rowNode)
            }
          })
          
          if (tableRows.length > 0) {
            const tableNode = schema.nodes.table.create({ id: getId() }, tableRows)
            tr.replaceWith(range.from, range.to, tableNode)
          }
        }
      }
    ]
  }
})
