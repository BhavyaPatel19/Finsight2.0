import { useEffect, useState, useCallback } from 'react'
import { marketApi, portfolioApi } from '../api/client'
import { Activity, RefreshCw, TrendingUp, TrendingDown, Clock } from 'lucide-react'
import {
  AreaChart, Area, XAxis, YAxis, Tooltip,
  ResponsiveContainer, CartesianGrid
} from 'recharts'

const fmtCcy = (n) =>
  n == null ? '—' : '₹' + new Intl.NumberFormat('en-IN', { maximumFractionDigits: 2 }).format(n)

const fmtVol = (n) => {
  if (n >= 10000000) return (n / 10000000).toFixed(2) + 'Cr'
  if (n >= 100000) return (n / 100000).toFixed(2) + 'L'
  if (n >= 1000) return (n / 1000).toFixed(1) + 'K'
  return n
}

function isMarketOpen() {
  const now = new Date()
  const h = now.getHours(), m = now.getMinutes()
  const day = now.getDay()
  if (day === 0 || day === 6) return false
  const mins = h * 60 + m
  return mins >= 555 && mins <= 930 // 9:15 AM to 3:30 PM IST
}

export default function Market() {
  const [quotes, setQuotes] = useState({})
  const [loading, setLoading] = useState(true)
  const [selectedSymbol, setSelectedSymbol] = useState(null)
  const [history, setHistory] = useState([])
  const [histLoading, setHistLoading] = useState(false)
  const [interval, setInterval_] = useState('day')
  const [autoRefresh, setAutoRefresh] = useState(false)
  const [lastUpdated, setLastUpdated] = useState(null)

  const load = useCallback(async () => {
    setLoading(true)
    try {
      const r = await marketApi.quotes()
      setQuotes(r.data.quotes ?? {})
      setLastUpdated(new Date())
    } catch { setQuotes({}) }
    finally { setLoading(false) }
  }, [])

  useEffect(() => { load() }, [load])

  // Auto-refresh every 15s during market hours
  useEffect(() => {
    if (!autoRefresh) return
    const id = setInterval(() => {
      if (isMarketOpen()) load()
    }, 15000)
    return () => clearInterval(id)
  }, [autoRefresh, load])

  const loadHistory = async (sym) => {
    setSelectedSymbol(sym)
    setHistLoading(true)
    try {
      const r = await marketApi.history(sym, interval)
      setHistory(r.data.candles ?? [])
    } catch { setHistory([]) }
    finally { setHistLoading(false) }
  }

  useEffect(() => {
    if (selectedSymbol) loadHistory(selectedSymbol)
  }, [interval])

  const sortedSymbols = Object.keys(quotes).sort()
  const marketOpen = isMarketOpen()

  return (
    <div>
      <div className="flex-between mb-6">
        <div className="page-header" style={{ marginBottom: 0 }}>
          <h1 className="page-title" style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
            <Activity size={24} color="#6366f1" /> Live Market
          </h1>
          <p className="page-sub">Real-time quotes from Zerodha Kite Connect</p>
        </div>
        <div className="flex gap-2" style={{ alignItems: 'center' }}>
          <div style={{
            display: 'flex', alignItems: 'center', gap: 6, padding: '6px 12px',
            borderRadius: 8, background: marketOpen ? 'rgba(34,211,165,0.1)' : 'rgba(244,63,94,0.1)',
            fontSize: 12, fontWeight: 600, color: marketOpen ? '#22d3a5' : '#f43f5e'
          }}>
            <span style={{
              width: 8, height: 8, borderRadius: '50%',
              background: marketOpen ? '#22d3a5' : '#f43f5e',
              animation: marketOpen ? 'pulse 2s infinite' : 'none'
            }} />
            {marketOpen ? 'Market Open' : 'Market Closed'}
          </div>
          <label style={{ display: 'flex', alignItems: 'center', gap: 6, fontSize: 12, color: 'var(--text-muted)', cursor: 'pointer' }}>
            <input type="checkbox" checked={autoRefresh} onChange={e => setAutoRefresh(e.target.checked)}
              style={{ accentColor: '#6366f1' }} />
            Auto (15s)
          </label>
          <button className="btn btn-ghost btn-sm flex-center gap-2" onClick={load}>
            <RefreshCw size={14} /> Refresh
          </button>
        </div>
      </div>

      {lastUpdated && (
        <div className="text-xs text-muted mb-4" style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
          <Clock size={12} /> Last updated: {lastUpdated.toLocaleTimeString()}
        </div>
      )}

      {loading && Object.keys(quotes).length === 0 ? (
        <div className="empty-state"><span className="spinner" style={{ width: 36, height: 36, borderWidth: 3 }} /></div>
      ) : sortedSymbols.length === 0 ? (
        <div className="empty-state card">
          <Activity size={48} />
          <p>No market data available.<br />Link Zerodha and sync holdings first.</p>
        </div>
      ) : (
        <>
          {/* Quote cards grid */}
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(220px, 1fr))', gap: 14, marginBottom: 24 }}>
            {sortedSymbols.map(key => {
              const q = quotes[key]
              const sym = key.split(':').pop()
              const change = q.last_price - (q.ohlc?.close ?? q.last_price)
              const changePct = q.ohlc?.close ? (change / q.ohlc.close) * 100 : 0
              const up = change >= 0

              return (
                <div
                  key={key}
                  className="card"
                  style={{
                    padding: '16px 18px', cursor: 'pointer',
                    border: selectedSymbol === sym ? '1px solid #6366f1' : '1px solid transparent',
                    transition: 'border 0.2s'
                  }}
                  onClick={() => loadHistory(sym)}
                >
                  <div className="flex-between" style={{ marginBottom: 8 }}>
                    <span className="badge badge-accent" style={{ fontSize: 13 }}>{sym}</span>
                    {up ? <TrendingUp size={16} color="#22d3a5" /> : <TrendingDown size={16} color="#f43f5e" />}
                  </div>
                  <div style={{ fontSize: 20, fontWeight: 700, color: 'var(--text-primary)' }}>
                    {fmtCcy(q.last_price)}
                  </div>
                  <div style={{ fontSize: 13, fontWeight: 600, color: up ? '#22d3a5' : '#f43f5e', marginTop: 4 }}>
                    {up ? '+' : ''}{fmtCcy(change)} ({changePct.toFixed(2)}%)
                  </div>
                  <div className="text-xs text-muted" style={{ marginTop: 8, display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '2px 10px' }}>
                    <span>O: {fmtCcy(q.ohlc?.open)}</span>
                    <span>H: {fmtCcy(q.ohlc?.high)}</span>
                    <span>L: {fmtCcy(q.ohlc?.low)}</span>
                    <span>V: {fmtVol(q.volume)}</span>
                  </div>
                </div>
              )
            })}
          </div>

          {/* Historical chart */}
          {selectedSymbol && (
            <div className="card">
              <div className="flex-between" style={{ marginBottom: 16 }}>
                <h3 style={{ fontSize: 15, fontWeight: 600 }}>
                  {selectedSymbol} — Price History
                </h3>
                <div className="flex gap-2">
                  {['day', '15minute', '5minute', 'minute'].map(iv => (
                    <button
                      key={iv}
                      className={`btn btn-sm ${interval === iv ? 'btn-primary' : 'btn-ghost'}`}
                      onClick={() => setInterval_(iv)}
                      style={{ fontSize: 11, padding: '4px 10px' }}
                    >
                      {iv === 'day' ? '1D' : iv === '15minute' ? '15m' : iv === '5minute' ? '5m' : '1m'}
                    </button>
                  ))}
                </div>
              </div>
              {histLoading ? (
                <div className="empty-state"><span className="spinner" /></div>
              ) : history.length === 0 ? (
                <div className="empty-state text-muted">No historical data available</div>
              ) : (
                <ResponsiveContainer width="100%" height={300}>
                  <AreaChart data={history.slice(-100)}>
                    <defs>
                      <linearGradient id="gradClose" x1="0" y1="0" x2="0" y2="1">
                        <stop offset="5%" stopColor="#6366f1" stopOpacity={0.3} />
                        <stop offset="95%" stopColor="#6366f1" stopOpacity={0} />
                      </linearGradient>
                    </defs>
                    <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.05)" />
                    <XAxis
                      dataKey="timestamp"
                      tick={{ fill: '#94a3b8', fontSize: 10 }}
                      axisLine={false} tickLine={false}
                      tickFormatter={t => {
                        const d = new Date(t)
                        return interval === 'day'
                          ? `${d.getDate()}/${d.getMonth()+1}`
                          : `${d.getHours()}:${String(d.getMinutes()).padStart(2,'0')}`
                      }}
                    />
                    <YAxis
                      domain={['auto', 'auto']}
                      tick={{ fill: '#94a3b8', fontSize: 11 }}
                      axisLine={false} tickLine={false}
                      tickFormatter={v => '₹' + v}
                    />
                    <Tooltip
                      contentStyle={{ background: '#0e1421', border: '1px solid rgba(255,255,255,0.1)', borderRadius: 10, fontSize: 12 }}
                      formatter={(v, name) => [fmtCcy(v), name.charAt(0).toUpperCase() + name.slice(1)]}
                      labelFormatter={t => new Date(t).toLocaleString()}
                    />
                    <Area type="monotone" dataKey="close" stroke="#6366f1" strokeWidth={2} fill="url(#gradClose)" name="close" />
                  </AreaChart>
                </ResponsiveContainer>
              )}
            </div>
          )}
        </>
      )}
    </div>
  )
}
