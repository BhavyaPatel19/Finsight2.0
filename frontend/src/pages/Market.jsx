import { useEffect, useState, useCallback, useRef } from 'react'
import { useSearchParams } from 'react-router-dom'
import { useTheme } from '../context/ThemeContext'
import { getChartColors } from '../utils/chartTheme'
import { marketApi } from '../api/client'
import {
  Activity, RefreshCw, TrendingUp, TrendingDown,
  Search, X, BarChart3, Loader, Sparkles
} from 'lucide-react'
import {
  XAxis, YAxis, Tooltip,
  ResponsiveContainer, CartesianGrid,
  ComposedChart, Bar, Area, Line
} from 'recharts'
import AnimatedCheckbox from '../components/AnimatedCheckbox'

/* ── Formatters ── */
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
  { key: '1D', label: '1D', interval: 'minute', days: 0 },
  { key: '1W', label: '1W', interval: '15minute', days: 7 },
  { key: '1M', label: '1M', interval: 'day', days: 30 },
  { key: '3M', label: '3M', interval: 'day', days: 90 },
  { key: '1Y', label: '1Y', interval: 'day', days: 365 },
]

/* ── Company logo domains ── */
const COMPANY_DOMAINS = {
  RELIANCE: 'ril.com', TCS: 'tcs.com', HDFCBANK: 'hdfcbank.com',
  INFY: 'infosys.com', ITC: 'itcportal.com', SBIN: 'sbi.co.in',
  BAJFINANCE: 'bajajfinserv.in', BHARTIARTL: 'airtel.in',
  LT: 'larsentoubro.com', ICICIBANK: 'icicibank.com',
  WIPRO: 'wipro.com', HCLTECH: 'hcltech.com',
  TATAMOTORS: 'tatamotors.com', TATASTEEL: 'tatasteel.com',
  NESTLEIND: 'nestle.in', HINDUNILVR: 'hul.co.in',
  KOTAKBANK: 'kotak.com', AXISBANK: 'axisbank.com',
  MARUTI: 'marutisuzuki.com', ASIANPAINT: 'asianpaints.com',
  ADANIENT: 'adani.com', SUNPHARMA: 'sunpharma.com',
  TECHM: 'techmahindra.com', ULTRACEMCO: 'ultratechcement.com',
  TITAN: 'titancompany.in', POWERGRID: 'powergrid.in',
  NTPC: 'ntpc.co.in', JSWSTEEL: 'jsw.in',
  ONGC: 'ongcindia.com', COALINDIA: 'coalindia.in',
}

const COMPANY_NAMES = {
  RELIANCE: 'Reliance Industries', TCS: 'Tata Consultancy Services',
  HDFCBANK: 'HDFC Bank', INFY: 'Infosys', ITC: 'ITC Limited',
  SBIN: 'State Bank of India', BAJFINANCE: 'Bajaj Finance',
  BHARTIARTL: 'Bharti Airtel', LT: 'Larsen & Toubro',
  ICICIBANK: 'ICICI Bank', WIPRO: 'Wipro', HCLTECH: 'HCL Technologies',
  TATAMOTORS: 'Tata Motors', TATASTEEL: 'Tata Steel',
  NESTLEIND: 'Nestle India', HINDUNILVR: 'Hindustan Unilever',
  KOTAKBANK: 'Kotak Mahindra Bank', AXISBANK: 'Axis Bank',
  MARUTI: 'Maruti Suzuki', ASIANPAINT: 'Asian Paints',
  ADANIENT: 'Adani Enterprises', SUNPHARMA: 'Sun Pharma',
  TECHM: 'Tech Mahindra', ULTRACEMCO: 'UltraTech Cement',
  TITAN: 'Titan Company', POWERGRID: 'Power Grid Corp',
  NTPC: 'NTPC Limited', JSWSTEEL: 'JSW Steel',
  ONGC: 'Oil & Natural Gas Corp', COALINDIA: 'Coal India',
}

function getLogoUrl(symbol) {
  const domain = COMPANY_DOMAINS[symbol.toUpperCase()]
  return domain ? `https://logo.clearbit.com/${domain}` : null
}

