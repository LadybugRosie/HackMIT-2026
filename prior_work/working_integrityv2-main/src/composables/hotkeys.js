import hotkeys from 'hotkeys-js'

export const useHotkeys = (keys, callback) => {
  hotkeys.filter = () => true
  hotkeys(keys, (e) => {
    // Only prevent default if callback returns true or undefined
    // Allow callback to return false to let browser handle the event naturally
    const result = callback()
    if (result !== false) {
      e.preventDefault()
    }
    return result !== false
  })
}
