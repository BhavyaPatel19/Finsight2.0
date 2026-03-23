import { useState } from 'react'
import { useNavigate, Link } from 'react-router-dom'
import { useAuth } from '../context/AuthContext'
import { useTheme } from '../context/ThemeContext'
import { LogIn, Moon, Sun } from 'lucide-react'
import { FinSightLogo } from '../components/FinSightLogo'
import { FloatingCurrencies } from '../components/FloatingCurrencies'

export default function Login() {
  const { login } = useAuth()
  const { theme, toggleTheme } = useTheme()
  const isDark = theme === 'dark'
  const navigate = useNavigate()
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)

  const pageBackground = isDark
    ? 'radial-gradient(1200px 600px at 50% -10%, rgba(20,143,119,0.18), transparent 55%), linear-gradient(135deg, #080f1d, #0d1626, #111c2e)'
    : 'linear-gradient(135deg, #f0f4f8, #e8eef5, #dce6f0)'
  const cardBg = isDark ? 'rgba(12, 18, 30, 0.76)' : 'rgba(255, 255, 255, 0.75)'
  const cardBorder = isDark ? '1px solid rgba(148, 163, 184, 0.22)' : '1px solid rgba(213, 221, 229, 0.6)'
  const cardShadow = isDark
    ? '0 12px 42px rgba(2, 6, 23, 0.58), 0 3px 14px rgba(2, 6, 23, 0.35)'
    : '0 8px 32px rgba(27, 42, 74, 0.08), 0 2px 8px rgba(27, 42, 74, 0.04)'
  const headingColor = isDark ? '#E2E8F0' : '#1B2A4A'
  const bodyColor = isDark ? '#94A3B8' : '#5D6D7E'
  const labelColor = isDark ? '#CBD5E1' : '#1B2A4A'
  const inputBg = isDark ? 'rgba(15, 23, 42, 0.66)' : 'rgba(255,255,255,0.8)'
  const inputBorder = isDark ? '1px solid rgba(148,163,184,0.28)' : '1px solid #d5dde5'
  const inputText = isDark ? '#E2E8F0' : '#1B2A4A'

  const handleSubmit = async (e) => {
    e.preventDefault()
    setError(''); setLoading(true)
    try {
      await login(email, password)
      navigate('/dashboard')
    } catch (err) {
      setError(err.response?.data?.detail ?? 'Invalid credentials. Please try again.')
    } finally { setLoading(false) }
  }

  return (
    <div style={{
      minHeight: '100vh',
      width: '100%',
      background: pageBackground,
      display: 'flex',
      flexDirection: 'column',
      alignItems: 'center',
      justifyContent: 'center',
      position: 'relative',
      overflow: 'hidden',
      fontFamily: '-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif',
    }}>
      <button
        className="auth-theme-toggle"
        onClick={toggleTheme}
        aria-label="Toggle theme"
        title={theme === 'dark' ? 'Switch to light mode' : 'Switch to dark mode'}
      >
        {theme === 'dark' ? <Sun size={16} /> : <Moon size={16} />}
      </button>

      {/* Floating currencies background */}
      <FloatingCurrencies theme={theme} />

      {/* Content container */}
      <div style={{
        position: 'relative',
        zIndex: 10,
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        width: '100%',
        maxWidth: '420px',
        padding: '0 24px',
      }}>
        {/* Animated Logo */}
        <div style={{ marginBottom: '32px' }}>
          <FinSightLogo size="xl" showTagline animated theme={theme} />
        </div>

        {/* Login Card */}
        <div style={{
          width: '100%',
          background: cardBg,
          backdropFilter: 'blur(16px)',
          WebkitBackdropFilter: 'blur(16px)',
          borderRadius: '20px',
          border: cardBorder,
          padding: '36px 32px',
          boxShadow: cardShadow,
        }}>
          <div style={{ textAlign: 'center', marginBottom: '28px' }}>
            <h2 style={{
              fontSize: '1.4rem',
              fontWeight: 700,
              color: headingColor,
              margin: 0,
            }}>Welcome back</h2>
            <p style={{
              fontSize: '0.85rem',
              color: bodyColor,
              marginTop: '6px',
            }}>Sign in to your FinSight account</p>
          </div>

          {error && (
            <div style={{
              background: 'rgba(231, 76, 60, 0.08)',
              border: '1px solid rgba(231, 76, 60, 0.2)',
              borderRadius: '10px',
              padding: '10px 14px',
              marginBottom: '20px',
              fontSize: '0.82rem',
              color: '#c0392b',
              display: 'flex',
              alignItems: 'center',
              gap: '8px',
            }}>
              <span>&#9888;</span> {error}
            </div>
          )}

          <form onSubmit={handleSubmit}>
            <div style={{ marginBottom: '18px' }}>
              <label style={{
                display: 'block',
                fontSize: '0.78rem',
                fontWeight: 600,
                color: labelColor,
                marginBottom: '6px',
              }}>Email address</label>
              <input
                id="login-email"
                type="email"
                placeholder="you@example.com"
                value={email}
                onChange={e => setEmail(e.target.value)}
                required
                autoFocus
                style={{
                  width: '100%',
                  padding: '11px 14px',
                  borderRadius: '10px',
                  border: inputBorder,
                  background: inputBg,
                  fontSize: '0.88rem',
                  color: inputText,
                  outline: 'none',
                  transition: 'border-color 0.2s, box-shadow 0.2s',
                  boxSizing: 'border-box',
                }}
                onFocus={e => {
                  e.target.style.borderColor = '#1ABC9C'
                  e.target.style.boxShadow = '0 0 0 3px rgba(26, 188, 156, 0.12)'
                }}
                onBlur={e => {
                  e.target.style.borderColor = isDark ? 'rgba(148,163,184,0.28)' : '#d5dde5'
                  e.target.style.boxShadow = 'none'
                }}
              />
            </div>

            <div style={{ marginBottom: '24px' }}>
              <label style={{
                display: 'block',
                fontSize: '0.78rem',
                fontWeight: 600,
                color: labelColor,
                marginBottom: '6px',
              }}>Password</label>
              <input
                id="login-password"
                type="password"
                placeholder="••••••••"
                value={password}
                onChange={e => setPassword(e.target.value)}
                required
                style={{
                  width: '100%',
                  padding: '11px 14px',
                  borderRadius: '10px',
                  border: inputBorder,
                  background: inputBg,
                  fontSize: '0.88rem',
                  color: inputText,
                  outline: 'none',
                  transition: 'border-color 0.2s, box-shadow 0.2s',
                  boxSizing: 'border-box',
                }}
                onFocus={e => {
                  e.target.style.borderColor = '#1ABC9C'
                  e.target.style.boxShadow = '0 0 0 3px rgba(26, 188, 156, 0.12)'
                }}
                onBlur={e => {
                  e.target.style.borderColor = isDark ? 'rgba(148,163,184,0.28)' : '#d5dde5'
                  e.target.style.boxShadow = 'none'
                }}
              />
            </div>

            {loading ? (
              <button
                type="submit"
                disabled
                className="btn btn-primary"
                style={{ width: '100%', justifyContent: 'center', padding: '12px' }}
              >
                <span className="spinner" /> Signing in...
              </button>
            ) : (
              <button
                id="login-submit"
                type="submit"
                className="btn btn-primary"
                style={{ width: '100%', justifyContent: 'center', padding: '12px' }}
              >
                <LogIn size={15} /> Sign In
              </button>
            )}
          </form>

          <div style={{
            textAlign: 'center',
            marginTop: '22px',
            fontSize: '0.82rem',
            color: bodyColor,
          }}>
            Don't have an account?{' '}
            <Link to="/register" style={{
              color: '#148F77',
              fontWeight: 600,
              textDecoration: 'none',
            }}>Create one</Link>
          </div>
        </div>
      </div>
    </div>
  )
}
