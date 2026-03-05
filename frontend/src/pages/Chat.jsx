import { useState, useRef, useEffect } from 'react'
import { ragApi } from '../api/client'
import {
  Send, Bot, Sparkles, FileText, CheckCircle, Loader,
  ChevronDown, ChevronRight, Navigation, Brain, AlertCircle,
} from 'lucide-react'

const MODELS = [
  { value: 'deepseek-r1:14b', label: 'DeepSeek-R1 14B (Reasoning)' },
  { value: 'llama3.1:8b-instruct-q8_0', label: 'Llama 3.1 8B (Fast)' },
]

const WELCOME = {
  id: 'welcome',
  role: 'ai',
  text: "Hi! I'm FinSight AI. Select documents from the left panel, prepare them, and ask me anything about earnings, revenue, debt, management guidance, and more.",
  sources: [],
  navigations: [],
  thinking: null,
}

export default function Chat() {
  const [messages, setMessages] = useState([WELCOME])
  const [input, setInput] = useState('')
  const [loading, setLoading] = useState(false)
  const [statusText, setStatusText] = useState('')
  const bottomRef = useRef(null)

  // Document picker
  const [documents, setDocuments] = useState([])
  const [selectedIds, setSelectedIds] = useState(new Set())
  const [preparing, setPreparing] = useState(false)
  const [docsLoading, setDocsLoading] = useState(true)

  // Model selection
  const [model, setModel] = useState(MODELS[0].value)

  // Load available documents on mount
  useEffect(() => {
    loadDocuments()
  }, [])

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  const loadDocuments = async () => {
    setDocsLoading(true)
    try {
      const r = await ragApi.availableDocuments()
      setDocuments(r.data)
    } catch {
      setDocuments([])
    } finally {
      setDocsLoading(false)
    }
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
    if (selectedIds.size === documents.length) {
      setSelectedIds(new Set())
    } else {
      setSelectedIds(new Set(documents.map(d => d.id)))
    }
  }

  const prepareSelected = async () => {
    const ids = [...selectedIds]
    const needsProcessing = ids.filter(id => {
      const doc = documents.find(d => d.id === id)
      return doc && doc.status !== 'indexed'
    })
    if (needsProcessing.length === 0) {
      setStatusText('All selected documents are already indexed.')
      setTimeout(() => setStatusText(''), 3000)
      return
    }
    setPreparing(true)
    setStatusText(`Processing ${needsProcessing.length} document(s)...`)
    try {
      const r = await ragApi.prepare(needsProcessing)
      const results = r.data.results || []
      const indexed = results.filter(r => r.status === 'indexed' || r.status === 'already_indexed').length
      setStatusText(`Done! ${indexed} document(s) ready for analysis.`)
      await loadDocuments() // refresh statuses
    } catch (err) {
      setStatusText(`Error: ${err.response?.data?.detail || 'Processing failed'}`)
    } finally {
      setPreparing(false)
      setTimeout(() => setStatusText(''), 5000)
    }
  }

  const send = async () => {
    const q = input.trim()
    if (!q || loading) return

    const docIds = [...selectedIds].filter(id => {
      const doc = documents.find(d => d.id === id)
      return doc && doc.status === 'indexed'
    })

    if (docIds.length === 0) {
      setMessages(prev => [...prev, {
        id: Date.now(),
        role: 'ai',
        text: 'Please select and prepare at least one document before asking questions.',
        sources: [], navigations: [], thinking: null,
      }])
      return
    }

    setInput('')
    setMessages(prev => [...prev, { id: Date.now(), role: 'user', text: q, sources: [], navigations: [], thinking: null }])
    setLoading(true)
    setStatusText('Searching documents...')

    try {
      setStatusText('Analyzing with AI...')
      const r = await ragApi.query(q, docIds, model)
      setMessages(prev => [...prev, {
        id: Date.now() + 1,
        role: 'ai',
        text: r.data.answer,
        sources: r.data.sources ?? [],
        navigations: r.data.navigations ?? [],
        thinking: r.data.thinking ?? null,
        modelUsed: r.data.model_used ?? '',
      }])
      setStatusText('')
    } catch (err) {
      setMessages(prev => [...prev, {
        id: Date.now() + 1,
        role: 'ai',
        text: `Error: ${err.response?.data?.detail ?? 'Failed to get answer. Is Ollama running?'}`,
        sources: [], navigations: [], thinking: null,
      }])
      setStatusText('')
    } finally { setLoading(false) }
  }

  const onKey = (e) => { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); send() } }

  const indexedCount = [...selectedIds].filter(id => {
    const doc = documents.find(d => d.id === id)
    return doc && doc.status === 'indexed'
  }).length

  const pendingCount = selectedIds.size - indexedCount

  return (
    <div>
      <div className="page-header">
        <h1 className="page-title" style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
          <Sparkles size={24} color="#6366f1" /> RAG Analysis
        </h1>
        <p className="page-sub">Select documents, prepare them for analysis, then ask questions</p>
      </div>

      <div style={{ display: 'flex', gap: 16, height: 'calc(100vh - 220px)', minHeight: 500 }}>
        {/* Left panel — Document picker */}
        <div className="card" style={{ width: 280, minWidth: 280, display: 'flex', flexDirection: 'column', padding: 0, overflow: 'hidden' }}>
          <div style={{ padding: '14px 16px 10px', borderBottom: '1px solid var(--border)' }}>
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 8 }}>
              <span style={{ fontWeight: 600, fontSize: 14 }}>
                <FileText size={14} style={{ marginRight: 6, verticalAlign: -2 }} />
                Documents
              </span>
              <button
                className="btn btn-sm"
                onClick={selectAll}
                style={{ fontSize: 11, padding: '2px 8px' }}
              >
                {selectedIds.size === documents.length ? 'None' : 'All'}
              </button>
            </div>

            {/* Model selector */}
            <select
              className="form-control"
              value={model}
              onChange={e => setModel(e.target.value)}
              style={{ fontSize: 12, padding: '4px 8px', marginBottom: 0 }}
            >
              {MODELS.map(m => (
                <option key={m.value} value={m.value}>{m.label}</option>
              ))}
            </select>
          </div>

          {/* Document list */}
          <div style={{ flex: 1, overflowY: 'auto', padding: '8px 0' }}>
            {docsLoading ? (
              <div style={{ textAlign: 'center', padding: 20, color: 'var(--text-muted)' }}>
                <Loader size={16} className="spin" /> Loading...
              </div>
            ) : documents.length === 0 ? (
              <div style={{ textAlign: 'center', padding: 20, color: 'var(--text-muted)', fontSize: 13 }}>
                No documents found. Download some in the Documents tab first.
              </div>
            ) : (
              documents.map(doc => (
                <label
                  key={doc.id}
                  style={{
                    display: 'flex', alignItems: 'flex-start', gap: 8,
                    padding: '8px 16px', cursor: 'pointer',
                    background: selectedIds.has(doc.id) ? 'var(--bg-hover, rgba(99,102,241,0.08))' : 'transparent',
                    borderLeft: selectedIds.has(doc.id) ? '3px solid #6366f1' : '3px solid transparent',
                  }}
                >
                  <input
                    type="checkbox"
                    checked={selectedIds.has(doc.id)}
                    onChange={() => toggleDoc(doc.id)}
                    style={{ marginTop: 3 }}
                  />
                  <div style={{ flex: 1, minWidth: 0 }}>
                    <div style={{ fontWeight: 500, fontSize: 13, lineHeight: 1.3 }}>
                      {doc.symbol}
                    </div>
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

          {/* Prepare button */}
          <div style={{ padding: '10px 16px', borderTop: '1px solid var(--border)' }}>
            {statusText && (
              <div style={{ fontSize: 11, color: '#6366f1', marginBottom: 6, lineHeight: 1.4 }}>
                {preparing && <Loader size={10} className="spin" style={{ marginRight: 4, verticalAlign: -1 }} />}
                {statusText}
              </div>
            )}
            <button
              className="btn btn-primary"
              onClick={prepareSelected}
              disabled={selectedIds.size === 0 || preparing}
              style={{ width: '100%', fontSize: 13 }}
            >
              {preparing ? 'Processing...' : `Prepare Selected (${selectedIds.size})`}
            </button>
            {selectedIds.size > 0 && (
              <div style={{ fontSize: 11, color: 'var(--text-muted)', marginTop: 4, textAlign: 'center' }}>
                {indexedCount} ready{pendingCount > 0 ? ` · ${pendingCount} need processing` : ''}
              </div>
            )}
          </div>
        </div>

        {/* Right panel — Chat */}
        <div style={{ flex: 1, display: 'flex', flexDirection: 'column', minWidth: 0 }}>
          <div className="card" style={{ flex: 1, display: 'flex', flexDirection: 'column', padding: 0, overflow: 'hidden' }}>
            {/* Messages */}
            <div style={{ flex: 1, overflowY: 'auto', padding: 16 }}>
              {messages.map(msg => (
                <div key={msg.id} className={`chat-msg ${msg.role}`}>
                  <div className={`chat-avatar ${msg.role}`}>
                    {msg.role === 'ai' ? <Bot size={16} /> : 'U'}
                  </div>
                  <div style={{ flex: 1, minWidth: 0 }}>
                    <div className="chat-bubble">{msg.text}</div>

                    {/* Navigation breadcrumbs */}
                    {msg.navigations?.length > 0 && (
                      <NavigationTrail navigations={msg.navigations} />
                    )}

                    {/* Thinking panel (DeepSeek-R1) */}
                    {msg.thinking && (
                      <ThinkingPanel thinking={msg.thinking} />
                    )}

                    {/* Source chips */}
                    {msg.sources?.length > 0 && (
                      <div className="chat-sources">
                        {msg.sources.slice(0, 6).map((s, i) => (
                          <span key={i} className="source-chip">
                            [{i+1}] {s.symbol} · {s.doc_type?.replace(/_/g,' ')}
                            {s.page_number ? ` · p.${s.page_number}` : ''}
                            {s.fiscal_year ? ` · ${s.fiscal_year}` : ''}
                          </span>
                        ))}
                      </div>
                    )}
                  </div>
                </div>
              ))}
              {loading && (
                <div className="chat-msg ai">
                  <div className="chat-avatar ai"><Bot size={16} /></div>
                  <div className="chat-bubble" style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                    <span className="spinner" />
                    {statusText || 'Thinking...'}
                  </div>
                </div>
              )}
              <div ref={bottomRef} />
            </div>

            {/* Input */}
            <div style={{ padding: '12px 16px', borderTop: '1px solid var(--border)', display: 'flex', gap: 10 }}>
              <input
                className="form-control"
                placeholder="Ask about your financial documents... (Enter to send)"
                value={input}
                onChange={e => setInput(e.target.value)}
                onKeyDown={onKey}
                disabled={loading}
                style={{ marginBottom: 0 }}
              />
              <button
                className="btn btn-primary"
                onClick={send}
                disabled={loading || !input.trim()}
                style={{ flexShrink: 0 }}
              >
                <Send size={16} />
              </button>
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}


/* ── Sub-components ──────────────────────────────────── */

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


function NavigationTrail({ navigations }) {
  if (!navigations || navigations.length === 0) return null
  return (
    <div style={{
      margin: '8px 0', padding: '8px 12px', borderRadius: 8,
      background: 'rgba(99,102,241,0.06)', border: '1px solid rgba(99,102,241,0.15)',
      fontSize: 12,
    }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 4, fontWeight: 600, color: '#6366f1', marginBottom: 4 }}>
        <Navigation size={12} /> Navigated to:
      </div>
      {navigations.map((nav, i) => (
        <div key={i} style={{ display: 'flex', alignItems: 'center', gap: 4, color: 'var(--text-secondary)', paddingLeft: 8, lineHeight: 1.6 }}>
          <ChevronRight size={10} style={{ flexShrink: 0 }} />
          {nav.section && <span>{nav.section}</span>}
          {nav.sub_section && <><span style={{ color: 'var(--text-muted)' }}>&gt;</span> <span>{nav.sub_section}</span></>}
          {nav.page_number > 0 && <><span style={{ color: 'var(--text-muted)' }}>&gt;</span> <span style={{ fontWeight: 500 }}>Page {nav.page_number}</span></>}
        </div>
      ))}
    </div>
  )
}


function ThinkingPanel({ thinking }) {
  const [open, setOpen] = useState(false)
  if (!thinking) return null
  return (
    <div style={{
      margin: '6px 0', borderRadius: 8,
      background: 'rgba(234,179,8,0.06)', border: '1px solid rgba(234,179,8,0.2)',
      fontSize: 12, overflow: 'hidden',
    }}>
      <button
        onClick={() => setOpen(!open)}
        style={{
          display: 'flex', alignItems: 'center', gap: 6, width: '100%',
          padding: '8px 12px', background: 'none', border: 'none',
          cursor: 'pointer', color: '#a16207', fontWeight: 500, fontSize: 12,
        }}
      >
        <Brain size={12} />
        AI Reasoning
        {open ? <ChevronDown size={12} /> : <ChevronRight size={12} />}
      </button>
      {open && (
        <div style={{
          padding: '0 12px 10px', color: 'var(--text-secondary)',
          whiteSpace: 'pre-wrap', lineHeight: 1.5, maxHeight: 200, overflowY: 'auto',
        }}>
          {thinking}
        </div>
      )}
    </div>
  )
}
