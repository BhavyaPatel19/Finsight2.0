import { useEffect, useState, useCallback, useRef } from 'react'
import { useNavigate } from 'react-router-dom'
import { watchlistApi, marketApi } from '../api/client'
import {
  Plus, X, Search, Edit3, Trash2, Check, Star,
  TrendingUp, TrendingDown, StickyNote, MoreVertical,
  List, ChevronRight, ArrowUpDown, Filter,
} from 'lucide-react'
import {
  ResponsiveContainer, AreaChart, Area,
} from 'recharts'
import GlowCard from '../components/GlowCard'

const fmt = (n) => n == null ? '—' : new Intl.NumberFormat('en-IN', { maximumFractionDigits: 2 }).format(n)
const fmtCcy = (n) => n == null ? '—' : '₹' + new Intl.NumberFormat('en-IN', { maximumFractionDigits: 2 }).format(n)
const fmtMcap = (n) => {
  if (n == null) return '—'
  const cr = n / 1e7
  if (cr >= 100000) return `₹${(cr / 100000).toFixed(2)}L Cr`
  if (cr >= 1000) return `₹${(cr / 1000).toFixed(1)}K Cr`
  return `₹${cr.toFixed(0)} Cr`
}

/* ── Mini Sparkline ── */
function Sparkline({ data, color }) {
  if (!data || data.length < 2) return <div className="wl-sparkline-empty" />
  return (
    <div className="wl-sparkline">
      <ResponsiveContainer width="100%" height={28}>
        <AreaChart data={data}>
          <Area
            type="monotone" dataKey="close"
            stroke={color} fill={color} fillOpacity={0.1}
            strokeWidth={1.5} dot={false} isAnimationActive={false}
          />
        </AreaChart>
      </ResponsiveContainer>
    </div>
  )
}

/* ── 52-Week Range Bar ── */
function RangeBar({ low, high, current }) {
  if (!low || !high || !current) return <span className="text-muted">—</span>
  const pct = Math.min(100, Math.max(0, ((current - low) / (high - low)) * 100))
  return (
    <div className="wl-range-bar">
      <div className="wl-range-track">
        <div className="wl-range-fill" style={{ width: `${pct}%` }} />
        <div className="wl-range-dot" style={{ left: `${pct}%` }} />
      </div>
      <div className="wl-range-labels">
        <span>{fmtCcy(low)}</span>
        <span>{fmtCcy(high)}</span>
      </div>
    </div>
  )
}

/* ── Notes Inline Editor ── */
function NotesCell({ notes, onSave }) {
  const [editing, setEditing] = useState(false)
  const [text, setText] = useState(notes || '')
  const inputRef = useRef(null)

  useEffect(() => { if (editing && inputRef.current) inputRef.current.focus() }, [editing])

  const save = () => {
    setEditing(false)
    if (text !== (notes || '')) onSave(text)
  }

  if (editing) {
    return (
      <div className="wl-notes-edit">
        <input
          ref={inputRef}
          value={text}
          onChange={e => setText(e.target.value)}
          onKeyDown={e => { if (e.key === 'Enter') save(); if (e.key === 'Escape') setEditing(false) }}
          onBlur={save}
          placeholder="Add note..."
          className="wl-notes-input"
        />
      </div>
    )
  }

  return (
    <div className="wl-notes-cell" onClick={() => setEditing(true)} title="Click to edit">
      {notes ? (
        <span className="wl-notes-text">{notes}</span>
      ) : (
        <span className="wl-notes-placeholder"><StickyNote size={12} /> Add note</span>
      )}
    </div>
  )
}

