import { useState, useRef, useEffect } from 'react'
import { ragApi } from '../api/client'
import { Send, Bot, Sparkles } from 'lucide-react'

const WELCOME = {
  id: 'welcome',
  role: 'ai',
  text: "👋 Hi! I'm FinSight AI. Ask me anything about the financial documents you've uploaded — earnings, revenue growth, debt levels, management guidance, and more.",
  sources: [],
}

export default function Chat() {
  const [messages, setMessages] = useState([WELCOME])
  const [input, setInput] = useState('')
  const [symbol, setSymbol] = useState('')
  const [loading, setLoading] = useState(false)
  const bottomRef = useRef(null)

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  const send = async () => {
    const q = input.trim()
    if (!q || loading) return
    setInput('')
    setMessages(prev => [...prev, { id: Date.now(), role: 'user', text: q, sources: [] }])
    setLoading(true)
    try {
      const r = await ragApi.query(q, symbol || undefined)
      setMessages(prev => [...prev, {
        id: Date.now() + 1,
        role: 'ai',
        text: r.data.answer,
        sources: r.data.sources ?? [],
      }])
    } catch (err) {
      setMessages(prev => [...prev, {
        id: Date.now() + 1,
        role: 'ai',
        text: `⚠ Error: ${err.response?.data?.detail ?? 'Failed to get answer. Is Ollama running?'}`,
        sources: [],
      }])
    } finally { setLoading(false) }
  }

  const onKey = (e) => { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); send() } }

  return (
    <div>
      <div className="page-header">
        <h1 className="page-title" style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
          <Sparkles size={24} color="#6366f1" /> RAG Chat
        </h1>
        <p className="page-sub">Ask questions grounded in your uploaded financial documents</p>
      </div>

      {/* Filter bar */}
      <div className="card mb-4" style={{ display: 'flex', gap: 12, alignItems: 'center', padding: '14px 18px' }}>
        <span className="text-sm text-muted" style={{ whiteSpace: 'nowrap' }}>Filter by symbol:</span>
        <input
          id="chat-symbol-filter"
          className="form-control"
          style={{ maxWidth: 160, marginBottom: 0 }}
          placeholder="e.g. INFY (optional)"
          value={symbol}
          onChange={e => setSymbol(e.target.value)}
        />
        <span className="text-xs text-muted">Leave blank to search all documents</span>
      </div>

      <div className="chat-layout">
        <div className="chat-messages">
          {messages.map(msg => (
            <div key={msg.id} className={`chat-msg ${msg.role}`}>
              <div className={`chat-avatar ${msg.role}`}>
                {msg.role === 'ai' ? <Bot size={16} /> : 'U'}
              </div>
              <div>
                <div className="chat-bubble">{msg.text}</div>
                {msg.sources?.length > 0 && (
                  <div className="chat-sources">
                    {msg.sources.slice(0, 5).map((s, i) => (
                      <span key={i} className="source-chip">
                        [{i+1}] {s.symbol} · {s.doc_type?.replace(/_/g,' ')}
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
                <span className="spinner" /> Thinking…
              </div>
            </div>
          )}
          <div ref={bottomRef} />
        </div>

        <div className="chat-input-row">
          <input
            id="chat-input"
            className="form-control"
            placeholder="Ask a financial question… (Enter to send)"
            value={input}
            onChange={e => setInput(e.target.value)}
            onKeyDown={onKey}
            disabled={loading}
          />
          <button
            id="chat-send"
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
  )
}
