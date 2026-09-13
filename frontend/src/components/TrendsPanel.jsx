import { useEffect, useState } from 'react'
import { api } from '../api'
import TrendChart from './TrendChart'
import { formatRelativeTime } from '../format'

export default function TrendsPanel({ runs }) {
  const [trend, setTrend] = useState(null)

  useEffect(() => {
    api.getTrend().then(setTrend).catch(() => setTrend({ points: [] }))
  }, [runs])

  if (!trend) {
    return <div style={{ padding: 30, color: 'var(--muted)' }}>Loading trends…</div>
  }

  return (
    <div style={{ padding: '20px 24px' }}>
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 32, marginBottom: 28 }}>
        <TrendChart
          points={trend.points}
          valueKey="match_rate"
          label="Deterministic match rate, per run"
          color="var(--accent)"
          formatValue={(v) => `${(v * 100).toFixed(1)}%`}
        />
        <TrendChart
          points={trend.points}
          valueKey="total_exceptions"
          label="Exceptions surfaced, per run"
          color="var(--warn)"
          formatValue={(v) => `${v}`}
        />
      </div>

      <div style={{ fontSize: 12, fontWeight: 600, color: 'var(--muted)', textTransform: 'uppercase', letterSpacing: '0.03em', marginBottom: 10 }}>
        Run history
      </div>
      <div>
        <div style={{ display: 'flex', gap: 16, padding: '8px 0', fontSize: 11.5, color: 'var(--muted)', textTransform: 'uppercase', borderBottom: '1px solid var(--line)' }}>
          <span style={{ flex: 1 }}>Run</span>
          <span style={{ width: 90, textAlign: 'right' }}>Auto-cleared</span>
          <span style={{ width: 90, textAlign: 'right' }}>Needs review</span>
          <span style={{ width: 70, textAlign: 'right' }}>Age</span>
          <span style={{ width: 90, textAlign: 'right' }}>Report</span>
        </div>
        {runs.slice(0, 10).map((run) => (
          <div key={run.id} style={{ display: 'flex', gap: 16, padding: '10px 0', fontSize: 13.5, borderBottom: '1px solid var(--line)', alignItems: 'center' }}>
            <span style={{ flex: 1, fontFamily: 'var(--font-mono)', color: 'var(--muted)' }}>{run.id}</span>
            <span style={{ width: 90, textAlign: 'right', fontFamily: 'var(--font-mono)' }}>{run.stats?.auto_cleared ?? '—'}</span>
            <span style={{ width: 90, textAlign: 'right', fontFamily: 'var(--font-mono)' }}>{run.stats?.needs_review ?? '—'}</span>
            <span style={{ width: 70, textAlign: 'right', color: 'var(--muted)' }}>{formatRelativeTime(run.finished_at || run.started_at)}</span>
            <span style={{ width: 90, textAlign: 'right' }}>
              <a href={api.runReportUrl(run.id)} style={{ color: 'var(--accent)', fontSize: 12.5 }}>Download</a>
            </span>
          </div>
        ))}
        {runs.length === 0 && (
          <div style={{ padding: '20px 0', color: 'var(--muted)', fontSize: 13.5 }}>No runs yet.</div>
        )}
      </div>
    </div>
  )
}
