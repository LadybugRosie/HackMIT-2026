export function fmtDate(ms) {
  if (!ms) return '—'
  return new Date(ms).toLocaleString(undefined, { month: 'short', day: 'numeric', hour: 'numeric', minute: '2-digit' })
}

export function dueLabel(ms) {
  if (!ms) return 'No due date'
  const diff = ms - Date.now()
  const days = Math.round(diff / 86_400_000)
  if (diff < 0) return `Due ${fmtDate(ms)} (past due)`
  if (days === 0) return `Due today, ${fmtDate(ms)}`
  if (days === 1) return `Due tomorrow, ${fmtDate(ms)}`
  return `Due ${fmtDate(ms)}`
}

export const STATUS_LABEL = {
  not_started: 'Not started', draft: 'In progress', submitted: 'Submitted', graded: 'Graded', returned: 'Returned',
}

/** datetime-local <input> value ↔ epoch ms */
export function msToLocalInput(ms) {
  if (!ms) return ''
  const d = new Date(ms)
  const pad = (n) => String(n).padStart(2, '0')
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}T${pad(d.getHours())}:${pad(d.getMinutes())}`
}
export function localInputToMs(value) {
  return value ? new Date(value).getTime() : null
}
