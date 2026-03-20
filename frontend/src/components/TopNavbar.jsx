import { useLocation, useNavigate, Link } from 'react-router-dom'
import { motion } from 'motion/react'
import {
  LayoutDashboard, FileText, MessageSquare,
  BarChart2, LogOut, Activity, Scale
} from 'lucide-react'
import { useAuth } from '../context/AuthContext'
import { FinSightLogo } from './FinSightLogo'

const NAV = [
  { to: '/', icon: LayoutDashboard, label: 'Dashboard' },
  { to: '/market', icon: Activity, label: 'Market' },
  { to: '/documents', icon: FileText, label: 'Documents' },
  { to: '/chat', icon: MessageSquare, label: 'Chat' },
  { to: '/credisentiment', icon: Scale, label: 'CrediSentiment' },
  { to: '/portfolio', icon: BarChart2, label: 'Portfolio' },
]

export default function TopNavbar() {
  const { pathname } = useLocation()
  const navigate = useNavigate()
  const { user, logout } = useAuth()

  const handleLogout = () => { logout(); navigate('/login') }
  const initial = (user?.email?.[0] ?? 'U').toUpperCase()

  return (
    <nav className="topnav">
      {/* Logo — left */}
      <Link to="/" className="topnav-logo">
        <FinSightLogo size="small" animated theme="dark" />
      </Link>

      {/* Tubelight pill — center */}
      <div className="topnav-pill">
        {NAV.map(({ to, icon: Icon, label }) => {
          const isActive = pathname === to
          return (
            <Link
              key={to}
              to={to}
              className={`topnav-item ${isActive ? 'active' : ''}`}
            >
              <span className="topnav-item-label">{label}</span>
              <span className="topnav-item-icon">
                <Icon size={18} strokeWidth={2.5} />
              </span>

              {isActive && (
                <motion.div
                  layoutId="tubelight"
                  className="topnav-glow"
                  initial={false}
                  transition={{ type: 'spring', stiffness: 300, damping: 30 }}
                >
                  {/* The lamp bar */}
                  <div className="topnav-lamp">
                    <div className="topnav-lamp-blur1" />
                    <div className="topnav-lamp-blur2" />
                    <div className="topnav-lamp-blur3" />
                  </div>
                </motion.div>
              )}
            </Link>
          )
        })}
      </div>

      {/* Profile + logout — right */}
      <div className="topnav-right">
        <div className="topnav-profile">
          <div className="topnav-avatar">{initial}</div>
          <span className="topnav-username">{user?.email?.split('@')[0] ?? 'User'}</span>
        </div>
        <button className="topnav-logout" onClick={handleLogout} title="Logout">
          <LogOut size={16} />
        </button>
      </div>
    </nav>
  )
}
