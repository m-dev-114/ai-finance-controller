import { useState, useEffect, useCallback } from 'react'
import { api } from '../api'

export default function SettingsPanel({ onChanged }) {
  const [open, setOpen] = useState(false)
  const [current, setCurrent] = useState(null)
  const [draft, setDraft] = useState(0.9)
  const [simulation, setSimulation] = useState(null)
  const [saving, setSaving] = useState(false)
  const [saveResult, setSaveResult] = useState(null)

  useEffect(() => {
    if (open) {
      api.getSettings().then((s) => {
        setCurrent(s.auto_clear_confidence)
        setDraft(s.auto_clear_confidence)
      })
    }
  }, [open])

  const runSimulation = useCallback((value) => {
    api.simulateThreshold(value).then(setSimulation).catch(() => setSimulation(null))
  }, [])

  useEffect(() => {
    if (open) runSimulation(draft)
  }, [draft, open, runSimulation])

  async function handleSave() {
    setSaving(true)
    setSaveResult(null)
    try {
      await api.updateSettings({ auto_clear_confidence: draft })
      setCurrent(draft)
      // Apply retroactively: without this, existing needs-review exceptions
      // never get re-checked against the new threshold — only brand-new
      // exceptions from a future run would see it.
      const result = await api.reevaluateThreshold()
      setSaveResult(result)
      onChanged && onChanged()
    } finally {
      setSaving(false)
    }
  }

  if (!open) {
    return (
      <button
        onClick={() => setOpen(true)}
        style={{
          padding: '10px 16px', fontSize: 14, fontWeight: 500,
          border: '1px solid var(--line-strong)', borderRadius: 3,
          background: 'var(--paper)', color: 'var(--ink)',
        }}
      >
        Auto-clear settings
      </button>
    )
  }

  return (
    <div style={{
      background: 'var(--paper)', border: '1px solid var(--line)', borderRadius: 4,
      padding: '20px 24px',
    }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 6 }}>
        <h3 style={{ fontFamily: 'var(--font-display)', fontSize: 16, margin: 0 }}>
          Auto-clear confidence threshold
        </h3>
        <button onClick={() => setOpen(false)} style={{ border: 'none', background: 'transparent', color: 'var(--muted)', fontSize: 13 }}>
          Close
        </button>
      </div>
      <p style={{ fontSize: 13.5, color: 'var(--muted)', margin: '0 0 16px' }}>
        Exceptions the agent scores at or above this confidence auto-clear without a human.
        Currently <strong>{current !== null ? `${Math.round(current * 100)}%` : '…'}</strong>.
        Note: no single check currently scores above ~92% confidence — setting the
        threshold above that will stop auto-clearing anything at all.
      </p>

      <input
        type="range" min="0.5" max="0.99" step="0.01"
        value={draft}
        onChange={(e) => setDraft(parseFloat(e.target.value))}
        style={{ width: '100%' }}
      />
      <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 12, color: 'var(--muted)', marginTop: 4 }}>
        <span>50% (aggressive automation)</span>
        <span style={{ fontFamily: 'var(--font-mono)', fontWeight: 600, color: 'var(--ink)' }}>
          {Math.round(draft * 100)}%
        </span>
        <span>99% (very conservative)</span>
      </div>

      {simulation && (
        <div style={{ marginTop: 16, padding: '12px 14px', background: 'var(--paper-dim)', borderRadius: 3, fontSize: 13.5 }}>
          At this threshold, of exceptions the agent has scored so far:{' '}
          <strong style={{ color: 'var(--accent)' }}>{simulation.would_auto_clear}</strong> would auto-clear,{' '}
          <strong style={{ color: 'var(--warn)' }}>{simulation.would_need_review}</strong> would need review.
        </div>
      )}

      <button
        onClick={handleSave}
        disabled={saving || draft === current}
        style={{
          marginTop: 14, padding: '9px 18px', fontSize: 13.5, fontWeight: 600, borderRadius: 3,
          border: '1px solid var(--ink)', background: 'var(--ink)', color: 'var(--paper)',
          opacity: saving || draft === current ? 0.5 : 1,
        }}
      >
        {saving ? 'Saving…' : 'Save threshold'}
      </button>

      {saveResult && (
        <div style={{ marginTop: 10, fontSize: 13, color: 'var(--muted)' }}>
          {saveResult.promoted.length > 0
            ? `Saved — ${saveResult.promoted.length} existing exception(s) auto-cleared under the new threshold, ${saveResult.remaining_needs_review} still need review.`
            : 'Saved — no existing needs-review exceptions qualified at this threshold.'}
        </div>
      )}
    </div>
  )
}
