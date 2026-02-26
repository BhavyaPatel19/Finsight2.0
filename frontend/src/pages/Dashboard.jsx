import { useEffect, useState } from 'react'
import { portfolioApi, zerodhaApi } from '../api/client'
import {
  DollarSign, TrendingUp, ShieldCheck, BarChart2, RefreshCw,
  Link2, Download
} from 'lucide-react'
import {
  AreaChart, Area, XAxis, YAxis, Tooltip,
  ResponsiveContainer, CartesianGrid
} from 'recharts'

const fmt = (n) =>
  n == null ? '—' : new Intl.NumberFormat('en-IN', { maximumFractionDigits: 2 }).format(n)

const fmtCcy = (n) =>
  n == null ? '—' : '₹' + new Intl.NumberFormat('en-IN', { maximumFractionDigits: 0 }).format(n)

function ScoreGauge({ score, label, color }) {
  const pct = score ?? 0
  const stroke = color ?? '#6366f1'
  const r = 40, cx = 50, cy = 50
  const circ = 2 * Math.PI * r
  const dash = (pct / 100) * circ

  return (
    <div className="score-ring-wrap">
      <svg width={100} height={100} viewBox="0 0 100 100">
        <circle cx={cx} cy={cy} r={r} fill="none" stroke="rgba(255,255,255,0.06)" strokeWidth={10} />
        <circle
          cx={cx} cy={cy} r={r} fill="none"
          stroke={stroke} strokeWidth={10}
          strokeDasharray={`${dash} ${circ}`}
          strokeLinecap="round"
          transform={`rotate(-90 ${cx} ${cy})`}
          style={{ transition: 'stroke-dasharray 0.8s ease' }}
        />
        <text x={cx} y={cy + 6} textAnchor="middle" fill="#f1f5f9"
          fontSize={16} fontWeight={700} fontFamily="Inter">
          {score != null ? Math.round(score) : '—'}
        </text>
      </svg>
      <span className="score-ring-label">{label}</span>
    </div>
  )
}

