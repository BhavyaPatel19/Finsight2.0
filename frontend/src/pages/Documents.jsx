import { useEffect, useState, useRef } from 'react'
import { ingestionApi } from '../api/client'
import { Upload, Play, FileText, RefreshCw, X } from 'lucide-react'

const DOC_TYPES = ['annual_report', 'quarterly_report', 'earnings_call', 'investor_presentation', 'other']

function UploadModal({ onClose, onUploaded }) {
  const [file, setFile] = useState(null)
  const [symbol, setSymbol] = useState('')
  const [docType, setDocType] = useState('annual_report')
  const [quarter, setQuarter] = useState('')
  const [year, setYear] = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')

  const handleSubmit = async (e) => {
    e.preventDefault()
    if (!file || !symbol) { setError('File and symbol are required.'); return }
    setLoading(true); setError('')
    try {
      const r = await ingestionApi.upload(file, symbol.toUpperCase(), docType, quarter, year)
      onUploaded(r.data)
    } catch (err) {
      setError(err.response?.data?.detail ?? 'Upload failed.')
    } finally { setLoading(false) }
  }

  return (
    <div style={{
      position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.7)',
      display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 999
    }}>
      <div className="card" style={{ width: 480, maxWidth: '95vw', position: 'relative' }}>
        <div className="flex-between mb-4">
          <h3 style={{ fontSize: 16, fontWeight: 700 }}>Upload Document</h3>
          <button className="btn btn-ghost btn-sm" onClick={onClose} style={{ padding: '4px 8px' }}>
            <X size={16} />
          </button>
        </div>

        {error && <div className="alert alert-error"><span>⚠</span> {error}</div>}

        <form onSubmit={handleSubmit}>
          <div className="form-group">
            <label className="form-label">PDF File *</label>
            <input
              id="doc-file"
              className="form-control"
              type="file"
              accept=".pdf"
              onChange={e => setFile(e.target.files[0])}
              required
            />
          </div>
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12 }}>
            <div className="form-group">
              <label className="form-label">Symbol *</label>
              <input id="doc-symbol" className="form-control" placeholder="e.g. INFY" value={symbol}
                onChange={e => setSymbol(e.target.value)} required />
            </div>
            <div className="form-group">
              <label className="form-label">Doc Type *</label>
              <select id="doc-type" className="form-control" value={docType} onChange={e => setDocType(e.target.value)}>
                {DOC_TYPES.map(t => <option key={t} value={t}>{t.replace(/_/g, ' ')}</option>)}
              </select>
            </div>
            <div className="form-group">
              <label className="form-label">Fiscal Quarter</label>
              <input id="doc-quarter" className="form-control" placeholder="e.g. Q3" value={quarter}
                onChange={e => setQuarter(e.target.value)} />
            </div>
            <div className="form-group">
              <label className="form-label">Fiscal Year</label>
              <input id="doc-year" className="form-control" placeholder="e.g. FY25" value={year}
                onChange={e => setYear(e.target.value)} />
            </div>
          </div>
          <button id="doc-upload-btn" className="btn btn-primary w-full" type="submit"
            disabled={loading} style={{ justifyContent: 'center' }}>
            {loading ? <><span className="spinner" /> Uploading…</> : <><Upload size={15} /> Upload & Register</>}
          </button>
        </form>
      </div>
    </div>
  )
}

