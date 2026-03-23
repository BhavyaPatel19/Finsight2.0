import { useMemo } from 'react'
import { User, Mail, CalendarClock, Clock3 } from 'lucide-react'
import { useAuth } from '../context/AuthContext'

function formatDate(value) {
  if (!value) return 'Not available'
  const d = new Date(value)
  if (Number.isNaN(d.getTime())) return 'Not available'
  return d.toLocaleString()
}

export default function Profile() {
  const { user } = useAuth()

  const fullName = useMemo(() => {
    const name = `${user?.first_name ?? ''} ${user?.last_name ?? ''}`.trim()
    return name || 'User'
  }, [user])

  const infoRows = [
    { icon: User, label: 'First Name', value: user?.first_name || 'Not set' },
    { icon: User, label: 'Last Name', value: user?.last_name || 'Not set' },
    { icon: Mail, label: 'Email', value: user?.email || 'Not set' },
    { icon: CalendarClock, label: 'Created At', value: formatDate(user?.created_at) },
    { icon: Clock3, label: 'Last Login', value: formatDate(user?.last_login_at) },
  ]

  return (
    <div>
      <header className="page-header">
        <h1 className="page-title">Profile</h1>
        <p className="page-sub">View your account details.</p>
      </header>

      <section className="card" style={{ maxWidth: 760 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 14, marginBottom: 18 }}>
          <div
            style={{
              width: 52,
              height: 52,
              borderRadius: '50%',
              display: 'grid',
              placeItems: 'center',
              color: '#fff',
              fontWeight: 700,
              background: 'linear-gradient(135deg, #1A5276, var(--accent))',
            }}
          >
            {(fullName[0] || 'U').toUpperCase()}
          </div>
          <div>
            <div style={{ fontSize: 19, fontWeight: 700 }}>{fullName}</div>
            <div style={{ fontSize: 13, color: 'var(--text-secondary)' }}>{user?.email}</div>
          </div>
        </div>

        <div style={{ display: 'grid', gap: 12 }}>
          {infoRows.map(({ icon: Icon, label, value }) => (
            <div
              key={label}
              style={{
                display: 'grid',
                gridTemplateColumns: '28px 160px 1fr',
                alignItems: 'center',
                gap: 8,
                background: 'var(--bg-card)',
                border: '1px solid var(--border)',
                borderRadius: 12,
                padding: '11px 12px',
              }}
            >
              <Icon size={16} color="var(--accent-light)" />
              <span style={{ color: 'var(--text-secondary)', fontSize: 13 }}>{label}</span>
              <span style={{ color: 'var(--text-primary)', fontWeight: 600 }}>{value}</span>
            </div>
          ))}
        </div>
      </section>
    </div>
  )
}
