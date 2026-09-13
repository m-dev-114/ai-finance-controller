const BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000'

async function request(path, options = {}) {
  const res = await fetch(`${BASE_URL}${path}`, {
    headers: { 'Content-Type': 'application/json' },
    ...options,
  })
  if (!res.ok) {
    const text = await res.text().catch(() => '')
    throw new Error(`${res.status} ${res.statusText}: ${text}`)
  }
  return res.json()
}

export const api = {
  seed: () => request('/reconcile/seed', { method: 'POST' }),
  runReconciliation: () => request('/reconcile/run', { method: 'POST' }),
  listRuns: () => request('/reconcile/runs'),
  previewImport: (settlementFile, bankFile) => {
    const form = new FormData()
    form.append('settlement_csv', settlementFile)
    form.append('bank_csv', bankFile)
    return request('/reconcile/import/preview', { method: 'POST', headers: {}, body: form })
  },
  runImport: (settlementFile, bankFile) => {
    const form = new FormData()
    form.append('settlement_csv', settlementFile)
    form.append('bank_csv', bankFile)
    return request('/reconcile/import', { method: 'POST', headers: {}, body: form })
  },
  settlementTemplateUrl: () => `${BASE_URL}/reconcile/import/template/settlement`,
  bankTemplateUrl: () => `${BASE_URL}/reconcile/import/template/bank`,
  listExceptions: (params = {}) => {
    const qs = new URLSearchParams(params).toString()
    return request(`/exceptions${qs ? `?${qs}` : ''}`)
  },
  getAuditTrail: (exceptionId) => request(`/exceptions/${exceptionId}/audit`),
  resolveException: (exceptionId, body) =>
    request(`/exceptions/${exceptionId}/resolve`, {
      method: 'POST',
      body: JSON.stringify(body),
    }),
  getMetrics: () => request('/metrics'),
  getTrend: () => request('/metrics/trend'),
  getSettings: () => request('/settings'),
  updateSettings: (body) => request('/settings', { method: 'POST', body: JSON.stringify(body) }),
  reevaluateThreshold: () => request('/settings/reevaluate', { method: 'POST' }),
  simulateThreshold: (threshold) => request(`/settings/simulate?threshold=${threshold}`),
  bulkResolve: (body) => request('/exceptions/bulk-resolve', { method: 'POST', body: JSON.stringify(body) }),
  exampleSettlementUrl: () => `${BASE_URL}/reconcile/import/example/settlement`,
  exampleBankUrl: () => `${BASE_URL}/reconcile/import/example/bank`,
  runReportUrl: (runId) => `${BASE_URL}/reconcile/runs/${runId}/report.csv`,
}
