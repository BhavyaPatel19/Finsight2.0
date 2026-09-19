import { motion, AnimatePresence, useScroll, useTransform, useInView, useMotionValue, animate } from 'motion/react'
import { useRef, useEffect } from 'react'
import { Link } from 'react-router-dom'
import {
  ChevronDown, Sun, Moon, FileText, MessageSquare,
  Shield, Brain, TrendingUp, PieChart, List,
  AlertTriangle, Search, Clock, CheckCircle, Zap,
  ArrowRight, Github, Linkedin, ChevronRight,
  Database, Cpu, Layers, GitBranch,
  Microscope, Target, BookOpen, Sparkles,
  Server, Globe, Lock, Activity,
} from 'lucide-react'
import { useAuth } from '../context/AuthContext'
import { useTheme } from '../context/ThemeContext'
import { FinSightLogo } from '../components/FinSightLogo'
import { FloatingCurrencies } from '../components/FloatingCurrencies'
import GlowCard from '../components/GlowCard'
import ShaderBackground from '../components/ShaderBackground'

/* ═══════════════════════════════════════════════════════
   ANIMATION PRIMITIVES (ZettaJoule-inspired)
   ═══════════════════════════════════════════════════════ */
const expo = [0.16, 1, 0.3, 1]

function Reveal({ children, delay = 0, direction = 'up', className = '', blur = false, scale: doScale = false }) {
  const y = direction === 'up' ? 50 : direction === 'down' ? -50 : 0
  const x = direction === 'left' ? 60 : direction === 'right' ? -60 : 0
  return (
    <motion.div
      className={className}
      initial={{
        opacity: 0, y, x,
        filter: blur ? 'blur(10px)' : 'none',
        scale: doScale ? 1.15 : 1,
      }}
      whileInView={{
        opacity: 1, y: 0, x: 0,
        filter: 'blur(0px)',
        scale: 1,
      }}
      viewport={{ once: true, margin: '-80px' }}
      transition={{ duration: 0.8, delay, ease: expo }}
    >
      {children}
    </motion.div>
  )
}

/* Stagger variants */
const staggerContainer = {
  hidden: {},
  visible: { transition: { staggerChildren: 0.1, delayChildren: 0.15 } },
}
const staggerItem = {
  hidden: { opacity: 0, y: 35, filter: 'blur(4px)' },
  visible: { opacity: 1, y: 0, filter: 'blur(0px)', transition: { duration: 0.7, ease: expo } },
}

/* Animated counter */
function CountUp({ target, suffix = '', prefix = '', duration = 1.8 }) {
  const ref = useRef(null)
  const inView = useInView(ref, { once: true, margin: '-100px' })
  const motionVal = useMotionValue(0)

  useEffect(() => {
    if (inView) animate(motionVal, target, { duration, ease: 'easeOut' })
  }, [inView, target, duration, motionVal])

  useEffect(() => {
    return motionVal.on('change', v => {
      if (ref.current) {
        const display = Number.isInteger(target) ? Math.round(v) : v.toFixed(1)
        ref.current.textContent = `${prefix}${display}${suffix}`
      }
    })
  }, [motionVal, prefix, suffix, target])

  return <span ref={ref}>{prefix}0{suffix}</span>
}

/* Spring scale-in for icons/numbers */
function ScaleIn({ children, delay = 0, className = '' }) {
  return (
    <motion.div
      className={className}
      initial={{ opacity: 0, scale: 0 }}
      whileInView={{ opacity: 1, scale: 1 }}
      viewport={{ once: true, margin: '-80px' }}
      transition={{ type: 'spring', stiffness: 200, damping: 15, delay }}
    >
      {children}
    </motion.div>
  )
}

/* Animated horizontal divider line */
function AnimatedLine() {
  return (
    <motion.div
      className="landing-divider"
      initial={{ scaleX: 0 }}
      whileInView={{ scaleX: 1 }}
      viewport={{ once: true, margin: '-80px' }}
      transition={{ duration: 0.8, ease: expo }}
      style={{ transformOrigin: 'left' }}
    />
  )
}

/* Scroll-linked pipeline progress line */
function PipelineProgressLine() {
  const ref = useRef(null)
  const { scrollYProgress } = useScroll({
    target: ref,
    offset: ['start end', 'end start'],
  })
  const scaleY = useTransform(scrollYProgress, [0.1, 0.9], [0, 1])

  return (
    <div ref={ref} className="landing-pipeline-line-track">
      <motion.div
        className="landing-pipeline-line-fill"
        style={{ scaleY, transformOrigin: 'top' }}
      />
    </div>
  )
}

