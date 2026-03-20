import { useLocation, useNavigate, Link } from 'react-router-dom'
import {
  LayoutDashboard, FileText, MessageSquare,
  BarChart2, LogOut, Activity, Scale
} from 'lucide-react'
import { useAuth } from '../context/AuthContext'

const NAV = [
  { to: '/', icon: LayoutDashboard, label: 'Dashboard' },
  { to: '/market', icon: Activity, label: 'Live Market' },
  { to: '/documents', icon: FileText, label: 'Documents' },
  { to: '/chat', icon: MessageSquare, label: 'RAG Chat' },
  { to: '/credisentiment', icon: Scale, label: 'CrediSentiment' },
  { to: '/portfolio', icon: BarChart2, label: 'Portfolio' },
]

export default function Sidebar() {
  const { pathname } = useLocation()
  const navigate = useNavigate()
  const { user, logout } = useAuth()

  const handleLogout = () => { logout(); navigate('/login') }

  const initial = (user?.email?.[0] ?? 'U').toUpperCase()

  return (
    <aside className="sidebar">
      <div className="sidebar-logo">
        <div className="sidebar-logo-icon">💹</div>
        <span className="sidebar-logo-text">FinSight</span>
      </div>

      {NAV.map(({ to, icon: Icon, label }) => (
        <Link
          key={to}
          to={to}
          className={`nav-link ${pathname === to ? 'active' : ''}`}
        >
          <Icon className="nav-icon" size={17} />
          {label}
        </Link>
      ))}

      <div className="sidebar-spacer" />

      <div className="sidebar-user">
        <div className="sidebar-avatar">{initial}</div>
        <div className="sidebar-user-info">
          <div className="sidebar-user-name">{user?.email ?? 'User'}</div>
          <div className="sidebar-user-role">Analyst</div>
        </div>
      </div>

      <button
        className="nav-link btn-danger"
        style={{ marginTop: 6, width: '100%', border: 'none', background: 'transparent' }}
        onClick={handleLogout}
      >
        <LogOut size={16} /> Logout
      </button>
    </aside>
  )
}
