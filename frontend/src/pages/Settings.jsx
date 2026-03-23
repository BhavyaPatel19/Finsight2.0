import { useMemo, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { AlertTriangle, Save } from 'lucide-react'
import { useAuth } from '../context/AuthContext'

export default function Settings() {
  const { user, updateAccount, deleteAccount } = useAuth()
  const navigate = useNavigate()

  const [firstName, setFirstName] = useState(user?.first_name || '')
  const [lastName, setLastName] = useState(user?.last_name || '')
  const [email, setEmail] = useState(user?.email || '')
  const [password, setPassword] = useState('')
  const [confirmPassword, setConfirmPassword] = useState('')
  const [loading, setLoading] = useState(false)
  const [deleting, setDeleting] = useState(false)
  const [error, setError] = useState('')
  const [success, setSuccess] = useState('')

  const hasChanges = useMemo(() => {
    return (
      firstName.trim() !== (user?.first_name || '') ||
      lastName.trim() !== (user?.last_name || '') ||
      email.trim() !== (user?.email || '') ||
      password.length > 0
    )
  }, [firstName, lastName, email, password, user])

  const handleSave = async (e) => {
    e.preventDefault()
    setError('')
    setSuccess('')

    if (!firstName.trim() || !lastName.trim()) {
      setError('First name and last name are required.')
      return
    }

    if (password) {
      if (password.length < 6) {
        setError('New password must be at least 6 characters.')
        return
      }
      if (password !== confirmPassword) {
        setError('Password confirmation does not match.')
        return
      }
    }

    const payload = {
      first_name: firstName.trim(),
      last_name: lastName.trim(),
      email: email.trim(),
    }
    if (password) payload.password = password

    setLoading(true)
    try {
      await updateAccount(payload)
      setPassword('')
      setConfirmPassword('')
      setSuccess('Your account details have been updated.')
    } catch (err) {
      setError(err.response?.data?.detail ?? 'Failed to update account details.')
    } finally {
      setLoading(false)
    }
  }

  const handleDelete = async () => {
    const ok = window.confirm('Are you sure you want to delete your account? This cannot be undone.')
    if (!ok) return

    setDeleting(true)
    setError('')
    setSuccess('')
    try {
      await deleteAccount()
      navigate('/register')
    } catch (err) {
      setError(err.response?.data?.detail ?? 'Failed to delete account.')
      setDeleting(false)
    }
  }

  const labelStyle = {
    display: 'block',
    fontSize: 12,
    fontWeight: 600,
    color: 'var(--text-secondary)',
    marginBottom: 6,
  }

  const inputStyle = {
    width: '100%',
    padding: '11px 12px',
    borderRadius: 10,
    border: '1px solid var(--input-border)',
    background: 'var(--input-bg)',
    color: 'var(--text-primary)',
    outline: 'none',
  }

  return (
    <div>
      <header className="page-header">
        <h1 className="page-title">Settings</h1>
        <p className="page-sub">Update all your account details or delete your account.</p>
      </header>

      <section className="card" style={{ maxWidth: 760, marginBottom: 18 }}>
        <h3 style={{ marginBottom: 14 }}>Account Details</h3>

        {error && (
          <div style={{
            marginBottom: 12,
            padding: '10px 12px',
            borderRadius: 10,
            border: '1px solid rgba(239, 68, 68, 0.4)',
            background: 'rgba(239, 68, 68, 0.1)',
            color: 'var(--danger)',
            fontSize: 13,
          }}>
            {error}
          </div>
        )}

        {success && (
          <div style={{
            marginBottom: 12,
            padding: '10px 12px',
            borderRadius: 10,
            border: '1px solid rgba(16, 185, 129, 0.35)',
            background: 'rgba(16, 185, 129, 0.12)',
            color: 'var(--success)',
            fontSize: 13,
          }}>
            {success}
          </div>
        )}

        <form onSubmit={handleSave}>
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12 }}>
            <div>
              <label htmlFor="settings-first-name" style={labelStyle}>First Name</label>
              <input
                id="settings-first-name"
                type="text"
                value={firstName}
                onChange={(e) => setFirstName(e.target.value)}
                style={inputStyle}
                required
              />
            </div>
            <div>
              <label htmlFor="settings-last-name" style={labelStyle}>Last Name</label>
              <input
                id="settings-last-name"
                type="text"
                value={lastName}
                onChange={(e) => setLastName(e.target.value)}
                style={inputStyle}
                required
              />
            </div>
          </div>

          <div style={{ marginTop: 12 }}>
            <label htmlFor="settings-email" style={labelStyle}>Email</label>
            <input
              id="settings-email"
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              style={inputStyle}
              required
            />
          </div>

          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12, marginTop: 12 }}>
            <div>
              <label htmlFor="settings-password" style={labelStyle}>New Password</label>
              <input
                id="settings-password"
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                placeholder="Leave blank to keep current password"
                style={inputStyle}
              />
            </div>
            <div>
              <label htmlFor="settings-confirm" style={labelStyle}>Confirm Password</label>
              <input
                id="settings-confirm"
                type="password"
                value={confirmPassword}
                onChange={(e) => setConfirmPassword(e.target.value)}
                placeholder="Confirm new password"
                style={inputStyle}
              />
            </div>
          </div>

          <button
            type="submit"
            disabled={loading || !hasChanges}
            style={{
              marginTop: 16,
              border: '1px solid var(--border)',
              background: hasChanges ? 'var(--accent)' : 'var(--bg-card)',
              color: hasChanges ? '#fff' : 'var(--text-secondary)',
              borderRadius: 10,
              padding: '10px 16px',
              fontWeight: 600,
              cursor: hasChanges && !loading ? 'pointer' : 'not-allowed',
              display: 'inline-flex',
              gap: 8,
              alignItems: 'center',
            }}
          >
            <Save size={15} />
            {loading ? 'Saving...' : 'Save Changes'}
          </button>
        </form>
      </section>

      <section className="card" style={{ maxWidth: 760, borderColor: 'rgba(239,68,68,0.35)' }}>
        <h3 style={{ marginBottom: 8, color: 'var(--danger)' }}>Danger Zone</h3>
        <p style={{ color: 'var(--text-secondary)', fontSize: 13, marginBottom: 12 }}>
          Deleting your account is permanent. All associated data will be removed.
        </p>
        <button
          type="button"
          onClick={handleDelete}
          disabled={deleting}
          style={{
            border: '1px solid rgba(239,68,68,0.5)',
            background: 'rgba(239,68,68,0.12)',
            color: 'var(--danger)',
            borderRadius: 10,
            padding: '10px 16px',
            fontWeight: 700,
            cursor: deleting ? 'not-allowed' : 'pointer',
            display: 'inline-flex',
            gap: 8,
            alignItems: 'center',
          }}
        >
          <AlertTriangle size={15} />
          {deleting ? 'Deleting...' : 'Delete Account'}
        </button>
      </section>
    </div>
  )
}