/* Particle dots canvas (ZettaJoule-inspired) */
function ParticleDots({ count = 35, color = 'rgba(20, 143, 119, 0.35)', className = '' }) {
  const canvasRef = useRef(null)
  const animRef = useRef(null)
  const particles = useRef([])

  useEffect(() => {
    const canvas = canvasRef.current
    if (!canvas) return
    const ctx = canvas.getContext('2d')
    if (!ctx) return

    const resize = () => {
      canvas.width = canvas.clientWidth * (window.devicePixelRatio || 1)
      canvas.height = canvas.clientHeight * (window.devicePixelRatio || 1)
    }
    resize()
    window.addEventListener('resize', resize)

    // Init particles
    particles.current = Array.from({ length: count }, () => ({
      x: Math.random() * canvas.width,
      y: Math.random() * canvas.height,
      vx: (Math.random() - 0.5) * 0.4,
      vy: (Math.random() - 0.5) * 0.4,
      r: 1.5 + Math.random() * 2,
    }))

    const render = () => {
      ctx.clearRect(0, 0, canvas.width, canvas.height)
      const p = particles.current

      // Draw connections
      ctx.strokeStyle = color.replace(/[\d.]+\)$/, '0.08)')
      ctx.lineWidth = 0.8
      for (let i = 0; i < p.length; i++) {
        for (let j = i + 1; j < p.length; j++) {
          const dx = p[i].x - p[j].x
          const dy = p[i].y - p[j].y
          const dist = Math.sqrt(dx * dx + dy * dy)
          if (dist < 120) {
            ctx.globalAlpha = 1 - dist / 120
            ctx.beginPath()
            ctx.moveTo(p[i].x, p[i].y)
            ctx.lineTo(p[j].x, p[j].y)
            ctx.stroke()
          }
        }
      }

      // Draw dots
      ctx.globalAlpha = 1
      for (const dot of p) {
        dot.x += dot.vx
        dot.y += dot.vy
        if (dot.x < 0 || dot.x > canvas.width) dot.vx *= -1
        if (dot.y < 0 || dot.y > canvas.height) dot.vy *= -1

        ctx.fillStyle = color
        ctx.beginPath()
        ctx.arc(dot.x, dot.y, dot.r, 0, Math.PI * 2)
        ctx.fill()
      }

      animRef.current = requestAnimationFrame(render)
    }
    render()

    return () => {
      window.removeEventListener('resize', resize)
      if (animRef.current) cancelAnimationFrame(animRef.current)
    }
  }, [count, color])

  return (
    <canvas
      ref={canvasRef}
      className={className}
      style={{
        position: 'absolute',
        inset: 0,
        width: '100%',
        height: '100%',
        pointerEvents: 'none',
        opacity: 0.6,
      }}
    />
  )
}

/* Mockup frame with perspective tilt */
function MockupFrame({ src, alt, caption, size = 'large' }) {
  const ref = useRef(null)
  const { scrollYProgress } = useScroll({
    target: ref,
    offset: ['start end', 'end start'],
  })
  const y = useTransform(scrollYProgress, [0, 1], [30, -30])

  return (
    <motion.div ref={ref} className={`landing-mockup-wrap ${size}`} style={{ y }}>
      <div className="landing-mockup-frame">
        {/* Browser dots */}
        <div className="landing-mockup-bar">
          <span /><span /><span />
        </div>
        <img src={src} alt={alt} loading="lazy" />
      </div>
      {caption && <p className="landing-mockup-caption">{caption}</p>}
    </motion.div>
  )
}


/* ═══════════════════════════════════════════════════════
   DATA CONSTANTS
   ═══════════════════════════════════════════════════════ */
const FEATURES = [
  { icon: FileText, title: 'Document Intelligence', desc: 'Upload annual reports and earnings calls — auto-extract, chunk, and embed for instant retrieval.', tags: ['PyMuPDF', 'bge-base-en-v1.5', 'ChromaDB'] },
  { icon: MessageSquare, title: 'AI Chat (RAG)', desc: 'Ask context-aware questions about your documents, powered by hybrid retrieval and grounded generation.', tags: ['DeepSeek-R1:14B', 'Hybrid RAG', 'RRF'] },
  { icon: Shield, title: 'Credibility Scoring', desc: 'Extract management claims and verify them against financial data to score trustworthiness.', tags: ['Claim Extraction', 'Deviation Score'] },
  { icon: Brain, title: 'FinBERT Sentiment', desc: 'Analyze earnings call transcripts with domain-specific NLP for bullish/bearish signals.', tags: ['ProsusAI/finbert', 'batch=32'] },
  { icon: TrendingUp, title: 'Market Data', desc: 'NSE quotes, candlestick charts, fundamentals and news — free delayed data out of the box, live via Zerodha Kite when you link an account.', tags: ['yfinance', 'Zerodha Kite'] },
  { icon: PieChart, title: 'Portfolio Analytics', desc: 'Visualize holdings with sector allocation, P&L tracking, and AI-driven insights.', tags: ['Groq Insights', 'Sector Allocation'] },
  { icon: List, title: 'Watchlist & AI Digest', desc: 'Track stocks with personalized watchlists, screener filters, and AI-generated digests.', tags: ['2h TTL Cache', 'AI Digest'] },
]