/* ── Company Logo ── */
function CompanyLogo({ symbol, size = 32, className, fallbackClass }) {
  const [err, setErr] = useState(false)
  const url = getLogoUrl(symbol)
  const initials = symbol.slice(0, 2).toUpperCase()

  if (!url || err) {
    return (
      <div
        className={fallbackClass || 'mk-logo-fallback'}
        style={size !== 32 ? { width: size, height: size, fontSize: size * 0.35, borderRadius: size > 40 ? 12 : 8 } : undefined}
      >
        {initials}
      </div>
    )
  }

  return (
    <img
      src={url}
      alt={symbol}
      className={className || 'mk-logo'}
      style={size !== 32 ? { width: size, height: size, borderRadius: size > 40 ? 12 : 8 } : undefined}
      onError={() => setErr(true)}
    />
  )
}

/* ── Stock Row (left panel) ── */
function StockRow({ symKey, quote, isSelected, onClick, isCustom, onRemove, customName }) {
  const sym = symKey.split(':').pop()
  const change = quote.last_price - (quote.ohlc?.close ?? quote.last_price)
  const changePct = quote.ohlc?.close ? (change / quote.ohlc.close) * 100 : 0
  const up = change >= 0
  const name = COMPANY_NAMES[sym] || customName || sym

  return (
    <div
      className={`mk-stock-row${isSelected ? ' selected' : ''}`}
      onClick={() => onClick(sym)}
    >
      <CompanyLogo symbol={sym} size={32} />
      <div className="mk-stock-info">
        <div className="mk-stock-sym">{sym}</div>
        <div className="mk-stock-name">{name}</div>
      </div>
      <div className="mk-stock-metrics">
        <div className="mk-price">{fmtCcy(quote.last_price)}</div>
        <div className="mk-metrics-row">
          <span className={`mk-change ${up ? 'up' : 'down'}`}>
            {up ? '+' : ''}{fmtCcy(Math.abs(change))}
          </span>
          <span className={`mk-change ${up ? 'up' : 'down'}`}>
            ({up ? '+' : ''}{changePct.toFixed(2)}%)
          </span>
          {quote.volume > 0 && (
            <span className="mk-stock-vol">{fmtVol(quote.volume)}</span>
          )}
        </div>
      </div>
      {isCustom && (
        <button className="mk-remove-btn" onClick={e => { e.stopPropagation(); onRemove(sym) }}>
          <X size={10} color="#f43f5e" />
        </button>
      )}
    </div>
  )
}

/* ── Fundamentals Grid ── */
function FundamentalsGrid({ data, loading }) {
  if (loading) {
    return (
      <div className="mk-chart-card">
        <div className="mk-insight-loading">
          <Loader size={14} className="spin" /> Loading fundamentals...
        </div>
      </div>
    )
  }
  if (!data || data.error) return null

  const deColor = data.debt_to_equity != null
    ? (data.debt_to_equity > 1.5 ? '#f43f5e' : data.debt_to_equity < 0.5 ? '#22d3a5' : undefined)
    : undefined
  const roeColor = data.roe != null
    ? (data.roe > 15 ? '#22d3a5' : data.roe < 10 ? '#f43f5e' : undefined)
    : undefined
  const roceColor = data.roce != null
    ? (data.roce > 15 ? '#22d3a5' : data.roce < 10 ? '#f43f5e' : undefined)
    : undefined

  const metrics = [
    data.pe_ratio != null && { label: 'P/E Ratio', value: data.pe_ratio.toFixed(2) },
    data.pb_ratio != null && { label: 'P/B Ratio', value: data.pb_ratio.toFixed(2) },
    data.roe != null && { label: 'ROE', value: fmtPct(data.roe), color: roeColor },
    data.roce != null && { label: 'ROCE', value: fmtPct(data.roce), color: roceColor },
    data.eps != null && { label: 'EPS', value: '₹' + data.eps.toFixed(2) },
    data.debt_to_equity != null && { label: 'D/E Ratio', value: data.debt_to_equity.toFixed(2), color: deColor },
    data.dividend_yield != null && { label: 'Div Yield', value: fmtPct(data.dividend_yield) },
    data.market_cap != null && { label: 'Market Cap', value: fmtMcap(data.market_cap) },
    data.book_value != null && { label: 'Book Value', value: '₹' + data.book_value.toFixed(2) },
    data.high_52w != null && { label: '52W High', value: fmtCcy(data.high_52w), color: '#22d3a5' },
    data.low_52w != null && { label: '52W Low', value: fmtCcy(data.low_52w), color: '#f43f5e' },
  ].filter(Boolean)

  return (
    <div className="mk-chart-card">
      <div className="mk-chart-header" style={{ marginBottom: 12 }}>
        <span className="mk-chart-title" style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          <BarChart3 size={15} color="var(--accent, #148F77)" /> Fundamentals
        </span>
        {data.sector && (
          <span className="badge" style={{ fontSize: 10 }}>{data.sector}</span>
        )}
      </div>
      <div className="mk-fund-grid">
        {metrics.map(m => (
          <div key={m.label} className="mk-fund-card">
            <div className="mk-fund-label">{m.label}</div>
            <div className="mk-fund-value" style={m.color ? { color: m.color } : undefined}>{m.value}</div>
          </div>
        ))}
      </div>
    </div>
  )
}

