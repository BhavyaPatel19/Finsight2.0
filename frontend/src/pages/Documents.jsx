import { useEffect, useState, useRef, useCallback } from 'react'
import { useNavigate } from 'react-router-dom'
import { ingestionApi, scraperApi, credisentimentApi } from '../api/client'
import GlowCard from '../components/GlowCard'
import AnimatedCheckbox from '../components/AnimatedCheckbox'
import {
  Search, FileText, Trash2, Eye, MessageSquare,
  Download, RefreshCw, Loader, CheckCircle, AlertCircle,
  Upload, X, Play, ChevronRight, BookOpen, Mic
} from 'lucide-react'

const PIPELINE_STATUS = {
  pending:    { label: 'Unprocessed', color: '#94a3b8', bg: 'rgba(148,163,184,0.12)', icon: null },
  processing: { label: 'Processing',  color: '#38bdf8', bg: 'rgba(56,189,248,0.12)', spin: true },
  indexed:    { label: 'Processed',   color: '#22d3a5', bg: 'rgba(34,211,165,0.12)', icon: CheckCircle },
  error:      { label: 'Error',       color: '#f43f5e', bg: 'rgba(244,63,94,0.12)', icon: AlertCircle },
}

const CATEGORY_ICONS = {
  annual_report: BookOpen,
  concall: Mic,
  announcement: FileText,
  credit_rating: FileText,
}

const CATEGORY_COLORS = {
  annual_report: { color: '#818cf8', bg: 'rgba(129,140,248,0.12)' },
  concall: { color: '#34d399', bg: 'rgba(52,211,153,0.12)' },
  announcement: { color: '#fbbf24', bg: 'rgba(251,191,36,0.12)' },
  credit_rating: { color: '#f472b6', bg: 'rgba(244,114,182,0.12)' },
}

function PipelineStatusBadge({ status, label }) {
  const cfg = PIPELINE_STATUS[status] || PIPELINE_STATUS.pending
  const Icon = cfg.icon
  return (
    <span style={{
      display: 'inline-flex', alignItems: 'center', gap: 5,
      padding: '3px 10px', borderRadius: 20, fontSize: 12, fontWeight: 600,
      color: cfg.color, background: cfg.bg,
    }}>
      {cfg.spin && <span className="spinner" style={{ width: 12, height: 12, borderWidth: 2, borderColor: `${cfg.color} transparent transparent transparent` }} />}
      {Icon && <Icon size={12} />}
      {label}: {cfg.label}
    </span>
  )
}

function ProcessButton({ status, onClick, label }) {
  if (status === 'processing') {
    return (
      <button disabled className="doc-action-btn" title={`${label}: Processing...`}>
        <span className="spinner" style={{ width: 14, height: 14, borderWidth: 2 }} />
      </button>
    )
  }
  if (status === 'indexed') {
    return (
      <button disabled className="doc-action-btn success" title={`${label}: Processed`}>
        <CheckCircle size={14} />
      </button>
    )
  }
  return (
    <button className="doc-action-btn" onClick={onClick}
      title={`Process for ${label}`}>
      <Play size={14} style={{ color: status === 'error' ? 'var(--danger)' : undefined }} />
    </button>
  )
}

function CategoryBadge({ category }) {
  const cfg = CATEGORY_COLORS[category] || CATEGORY_COLORS.announcement
  return (
    <span style={{
      display: 'inline-flex', alignItems: 'center', gap: 4,
      padding: '2px 8px', borderRadius: 12, fontSize: 11, fontWeight: 600,
      color: cfg.color, background: cfg.bg,
    }}>
      {category?.replace(/_/g, ' ')}
    </span>
  )
}

function formatSize(bytes) {
  if (!bytes) return '—'
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1048576) return `${(bytes / 1024).toFixed(1)} KB`
  return `${(bytes / 1048576).toFixed(1)} MB`
}