const PIPELINE_RAG = [
  { step: 1, title: 'Embedding', subtitle: 'BAAI/bge-base-en-v1.5', detail: '768-dimensional dense vectors with asymmetric query prefix for semantic search. Documents encoded without prefix, queries use "Represent this sentence for searching relevant passages:" prefix.', stat: { value: 768, suffix: '-d', label: 'Vector Dims' }, icon: Database },
  { step: 2, title: 'Hybrid Retrieval', subtitle: 'Dense + BM25', detail: 'ChromaDB cosine similarity retrieves top-30 dense matches. In parallel, rank-bm25 performs keyword retrieval with custom regex tokenizer for another top-30.', stat: { value: 30, suffix: '', label: 'Top-K Each' }, icon: Search },
  { step: 3, title: 'Reciprocal Rank Fusion', subtitle: 'RRF k=60', detail: 'Merges dense and sparse results: score = 1/(k + rank_dense) + 1/(k + rank_bm25). Deduplicates by document_id + chunk_index.', stat: { value: 60, suffix: '', label: 'RRF k-param' }, icon: GitBranch },
  { step: 4, title: 'Cross-Encoder Reranking', subtitle: 'BAAI/bge-reranker-base', detail: 'Reranks all fused candidates with cross-attention scoring. Returns top-8 most relevant passages for final context assembly.', stat: { value: 8, suffix: '', label: 'Final Passages' }, icon: Target },
  { step: 5, title: 'Grounded Generation', subtitle: 'Citation Enforcement', detail: 'Strict prompt: answer ONLY from context, quote numbers exactly, cite [Section > Page]. "Not found in selected documents" if missing.', stat: null, icon: BookOpen },
  { step: 6, title: 'Multi-LLM Inference', subtitle: 'DeepSeek / Llama / Groq', detail: 'DeepSeek-R1:14B for deep reasoning, Llama 3.1:8B for fast queries, Groq llama-3.3-70b-versatile for cloud inference.', stat: { value: 3, suffix: '', label: 'LLM Options' }, icon: Cpu },
]

const PIPELINE_INGESTION = [
  { title: 'PDF Extraction', detail: 'Dual fallback: PyMuPDF (fitz) primary, pdfplumber secondary. Per-page text with UTF-8 encoding.', tags: ['PyMuPDF', 'pdfplumber', 'Dual Fallback'] },
  { title: '3-Tier Chunking', detail: '512-char (legacy) | 1500-char/200-overlap (RAG) | 3500-char/500-overlap (credibility context).', tags: ['512-char', '1500/200', '3500/500'] },
  { title: 'Structure-Aware', detail: 'TOC parsing builds section tree. Paragraph-aware buffer flush at section boundaries with backward \\n\\n break search.', tags: ['Section Tree', 'Buffer Flush', 'Boundary Detection'] },
  { title: 'Concall Detection', detail: 'Regex matches speaker turns (CEO, CFO, Moderator patterns). 5+ matches in first 5 pages triggers concall chunking mode.', tags: ['Regex', 'Speaker Turns', '≥5 Threshold'] },
]

const FINBERT_SPECS = [
  { label: 'Batch Size', value: 32, suffix: '' },
  { label: 'Max Tokens', value: 512, suffix: '' },
  { label: 'Model Size', value: 500, suffix: 'MB' },
]

const FINBERT_FEATURES = [
  'Risk Tone Index — risk keywords ∩ negative probability > 0.4',
  'Optimism Index — weighted positive sentiment probability',
  'Financial sentence splitter handles Rs., Q3., FY25. abbreviations',
  'CUDA-aware — automatic GPU/CPU detection at load time',
]

const CREDIBILITY_STAGES = [
  { num: 1, name: 'Claim Extraction', detail: 'LLM extracts forward-looking claims from first 8000 chars → revenue_growth, margin_expansion, debt_reduction, market_expansion' },
  { num: 2, name: 'Financial Verification', detail: 'Each claim verified against actual FinancialMetric table data for symbol + period' },
  { num: 3, name: 'Deviation Scoring', detail: 'score = max(0, 100 × (1 − avg_deviation)) where deviation = |claim − actual| / |claim|' },
]

const MARKET_ZERODHA = [
  'OAuth 2.0 with SHA256 checksum (api_key + request_token + secret)',
  '500+ instruments indexed with prefix + contains search',
  'Groq-powered AI insights with 2-hour TTL cache (temp 0.3)',
  'yfinance fundamentals with 24-hour SQLite cache',
]

const MARKET_SCRAPER = [
  'BSE corporate filing API with date-range search',
  'User-Agent rotation across 6 browser profiles',
  'Exponential backoff + anti-bot homepage cookie grab',
  '61-stock local instrument database for instant lookup',
]