/* ── AI Insight Card ── */
const INSIGHT_SECTIONS = [
  { key: 'OVERVIEW', icon: '📋', color: 'var(--text-primary)' },
  { key: 'BULL CASE', icon: '🟢', color: '#22c55e' },
  { key: 'BEAR CASE', icon: '🔴', color: '#ef4444' },
  { key: 'KEY METRIC', icon: '📊', color: '#3b82f6' },
  { key: 'VERDICT', icon: '⚖️', color: '#f59e0b' },
]

function parseInsightSections(text) {
  const sections = []
  for (const { key, icon, color } of INSIGHT_SECTIONS) {
    const regex = new RegExp(`${key}:\\s*(.+?)(?=\\n(?:BULL|BEAR|KEY|VERDICT|$))`, 's')
    const match = text.match(regex)
    if (match) sections.push({ label: key, icon, color, text: match[1].trim() })
  }
  return sections
}

function AIInsightCard({ insight, loading }) {
  const sections = insight ? parseInsightSections(insight) : []
  const hasSections = sections.length > 0

  return (
    <div className="mk-insight-card">
      <div className="mk-insight-header">
        <Sparkles size={14} />
        AI Insights
        <span style={{ marginLeft: 'auto', fontSize: 10, color: 'var(--text-muted)', fontWeight: 400 }}>
          Powered by Groq
        </span>
      </div>
      {loading ? (
        <div className="mk-insight-loading">
          <span className="spinner" style={{ width: 14, height: 14, borderWidth: 2 }} />
          Analyzing fundamentals...
        </div>
      ) : hasSections ? (
        <div className="mk-insight-sections">
          {sections.map(s => (
            <div key={s.label} className="mk-insight-section">
              <div className="mk-insight-label" style={{ color: s.color }}>
                <span>{s.icon}</span> {s.label}
              </div>
              <p className="mk-insight-body">{s.text}</p>
            </div>
          ))}
        </div>
      ) : insight ? (
        <p className="mk-insight-text">{insight}</p>
      ) : (
        <p className="mk-insight-text" style={{ color: 'var(--text-muted)', fontStyle: 'italic' }}>
          Select a stock to view AI-generated insights.
        </p>
      )}
    </div>
  )
}

/* ── Market Open Check ── */
function isMarketOpen() {
  const now = new Date()
  const day = now.getDay()
  if (day === 0 || day === 6) return false
  const mins = now.getHours() * 60 + now.getMinutes()
  return mins >= 555 && mins <= 930
}

/* ================================================================
   Main Market Component
   ================================================================ */
