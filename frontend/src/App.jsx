import { useEffect, useMemo, useState } from 'react'
import './App.css'

const tabs = [
  {
    id: 'overview',
    label: 'Overview',
    body: 'Hello world from E2ERA. This is a React + Django + Nginx starter.',
  },
  {
    id: 'account',
    label: 'Account',
    body: 'Sign in or create an account to see your session info.',
  },
  {
    id: 'settings',
    label: 'Settings',
    body: 'Keep environment-driven settings in AWS Secrets Manager.',
  },
  {
    id: 'support',
    label: 'Support',
    body: 'Add docs, links, or contact details here.',
  },
]

function App() {
  const [activeTab, setActiveTab] = useState('account')
  const [apiMessage, setApiMessage] = useState('Checking backend...')
  const [user, setUser] = useState(null)
  const [authError, setAuthError] = useState('')
  const [authLoading, setAuthLoading] = useState(false)
  const [formState, setFormState] = useState({ username: '', password: '' })
  const [mode, setMode] = useState('login')
  const [email, setEmail] = useState('')
  const currentTab = useMemo(
    () => tabs.find((tab) => tab.id === activeTab) ?? tabs[0],
    [activeTab],
  )

  useEffect(() => {
    fetch('/api/hello/')
      .then((res) => res.json())
      .then((data) => {
        setApiMessage(data?.message ?? 'Backend responded')
      })
      .catch(() => {
        setApiMessage('Backend unreachable')
      })
  }, [])

  useEffect(() => {
    fetch('/api/auth/me/', { credentials: 'include' })
      .then((res) => {
        if (!res.ok) throw new Error('not authed')
        return res.json()
      })
      .then((data) => {
        setUser(data.user)
      })
      .catch(() => {
        setUser(null)
      })
  }, [])

  const handleInput = (e) => {
    setFormState((prev) => ({ ...prev, [e.target.name]: e.target.value }))
  }

  const login = (e) => {
    e.preventDefault()
    setAuthError('')
    setAuthLoading(true)
    const body = new URLSearchParams({
      username: formState.username,
      password: formState.password,
    })
    fetch('/api/auth/login/', {
      method: 'POST',
      credentials: 'include',
      headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
      body,
    })
      .then(async (res) => {
        const data = await res.json().catch(() => ({}))
        if (!res.ok) {
          throw new Error(data?.error || 'Login failed')
        }
        setUser(data.user)
        setFormState({ username: '', password: '' })
      })
      .catch((err) => setAuthError(err.message))
      .finally(() => setAuthLoading(false))
  }

  const logout = () => {
    setAuthLoading(true)
    fetch('/api/auth/logout/', { method: 'POST', credentials: 'include' })
      .then(() => {
        setUser(null)
      })
      .finally(() => setAuthLoading(false))
  }

  const register = (e) => {
    e.preventDefault()
    setAuthError('')
    setAuthLoading(true)
    const body = new URLSearchParams({
      username: formState.username,
      password: formState.password,
      email,
    })
    fetch('/api/auth/register/', {
      method: 'POST',
      credentials: 'include',
      headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
      body,
    })
      .then(async (res) => {
        const data = await res.json().catch(() => ({}))
        if (!res.ok) {
          throw new Error(data?.error || 'Registration failed')
        }
        setUser(data.user)
        setFormState({ username: '', password: '' })
        setEmail('')
      })
      .catch((err) => setAuthError(err.message))
      .finally(() => setAuthLoading(false))
  }

  const renderPanel = () => {
    if (currentTab.id === 'account') {
      return (
        <div className="panel">
          <h2>Account</h2>
          {user ? (
            <div className="card-box">
              <p className="muted">Signed in as</p>
              <div className="user-row">
                <div>
                  <div className="user-name">{user.username}</div>
                  {user.email ? <div className="muted">{user.email}</div> : null}
                </div>
                <button
                  type="button"
                  className="btn secondary"
                  onClick={logout}
                  disabled={authLoading}
                >
                  {authLoading ? 'Signing out...' : 'Sign out'}
                </button>
              </div>
            </div>
          ) : (
            <form
              className="card-box"
              onSubmit={mode === 'login' ? login : register}
            >
              <div className="field">
                <label htmlFor="username">Username</label>
                <input
                  id="username"
                  name="username"
                  autoComplete="username"
                  value={formState.username}
                  onChange={handleInput}
                  required
                />
              </div>
              {mode === 'register' ? (
                <div className="field">
                  <label htmlFor="email">Email (optional)</label>
                  <input
                    id="email"
                    name="email"
                    type="email"
                    autoComplete="email"
                    value={email}
                    onChange={(e) => setEmail(e.target.value)}
                  />
                </div>
              ) : null}
              <div className="field">
                <label htmlFor="password">Password</label>
                <input
                  id="password"
                  name="password"
                  type="password"
                  autoComplete="current-password"
                  value={formState.password}
                  onChange={handleInput}
                  required
                />
              </div>
              {authError ? <div className="error">{authError}</div> : null}
              <div className="actions-row">
                <button
                  type="submit"
                  className="btn primary"
                  disabled={authLoading}
                >
                  {authLoading
                    ? mode === 'login'
                      ? 'Signing in...'
                      : 'Creating...'
                    : mode === 'login'
                      ? 'Sign in'
                      : 'Create account'}
                </button>
                <button
                  type="button"
                  className="btn tertiary"
                  onClick={() => {
                    setMode((m) => (m === 'login' ? 'register' : 'login'))
                    setAuthError('')
                  }}
                >
                  {mode === 'login'
                    ? 'Need an account? Register'
                    : 'Have an account? Sign in'}
                </button>
              </div>
            </form>
          )}
        </div>
      )
    }

    return (
      <section className="panel">
        <h2>{currentTab.label}</h2>
        <p>{currentTab.body}</p>
      </section>
    )
  }

  return (
    <div className="page">
      <header className="hero">
        <div>
          <p className="eyebrow">E2E Ready App</p>
          <h1>E2ERA</h1>
          <p className="subtitle">
            React frontend, Django backend, Nginx edge. Docker Compose ready.
          </p>
        </div>
        <div className="hero-right">
          {user ? (
            <div className="user-chip">
              <div className="dot" />
              <div className="user-chip-text">
                <div className="user-name">{user.username}</div>
                {user.email ? <div className="muted">{user.email}</div> : null}
              </div>
            </div>
          ) : (
            <div className="badge">{apiMessage}</div>
          )}
        </div>
      </header>

      <nav className="tabs">
        {tabs.map((tab) => (
          <button
            key={tab.id}
            className={tab.id === activeTab ? 'tab active' : 'tab'}
            onClick={() => setActiveTab(tab.id)}
            type="button"
          >
            {tab.label}
          </button>
        ))}
      </nav>

      {renderPanel()}
    </div>
  )
}

export default App
