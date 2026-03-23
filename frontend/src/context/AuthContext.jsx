import { createContext, useContext, useState, useEffect } from 'react'
import { authApi } from '../api/client'

const AuthContext = createContext(null)

export function AuthProvider({ children }) {
  const [user, setUser] = useState(() => {
    try { return JSON.parse(localStorage.getItem('fs_user')) } catch { return null }
  })
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    const token = localStorage.getItem('fs_token')
    if (!token) { setLoading(false); return }
    authApi.me()
      .then(r => { setUser(r.data); localStorage.setItem('fs_user', JSON.stringify(r.data)) })
      .catch(() => { localStorage.removeItem('fs_token'); localStorage.removeItem('fs_user'); setUser(null) })
      .finally(() => setLoading(false))
  }, [])

  const refreshUser = async () => {
    const me = await authApi.me()
    localStorage.setItem('fs_user', JSON.stringify(me.data))
    setUser(me.data)
    return me.data
  }

  const login = async (email, password) => {
    const r = await authApi.login(email, password)
    const token = r.data.access_token
    localStorage.setItem('fs_token', token)
    const me = await authApi.me()
    localStorage.setItem('fs_user', JSON.stringify(me.data))
    setUser(me.data)
    return me.data
  }

  const register = async (firstName, lastName, email, password) => {
    await authApi.register(firstName, lastName, email, password)
    return login(email, password)
  }

  const updateAccount = async (payload) => {
    const r = await authApi.updateMe(payload)
    localStorage.setItem('fs_user', JSON.stringify(r.data))
    setUser(r.data)
    return r.data
  }

  const deleteAccount = async () => {
    await authApi.deleteMe()
    logout()
  }

  const logout = () => {
    localStorage.removeItem('fs_token')
    localStorage.removeItem('fs_user')
    setUser(null)
  }

  return (
    <AuthContext.Provider value={{ user, loading, login, register, logout, refreshUser, updateAccount, deleteAccount }}>
      {children}
    </AuthContext.Provider>
  )
}

export function useAuth() {
  return useContext(AuthContext)
}
