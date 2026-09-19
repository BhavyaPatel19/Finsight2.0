import { useState } from 'react'
import { useNavigate, Link } from 'react-router-dom'
import { useAuth } from '../context/AuthContext'
import { useTheme } from '../context/ThemeContext'
import { Check, ArrowRight, Moon, Sun } from 'lucide-react'
import { FinSightLogo } from '../components/FinSightLogo'
import { FloatingCurrencies } from '../components/FloatingCurrencies'

export default function Register() {
  const { register } = useAuth()
  const { theme, toggleTheme } = useTheme()
  const navigate = useNavigate()
  const [currentStep, setCurrentStep] = useState(0)
  const [isComplete, setIsComplete] = useState(false)
  const [firstName, setFirstName] = useState('')
  const [lastName, setLastName] = useState('')
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [confirm, setConfirm] = useState('')
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)

  const steps = [
    { id: 1, label: 'Name' },
    { id: 2, label: 'Email' },
    { id: 3, label: 'Password' },
  ]

  const progress = ((currentStep + 1) / steps.length) * 100

  const validateStep = () => {
    setError('')
    if (currentStep === 0) {
      if (!firstName.trim() || !lastName.trim()) {
        setError('First name and last name are required.')
        return false
      }
      return true
    }

    if (currentStep === 1) {
      if (!email.trim()) {
        setError('Email is required.')
        return false
      }
      return true
    }

    if (!password || !confirm) {
      setError('Password and confirm password are required.')
      return false
    }
    if (password !== confirm) {
      setError('Passwords do not match.')
      return false
    }
    if (password.length < 8) {
      setError('Password must be at least 8 characters.')
      return false
    }
    return true
  }

  const handleContinue = async (e) => {
    e.preventDefault()
    if (!validateStep()) return

    if (currentStep < steps.length - 1) {
      setCurrentStep(s => s + 1)
      return
    }

    setLoading(true)
    try {
      await register(firstName.trim(), lastName.trim(), email, password)
      setIsComplete(true)
    } catch (err) {
      setError(err.response?.data?.detail ?? 'Registration failed. Please try again.')
    } finally { setLoading(false) }
  }

  const goBack = () => {
    if (currentStep > 0) setCurrentStep(s => s - 1)
  }

  const fullName = `${firstName} ${lastName}`.trim()

  const renderStepFields = () => {
    if (currentStep === 0) {
      return (
        <div className="register-step-grid">
          <input
            id="reg-first-name"
            type="text"
            placeholder="First name"
            value={firstName}
            onChange={e => setFirstName(e.target.value)}
            className="form-control register-step-input"
            autoFocus
          />
          <input
            id="reg-last-name"
            type="text"
            placeholder="Last name"
            value={lastName}
            onChange={e => setLastName(e.target.value)}
            className="form-control register-step-input"
          />
        </div>
      )
    }

    if (currentStep === 1) {
      return (
        <input
          id="reg-email"
          type="email"
          placeholder="you@example.com"
          value={email}
          onChange={e => setEmail(e.target.value)}
          className="form-control register-step-input"
          autoFocus
        />
      )
    }

    return (
      <div className="register-step-stack">
        <input
          id="reg-password"
          type="password"
          placeholder="Password (min 8 characters)"
          value={password}
          onChange={e => setPassword(e.target.value)}
          className="form-control register-step-input"
          autoFocus
        />
        <input
          id="reg-confirm"
          type="password"
          placeholder="Confirm password"
          value={confirm}
          onChange={e => setConfirm(e.target.value)}
          className="form-control register-step-input"
        />
      </div>
    )
  }

  return (
    <div className="auth-layout register-layout">
      <button
        className="auth-theme-toggle"
        onClick={toggleTheme}
        aria-label="Toggle theme"
        title={theme === 'dark' ? 'Switch to light mode' : 'Switch to dark mode'}
      >
        {theme === 'dark' ? <Sun size={16} /> : <Moon size={16} />}
      </button>

      <FloatingCurrencies theme={theme} />

      <div className="register-shell">
        <div className="register-logo">
          <FinSightLogo size="xl" showTagline animated theme={theme} />
        </div>

        <div className="register-wizard">
          {isComplete ? (
            <div className="register-complete">
              <div className="register-complete-icon-wrap">
                <Check size={34} strokeWidth={2.6} />
              </div>
              <h2 className="register-complete-title">You're all set</h2>
              <p className="register-complete-sub">{fullName || email}</p>
              <button
                className="btn btn-primary register-next-btn"
                onClick={() => navigate('/dashboard')}
              >
                Go to Dashboard <ArrowRight size={16} />
              </button>
            </div>
          ) : (
            <>
              <div className="register-stepper">
                {steps.map((step, index) => (
                  <div key={step.id} className="register-stepper-item">
                    <button
                      type="button"
                      className={`register-step-dot ${index < currentStep ? 'done' : ''} ${index === currentStep ? 'active' : ''}`}
                      disabled={index > currentStep}
                      onClick={() => index < currentStep && setCurrentStep(index)}
                    >
                      {index < currentStep ? <Check size={15} strokeWidth={2.8} /> : <span>{step.id}</span>}
                    </button>
                    {index < steps.length - 1 && (
                      <div className="register-step-line">
                        <div
                          className="register-step-line-active"
                          style={{ transform: `scaleX(${index < currentStep ? 1 : 0})` }}
                        />
                      </div>
                    )}
                  </div>
                ))}
              </div>

              <div className="register-progress-wrap">
                <div className="register-progress" style={{ width: `${progress}%` }} />
              </div>

              <form onSubmit={handleContinue} className="register-step-content">
                <div className="register-step-header">
                  <label className="register-step-label">{steps[currentStep].label}</label>
                  <span className="register-step-count">{currentStep + 1}/{steps.length}</span>
                </div>

                {renderStepFields()}

                {error && <p className="register-step-error">{error}</p>}

                <button
                  id="reg-submit"
                  type="submit"
                  className="btn btn-primary register-next-btn"
                  disabled={loading}
                >
                  {loading ? <span className="spinner" style={{ width: 16, height: 16, borderWidth: 2 }} /> : null}
                  {loading ? 'Creating account...' : (currentStep === steps.length - 1 ? 'Complete' : 'Continue')}
                  {!loading && <ArrowRight size={16} />}
                </button>

                {currentStep > 0 && (
                  <button
                    type="button"
                    className="register-back-btn"
                    onClick={goBack}
                  >
                    Go back
                  </button>
                )}
              </form>
            </>
          )}

          {!isComplete && (
            <div className="auth-switch" style={{ marginTop: 18 }}>
              Already have an account? <Link to="/login">Sign in</Link>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
