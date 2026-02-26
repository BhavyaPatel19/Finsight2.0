import { useState } from 'react'
import { credibilityApi } from '../api/client'
import { ShieldCheck, RefreshCw, Zap } from 'lucide-react'
import {
  RadialBarChart, RadialBar, ResponsiveContainer, PolarAngleAxis
} from 'recharts'

const scoreColor = (s) => {
  if (s >= 75) return '#22d3a5'
  if (s >= 50) return '#f59e0b'
  return '#f43f5e'
}

const scoreBadge = (s) => {
  if (s >= 75) return 'badge-success'
  if (s >= 50) return 'badge-warning'
  return 'badge-danger'
}

function ScoreDial({ score }) {
  const color = scoreColor(score ?? 0)
  return (
    <div style={{ width: 160, height: 160, margin: '0 auto' }}>
      <ResponsiveContainer>
        <RadialBarChart
          innerRadius="70%" outerRadius="100%"
          data={[{ value: score ?? 0, fill: color }]}
          startAngle={225} endAngle={-45}
        >
          <PolarAngleAxis type="number" domain={[0, 100]} angleAxisId={0} tick={false} />
          <RadialBar
            background={{ fill: 'rgba(255,255,255,0.06)' }}
            dataKey="value" cornerRadius={8} angleAxisId={0}
          />
          <text x="50%" y="50%" textAnchor="middle" dominantBaseline="middle"
            fill="#f1f5f9" fontSize={26} fontWeight={700} fontFamily="Inter">
            {score != null ? Math.round(score) : '—'}
          </text>
          <text x="50%" y="62%" textAnchor="middle" dominantBaseline="middle"
            fill="#94a3b8" fontSize={11} fontFamily="Inter">
            / 100
          </text>
        </RadialBarChart>
      </ResponsiveContainer>
    </div>
  )
}

export default function Credibility() {
  const [symbol, setSymbol] = useState('')
  const [records, setRecords] = useState([])
  const [loading, setLoading] = useState(false)
  const [recomputePeriod, setRecomputePeriod] = useState('')
  const [recomputing, setRecomputing] = useState(false)
  const [recomputeMsg, setRecomputeMsg] = useState('')
  const [searched, setSearched] = useState(false)

  const search = async () => {
    if (!symbol.trim()) return
    setLoading(true); setSearched(true)
    try {
      const r = await credibilityApi.history(symbol.toUpperCase())
      setRecords(Array.isArray(r.data) ? r.data : [])
    } catch { setRecords([]) }
    finally { setLoading(false) }
  }

  const recompute = async () => {
    if (!symbol || !recomputePeriod) { setRecomputeMsg('Enter symbol and period first.'); return }
    setRecomputing(true); setRecomputeMsg('')
    try {
      const r = await credibilityApi.recompute(symbol.toUpperCase(), recomputePeriod)
      setRecomputeMsg(`✅ Score: ${r.data.score_0_100}`)
      search()
    } catch (err) {
      setRecomputeMsg(`❌ ${err.response?.data?.detail ?? 'Failed'}`)
    } finally { setRecomputing(false) }
  }

  const latest = records[0]

  return (
    <div>
      <div className="page-header">
        <h1 className="page-title" style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
          <ShieldCheck size={24} color="#6366f1" /> Credibility Scoring
        </h1>
        <p className="page-sub">Compare management claims against actual financial metrics</p>
      </div>

      {/* Search + recompute bar */}
      <div className="card mb-6" style={{ display: 'flex', gap: 12, flexWrap: 'wrap', alignItems: 'center', padding: '16px 20px' }}>
        <input
          id="cred-symbol-input"
          className="form-control"
          style={{ maxWidth: 180, marginBottom: 0 }}
          placeholder="Symbol (e.g. INFY)"
          value={symbol}
          onChange={e => setSymbol(e.target.value)}
          onKeyDown={e => e.key === 'Enter' && search()}
        />
        <button id="cred-search-btn" className="btn btn-primary btn-sm" onClick={search} disabled={loading}>
          {loading ? <span className="spinner" /> : <RefreshCw size={14} />} Load History
        </button>

        <div style={{ width: 1, height: 28, background: 'var(--border)' }} />

        <input
          id="cred-period-input"
          className="form-control"
          style={{ maxWidth: 140, marginBottom: 0 }}
          placeholder="Period (e.g. FY25)"
          value={recomputePeriod}
          onChange={e => setRecomputePeriod(e.target.value)}
        />
        <button id="cred-recompute-btn" className="btn btn-ghost btn-sm flex-center gap-2"
          onClick={recompute} disabled={recomputing}>
          {recomputing ? <span className="spinner" /> : <Zap size={14} />} Recompute
        </button>
        {recomputeMsg && (
          <span className="text-sm" style={{ color: recomputeMsg.startsWith('✅') ? 'var(--success)' : 'var(--danger)' }}>
            {recomputeMsg}
          </span>
        )}
      </div>

      {loading && <div className="empty-state"><span className="spinner" style={{ width: 36, height: 36, borderWidth: 3 }} /></div>}

      {!loading && searched && records.length === 0 && (
        <div className="empty-state card">
          <ShieldCheck size={40} />
          <p>No credibility records for <strong>{symbol.toUpperCase()}</strong>.<br />
            Upload a doc, run claim extraction, then recompute.</p>
        </div>
      )}

      {!loading && records.length > 0 && (
        <>
          {/* Latest score */}
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 2fr', gap: 20, marginBottom: 24 }}>
            <div className="card" style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 12, padding: '28px 20px' }}>
              <div className="text-sm text-muted" style={{ textTransform: 'uppercase', letterSpacing: '0.06em' }}>Latest Score</div>
              <ScoreDial score={latest?.score_0_100} />
              <span className={`badge ${scoreBadge(latest?.score_0_100)}`} style={{ fontSize: 13 }}>
                {latest?.score_0_100 >= 75 ? 'High Credibility'
                  : latest?.score_0_100 >= 50 ? 'Moderate Credibility' : 'Low Credibility'}
              </span>
              <div className="text-xs text-muted">
                Period: {latest?.period ?? '—'} · Avg deviation: {(latest?.avg_deviation * 100)?.toFixed(2) ?? '—'}%
              </div>
            </div>

            <div className="card">
              <h3 style={{ fontSize: 15, fontWeight: 600, marginBottom: 14 }}>Score History</h3>
              <div className="table-wrap" style={{ borderRadius: 8 }}>
                <table>
                  <thead>
                    <tr><th>Period</th><th>Score</th><th>Avg Deviation</th><th>Grade</th><th>Date</th></tr>
                  </thead>
                  <tbody>
                    {records.map(r => (
                      <tr key={r.id}>
                        <td className="font-bold">{r.period}</td>
                        <td style={{ fontWeight: 700, color: scoreColor(r.score_0_100) }}>
                          {r.score_0_100.toFixed(1)}
                        </td>
                        <td>{(r.avg_deviation * 100).toFixed(2)}%</td>
                        <td><span className={`badge ${scoreBadge(r.score_0_100)}`}>
                          {r.score_0_100 >= 75 ? 'High' : r.score_0_100 >= 50 ? 'Medium' : 'Low'}
                        </span></td>
                        <td className="text-muted text-sm">
                          {new Date(r.computed_at).toLocaleDateString()}
                        </td>
                      </tr>
                    ))}
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
