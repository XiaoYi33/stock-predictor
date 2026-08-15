const BASE = '/api'

async function api(path, opts) {
  const res = await fetch(BASE + path, opts)
  if (!res.ok) {
    const body = await res.json().catch(() => ({}))
    throw new Error(body.error || `HTTP ${res.status}`)
  }
  return res.json()
}

export const searchStock = (kw) => api(`/search?kw=${encodeURIComponent(kw)}`)
export const getStock = (code) => api(`/stock/${code}`)
export const getAnalysis = (code) => api(`/stock/${code}/analysis`)
export const getBacktest = (code, days = 30) => api(`/stock/${code}/backtest?days=${days}`)
export const getKline = (code, days = 250) => api(`/stock/${code}/kline?days=${days}`)
export const getModelStatus = () => api('/model/status')
export const triggerTrain = () => api('/model/train', { method: 'POST' })
