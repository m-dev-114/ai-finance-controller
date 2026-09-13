export function formatINR(amount) {
  if (amount === null || amount === undefined) return '—'
  const sign = amount < 0 ? '-' : ''
  const abs = Math.abs(amount)
  return `${sign}\u20b9${abs.toLocaleString('en-IN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`
}

export function formatRelativeTime(isoString) {
  if (!isoString) return '—'
  const then = new Date(isoString + (isoString.endsWith('Z') ? '' : 'Z'))
  const diffMs = Date.now() - then.getTime()
  const mins = Math.round(diffMs / 60000)
  if (mins < 1) return 'just now'
  if (mins < 60) return `${mins}m ago`
  const hours = Math.round(mins / 60)
  if (hours < 24) return `${hours}h ago`
  const days = Math.round(hours / 24)
  return `${days}d ago`
}

export function levelLabel(level) {
  return { transaction: 'Transaction', batch: 'Settlement batch', ledger: 'Ledger' }[level] || level
}

export function statusMeta(status) {
  switch (status) {
    case 'auto_cleared':
      return { label: 'Auto-cleared', color: 'var(--accent)', bg: 'var(--accent-soft)' }
    case 'needs_review':
      return { label: 'Needs review', color: 'var(--warn)', bg: 'var(--warn-soft)' }
    case 'resolved':
      return { label: 'Resolved', color: 'var(--muted)', bg: 'var(--paper-dim)' }
    case 'dismissed':
      return { label: 'Dismissed', color: 'var(--muted)', bg: 'var(--paper-dim)' }
    default:
      return { label: status, color: 'var(--muted)', bg: 'var(--paper-dim)' }
  }
}
