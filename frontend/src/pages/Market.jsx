import { useEffect, useState, useCallback, useRef } from 'react'
import { marketApi } from '../api/client'
import {
  Activity, RefreshCw, TrendingUp, TrendingDown, Clock,
  Search, X, Star, BarChart3, Loader
} from 'lucide-react'
import {
  AreaChart, Area, XAxis, YAxis, Tooltip,
  ResponsiveContainer, CartesianGrid,
  ComposedChart, Bar, Line
} from 'recharts'

const fmtCcy = (n) =>
  n == null ? '—' : '₹' + new Intl.NumberFormat('en-IN', { maximumFractionDigits: 2 }).format(n)

const fmtVol = (n) => {
  if (n == null) return '—'
  if (n >= 10000000) return (n / 10000000).toFixed(2) + 'Cr'
  if (n >= 100000) return (n / 100000).toFixed(2) + 'L'
  if (n >= 1000) return (n / 1000).toFixed(1) + 'K'
  return n
}

const fmtMcap = (n) => {
  if (n == null) return '—'
  if (n >= 1e12) return '₹' + (n / 1e12).toFixed(2) + 'T'
  if (n >= 1e9) return '₹' + (n / 1e9).toFixed(2) + 'B'
  if (n >= 1e7) return '₹' + (n / 1e7).toFixed(2) + 'Cr'
  return fmtCcy(n)
}

const fmtPct = (n) => n == null ? '—' : n.toFixed(2) + '%'

const TIME_RANGES = [
  { key: '1D', label: '1 Day', interval: 'minute', days: 0 },
  { key: '1W', label: '1 Week', interval: '15minute', days: 7 },
  { key: '1M', label: '1 Month', interval: 'day', days: 30 },
  { key: '3M', label: '3 Months', interval: 'day', days: 90 },
  { key: '1Y', label: '1 Year', interval: 'day', days: 365 },
]

function MetricCard({ label, value, color }) {
  return (
    <div style={{
      padding: '10px 14px', background: 'rgba(255,255,255,0.03)',
      borderRadius: 10, border: '1px solid rgba(255,255,255,0.06)',
    }}>
      <div className="text-xs text-muted" style={{ marginBottom: 4 }}>{label}</div>
      <div style={{ fontSize: 15, fontWeight: 700, color: color || 'var(--text-primary)' }}>
        {value}
      </div>
    </div>
  )
}

function MetricsPanel({ data, loading }) {
  if (loading) {
    return (
      <div className="card" style={{ marginBottom: 16, padding: 20 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 10, color: 'var(--text-muted)', fontSize: 13 }}>
          <Loader size={16} className="spin" /> Loading fundamentals...
        </div>
      </div>
    )
  }
  if (!data || data.error) return null

  const deColor = data.debt_to_equity != null
    ? (data.debt_to_equity > 1.5 ? '#f43f5e' : data.debt_to_equity < 0.5 ? '#22d3a5' : 'var(--text-primary)')
    : undefined
  const roeColor = data.roe != null
    ? (data.roe > 15 ? '#22d3a5' : data.roe < 10 ? '#f43f5e' : 'var(--text-primary)')
    : undefined
  const roceColor = data.roce != null
    ? (data.roce > 15 ? '#22d3a5' : data.roce < 10 ? '#f43f5e' : 'var(--text-primary)')
    : undefined

  return (
    <div className="card" style={{ marginBottom: 16 }}>
      <h4 style={{ fontSize: 14, fontWeight: 600, marginBottom: 12, display: 'flex', alignItems: 'center', gap: 8 }}>
        <BarChart3 size={16} color="#6366f1" /> Fundamentals
        {data.sector && <span className="badge" style={{ fontSize: 10, marginLeft: 'auto' }}>{data.sector}</span>}
      </h4>
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(130px, 1fr))', gap: 8 }}>
        {data.pe_ratio != null && <MetricCard label="P/E Ratio" value={data.pe_ratio.toFixed(2)} />}
        {data.pb_ratio != null && <MetricCard label="P/B Ratio" value={data.pb_ratio.toFixed(2)} />}
        {data.roe != null && <MetricCard label="ROE" value={fmtPct(data.roe)} color={roeColor} />}
        {data.roce != null && <MetricCard label="ROCE" value={fmtPct(data.roce)} color={roceColor} />}
        {data.eps != null && <MetricCard label="EPS" value={'₹' + data.eps.toFixed(2)} />}
        {data.debt_to_equity != null && <MetricCard label="D/E Ratio" value={data.debt_to_equity.toFixed(2)} color={deColor} />}
        {data.dividend_yield != null && <MetricCard label="Div Yield" value={fmtPct(data.dividend_yield)} />}
        {data.market_cap != null && <MetricCard label="Market Cap" value={fmtMcap(data.market_cap)} />}
        {data.book_value != null && <MetricCard label="Book Value" value={'₹' + data.book_value.toFixed(2)} />}
        {data.high_52w != null && <MetricCard label="52W High" value={fmtCcy(data.high_52w)} color="#22d3a5" />}
        {data.low_52w != null && <MetricCard label="52W Low" value={fmtCcy(data.low_52w)} color="#f43f5e" />}
      </div>
    </div>
  )
}

