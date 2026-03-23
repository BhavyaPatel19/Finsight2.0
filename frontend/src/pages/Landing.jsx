import { motion, AnimatePresence, useScroll, useTransform } from 'motion/react'
import { useRef } from 'react'
import { Link } from 'react-router-dom'
import {
  ChevronDown, Sun, Moon, FileText, MessageSquare,
  Shield, Brain, TrendingUp, PieChart, List,
  AlertTriangle, Search, Clock, CheckCircle, Zap,
  ArrowRight, Github, Linkedin, ChevronRight,
} from 'lucide-react'
import { useAuth } from '../context/AuthContext'
import { useTheme } from '../context/ThemeContext'
import { FinSightLogo } from '../components/FinSightLogo'
import { FloatingCurrencies } from '../components/FloatingCurrencies'
import GlowCard from '../components/GlowCard'
import HoverButton from '../components/HoverButton'

/* ── Scroll-triggered reveal wrapper ─────────────── */
function Reveal({ children, delay = 0, direction = 'up', className = '' }) {
  const y = direction === 'up' ? 40 : direction === 'down' ? -40 : 0
  const x = direction === 'left' ? 40 : direction === 'right' ? -40 : 0
  return (
    <motion.div
      className={className}
      initial={{ opacity: 0, y, x }}
      whileInView={{ opacity: 1, y: 0, x: 0 }}
      viewport={{ once: true, margin: '-80px' }}
      transition={{ duration: 0.6, delay, ease: [0.16, 1, 0.3, 1] }}
    >
      {children}
    </motion.div>
  )
}

/* ── Data ─────────────────────────────────────────── */
const FEATURES = [
  { icon: FileText, title: 'Document Intelligence', desc: 'Upload annual reports and earnings calls — auto-extract, chunk, and embed for instant retrieval.' },
  { icon: MessageSquare, title: 'AI Chat', desc: 'Ask context-aware questions about your documents, powered by Llama 3 and RAG.' },
  { icon: Shield, title: 'Credibility Scoring', desc: 'Extract management claims and verify them against financial data to score trustworthiness.' },
  { icon: Brain, title: 'FinBERT Sentiment', desc: 'Analyze earnings call transcripts with domain-specific NLP for bullish/bearish signals.' },
  { icon: TrendingUp, title: 'Live Market Data', desc: 'Real-time quotes, candlestick charts, and 52-week ranges via Zerodha Kite integration.' },
  { icon: PieChart, title: 'Portfolio Analytics', desc: 'Visualize holdings with sector allocation, P&L tracking, and AI-driven insights.' },
  { icon: List, title: 'Watchlist & AI Digest', desc: 'Track stocks with personalized watchlists, screener filters, and AI-generated digests.' },
]

const TECH_STACK = [
  { category: 'Backend', techs: ['FastAPI', 'SQLite', 'SQLModel', 'ChromaDB', 'APScheduler'] },
  { category: 'AI / ML', techs: ['Llama 3 (Ollama)', 'FinBERT', 'Sentence Transformers', 'Groq'] },
  { category: 'Frontend', techs: ['React 18', 'Vite', 'Framer Motion', 'Recharts', 'Lucide'] },
  { category: 'Integration', techs: ['Zerodha Kite API', 'Screener.in', 'BSE Filings', 'OAuth 2.0'] },
]

const FLOW_PIPELINES = [
  { label: 'Document Pipeline', steps: ['Upload PDF', 'Extract Text', 'Chunk & Embed', 'ChromaDB', 'RAG Query', 'AI Response'] },
  { label: 'Market Pipeline', steps: ['Zerodha API', 'Live Quotes', 'Portfolio Analytics', 'AI Insights'] },
  { label: 'Credibility Pipeline', steps: ['Earnings Transcript', 'Claim Extraction', 'FinBERT Analysis', 'Credibility Score'] },
]

const JOURNEY_STEPS = [
  { num: 1, title: 'Connect & Upload', desc: 'Link your Zerodha account and upload annual reports or earnings transcripts.' },
  { num: 2, title: 'Explore & Analyze', desc: 'View live market data, portfolio holdings, and sector-level breakdowns.' },
  { num: 3, title: 'Ask AI Questions', desc: 'Chat with your documents — get sourced answers backed by RAG retrieval.' },
  { num: 4, title: 'Get Insights', desc: 'Review credibility scores, sentiment trends, and AI-generated investment digests.' },
]