/* ─── Upload Modal ─────────────────────────────────── */
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
            <input className="form-control" type="file" accept=".pdf,.htm,.html,.txt"
              onChange={e => setFile(e.target.files[0])} required />
          </div>
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12 }}>
            <div className="form-group">
              <label className="form-label">Symbol *</label>
              <input className="form-control" placeholder="e.g. INFY" value={symbol}
                onChange={e => setSymbol(e.target.value)} required />
            </div>
            <div className="form-group">
              <label className="form-label">Doc Type</label>
              <select className="form-control" value={docType} onChange={e => setDocType(e.target.value)}>
                <option value="annual_report">Annual Report</option>
                <option value="quarterly_report">Quarterly Report</option>
                <option value="concall">Concall Transcript</option>
                <option value="other">Other</option>
              </select>
            </div>
            <div className="form-group">
              <label className="form-label">Fiscal Quarter</label>
              <input className="form-control" placeholder="e.g. Q3" value={quarter}
                onChange={e => setQuarter(e.target.value)} />
            </div>
            <div className="form-group">
              <label className="form-label">Fiscal Year</label>
              <input className="form-control" placeholder="e.g. FY25" value={year}
                onChange={e => setYear(e.target.value)} />
            </div>
          </div>
          <button className="btn btn-primary w-full" type="submit"
            disabled={loading} style={{ justifyContent: 'center' }}>
            {loading ? <><span className="spinner" /> Uploading…</> : <><Upload size={15} /> Upload & Index</>}
          </button>
        </form>
      </div>
    </div>
  )
}

/* ─── Delete Confirmation ──────────────────────────── */
function DeleteConfirm({ doc, onCancel, onConfirm, deleting }) {
  return (
    <div style={{
      position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.7)',
      display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 999
    }}>
      <div className="card" style={{ width: 420, maxWidth: '95vw', textAlign: 'center' }}>
        <Trash2 size={36} style={{ color: 'var(--danger)', marginBottom: 8 }} />
        <h3 style={{ fontSize: 16, fontWeight: 700, marginBottom: 4 }}>Delete Document</h3>
        <p className="text-sm text-muted" style={{ margin: '0 0 16px' }}>
          Permanently removes the PDF, text chunks, and ChromaDB embeddings.
        </p>
        <div style={{
          padding: '10px 14px', borderRadius: 8, marginBottom: 16,
          background: 'rgba(244,63,94,0.06)', border: '1px solid rgba(244,63,94,0.15)',
          fontSize: 13, textAlign: 'left',
        }}>
          <strong>{doc.company_name || doc.symbol}</strong>
          <span className="text-muted" style={{ marginLeft: 8 }}>
            #{doc.id} · {doc.doc_type?.replace(/_/g, ' ')}
          </span>
        </div>
        <div style={{ display: 'flex', gap: 10, justifyContent: 'center' }}>
          <button className="btn btn-ghost btn-sm" onClick={onCancel} disabled={deleting}>Cancel</button>
          <button className="btn btn-sm" onClick={onConfirm} disabled={deleting}
            style={{ background: 'var(--danger)', color: '#fff', border: 'none' }}>
            {deleting ? <><span className="spinner" /> Deleting…</> : <><Trash2 size={13} /> Delete</>}
          </button>
        </div>
      </div>
    </div>
  )
}