function isMarketOpen() {
  const now = new Date()
  const h = now.getHours(), m = now.getMinutes()
  const day = now.getDay()
  if (day === 0 || day === 6) return false
  const mins = h * 60 + m
  return mins >= 555 && mins <= 930
}

function QuoteCard({ symKey, quote, isSelected, onClick }) {
  const sym = symKey.split(':').pop()
  const change = quote.last_price - (quote.ohlc?.close ?? quote.last_price)
  const changePct = quote.ohlc?.close ? (change / quote.ohlc.close) * 100 : 0
  const up = change >= 0

  return (
    <div
      className="card"
      style={{
        padding: '14px 16px', cursor: 'pointer',
        border: isSelected ? '1px solid #6366f1' : '1px solid transparent',
        transition: 'all 0.2s',
        background: isSelected ? 'rgba(99,102,241,0.06)' : undefined,
      }}
      onClick={() => onClick(sym)}
    >
      <div className="flex-between" style={{ marginBottom: 6 }}>
        <span className="badge badge-accent" style={{ fontSize: 12 }}>{sym}</span>
        {up ? <TrendingUp size={14} color="#22d3a5" /> : <TrendingDown size={14} color="#f43f5e" />}
      </div>
      <div style={{ fontSize: 18, fontWeight: 700, color: 'var(--text-primary)' }}>
        {fmtCcy(quote.last_price)}
      </div>
      <div style={{ fontSize: 12, fontWeight: 600, color: up ? '#22d3a5' : '#f43f5e', marginTop: 3 }}>
        {up ? '+' : ''}{fmtCcy(change)} ({changePct.toFixed(2)}%)
      </div>
      <div className="text-xs text-muted" style={{ marginTop: 6, display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '2px 8px' }}>
        <span>H: {fmtCcy(quote.ohlc?.high)}</span>
        <span>L: {fmtCcy(quote.ohlc?.low)}</span>
        <span>O: {fmtCcy(quote.ohlc?.open)}</span>
        <span>V: {fmtVol(quote.volume)}</span>
      </div>
    </div>
  )
}

