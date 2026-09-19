import { useState, useRef, useEffect, useMemo } from 'react'
import { ragApi, llmApi } from '../api/client'
import {
  Send, Bot, FileText, CheckCircle, Loader,
  ChevronDown, ChevronRight, Navigation, Brain, AlertCircle, Trash2,
  TrendingUp, BarChart2, FileSearch, Scale, Sparkles,
} from 'lucide-react'
import { FinSightLogo } from '../components/FinSightLogo'
import GlowCard from '../components/GlowCard'
import AnimatedCheckbox from '../components/AnimatedCheckbox'
import { useAuth } from '../context/AuthContext'
import TextGenerateEffect from '../components/TextGenerateEffect'

// Shown until /llm/models answers; the backend picks the real default.
const FALLBACK_MODELS = [{ value: '', label: 'Default model' }]

const PROMPT_CHIPS = [
  { icon: FileSearch, label: 'Summarize', prompt: 'Give me a concise summary of the selected documents.' },
  { icon: TrendingUp, label: 'Revenue Trends', prompt: 'What are the revenue trends across the selected documents?' },
  { icon: BarChart2, label: 'Key Metrics', prompt: 'What are the key financial metrics and KPIs from these filings?' },
  { icon: Scale, label: 'Risk Factors', prompt: 'What are the main risk factors mentioned in these documents?' },
  { icon: Sparkles, label: 'Management Guidance', prompt: 'What guidance did management provide for the upcoming period?' },
]

function getGreeting() {
  const h = new Date().getHours()
  if (h < 12) return 'Good morning'
  if (h < 17) return 'Good afternoon'
  return 'Good evening'
}

const STORAGE_KEY = 'finsight_chat_v3'