const TECH_STACK = [
  { category: 'Backend', techs: [
    { name: 'FastAPI', color: '#009688', logo: '/tech-logos/fastapi.svg', desc: 'High-performance async Python web framework for building APIs.' },
    { name: 'SQLite', color: '#003B57', logo: '/tech-logos/sqlite.png', desc: 'Lightweight embedded relational database for local persistence.' },
    { name: 'SQLModel', color: '#e91e63', logo: '/tech-logos/sqlmodel.svg', desc: 'Pydantic + SQLAlchemy ORM for type-safe database models.' },
    { name: 'ChromaDB', color: '#FFD54F', logo: '/tech-logos/chromadb.png', desc: 'Open-source vector database for semantic document embeddings.' },
    { name: 'APScheduler', color: '#7E57C2', logo: '/tech-logos/apscheduler.png', desc: 'Background job scheduler for periodic document fetches.' },
  ]},
  { category: 'AI / ML', techs: [
    { name: 'Llama 3', color: '#7B1FA2', desc: 'Meta\'s open-source LLM, served locally via Ollama for RAG.' },
    { name: 'FinBERT', color: '#FF7043', logo: '/tech-logos/finbert.png', desc: 'Finance-domain BERT model for sentiment analysis on earnings calls.' },
    { name: 'Sentence Transformers', color: '#FFB300', logo: '/tech-logos/sentence-transformers.svg', desc: 'Transformer models for generating semantic text embeddings.' },
    { name: 'Groq', color: '#F55036', logo: '/tech-logos/groq.png', desc: 'Ultra-fast cloud LLM inference for market insights and digests.' },
  ]},
  { category: 'Frontend', techs: [
    { name: 'React 18', color: '#61DAFB', logo: '/tech-logos/react.png', desc: 'Component-based UI library with concurrent rendering features.' },
    { name: 'Vite', color: '#646CFF', logo: '/tech-logos/vite.png', desc: 'Next-gen frontend build tool with instant HMR and fast bundling.' },
    { name: 'Framer Motion', color: '#FF0055', logo: '/tech-logos/framer-motion.webp', desc: 'Production-ready animation library for fluid UI transitions.' },
    { name: 'Recharts', color: '#22B5BF', logo: '/tech-logos/recharts.jpeg', desc: 'Composable charting library built on React and D3 primitives.' },
    { name: 'Lucide', color: '#F56565', logo: '/tech-logos/lucide.png', desc: 'Beautiful open-source icon set with tree-shakeable React components.' },
  ]},
  { category: 'Integration', techs: [
    { name: 'Zerodha Kite', color: '#387ED1', logo: '/tech-logos/zerodha.jpg', desc: 'India\'s largest broker API for live quotes, holdings, and OAuth.' },
    { name: 'Screener.in', color: '#4CAF50', logo: '/tech-logos/screener.png', desc: 'Financial data source for company documents and annual reports.' },
    { name: 'BSE Filings', color: '#FF9800', logo: '/tech-logos/bse.png', desc: 'Bombay Stock Exchange corporate filing scraper integration.' },
    { name: 'OAuth 2.0', color: '#1565C0', logo: '/tech-logos/oauth.png', desc: 'Secure token-based authentication for Zerodha broker access.' },
  ]},
]

const JOURNEY_STEPS = [
  { num: 1, title: 'Bring Your Filings', icon: Lock, accent: '#2980B9', desc: 'Upload annual reports or earnings-call transcripts, or start with the bundled public Infosys filings. Optionally link Zerodha for live holdings.' },
  { num: 2, title: 'Upload Financial Documents', icon: FileText, accent: '#1ABC9C', desc: 'Drop annual reports, concall transcripts, or investor presentations. FinSight extracts text, builds a section tree, and embeds 1500-char chunks into ChromaDB.' },
  { num: 3, title: 'Ask Your Documents Questions', icon: MessageSquare, accent: '#8E44AD', desc: 'Type "What was TCS\'s EBIT margin guidance for FY26?" and get a sourced answer with [Section > Page] citations in seconds.' },
  { num: 4, title: 'Act on Verified Insights', icon: TrendingUp, accent: '#E67E22', desc: 'Review credibility scores, FinBERT sentiment trends, and AI-generated investment digests for your watchlist.' },
]

const TEAM = [
  { name: 'Team Member 1', role: 'Full Stack Developer', initial: 'A', bio: 'Passionate about building scalable web applications and AI-powered tools.' },
  { name: 'Team Member 2', role: 'ML & Backend Engineer', initial: 'B', bio: 'Focused on NLP, financial modeling, and building robust data pipelines.' },
  { name: 'Team Member 3', role: 'Frontend & Design', initial: 'C', bio: 'Creating intuitive interfaces with modern design systems and animations.' },
]

const TRANSFORMATIONS = [
  {
    pain: { icon: Search, headline: '200+ Page Annual Reports',
      body: 'You download a 240-page annual report at 11 PM. By page 30, your eyes glaze over. The revenue guidance is buried on page 187 — you never find it.' },
    fix: { icon: Zap, headline: 'Ask, and Receive',
      body: '"What was the revenue guidance for FY26?" — sourced answer with page citation in 3 seconds flat. RAG retrieval reads every page so you don\'t have to.' },
  },
  {
    pain: { icon: AlertTriangle, headline: 'Management Says "Strong Growth"',
      body: 'Every concall transcript sounds bullish. "Record quarter," "strong pipeline," "margin expansion ahead." How do you know who is actually delivering?' },
    fix: { icon: Shield, headline: 'Claims Meet Reality',
      body: 'FinSight extracts forward-looking claims, then checks them against actual financials. A credibility score tells you who walks the talk — and who just talks.' },
  },
  {
    pain: { icon: Clock, headline: 'Gut Feel Investing',
      body: 'You read a bullish post on Twitter, skim one article, and press Buy. No sentiment analysis. No data-backed conviction. Just FOMO and hope.' },
    fix: { icon: Brain, headline: 'FinBERT-Powered Conviction',
      body: 'Domain-specific NLP reads earnings transcripts sentence by sentence. Quantified bullish/bearish signals, risk tone index, and optimism trends — not vibes.' },
  },
]