/* ─── Document Picker (available docs from Screener) ─ */
function DocumentPicker({ companyDocs, onDownload, onClose, downloading }) {
  const [selected, setSelected] = useState(new Set())
  const allDocs = [
    ...(companyDocs.annual_reports || []),
    ...(companyDocs.concalls || []),
    ...(companyDocs.announcements || []),
    ...(companyDocs.credit_ratings || []),
  ]

  const toggle = (idx) => {
    const next = new Set(selected)
    next.has(idx) ? next.delete(idx) : next.add(idx)
    setSelected(next)
  }

  const toggleCategory = (cat) => {
    const catDocs = allDocs
      .map((d, i) => ({ ...d, _idx: i }))
      .filter(d => d.category === cat)
    const allSelected = catDocs.every(d => selected.has(d._idx))
    const next = new Set(selected)
    catDocs.forEach(d => allSelected ? next.delete(d._idx) : next.add(d._idx))
    setSelected(next)
  }

  const handleDownload = () => {
    const docs = allDocs.filter((_, i) => selected.has(i))
    onDownload(docs)
  }

  const renderCategory = (title, docs, category) => {
    if (!docs.length) return null
    const catIdx = allDocs.map((d, i) => ({ d, i })).filter(x => x.d.category === category)
    const allSel = catIdx.every(x => selected.has(x.i))
    const CatIcon = CATEGORY_ICONS[category] || FileText
    const catCfg = CATEGORY_COLORS[category] || CATEGORY_COLORS.announcement

    return (
      <div style={{ marginBottom: 16 }}>
        <div style={{
          display: 'flex', alignItems: 'center', gap: 8, marginBottom: 8,
          cursor: 'pointer', userSelect: 'none',
        }} onClick={() => toggleCategory(category)}>
          {allSel
            ? <AnimatedCheckbox checked={true} onChange={() => toggleCategory(category)} size={18} />
            : <AnimatedCheckbox checked={false} onChange={() => toggleCategory(category)} size={18} />
          }
          <CatIcon size={15} style={{ color: catCfg.color }} />
          <span style={{ fontWeight: 600, fontSize: 13 }}>{title}</span>
          <span className="text-xs text-muted doc-picker-count">({docs.length})</span>
        </div>
        <div style={{ display: 'flex', flexDirection: 'column', gap: 4, paddingLeft: 28 }}>
          {docs.map((doc) => {
            const globalIdx = allDocs.indexOf(doc)
            const isSel = selected.has(globalIdx)
            return (
              <div
                key={globalIdx}
                className={`doc-picker-item${isSel ? ' selected' : ''}`}
                style={{
                  display: 'flex', alignItems: 'center', gap: 8, padding: '6px 10px',
                  borderRadius: 6, cursor: 'pointer', fontSize: 13,
                  transition: 'all 0.15s',
                }}
                onClick={() => toggle(globalIdx)}
              >
                <AnimatedCheckbox
                  checked={isSel}
                  onChange={() => toggle(globalIdx)}
                  size={16}
                  style={{ flexShrink: 0 }}
                />
                <span className="doc-picker-title" style={{ flex: 1, lineHeight: 1.3 }}>{doc.title}</span>
                {doc.date && <span className="text-xs text-muted doc-picker-date" style={{ whiteSpace: 'nowrap' }}>{doc.date}</span>}
              </div>
            )
          })}
        </div>
      </div>
    )
  }

  return (
    <div style={{
      position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.7)',
      display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 999
    }}>
      <div className="card doc-picker-panel" style={{ width: 640, maxWidth: '95vw', maxHeight: '80vh', display: 'flex', flexDirection: 'column' }}>
        <div className="flex-between" style={{ marginBottom: 12 }}>
          <div>
            <h3 style={{ fontSize: 16, fontWeight: 700, margin: 0 }}>
              {companyDocs.company_name}
            </h3>
            <p className="text-sm text-muted doc-picker-sub" style={{ margin: '2px 0 0' }}>
              Select documents to download & index · {allDocs.length} available
            </p>
          </div>
          <button className="btn btn-ghost btn-sm" onClick={onClose} style={{ padding: '4px 8px' }}>
            <X size={16} />
          </button>
        </div>

        <div style={{ flex: 1, overflowY: 'auto', marginBottom: 12, paddingRight: 4 }}>
          {allDocs.length === 0 ? (
            <div className="empty-state" style={{ padding: 32 }}>
              <FileText size={36} />
              <p>No downloadable documents found on Screener for this company.</p>
            </div>
          ) : (
            <>
              {renderCategory('Annual Reports', companyDocs.annual_reports || [], 'annual_report')}
              {renderCategory('Concall Transcripts', companyDocs.concalls || [], 'concall')}
              {renderCategory('Credit Ratings', companyDocs.credit_ratings || [], 'credit_rating')}
              {renderCategory('Announcements', companyDocs.announcements || [], 'announcement')}
            </>
          )}
        </div>

        <div style={{ display: 'flex', gap: 10, justifyContent: 'space-between', alignItems: 'center' }}>
          <span className="text-sm text-muted">
            {selected.size} selected
          </span>
          <div className="flex gap-2">
            <button className="btn btn-ghost btn-sm" onClick={onClose}>Cancel</button>
            <button className="btn btn-primary btn-sm" onClick={handleDownload}
              disabled={selected.size === 0 || downloading}>
              {downloading
                ? <><span className="spinner" /> Starting…</>
                : <><Download size={14} /> Download {selected.size > 0 && `(${selected.size})`}</>
              }
            </button>
          </div>
        </div>
      </div>
    </div>
  )
}