export default function Dashboard() {
  const [holdings, setHoldings] = useState([])
  const [insights, setInsights] = useState(null)
  const [loading, setLoading] = useState(true)
  const [syncing, setSyncing] = useState(false)
  const [syncMsg, setSyncMsg] = useState('')
  const [connecting, setConnecting] = useState(false)
  const [requestToken, setRequestToken] = useState('')
  const [linking, setLinking] = useState(false)

  const load = async () => {
    setLoading(true)
    try {
      const [h, i] = await Promise.all([portfolioApi.holdings(), portfolioApi.insights()])
      setHoldings(h.data.holdings ?? [])
      setInsights(i.data)
    } catch {
      setHoldings([]); setInsights(null)
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

  const chartData = holdings.map(h => ({
    name: h.symbol,
    value: Math.round((h.current_price ?? h.avg_price) * h.quantity),
  }))

  return (
    <div>
      <div className="flex-between mb-6">
        <div className="page-header" style={{ marginBottom: 0 }}>
          <h1 className="page-title">Dashboard</h1>
          <p className="page-sub">Your portfolio overview, credibility & sentiment at a glance</p>
        </div>
        <div className="flex gap-2">
          <button className="btn btn-ghost btn-sm flex-center gap-2" onClick={load}>
            <RefreshCw size={14} /> Refresh
          </button>
        </div>
      </div>

      {/* ── Zerodha Connect/Sync Bar ── */}
      <div className="card mb-6" style={{ display: 'flex', gap: 14, flexWrap: 'wrap', alignItems: 'center', padding: '16px 22px' }}>
        <div style={{ flex: 1, minWidth: 180 }}>
          <div style={{ fontSize: 14, fontWeight: 600, color: 'var(--text-primary)', marginBottom: 2 }}>🔗 Zerodha Integration</div>
          <div className="text-xs text-muted">Connect → Paste token → Link → Sync</div>
        </div>
        <button id="zerodha-connect-btn" className="btn btn-primary btn-sm flex-center gap-2" onClick={connectZerodha} disabled={connecting}>
          {connecting ? <span className="spinner" /> : <Link2 size={14} />}
          {connecting ? 'Opening…' : '1. Connect'}
        </button>
        <input
          id="zerodha-token-input"
          className="form-control"
          style={{ maxWidth: 220, marginBottom: 0, fontSize: 12 }}
          placeholder="Paste request_token here"
          value={requestToken}
          onChange={e => setRequestToken(e.target.value)}
        />
        <button id="zerodha-link-btn" className="btn btn-ghost btn-sm flex-center gap-2" onClick={linkZerodha} disabled={linking || !requestToken.trim()}>
          {linking ? <span className="spinner" /> : <Link2 size={14} />}
          {linking ? 'Linking…' : '2. Link'}
        </button>
        <button id="zerodha-sync-btn" className="btn btn-ghost btn-sm flex-center gap-2" onClick={syncHoldings} disabled={syncing}>
          {syncing ? <span className="spinner" /> : <Download size={14} />}
          {syncing ? 'Syncing…' : '3. Sync'}
        </button>
        {syncMsg && (
          <span className="text-sm" style={{ width: '100%', color: syncMsg.startsWith('✅') ? 'var(--success)' : 'var(--danger)' }}>
            {syncMsg}
          </span>
        )}
      </div>

      {loading ? (
        <div className="empty-state"><span className="spinner" style={{ width: 36, height: 36, borderWidth: 3 }} /></div>
      ) : (
        <>
          {/* ── Stat cards ── */}
          <div className="card-grid">
            <div className="stat-card">
              <div className="stat-icon" style={{ background: 'rgba(99,102,241,0.15)' }}>
                <DollarSign size={20} color="#6366f1" />
              </div>
              <div className="stat-label">Portfolio Value</div>
              <div className="stat-value" style={{ fontSize: 22 }}>{fmtCcy(totalValue)}</div>
              <div className={`stat-sub ${pnl >= 0 ? 'text-success' : 'text-danger'}`}>
                {pnl >= 0 ? '▲' : '▼'} {fmtCcy(Math.abs(pnl))} ({pnlPct.toFixed(2)}%)
              </div>
            </div>

            <div className="stat-card">
              <div className="stat-icon" style={{ background: 'rgba(34,211,165,0.12)' }}>
                <BarChart2 size={20} color="#22d3a5" />
              </div>
              <div className="stat-label">Holdings</div>
              <div className="stat-value">{holdings.length}</div>
              <div className="stat-sub text-muted">Tracked stocks</div>
            </div>

            <div className="stat-card">
              <div className="stat-icon" style={{ background: 'rgba(99,102,241,0.15)' }}>
                <ShieldCheck size={20} color="#818cf8" />
              </div>
              <div className="stat-label">Portfolio Credibility</div>
              <div className="stat-value">
                {insights?.portfolio_credibility_score != null
                  ? Math.round(insights.portfolio_credibility_score) + '/100'
                  : '—'}
              </div>
              <div className="stat-sub text-muted">Weighted avg score</div>
            </div>

            <div className="stat-card">
              <div className="stat-icon" style={{ background: 'rgba(244,63,94,0.12)' }}>
                <TrendingUp size={20} color="#f43f5e" />
              </div>
              <div className="stat-label">Low Credibility Exposure</div>
              <div className="stat-value" style={{ color: insights?.low_credibility_exposure_pct > 20 ? '#f43f5e' : '#22d3a5' }}>
                {insights?.low_credibility_exposure_pct != null
                  ? insights.low_credibility_exposure_pct.toFixed(1) + '%'
                  : '—'}
              </div>
              <div className="stat-sub text-muted">Of portfolio value</div>
            </div>
          </div>

          {/* ── Score gauges ── */}
          <div className="card mb-6" style={{ display: 'flex', gap: 40, flexWrap: 'wrap', alignItems: 'center', justifyContent: 'center' }}>
            <ScoreGauge score={insights?.portfolio_credibility_score} label="Credibility" color="#6366f1" />
            <div style={{ width: 1, height: 80, background: 'rgba(255,255,255,0.06)' }} />
            <ScoreGauge
              score={insights?.low_credibility_exposure_pct != null
                ? 100 - insights.low_credibility_exposure_pct : null}
              label="Portfolio Health"
              color="#22d3a5"
            />
            <div style={{ width: 1, height: 80, background: 'rgba(255,255,255,0.06)' }} />
            <ScoreGauge
              score={pnlPct > 0 ? Math.min(100, 50 + pnlPct * 2) : Math.max(0, 50 + pnlPct * 2)}
              label="P&L Score"
              color="#f59e0b"
            />
          </div>

          {/* ── Holdings chart ── */}
          {chartData.length > 0 && (
            <div className="card mb-6">
              <h3 style={{ fontSize: 15, fontWeight: 600, marginBottom: 16, color: 'var(--text-primary)' }}>
                Holdings Value Distribution
              </h3>
              <ResponsiveContainer width="100%" height={220}>
                <AreaChart data={chartData}>
                  <defs>
                    <linearGradient id="gradV" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="5%" stopColor="#6366f1" stopOpacity={0.3} />
                      <stop offset="95%" stopColor="#6366f1" stopOpacity={0} />
                    </linearGradient>
                  </defs>
                  <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.05)" />
                  <XAxis dataKey="name" tick={{ fill: '#94a3b8', fontSize: 12 }} axisLine={false} tickLine={false} />
                  <YAxis tick={{ fill: '#94a3b8', fontSize: 12 }} axisLine={false} tickLine={false}
                    tickFormatter={v => '₹' + (v >= 1000 ? (v/1000).toFixed(0)+'k' : v)} />
                  <Tooltip
                    contentStyle={{ background: '#0e1421', border: '1px solid rgba(255,255,255,0.1)', borderRadius: 10, fontSize: 13 }}
                    formatter={val => [fmtCcy(val), 'Value']}
                  />
                  <Area type="monotone" dataKey="value" stroke="#6366f1" strokeWidth={2} fill="url(#gradV)" />
                </AreaChart>
              </ResponsiveContainer>
            </div>
          )}

          {/* ── Holdings table ── */}
          <div className="card">
            <h3 style={{ fontSize: 15, fontWeight: 600, marginBottom: 16 }}>Holdings</h3>
            {holdings.length === 0 ? (
              <div className="empty-state">
                <BarChart2 size={40} />
                <p>No holdings yet.<br />Sync your Zerodha account or add holdings manually.</p>
              </div>
            ) : (
              <div className="table-wrap">
                <table>
                  <thead>
                    <tr>
                      <th>Symbol</th><th>Qty</th><th>Avg Price</th>
                      <th>Current</th><th>Value</th><th>P&L</th>
                    </tr>
                  </thead>
                  <tbody>
                    {holdings.map(h => {
                      const cur = h.current_price ?? h.avg_price
                      const val = cur * h.quantity
                      const pl = (cur - h.avg_price) * h.quantity
                      const plPct = ((cur - h.avg_price) / h.avg_price) * 100
                      return (
                        <tr key={h.symbol}>
                          <td><span className="badge badge-accent">{h.symbol}</span></td>
                          <td>{h.quantity}</td>
                          <td>{fmtCcy(h.avg_price)}</td>
                          <td>{fmtCcy(cur)}</td>
                          <td className="font-bold">{fmtCcy(val)}</td>
                          <td className={pl >= 0 ? 'text-success' : 'text-danger'}>
                            {pl >= 0 ? '+' : ''}{fmtCcy(pl)} ({plPct.toFixed(1)}%)
                          </td>
                        </tr>
                      )
                    })}
                  </tbody>
                </table>
              </div>
            )}
          </div>
        </>
      )}
    </div>
  )
}
