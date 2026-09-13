function Stat({ value, label }) {
  return (
    <div style={{ flex: 1, padding: '20px 28px' }}>
      <div style={{
        fontFamily: 'var(--font-mono)', fontSize: 28, fontWeight: 500,
        color: 'var(--ink)', lineHeight: 1.1,
      }}>
        {value}
      </div>
      <div style={{ marginTop: 6, fontSize: 13, color: 'var(--muted)' }}>{label}</div>
    </div>
  )
}

export default function MetricsStrip({ metrics }) {
  if (!metrics) return null

  const matchRates = metrics.match_rate_by_level || {}
  const overallMatch = ['transaction', 'batch', 'ledger']
    .map((k) => matchRates[k])
    .filter((v) => typeof v === 'number')
  const avgMatch = overallMatch.length
    ? overallMatch.reduce((a, b) => a + b, 0) / overallMatch.length
    : null

  return (
    <div style={{
      maxWidth: 1180, margin: '24px auto 0', background: 'var(--paper)',
      border: '1px solid var(--line)', borderRadius: 4,
      display: 'flex',
    }}>
      <Stat
        value={avgMatch !== null ? `${(avgMatch * 100).toFixed(1)}%` : '—'}
        label="auto-matched, deterministically"
      />
      <div style={{ width: 1, background: 'var(--line)' }} />
      <Stat
        value={metrics.exceptions_by_status?.auto_cleared ?? 0}
        label="exceptions auto-cleared by agent"
      />
      <div style={{ width: 1, background: 'var(--line)' }} />
      <Stat
        value={metrics.exceptions_by_status?.needs_review ?? 0}
        label="flagged for human review"
      />
      <div style={{ width: 1, background: 'var(--line)' }} />
      <Stat
        value={`${(metrics.auto_clear_rate * 100).toFixed(0)}%`}
        label="of exceptions resolved without a human"
      />
      <div style={{ width: 1, background: 'var(--line)' }} />
      <Stat
        value={metrics.total_runs}
        label="reconciliation run(s) to date"
      />
    </div>
  )
}
