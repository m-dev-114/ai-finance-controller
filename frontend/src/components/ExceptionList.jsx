import { useMemo, useState } from 'react'
import ExceptionRow from './ExceptionRow'
import { api } from '../api'

const SORT_OPTIONS = [
  { key: 'newest', label: 'Newest first' },
  { key: 'oldest', label: 'Oldest first' },
  { key: 'amount_desc', label: 'Largest amount' },
  { key: 'amount_asc', label: 'Smallest amount' },
  { key: 'confidence_desc', label: 'Highest confidence' },
  { key: 'confidence_asc', label: 'Lowest confidence' },
]

function applySort(list, sortKey) {
  const sorted = [...list]
  switch (sortKey) {
    case 'oldest': return sorted.sort((a, b) => new Date(a.created_at) - new Date(b.created_at))
    case 'amount_desc': return sorted.sort((a, b) => Math.abs(b.amount_delta ?? 0) - Math.abs(a.amount_delta ?? 0))
    case 'amount_asc': return sorted.sort((a, b) => Math.abs(a.amount_delta ?? 0) - Math.abs(b.amount_delta ?? 0))
    case 'confidence_desc': return sorted.sort((a, b) => (b.confidence ?? -1) - (a.confidence ?? -1))
    case 'confidence_asc': return sorted.sort((a, b) => (a.confidence ?? 2) - (b.confidence ?? 2))
    default: return sorted.sort((a, b) => new Date(b.created_at) - new Date(a.created_at))
  }
}

export default function ExceptionList({ exceptions, onResolve, onBulkResolved }) {
  const [search, setSearch] = useState('')
  const [sortKey, setSortKey] = useState('newest')
  const [selected, setSelected] = useState(new Set())
  const [bulkBusy, setBulkBusy] = useState(false)

  const filtered = useMemo(() => {
    let list = exceptions
    if (search.trim()) {
      const q = search.trim().toLowerCase()
      list = list.filter((e) =>
        e.id.toLowerCase().includes(q) ||
        e.level.toLowerCase().includes(q) ||
        (e.hypothesis || '').toLowerCase().includes(q) ||
        (e.reference_ids || []).some((r) => r.toLowerCase().includes(q))
      )
    }
    return applySort(list, sortKey)
  }, [exceptions, search, sortKey])

  const actionableIds = filtered.filter((e) => e.status === 'needs_review').map((e) => e.id)
  const allActionableSelected = actionableIds.length > 0 && actionableIds.every((id) => selected.has(id))

  function toggleOne(id) {
    setSelected((prev) => {
      const next = new Set(prev)
      next.has(id) ? next.delete(id) : next.add(id)
      return next
    })
  }

  function toggleAll() {
    setSelected((prev) => {
      if (allActionableSelected) return new Set()
      return new Set(actionableIds)
    })
  }

  async function handleBulk(outcome) {
    setBulkBusy(true)
    try {
      await api.bulkResolve({
        exception_ids: Array.from(selected),
        resolved_by: 'human:dashboard-user',
        outcome,
        note: `Bulk ${outcome} via the dashboard.`,
      })
      setSelected(new Set())
      onBulkResolved && await onBulkResolved()
    } finally {
      setBulkBusy(false)
    }
  }

  return (
    <div>
      <div style={{ display: 'flex', gap: 10, padding: '12px 20px', borderBottom: '1px solid var(--line)', alignItems: 'center' }}>
        <input
          type="text"
          placeholder="Search by ID, level, or hypothesis…"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          style={{
            flex: 1, padding: '8px 12px', fontSize: 13.5, borderRadius: 3,
            border: '1px solid var(--line-strong)', fontFamily: 'var(--font-body)',
          }}
        />
        <select
          value={sortKey}
          onChange={(e) => setSortKey(e.target.value)}
          style={{ padding: '8px 10px', fontSize: 13.5, borderRadius: 3, border: '1px solid var(--line-strong)' }}
        >
          {SORT_OPTIONS.map((opt) => (
            <option key={opt.key} value={opt.key}>{opt.label}</option>
          ))}
        </select>
      </div>

      {selected.size > 0 && (
        <div style={{
          display: 'flex', alignItems: 'center', gap: 12, padding: '10px 20px',
          background: 'var(--accent-soft)', borderBottom: '1px solid var(--line)', fontSize: 13.5,
        }}>
          <span><strong>{selected.size}</strong> selected</span>
          <button
            onClick={() => handleBulk('resolved')}
            disabled={bulkBusy}
            style={{ padding: '6px 12px', fontSize: 13, borderRadius: 3, border: '1px solid var(--accent)', background: 'var(--paper)', color: 'var(--accent)' }}
          >
            Resolve selected
          </button>
          <button
            onClick={() => handleBulk('dismissed')}
            disabled={bulkBusy}
            style={{ padding: '6px 12px', fontSize: 13, borderRadius: 3, border: '1px solid var(--line-strong)', background: 'var(--paper)', color: 'var(--muted)' }}
          >
            Dismiss selected
          </button>
          <button
            onClick={() => setSelected(new Set())}
            style={{ padding: '6px 12px', fontSize: 13, borderRadius: 3, border: 'none', background: 'transparent', color: 'var(--muted)' }}
          >
            Clear
          </button>
        </div>
      )}

      {filtered.length === 0 ? (
        <div style={{ padding: '48px 20px', textAlign: 'center', color: 'var(--muted)', fontSize: 14 }}>
          Nothing matches here. Try a different search or run a reconciliation.
        </div>
      ) : (
        <div>
          <div style={{
            display: 'flex', gap: 16, padding: '10px 20px', fontSize: 11.5,
            color: 'var(--muted)', textTransform: 'uppercase', letterSpacing: '0.03em',
            borderBottom: '1px solid var(--line)', alignItems: 'center',
          }}>
            <span style={{ paddingLeft: 16, width: 26 }}>
              <input type="checkbox" checked={allActionableSelected} onChange={toggleAll}
                     disabled={actionableIds.length === 0} />
            </span>
            <span style={{ minWidth: 108 }}>Status</span>
            <span style={{ width: 130 }}>Level</span>
            <span style={{ flex: 1, minWidth: 0 }}>Hypothesis</span>
            <span style={{ width: 110, textAlign: 'right' }}>Delta</span>
            <span style={{ width: 50, textAlign: 'right' }}>Conf.</span>
            <span style={{ width: 70, textAlign: 'right' }}>Age</span>
            <span style={{ width: 16 }} />
          </div>
          {filtered.map((exc) => (
            <ExceptionRow
              key={exc.id}
              exception={exc}
              onResolve={onResolve}
              selectable
              selected={selected.has(exc.id)}
              onToggleSelect={toggleOne}
            />
          ))}
        </div>
      )}
    </div>
  )
}