const TEAM = [
  { name: 'Team Member 1', role: 'Full Stack Developer', initial: 'A', bio: 'Passionate about building scalable web applications and AI-powered tools.' },
  { name: 'Team Member 2', role: 'ML & Backend Engineer', initial: 'B', bio: 'Focused on NLP, financial modeling, and building robust data pipelines.' },
  { name: 'Team Member 3', role: 'Frontend & Design', initial: 'C', bio: 'Creating intuitive interfaces with modern design systems and animations.' },
]

const PROBLEMS = [
  { icon: Search, text: 'Information overload — 100s of pages in annual reports, no time to read them all' },
  { icon: AlertTriangle, text: 'Trust deficit — management claims go unverified by most retail investors' },
  { icon: Clock, text: 'Manual analysis — sentiment and credibility assessed by gut feel, not data' },
]

const SOLUTIONS = [
  { icon: Zap, text: 'AI-powered document Q&A — ask questions, get sourced answers in seconds' },
  { icon: Shield, text: 'Credibility scoring — automated claim extraction and financial verification' },
  { icon: Brain, text: 'FinBERT sentiment — domain-specific NLP on earnings transcripts' },
]

/* ── Landing Page ─────────────────────────────────── */
export default function Landing() {
  const { user } = useAuth()
  const { theme, toggleTheme } = useTheme()
  const heroRef = useRef(null)
  const { scrollYProgress } = useScroll({
    target: heroRef,
    offset: ['start start', 'end start'],
  })
  const heroOpacity = useTransform(scrollYProgress, [0, 1], [1, 0])
  const heroScale = useTransform(scrollYProgress, [0, 1], [1, 0.95])

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
        style={{ opacity: heroOpacity, scale: heroScale }}
      >
        <motion.div
          initial={{ opacity: 0, y: 30 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.8, ease: [0.16, 1, 0.3, 1] }}
        >
          <FinSightLogo size="xl" showTagline animated theme={theme} />
        </motion.div>

        <motion.h1
          className="landing-hero-tagline"
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.3, duration: 0.7 }}
        >
          AI-Powered Financial Intelligence for Indian Retail Investors
        </motion.h1>

        <motion.p
          className="landing-hero-description"
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.5, duration: 0.7 }}
        >
          Upload earnings reports, chat with your documents, and get credibility-scored
          insights — all in one intelligent platform.
        </motion.p>

        <motion.div
          className="landing-hero-cta"
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.7, duration: 0.7 }}
        >
          {user ? (
            <Link to="/dashboard">
              <HoverButton text="Go to Dashboard" icon={ArrowRight} />
            </Link>
          ) : (
            <>
              <Link to="/login">
                <HoverButton text="Get Started" icon={ArrowRight} />
              </Link>
              <Link to="/register">
                <HoverButton text="Create Account" variant="ghost" />
              </Link>
            </>
          )}
        </motion.div>

        <div className="landing-scroll-indicator">
          <span>Scroll</span>
          <motion.div
            animate={{ y: [0, 8, 0] }}
            transition={{ duration: 1.5, repeat: Infinity, ease: 'easeInOut' }}
          >
            <ChevronDown size={20} />
          </motion.div>
        </div>
      </motion.section>

      {/* ═══ WHY FINSIGHT ═══ */}
      <section className="landing-section-half">
        <div className="landing-container">
          <Reveal>
            <div className="landing-divider" />
            <h2 className="landing-section-title">Why FinSight?</h2>
            <p className="landing-section-subtitle">
              Indian retail investors face unique challenges. We built FinSight to bridge the gap.
            </p>
          </Reveal>

          <div className="landing-ps-grid">
            <Reveal delay={0.1} className="landing-ps-column landing-ps-problem">
              <h3><AlertTriangle size={20} style={{ color: 'var(--danger)' }} /> The Problem</h3>
              {PROBLEMS.map((item, i) => (
                <Reveal key={i} delay={0.15 + i * 0.1}>
                  <div className="landing-ps-item">
                    <div className="landing-ps-icon"><item.icon size={18} /></div>
                    <span>{item.text}</span>
                  </div>
                </Reveal>
              ))}
            </Reveal>

            <Reveal delay={0.2} className="landing-ps-column landing-ps-solution">
              <h3><CheckCircle size={20} style={{ color: 'var(--accent)' }} /> The Solution</h3>
              {SOLUTIONS.map((item, i) => (
                <Reveal key={i} delay={0.25 + i * 0.1}>
                  <div className="landing-ps-item">
                    <div className="landing-ps-icon"><item.icon size={18} /></div>
                    <span>{item.text}</span>
                  </div>
                </Reveal>
              ))}
            </Reveal>
          </div>
        </div>
      </section>

      {/* ═══ FEATURES ═══ */}
      <section className="landing-section-half" style={{ background: 'var(--bg-surface)' }}>
        <div className="landing-container">
          <Reveal>
            <div className="landing-divider" />
            <h2 className="landing-section-title">Key Features</h2>
            <p className="landing-section-subtitle">
              Everything you need to make smarter investment decisions.
            </p>
          </Reveal>

          <div className="landing-features-grid">
            {FEATURES.map((feat, i) => (
              <Reveal key={i} delay={i * 0.08}>
                <GlowCard className="landing-feature-card">
                  <div className="landing-feature-icon">
                    <feat.icon size={22} />
                  </div>
                  <h3>{feat.title}</h3>
                  <p>{feat.desc}</p>
                </GlowCard>
              </Reveal>
            ))}
          </div>
        </div>
      </section>

      {/* ═══ TECH STACK ═══ */}
      <section className="landing-section-half">
        <div className="landing-container">
          <Reveal>
            <div className="landing-divider" />
            <h2 className="landing-section-title">Technology Stack</h2>
            <p className="landing-section-subtitle">
              Built with modern, production-grade technologies.
            </p>
          </Reveal>

          <div className="landing-tech-grid">
            {TECH_STACK.map((cat, i) => (
              <Reveal key={i} delay={i * 0.1}>
                <div className="landing-tech-category">
                  <h4>{cat.category}</h4>
                  <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6 }}>
                    {cat.techs.map((tech, j) => (
                      <span key={j} className="landing-tech-badge">{tech}</span>
                    ))}
                  </div>
                </div>
              </Reveal>
            ))}
          </div>
        </div>
      </section>

      {/* ═══ ARCHITECTURE FLOW ═══ */}
      <section className="landing-section-half" style={{ background: 'var(--bg-surface)' }}>
        <div className="landing-container">
          <Reveal>
            <div className="landing-divider" />
            <h2 className="landing-section-title">How It Works</h2>
            <p className="landing-section-subtitle">
              Three intelligent pipelines working together.
            </p>
          </Reveal>

          <div className="landing-flow">
            {FLOW_PIPELINES.map((pipeline, pi) => (
              <Reveal key={pi} delay={pi * 0.15}>
                <div style={{ marginBottom: 8 }}>
                  <span className="landing-flow-label">{pipeline.label}</span>
                  <div className="landing-flow-row">
                    {pipeline.steps.map((step, si) => (
                      <div key={si} style={{ display: 'contents' }}>
                        {si > 0 && (
                          <div className="landing-flow-arrow">
                            <ChevronRight size={18} />
                          </div>
                        )}
                        <div className="landing-flow-step">{step}</div>
                      </div>
                    ))}
                  </div>
                </div>
              </Reveal>
            ))}
          </div>
        </div>
      </section>

      {/* ═══ USER JOURNEY ═══ */}
      <section className="landing-section-half">
        <div className="landing-container">
          <Reveal>
            <div className="landing-divider" />
            <h2 className="landing-section-title">Your Journey</h2>
            <p className="landing-section-subtitle">
              From setup to insights in four simple steps.
            </p>
          </Reveal>

          <div className="landing-journey-grid">
            {JOURNEY_STEPS.map((step, i) => (
              <Reveal key={i} delay={i * 0.12}>
                <GlowCard className="landing-journey-card">
                  <div className="landing-journey-number">{step.num}</div>
                  <h3>{step.title}</h3>
                  <p>{step.desc}</p>
                </GlowCard>
              </Reveal>
            ))}
          </div>
        </div>
      </section>

      {/* ═══ TEAM ═══ */}
      <section className="landing-section-half" style={{ background: 'var(--bg-surface)' }}>
        <div className="landing-container">
          <Reveal>
            <div className="landing-divider" />
            <h2 className="landing-section-title">Meet the Team</h2>
            <p className="landing-section-subtitle">
              Built with care by a team of three.
            </p>
          </Reveal>

          <div className="landing-team-grid">
            {TEAM.map((member, i) => (
              <Reveal key={i} delay={i * 0.12}>
                <GlowCard className="landing-team-card">
                  <div className="landing-team-avatar">{member.initial}</div>
                  <h3>{member.name}</h3>
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
      <footer className="landing-footer">
        <FinSightLogo size="small" theme={theme} animated={false} />
        <p className="landing-footer-text">
          Built for 8th Semester Project &middot; 2026
        </p>
        <div className="landing-footer-links">
          <Link to="/login">Login</Link>
          <Link to="/register">Register</Link>
        </div>
      </footer>
    </div>
  )
}
