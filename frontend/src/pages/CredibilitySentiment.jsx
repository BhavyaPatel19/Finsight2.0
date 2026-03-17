import { useState, useEffect } from 'react'
import { credisentimentApi } from '../api/client'
import {
    Scale, FileText, Loader, CheckCircle,
    AlertCircle, BarChart3, Crosshair, ChevronRight,
    RefreshCw, ArrowRight, Brain, ChevronDown, Info,
} from 'lucide-react'
import {
    BarChart, Bar, XAxis, YAxis, Tooltip,
    ResponsiveContainer, CartesianGrid, Cell,
    RadialBarChart, RadialBar, PolarAngleAxis,
} from 'recharts'

/* ── Helpers ────────────────────────────────────────────── */

const scoreColor = (s) => {
    if (s > 0.1) return '#22d3a5'
    if (s < -0.1) return '#f43f5e'
    return '#f59e0b'
}

const credScoreColor = (s) => {
    if (s >= 75) return '#22d3a5'
    if (s >= 50) return '#f59e0b'
    return '#f43f5e'
}

const credBadge = (s) => {
    if (s >= 75) return { label: 'Highly Credible', cls: 'badge-success' }
    if (s >= 50) return { label: 'Moderately Credible', cls: 'badge-warning' }
    return { label: 'Low Credibility', cls: 'badge-danger' }
}

const metBadge = (met) => {
    if (met === true) return { label: '✅ Met', color: '#22d3a5' }
    if (met === false) return { label: '❌ Missed', color: '#f43f5e' }
    return { label: '❓ Unclear', color: '#94a3b8' }
}

/* ── Score Dial ─────────────────────────────────────────── */

