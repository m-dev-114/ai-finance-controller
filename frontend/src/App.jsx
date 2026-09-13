import { useEffect, useState, useCallback, useMemo } from 'react'
import { api } from './api'
import Header from './components/Header'
import MetricsStrip from './components/MetricsStrip'
import QueueTabs from './components/QueueTabs'
import ExceptionList from './components/ExceptionList'
import ImportPanel from './components/ImportPanel'
import SettingsPanel from './components/SettingsPanel'
import TrendsPanel from './components/TrendsPanel'
import { formatRelativeTime } from './format'

export default function App() {
  const [exceptions, setExceptions] = useState([])
  const [metrics, setMetrics] = useState(null)
  const [runs, setRuns] = useState([])
  const [activeTab, setActiveTab] = useState('all')
  const [view, setView] = useState('queue') // 'queue' | 'trends'
  const [seeding, setSeeding] = useState(false)
  const [running, setRunning] = useState(false)
  const [error, setError] = useState(null)
  const [loaded, setLoaded] = useState(false)
  const [dataVersion, setDataVersion] = useState(0)

  const refresh = useCallback(async () => {
    try {
      const [excData, metricsData, runsData] = await Promise.all([
        api.listExceptions(),
        api.getMetrics(),
        api.listRuns(),
      ])
      setExceptions(excData)
      setMetrics(metricsData)
      setRuns(runsData)
      setError(null)
      setDataVersion((v) => v + 1)
    } catch (e) {
      setError(e.message)
    } finally {
      setLoaded(true)
    }
  }, [])

  useEffect(() => { refresh() }, [refresh])

  async function handleSeed() {
    setSeeding(true)
    setError(null)
    try {
      await api.seed()
      await refresh()
    } catch (e) {
      setError(e.message)
    } finally {
      setSeeding(false)
    }
  }

  async function handleRun() {
    setRunning(true)
    setError(null)
    try {
      await api.runReconciliation()
      await refresh()
    } catch (e) {
      setError(e.message)
    } finally {
      setRunning(false)
    }
  }

  async function handleResolve(exceptionId, body) {
    await api.resolveException(exceptionId, body)
    await refresh()
  }

  const counts = useMemo(() => ({
    all: exceptions.length,
    needs_review: exceptions.filter((e) => e.status === 'needs_review').length,
    auto_cleared: exceptions.filter((e) => e.status === 'auto_cleared').length,
    resolved: exceptions.filter((e) => e.status === 'resolved' || e.status === 'dismissed').length,
  }), [exceptions])

  const filtered = useMemo(() => {
    if (activeTab === 'all') return exceptions
    if (activeTab === 'resolved') return exceptions.filter((e) => e.status === 'resolved' || e.status === 'dismissed')
    return exceptions.filter((e) => e.status === activeTab)
  }, [exceptions, activeTab])

  const lastRun = runs[0] ? formatRelativeTime(runs[0].finished_at || runs[0].started_at) : null

  return (
    <div>
      <Header
        onSeed={handleSeed}
        onRun={handleRun}
        seeding={seeding}
        running={running}
        lastRun={lastRun}
        datasetSize={metrics?.total_transactions_in_dataset}
      />

      <main style={{ padding: '0 40px 60px' }}>
        <MetricsStrip metrics={metrics} />

        <div style={{ maxWidth: 1180, margin: '20px auto 0', display: 'flex', gap: 10, justifyContent: 'flex-end', flexWrap: 'wrap' }}>
          <SettingsPanel onChanged={refresh} dataVersion={dataVersion} />
          <ImportPanel onImported={refresh} />
        </div>

        {error && (
          <div style={{
            maxWidth: 1180, margin: '20px auto 0', padding: '12px 16px',
            background: 'var(--bad-soft)', color: 'var(--bad)', borderRadius: 4,
            fontSize: 13.5,
          }}>
            Something went wrong talking to the backend: {error}. Confirm the API is
            running and VITE_API_BASE_URL points at it.
          </div>
        )}

        <div style={{
          maxWidth: 1180, margin: '32px auto 0', background: 'var(--paper)',
          border: '1px solid var(--line)', borderRadius: 4, overflow: 'hidden',
        }}>
          <div style={{ display: 'flex', padding: '0 20px', borderBottom: '1px solid var(--line)' }}>
            {[{ key: 'queue', label: 'Queue' }, { key: 'trends', label: 'Trends' }].map((v) => (
              <button
                key={v.key}
                onClick={() => setView(v.key)}
                style={{
                  padding: '14px 16px', background: 'transparent', border: 'none',
                  borderBottom: view === v.key ? '2px solid var(--ink)' : '2px solid transparent',
                  fontSize: 14.5, fontWeight: view === v.key ? 700 : 500,
                  color: view === v.key ? 'var(--ink)' : 'var(--muted)',
                  fontFamily: 'var(--font-display)', marginBottom: -1,
                }}
              >
                {v.label}
              </button>
            ))}
          </div>

          {view === 'queue' ? (
            <>
              <div style={{ padding: '4px 20px 0' }}>
                <QueueTabs active={activeTab} onChange={setActiveTab} counts={counts} />
              </div>
              {loaded ? (
                <ExceptionList exceptions={filtered} onResolve={handleResolve} onBulkResolved={refresh} />
              ) : (
                <div style={{ padding: 40, textAlign: 'center', color: 'var(--muted)' }}>Loading…</div>
              )}
            </>
          ) : (
            <TrendsPanel runs={runs} />
          )}
        </div>

        {loaded && exceptions.length === 0 && !error && (
          <p style={{ maxWidth: 1180, margin: '20px auto 0', color: 'var(--muted)', fontSize: 14 }}>
            No data yet — click <strong>Generate sample data</strong> to load a synthetic
            reconciliation dataset, then <strong>Run reconciliation</strong> to see the matching
            engine and investigation agent in action.
          </p>
        )}
      </main>
    </div>
  )
}
