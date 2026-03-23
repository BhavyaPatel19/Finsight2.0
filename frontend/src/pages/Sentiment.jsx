import { useState } from 'react'
import { useTheme } from '../context/ThemeContext'
import { getChartColors } from '../utils/chartTheme'
import { sentimentApi } from '../api/client'
import { TrendingUp, RefreshCw } from 'lucide-react'
import {
  BarChart, Bar, XAxis, YAxis, Tooltip,
  ResponsiveContainer, CartesianGrid, Cell
} from 'recharts'

const scoreColor = (s) => {
  if (s > 0.1) return '#22d3a5'
  if (s < -0.1) return '#f43f5e'
  return '#f59e0b'
}

const sentimentLabel = (s) => {
  if (s > 0.15) return { label: 'Positive', cls: 'badge-success' }
  if (s < -0.15) return { label: 'Negative', cls: 'badge-danger' }
  return { label: 'Neutral', cls: 'badge-warning' }
}

export default function Sentiment() {
  const { theme } = useTheme()
  const cc = getChartColors(theme)
  const [symbol, setSymbol] = useState('')
  const [records, setRecords] = useState([])
  const [loading, setLoading] = useState(false)
  const [searched, setSearched] = useState(false)

  const search = async () => {
    if (!symbol.trim()) return
    setLoading(true); setSearched(true)
    try {
      const r = await sentimentApi.history(symbol.toUpperCase())
      setRecords(Array.isArray(r.data) ? r.data : [])
    } catch { setRecords([]) }
    finally { setLoading(false) }
  }

  const chartData = records.map(r => ({
    label: [r.fiscal_quarter, r.fiscal_year].filter(Boolean).join(' ') || `#${r.id}`,
    overall: +(r.overall_score ?? 0).toFixed(4),
    optimism: +(r.optimism_index ?? 0).toFixed(4),
    risk: +(r.risk_tone_index ?? 0).toFixed(4),
  }))

  return (
    <div>
      <div className="page-header">
        <h1 className="page-title" style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
          <TrendingUp size={24} color="#22d3a5" /> Sentiment Analysis
        </h1>
        <p className="page-sub">FinBERT-powered sentiment scores from financial documents</p>
      </div>

      {/* Search bar */}
      <div className="card mb-6" style={{ display: 'flex', gap: 12, alignItems: 'center', padding: '16px 20px' }}>
        <input
          id="sent-symbol-input"
          className="form-control"
          style={{ maxWidth: 200, marginBottom: 0 }}
          placeholder="Enter symbol (e.g. INFY)"
          value={symbol}
          onChange={e => setSymbol(e.target.value)}
          onKeyDown={e => e.key === 'Enter' && search()}
        />
        <button id="sent-search-btn" className="btn btn-primary btn-sm flex-center gap-2" onClick={search} disabled={loading}>
          {loading ? <span className="spinner" /> : <RefreshCw size={14} />} Analyse
        </button>
      </div>

      {loading && <div className="empty-state"><span className="spinner" style={{ width: 36, height: 36, borderWidth: 3 }} /></div>}

      {!loading && searched && records.length === 0 && (
        <div className="empty-state card">
          <TrendingUp size={40} />
          <p>No sentiment records for <strong>{symbol.toUpperCase()}</strong>.<br />
            Upload a document and run <em>POST /sentiment/recompute/&#123;id&#125;</em> first.</p>
        </div>
      )}

      {!loading && records.length > 0 && (
        <>
          {/* Chart */}
          <div className="card mb-6">
            <h3 style={{ fontSize: 15, fontWeight: 600, marginBottom: 16 }}>Sentiment Over Time — {symbol.toUpperCase()}</h3>
            <ResponsiveContainer width="100%" height={240}>
              <BarChart data={chartData} barGap={4}>
                <CartesianGrid strokeDasharray="3 3" stroke={cc.grid} />
                <XAxis dataKey="label" tick={{ fill: cc.tick, fontSize: 12 }} axisLine={false} tickLine={false} />
                <YAxis domain={[-1, 1]} tick={{ fill: cc.tick, fontSize: 12 }} axisLine={false} tickLine={false} />
                <Tooltip
                  contentStyle={cc.tooltip}
                />
                <Bar dataKey="overall" name="Overall" radius={[4,4,0,0]}>
                  {chartData.map((entry, i) => (
                    <Cell key={i} fill={scoreColor(entry.overall)} />
                  ))}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          </div>

          {/* Table */}
          <div className="table-wrap card" style={{ padding: 0 }}>
            <table>
              <thead>
                <tr>
                  <th>Period</th><th>Overall Score</th><th>Optimism</th>
                  <th>Risk Tone</th><th>Sentiment</th><th>Date</th>
                </tr>
              </thead>
              <tbody>
                {records.map(r => {
                  const { label, cls } = sentimentLabel(r.overall_score)
                  return (
                    <tr key={r.id}>
                      <td className="text-sm">
                        {[r.fiscal_quarter, r.fiscal_year].filter(Boolean).join(' / ') || '—'}
                      </td>
                      <td style={{ fontWeight: 700, color: scoreColor(r.overall_score) }}>
                        {(r.overall_score ?? 0).toFixed(4)}
                      </td>
                      <td>{(r.optimism_index ?? 0).toFixed(4)}</td>
                      <td style={{ color: 'var(--danger)' }}>{(r.risk_tone_index ?? 0).toFixed(4)}</td>
                      <td><span className={`badge ${cls}`}>{label}</span></td>
                      <td className="text-muted text-sm">
                        {new Date(r.computed_at).toLocaleDateString()}
                      </td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </div>
        </>
      )}
    </div>
  )
}
