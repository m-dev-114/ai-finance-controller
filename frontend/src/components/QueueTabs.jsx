const TABS = [
  { key: 'all', label: 'All' },
  { key: 'needs_review', label: 'Needs review' },
  { key: 'auto_cleared', label: 'Auto-cleared' },
  { key: 'resolved', label: 'Resolved' },
]

export default function QueueTabs({ active, onChange, counts }) {
  return (
    <div style={{ display: 'flex', gap: 2, borderBottom: '1px solid var(--line)' }}>
      {TABS.map((tab) => {
        const isActive = active === tab.key
        return (
          <button
            key={tab.key}
            onClick={() => onChange(tab.key)}
            style={{
              padding: '12px 18px 10px',
              background: 'transparent',
              border: 'none',
              borderBottom: isActive ? '2px solid var(--ink)' : '2px solid transparent',
              fontSize: 14,
              fontWeight: isActive ? 600 : 500,
              color: isActive ? 'var(--ink)' : 'var(--muted)',
              marginBottom: -1,
            }}
          >
            {tab.label}
            <span style={{ fontFamily: 'var(--font-mono)', marginLeft: 6, fontSize: 12.5, color: 'var(--muted)' }}>
              {counts[tab.key] ?? 0}
            </span>
          </button>
        )
      })}
    </div>
  )
}
