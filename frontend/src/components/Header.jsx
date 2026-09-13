export default function Header({ onSeed, onRun, seeding, running, lastRun }) {
  return (
    <header style={{
      borderBottom: '1px solid var(--line)',
      background: 'var(--paper)',
      padding: '28px 40px 22px',
    }}>
      <div style={{
        display: 'flex', justifyContent: 'space-between', alignItems: 'flex-end',
        maxWidth: 1180, margin: '0 auto',
      }}>
        <div>
          <h1 style={{
            fontFamily: 'var(--font-display)', fontWeight: 700, fontSize: 26,
            margin: 0, letterSpacing: '-0.01em',
          }}>
            Finance Controller
          </h1>
          <p style={{ margin: '6px 0 0', color: 'var(--muted)', fontSize: 14.5 }}>
            Multi-level payment reconciliation — transactions, settlement batches, and the ledger.
          </p>
        </div>
        <div style={{ display: 'flex', gap: 10, alignItems: 'center' }}>
          {lastRun && (
            <span style={{ fontFamily: 'var(--font-mono)', fontSize: 12.5, color: 'var(--muted)', marginRight: 6 }}>
              last run {lastRun}
            </span>
          )}
          <button
            onClick={onSeed}
            disabled={seeding}
            style={{
              padding: '10px 16px', fontSize: 14, fontWeight: 500,
              border: '1px solid var(--line-strong)', borderRadius: 3,
              background: 'var(--paper)', color: 'var(--ink)',
              opacity: seeding ? 0.6 : 1,
            }}
          >
            {seeding ? 'Generating…' : 'Generate sample data'}
          </button>
          <button
            onClick={onRun}
            disabled={running}
            style={{
              padding: '10px 18px', fontSize: 14, fontWeight: 600,
              border: '1px solid var(--ink)', borderRadius: 3,
              background: 'var(--ink)', color: 'var(--paper)',
              opacity: running ? 0.7 : 1,
            }}
          >
            {running ? 'Reconciling…' : 'Run reconciliation'}
          </button>
        </div>
      </div>
    </header>
  )
}