export default function Market() {
  const [watchlistQuotes, setWatchlistQuotes] = useState({})
  const [customSymbols, setCustomSymbols] = useState([])
  const [customQuotes, setCustomQuotes] = useState({})
  const [loading, setLoading] = useState(true)
  const [selectedSymbol, setSelectedSymbol] = useState(null)
  const [history, setHistory] = useState([])
  const [histLoading, setHistLoading] = useState(false)
  const [timeRange, setTimeRange] = useState('1M')
  const [autoRefresh, setAutoRefresh] = useState(false)
  const [fundamentals, setFundamentals] = useState(null)
  const [fundLoading, setFundLoading] = useState(false)
  const [lastUpdated, setLastUpdated] = useState(null)

  // Search state
  const [searchQuery, setSearchQuery] = useState('')
  const [searchResults, setSearchResults] = useState([])
  const [searchOpen, setSearchOpen] = useState(false)
  const [searching, setSearching] = useState(false)
  const searchRef = useRef(null)
  const debounceRef = useRef(null)

  // Load default watchlist
  const loadWatchlist = useCallback(async () => {
    setLoading(true)
    try {
      const r = await marketApi.watchlist()
      setWatchlistQuotes(r.data.quotes ?? {})
      setLastUpdated(new Date())
    } catch { setWatchlistQuotes({}) }
    finally { setLoading(false) }
  }, [])

  // Load custom symbols quotes
  const loadCustom = useCallback(async () => {
    if (customSymbols.length === 0) { setCustomQuotes({}); return }
    try {
      const r = await marketApi.quotes(customSymbols.join(','))
      setCustomQuotes(r.data.quotes ?? {})
    } catch { /* keep old data */ }
  }, [customSymbols])

  useEffect(() => { loadWatchlist() }, [loadWatchlist])
  useEffect(() => { loadCustom() }, [loadCustom])

  // Auto-refresh
  useEffect(() => {
    if (!autoRefresh) return
    const id = setInterval(() => {
      if (isMarketOpen()) {
        loadWatchlist()
        loadCustom()
      }
    }, 15000)
    return () => clearInterval(id)
  }, [autoRefresh, loadWatchlist, loadCustom])

  // Search debounce
  useEffect(() => {
    if (!searchQuery.trim() || searchQuery.trim().length < 2) {
      setSearchResults([])
      return
    }
    if (debounceRef.current) clearTimeout(debounceRef.current)
    debounceRef.current = setTimeout(async () => {
      setSearching(true)
      try {
        const r = await marketApi.searchInstruments(searchQuery.trim())
        setSearchResults(r.data.results ?? [])
        setSearchOpen(true)
      } catch { setSearchResults([]) }
      finally { setSearching(false) }
    }, 300)
    return () => { if (debounceRef.current) clearTimeout(debounceRef.current) }
  }, [searchQuery])

  // Close dropdown on outside click
  useEffect(() => {
    const handler = (e) => {
      if (searchRef.current && !searchRef.current.contains(e.target)) {
        setSearchOpen(false)
      }
    }
    document.addEventListener('mousedown', handler)
    return () => document.removeEventListener('mousedown', handler)
  }, [])

  const addSymbol = (symbol) => {
    if (!customSymbols.includes(symbol)) {
      setCustomSymbols(prev => [...prev, symbol])
    }
    setSearchQuery('')
    setSearchOpen(false)
    selectStock(symbol)
  }

  const removeSymbol = (symbol) => {
    setCustomSymbols(prev => prev.filter(s => s !== symbol))
    const key = `NSE:${symbol}`
    setCustomQuotes(prev => {
      const next = { ...prev }
      delete next[key]
      return next
    })
    if (selectedSymbol === symbol) setSelectedSymbol(null)
  }

  const loadHistory = async (sym, range) => {
    const r_ = range || timeRange
    const cfg = TIME_RANGES.find(t => t.key === r_) || TIME_RANGES[2]
    setSelectedSymbol(sym)
    setHistLoading(true)
    try {
      let fromDate, toDate
      const today = new Date()
      toDate = today.toISOString().split('T')[0]
      if (cfg.days === 0) {
        fromDate = toDate // same day
      } else {
        const from = new Date(today)
        from.setDate(from.getDate() - cfg.days)
        fromDate = from.toISOString().split('T')[0]
      }
      const r = await marketApi.history(sym, cfg.interval, fromDate, toDate)
      setHistory(r.data.candles ?? [])
    } catch { setHistory([]) }
    finally { setHistLoading(false) }
  }

  const loadFundamentals = async (sym) => {
    setFundLoading(true)
    try {
      const r = await marketApi.fundamentals(sym)
      setFundamentals(r.data)
    } catch { setFundamentals(null) }
    finally { setFundLoading(false) }
  }

  const selectStock = (sym) => {
    loadHistory(sym)
    loadFundamentals(sym)
  }

  useEffect(() => {
    if (selectedSymbol) loadHistory(selectedSymbol, timeRange)
  }, [timeRange])

  const refreshAll = () => {
    loadWatchlist()
    loadCustom()
  }

  const marketOpen = isMarketOpen()
  const watchlistKeys = Object.keys(watchlistQuotes).sort()
  const customKeys = Object.keys(customQuotes).sort()

  return (
    <div>
      {/* Header */}
      <div className="flex-between mb-6">
        <div className="page-header" style={{ marginBottom: 0 }}>
          <h1 className="page-title" style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
            <Activity size={24} color="#6366f1" /> Live Market
          </h1>
          <p className="page-sub">Real-time quotes & charts from Zerodha Kite Connect</p>
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
          <button className="btn btn-ghost btn-sm flex-center gap-2" onClick={refreshAll}>
            <RefreshCw size={14} /> Refresh
          </button>
        </div>
      </div>

      {/* Search bar */}
      <div ref={searchRef} style={{ position: 'relative', marginBottom: 20 }}>
        <div style={{
          display: 'flex', alignItems: 'center', gap: 10,
          background: 'rgba(255,255,255,0.04)', border: '1px solid rgba(255,255,255,0.08)',
          borderRadius: 12, padding: '10px 16px',
        }}>
          <Search size={18} color="#94a3b8" />
          <input
            type="text"
            placeholder="Search any stock by name or symbol (e.g. Reliance, TCS, HDFC)..."
            value={searchQuery}
            onChange={e => setSearchQuery(e.target.value)}
            onFocus={() => searchResults.length > 0 && setSearchOpen(true)}
            style={{
              flex: 1, background: 'transparent', border: 'none', outline: 'none',
              color: 'var(--text-primary)', fontSize: 14, fontFamily: 'inherit',
            }}
          />
          {searchQuery && (
            <button onClick={() => { setSearchQuery(''); setSearchOpen(false) }}
              style={{ background: 'none', border: 'none', cursor: 'pointer', padding: 0 }}>
              <X size={16} color="#94a3b8" />
            </button>
          )}
          {searching && <span className="spinner" style={{ width: 16, height: 16, borderWidth: 2 }} />}
        </div>

        {/* Dropdown */}
        {searchOpen && searchResults.length > 0 && (
          <div style={{
            position: 'absolute', top: '100%', left: 0, right: 0, marginTop: 4,
            background: '#0e1421', border: '1px solid rgba(255,255,255,0.1)',
            borderRadius: 12, maxHeight: 320, overflowY: 'auto', zIndex: 50,
            boxShadow: '0 12px 40px rgba(0,0,0,0.5)',
          }}>
            {searchResults.map((inst, i) => (
              <div
                key={i}
                onClick={() => addSymbol(inst.symbol)}
                style={{
                  display: 'flex', justifyContent: 'space-between', alignItems: 'center',
                  padding: '10px 16px', cursor: 'pointer',
                  borderBottom: i < searchResults.length - 1 ? '1px solid rgba(255,255,255,0.04)' : 'none',
                  transition: 'background 0.15s',
                }}
                onMouseEnter={e => e.currentTarget.style.background = 'rgba(99,102,241,0.08)'}
                onMouseLeave={e => e.currentTarget.style.background = 'transparent'}
              >
                <div>
                  <span style={{ fontWeight: 600, color: 'var(--text-primary)', fontSize: 13 }}>{inst.symbol}</span>
                  <span className="text-xs text-muted" style={{ marginLeft: 8 }}>{inst.name}</span>
                </div>
                <span className="text-xs text-muted">{inst.exchange}</span>
              </div>
            ))}
          </div>
        )}
      </div>

      {lastUpdated && (
        <div className="text-xs text-muted mb-4" style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
          <Clock size={12} /> Last updated: {lastUpdated.toLocaleTimeString()}
        </div>
      )}

      {loading && watchlistKeys.length === 0 ? (
        <div className="empty-state"><span className="spinner" style={{ width: 36, height: 36, borderWidth: 3 }} /></div>
      ) : watchlistKeys.length === 0 && customKeys.length === 0 ? (
        <div className="empty-state card">
          <Activity size={48} />
          <p>No market data available.<br />Link Zerodha and sync holdings first.</p>
        </div>
      ) : (
        <>
          {/* Watchlist */}
          {watchlistKeys.length > 0 && (
            <div style={{ marginBottom: 24 }}>
              <h3 style={{ fontSize: 15, fontWeight: 600, marginBottom: 12, display: 'flex', alignItems: 'center', gap: 8, color: 'var(--text-primary)' }}>
                <Star size={16} color="#f59e0b" /> Blue-Chip Watchlist
              </h3>
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(200px, 1fr))', gap: 12 }}>
                {watchlistKeys.map(key => (
                  <QuoteCard
                    key={key}
                    symKey={key}
                    quote={watchlistQuotes[key]}
                    isSelected={selectedSymbol === key.split(':').pop()}
                    onClick={selectStock}
                  />
                ))}
              </div>
            </div>
          )}

          {/* Custom symbols */}
          {customKeys.length > 0 && (
            <div style={{ marginBottom: 24 }}>
              <h3 style={{ fontSize: 15, fontWeight: 600, marginBottom: 12, display: 'flex', alignItems: 'center', gap: 8, color: 'var(--text-primary)' }}>
                <Search size={16} color="#6366f1" /> Searched Stocks
              </h3>
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(200px, 1fr))', gap: 12 }}>
                {customKeys.map(key => {
                  const sym = key.split(':').pop()
                  return (
                    <div key={key} style={{ position: 'relative' }}>
                      <QuoteCard
                        symKey={key}
                        quote={customQuotes[key]}
                        isSelected={selectedSymbol === sym}
                        onClick={selectStock}
                      />
                      <button
                        onClick={(e) => { e.stopPropagation(); removeSymbol(sym) }}
                        style={{
                          position: 'absolute', top: 8, right: 8, background: 'rgba(244,63,94,0.15)',
                          border: 'none', borderRadius: '50%', width: 22, height: 22,
                          display: 'flex', alignItems: 'center', justifyContent: 'center', cursor: 'pointer',
                        }}
                      >
                        <X size={12} color="#f43f5e" />
                      </button>
                    </div>
                  )
                })}
              </div>
            </div>
          )}

          {/* Fundamentals */}
          {selectedSymbol && (
            <MetricsPanel data={fundamentals} loading={fundLoading} />
          )}

          {/* Chart */}
          {selectedSymbol && (
            <div className="card">
              <div className="flex-between" style={{ marginBottom: 16 }}>
                <h3 style={{ fontSize: 15, fontWeight: 600 }}>
                  {selectedSymbol} — Price History
                </h3>
                <div className="flex gap-2">
                  {TIME_RANGES.map(({ key, label }) => (
                    <button
                      key={key}
                      className={`btn btn-sm ${timeRange === key ? 'btn-primary' : 'btn-ghost'}`}
                      onClick={() => setTimeRange(key)}
                      style={{ fontSize: 11, padding: '4px 10px' }}
                    >
                      {label}
                    </button>
                  ))}
                </div>
              </div>
              {histLoading ? (
                <div className="empty-state"><span className="spinner" /></div>
              ) : history.length === 0 ? (
                <div className="empty-state text-muted">No historical data available</div>
              ) : (
                <ResponsiveContainer width="100%" height={350}>
                  <ComposedChart data={history}>
                    <defs>
                      <linearGradient id="gradClose" x1="0" y1="0" x2="0" y2="1">
                        <stop offset="5%" stopColor="#6366f1" stopOpacity={0.25} />
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
                        const cfg = TIME_RANGES.find(r => r.key === timeRange)
                        return cfg && cfg.interval === 'day'
                          ? `${d.getDate()}/${d.getMonth() + 1}`
                          : `${d.getHours()}:${String(d.getMinutes()).padStart(2, '0')}`
                      }}
                    />
                    <YAxis
                      yAxisId="price"
                      domain={['auto', 'auto']}
                      tick={{ fill: '#94a3b8', fontSize: 11 }}
                      axisLine={false} tickLine={false}
                      tickFormatter={v => '₹' + v}
                    />
                    <YAxis
                      yAxisId="volume"
                      orientation="right"
                      tick={{ fill: '#94a3b8', fontSize: 10 }}
                      axisLine={false} tickLine={false}
                      tickFormatter={v => fmtVol(v)}
                      hide
                    />
                    <Tooltip
                      contentStyle={{ background: '#0e1421', border: '1px solid rgba(255,255,255,0.1)', borderRadius: 10, fontSize: 12 }}
                      formatter={(v, name) => {
                        if (name === 'volume') return [fmtVol(v), 'Volume']
                        return [fmtCcy(v), name.charAt(0).toUpperCase() + name.slice(1)]
                      }}
                      labelFormatter={t => new Date(t).toLocaleString()}
                    />
                    <Bar yAxisId="volume" dataKey="volume" fill="rgba(99,102,241,0.12)" radius={[2, 2, 0, 0]} />
                    <Area yAxisId="price" type="monotone" dataKey="close" stroke="#6366f1" strokeWidth={2} fill="url(#gradClose)" name="close" />
                    <Line yAxisId="price" type="monotone" dataKey="high" stroke="rgba(34,211,165,0.3)" strokeWidth={1} dot={false} name="high" />
                    <Line yAxisId="price" type="monotone" dataKey="low" stroke="rgba(244,63,94,0.3)" strokeWidth={1} dot={false} name="low" />
                  </ComposedChart>
                </ResponsiveContainer>
              )}
            </div>
          )}
        </>
      )}
    </div>
  )
}
