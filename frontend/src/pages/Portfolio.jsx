import { useEffect, useState } from 'react'
import { portfolioApi } from '../api/client'
import { BarChart2, RefreshCw } from 'lucide-react'
import {
  PieChart, Pie, Cell, Tooltip, ResponsiveContainer
} from 'recharts'
import GlowCard from '../components/GlowCard'

const COLORS = ['#6366f1','#22d3a5','#f59e0b','#f43f5e','#38bdf8','#c084fc','#fb7185','#34d399']

const fmt = (n) => n == null ? '—' : new Intl.NumberFormat('en-IN', { maximumFractionDigits: 2 }).format(n)
const fmtCcy = (n) => n == null ? '—' : '₹' + new Intl.NumberFormat('en-IN', { maximumFractionDigits: 0 }).format(n)

export default function Portfolio() {
  const [holdings, setHoldings] = useState([])
  const [loading, setLoading] = useState(true)

  const load = async () => {
    setLoading(true)
    try {
      const h = await portfolioApi.holdings()
      setHoldings(h.data.holdings ?? [])
    } catch { setHoldings([]) }
    finally { setLoading(false) }
  }

  useEffect(() => { load() }, [])

  const pieData = holdings.map(h => ({
    name: h.symbol,
    value: Math.round((h.current_price ?? h.avg_price) * h.quantity),
  }))

  const totalValue = holdings.reduce((s, h) => s + (h.current_price ?? h.avg_price) * h.quantity, 0)
  const totalCost = holdings.reduce((s, h) => s + h.avg_price * h.quantity, 0)
  const pnl = totalValue - totalCost
  const pnlPct = totalCost ? (pnl / totalCost) * 100 : 0

  return (
    <div>
      <div className="flex-between mb-6">
        <div className="page-header" style={{ marginBottom: 0 }}>
          <h1 className="page-title" style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
            <BarChart2 size={24} color="#f59e0b" /> Portfolio Details
          </h1>
          <p className="page-sub">Holdings with market data and allocation breakdown</p>
        </div>
        <button className="btn btn-ghost btn-sm flex-center gap-2" onClick={load}>
          <RefreshCw size={14} /> Refresh
        </button>
      </div>

      {loading ? (
        <div className="empty-state"><span className="spinner" style={{ width: 36, height: 36, borderWidth: 3 }} /></div>
      ) : holdings.length === 0 ? (
        <div className="empty-state card">
          <BarChart2 size={48} />
          <p>No holdings found.<br />Sync Zerodha via the Dashboard.</p>
        </div>
      ) : (
        <>
          {/* Summary strip */}
          <div className="card-grid" style={{ marginBottom: 24 }}>
            <GlowCard className="stat-card">
              <div className="stat-label">Total Value</div>
              <div className="stat-value" style={{ fontSize: 22 }}>{fmtCcy(totalValue)}</div>
            </GlowCard>
            <GlowCard className="stat-card">
              <div className="stat-label">Total Invested</div>
              <div className="stat-value">{fmtCcy(totalCost)}</div>
            </GlowCard>
            <GlowCard className="stat-card">
              <div className="stat-label">Total P&L</div>
              <div className="stat-value" style={{ color: pnl >= 0 ? 'var(--success)' : 'var(--danger)' }}>
                {pnl >= 0 ? '+' : ''}{fmtCcy(pnl)} ({pnlPct.toFixed(1)}%)
              </div>
            </GlowCard>
          </div>

          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1.5fr', gap: 20, marginBottom: 24 }}>
            {/* Pie chart */}
            <GlowCard className="card">
              <h3 style={{ fontSize: 15, fontWeight: 600, marginBottom: 14 }}>Allocation</h3>
              <ResponsiveContainer width="100%" height={260}>
                <PieChart>
                  <Pie data={pieData} cx="50%" cy="50%" innerRadius={55} outerRadius={95}
                    dataKey="value" paddingAngle={3} label={({ name, percent }) => `${name} ${(percent*100).toFixed(0)}%`}
                    labelLine={false}
                  >
                    {pieData.map((_, i) => <Cell key={i} fill={COLORS[i % COLORS.length]} />)}
                  </Pie>
                  <Tooltip formatter={(v) => fmtCcy(v)}
                    contentStyle={{ background: '#0e1421', border: '1px solid rgba(255,255,255,0.1)', borderRadius: 10, fontSize: 13 }}
                  />
                </PieChart>
              </ResponsiveContainer>
            </GlowCard>

            {/* Holdings table */}
            <GlowCard className="card">
              <h3 style={{ fontSize: 15, fontWeight: 600, marginBottom: 14 }}>Holdings</h3>
              <div className="table-wrap" style={{ borderRadius: 8 }}>
                <table>
                  <thead>
                    <tr>
                      <th>Symbol</th>
                      <th>Qty</th>
                      <th>Avg Price</th>
                      <th>Invested</th>
                      <th>LTP</th>
                      <th>Day Chg</th>
                      <th>P&L</th>
                      <th>Value</th>
                    </tr>
                  </thead>
                  <tbody>
                    {holdings.map(h => {
                      const cur = h.current_price ?? h.avg_price
                      const val = cur * h.quantity
                      const pl = h.pnl ?? ((cur - h.avg_price) * h.quantity)
                      const plPct = h.avg_price ? ((cur - h.avg_price) / h.avg_price) * 100 : 0
                      return (
                        <tr key={h.symbol}>
                          <td>
                            <span className="badge badge-accent">{h.symbol}</span>
                            {h.exchange && <span className="text-xs text-muted" style={{ marginLeft: 4 }}>{h.exchange}</span>}
                          </td>
                          <td>{h.quantity}</td>
                          <td>{fmtCcy(h.avg_price)}</td>
                          <td>{fmtCcy(h.avg_price * h.quantity)}</td>
                          <td>{fmtCcy(cur)}</td>
                          <td className={h.day_change_pct >= 0 ? 'text-success' : 'text-danger'}>
                            {h.day_change_pct != null
                              ? `${h.day_change_pct >= 0 ? '+' : ''}${h.day_change_pct.toFixed(2)}%`
                              : '—'}
                          </td>
                          <td className={pl >= 0 ? 'text-success' : 'text-danger'}>
                            {pl >= 0 ? '+' : ''}{fmtCcy(pl)}
                            <span className="text-xs" style={{ marginLeft: 4 }}>({plPct.toFixed(1)}%)</span>
                          </td>
                          <td className="font-bold">{fmtCcy(val)}</td>
                        </tr>
                      )
                    })}
                  </tbody>
                </table>
              </div>
            </GlowCard>
          </div>
        </>
      )}
    </div>
  )
}