function ScoreDial({ score, size = 180 }) {
    const color = credScoreColor(score ?? 0)
    return (
        <div style={{ width: size, height: size, margin: '0 auto' }}>
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
                    <text x="50%" y="48%" textAnchor="middle" dominantBaseline="middle"
                        fill="#f1f5f9" fontSize={28} fontWeight={700} fontFamily="Inter">
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

/* ── Status badge ──────────────────────────────────────── */

function StatusBadge({ status, chunks }) {
    const styles = {
        indexed: { bg: '#dcfce7', color: '#166534', icon: <CheckCircle size={10} /> },
        processing: { bg: '#dbeafe', color: '#1e40af', icon: <Loader size={10} className="spin" /> },
        pending: { bg: '#fef3c7', color: '#92400e', icon: null },
        downloaded: { bg: '#fef3c7', color: '#92400e', icon: null },
        error: { bg: '#fee2e2', color: '#991b1b', icon: <AlertCircle size={10} /> },
    }
    const s = styles[status] || styles.pending
    return (
        <span style={{
            display: 'inline-flex', alignItems: 'center', gap: 3,
            fontSize: 10, padding: '1px 6px', borderRadius: 4,
            background: s.bg, color: s.color, marginTop: 3,
        }}>
            {s.icon} {status}{chunks > 0 ? ` · ${chunks} chunks` : ''}
        </span>
    )
}

/* ── Main Page ─────────────────────────────────────────── */

export default function CredibilitySentiment() {
    // Documents
    const [documents, setDocuments] = useState([])
    const [docsLoading, setDocsLoading] = useState(true)
    const [selectedIds, setSelectedIds] = useState(new Set())

    // Active tab
    const [tab, setTab] = useState('sentiment')

    // Feature 1: Sentiment
    const [sentimentResults, setSentimentResults] = useState([])
    const [analyzingS, setAnalyzingS] = useState(false)

    // Feature 2: Walk the Talk
    const [claimsDocId, setClaimsDocId] = useState(null)
    const [actualsDocId, setActualsDocId] = useState(null)
    const [wttResult, setWttResult] = useState(null)
    const [analyzingW, setAnalyzingW] = useState(false)
    const [wttError, setWttError] = useState('')

    useEffect(() => { loadDocuments() }, [])

    const loadDocuments = async () => {
        setDocsLoading(true)
        try {
            const r = await credisentimentApi.availableDocuments()
            setDocuments(r.data)
        } catch { setDocuments([]) }
        finally { setDocsLoading(false) }
    }

    const toggleDoc = (id) => {
        setSelectedIds(prev => {
            const next = new Set(prev)
            if (next.has(id)) next.delete(id)
            else next.add(id)
            return next
        })
    }

    const selectAll = () => {
        if (selectedIds.size === documents.length) setSelectedIds(new Set())
        else setSelectedIds(new Set(documents.map(d => d.id)))
    }

    /* ── Feature 1: Analyze Sentiment ──── */
    const runSentiment = async () => {
        const ids = [...selectedIds]
        if (!ids.length) return
        setAnalyzingS(true)
        setSentimentResults([])
        try {
            const r = await credisentimentApi.analyzeSentiment(ids)
            setSentimentResults(r.data)
        } catch (err) {
            setSentimentResults([])
        }
        finally { setAnalyzingS(false) }
    }

    /* ── Feature 2: Walk the Talk ──── */
    const runWalkTheTalk = async () => {
        if (!claimsDocId || !actualsDocId) {
            setWttError('Please select both a Claims Document and an Actuals Document.')
            return
        }
        if (claimsDocId === actualsDocId) {
            setWttError('Claims and Actuals documents must be different.')
            return
        }
        setAnalyzingW(true)
        setWttResult(null)
        setWttError('')
        try {
            const r = await credisentimentApi.walkTheTalk(claimsDocId, actualsDocId)
            setWttResult(r.data)
        } catch (err) {
            setWttError(err.response?.data?.detail || 'Analysis failed. Is Ollama running?')
        }
        finally { setAnalyzingW(false) }
    }

    /* ── Derived ──── */
    const getDocLabel = (id) => {
        const d = documents.find(x => x.id === id)
        if (!d) return `Doc #${id}`
        return `${d.symbol} · ${d.doc_type?.replace(/_/g, ' ')} ${d.fiscal_year || ''}`
    }

    return (
        <div>
            {/* Page header */}
            <div className="page-header">
                <h1 className="page-title" style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                    <Scale size={24} color="#8b5cf6" /> Credibility Sentiment
                </h1>
                <p className="page-sub">Division-level FinBERT sentiment analysis &amp; management credibility scoring</p>
            </div>

            <div style={{ display: 'flex', gap: 16, height: 'calc(100vh - 220px)', minHeight: 500 }}>

                {/* ── Left Panel: Document Picker ── */}
                <div className="card" style={{ width: 280, minWidth: 280, display: 'flex', flexDirection: 'column', padding: 0, overflow: 'hidden' }}>
                    <div style={{ padding: '14px 16px 10px', borderBottom: '1px solid var(--border)' }}>
                        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 8 }}>
                            <span style={{ fontWeight: 600, fontSize: 14 }}>
                                <FileText size={14} style={{ marginRight: 6, verticalAlign: -2 }} />
                                Documents
                            </span>
                            <div style={{ display: 'flex', gap: 4 }}>
                                <button className="btn btn-sm" onClick={selectAll} style={{ fontSize: 11, padding: '2px 8px' }}>
                                    {selectedIds.size === documents.length ? 'None' : 'All'}
                                </button>
                            </div>
                        </div>
                    </div>

                    {/* Document list */}
                    <div style={{ flex: 1, overflowY: 'auto', padding: '8px 0' }}>
                        {docsLoading ? (
                            <div style={{ textAlign: 'center', padding: 20, color: 'var(--text-muted)' }}>
                                <Loader size={16} className="spin" /> Loading...
                            </div>
                        ) : documents.length === 0 ? (
                            <div style={{ textAlign: 'center', padding: 20, color: 'var(--text-muted)', fontSize: 13 }}>
                                No documents found. Download some in the Documents tab or upload above.
                            </div>
                        ) : (
                            documents.map(doc => (
                                <label
                                    key={doc.id}
                                    style={{
                                        display: 'flex', alignItems: 'flex-start', gap: 8,
                                        padding: '8px 16px', cursor: 'pointer',
                                        background: selectedIds.has(doc.id) ? 'rgba(139,92,246,0.08)' : 'transparent',
                                        borderLeft: selectedIds.has(doc.id) ? '3px solid #8b5cf6' : '3px solid transparent',
                                        transition: 'background 0.15s',
                                    }}
                                >
                                    <input
                                        type="checkbox"
                                        checked={selectedIds.has(doc.id)}
                                        onChange={() => toggleDoc(doc.id)}
                                        style={{ marginTop: 3 }}
                                    />
                                    <div style={{ flex: 1, minWidth: 0 }}>
                                        <div style={{ fontWeight: 500, fontSize: 13, lineHeight: 1.3 }}>{doc.symbol}</div>
                                        <div style={{ fontSize: 11, color: 'var(--text-muted)', lineHeight: 1.4 }}>
                                            {doc.company_name || doc.doc_type?.replace(/_/g, ' ')}
                                            {doc.fiscal_year ? ` · ${doc.fiscal_year}` : ''}
                                        </div>
                                        <StatusBadge status={doc.status} chunks={doc.chunk_count} />
                                    </div>
                                </label>
                            ))
                        )}
                    </div>

                    {/* Action area */}
                    <div style={{ padding: '10px 16px', borderTop: '1px solid var(--border)' }}>
                        <div style={{ fontSize: 11, color: 'var(--text-muted)', marginBottom: 6, textAlign: 'center' }}>
                            {selectedIds.size} document(s) selected
                        </div>
                    </div>
                </div>

                {/* ── Right Panel: Tabs + Content ── */}
                <div style={{ flex: 1, display: 'flex', flexDirection: 'column', minWidth: 0 }}>
                    {/* Tab bar */}
                    <div style={{ display: 'flex', gap: 2, marginBottom: 16 }}>
                        <button
                            id="tab-sentiment"
                            className={`btn ${tab === 'sentiment' ? 'btn-primary' : 'btn-ghost'}`}
                            onClick={() => setTab('sentiment')}
                            style={{ flex: 1, borderRadius: '10px 10px 0 0', fontSize: 14, padding: '10px 0', fontWeight: 600, display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 8 }}
                        >
                            <BarChart3 size={16} /> FinBERT Sentiment
                        </button>
                        <button
                            id="tab-walkthetalk"
                            className={`btn ${tab === 'wtt' ? 'btn-primary' : 'btn-ghost'}`}
                            onClick={() => setTab('wtt')}
                            style={{ flex: 1, borderRadius: '10px 10px 0 0', fontSize: 14, padding: '10px 0', fontWeight: 600, display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 8 }}
                        >
                            <Crosshair size={16} /> Walking the Talk
                        </button>
                    </div>

                    {/* Tab content */}
                    <div className="card" style={{ flex: 1, overflow: 'auto', padding: 24 }}>

                        {/* ── TAB 1: FinBERT Sentiment ── */}
                        <div style={{ display: tab === 'sentiment' ? 'block' : 'none' }}>
                                <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 20 }}>
                                    <div>
                                        <h2 style={{ fontSize: 18, fontWeight: 700, margin: 0 }}>Division-Level Sentiment</h2>
                                        <p style={{ fontSize: 13, color: 'var(--text-muted)', margin: '4px 0 0' }}>
                                            FinBERT analyses sentiment per business division/section of your documents
                                        </p>
                                    </div>
                                    <button
                                        id="run-sentiment-btn"
                                        className="btn btn-primary flex-center gap-2"
                                        onClick={runSentiment}
                                        disabled={analyzingS || selectedIds.size === 0}
                                        style={{ fontSize: 13 }}
                                    >
                                        {analyzingS ? <><Loader size={14} className="spin" /> Analyzing...</> : <><RefreshCw size={14} /> Analyze Selected</>}
                                    </button>
                                </div>

                                {analyzingS && (
                                    <div className="empty-state">
                                        <span className="spinner" style={{ width: 36, height: 36, borderWidth: 3 }} />
                                        <p style={{ marginTop: 12 }}>Running FinBERT on document sections... This may take a minute.</p>
                                    </div>
                                )}

                                {!analyzingS && selectedIds.size === 0 && sentimentResults.length === 0 && (
                                    <div className="empty-state">
                                        <BarChart3 size={48} style={{ color: 'var(--text-muted)' }} />
                                        <p style={{ marginTop: 12, color: 'var(--text-muted)' }}>Select documents from the left panel and click <strong>Analyze Selected</strong></p>
                                    </div>
                                )}

                                {!analyzingS && sentimentResults.length > 0 && sentimentResults.map((docResult, di) => (
                                    <div key={di} style={{ marginBottom: 32 }}>
                                        <h3 style={{ fontSize: 15, fontWeight: 600, marginBottom: 16, display: 'flex', alignItems: 'center', gap: 8 }}>
                                            <FileText size={14} /> {docResult.symbol}
                                            <span style={{ fontSize: 12, fontWeight: 400, color: 'var(--text-muted)' }}>Document #{docResult.document_id}</span>
                                        </h3>

                                        {docResult.divisions.length === 0 ? (
                                            <div style={{ padding: 20, textAlign: 'center', color: 'var(--text-muted)', fontSize: 13 }}>
                                                No divisions/sections found in this document.
                                            </div>
                                        ) : (
                                            <>
                                                {/* Bar chart */}
                                                <div style={{ marginBottom: 20 }}>
                                                    <ResponsiveContainer width="100%" height={Math.max(200, docResult.divisions.length * 50)}>
                                                        <BarChart
                                                            data={docResult.divisions.map(d => ({
                                                                name: d.division_name.length > 30 ? d.division_name.slice(0, 28) + '…' : d.division_name,
                                                                positive: +(d.positive_score).toFixed(3),
                                                                negative: -(d.negative_score).toFixed(3),
                                                                neutral: +(d.neutral_score).toFixed(3),
                                                                overall: +(d.overall_score).toFixed(3),
                                                            }))}
                                                            layout="vertical"
                                                            margin={{ left: 10, right: 30 }}
                                                        >
                                                            <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.05)" />
                                                            <XAxis type="number" domain={[-1, 1]} tick={{ fill: '#94a3b8', fontSize: 11 }} axisLine={false} tickLine={false} />
                                                            <YAxis type="category" dataKey="name" width={160} tick={{ fill: '#cbd5e1', fontSize: 12 }} axisLine={false} tickLine={false} />
                                                            <Tooltip
                                                                contentStyle={{ background: '#0e1421', border: '1px solid rgba(255,255,255,0.1)', borderRadius: 10, fontSize: 13 }}
                                                            />
                                                            <Bar dataKey="positive" name="Positive" fill="#22d3a5" radius={[0, 4, 4, 0]} barSize={14} />
                                                            <Bar dataKey="negative" name="Negative" fill="#f43f5e" radius={[4, 0, 0, 4]} barSize={14} />
                                                        </BarChart>
                                                    </ResponsiveContainer>
                                                </div>

                                                {/* Table */}
                                                <div className="table-wrap" style={{ borderRadius: 10 }}>
                                                    <table>
                                                        <thead>
                                                            <tr>
                                                                <th>Division / Section</th>
                                                                <th>Positive</th>
                                                                <th>Negative</th>
                                                                <th>Neutral</th>
                                                                <th>Overall</th>
                                                                <th>Sentences</th>
                                                            </tr>
                                                        </thead>
                                                        <tbody>
                                                            {docResult.divisions.map((d, i) => (
                                                                <tr key={i}>
                                                                    <td style={{ fontWeight: 500 }}>{d.division_name}</td>
                                                                    <td style={{ color: '#22d3a5' }}>{d.positive_score.toFixed(3)}</td>
                                                                    <td style={{ color: '#f43f5e' }}>{d.negative_score.toFixed(3)}</td>
                                                                    <td style={{ color: '#f59e0b' }}>{d.neutral_score.toFixed(3)}</td>
                                                                    <td style={{ fontWeight: 700, color: scoreColor(d.overall_score) }}>
                                                                        {d.overall_score.toFixed(3)}
                                                                    </td>
                                                                    <td className="text-muted">{d.sentence_count}</td>
                                                                </tr>
                                                            ))}
                                                        </tbody>
                                                    </table>
                                                </div>
                                            </>
                                        )}
                                    </div>
                                ))}
                        </div>

                        {/* ── TAB 2: Walking the Talk ── */}
                        <div style={{ display: tab === 'wtt' ? 'block' : 'none' }}>
                                <div style={{ marginBottom: 20 }}>
                                    <h2 style={{ fontSize: 18, fontWeight: 700, margin: 0 }}>Walking the Talk</h2>
                                    <p style={{ fontSize: 13, color: 'var(--text-muted)', margin: '4px 0 0' }}>
                                        Compare management's promises against actual results using DeepSeek R1
                                    </p>
                                </div>

                                {/* Document selectors */}
                                <div style={{
                                    display: 'grid', gridTemplateColumns: '1fr auto 1fr', gap: 16,
                                    alignItems: 'start', marginBottom: 20,
                                }}>
                                    {/* Claims doc */}
                                    <div style={{
                                        padding: 16, borderRadius: 12,
                                        background: 'rgba(99,102,241,0.06)', border: '1px solid rgba(99,102,241,0.15)',
                                    }}>
                                        <div style={{ fontSize: 12, fontWeight: 600, color: '#818cf8', marginBottom: 8, textTransform: 'uppercase', letterSpacing: '0.05em' }}>
                                            📄 Claims Document (Older)
                                        </div>
                                        <select
                                            id="claims-doc-select"
                                            className="form-control"
                                            value={claimsDocId || ''}
                                            onChange={e => setClaimsDocId(e.target.value ? Number(e.target.value) : null)}
                                            style={{ marginBottom: 0, fontSize: 13 }}
                                        >
                                            <option value="">Select document...</option>
                                            {documents.map(d => (
                                                <option key={d.id} value={d.id}>
                                                    {d.symbol} · {d.doc_type?.replace(/_/g, ' ')} {d.fiscal_year || ''}
                                                    {d.company_name ? ` (${d.company_name})` : ''}
                                                </option>
                                            ))}
                                        </select>
                                        <div style={{ fontSize: 11, color: 'var(--text-muted)', marginTop: 4 }}>
                                            Contains promises, guidance, forward-looking statements
                                        </div>
                                    </div>

                                    {/* Arrow */}
                                    <div style={{ display: 'flex', alignItems: 'center', paddingTop: 32 }}>
                                        <ArrowRight size={24} style={{ color: '#8b5cf6' }} />
                                    </div>

                                    {/* Actuals doc */}
                                    <div style={{
                                        padding: 16, borderRadius: 12,
                                        background: 'rgba(34,211,165,0.06)', border: '1px solid rgba(34,211,165,0.15)',
                                    }}>
                                        <div style={{ fontSize: 12, fontWeight: 600, color: '#22d3a5', marginBottom: 8, textTransform: 'uppercase', letterSpacing: '0.05em' }}>
                                            📊 Actuals Document (Newer)
                                        </div>
                                        <select
                                            id="actuals-doc-select"
                                            className="form-control"
                                            value={actualsDocId || ''}
                                            onChange={e => setActualsDocId(e.target.value ? Number(e.target.value) : null)}
                                            style={{ marginBottom: 0, fontSize: 13 }}
                                        >
                                            <option value="">Select document...</option>
                                            {documents.map(d => (
                                                <option key={d.id} value={d.id}>
                                                    {d.symbol} · {d.doc_type?.replace(/_/g, ' ')} {d.fiscal_year || ''}
                                                    {d.company_name ? ` (${d.company_name})` : ''}
                                                </option>
                                            ))}
                                        </select>
                                        <div style={{ fontSize: 11, color: 'var(--text-muted)', marginTop: 4 }}>
                                            Contains actual financial results and outcomes
                                        </div>
                                    </div>
                                </div>

                                {/* Compare button */}
                                <div style={{ textAlign: 'center', marginBottom: 24 }}>
                                    <button
                                        id="run-wtt-btn"
                                        className="btn btn-primary flex-center gap-2"
                                        onClick={runWalkTheTalk}
                                        disabled={analyzingW || !claimsDocId || !actualsDocId}
                                        style={{ fontSize: 14, padding: '10px 32px' }}
                                    >
                                        {analyzingW ? (
                                            <><Loader size={14} className="spin" /> Analyzing with DeepSeek R1...</>
                                        ) : (
                                            <><Crosshair size={16} /> Compare &amp; Analyze</>
                                        )}
                                    </button>
                                    {wttError && (
                                        <div style={{ marginTop: 8, color: 'var(--danger)', fontSize: 13 }}>
                                            <AlertCircle size={13} style={{ verticalAlign: -2, marginRight: 4 }} />{wttError}
                                        </div>
                                    )}
                                </div>

                                {analyzingW && (
                                    <div className="empty-state">
                                        <span className="spinner" style={{ width: 36, height: 36, borderWidth: 3 }} />
                                        <p style={{ marginTop: 12 }}>DeepSeek R1 is analyzing documents... This may take 1-3 minutes.</p>
                                    </div>
                                )}

                                {!analyzingW && !wttResult && !wttError && (
                                    <div className="empty-state" style={{ marginTop: 40 }}>
                                        <Crosshair size={48} style={{ color: 'var(--text-muted)' }} />
                                        <p style={{ marginTop: 12, color: 'var(--text-muted)' }}>
                                            Select a <strong>Claims Document</strong> (older — with promises) and an <strong>Actuals Document</strong> (newer — with results),
                                            then click <strong>Compare &amp; Analyze</strong>
                                        </p>
                                    </div>
                                )}

                                {!analyzingW && wttResult && (
                                    <div>
                                        {/* Score + Summary */}
                                        <div style={{ display: 'grid', gridTemplateColumns: '240px 1fr', gap: 20, marginBottom: 24 }}>
                                            <div className="card" style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 12, padding: '24px 16px' }}>
                                                <div style={{ fontSize: 11, textTransform: 'uppercase', letterSpacing: '0.06em', color: 'var(--text-muted)', fontWeight: 600 }}>
                                                    Credibility Score
                                                </div>
                                                <ScoreDial score={wttResult.overall_score} size={160} />
                                                <span className={`badge ${credBadge(wttResult.overall_score).cls}`} style={{ fontSize: 13 }}>
                                                    {credBadge(wttResult.overall_score).label}
                                                </span>
                                            </div>

                                            <div className="card" style={{ padding: 20 }}>
                                                <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 10 }}>
                                                    <Brain size={16} color="#8b5cf6" />
                                                    <h3 style={{ fontSize: 15, fontWeight: 600, margin: 0 }}>AI Assessment</h3>
                                                </div>
                                                <p style={{ fontSize: 14, lineHeight: 1.7, color: 'var(--text-secondary)', margin: 0 }}>
                                                    {wttResult.narrative_summary}
                                                </p>
                                                <div style={{ marginTop: 12, display: 'flex', gap: 12, fontSize: 11, color: 'var(--text-muted)' }}>
                                                    <span>📄 Claims: {getDocLabel(wttResult.claims_document_id)}</span>
                                                    <span>📊 Actuals: {getDocLabel(wttResult.actuals_document_id)}</span>
                                                </div>
                                            </div>
                                        </div>

                                        {/* Claim comparison cards */}
                                        {wttResult.claims.length > 0 && (
                                            <div>
                                                <h3 style={{ fontSize: 15, fontWeight: 600, marginBottom: 16, display: 'flex', alignItems: 'center', gap: 8 }}>
                                                    <Info size={14} color="#8b5cf6" /> Claim-by-Claim Comparison ({wttResult.claims.length})
                                                </h3>
                                                <div style={{ display: 'grid', gap: 12 }}>
                                                    {wttResult.claims.map((c, i) => {
                                                        const { label: metLabel, color: metColor } = metBadge(c.met)
                                                        return (
                                                            <div key={i} style={{
                                                                padding: '16px 20px', borderRadius: 12,
                                                                background: 'rgba(255,255,255,0.02)',
                                                                border: `1px solid ${c.met === true ? 'rgba(34,211,165,0.2)' : c.met === false ? 'rgba(244,63,94,0.2)' : 'rgba(148,163,184,0.15)'}`,
                                                            }}>
                                                                <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', gap: 12 }}>
                                                                    <div style={{ flex: 1 }}>
                                                                        <div style={{ fontWeight: 600, fontSize: 14, marginBottom: 6, lineHeight: 1.4 }}>
                                                                            {c.claim}
                                                                        </div>
                                                                        <div style={{ display: 'flex', gap: 16, flexWrap: 'wrap', fontSize: 13, marginBottom: 6 }}>
                                                                            {c.claimed_value && (
                                                                                <span style={{ color: '#818cf8' }}>
                                                                                    <strong>Claimed:</strong> {c.claimed_value}
                                                                                </span>
                                                                            )}
                                                                            {c.actual_value && (
                                                                                <span style={{ color: '#22d3a5' }}>
                                                                                    <strong>Actual:</strong> {c.actual_value}
                                                                                </span>
                                                                            )}
                                                                        </div>
                                                                        {c.explanation && (
                                                                            <div style={{ fontSize: 12, color: 'var(--text-muted)', lineHeight: 1.5 }}>
                                                                                {c.explanation}
                                                                            </div>
                                                                        )}
                                                                    </div>
                                                                    <div style={{
                                                                        flexShrink: 0, padding: '4px 12px', borderRadius: 8,
                                                                        fontSize: 12, fontWeight: 600, color: metColor,
                                                                        background: `${metColor}15`,
                                                                    }}>
                                                                        {metLabel}
                                                                    </div>
                                                                </div>
                                                                <div style={{ marginTop: 6, fontSize: 11, color: 'var(--text-muted)' }}>
                                                                    Category: <span style={{ textTransform: 'capitalize' }}>{c.category?.replace(/_/g, ' ')}</span>
                                                                </div>
                                                            </div>
                                                        )
                                                    })}
                                                </div>
                                            </div>
                                        )}
                                    </div>
                                )}
                        </div>
                    </div>
                </div>
            </div>
        </div>
    )
}