/* ── Main Watchlist Page ── */
export default function WatchlistPage() {
  const navigate = useNavigate()

  // Watchlist state
  const [watchlists, setWatchlists] = useState([])
  const [selectedId, setSelectedId] = useState(null)
  const [items, setItems] = useState([])
  const [quotes, setQuotes] = useState({})
  const [sparklines, setSparklines] = useState({})
  const [fundamentals, setFundamentals] = useState({})
  const [loading, setLoading] = useState(true)
  const [quotesLoading, setQuotesLoading] = useState(false)

  // Create / rename state
  const [creating, setCreating] = useState(false)
  const [newName, setNewName] = useState('')
  const [renamingId, setRenamingId] = useState(null)
  const [renameText, setRenameText] = useState('')

  // Search state
  const [searchQuery, setSearchQuery] = useState('')
  const [searchResults, setSearchResults] = useState([])
  const [searchOpen, setSearchOpen] = useState(false)
  const debounceRef = useRef(null)

  // Sort state
  const [sortKey, setSortKey] = useState(null) // 'symbol' | 'change' | 'pe'
  const [sortDir, setSortDir] = useState('asc')

  // ── Load watchlists ──
  const loadWatchlists = useCallback(async () => {
    try {
      const r = await watchlistApi.list()
      setWatchlists(r.data)
      if (r.data.length > 0 && !selectedId) {
        const def = r.data.find(w => w.is_default) || r.data[0]
        setSelectedId(def.id)
      }
    } catch (err) { console.error('Load watchlists:', err) }
    finally { setLoading(false) }
  }, [])

  useEffect(() => { loadWatchlists() }, [loadWatchlists])

  // ── Load selected watchlist details ──
  const loadDetail = useCallback(async (id) => {
    if (!id) return
    try {
      const r = await watchlistApi.get(id)
      setItems(r.data.items || [])
    } catch (err) { console.error('Load detail:', err) }
  }, [])

  useEffect(() => { if (selectedId) loadDetail(selectedId) }, [selectedId, loadDetail])

  // ── Load quotes for items ──
  const loadQuotes = useCallback(async () => {
    if (!selectedId || items.length === 0) { setQuotes({}); return }
    setQuotesLoading(true)
    try {
      const r = await watchlistApi.quotes(selectedId)
      setQuotes(r.data.quotes || {})
    } catch (err) { console.error('Load quotes:', err) }
    finally { setQuotesLoading(false) }
  }, [selectedId, items])

  useEffect(() => { loadQuotes() }, [loadQuotes])

  // ── Load sparklines (7-day history) ──
  useEffect(() => {
    if (items.length === 0) return
    const today = new Date()
    const from = new Date(today)
    from.setDate(from.getDate() - 10)
    const fromStr = from.toISOString().split('T')[0]
    const toStr = today.toISOString().split('T')[0]

    items.forEach(async (item) => {
      if (sparklines[item.symbol]) return
      try {
        const r = await marketApi.history(item.symbol, 'day', fromStr, toStr)
        setSparklines(prev => ({ ...prev, [item.symbol]: r.data.candles || [] }))
      } catch { /* ignore */ }
    })
  }, [items])

  // ── Load fundamentals ──
  useEffect(() => {
    if (items.length === 0) return
    items.forEach(async (item) => {
      if (fundamentals[item.symbol]) return
      try {
        const r = await marketApi.fundamentals(item.symbol)
        setFundamentals(prev => ({ ...prev, [item.symbol]: r.data }))
      } catch { /* ignore */ }
    })
  }, [items])

  // ── Search instruments ──
  useEffect(() => {
    if (debounceRef.current) clearTimeout(debounceRef.current)
    if (searchQuery.trim().length < 2) { setSearchResults([]); return }
    debounceRef.current = setTimeout(async () => {
      try {
        const r = await marketApi.searchInstruments(searchQuery)
        setSearchResults(r.data.results || [])
      } catch { setSearchResults([]) }
    }, 300)
    return () => clearTimeout(debounceRef.current)
  }, [searchQuery])

  // ── Actions ──
  const createWatchlist = async () => {
    if (!newName.trim()) return
    try {
      const r = await watchlistApi.create(newName.trim())
      setNewName('')
      setCreating(false)
      await loadWatchlists()
      setSelectedId(r.data.id)
    } catch (err) { console.error('Create:', err) }
  }

  const renameWatchlist = async (id) => {
    if (!renameText.trim()) return
    try {
      await watchlistApi.update(id, { name: renameText.trim() })
      setRenamingId(null)
      setRenameText('')
      await loadWatchlists()
    } catch (err) { console.error('Rename:', err) }
  }

  const deleteWatchlist = async (id) => {
    try {
      await watchlistApi.delete(id)
      if (selectedId === id) setSelectedId(null)
      await loadWatchlists()
    } catch (err) { console.error('Delete:', err) }
  }

  const setDefault = async (id) => {
    try {
      await watchlistApi.update(id, { is_default: true })
      await loadWatchlists()
    } catch (err) { console.error('Set default:', err) }
  }

  const addStock = async (symbol) => {
    if (!selectedId) return
    try {
      await watchlistApi.addItem(selectedId, symbol)
      setSearchQuery('')
      setSearchOpen(false)
      await loadDetail(selectedId)
      await loadWatchlists()
    } catch (err) { console.error('Add stock:', err) }
  }

  const removeStock = async (symbol) => {
    if (!selectedId) return
    try {
      await watchlistApi.removeItem(selectedId, symbol)
      setItems(prev => prev.filter(i => i.symbol !== symbol))
      await loadWatchlists()
    } catch (err) { console.error('Remove stock:', err) }
  }

  const updateNotes = async (itemId, notes) => {
    if (!selectedId) return
    try {
      await watchlistApi.updateItem(selectedId, itemId, notes)
      setItems(prev => prev.map(i => i.id === itemId ? { ...i, notes } : i))
    } catch (err) { console.error('Update notes:', err) }
  }

  // ── Sorting ──
  const toggleSort = (key) => {
    if (sortKey === key) setSortDir(d => d === 'asc' ? 'desc' : 'asc')
    else { setSortKey(key); setSortDir('asc') }
  }

  const sortedItems = [...items].sort((a, b) => {
    if (!sortKey) return 0
    const dir = sortDir === 'asc' ? 1 : -1
    if (sortKey === 'symbol') return a.symbol.localeCompare(b.symbol) * dir
    if (sortKey === 'change') {
      const qa = quotes[`NSE:${a.symbol}`]
      const qb = quotes[`NSE:${b.symbol}`]
      const ca = qa ? ((qa.last_price - (qa.ohlc?.close || qa.last_price)) / (qa.ohlc?.close || 1)) * 100 : 0
      const cb = qb ? ((qb.last_price - (qb.ohlc?.close || qb.last_price)) / (qb.ohlc?.close || 1)) * 100 : 0
      return (ca - cb) * dir
    }
    if (sortKey === 'pe') {
      const pa = fundamentals[a.symbol]?.pe_ratio ?? 999
      const pb = fundamentals[b.symbol]?.pe_ratio ?? 999
      return (pa - pb) * dir
    }
    return 0
  })

  const selectedWl = watchlists.find(w => w.id === selectedId)

  // ── Render ──
  return (
    <div className="wl-page">
      <div className="page-header" style={{ marginBottom: 20 }}>
        <h1 className="page-title" style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
          <List size={24} color="#3b82f6" /> Watchlists
        </h1>
        <p className="page-sub">Track and research your favourite stocks</p>
      </div>

      <div className="wl-layout">
        {/* ── Left: Watchlist Selector ── */}
        <div className="wl-sidebar">
          <div className="wl-sidebar-header">
            <span className="wl-sidebar-title">My Watchlists</span>
            <button className="wl-icon-btn" onClick={() => setCreating(true)} title="New watchlist">
              <Plus size={16} />
            </button>
          </div>

          {creating && (
            <div className="wl-create-row">
              <input
                autoFocus
                value={newName}
                onChange={e => setNewName(e.target.value)}
                onKeyDown={e => { if (e.key === 'Enter') createWatchlist(); if (e.key === 'Escape') setCreating(false) }}
                placeholder="Watchlist name..."
                className="wl-create-input"
              />
              <button className="wl-icon-btn success" onClick={createWatchlist}><Check size={14} /></button>
              <button className="wl-icon-btn" onClick={() => setCreating(false)}><X size={14} /></button>
            </div>
          )}

          {loading ? (
            <div className="wl-sidebar-empty"><span className="spinner" style={{ width: 18, height: 18, borderWidth: 2 }} /></div>
          ) : watchlists.length === 0 ? (
            <div className="wl-sidebar-empty">
              <p>No watchlists yet.</p>
              <button className="btn btn-accent btn-sm" onClick={() => setCreating(true)}>
                <Plus size={14} /> Create one
              </button>
            </div>
          ) : (
            <div className="wl-list">
              {watchlists.map(wl => (
                <div
                  key={wl.id}
                  className={`wl-list-item${selectedId === wl.id ? ' active' : ''}`}
                  onClick={() => setSelectedId(wl.id)}
                >
                  {renamingId === wl.id ? (
                    <input
                      autoFocus
                      value={renameText}
                      onChange={e => setRenameText(e.target.value)}
                      onKeyDown={e => { if (e.key === 'Enter') renameWatchlist(wl.id); if (e.key === 'Escape') setRenamingId(null) }}
                      onBlur={() => renameWatchlist(wl.id)}
                      className="wl-rename-input"
                      onClick={e => e.stopPropagation()}
                    />
                  ) : (
                    <>
                      <div className="wl-list-name">
                        {wl.is_default && <Star size={12} className="wl-default-star" />}
                        {wl.name}
                      </div>
                      <span className="wl-list-count">{wl.item_count}</span>
                      <div className="wl-list-actions" onClick={e => e.stopPropagation()}>
                        {!wl.is_default && (
                          <button className="wl-icon-btn tiny" onClick={() => setDefault(wl.id)} title="Set as default">
                            <Star size={11} />
                          </button>
                        )}
                        <button className="wl-icon-btn tiny" onClick={() => { setRenamingId(wl.id); setRenameText(wl.name) }} title="Rename">
                          <Edit3 size={11} />
                        </button>
                        <button className="wl-icon-btn tiny danger" onClick={() => deleteWatchlist(wl.id)} title="Delete">
                          <Trash2 size={11} />
                        </button>
                      </div>
                    </>
                  )}
                </div>
              ))}
            </div>
          )}
        </div>

        {/* ── Right: Stock Table ── */}
        <div className="wl-main">
          {!selectedId ? (
            <div className="wl-empty-main">
              <List size={48} strokeWidth={1} />
              <p>Select or create a watchlist to get started.</p>
            </div>
          ) : (
            <>
              {/* Search bar */}
              <div className="wl-search-wrap">
                <div className="wl-search-box">
                  <Search size={16} />
                  <input
                    value={searchQuery}
                    onChange={e => { setSearchQuery(e.target.value); setSearchOpen(true) }}
                    onFocus={() => setSearchOpen(true)}
                    placeholder="Search & add stocks..."
                  />
                  {searchQuery && (
                    <button className="wl-icon-btn" onClick={() => { setSearchQuery(''); setSearchOpen(false) }}>
                      <X size={14} />
                    </button>
                  )}
                </div>
                {searchOpen && searchResults.length > 0 && (
                  <div className="wl-search-dropdown">
                    {searchResults.slice(0, 10).map((r, i) => {
                      const alreadyAdded = items.some(it => it.symbol === r.symbol)
                      return (
                        <div
                          key={i}
                          className={`wl-search-item${alreadyAdded ? ' disabled' : ''}`}
                          onClick={() => !alreadyAdded && addStock(r.symbol)}
                        >
                          <span className="wl-search-sym">{r.symbol}</span>
                          <span className="wl-search-name">{r.name}</span>
                          {alreadyAdded ? (
                            <span className="wl-search-added"><Check size={12} /> Added</span>
                          ) : (
                            <Plus size={14} className="wl-search-add" />
                          )}
                        </div>
                      )
                    })}
                  </div>
                )}
              </div>

              {/* Sort controls */}
              {items.length > 0 && (
                <div className="wl-sort-bar">
                  <span className="wl-sort-label"><ArrowUpDown size={12} /> Sort:</span>
                  {[['symbol', 'Name'], ['change', 'Change %'], ['pe', 'P/E']].map(([key, label]) => (
                    <button
                      key={key}
                      className={`wl-sort-btn${sortKey === key ? ' active' : ''}`}
                      onClick={() => toggleSort(key)}
                    >
                      {label} {sortKey === key && (sortDir === 'asc' ? '↑' : '↓')}
                    </button>
                  ))}
                </div>
              )}

              {/* Stock table */}
              {items.length === 0 ? (
                <div className="wl-empty-main" style={{ minHeight: 200 }}>
                  <Search size={36} strokeWidth={1} />
                  <p>This watchlist is empty.<br />Search and add stocks above.</p>
                </div>
              ) : (
                <div className="wl-table-wrap">
                  <table className="wl-table">
                    <thead>
                      <tr>
                        <th>Stock</th>
                        <th>7D Trend</th>
                        <th>LTP</th>
                        <th>Day Chg</th>
                        <th>52W Range</th>
                        <th>P/E</th>
                        <th>MCap</th>
                        <th>Notes</th>
                        <th></th>
                      </tr>
                    </thead>
                    <tbody>
                      {sortedItems.map(item => {
                        const q = quotes[`NSE:${item.symbol}`]
                        const fund = fundamentals[item.symbol]
                        const ltp = q?.last_price
                        const prevClose = q?.ohlc?.close
                        const change = ltp && prevClose ? ltp - prevClose : null
                        const changePct = change != null && prevClose ? (change / prevClose) * 100 : null
                        const up = change != null ? change >= 0 : null
                        const sparkColor = up === null ? '#64748b' : up ? '#22c55e' : '#ef4444'

                        return (
                          <tr key={item.symbol}>
                            <td>
                              <div className="wl-stock-cell">
                                <span
                                  className="wl-stock-sym wl-stock-link"
                                  onClick={() => navigate(`/market?symbol=${item.symbol}`)}
                                  title="View in Market"
                                >{item.symbol}</span>
                              </div>
                            </td>
                            <td>
                              <Sparkline data={sparklines[item.symbol]} color={sparkColor} />
                            </td>
                            <td className="font-mono">{ltp ? fmtCcy(ltp) : '—'}</td>
                            <td>
                              {changePct != null ? (
                                <span className={up ? 'text-success' : 'text-danger'}>
                                  {up ? '+' : ''}{changePct.toFixed(2)}%
                                </span>
                              ) : '—'}
                            </td>
                            <td>
                              <RangeBar
                                low={fund?.low_52w}
                                high={fund?.high_52w}
                                current={ltp}
                              />
                            </td>
                            <td className="font-mono">{fund?.pe_ratio ? fmt(fund.pe_ratio) : '—'}</td>
                            <td className="font-mono">{fmtMcap(fund?.market_cap)}</td>
                            <td>
                              <NotesCell
                                notes={item.notes}
                                onSave={(text) => updateNotes(item.id, text)}
                              />
                            </td>
                            <td>
                              <button
                                className="wl-icon-btn tiny danger"
                                onClick={() => removeStock(item.symbol)}
                                title="Remove"
                              >
                                <X size={14} />
                              </button>
                            </td>
                          </tr>
                        )
                      })}
                    </tbody>
                  </table>
                </div>
              )}
            </>
          )}
        </div>
      </div>
    </div>
  )
}