/* ═══════════════════════════════════════════════════════
   MEET THE TEAM
   ═══════════════════════════════════════════════════════ */
const TEAM_COLORS = ['#2980B9', '#148F77', '#1ABC9C']


/* ═══════════════════════════════════════════════════════
   LANDING PAGE
   ═══════════════════════════════════════════════════════ */
export default function Landing() {
  const { user } = useAuth()
  const { theme, toggleTheme } = useTheme()
  const heroRef = useRef(null)
  const { scrollYProgress } = useScroll({
    target: heroRef,
    offset: ['start start', 'end start'],
  })
  const heroOpacity = useTransform(scrollYProgress, [0, 1], [1, 0])
  const heroScale = useTransform(scrollYProgress, [0, 1], [1, 0.92])
  const heroY = useTransform(scrollYProgress, [0, 1], [0, -60])

  // Journey timeline scroll-linked progress
  const journeyRef = useRef(null)
  const { scrollYProgress: journeyScroll } = useScroll({
    target: journeyRef,
    offset: ['start end', 'end start'],
  })
  const journeyLineProgress = useTransform(journeyScroll, [0.1, 0.85], [0, 1])

  return (
    <div className="landing-page">
      <FloatingCurrencies theme={theme} />

      {/* Floating theme toggle */}
      <button className="landing-theme-toggle" onClick={toggleTheme} aria-label="Toggle theme">
        <AnimatePresence mode="wait" initial={false}>
          <motion.div
            key={theme}
            initial={{ rotate: -90, opacity: 0, scale: 0.5 }}
            animate={{ rotate: 0, opacity: 1, scale: 1 }}
            exit={{ rotate: 90, opacity: 0, scale: 0.5 }}
            transition={{ duration: 0.2 }}
            style={{ display: 'flex', alignItems: 'center', justifyContent: 'center' }}
          >
            {theme === 'dark' ? <Sun size={18} /> : <Moon size={18} />}
          </motion.div>
        </AnimatePresence>
      </button>

      {/* ═══ HERO ═══ */}
      <motion.section
        ref={heroRef}
        className="landing-section landing-hero"
        style={{ opacity: heroOpacity, scale: heroScale, y: heroY }}
      >
        <ShaderBackground />
        <ParticleDots count={30} color="rgba(20, 143, 119, 0.25)" />

        <motion.div
          initial={{ opacity: 0, y: 30 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.8, ease: expo }}
          style={{ position: 'relative', zIndex: 1 }}
        >
          <FinSightLogo size="xl" showTagline animated theme={theme} />
        </motion.div>

        <motion.h1
          className="landing-hero-tagline"
          initial={{ opacity: 0, y: 30, filter: 'blur(10px)' }}
          animate={{ opacity: 1, y: 0, filter: 'blur(0px)' }}
          transition={{ delay: 0.3, duration: 0.9, ease: expo }}
        >
          AI-Powered Financial Intelligence
          <br />for Indian Retail Investors
        </motion.h1>

        <motion.p
          className="landing-hero-description"
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.55, duration: 0.7, ease: expo }}
        >
          Upload earnings reports, chat with your documents, and get credibility-scored
          insights — all in one intelligent platform.
        </motion.p>

        <motion.div
          className="landing-hero-cta"
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.75, duration: 0.7, ease: expo }}
        >
          {user ? (
            <Link to="/dashboard" className="btn btn-primary landing-btn-slide" style={{ minWidth: 170, justifyContent: 'center' }}>
              Go to Dashboard <ArrowRight size={15} />
            </Link>
          ) : (
            <>
              <Link to="/login" className="btn btn-primary landing-btn-slide" style={{ minWidth: 160, justifyContent: 'center' }}>
                Get Started <ArrowRight size={15} />
              </Link>
              <Link to="/register" className="btn btn-ghost landing-btn-slide" style={{ minWidth: 160, justifyContent: 'center' }}>
                Create Account
              </Link>
            </>
          )}
        </motion.div>

        <motion.div
          className="landing-scroll-indicator"
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          transition={{ delay: 1.2, duration: 0.6 }}
        >
          <span>Scroll</span>
          <motion.div
            animate={{ y: [0, 8, 0] }}
            transition={{ duration: 1.5, repeat: Infinity, ease: 'easeInOut' }}
          >
            <ChevronDown size={20} />
          </motion.div>
        </motion.div>
      </motion.section>

      {/* ═══ PRODUCT SHOWCASE ═══ */}
      <section className="landing-section-half" style={{ paddingTop: 100, paddingBottom: 100, position: 'relative', overflow: 'hidden' }}>
        <ParticleDots count={20} color="rgba(20, 143, 119, 0.15)" />
        <div className="landing-container" style={{ position: 'relative', zIndex: 1 }}>
          <Reveal blur>
            <AnimatedLine />
            <h2 className="landing-section-title">See It in Action</h2>
            <p className="landing-section-subtitle">
              A glimpse into the platform that powers smarter investing.
            </p>
          </Reveal>

          {/* Large hero mockup */}
          <Reveal scale delay={0.2}>
            <MockupFrame
              src="/screenshots/dashboard.jpeg"
              alt="FinSight Dashboard — Portfolio overview with Zerodha integration"
              caption="Dashboard — Real-time portfolio overview with Zerodha integration"
              size="large"
            />
          </Reveal>

          {/* Three smaller mockups */}
          <div className="landing-mockup-row">
            <Reveal scale delay={0.1}>
              <MockupFrame
                src="/screenshots/market.jpeg"
                alt="Live Market — Watchlist, charts, fundamentals, AI insights"
                caption="Live Market & AI Insights"
                size="small"
              />
            </Reveal>
            <Reveal scale delay={0.2}>
              <MockupFrame
                src="/screenshots/chat.jpeg"
                alt="RAG Chat — Ask questions about financial documents"
                caption="RAG-Powered Document Chat"
                size="small"
              />
            </Reveal>
            <Reveal scale delay={0.3}>
              <MockupFrame
                src="/screenshots/credisentiment.jpeg"
                alt="CrediSentiment — Walking the Talk credibility analysis"
                caption="Credibility & Sentiment Analysis"
                size="small"
              />
            </Reveal>
          </div>
        </div>
      </section>

      {/* ═══ WHY FINSIGHT ═══ */}
      <section className="landing-section-half landing-why">
        <div className="landing-container">
          <Reveal blur>
            <AnimatedLine />
            <h2 className="landing-section-title">Why FinSight?</h2>
            <p className="landing-section-subtitle">
              Indian retail investors deserve better tools. Here's what changes.
            </p>
          </Reveal>

          <div className="landing-transform-list">
            {TRANSFORMATIONS.map((t, i) => (
              <div key={i} className="landing-transform-row">
                <Reveal delay={i * 0.15} direction="left" className="landing-transform-card landing-transform-pain">
                  <div className="landing-transform-icon landing-transform-icon--pain">
                    <t.pain.icon size={22} />
                  </div>
                  <h3>{t.pain.headline}</h3>
                  <p>{t.pain.body}</p>
                </Reveal>

                <ScaleIn delay={i * 0.15 + 0.2} className="landing-transform-arrow">
                  <ArrowRight size={28} />
                </ScaleIn>

                <Reveal delay={i * 0.15 + 0.3} direction="right" className="landing-transform-card landing-transform-fix">
                  <div className="landing-transform-icon landing-transform-icon--fix">
                    <t.fix.icon size={22} />
                  </div>
                  <h3>{t.fix.headline}</h3>
                  <p>{t.fix.body}</p>
                </Reveal>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* ═══ FEATURES ═══ */}
      <section className="landing-section-half" style={{ background: 'var(--bg-surface)' }}>
        <div className="landing-container">
          <Reveal blur>
            <AnimatedLine />
            <h2 className="landing-section-title">Key Features</h2>
            <p className="landing-section-subtitle">
              Everything you need to make smarter investment decisions.
            </p>
          </Reveal>

          <motion.div
            className="landing-features-grid"
            variants={staggerContainer}
            initial="hidden"
            whileInView="visible"
            viewport={{ once: true, margin: '-60px' }}
          >
            {FEATURES.map((feat, i) => (
              <motion.div key={i} variants={staggerItem}>
                <GlowCard className="landing-feature-card">
                  <div className="landing-feature-icon">
                    <feat.icon size={22} />
                  </div>
                  <h3>{feat.title}</h3>
                  <p>{feat.desc}</p>
                  {feat.tags && (
                    <div className="landing-tag-row">
                      {feat.tags.map((tag, j) => (
                        <span key={j} className="landing-code-tag">{tag}</span>
                      ))}
                    </div>
                  )}
                </GlowCard>
              </motion.div>
            ))}
          </motion.div>
        </div>
      </section>

      {/* ═══ UNDER THE HOOD ═══ */}
      <section className="landing-section-half landing-hood" style={{ background: 'var(--bg-base)', paddingTop: 120, paddingBottom: 120 }}>
        <div className="landing-container">
          <Reveal blur>
            <AnimatedLine />
            <h2 className="landing-section-title">Under the Hood</h2>
            <p className="landing-section-subtitle">
              Production-grade AI pipelines — not a toy demo.
            </p>
          </Reveal>

          {/* ── RAG Pipeline ── */}
          <div className="landing-hood-subsection">
            <Reveal blur>
              <h3 className="landing-hood-subtitle"><Sparkles size={20} /> RAG Pipeline — The Crown Jewel</h3>
            </Reveal>

            <div className="landing-pipeline-track">
              <PipelineProgressLine />

              {PIPELINE_RAG.map((item, i) => (
                <Reveal key={i} delay={i * 0.08} direction={i % 2 === 0 ? 'left' : 'right'}>
                  <div className="landing-pipeline-step">
                    <ScaleIn delay={i * 0.08 + 0.1}>
                      <div className="landing-pipeline-num">{item.step}</div>
                    </ScaleIn>
                    <div className="landing-pipeline-content">
                      <div className="landing-pipeline-header">
                        <item.icon size={18} />
                        <h4>{item.title}</h4>
                      </div>
                      <span className="landing-code-tag">{item.subtitle}</span>
                      <p>{item.detail}</p>
                      {item.stat && (
                        <div className="landing-stat-badge">
                          <span className="landing-stat-value">
                            <CountUp target={item.stat.value} suffix={item.stat.suffix} />
                          </span>
                          <span className="landing-stat-label">{item.stat.label}</span>
                        </div>
                      )}
                    </div>
                  </div>
                </Reveal>
              ))}
            </div>
          </div>

          {/* ── Ingestion & Chunking ── */}
          <div className="landing-hood-subsection">
            <Reveal blur>
              <h3 className="landing-hood-subtitle"><Layers size={20} /> Ingestion & Chunking Pipeline</h3>
            </Reveal>

            <motion.div
              className="landing-ingestion-grid"
              variants={staggerContainer}
              initial="hidden"
              whileInView="visible"
              viewport={{ once: true }}
            >
              {PIPELINE_INGESTION.map((item, i) => (
                <motion.div key={i} variants={staggerItem}>
                  <GlowCard className="landing-tech-callout">
                    <h4>{item.title}</h4>
                    <p>{item.detail}</p>
                    <div className="landing-tag-row">
                      {item.tags.map((tag, j) => (
                        <span key={j} className="landing-code-tag">{tag}</span>
                      ))}
                    </div>
                  </GlowCard>
                </motion.div>
              ))}
            </motion.div>
          </div>

          {/* ── Sentiment & Credibility ── */}
          <div className="landing-hood-subsection">
            <Reveal blur>
              <h3 className="landing-hood-subtitle"><Microscope size={20} /> Sentiment & Credibility Analysis</h3>
            </Reveal>

            <div className="landing-sent-cred-grid">
              <Reveal direction="left">
                <GlowCard className="landing-tech-callout">
                  <h4>FinBERT Sentiment Engine</h4>
                  <span className="landing-code-tag">ProsusAI/finbert</span>
                  <div className="landing-spec-row">
                    {FINBERT_SPECS.map((spec, i) => (
                      <div key={i} className="landing-stat-badge">
                        <span className="landing-stat-value">
                          <CountUp target={spec.value} suffix={spec.suffix} />
                        </span>
                        <span className="landing-stat-label">{spec.label}</span>
                      </div>
                    ))}
                  </div>
                  <ul className="landing-feature-list">
                    {FINBERT_FEATURES.map((f, i) => <li key={i}>{f}</li>)}
                  </ul>
                </GlowCard>
              </Reveal>

              <Reveal direction="right">
                <GlowCard className="landing-tech-callout">
                  <h4>Credibility Scoring — "Walking the Talk"</h4>
                  {CREDIBILITY_STAGES.map((stage, i) => (
                    <div key={i} className="landing-cred-stage">
                      <ScaleIn delay={i * 0.12}>
                        <div className="landing-pipeline-num small">{stage.num}</div>
                      </ScaleIn>
                      <div>
                        <strong>{stage.name}</strong>
                        <p>{stage.detail}</p>
                      </div>
                    </div>
                  ))}
                  <div className="landing-tag-row" style={{ marginTop: 12 }}>
                    <span className="landing-code-tag">Separate ChromaDB collection</span>
                    <span className="landing-code-tag">3500-char context chunks</span>
                    <span className="landing-code-tag">credisentiment_docs</span>
                  </div>
                </GlowCard>
              </Reveal>
            </div>
          </div>

          {/* ── Market & Scraper ── */}
          <div className="landing-hood-subsection">
            <Reveal blur>
              <h3 className="landing-hood-subtitle"><Activity size={20} /> Market Data & BSE Scraper</h3>
            </Reveal>

            <div className="landing-sent-cred-grid">
              <Reveal direction="left">
                <GlowCard className="landing-tech-callout">
                  <h4><Globe size={16} /> Zerodha Integration</h4>
                  <ul className="landing-feature-list">
                    {MARKET_ZERODHA.map((item, i) => <li key={i}>{item}</li>)}
                  </ul>
                </GlowCard>
              </Reveal>
              <Reveal direction="right">
                <GlowCard className="landing-tech-callout">
                  <h4><Server size={16} /> BSE Filing Scraper</h4>
                  <ul className="landing-feature-list">
                    {MARKET_SCRAPER.map((item, i) => <li key={i}>{item}</li>)}
                  </ul>
                </GlowCard>
              </Reveal>
            </div>
          </div>
        </div>
      </section>

      {/* ═══ TECH STACK ═══ */}
      <section className="landing-section-half">
        <div className="landing-container">
          <Reveal blur>
            <AnimatedLine />
            <h2 className="landing-section-title">Technology Stack</h2>
            <p className="landing-section-subtitle">
              Built with modern, production-grade technologies.
            </p>
          </Reveal>

          <motion.div
            className="landing-tech-grid"
            variants={staggerContainer}
            initial="hidden"
            whileInView="visible"
            viewport={{ once: true }}
          >
            {TECH_STACK.map((cat, i) => (
              <motion.div key={i} variants={staggerItem}>
                <div className="landing-tech-category">
                  <h4>{cat.category}</h4>
                  <div className="landing-tech-list">
                    {cat.techs.map((tech, j) => (
                      <div key={j} className="landing-tech-item">
                        {tech.logo ? (
                          <img src={tech.logo} alt={tech.name} className="landing-tech-logo-img" />
                        ) : (
                          <div className="landing-tech-logo" style={{ background: tech.color }}>
                            {tech.name[0]}
                          </div>
                        )}
                        <div>
                          <div className="landing-tech-name">{tech.name}</div>
                          <div className="landing-tech-desc">{tech.desc}</div>
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              </motion.div>
            ))}
          </motion.div>
        </div>
      </section>

      {/* ═══ YOUR JOURNEY ═══ */}
      <section className="landing-section-half" style={{ background: 'var(--bg-surface)' }}>
        <div className="landing-container">
          <Reveal blur>
            <AnimatedLine />
            <h2 className="landing-section-title">Your Journey</h2>
            <p className="landing-section-subtitle">
              From broker connect to verified insights in four steps.
            </p>
          </Reveal>

          <div className="landing-timeline" ref={journeyRef}>
            <div className="landing-timeline-track">
              <motion.div
                className="landing-timeline-fill"
                style={{ scaleY: journeyLineProgress, transformOrigin: 'top' }}
              />
            </div>

            {JOURNEY_STEPS.map((step, i) => (
              <Reveal
                key={i}
                delay={i * 0.12}
                direction={i % 2 === 0 ? 'left' : 'right'}
                className={`landing-timeline-item ${i % 2 === 0 ? 'landing-timeline-left' : 'landing-timeline-right'}`}
              >
                <ScaleIn delay={i * 0.12 + 0.1}>
                  <div
                    className="landing-timeline-node"
                    style={{ background: step.accent }}
                  >
                    {step.num}
                  </div>
                </ScaleIn>

                <GlowCard className="landing-timeline-card">
                  <div className="landing-timeline-card-icon" style={{ background: `${step.accent}20`, color: step.accent }}>
                    <step.icon size={20} />
                  </div>
                  <h3>{step.title}</h3>
                  <p>{step.desc}</p>
                </GlowCard>
              </Reveal>
            ))}
          </div>
        </div>
      </section>

      {/* ═══ TEAM ═══ */}
      <section className="landing-section-half landing-team-section">
        <div className="landing-container">
          <Reveal blur>
            <AnimatedLine />
            <h2 className="landing-section-title">Meet the Team</h2>
            <p className="landing-section-subtitle">
              Three builders. One vision. Making finance intelligent.
            </p>
          </Reveal>

          <ScaleIn delay={0.15}>
            <div className="landing-team-logo">
              <FinSightLogo size="xl" />
            </div>
          </ScaleIn>

          <div className="landing-team-grid">
            {TEAM.map((member, i) => (
              <Reveal key={i} delay={0.15 + i * 0.12} direction={i === 0 ? 'left' : i === 2 ? 'right' : 'up'}>
                <GlowCard className="landing-team-card">
                  <div className="landing-team-avatar" style={{ background: TEAM_COLORS[i] }}>
                    {member.initial}
                  </div>
                  <h3 className="landing-team-name">{member.name}</h3>
                  <div className="landing-team-role">{member.role}</div>
                  <p className="landing-team-bio">{member.bio}</p>
                  <div className="landing-team-links">
                    <a href="#" title="GitHub"><Github size={18} /></a>
                    <a href="#" title="LinkedIn"><Linkedin size={18} /></a>
                  </div>
                </GlowCard>
              </Reveal>
            ))}
          </div>
        </div>
      </section>

      {/* ═══ FOOTER ═══ */}
      <footer className="landing-footer" style={{ position: 'relative', overflow: 'hidden' }}>
        <ParticleDots count={15} color="rgba(20, 143, 119, 0.2)" />
        <div style={{ position: 'relative', zIndex: 1 }}>
          <FinSightLogo size="small" theme={theme} animated={false} />
          <p className="landing-footer-text">
            Built for 8th Semester Project &middot; 2026
          </p>
          <div className="landing-footer-links">
            <Link to="/login">Login</Link>
            <Link to="/register">Register</Link>
          </div>
        </div>
      </footer>
    </div>
  )
}