export default function Documents() {
  const [docs, setDocs] = useState([])
  const [loading, setLoading] = useState(true)
  const [showUpload, setShowUpload] = useState(false)
  const [running, setRunning] = useState({})
  const [statusMsg, setStatusMsg] = useState({})
  const [filterSymbol, setFilterSymbol] = useState('')

  const load = async () => {
    setLoading(true)
    try {
      const r = await ingestionApi.list(filterSymbol || undefined)
      setDocs(r.data)
    } catch { setDocs([]) }
    finally { setLoading(false) }
  }

  useEffect(() => { load() }, [filterSymbol])

  const runIngestion = async (docId) => {
    setRunning(p => ({ ...p, [docId]: true }))
    setStatusMsg(p => ({ ...p, [docId]: '' }))
    try {
      const r = await ingestionApi.run(docId)
      setStatusMsg(p => ({ ...p, [docId]: `✅ Indexed ${r.data.chunks_indexed ?? ''} chunks` }))
    } catch (err) {
      setStatusMsg(p => ({ ...p, [docId]: `❌ ${err.response?.data?.detail ?? 'Failed'}` }))
    } finally { setRunning(p => ({ ...p, [docId]: false })) }
  }

  const handleUploaded = (doc) => {
    setShowUpload(false)
    setDocs(prev => [doc, ...prev])
  }

  return (
    <div>
      <div className="flex-between mb-6">
        <div className="page-header" style={{ marginBottom: 0 }}>
          <h1 className="page-title">Documents</h1>
          <p className="page-sub">Upload PDFs and ingest them into the RAG knowledge base</p>
        </div>
        <div className="flex gap-2">
          <button className="btn btn-ghost btn-sm flex-center gap-2" onClick={load}>
            <RefreshCw size={14} />
          </button>
          <button id="open-upload-modal" className="btn btn-primary btn-sm" onClick={() => setShowUpload(true)}>
            <Upload size={14} /> Upload PDF
          </button>
        </div>
      </div>

      <div className="card mb-6" style={{ display: 'flex', gap: 12, alignItems: 'center' }}>
        <input className="form-control" style={{ maxWidth: 240, marginBottom: 0 }}
          placeholder="Filter by symbol…" value={filterSymbol}
          onChange={e => setFilterSymbol(e.target.value)} />
        <span className="text-sm text-muted">{docs.length} document{docs.length !== 1 ? 's' : ''}</span>
      </div>

      {loading ? (
        <div className="empty-state"><span className="spinner" style={{ width: 36, height: 36, borderWidth: 3 }} /></div>
      ) : docs.length === 0 ? (
        <div className="empty-state card">
          <FileText size={48} /><p>No documents yet.<br />Upload a PDF to get started.</p>
        </div>
      ) : (
        <div className="table-wrap card" style={{ padding: 0 }}>
          <table>
            <thead>
              <tr>
                <th>ID</th><th>Symbol</th><th>Type</th><th>Period</th>
                <th>Ingested</th><th>Status</th><th>Actions</th>
              </tr>
            </thead>
            <tbody>
              {docs.map(doc => (
                <tr key={doc.id}>
                  <td className="text-muted text-xs">#{doc.id}</td>
                  <td><span className="badge badge-accent">{doc.symbol}</span></td>
                  <td><span className="badge badge-info">{doc.doc_type?.replace(/_/g,' ')}</span></td>
                  <td className="text-sm">
                    {[doc.fiscal_quarter, doc.fiscal_year].filter(Boolean).join(' / ') || '—'}
                  </td>
                  <td className="text-sm text-muted">
                    {new Date(doc.ingested_at).toLocaleDateString()}
                  </td>
                  <td>
                    {doc.text_path
                      ? <span className="badge badge-success">✓ Extracted</span>
                      : <span className="badge badge-warning">Pending</span>}
                  </td>
                  <td>
                    <div className="flex gap-2" style={{ alignItems: 'center' }}>
                      <button
                        id={`ingest-btn-${doc.id}`}
                        className="btn btn-ghost btn-sm flex-center gap-2"
                        disabled={running[doc.id]}
                        onClick={() => runIngestion(doc.id)}
                      >
                        {running[doc.id] ? <span className="spinner" /> : <Play size={13} />}
                        Ingest
                      </button>
                      {statusMsg[doc.id] && (
                        <span className="text-xs" style={{ color: statusMsg[doc.id].startsWith('✅') ? 'var(--success)' : 'var(--danger)' }}>
                          {statusMsg[doc.id]}
                        </span>
                      )}
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {showUpload && <UploadModal onClose={() => setShowUpload(false)} onUploaded={handleUploaded} />}
    </div>
  )
}
