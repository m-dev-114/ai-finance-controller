import { useState, useRef } from 'react'
import { api } from '../api'

export default function ImportPanel({ onImported }) {
  const [open, setOpen] = useState(false)
  const [settlementFile, setSettlementFile] = useState(null)
  const [bankFile, setBankFile] = useState(null)
  const [preview, setPreview] = useState(null)
  const [error, setError] = useState(null)
  const [busy, setBusy] = useState(false)
  const settlementRef = useRef(null)
  const bankRef = useRef(null)

  const canPreview = settlementFile && bankFile

  async function handlePreview() {
    setBusy(true); setError(null); setPreview(null)
    try {
      const result = await api.previewImport(settlementFile, bankFile)
      setPreview(result)
    } catch (e) {
      setError(e.message)
    } finally {
      setBusy(false)
    }
  }

  async function handleImport() {
    setBusy(true); setError(null)
    try {
      await api.runImport(settlementFile, bankFile)
      setPreview(null)
      setSettlementFile(null)
      setBankFile(null)
      if (settlementRef.current) settlementRef.current.value = ''
      if (bankRef.current) bankRef.current.value = ''
      setOpen(false)
      await onImported()
    } catch (e) {
      setError(e.message)
    } finally {
      setBusy(false)
    }
  }

  if (!open) {
    return (
      <div style={{ textAlign: 'right' }}>
        <button
          onClick={() => setOpen(true)}
          style={{
            padding: '10px 16px', fontSize: 14, fontWeight: 500,
            border: '1px solid var(--line-strong)', borderRadius: 3,
            background: 'var(--paper)', color: 'var(--ink)',
          }}
        >
          Import CSVs
        </button>
      </div>
    )
  }

  return (
    <div style={{
      background: 'var(--paper)',
      border: '1px solid var(--line)', borderRadius: 4, padding: '20px 24px',
    }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <h3 style={{ fontFamily: 'var(--font-display)', fontSize: 16, margin: 0 }}>
          Import settlement + bank data
        </h3>
        <button
          onClick={() => setOpen(false)}
          style={{ border: 'none', background: 'transparent', color: 'var(--muted)', fontSize: 13 }}
        >
          Close
        </button>
      </div>

      <p style={{ fontSize: 13.5, color: 'var(--muted)', margin: '8px 0 16px' }}>
        This replaces any existing data. Not sure of the format?{' '}
        <a href={api.settlementTemplateUrl()} style={{ color: 'var(--accent)' }}>
          Format reference (settlement)
        </a>{' '}
        ·{' '}
        <a href={api.bankTemplateUrl()} style={{ color: 'var(--accent)' }}>
          Format reference (bank)
        </a>
        <br />
        Want something bigger to try?{' '}
        <a href={api.exampleSettlementUrl()} style={{ color: 'var(--accent)' }}>
          Download example settlement CSV
        </a>{' '}
        ·{' '}
        <a href={api.exampleBankUrl()} style={{ color: 'var(--accent)' }}>
          Download example bank CSV
        </a>{' '}
        — a ~40-transaction dataset that exercises every pattern the agent knows how to investigate.
      </p>

      <div style={{ display: 'flex', gap: 20, marginBottom: 16 }}>
        <div style={{ flex: 1 }}>
          <label style={{ fontSize: 12.5, fontWeight: 600, color: 'var(--muted)', display: 'block', marginBottom: 6 }}>
            SETTLEMENT CSV
          </label>
          <input
            ref={settlementRef}
            type="file"
            accept=".csv"
            onChange={(e) => { setSettlementFile(e.target.files[0]); setPreview(null) }}
            style={{ fontSize: 13, width: '100%' }}
          />
        </div>
        <div style={{ flex: 1 }}>
          <label style={{ fontSize: 12.5, fontWeight: 600, color: 'var(--muted)', display: 'block', marginBottom: 6 }}>
            BANK STATEMENT CSV
          </label>
          <input
            ref={bankRef}
            type="file"
            accept=".csv"
            onChange={(e) => { setBankFile(e.target.files[0]); setPreview(null) }}
            style={{ fontSize: 13, width: '100%' }}
          />
        </div>
      </div>

      {error && (
        <div style={{ padding: '10px 12px', background: 'var(--bad-soft)', color: 'var(--bad)', borderRadius: 3, fontSize: 13, marginBottom: 12 }}>
          {error}
        </div>
      )}

      {preview && (
        <div style={{ padding: '12px 14px', background: 'var(--paper-dim)', borderRadius: 3, marginBottom: 12, fontSize: 13.5 }}>
          <strong>{preview.settlement_rows}</strong> settlement rows across{' '}
          <strong>{preview.distinct_settlement_batches}</strong> batch(es),{' '}
          <strong>{preview.bank_rows}</strong> bank lines.{' '}
          {Object.entries(preview.status_breakdown).map(([status, count]) => (
            <span key={status} style={{ marginRight: 10, fontFamily: 'var(--font-mono)', color: 'var(--muted)' }}>
              {status}: {count}
            </span>
          ))}
        </div>
      )}

      <div style={{ display: 'flex', gap: 8 }}>
        <button
          onClick={handlePreview}
          disabled={!canPreview || busy}
          style={{
            padding: '9px 16px', fontSize: 13.5, fontWeight: 500, borderRadius: 3,
            border: '1px solid var(--line-strong)', background: 'var(--paper)',
            opacity: !canPreview || busy ? 0.5 : 1,
          }}
        >
          Preview
        </button>
        <button
          onClick={handleImport}
          disabled={!preview || busy}
          style={{
            padding: '9px 18px', fontSize: 13.5, fontWeight: 600, borderRadius: 3,
            border: '1px solid var(--ink)', background: 'var(--ink)', color: 'var(--paper)',
            opacity: !preview || busy ? 0.5 : 1,
          }}
        >
          {busy ? 'Working…' : 'Confirm import'}
        </button>
      </div>
    </div>
  )
}