export default function Market() {
  const { theme } = useTheme()
  const cc = getChartColors(theme)
  const [searchParams] = useSearchParams()
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

  // Search
  const [searchQuery, setSearchQuery] = useState('')
  const [searchResults, setSearchResults] = useState([])
  const [searchOpen, setSearchOpen] = useState(false)
  const [searching, setSearching] = useState(false)
  const searchRef = useRef(null)
  const debounceRef = useRef(null)

  // AI Insights
  const [insight, setInsight] = useState('')
  const [insightLoading, setInsightLoading] = useState(false)

  // Custom symbol names (from search results)
  const [customNames, setCustomNames] = useState({})

  /* ── Data loaders ── */
  const loadWatchlist = useCallback(async () => {
    setLoading(true)
    try {
      const r = await marketApi.watchlist()
      setWatchlistQuotes(r.data.quotes ?? {})
      setLastUpdated(new Date())
    } catch { setWatchlistQuotes({}) }
    finally { setLoading(false) }
  }, [])

  const loadCustom = useCallback(async () => {
    if (customSymbols.length === 0) { setCustomQuotes({}); return }
    try {
      const r = await marketApi.quotes(customSymbols.join(','))
      setCustomQuotes(r.data.quotes ?? {})
    } catch { /* keep old */ }
  }, [customSymbols])

  useEffect(() => { loadWatchlist() }, [loadWatchlist])
  useEffect(() => { loadCustom() }, [loadCustom])

  // Auto-select stock from URL query param (e.g., /market?symbol=INFY)
  useEffect(() => {
    const sym = searchParams.get('symbol')
    if (sym && !loading) {
      const upper = sym.toUpperCase()
      const inWatchlist = Object.keys(watchlistQuotes).some(k => k.split(':').pop() === upper)
      if (!inWatchlist && !customSymbols.includes(upper)) {
        setCustomSymbols(prev => [...prev, upper])
      }
      selectStock(upper)
    }
  }, [loading]) // run once after watchlist loads

  // Auto-refresh
  useEffect(() => {
    if (!autoRefresh) return
    const id = setInterval(() => {
      if (isMarketOpen()) { loadWatchlist(); loadCustom() }
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

  // Outside click
  useEffect(() => {
    const handler = (e) => {
      if (searchRef.current && !searchRef.current.contains(e.target)) setSearchOpen(false)
    }
    document.addEventListener('mousedown', handler)
    return () => document.removeEventListener('mousedown', handler)
  }, [])

  const loadHistory = async (sym, range) => {
    const r_ = range || timeRange
    const cfg = TIME_RANGES.find(t => t.key === r_) || TIME_RANGES[2]
    setHistLoading(true)
    try {
      const today = new Date()
      const toDate = today.toISOString().split('T')[0]
      let fromDate
      if (cfg.days === 0) {
        fromDate = toDate
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

  const loadInsight = async (sym) => {
    setInsightLoading(true)
    setInsight('')
    try {
      const r = await marketApi.insights(sym)
      setInsight(r.data.insight || '')
    } catch (err) { console.error('AI Insights error:', err); setInsight('') }
    finally { setInsightLoading(false) }
  }

  const selectStock = (sym) => {
    setSelectedSymbol(sym)
    setFundamentals(null)
    loadHistory(sym)
    loadFundamentals(sym)
    loadInsight(sym)
  }

  useEffect(() => {
    if (selectedSymbol) loadHistory(selectedSymbol, timeRange)
  }, [timeRange])

  const addSymbol = (symbol, name) => {
    if (!customSymbols.includes(symbol)) {
      setCustomSymbols(prev => [...prev, symbol])
      if (name) setCustomNames(prev => ({ ...prev, [symbol]: name }))
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

  const refreshAll = () => { loadWatchlist(); loadCustom() }

  const marketOpen = isMarketOpen()
  const watchlistKeys = Object.keys(watchlistQuotes).sort()
  const customKeys = Object.keys(customQuotes).sort()

  // Get quote for selected symbol
  const selectedQuote = selectedSymbol
    ? (watchlistQuotes[`NSE:${selectedSymbol}`] || customQuotes[`NSE:${selectedSymbol}`])
    : null
  const selectedChange = selectedQuote
    ? selectedQuote.last_price - (selectedQuote.ohlc?.close ?? selectedQuote.last_price)
    : 0
  const selectedChangePct = selectedQuote?.ohlc?.close
    ? (selectedChange / selectedQuote.ohlc.close) * 100
    : 0
  const selectedUp = selectedChange >= 0

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: 'calc(100vh - 88px)' }}>
      {/* Page title */}
      <div className="flex-between" style={{ flexShrink: 0, marginBottom: 14 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
          <Activity size={22} color="var(--accent, #148F77)" />
          <div>
            <h1 style={{ fontSize: 20, fontWeight: 700, color: 'var(--text-primary)', margin: 0 }}>Live Market</h1>
            <p style={{ fontSize: 12, color: 'var(--text-muted)', margin: 0 }}>NSE quotes · live via Zerodha when linked, otherwise delayed via Yahoo Finance</p>
          </div>
        </div>
      </div>

      {/* Two-panel layout */}
      <div className="mk-layout" style={{ flex: 1 }}>

        {/* ── LEFT PANEL ── */}
        <div className="mk-left">
          <div className="mk-left-header">
            <div ref={searchRef} style={{ position: 'relative' }}>
              <div className="mk-search-box">
                <Search size={15} color="var(--text-muted)" />
                <input
                  className="mk-search-input"
                  placeholder="Search stocks..."
                  value={searchQuery}
                  onChange={e => setSearchQuery(e.target.value)}
                  onFocus={() => searchResults.length > 0 && setSearchOpen(true)}
                />
                {searching && <span className="spinner" style={{ width: 14, height: 14, borderWidth: 2 }} />}
                {searchQuery && !searching && (
                  <button onClick={() => { setSearchQuery(''); setSearchOpen(false) }}
                    style={{ background: 'none', border: 'none', cursor: 'pointer', padding: 0 }}>
                    <X size={13} color="var(--text-muted)" />
                  </button>
                )}
              </div>
              {searchOpen && searchResults.length > 0 && (
                <div className="mk-search-dropdown">
                  {searchResults.map((inst, i) => (
                    <div key={i} className="mk-search-item" onClick={() => addSymbol(inst.symbol, inst.name)}>
                      <div>
                        <span style={{ fontWeight: 600, fontSize: 12, color: 'var(--text-primary)' }}>{inst.symbol}</span>
                        <span style={{ fontSize: 11, color: 'var(--text-muted)', marginLeft: 8 }}>{inst.name}</span>
                      </div>
                      <span style={{ fontSize: 10, color: 'var(--text-muted)' }}>{inst.exchange}</span>
                    </div>
                  ))}
                </div>
              )}
            </div>
          </div>

          {/* Controls */}
          <div className="mk-controls">
            <div className={`mk-status-pill ${marketOpen ? 'open' : 'closed'}`}>
              <span className="mk-status-dot" />
              {marketOpen ? 'Open' : 'Closed'}
            </div>
            <div style={{ display: 'flex', alignItems: 'center', gap: 5, fontSize: 11, color: 'var(--text-muted)' }}>
              <AnimatedCheckbox checked={autoRefresh} onChange={e => setAutoRefresh(e.target.checked)} size={15} />
              <span style={{ cursor: 'pointer' }} onClick={() => setAutoRefresh(v => !v)}>Auto</span>
            </div>
            <button className="btn btn-ghost btn-sm flex-center gap-2" onClick={refreshAll}
              style={{ padding: '4px 10px', fontSize: 11 }}>
              <RefreshCw size={12} /> Refresh
            </button>
            {lastUpdated && (
              <span style={{ fontSize: 10, color: 'var(--text-muted)', marginLeft: 'auto' }}>
                {lastUpdated.toLocaleTimeString()}
              </span>
            )}
          </div>

          {/* Stock list */}
          <div className="mk-stock-list">
            {loading && watchlistKeys.length === 0 ? (
              <div style={{ padding: '40px 20px', textAlign: 'center' }}>
                <span className="spinner" style={{ width: 28, height: 28, borderWidth: 3 }} />
              </div>
            ) : watchlistKeys.length === 0 && customKeys.length === 0 ? (
              <div style={{ padding: '40px 20px', textAlign: 'center', color: 'var(--text-muted)', fontSize: 13 }}>
                <Activity size={32} style={{ opacity: 0.3, marginBottom: 8 }} />
                <p>No data for this symbol.</p>
              </div>
            ) : (
              <>
                {watchlistKeys.length > 0 && (
                  <>
                    <div className="mk-section-label">Blue-Chips</div>
                    {watchlistKeys.map(key => (
                      <StockRow
                        key={key}
                        symKey={key}
                        quote={watchlistQuotes[key]}
                        isSelected={selectedSymbol === key.split(':').pop()}
                        onClick={selectStock}
                        isCustom={false}
                      />
                    ))}
                  </>
                )}
                {customKeys.length > 0 && (
                  <>
                    <div className="mk-section-label" style={{ marginTop: 8 }}>Searched</div>
                    {customKeys.map(key => {
                      const sym = key.split(':').pop()
                      return (
                      <StockRow
                        key={key}
                        symKey={key}
                        quote={customQuotes[key]}
                        isSelected={selectedSymbol === sym}
                        onClick={selectStock}
                        isCustom={true}
                        onRemove={removeSymbol}
                        customName={customNames[sym]}
                      />
                      )
                    })}
                  </>
                )}
              </>
            )}
          </div>
        </div>

        {/* ── RIGHT PANEL ── */}
        <div className="mk-right">
          {!selectedSymbol ? (
            <div className="mk-right-empty">
              <BarChart3 size={48} style={{ opacity: 0.15 }} />
              <p style={{ fontSize: 14 }}>Select a stock to view analysis</p>
              <p style={{ fontSize: 12 }}>Click on any stock from the list</p>
            </div>
          ) : (
            <>
              {/* Stock Header */}
              <div className="mk-stock-header">
                <CompanyLogo
                  symbol={selectedSymbol}
                  size={48}
                  className="mk-header-logo"
                  fallbackClass="mk-header-logo-fallback"
                />
                <div>
                  <div className="mk-header-title">{COMPANY_NAMES[selectedSymbol] || customNames[selectedSymbol] || selectedSymbol}</div>
                  <div className="mk-header-sector">
                    {fundamentals?.sector || 'NSE'}
                    {fundamentals?.industry ? ` · ${fundamentals.industry}` : ''}
                  </div>
                </div>
                <div className="mk-header-price-block">
                  <div className="mk-header-price">{selectedQuote ? fmtCcy(selectedQuote.last_price) : '—'}</div>
                  {selectedQuote && (
                    <div className="mk-header-change" style={{
                      color: selectedUp ? '#22d3a5' : '#f43f5e',
                      textShadow: selectedUp
                        ? '0 0 8px rgba(34,211,165,0.5)'
                        : '0 0 8px rgba(244,63,94,0.5)'
                    }}>
                      {selectedUp ? <TrendingUp size={14} style={{ verticalAlign: 'middle', marginRight: 4 }} /> : <TrendingDown size={14} style={{ verticalAlign: 'middle', marginRight: 4 }} />}
                      {selectedUp ? '+' : ''}{fmtCcy(selectedChange)} ({selectedChangePct.toFixed(2)}%)
                    </div>
                  )}
                </div>
              </div>

              {/* Price Chart */}
              <div className="mk-chart-card">
                <div className="mk-chart-header">
                  <span className="mk-chart-title">Price History</span>
                  <div className="mk-time-btns">
                    {TIME_RANGES.map(({ key, label }) => (
                      <button
                        key={key}
                        className={`mk-time-btn${timeRange === key ? ' active' : ''}`}
                        onClick={() => setTimeRange(key)}
                      >
                        {label}
                      </button>
                    ))}
                  </div>
                </div>
                {histLoading ? (
                  <div style={{ padding: '40px 20px', textAlign: 'center' }}>
                    <span className="spinner" />
                  </div>
                ) : history.length === 0 ? (
                  <div style={{ padding: '40px 20px', textAlign: 'center', color: 'var(--text-muted)', fontSize: 13 }}>
                    No historical data available
                  </div>
                ) : (
                  <ResponsiveContainer width="100%" height={280}>
                    <ComposedChart data={history}>
                      <defs>
                        <linearGradient id="gradClose" x1="0" y1="0" x2="0" y2="1">
                          <stop offset="5%" stopColor="#6366f1" stopOpacity={0.25} />
                          <stop offset="95%" stopColor="#6366f1" stopOpacity={0} />
                        </linearGradient>
                      </defs>
                      <CartesianGrid strokeDasharray="3 3" stroke={cc.grid} />
                      <XAxis
                        dataKey="timestamp"
                        tick={{ fill: cc.tick, fontSize: 10 }}
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
                        tick={{ fill: cc.tick, fontSize: 11 }}
                        axisLine={false} tickLine={false}
                        tickFormatter={v => '₹' + v}
                      />
                      <YAxis
                        yAxisId="volume"
                        orientation="right"
                        hide
                      />
                      <Tooltip
                        contentStyle={cc.tooltip}
                        labelStyle={{ color: cc.labelPrimary }}
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

              {/* Fundamentals + AI Insights side-by-side */}
              <div className="mk-bottom-grid">
                <FundamentalsGrid data={fundamentals} loading={fundLoading} />
                <AIInsightCard insight={insight} loading={insightLoading} />
              </div>
            </>
          )}
        </div>
      </div>
    </div>
  )
}
