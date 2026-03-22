import { useState, useRef, useEffect } from 'react'
import { useLocation, useNavigate, Link } from 'react-router-dom'
import { motion, AnimatePresence } from 'motion/react'
import {
  LayoutDashboard, FileText, MessageSquare,
  BarChart2, LogOut, Activity, Scale, List,
  User, Settings, ChevronDown,
} from 'lucide-react'
import { useAuth } from '../context/AuthContext'
import { FinSightLogo } from './FinSightLogo'

const NAV = [
  { to: '/', icon: LayoutDashboard, label: 'Dashboard' },
  { to: '/market', icon: Activity, label: 'Market' },
  { to: '/watchlist', icon: List, label: 'Watchlist' },
  { to: '/documents', icon: FileText, label: 'Documents' },
  { to: '/chat', icon: MessageSquare, label: 'Chat' },
  { to: '/credisentiment', icon: Scale, label: 'CrediSentiment' },
  { to: '/portfolio', icon: BarChart2, label: 'Portfolio' },
]

export default function TopNavbar() {
  const { pathname } = useLocation()
  const navigate = useNavigate()
  const { user, logout } = useAuth()
  const [open, setOpen] = useState(false)
  const popoverRef = useRef(null)

  const handleLogout = () => { logout(); navigate('/login') }
  const initial = (user?.email?.[0] ?? 'U').toUpperCase()
  const username = user?.email?.split('@')[0] ?? 'User'
  const email = user?.email ?? ''

  // Close popover on outside click
  useEffect(() => {
    if (!open) return
    const handler = (e) => {
      if (popoverRef.current && !popoverRef.current.contains(e.target)) {
        setOpen(false)
      }
    }
    document.addEventListener('mousedown', handler)
    return () => document.removeEventListener('mousedown', handler)
  }, [open])

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

      {/* Profile popover — right */}
      <div className="topnav-right" ref={popoverRef} style={{ position: 'relative' }}>
        {/* Avatar trigger */}
        <button
          className="topnav-avatar-btn"
          onClick={() => setOpen(v => !v)}
          aria-expanded={open}
          title="Profile"
        >
          <div className="topnav-avatar">{initial}</div>
          <ChevronDown
            size={13}
            style={{
              transition: 'transform 0.25s ease',
              transform: open ? 'rotate(180deg)' : 'rotate(0deg)',
              color: 'var(--text-muted)',
            }}
          />
        </button>

        {/* Popover */}
        <AnimatePresence>
          {open && (
            <motion.div
              className="profile-popover"
              initial={{ opacity: 0, scale: 0.94, y: -8 }}
              animate={{ opacity: 1, scale: 1, y: 0 }}
              exit={{ opacity: 0, scale: 0.94, y: -8 }}
              transition={{ duration: 0.18, ease: [0.16, 1, 0.3, 1] }}
            >
              {/* Header */}
              <div className="profile-popover-header">
                <div className="profile-popover-avatar">{initial}</div>
                <div>
                  <div className="profile-popover-name">{username}</div>
                  <div className="profile-popover-email">{email}</div>
                </div>
              </div>

              {/* Menu items */}
              <div className="profile-popover-body">
                <button className="profile-popover-item" onClick={() => setOpen(false)}>
                  <User size={15} />
                  <span>View Profile</span>
                </button>
                <button className="profile-popover-item" onClick={() => setOpen(false)}>
                  <Settings size={15} />
                  <span>Settings</span>
                </button>
              </div>

              {/* Footer — Sign Out */}
              <div className="profile-popover-footer">
                <button
                  className="profile-popover-signout"
                  onClick={handleLogout}
                >
                  <LogOut size={15} />
                  <span>Sign Out</span>
                </button>
              </div>
            </motion.div>
          )}
        </AnimatePresence>
      </div>
    </nav>
  )
}
