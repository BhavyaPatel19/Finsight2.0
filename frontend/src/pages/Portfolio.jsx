import { useEffect, useState } from 'react'
import { portfolioApi } from '../api/client'
import { BarChart2, RefreshCw } from 'lucide-react'
import {
  PieChart, Pie, Cell, Tooltip, Legend, ResponsiveContainer
} from 'recharts'

const COLORS = ['#6366f1','#22d3a5','#f59e0b','#f43f5e','#38bdf8','#c084fc','#fb7185','#34d399']

const fmt = (n) => n == null ? '—' : new Intl.NumberFormat('en-IN', { maximumFractionDigits: 2 }).format(n)
const fmtCcy = (n) => n == null ? '—' : '₹' + new Intl.NumberFormat('en-IN', { maximumFractionDigits: 0 }).format(n)

export default function Portfolio() {
  const [holdings, setHoldings] = useState([])
  const [insights, setInsights] = useState(null)
  const [loading, setLoading] = useState(true)

  const load = async () => {
    setLoading(true)
    try {
      const [h, i] = await Promise.all([portfolioApi.holdings(), portfolioApi.insights()])
      setHoldings(h.data.holdings ?? [])
      setInsights(i.data)
    } catch { setHoldings([]); setInsights(null) }
    finally { setLoading(false) }
  }

  useEffect(() => { load() }, [])

  const pieData = holdings.map(h => ({
    name: h.symbol,
    value: Math.round((h.current_price ?? h.avg_price) * h.quantity),
  }))

  const totalValue = holdings.reduce((s, h) => s + (h.current_price ?? h.avg_price) * h.quantity, 0)

  return (
    <div>
      <div className="flex-between mb-6">
        <div className="page-header" style={{ marginBottom: 0 }}>
          <h1 className="page-title" style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
            <BarChart2 size={24} color="#f59e0b" /> Portfolio Details
          </h1>
          <p className="page-sub">Holdings with financial metrics and allocation breakdown</p>
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
          <p>No holdings found.<br />Sync Zerodha via <code style={{ background:'rgba(255,255,255,0.07)', padding: '2px 6px', borderRadius: 4 }}>POST /zerodha/sync</code></p>
        </div>
      ) : (
        <>
          {/* Summary strip */}
          <div className="card-grid" style={{ marginBottom: 24 }}>
            <div className="stat-card">
              <div className="stat-label">Total Value</div>
              <div className="stat-value" style={{ fontSize: 22 }}>{fmtCcy(totalValue)}</div>
            </div>
            <div className="stat-card">
              <div className="stat-label">Portfolio Credibility</div>
              <div className="stat-value">
                {insights?.portfolio_credibility_score != null ? insights.portfolio_credibility_score.toFixed(1) + '/100' : '—'}
              </div>
            </div>
            <div className="stat-card">
              <div className="stat-label">Low Cred Exposure</div>
              <div className="stat-value" style={{ color: insights?.low_credibility_exposure_pct > 20 ? 'var(--danger)' : 'var(--success)' }}>
                {insights?.low_credibility_exposure_pct != null ? insights.low_credibility_exposure_pct.toFixed(1) + '%' : '—'}
              </div>
            </div>
          </div>

          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1.5fr', gap: 20, marginBottom: 24 }}>
            {/* Pie chart */}
            <div className="card">
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
            </div>

            {/* Holdings with metrics table */}
            <div className="card">
              <h3 style={{ fontSize: 15, fontWeight: 600, marginBottom: 14 }}>Holdings + Metrics</h3>
              <div className="table-wrap" style={{ borderRadius: 8 }}>
                <table>
                  <thead>
                    <tr><th>Symbol</th><th>Value</th><th>P/E</th><th>ROCE</th><th>Rev Growth</th></tr>
                  </thead>
                  <tbody>
                    {holdings.map(h => {
                      const val = (h.current_price ?? h.avg_price) * h.quantity
                      return (
                        <tr key={h.symbol}>
                          <td><span className="badge badge-accent">{h.symbol}</span></td>
                          <td className="font-bold">{fmtCcy(val)}</td>
                          <td>{h.pe != null ? fmt(h.pe) : <span className="text-muted">—</span>}</td>
                          <td>{h.roce != null ? fmt(h.roce) + '%' : <span className="text-muted">—</span>}</td>
                          <td style={{ color: h.revenue_growth > 0 ? 'var(--success)' : h.revenue_growth < 0 ? 'var(--danger)' : undefined }}>
                            {h.revenue_growth != null ? (h.revenue_growth > 0 ? '+' : '') + fmt(h.revenue_growth) + '%' : <span className="text-muted">—</span>}
                          </td>
                        </tr>
                      )
                    })}
                  </tbody>
                </table>
              </div>
            </div>
          </div>
        </>
      )}
    </div>
  )
}
