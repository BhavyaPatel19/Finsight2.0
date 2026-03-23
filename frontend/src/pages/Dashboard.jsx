import { useEffect, useState } from 'react'
import { useTheme } from '../context/ThemeContext'
import { getChartColors } from '../utils/chartTheme'
import { portfolioApi, zerodhaApi } from '../api/client'
import {
  DollarSign, TrendingUp, TrendingDown, BarChart2, RefreshCw,
  Link2, Download, Briefcase
} from 'lucide-react'
import GlowCard from '../components/GlowCard'
import {
  AreaChart, Area, XAxis, YAxis, Tooltip,
  ResponsiveContainer, CartesianGrid, BarChart, Bar, Cell, LabelList
} from 'recharts'

const fmtCcy = (n) =>
  n == null ? '—' : '₹' + new Intl.NumberFormat('en-IN', { maximumFractionDigits: 0 }).format(n)

export default function Dashboard() {
  const { theme } = useTheme()
  const cc = getChartColors(theme)
  const [holdings, setHoldings] = useState([])
  const [loading, setLoading] = useState(true)
  const [syncing, setSyncing] = useState(false)
  const [syncMsg, setSyncMsg] = useState('')
  const [connecting, setConnecting] = useState(false)
  const [requestToken, setRequestToken] = useState('')
  const [linking, setLinking] = useState(false)

  const load = async () => {
    setLoading(true)
    try {
      const h = await portfolioApi.holdings()
      setHoldings(h.data.holdings ?? [])
    } catch {
      setHoldings([])
    } finally { setLoading(false) }
  }

  const connectZerodha = async () => {
    setConnecting(true); setSyncMsg('')
    try {
      const r = await zerodhaApi.connectUrl()
      const url = r.data.connect_url
      if (url) {
        window.open(url, '_blank')
        setSyncMsg('✅ Zerodha login opened. After login, come back and click "Sync Holdings".')
      } else {
        setSyncMsg('❌ Zerodha not configured')
      }
    } catch (err) {
      setSyncMsg(`❌ ${err.response?.data?.detail ?? 'Failed'}`)
    } finally { setConnecting(false) }
  }

  const syncHoldings = async () => {
    setSyncing(true); setSyncMsg('')
    try {
      const r = await zerodhaApi.sync()
      setSyncMsg(`✅ Synced ${r.data.synced} holdings from Zerodha`)
      load()
    } catch (err) {
      setSyncMsg(`❌ ${err.response?.data?.detail ?? 'Sync failed. Link Zerodha first.'}`)
    } finally { setSyncing(false) }
  }

  const linkZerodha = async () => {
    if (!requestToken.trim()) { setSyncMsg('Paste the request_token first.'); return }
    setLinking(true); setSyncMsg('')
    try {
      await zerodhaApi.link(requestToken.trim())
      setSyncMsg('✅ Zerodha linked! Now click "Sync Holdings".')
      setRequestToken('')
    } catch (err) {
      setSyncMsg(`❌ ${err.response?.data?.detail ?? 'Link failed. Token may have expired — try Connect again.'}`)
    } finally { setLinking(false) }
  }

  useEffect(() => { load() }, [])

  const totalValue = holdings.reduce(
    (s, h) => s + (h.current_price ?? h.avg_price) * h.quantity, 0
  )
  const totalCost = holdings.reduce((s, h) => s + h.avg_price * h.quantity, 0)
  const pnl = totalValue - totalCost
  const pnlPct = totalCost ? (pnl / totalCost) * 100 : 0

  // Top gainers & losers by day change %
  const sorted = [...holdings].filter(h => h.day_change_pct != null)
  const topGainers = [...sorted].sort((a, b) => (b.day_change_pct ?? 0) - (a.day_change_pct ?? 0)).slice(0, 5)
  const topLosers = [...sorted].sort((a, b) => (a.day_change_pct ?? 0) - (b.day_change_pct ?? 0)).slice(0, 5).filter(h => (h.day_change_pct ?? 0) < 0)

  // P&L bar chart data
  const pnlData = holdings
    .map(h => ({
      name: h.symbol,
      pnl: h.pnl ?? ((h.current_price ?? h.avg_price) - h.avg_price) * h.quantity,
    }))
    .sort((a, b) => b.pnl - a.pnl)

  // Value distribution
  const chartData = holdings.map(h => ({
    name: h.symbol,
    value: Math.round((h.current_price ?? h.avg_price) * h.quantity),
  }))

  return (
    <div>
      <div className="flex-between mb-6">
        <div className="page-header" style={{ marginBottom: 0 }}>
          <h1 className="page-title">Dashboard</h1>
          <p className="page-sub">Quick overview of your portfolio performance</p>
        </div>
        <div className="flex gap-2">
          <button className="btn btn-ghost btn-sm flex-center gap-2" onClick={load}>
            <RefreshCw size={14} /> Refresh
          </button>
        </div>
      </div>

      {/* ── Zerodha Connect/Sync Bar ── */}
      <GlowCard className="card mb-6" style={{ display: 'flex', gap: 14, flexWrap: 'wrap', alignItems: 'center', padding: '16px 22px' }}>
        <div style={{ flex: 1, minWidth: 180 }}>
          <div style={{ fontSize: 14, fontWeight: 600, color: 'var(--text-primary)', marginBottom: 2 }}>🔗 Zerodha Integration</div>
          <div className="text-xs text-muted">Connect → Sync</div>
        </div>
        <button id="zerodha-connect-btn" className="btn btn-primary btn-sm flex-center gap-2" onClick={connectZerodha} disabled={connecting}>
          {connecting ? <span className="spinner" /> : <Link2 size={14} />}
          {connecting ? 'Opening…' : 'Connect'}
        </button>
        <button id="zerodha-sync-btn" className="btn btn-ghost btn-sm flex-center gap-2" onClick={syncHoldings} disabled={syncing}>
          {syncing ? <span className="spinner" /> : <Download size={14} />}
          {syncing ? 'Syncing…' : 'Sync'}
        </button>
        {syncMsg && (
          <span className="text-sm" style={{ width: '100%', color: syncMsg.startsWith('✅') ? 'var(--success)' : 'var(--danger)' }}>
            {syncMsg}
          </span>
        )}
      </GlowCard>

      {loading ? (
        <div className="empty-state"><span className="spinner" style={{ width: 36, height: 36, borderWidth: 3 }} /></div>
      ) : (
        <>
          {/* ── Summary Cards ── */}
          <div className="card-grid">
            <GlowCard className="stat-card">
              <div className="stat-icon" style={{ background: 'rgba(99,102,241,0.15)' }}>
                <Briefcase size={20} color="#6366f1" />
              </div>
              <div className="stat-label">Portfolio Value</div>
              <div className="stat-value" style={{ fontSize: 22 }}>{fmtCcy(totalValue)}</div>
              <div className={`stat-sub ${pnl >= 0 ? 'text-success' : 'text-danger'}`} style={{ textShadow: pnl >= 0 ? '0 0 6px rgba(34,211,165,0.5)' : '0 0 6px rgba(244,63,94,0.5)' }}>
                {pnl >= 0 ? '▲' : '▼'} {fmtCcy(Math.abs(pnl))} ({pnlPct.toFixed(2)}%)
              </div>
            </GlowCard>

            <GlowCard className="stat-card">
              <div className="stat-icon" style={{ background: 'rgba(34,211,165,0.12)' }}>
                <BarChart2 size={20} color="#22d3a5" />
              </div>
              <div className="stat-label">Holdings</div>
              <div className="stat-value">{holdings.length}</div>
              <div className="stat-sub text-muted">Tracked stocks</div>
            </GlowCard>

            <GlowCard className="stat-card">
              <div className="stat-icon" style={{ background: 'rgba(245,158,11,0.12)' }}>
                <DollarSign size={20} color="#f59e0b" />
              </div>
              <div className="stat-label">Total Invested</div>
              <div className="stat-value">{fmtCcy(totalCost)}</div>
              <div className="stat-sub text-muted">Cost basis</div>
            </GlowCard>

            <GlowCard className="stat-card">
              <div className="stat-icon" style={{ background: pnl >= 0 ? 'rgba(34,211,165,0.12)' : 'rgba(244,63,94,0.12)' }}>
                {pnl >= 0 ? <TrendingUp size={20} color="#22d3a5" /> : <TrendingDown size={20} color="#f43f5e" />}
              </div>
              <div className="stat-label">Overall P&L</div>
              <div className="stat-value" style={{ color: pnl >= 0 ? '#22d3a5' : '#f43f5e', textShadow: pnl >= 0 ? '0 0 8px rgba(34,211,165,0.6), 0 0 20px rgba(34,211,165,0.3)' : '0 0 8px rgba(244,63,94,0.6), 0 0 20px rgba(244,63,94,0.3)' }}>
                {pnl >= 0 ? '+' : ''}{fmtCcy(pnl)}
              </div>
              <div className="stat-sub text-muted">{pnlPct.toFixed(2)}% return</div>
            </GlowCard>
          </div>

          {/* ── Top Gainers & Losers ── */}
          {sorted.length > 0 && (
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 20, marginBottom: 20 }}>
              <GlowCard className="card">
                <h3 style={{ fontSize: 15, fontWeight: 600, marginBottom: 14, display: 'flex', alignItems: 'center', gap: 8 }}>
                  <TrendingUp size={16} color="#22d3a5" /> Today's Gainers
                </h3>
                {topGainers.length === 0 ? (
                  <p className="text-muted text-sm">No gainers today</p>
                ) : (
                  <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
                    {topGainers.map(h => (
                      <div key={h.symbol} style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '8px 12px', borderRadius: 8, background: 'rgba(34,211,165,0.06)' }}>
                        <span className="badge badge-accent">{h.symbol}</span>
                        <span style={{ color: '#22d3a5', fontWeight: 600, fontSize: 14, textShadow: '0 0 8px rgba(34,211,165,0.6), 0 0 20px rgba(34,211,165,0.3)' }}>
                          +{h.day_change_pct?.toFixed(2)}%
                        </span>
                      </div>
                    ))}
                  </div>
                )}
              </GlowCard>

              <GlowCard className="card">
                <h3 style={{ fontSize: 15, fontWeight: 600, marginBottom: 14, display: 'flex', alignItems: 'center', gap: 8 }}>
                  <TrendingDown size={16} color="#f43f5e" /> Today's Losers
                </h3>
                {topLosers.length === 0 ? (
                  <p className="text-muted text-sm">No losers today 🎉</p>
                ) : (
                  <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
                    {topLosers.map(h => (
                      <div key={h.symbol} style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '8px 12px', borderRadius: 8, background: 'rgba(244,63,94,0.06)' }}>
                        <span className="badge badge-danger">{h.symbol}</span>
                        <span style={{ color: '#f43f5e', fontWeight: 600, fontSize: 14, textShadow: '0 0 8px rgba(244,63,94,0.6), 0 0 20px rgba(244,63,94,0.3)' }}>
                          {h.day_change_pct?.toFixed(2)}%
                        </span>
                      </div>
                    ))}
                  </div>
                )}
              </GlowCard>
            </div>
          )}

          {/* ── P&L by Stock (bar chart) ── */}
          {pnlData.length > 0 && (
            <GlowCard className="card mb-6">
              <h3 style={{ fontSize: 15, fontWeight: 600, marginBottom: 16, color: 'var(--text-primary)' }}>
                P&L by Stock
              </h3>
              <ResponsiveContainer width="100%" height={220}>
                <BarChart data={pnlData} layout="vertical">
                  <CartesianGrid strokeDasharray="3 3" stroke={cc.grid} />
                  <XAxis type="number" tick={{ fill: cc.tick, fontSize: 12 }} axisLine={false} tickLine={false}
                    tickFormatter={v => '₹' + (Math.abs(v) >= 1000 ? (v/1000).toFixed(1)+'k' : v)} />
                  <YAxis type="category" dataKey="name" tick={{ fill: cc.tick, fontSize: 11 }} axisLine={false} tickLine={false} width={70} />
                  <Tooltip
                    contentStyle={cc.tooltip}
                    labelStyle={{ color: cc.labelPrimary, fontWeight: 600 }}
                    itemStyle={{ color: cc.labelPrimary }}
                    formatter={(val) => [<span style={{ color: val >= 0 ? '#22d3a5' : '#f43f5e', fontWeight: 600 }}>{fmtCcy(val)}</span>, 'P&L']}
                  />
                  <Bar dataKey="pnl" radius={[0, 4, 4, 0]}>
                    {pnlData.map((entry, i) => (
                      <Cell key={i} fill={entry.pnl >= 0 ? '#22d3a5' : '#f43f5e'} />
                    ))}
                  </Bar>
                </BarChart>
              </ResponsiveContainer>
            </GlowCard>
          )}

          {/* ── Value Distribution ── */}
          {chartData.length > 0 && (
            <GlowCard className="card mb-6">
              <h3 style={{ fontSize: 15, fontWeight: 600, marginBottom: 16, color: 'var(--text-primary)' }}>
                Holdings Value Distribution
              </h3>
              <ResponsiveContainer width="100%" height={Math.max(280, chartData.length * 32)}>
                <BarChart data={[...chartData].sort((a, b) => b.value - a.value)} layout="vertical" margin={{ left: 10, right: 30, top: 5, bottom: 5 }}>
                  <defs>
                    <linearGradient id="gradBar" x1="0" y1="0" x2="1" y2="0">
                      <stop offset="0%" stopColor="#6366f1" stopOpacity={0.8} />
                      <stop offset="100%" stopColor="#818cf8" stopOpacity={1} />
                    </linearGradient>
                  </defs>
                  <CartesianGrid strokeDasharray="3 3" stroke={cc.grid} horizontal={false} />
                  <XAxis type="number" tick={{ fill: cc.tick, fontSize: 11 }} axisLine={false} tickLine={false}
                    tickFormatter={v => '₹' + (v >= 1000 ? (v/1000).toFixed(0)+'k' : v)} />
                  <YAxis type="category" dataKey="name" tick={{ fill: cc.labelMuted, fontSize: 12, fontWeight: 500 }} axisLine={false} tickLine={false} width={90} />
                  <Tooltip
                    cursor={{ fill: 'rgba(99,102,241,0.08)' }}
                    contentStyle={cc.tooltip}
                    formatter={val => [fmtCcy(val), 'Value']}
                  />
                  <Bar dataKey="value" fill="url(#gradBar)" radius={[0, 6, 6, 0]} barSize={20}>
                    {[...chartData].sort((a, b) => b.value - a.value).map((entry, i) => (
                      <Cell key={i} fill={`hsl(${235 + i * 8}, 70%, ${60 + (i % 3) * 5}%)`} />
                    ))}
                    <LabelList dataKey="value" position="right" fill="#c8d0da" fontSize={11} fontWeight={500}
                      formatter={v => '₹' + (v >= 1000 ? (v/1000).toFixed(1)+'k' : v)} />
                  </Bar>
                </BarChart>
              </ResponsiveContainer>
            </GlowCard>
          )}
        </>
      )}
    </div>
  )
}