export default function Chat() {
  const { user } = useAuth()
  const username = user?.first_name?.trim() || user?.email?.split('@')[0] || 'there'
  const [logoTheme, setLogoTheme] = useState(() => (
    typeof document !== 'undefined' && document.documentElement.getAttribute('data-theme') === 'light'
      ? 'light'
      : 'dark'
  ))
  const [messages, setMessages] = useState(() => {
    try {
      const saved = sessionStorage.getItem(STORAGE_KEY)
      if (saved) return JSON.parse(saved)
    } catch {}
    return []
  })
  const [input, setInput] = useState('')
  const [loading, setLoading] = useState(false)
  const [statusText, setStatusText] = useState('')
  const bottomRef = useRef(null)

  // Document picker
  const [documents, setDocuments] = useState([])
  const [selectedIds, setSelectedIds] = useState(new Set())
  const [preparing, setPreparing] = useState(false)
  const [docsLoading, setDocsLoading] = useState(true)

  // Model selection — list comes from the active provider (Groq or Ollama)
  const [models, setModels] = useState(FALLBACK_MODELS)
  const [model, setModel] = useState('')
  const [provider, setProvider] = useState(null)

  // Load available documents + models on mount
  useEffect(() => {
    loadDocuments()
    llmApi.models()
      .then(r => {
        const list = (r.data.models || []).map(m => ({ value: m.id, label: m.label }))
        if (list.length) {
          setModels(list)
          setModel(r.data.default_model || list[0].value)
        }
        setProvider(r.data.provider)
      })
      .catch(() => {})
  }, [])

  useEffect(() => {
    if (typeof document === 'undefined') return
    const root = document.documentElement
    const updateTheme = () => {
      setLogoTheme(root.getAttribute('data-theme') === 'light' ? 'light' : 'dark')
    }
    updateTheme()
    const observer = new MutationObserver(updateTheme)
    observer.observe(root, { attributes: true, attributeFilter: ['data-theme'] })
    return () => observer.disconnect()
  }, [])

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
    sessionStorage.setItem(STORAGE_KEY, JSON.stringify(messages))
  }, [messages])

  const clearChat = () => {
    setMessages([])
    sessionStorage.removeItem(STORAGE_KEY)
  }

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
      const r = await ragApi.query(q, docIds, model || undefined)
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
        text: `Error: ${err.response?.data?.detail ?? 'Failed to get answer. Is the LLM provider configured?'}`,
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
          <FinSightLogo size="small" variant="icon" theme={logoTheme} animated={false} />
          RAG Analysis
        </h1>
        <p className="page-sub">Select documents, prepare them for analysis, then ask questions</p>
      </div>

      <div style={{ display: 'flex', gap: 16, height: 'calc(100vh - 220px)', minHeight: 500 }}>
        {/* Left panel — Document picker */}
        <GlowCard className="card" style={{ width: 280, minWidth: 280, display: 'flex', flexDirection: 'column', padding: 0, overflow: 'hidden' }}>
          <div style={{ padding: '14px 16px 10px', borderBottom: '1px solid var(--border)' }}>
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 8 }}>
              <span style={{ fontWeight: 600, fontSize: 14 }}>
                <FileText size={14} style={{ marginRight: 6, verticalAlign: -2 }} />
                Documents
              </span>
              <button
                className="btn btn-ghost btn-sm"
                onClick={selectAll}
                style={{ fontSize: 11, padding: '2px 8px' }}
              >
                {selectedIds.size === documents.length ? 'None' : 'All'}
              </button>
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
                No documents found. Download some in the Documents tab first.
              </div>
            ) : (
              documents.map(doc => (
                <label
                  key={doc.id}
                  onClick={() => toggleDoc(doc.id)}
                  style={{
                    display: 'flex', alignItems: 'flex-start', gap: 8,
                    padding: '8px 16px', cursor: 'pointer',
                    background: selectedIds.has(doc.id) ? 'var(--bg-hover, rgba(99,102,241,0.08))' : 'transparent',
                    borderLeft: selectedIds.has(doc.id) ? '3px solid #6366f1' : '3px solid transparent',
                  }}
                >
                  <AnimatedCheckbox
                    checked={selectedIds.has(doc.id)}
                    onChange={() => toggleDoc(doc.id)}
                    size={20}
                    style={{ marginTop: 2 }}
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
            {preparing ? (
              <button className="btn btn-primary" disabled style={{ width: '100%', fontSize: 13 }}>
                <Loader size={13} className="spin" /> Processing...
              </button>
            ) : (
              <button
                className="btn btn-primary"
                onClick={prepareSelected}
                disabled={selectedIds.size === 0}
                style={{ width: '100%', fontSize: 13 }}
              >
                Prepare ({selectedIds.size})
              </button>
            )}
            {selectedIds.size > 0 && (
              <div style={{ fontSize: 11, color: 'var(--text-muted)', marginTop: 4, textAlign: 'center' }}>
                {indexedCount} ready{pendingCount > 0 ? ` · ${pendingCount} need processing` : ''}
              </div>
            )}
          </div>
        </GlowCard>

        {/* Right panel — Chat */}
        <div style={{ flex: 1, display: 'flex', flexDirection: 'column', minWidth: 0 }}>
          <GlowCard className="card" style={{ flex: 1, display: 'flex', flexDirection: 'column', padding: 0, overflow: 'hidden' }}>

            {messages.length === 0 ? (
              /* ── Empty state ── */
              <div className="chat-empty-state">
                <FinSightLogo size="large" theme={logoTheme} animated />
                <h2 className="chat-greeting">
                  {getGreeting()},&nbsp;
                  <span className="chat-greeting-name">{username}</span>
                </h2>
                <p className="chat-greeting-sub">Select documents on the left, then ask me anything about your filings.</p>

                {/* Input */}
                <div className="chat-empty-input-wrap">
                  <input
                    className="form-control chat-empty-input"
                    placeholder="Ask about your financial documents..."
                    value={input}
                    onChange={e => setInput(e.target.value)}
                    onKeyDown={onKey}
                    disabled={loading}
                    autoFocus
                  />
                  <button
                    className="btn btn-primary chat-empty-send"
                    onClick={send}
                    disabled={loading || !input.trim()}
                  >
                    <Send size={16} />
                  </button>
                </div>

                {/* Model selector in empty state */}
                <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                  <span style={{ fontSize: 12, color: 'var(--text-muted)', fontWeight: 500 }}>Model:</span>
                  <select
                    value={model}
                    onChange={e => setModel(e.target.value)}
                    style={{
                      background: 'var(--bg-card)', border: '1px solid var(--border)',
                      borderRadius: 8, color: 'var(--text-secondary)', fontSize: 12,
                      padding: '4px 10px', cursor: 'pointer', outline: 'none',
                    }}
                  >
                    {models.map(m => <option key={m.value} value={m.value}>{m.label}</option>)}
                  </select>
                </div>

                {/* Prompt chips */}
                <div className="chat-prompt-chips">
                  {PROMPT_CHIPS.map(({ icon: Icon, label, prompt }) => (
                    <button
                      key={label}
                      className="chat-prompt-chip"
                      onClick={() => setInput(prompt)}
                    >
                      <Icon size={13} />
                      {label}
                    </button>
                  ))}
                </div>
              </div>
            ) : (
              /* ── Active chat view ── */
              <>
                {/* Clear Chat header */}
                <div style={{ display: 'flex', justifyContent: 'flex-end', padding: '8px 16px 0' }}>
                  <button
                    onClick={clearChat}
                    className="btn btn-sm"
                    style={{ fontSize: 11, padding: '3px 10px', display: 'flex', alignItems: 'center', gap: 4, color: '#991b1b' }}
                  >
                    <Trash2 size={12} /> Clear Chat
                  </button>
                </div>

                {/* Messages — Claude-style */}
                <div className="chat-thread">
                  {messages.map((msg, idx) => {
                    // Only animate the very last AI message
                    const isLatestAI =
                      msg.role === 'ai' &&
                      idx === [...messages].map(m => m.role).lastIndexOf('ai')

                    return (
                    <div key={msg.id} className={`chat-turn ${msg.role}`}>

                      {msg.role === 'user' ? (
                        /* User: right-aligned pill bubble */
                        <>
                          <div className="chat-user-header">
                            <span className="chat-user-label">You</span>
                            <div className="chat-user-avatar">{username[0]?.toUpperCase() ?? 'U'}</div>
                          </div>
                          <div className="chat-user-bubble">{msg.text}</div>
                        </>
                      ) : (
                        /* AI: left-aligned, word-by-word fade for latest */
                        <>
                          <div className="chat-ai-header">
                            <div className="chat-ai-avatar">
                              <svg width="14" height="14" viewBox="0 0 120 120" fill="none">
                                <ellipse cx="60" cy="60" rx="52" ry="32" stroke="#fff" strokeWidth="9" fill="none"/>
                                <circle cx="60" cy="60" r="16" fill="#1ABC9C"/>
                                <circle cx="60" cy="60" r="8" fill="#fff"/>
                              </svg>
                            </div>
                            <span className="chat-ai-label">FinSight AI</span>
                          </div>
                          <div className="chat-ai-body">
                            <TextGenerateEffect
                              text={msg.text}
                              animate={isLatestAI}
                              duration={0.35}
                              staggerDelay={0.04}
                            />
                          </div>
                          {msg.navigations?.length > 0 && (
                            <div style={{ paddingLeft: 38 }}><NavigationTrail navigations={msg.navigations} /></div>
                          )}
                          {msg.thinking && (
                            <div style={{ paddingLeft: 38 }}><ThinkingPanel thinking={msg.thinking} /></div>
                          )}
                          {msg.sources?.length > 0 && (
                            <div className="chat-sources-row">
                              {msg.sources.slice(0, 6).map((s, i) => (
                                <span key={i} className="source-chip">
                                  [{i+1}] {s.symbol} · {s.doc_type?.replace(/_/g,' ')}
                                  {s.page_number ? ` · p.${s.page_number}` : ''}
                                  {s.fiscal_year ? ` · ${s.fiscal_year}` : ''}
                                </span>
                              ))}
                            </div>
                          )}
                        </>
                      )}

                    </div>
                  )})
                  }
                  {loading && (
                    <div className="chat-turn ai">
                      <div className="chat-ai-header">
                        <div className="chat-ai-avatar">
                          <svg width="14" height="14" viewBox="0 0 120 120" fill="none">
                            <ellipse cx="60" cy="60" rx="52" ry="32" stroke="#fff" strokeWidth="9" fill="none"/>
                            <circle cx="60" cy="60" r="16" fill="#1ABC9C"/>
                            <circle cx="60" cy="60" r="8" fill="#fff"/>
                          </svg>
                        </div>
                        <span className="chat-ai-label">FinSight AI</span>
                      </div>
                      <div className="chat-ai-body" style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                        <span className="spinner" style={{ flexShrink: 0 }} />
                        <span style={{ color: 'var(--text-muted)', fontSize: 13 }}>{statusText || 'Thinking...'}</span>
                      </div>
                    </div>
                  )}
                  <div ref={bottomRef} />
                </div>

                {/* Input bar with model selector */}
                <div style={{ padding: '10px 16px 12px', borderTop: '1px solid var(--border)' }}>
                  <div style={{ display: 'flex', gap: 10, marginBottom: 8 }}>
                    <input
                      className="form-control"
                      placeholder="Ask about your financial documents... (Enter to send)"
                      value={input}
                      onChange={e => setInput(e.target.value)}
                      onKeyDown={onKey}
                      disabled={loading}
                      style={{ marginBottom: 0, flex: 1 }}
                    />
                    <button
                      className="btn btn-primary"
                      onClick={send}
                      disabled={loading || !input.trim()}
                      style={{ flexShrink: 0, height: 40, width: 40, padding: 0, display: 'flex', alignItems: 'center', justifyContent: 'center', borderRadius: 10 }}
                    >
                      <Send size={16} />
                    </button>
                  </div>
                  {/* Model selector row */}
                  <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                    <span style={{ fontSize: 11, color: 'var(--text-muted)', fontWeight: 500 }}>Model:</span>
                    <select
                      value={model}
                      onChange={e => setModel(e.target.value)}
                      style={{
                        background: 'rgba(255,255,255,0.04)', border: '1px solid var(--border)',
                        borderRadius: 8, color: 'var(--text-secondary)', fontSize: 12,
                        padding: '3px 8px', cursor: 'pointer', outline: 'none',
                      }}
                    >
                      {models.map(m => <option key={m.value} value={m.value}>{m.label}</option>)}
                    </select>
                  </div>
                </div>
              </>
            )}

          </GlowCard>
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
