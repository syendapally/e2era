import { useEffect, useMemo, useState } from 'react'
import './App.css'

const tabs = [
  { id: 'projects', label: 'Projects', body: '' },
  { id: 'account', label: 'Account', body: 'Sign in or create an account.' },
  { id: 'overview', label: 'Overview', body: 'E2ERA is an end-to-end research agent: plan, experiment, code, and draft papers with your uploaded context.' },
]

function App() {
  const [activeTab, setActiveTab] = useState('projects')
  const [apiMessage, setApiMessage] = useState('Checking backend...')
  const [user, setUser] = useState(null)
  const [authError, setAuthError] = useState('')
  const [authLoading, setAuthLoading] = useState(false)
  const [formState, setFormState] = useState({ username: '', password: '' })
  const [mode, setMode] = useState('login')
  const [email, setEmail] = useState('')
  const [projects, setProjects] = useState([])
  const [projectError, setProjectError] = useState('')
  const [newProjectTitle, setNewProjectTitle] = useState('')
  const [showCreate, setShowCreate] = useState(false)
  const [selectedProject, setSelectedProject] = useState(null)
  const [projectView, setProjectView] = useState('list') // 'list' | 'detail'
  const [agentData, setAgentData] = useState({ plan: null })
  const [agentLoading, setAgentLoading] = useState(false)
  const [agentError, setAgentError] = useState('')
  const [noteText, setNoteText] = useState('')
  const [uploading, setUploading] = useState(false)
  const [savingNote, setSavingNote] = useState(false)
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
        loadProjects()
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
        loadProjects()
      })
      .catch((err) => setAuthError(err.message))
      .finally(() => setAuthLoading(false))
  }

  const logout = () => {
    setAuthLoading(true)
    fetch('/api/auth/logout/', { method: 'POST', credentials: 'include' })
      .then(() => {
        setUser(null)
        setProjects([])
        setSelectedProject(null)
      })
      .finally(() => setAuthLoading(false))
  }

  const loadProjects = () => {
    setProjectError('')
    fetch('/api/projects/', { credentials: 'include' })
      .then((res) => {
        if (!res.ok) throw new Error('failed to load projects')
        return res.json()
      })
      .then((data) => {
        setProjects(data.projects || [])
        if (data.projects?.length) {
          setSelectedProject((prev) => prev || data.projects[0])
        } else {
          setSelectedProject(null)
          setProjectView('list')
        }
      })
      .catch(() => setProjectError('Could not load projects'))
  }

  const createProject = (e) => {
    e.preventDefault()
    if (!newProjectTitle.trim()) return
    setProjectError('')
    fetch('/api/projects/', {
      method: 'POST',
      credentials: 'include',
      headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
      body: new URLSearchParams({ title: newProjectTitle.trim() }),
    })
      .then((res) => res.json())
      .then((data) => {
        if (data.error) throw new Error(data.error)
        const proj = data.project
        setProjects((prev) => [proj, ...prev])
        setSelectedProject(proj)
        setNewProjectTitle('')
        setShowCreate(false)
        setProjectView('detail')
        setAgentData({ plan: null, code: null, report: null })
      })
      .catch((err) => setProjectError(err.message))
  }

  const uploadDoc = async (e) => {
    e.preventDefault()
    if (!selectedProject) return
    const file = e.target.file?.files?.[0]
    if (!file) return
    setUploading(true)
    const formData = new FormData()
    formData.append('file', file)
    try {
      const res = await fetch(`/api/projects/${selectedProject.id}/upload/`, {
        method: 'POST',
        credentials: 'include',
        body: formData,
      })
      const text = await res.text()
      let data = {}
      try {
        data = JSON.parse(text)
      } catch {
        throw new Error('Upload failed (unexpected response)')
      }
      if (!res.ok || data.error) throw new Error(data.error || 'Upload failed')
      setProjects((prev) =>
        prev.map((p) =>
          p.id === selectedProject.id
            ? { ...p, documents: [data.document, ...(p.documents || [])] }
            : p,
        ),
      )
      setSelectedProject((prev) =>
        prev ? { ...prev, documents: [data.document, ...(prev.documents || [])] } : prev,
      )
      e.target.reset()
    } catch (err) {
      setProjectError(err.message)
    } finally {
      setUploading(false)
    }
  }

  const saveNote = async (e) => {
    e.preventDefault()
    if (!selectedProject || !noteText.trim()) return
    setSavingNote(true)
    try {
      const res = await fetch(`/api/projects/${selectedProject.id}/notes/`, {
        method: 'POST',
        credentials: 'include',
        headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
        body: new URLSearchParams({ content: noteText.trim() }),
      })
      const text = await res.text()
      let data = {}
      try {
        data = JSON.parse(text)
      } catch {
        throw new Error('Save failed (unexpected response)')
      }
      if (!res.ok || data.error) throw new Error(data.error || 'Save failed')
      setProjects((prev) =>
        prev.map((p) =>
          p.id === selectedProject.id
            ? { ...p, notes: [data.note, ...(p.notes || [])] }
            : p,
        ),
      )
      setSelectedProject((prev) =>
        prev ? { ...prev, notes: [data.note, ...(prev.notes || [])] } : prev,
      )
      setNoteText('')
    } catch (err) {
      setProjectError(err.message)
    } finally {
      setSavingNote(false)
    }
  }

  const fetchAgentData = async (projectId) => {
    setAgentError('')
    try {
      const res = await fetch(`/api/projects/${projectId}/agent/data/`, {
        method: 'GET',
        credentials: 'include',
      })
      const data = await res.json()
      if (!res.ok || data.error) throw new Error(data.error || 'Failed to load agent data')
      setAgentData({
        plan: data.plan || null,
      })
    } catch (err) {
      setAgentError(err.message)
    }
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
        loadProjects()
      })
      .catch((err) => setAuthError(err.message))
      .finally(() => setAuthLoading(false))
  }

  const renderAccount = () => (
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

  const renderProjects = () => (
    <div className="panel">
      {projectView === 'list' ? (
        <>
          <div className="project-header">
            <div>
              <p className="muted">Workspace</p>
              <h3>Your research projects</h3>
            </div>
            <button
              type="button"
              className="icon-button"
              onClick={() => setShowCreate((v) => !v)}
              title="Create project"
            >
              +
              <span className="icon-label">New project</span>
            </button>
          </div>

          {!user ? (
            <p className="muted">Sign in to manage your projects.</p>
          ) : (
            <>
              {showCreate ? (
                <form className="card-box" onSubmit={createProject}>
                  <div className="field">
                    <label htmlFor="project-title">New project title</label>
                    <input
                      id="project-title"
                      name="project-title"
                      value={newProjectTitle}
                      onChange={(e) => setNewProjectTitle(e.target.value)}
                      placeholder="My research project"
                      required
                    />
                  </div>
                  <button type="submit" className="btn primary">
                    Create project
                  </button>
                  {projectError ? <div className="error">{projectError}</div> : null}
                </form>
              ) : null}

              <div className="project-grid">
                {projects.map((p) => (
                  <button
                    key={p.id}
                    type="button"
                    className={
                      selectedProject?.id === p.id
                        ? 'project-card selected'
                        : 'project-card'
                    }
                    onClick={() => {
                      setSelectedProject(p)
                      setProjectView('detail')
                      fetchAgentData(p.id)
                    }}
                  >
                <div className="project-title">{p.title}</div>
                <div className="project-meta">
                  {(p.documents?.length || 0)} docs · {(p.notes?.length || 0)} notes
                </div>
                  </button>
                ))}
                {!projects.length ? (
                  <p className="muted">No projects yet. Click “New project” to start.</p>
                ) : null}
              </div>
            </>
          )}
        </>
      ) : null}

      {projectView === 'detail' && selectedProject ? (
        <div className="project-detail">
          <div className="project-detail-header">
            <div>
              <p className="muted">Project</p>
              <h3>{selectedProject.title}</h3>
            </div>
            <div className="actions-row">
              <button
                type="button"
                className="btn tertiary"
                onClick={() => {
                  setSelectedProject(null)
                  setProjectView('list')
                  setAgentData({ plan: null })
                }}
              >
                Back to projects
              </button>
              <button
                type="button"
                className="btn primary"
                disabled={agentLoading}
                onClick={async () => {
                  if (!selectedProject) return
                  setAgentError('')
                  setAgentLoading(true)
                  try {
                    const res = await fetch(
                      `/api/projects/${selectedProject.id}/agent/run/`,
                      { method: 'POST', credentials: 'include' },
                    )
                    const data = await res.json()
                    if (!res.ok || data.error) throw new Error(data.error || 'Agent failed')
                    setAgentData({
                      plan: data.plan || null,
                    })
                  } catch (err) {
                    setAgentError(err.message)
                  } finally {
                    setAgentLoading(false)
                  }
                }}
              >
                {agentLoading ? 'Running...' : 'Run agent'}
              </button>
            </div>
          </div>
          <div className="project-columns">
            <div className="column">
              <h4>Documents</h4>
              <form className="upload-box" onSubmit={uploadDoc}>
                <input type="file" name="file" accept=".pdf,.txt,.doc,.docx" />
                <button
                  type="submit"
                  className="btn primary"
                  disabled={uploading}
                >
                  {uploading ? 'Uploading...' : 'Upload'}
                </button>
              </form>
              <ul className="doc-list">
                {(selectedProject.documents || []).map((doc) => (
                  <li key={doc.id}>
                    <a href={doc.url} target="_blank" rel="noreferrer">
                      {doc.name}
                    </a>
                  </li>
                ))}
                {!(selectedProject.documents || []).length ? (
                  <p className="muted">No documents yet.</p>
                ) : null}
              </ul>
            </div>
            <div className="column">
              <h4>Research notes</h4>
              <form className="card-box" onSubmit={saveNote}>
                <div className="field">
                  <label htmlFor="note">What do you want to research?</label>
                  <textarea
                    id="note"
                    name="note"
                    rows={4}
                    value={noteText}
                    onChange={(e) => setNoteText(e.target.value)}
                  />
                </div>
                <button
                  type="submit"
                  className="btn primary"
                  disabled={savingNote}
                >
                  {savingNote ? 'Saving...' : 'Save note'}
                </button>
              </form>
              <ul className="note-list">
                {(selectedProject.notes || []).map((note) => (
                  <li key={note.id}>
                    <div className="note-text">{note.content}</div>
                    <div className="muted">{note.created_at}</div>
                  </li>
                ))}
                {!(selectedProject.notes || []).length ? (
                  <p className="muted">No notes yet.</p>
                ) : null}
              </ul>
            </div>
            <div className="column">
              <h4>Agent output</h4>
              {agentError ? <div className="error">{agentError}</div> : null}
              <div className="card-box">
                <p className="muted">Plan</p>
                {agentData.plan ? (
                  <ul className="note-list">
                    {(agentData.plan.plan || []).map((step, idx) => (
                      <li key={idx}>{step}</li>
                    ))}
                    {agentData.plan.summary ? (
                      <li className="muted">Summary: {agentData.plan.summary}</li>
                    ) : null}
                  </ul>
                ) : (
                  <p className="muted">No plan yet.</p>
                )}
              </div>
            </div>
          </div>
        </div>
      ) : null}
    </div>
  )

  return (
    <div className="page">
      <header className="hero">
        <div>
          <p className="eyebrow">End-to-End Research Agent</p>
          <h1>E2ERA</h1>
          <p className="subtitle">
            Plan, run, and compile research with code, experiments, and papers—backed by your uploaded sources.
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

      {activeTab === 'projects' ? renderProjects() : null}
      {activeTab === 'account' ? renderAccount() : null}
      {activeTab === 'overview' ? (
        <section className="panel">
          <h2>{currentTab.label}</h2>
          <p>{currentTab.body}</p>
        </section>
      ) : null}
    </div>
  )
}

export default App
