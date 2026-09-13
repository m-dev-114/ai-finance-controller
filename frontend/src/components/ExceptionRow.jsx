import { useState } from 'react'
import { formatINR, formatRelativeTime, levelLabel, statusMeta } from '../format'

export default function ExceptionRow({ exception, onResolve, selectable, selected, onToggleSelect }) {
  const [expanded, setExpanded] = useState(false)
  const [resolving, setResolving] = useState(false)
  const status = statusMeta(exception.status)
  const isActionable = exception.status === 'needs_review'

  async function handleResolve(outcome) {
    setResolving(true)
    try {
      await onResolve(exception.id, {
        resolved_by: 'human:dashboard-user',
        outcome,
        note: outcome === 'resolved'
          ? 'Reviewed and confirmed in the dashboard.'
          : 'Dismissed after manual review — not a real discrepancy.',
      })
    } finally {
      setResolving(false)
    }
  }

  return (
    <div style={{ borderBottom: '1px solid var(--line)' }}>
      <div style={{ display: 'flex', alignItems: 'center' }}>
        {selectable && (
          <span style={{ paddingLeft: 16 }}>
            <input
              type="checkbox"
              checked={!!selected}
              disabled={!isActionable}
              onChange={() => onToggleSelect(exception.id)}
              onClick={(e) => e.stopPropagation()}
              style={{ opacity: isActionable ? 1 : 0.25 }}
            />
          </span>
        )}
        <button
          onClick={() => setExpanded((v) => !v)}
          style={{
            flex: 1, minWidth: 0, display: 'flex', alignItems: 'center', gap: 16,
            padding: '14px 20px', background: 'transparent', border: 'none',
            textAlign: 'left',
          }}
        >
        <span style={{
          fontSize: 11.5, fontWeight: 600, letterSpacing: '0.03em',
          textTransform: 'uppercase', color: status.color, background: status.bg,
          padding: '4px 8px', borderRadius: 2, minWidth: 108, textAlign: 'center',
        }}>
          {status.label}
        </span>

        <span style={{ width: 130, fontSize: 13.5, color: 'var(--muted)' }}>
          {levelLabel(exception.level)}
        </span>

        <span style={{
          flex: 1, minWidth: 0, fontSize: 13.5, color: 'var(--ink)',
          overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap',
        }}>
          {exception.hypothesis || 'Awaiting investigation'}
        </span>

        <span style={{
          fontFamily: 'var(--font-mono)', fontSize: 14, width: 110, textAlign: 'right',
          color: (exception.amount_delta ?? 0) < 0 ? 'var(--bad)' : 'var(--ink)',
        }}>
          {formatINR(exception.amount_delta)}
        </span>

        <span style={{ fontFamily: 'var(--font-mono)', fontSize: 13, width: 50, textAlign: 'right', color: 'var(--muted)' }}>
          {exception.confidence !== null ? `${Math.round(exception.confidence * 100)}%` : '—'}
        </span>

        <span style={{ width: 70, textAlign: 'right', fontSize: 13, color: 'var(--muted)' }}>
          {formatRelativeTime(exception.created_at)}
        </span>

        <span style={{ width: 16, textAlign: 'center', color: 'var(--muted)' }}>
          {expanded ? '\u25be' : '\u25b8'}
        </span>
        </button>
      </div>

      {expanded && (
        <div style={{ padding: '4px 20px 20px 20px', background: 'var(--paper-dim)' }}>
          <div style={{
            fontSize: 12, fontWeight: 600, color: 'var(--muted)', letterSpacing: '0.03em',
            textTransform: 'uppercase', marginBottom: 10,
          }}>
            Investigation trail
          </div>
          <ol style={{ margin: 0, padding: 0, listStyle: 'none' }}>
            {(exception.reasoning_trail || []).map((step, i) => (
              <li key={i} style={{
                display: 'flex', gap: 12, padding: '8px 0',
                borderTop: i > 0 ? '1px solid var(--line)' : 'none',
              }}>
                <span style={{
                  fontFamily: 'var(--font-mono)', fontSize: 12, color: 'var(--muted)',
                  width: 22, flexShrink: 0, paddingTop: 1,
                }}>
                  {String(i + 1).padStart(2, '0')}
                </span>
                <div>
                  <div style={{ fontSize: 12.5, fontFamily: 'var(--font-mono)', color: 'var(--accent)' }}>
                    {step.step}
                  </div>
                  <div style={{ fontSize: 13.5, marginTop: 2, color: 'var(--ink)' }}>
                    {step.finding}
                  </div>
                </div>
              </li>
            ))}
          </ol>

          {exception.resolved_by && (
            <div style={{ marginTop: 12, fontSize: 13, color: 'var(--muted)' }}>
              Resolved by <span style={{ fontFamily: 'var(--font-mono)' }}>{exception.resolved_by}</span>
              {' '}· {formatRelativeTime(exception.resolved_at)}
            </div>
          )}

          {isActionable && (
            <div style={{ marginTop: 14, display: 'flex', gap: 8 }}>
              <button
                onClick={() => handleResolve('resolved')}
                disabled={resolving}
                style={{
                  padding: '8px 14px', fontSize: 13, fontWeight: 500, borderRadius: 3,
                  border: '1px solid var(--accent)', background: 'var(--accent-soft)',
                  color: 'var(--accent)', opacity: resolving ? 0.6 : 1,
                }}
              >
                Mark resolved
              </button>
              <button
                onClick={() => handleResolve('dismissed')}
                disabled={resolving}
                style={{
                  padding: '8px 14px', fontSize: 13, fontWeight: 500, borderRadius: 3,
                  border: '1px solid var(--line-strong)', background: 'var(--paper)',
                  color: 'var(--muted)', opacity: resolving ? 0.6 : 1,
                }}
              >
                Dismiss
              </button>
            </div>
          )}
        </div>
      )}
    </div>
  )
}
