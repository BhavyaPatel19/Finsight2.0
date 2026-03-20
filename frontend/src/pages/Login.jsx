import { useState } from 'react'
import { useNavigate, Link } from 'react-router-dom'
import { useAuth } from '../context/AuthContext'
import { LogIn } from 'lucide-react'
import { FinSightLogo } from '../components/FinSightLogo'
import { FloatingCurrencies } from '../components/FloatingCurrencies'
import HoverButton from '../components/HoverButton'

export default function Login() {
  const { login } = useAuth()
  const navigate = useNavigate()
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)

  const handleSubmit = async (e) => {
    e.preventDefault()
    setError(''); setLoading(true)
    try {
      await login(email, password)
      navigate('/')
    } catch (err) {
      setError(err.response?.data?.detail ?? 'Invalid credentials. Please try again.')
    } finally { setLoading(false) }
  }

  return (
    <div style={{
      minHeight: '100vh',
      width: '100%',
      background: 'linear-gradient(135deg, #f0f4f8, #e8eef5, #dce6f0)',
      display: 'flex',
      flexDirection: 'column',
      alignItems: 'center',
      justifyContent: 'center',
      position: 'relative',
      overflow: 'hidden',
      fontFamily: '-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif',
    }}>
      {/* Floating currencies background */}
      <FloatingCurrencies />

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
          <FinSightLogo size="xl" showTagline animated />
        </div>

        {/* Login Card */}
        <div style={{
          width: '100%',
          background: 'rgba(255, 255, 255, 0.75)',
          backdropFilter: 'blur(16px)',
          WebkitBackdropFilter: 'blur(16px)',
          borderRadius: '20px',
          border: '1px solid rgba(213, 221, 229, 0.6)',
          padding: '36px 32px',
          boxShadow: '0 8px 32px rgba(27, 42, 74, 0.08), 0 2px 8px rgba(27, 42, 74, 0.04)',
        }}>
          <div style={{ textAlign: 'center', marginBottom: '28px' }}>
            <h2 style={{
              fontSize: '1.4rem',
              fontWeight: 700,
              color: '#1B2A4A',
              margin: 0,
            }}>Welcome back</h2>
            <p style={{
              fontSize: '0.85rem',
              color: '#5D6D7E',
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
                color: '#1B2A4A',
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
                  border: '1px solid #d5dde5',
                  background: 'rgba(255,255,255,0.8)',
                  fontSize: '0.88rem',
                  color: '#1B2A4A',
                  outline: 'none',
                  transition: 'border-color 0.2s, box-shadow 0.2s',
                  boxSizing: 'border-box',
                }}
                onFocus={e => {
                  e.target.style.borderColor = '#1ABC9C'
                  e.target.style.boxShadow = '0 0 0 3px rgba(26, 188, 156, 0.12)'
                }}
                onBlur={e => {
                  e.target.style.borderColor = '#d5dde5'
                  e.target.style.boxShadow = 'none'
                }}
              />
            </div>

            <div style={{ marginBottom: '24px' }}>
              <label style={{
                display: 'block',
                fontSize: '0.78rem',
                fontWeight: 600,
                color: '#1B2A4A',
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
                  border: '1px solid #d5dde5',
                  background: 'rgba(255,255,255,0.8)',
                  fontSize: '0.88rem',
                  color: '#1B2A4A',
                  outline: 'none',
                  transition: 'border-color 0.2s, box-shadow 0.2s',
                  boxSizing: 'border-box',
                }}
                onFocus={e => {
                  e.target.style.borderColor = '#1ABC9C'
                  e.target.style.boxShadow = '0 0 0 3px rgba(26, 188, 156, 0.12)'
                }}
                onBlur={e => {
                  e.target.style.borderColor = '#d5dde5'
                  e.target.style.boxShadow = 'none'
                }}
              />
            </div>

            {loading ? (
              <button
                type="submit"
                disabled
                style={{
                  width: '100%', padding: '12px', borderRadius: '10px', border: 'none',
                  background: 'linear-gradient(135deg, #1A5276, #148F77)', color: 'white',
                  fontSize: '0.9rem', fontWeight: 600, cursor: 'not-allowed', opacity: 0.7,
                  display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '8px',
                }}
              >
                <span className="spinner" /> Signing in...
              </button>
            ) : (
              <HoverButton
                id="login-submit"
                type="submit"
                text="Sign In"
                icon={LogIn}
                style={{ width: '100%', borderRadius: '10px', fontSize: '0.9rem', padding: '12px' }}
              />
            )}
          </form>

          <div style={{
            textAlign: 'center',
            marginTop: '22px',
            fontSize: '0.82rem',
            color: '#5D6D7E',
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
