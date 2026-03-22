import { Routes, Route, Navigate } from 'react-router-dom'
import { useAuth } from './context/AuthContext'
import TopNavbar from './components/TopNavbar'
import { FinSightLogo } from './components/FinSightLogo'
import { FloatingCurrencies } from './components/FloatingCurrencies'
import Login from './pages/Login'
import Register from './pages/Register'
import Dashboard from './pages/Dashboard'
import Documents from './pages/Documents'
import Chat from './pages/Chat'
import Portfolio from './pages/Portfolio'
import Market from './pages/Market'
import CredibilitySentiment from './pages/CredibilitySentiment'
import Watchlist from './pages/Watchlist'

function ProtectedLayout({ children }) {
  const { user, loading } = useAuth()
  if (loading) return (
    <div style={{ minHeight: '100vh', display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', gap: 20, background: '#080c14' }}>
      <FinSightLogo size="large" showTagline animated />
      <span className="spinner" style={{ width: 32, height: 32, borderWidth: 3 }} />
    </div>
  )
  if (!user) return <Navigate to="/login" replace />
  return (
    <div className="app-shell">
      <FloatingCurrencies theme="dark" />
      <TopNavbar />
      <main className="main-content">{children}</main>
    </div>
  )
}

export default function App() {
  return (
    <Routes>
      <Route path="/login" element={<Login />} />
      <Route path="/register" element={<Register />} />

      <Route path="/" element={<ProtectedLayout><Dashboard /></ProtectedLayout>} />
      <Route path="/documents" element={<ProtectedLayout><Documents /></ProtectedLayout>} />
      <Route path="/chat" element={<ProtectedLayout><Chat /></ProtectedLayout>} />
      <Route path="/credisentiment" element={<ProtectedLayout><CredibilitySentiment /></ProtectedLayout>} />
      <Route path="/portfolio" element={<ProtectedLayout><Portfolio /></ProtectedLayout>} />
      <Route path="/market" element={<ProtectedLayout><Market /></ProtectedLayout>} />
      <Route path="/watchlist" element={<ProtectedLayout><Watchlist /></ProtectedLayout>} />

      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  )
}
