import { useEffect, useState } from 'react'
import { ingestionApi, scraperApi } from '../api/client'
import { Upload, Play, FileText, RefreshCw, X, Search, Download, Zap } from 'lucide-react'

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
            <input id="doc-file" className="form-control" type="file" accept=".pdf"
              onChange={e => setFile(e.target.files[0])} required />
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
  // BSE Search state
  const [searchSymbol, setSearchSymbol] = useState('')
  const [filings, setFilings] = useState([])
  const [searchLoading, setSearchLoading] = useState(false)
  const [downloading, setDownloading] = useState({})
  const [autoFetching, setAutoFetching] = useState(false)
  const [autoFetchResult, setAutoFetchResult] = useState(null)
  const [activeTab, setActiveTab] = useState('manual') // 'manual' | 'auto'

  // Company Name Search state
  const [companySearch, setCompanySearch] = useState('')
  const [companyResults, setCompanyResults] = useState([])
  const [companyLoading, setCompanyLoading] = useState(false)

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

  const searchFilings = async (scripOverride) => {
    const query = scripOverride || searchSymbol.trim()
    if (!query) return
    setSearchSymbol(query)
    setSearchLoading(true); setFilings([])
    try {
      const r = await scraperApi.filings(query.toUpperCase())
      setFilings(r.data.filings ?? [])
    } catch (err) {
      setFilings([])
      alert(err.response?.data?.detail ?? 'Search failed')
    } finally { setSearchLoading(false) }
  }

  const handleSearchCompany = async () => {
    if (!companySearch.trim()) return
    setCompanyLoading(true); setCompanyResults([])
    try {
      const r = await scraperApi.searchCompany(companySearch.trim())
      setCompanyResults(r.data.results ?? [])
    } catch (err) {
       console.error(err)
    } finally { setCompanyLoading(false) }
  }

  const downloadFiling = async (filing) => {
    const key = filing.attachment_url
    setDownloading(p => ({ ...p, [key]: true }))
    try {
      const r = await scraperApi.download(filing.attachment_url, searchSymbol.toUpperCase(), 'quarterly_result')
      setDownloading(p => ({ ...p, [key]: `✅ Doc #${r.data.document_id}` }))
      load() // Refresh doc list
    } catch (err) {
      setDownloading(p => ({ ...p, [key]: `❌ ${err.response?.data?.detail ?? 'Failed'}` }))
    }
  }

  const autoFetch = async () => {
    setAutoFetching(true); setAutoFetchResult(null)
    try {
      const r = await scraperApi.autoFetch()
      setAutoFetchResult(r.data)
      load()
    } catch (err) {
      setAutoFetchResult({ status: 'error', detail: err.response?.data?.detail ?? 'Failed' })
    } finally { setAutoFetching(false) }
  }

  return (
    <div>
      <div className="flex-between mb-6">
        <div className="page-header" style={{ marginBottom: 0 }}>
          <h1 className="page-title">Documents</h1>
          <p className="page-sub">Upload PDFs or auto-fetch from BSE India</p>
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

      {/* Tab toggle */}
      <div className="card mb-6" style={{ padding: '6px', display: 'flex', gap: 4 }}>
        <button
          className={`btn btn-sm ${activeTab === 'manual' ? 'btn-primary' : 'btn-ghost'}`}
          onClick={() => setActiveTab('manual')}
          style={{ flex: 1 }}
        >
          <FileText size={14} /> My Documents
        </button>
        <button
          className={`btn btn-sm ${activeTab === 'auto' ? 'btn-primary' : 'btn-ghost'}`}
          onClick={() => setActiveTab('auto')}
          style={{ flex: 1 }}
        >
          <Search size={14} /> Search BSE Filings
        </button>
      </div>

      {activeTab === 'auto' && (
        <>
          {/* BSE Filing search */}
          <div className="card mb-6">
            <h3 style={{ fontSize: 14, fontWeight: 600, marginBottom: 12 }}>
              🔍 Search BSE Corporate Filings
            </h3>

            {/* Step 1: Search by Name */}
            <div style={{ padding: '12px', background: 'rgba(255,255,255,0.03)', borderRadius: 8, marginBottom: 16 }}>
              <div style={{ fontSize: 13, marginBottom: 8, color: 'var(--text-muted)' }}>
                1. Find the company (by name or partial name)
              </div>
              <div style={{ display: 'flex', gap: 10, alignItems: 'center', flexWrap: 'wrap' }}>
                <input className="form-control" style={{ maxWidth: 280, marginBottom: 0 }}
                  placeholder="e.g. Tata Motors" value={companySearch}
                  onChange={e => setCompanySearch(e.target.value)}
                  onKeyDown={e => e.key === 'Enter' && handleSearchCompany()} />
                <button className="btn btn-secondary btn-sm flex-center gap-2" onClick={handleSearchCompany}
                  disabled={companyLoading || !companySearch.trim()}>
                  {companyLoading ? <span className="spinner" /> : <Search size={14} />}
                  Find Company
                </button>
              </div>
              
              {companyResults.length > 0 && (
                <div style={{ marginTop: 12, display: 'flex', gap: 8, flexWrap: 'wrap' }}>
                  {companyResults.map((c, i) => (
                    <button key={i} className="btn btn-ghost btn-sm" 
                      style={{ border: '1px solid rgba(255,255,255,0.1)', textAlign: 'left', display: 'flex', flexDirection: 'column', alignItems: 'flex-start', padding: '6px 12px' }}
                      onClick={() => searchFilings(c.scrip_code)}>
                      <span style={{ fontWeight: 600, color: 'var(--text-primary)' }}>{c.company_name}</span>
                      <span style={{ fontSize: 11, color: 'var(--text-muted)' }}>Scrip: {c.scrip_code} • {c.industry}</span>
                    </button>
                  ))}
                </div>
              )}
            </div>

            <div style={{ fontSize: 13, marginBottom: 8, color: 'var(--text-muted)' }}>
              2. Or search directly by NSE Symbol or BSE Scrip Code
            </div>
            <div style={{ display: 'flex', gap: 10, alignItems: 'center', flexWrap: 'wrap', marginBottom: 12 }}>
              <input className="form-control" style={{ maxWidth: 200, marginBottom: 0 }}
                placeholder="NSE Symbol or Scrip Code" value={searchSymbol}
                onChange={e => setSearchSymbol(e.target.value)}
                onKeyDown={e => e.key === 'Enter' && searchFilings()} />
              <button className="btn btn-primary btn-sm flex-center gap-2" onClick={() => searchFilings()}
                disabled={searchLoading || !searchSymbol.trim()}>
                {searchLoading ? <span className="spinner" /> : <Search size={14} />}
                {searchLoading ? 'Searching…' : 'Search Filings'}
              </button>
              <div style={{ flex: 1 }} />
              <button className="btn btn-ghost btn-sm flex-center gap-2" onClick={autoFetch} disabled={autoFetching}>
                {autoFetching ? <span className="spinner" /> : <Zap size={14} />}
                {autoFetching ? 'Fetching…' : 'Auto-Fetch All Portfolio Docs'}
              </button>
            </div>

            {autoFetchResult && (
              <div className="text-sm mb-4" style={{
                padding: '8px 12px', borderRadius: 8,
                background: autoFetchResult.status === 'done' ? 'rgba(34,211,165,0.08)' : 'rgba(244,63,94,0.08)'
              }}>
                {autoFetchResult.status === 'done' ? (
                  autoFetchResult.results?.map((r, i) => (
                    <div key={i} style={{ marginBottom: 2 }}>
                      <strong>{r.symbol}</strong>: {r.status === 'ok' ? `${r.downloaded} new docs` : r.status}
                    </div>
                  ))
                ) : (
                  <span className="text-danger">{autoFetchResult.detail ?? 'Error'}</span>
                )}
              </div>
            )}

            {filings.length > 0 && (
              <div className="table-wrap" style={{ maxHeight: 400, overflow: 'auto' }}>
                <table>
                  <thead>
                    <tr>
                      <th>Date</th><th>Category</th><th>Title</th><th>Action</th>
                    </tr>
                  </thead>
                  <tbody>
                    {filings.map((f, i) => (
                      <tr key={i}>
                        <td className="text-xs text-muted" style={{ whiteSpace: 'nowrap' }}>{f.date}</td>
                        <td><span className="badge badge-info">{f.category}</span></td>
                        <td className="text-sm" style={{ maxWidth: 300, overflow: 'hidden', textOverflow: 'ellipsis' }}>
                          {f.title}
                        </td>
                        <td>
                          {f.attachment_url ? (
                            typeof downloading[f.attachment_url] === 'string' ? (
                              <span className="text-xs" style={{
                                color: downloading[f.attachment_url].startsWith('✅') ? 'var(--success)' : 'var(--danger)'
                              }}>
                                {downloading[f.attachment_url]}
                              </span>
                            ) : (
                              <button className="btn btn-ghost btn-sm flex-center gap-1"
                                onClick={() => downloadFiling(f)}
                                disabled={downloading[f.attachment_url] === true}>
                                {downloading[f.attachment_url] === true
                                  ? <span className="spinner" />
                                  : <Download size={13} />}
                                Download
                              </button>
                            )
                          ) : (
                            <span className="text-xs text-muted">No attachment</span>
                          )}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}

            {searchLoading === false && filings.length === 0 && searchSymbol && (
              <div className="text-sm text-muted" style={{ textAlign: 'center', padding: 20 }}>
                No filings found. Try a different symbol or check the BSE scrip code.
              </div>
            )}
          </div>
        </>
      )}

      {activeTab === 'manual' && (
        <>
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
              <FileText size={48} /><p>No documents yet.<br />Upload a PDF or search BSE filings.</p>
            </div>
          ) : (
            <div className="table-wrap card" style={{ padding: 0 }}>
              <table>
                <thead>
                  <tr>
                    <th>ID</th><th>Symbol</th><th>Type</th><th>Period</th>
                    <th>Uploaded</th><th>Status</th><th>Actions</th>
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
                        {doc.ingested_at ? new Date(doc.ingested_at).toLocaleDateString() : '—'}
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
        </>
      )}

      {showUpload && <UploadModal onClose={() => setShowUpload(false)} onUploaded={handleUploaded} />}
    </div>
  )
}