/* ─── Main Documents Page ──────────────────────────── */
export default function Documents() {
  const navigate = useNavigate()
  const [docs, setDocs] = useState([])
  const [loading, setLoading] = useState(true)
  const [showUpload, setShowUpload] = useState(false)
  const [filterSymbol, setFilterSymbol] = useState('')
  const [deleteTarget, setDeleteTarget] = useState(null)
  const [deleting, setDeleting] = useState(false)

  // Search state
  const [searchQuery, setSearchQuery] = useState('')
  const [companyResults, setCompanyResults] = useState([])
  const [companyLoading, setCompanyLoading] = useState(false)
  const searchTimerRef = useRef(null)
  const dropdownRef = useRef(null)

  // Document picker state
  const [pickerData, setPickerData] = useState(null)
  const [pickerLoading, setPickerLoading] = useState(false)
  const [downloadStarting, setDownloadStarting] = useState(false)

  // Job status state
  const [activeJob, setActiveJob] = useState(null)
  const pollRef = useRef(null)
  const processPollRef = useRef(null)

  // Load documents
  const loadDocs = useCallback(async () => {
    setLoading(true)
    try {
      const r = await ingestionApi.list(filterSymbol || undefined)
      setDocs(r.data)
    } catch { setDocs([]) }
    finally { setLoading(false) }
  }, [filterSymbol])

  useEffect(() => { loadDocs() }, [loadDocs])

  // Click outside to close dropdown
  useEffect(() => {
    const handleClickOutside = (e) => {
      if (dropdownRef.current && !dropdownRef.current.contains(e.target)) {
        setCompanyResults([])
      }
    }
    document.addEventListener('mousedown', handleClickOutside)
    return () => document.removeEventListener('mousedown', handleClickOutside)
  }, [])

  // Debounced search
  useEffect(() => {
    if (searchTimerRef.current) clearTimeout(searchTimerRef.current)
    if (!searchQuery.trim() || searchQuery.trim().length < 2) {
      setCompanyResults([])
      return
    }
    searchTimerRef.current = setTimeout(async () => {
      setCompanyLoading(true)
      try {
        const r = await scraperApi.searchCompany(searchQuery.trim())
        setCompanyResults(r.data.results ?? [])
      } catch { setCompanyResults([]) }
      finally { setCompanyLoading(false) }
    }, 400)
    return () => clearTimeout(searchTimerRef.current)
  }, [searchQuery])

  // Poll active job
  useEffect(() => {
    if (!activeJob || activeJob.status === 'done' || activeJob.status === 'error') {
      if (pollRef.current) clearInterval(pollRef.current)
      return
    }
    pollRef.current = setInterval(async () => {
      try {
        const r = await scraperApi.jobStatus(activeJob.job_id)
        setActiveJob(r.data)
        if (r.data.status === 'done' || r.data.status === 'error') {
          clearInterval(pollRef.current)
          loadDocs()
        }
      } catch { /* ignore */ }
    }, 2000)
    return () => clearInterval(pollRef.current)
  }, [activeJob?.job_id, activeJob?.status, loadDocs])

  // Open document picker for a company
  const openPicker = async (company) => {
    setCompanyResults([])
    setSearchQuery(company.name || company.symbol)
    setPickerLoading(true)
    try {
      const r = await scraperApi.companyDocuments(company.symbol)
      setPickerData(r.data)
    } catch {
      setPickerData(null)
    } finally { setPickerLoading(false) }
  }

  // Download selected documents
  const handleDownloadSelected = async (selectedDocs) => {
    if (!pickerData || !selectedDocs.length) return
    setDownloadStarting(true)
    try {
      const r = await scraperApi.downloadSelected(
        pickerData.symbol,
        pickerData.company_name,
        selectedDocs
      )
      setActiveJob({ ...r.data, company_name: pickerData.company_name })
      setPickerData(null)
    } catch (err) {
      setActiveJob({
        status: 'error',
        error: err.response?.data?.detail ?? 'Failed to start download',
        company_name: pickerData?.company_name,
      })
    } finally { setDownloadStarting(false) }
  }

  // Direct search on Enter
  const handleSearchSubmit = async () => {
    if (!searchQuery.trim()) return
    setCompanyLoading(true)
    try {
      const r = await scraperApi.searchCompany(searchQuery.trim())
      const results = r.data.results ?? []
      if (results.length === 1) {
        openPicker(results[0])
      } else {
        setCompanyResults(results)
      }
    } catch { setCompanyResults([]) }
    finally { setCompanyLoading(false) }
  }

  // Delete
  const handleDelete = async () => {
    if (!deleteTarget) return
    setDeleting(true)
    try {
      await ingestionApi.delete(deleteTarget.id)
      setDocs(prev => prev.filter(d => d.id !== deleteTarget.id))
      setDeleteTarget(null)
    } catch { /* keep modal open */ }
    finally { setDeleting(false) }
  }

  // Process polling
  const startProcessPolling = () => {
    if (processPollRef.current) return
    processPollRef.current = setInterval(async () => {
      try {
        const r = await ingestionApi.list(filterSymbol || undefined)
        setDocs(r.data)
        const anyProcessing = r.data.some(d =>
          d.status === 'processing' || d.cs_status === 'processing'
        )
        if (!anyProcessing) {
          clearInterval(processPollRef.current)
          processPollRef.current = null
        }
      } catch { /* ignore */ }
    }, 2000)
  }

  useEffect(() => {
    return () => {
      if (processPollRef.current) clearInterval(processPollRef.current)
    }
  }, [])

  // Process handlers
  const handleProcessRAG = async (docId) => {
    try {
      await ingestionApi.process(docId)
      startProcessPolling()
    } catch { /* ignore */ }
  }

  const handleProcessCS = async (docId) => {
    try {
      await credisentimentApi.process(docId)
      startProcessPolling()
    } catch { /* ignore */ }
  }

  const jobStatusLabel = (job) => {
    if (!job) return null
    const s = job.status
    if (s === 'queued') return 'Queued…'
    if (s === 'downloading') return `Downloading ${job.progress || 0}/${job.total || '?'}…`
    if (s === 'processing') return `Processing documents…`
    if (s === 'done') return `✓ Done — ${job.documents?.filter(d => d.status === 'indexed').length || 0} documents indexed`
    if (s === 'error') return `✗ Error: ${job.error || 'Unknown'}`
    return s
  }

  return (
    <div className="documents-page">
      {/* Header */}
      <div className="flex-between mb-6">
        <div className="page-header" style={{ marginBottom: 0 }}>
          <h1 className="page-title">Documents</h1>
          <p className="page-sub">Search companies on Screener.in, pick documents, and build your library</p>
        </div>
        <div className="flex gap-2">
          <button className="btn btn-ghost btn-sm flex-center gap-2" onClick={loadDocs}>
            <RefreshCw size={14} />
          </button>
          <button className="btn btn-primary btn-sm" onClick={() => setShowUpload(true)}>
            <Upload size={14} /> Upload PDF
          </button>
        </div>
      </div>

      {/* ── Search Bar ──────────────────────────────── */}
      <GlowCard className="card mb-6" style={{ position: 'relative', zIndex: 10 }}>
        <h3 style={{ fontSize: 14, fontWeight: 600, marginBottom: 12 }}>
          <Search size={15} style={{ display: 'inline', verticalAlign: -2, marginRight: 6 }} />
          Search & Download Reports
        </h3>
        <div style={{ display: 'flex', gap: 10, alignItems: 'center' }}>
          <div style={{ flex: 1, position: 'relative' }}>
            <input
              className="form-control"
              style={{ marginBottom: 0, paddingRight: 40 }}
              placeholder="Search any company… e.g. Tata Motors, Infosys, HDFC Bank"
              value={searchQuery}
              onChange={e => setSearchQuery(e.target.value)}
              onKeyDown={e => e.key === 'Enter' && handleSearchSubmit()}
            />
            {(companyLoading || pickerLoading) && (
              <span className="spinner" style={{
                position: 'absolute', right: 12, top: '50%', transform: 'translateY(-50%)',
                width: 16, height: 16, borderWidth: 2,
              }} />
            )}
          </div>
          <button className="btn btn-primary btn-sm flex-center gap-2"
            onClick={handleSearchSubmit}
            disabled={!searchQuery.trim() || companyLoading}>
            <Search size={14} /> Search
          </button>
        </div>

        {/* Company Dropdown */}
        {companyResults.length > 0 && (
          <div ref={dropdownRef} style={{
            position: 'absolute', left: 16, right: 16, top: '100%', zIndex: 50,
            background: 'var(--popover-bg)', border: '1px solid var(--glass-border)',
            borderRadius: 10, boxShadow: 'var(--popover-shadow)',
            maxHeight: 300, overflowY: 'auto', marginTop: 4,
          }}>
            {companyResults.map((c, i) => (
              <button key={i}
                style={{
                  display: 'flex', width: '100%', padding: '10px 16px',
                  alignItems: 'center', justifyContent: 'space-between',
                  background: 'none', border: 'none', borderBottom: '1px solid var(--glass-border)',
                  cursor: 'pointer', color: 'var(--text-primary)', textAlign: 'left',
                  transition: 'background 0.15s',
                }}
                onMouseEnter={e => e.currentTarget.style.background = 'var(--glass-hover)'}
                onMouseLeave={e => e.currentTarget.style.background = 'none'}
                onClick={() => openPicker(c)}
              >
                <div>
                  <div style={{ fontWeight: 600, fontSize: 13 }}>{c.name}</div>
                  <div style={{ fontSize: 11, color: 'var(--text-muted)' }}>{c.symbol}</div>
                </div>
                <div className="flex-center gap-1" style={{ color: 'var(--primary)', fontSize: 12, fontWeight: 600 }}>
                  <ChevronRight size={14} /> View Docs
                </div>
              </button>
            ))}
          </div>
        )}

        {/* Active Job Status */}
        {activeJob && (
          <div style={{
            marginTop: 12, padding: '10px 14px', borderRadius: 8,
            background: activeJob.status === 'done' ? 'rgba(34,211,165,0.08)'
              : activeJob.status === 'error' ? 'rgba(244,63,94,0.08)'
                : 'rgba(56,189,248,0.08)',
            display: 'flex', alignItems: 'center', gap: 10,
          }}>
            {activeJob.status !== 'done' && activeJob.status !== 'error' && (
              <span className="spinner" style={{ width: 16, height: 16, borderWidth: 2 }} />
            )}
            {activeJob.status === 'done' && <CheckCircle size={16} style={{ color: 'var(--success)' }} />}
            {activeJob.status === 'error' && <AlertCircle size={16} style={{ color: 'var(--danger)' }} />}
            <div style={{ flex: 1 }}>
              <div style={{ fontSize: 13, fontWeight: 600 }}>{activeJob.company_name || 'Company'}</div>
              <div style={{ fontSize: 12, color: 'var(--text-muted)' }}>{jobStatusLabel(activeJob)}</div>
            </div>
            {activeJob.status === 'done' && (
              <button className="btn btn-ghost btn-sm" onClick={() => setActiveJob(null)} style={{ padding: '2px 6px' }}>
                <X size={14} />
              </button>
            )}
          </div>
        )}
      </GlowCard>

      {/* ── Library Section ─────────────────────────── */}
      <GlowCard className="card mb-6" style={{ display: 'flex', gap: 12, alignItems: 'center' }}>
        <FileText size={15} style={{ color: 'var(--text-muted)' }} />
        <span style={{ fontWeight: 600, fontSize: 14 }}>Document Library</span>
        <div style={{ flex: 1 }} />
        <input className="form-control" style={{ maxWidth: 200, marginBottom: 0, fontSize: 13 }}
          placeholder="Filter by symbol…" value={filterSymbol}
          onChange={e => setFilterSymbol(e.target.value)} />
        <span className="text-sm text-muted">{docs.length} doc{docs.length !== 1 ? 's' : ''}</span>
      </GlowCard>

      {loading ? (
        <div className="empty-state"><span className="spinner" style={{ width: 36, height: 36, borderWidth: 3 }} /></div>
      ) : docs.length === 0 ? (
        <div className="empty-state card">
          <FileText size={48} />
          <p>No documents yet.<br />Search for a company above or upload a PDF.</p>
        </div>
      ) : (
        <div className="table-wrap card" style={{ padding: 0 }}>
          <table>
            <thead>
              <tr>
                <th>Company / Symbol</th>
                <th>Type</th>
                <th>Period</th>
                <th>RAG Status</th>
                <th>CS Status</th>
                <th>Date</th>
                <th>Size</th>
                <th style={{ textAlign: 'right' }}>Actions</th>
              </tr>
            </thead>
            <tbody>
              {docs.map(doc => (
                <tr key={doc.id}>
                  <td>
                    <div>
                      {doc.company_name && (
                        <div style={{ fontSize: 13, fontWeight: 600, lineHeight: 1.3 }}>
                          {doc.company_name}
                        </div>
                      )}
                      <span className="badge badge-accent">{doc.symbol}</span>
                    </div>
                  </td>
                  <td><CategoryBadge category={doc.doc_type} /></td>
                  <td className="text-sm">
                    {[doc.fiscal_quarter, doc.fiscal_year].filter(Boolean).join(' / ') || '—'}
                  </td>
                  <td><PipelineStatusBadge status={doc.status || 'pending'} label="RAG" /></td>
                  <td><PipelineStatusBadge status={doc.cs_status || 'pending'} label="CS" /></td>
                  <td className="text-sm text-muted" style={{ whiteSpace: 'nowrap' }}>
                    {doc.ingested_at ? new Date(doc.ingested_at).toLocaleDateString() : '—'}
                  </td>
                  <td className="text-sm text-muted">{formatSize(doc.file_size)}</td>
                  <td>
                    <div className="doc-actions">
                      {doc.pdf_path && (
                        <button className="doc-action-btn" title="View PDF"
                          onClick={async () => {
                            try {
                              const resp = await ingestionApi.getPdf(doc.id)
                              const blob = new Blob([resp.data], { type: 'application/pdf' })
                              window.open(URL.createObjectURL(blob), '_blank')
                            } catch { alert('Failed to load PDF') }
                          }}>
                          <Eye size={14} />
                        </button>
                      )}
                      {doc.status === 'indexed' && (
                        <button className="doc-action-btn" title="Chat with RAG"
                          onClick={() => navigate(`/chat?symbol=${doc.symbol}`)}>
                          <MessageSquare size={14} />
                        </button>
                      )}
                      <ProcessButton
                        status={doc.status || 'pending'}
                        onClick={() => handleProcessRAG(doc.id)}
                        label="RAG"
                      />
                      <ProcessButton
                        status={doc.cs_status || 'pending'}
                        onClick={() => handleProcessCS(doc.id)}
                        label="CrediSentiment"
                      />
                      <button className="doc-action-btn danger" title="Delete"
                        onClick={() => setDeleteTarget(doc)}>
                        <Trash2 size={14} />
                      </button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {/* Modals */}
      {showUpload && <UploadModal onClose={() => setShowUpload(false)} onUploaded={() => { setShowUpload(false); loadDocs() }} />}
      {deleteTarget && <DeleteConfirm doc={deleteTarget} deleting={deleting} onCancel={() => setDeleteTarget(null)} onConfirm={handleDelete} />}
      {pickerData && (
        <DocumentPicker
          companyDocs={pickerData}
          onDownload={handleDownloadSelected}
          onClose={() => setPickerData(null)}
          downloading={downloadStarting}
        />
      )}
    </div>
  )
}
