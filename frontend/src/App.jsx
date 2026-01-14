import { useEffect, useMemo, useState } from 'react'
import './App.css'

const tabs = [
  { id: 'projects', label: 'Projects', body: '' },
  { id: 'fraud', label: 'Fraud detection', body: 'Score inpatient facility claims with our XGBoost model.' },
  { id: 'account', label: 'Account', body: 'Sign in or create an account.' },
  { id: 'overview', label: 'Overview', body: 'E2ERA is an end-to-end research agent: plan, experiment, code, and draft papers with your uploaded context.' },
]

const defaultClaim = {
  claim_amount: '',
  paid_amount: '',
  drg_code: '',
  primary_diagnosis: '',
  primary_procedure: '',
  admission_type: '',
  admission_source: '',
  discharge_disposition: '',
  length_of_stay: '',
  patient_age: '',
  gender: '',
  num_diagnoses: '',
  num_procedures: '',
  provider_state: '',
  payer: '',
}

const claimFields = [
  { name: 'claim_amount', label: 'Claim amount ($)', type: 'number' },
  { name: 'paid_amount', label: 'Paid amount ($)', type: 'number' },
  { name: 'drg_code', label: 'DRG code', type: 'text' },
  { name: 'primary_diagnosis', label: 'Primary diagnosis', type: 'text' },
  { name: 'primary_procedure', label: 'Primary procedure', type: 'text' },
  { name: 'admission_type', label: 'Admission type', type: 'text' },
  { name: 'admission_source', label: 'Admission source', type: 'text' },
  { name: 'discharge_disposition', label: 'Discharge disposition', type: 'text' },
  { name: 'length_of_stay', label: 'Length of stay (days)', type: 'number' },
  { name: 'patient_age', label: 'Patient age', type: 'number' },
  { name: 'gender', label: 'Gender', type: 'text' },
  { name: 'num_diagnoses', label: '# of diagnoses codes', type: 'number' },
  { name: 'num_procedures', label: '# of procedure codes', type: 'number' },
  { name: 'provider_state', label: 'Provider state', type: 'text' },
  { name: 'payer', label: 'Payer', type: 'text' },
]

const numericClaimFields = claimFields.filter((f) => f.type === 'number').map((f) => f.name)

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
  const [agentData, setAgentData] = useState({ answer: null, code: null, exec: null })
  const [agentLoading, setAgentLoading] = useState(false)
  const [agentError, setAgentError] = useState('')
  const [noteText, setNoteText] = useState('')
  const [uploading, setUploading] = useState(false)
  const [savingNote, setSavingNote] = useState(false)
  const [claimInput, setClaimInput] = useState(defaultClaim)
  const [fraudResult, setFraudResult] = useState(null)
  const [fraudError, setFraudError] = useState('')
  const [fraudLoading, setFraudLoading] = useState(false)
  const [fraudFeatures, setFraudFeatures] = useState([])
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

  useEffect(() => {
    fetch('/api/fraud/model/')
      .then((res) => res.json())
      .then((data) => {
        setFraudFeatures(data?.features || [])
      })
      .catch(() => {
        setFraudFeatures([])
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
        setAgentData({ plan: null, code: null, exec: null })
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
        answer: data.answer || null,
        code: data.code || null,
        exec: data.exec || null,
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

  const handleClaimChange = (e) => {
    const { name, value } = e.target
    setClaimInput((prev) => ({ ...prev, [name]: value }))
  }

  const resetFraudForm = () => {
    setClaimInput(defaultClaim)
    setFraudResult(null)
    setFraudError('')
  }

  const submitFraud = async (e) => {
    e.preventDefault()
    setFraudError('')
    setFraudLoading(true)
    setFraudResult(null)
    const normalizedClaim = Object.fromEntries(
      Object.entries(claimInput).map(([key, value]) => {
        if (value === '') return [key, null]
        if (numericClaimFields.includes(key)) {
          const numericValue = Number(value)
          return [key, Number.isNaN(numericValue) ? null : numericValue]
        }
        return [key, value]
      }),
    )
    try {
      const res = await fetch('/api/fraud/predict/', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ claims: [normalizedClaim] }),
      })
      const text = await res.text()
      let data = {}
      try {
        data = JSON.parse(text)
      } catch {
        throw new Error('Prediction failed (unexpected response)')
      }
      if (!res.ok || data.error) {
        throw new Error(data.error || 'Prediction failed')
      }
      const firstPrediction = data.predictions?.[0]
      setFraudResult(firstPrediction ? { ...firstPrediction, threshold: data.threshold } : null)
    } catch (err) {
      setFraudError(err.message)
    } finally {
      setFraudLoading(false)
    }
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
                      setAgentData({ answer: null, code: null, exec: null })
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
                      answer: data.answer || null,
                      code: data.code || null,
                      exec: data.exec || null,
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
                <p className="muted">Answer</p>
                {agentData.answer ? (
                  <p>{agentData.answer}</p>
                ) : (
                  <p className="muted">No answer yet.</p>
                )}
              </div>
              <div className="card-box">
                <p className="muted">Code (if generated)</p>
                {agentData.code ? (
                  <>
                    <pre className="code-block">
                      {agentData.code.content || agentData.code}
                    </pre>
                    {agentData.code.status ? (
                      <p className="muted">Status: {agentData.code.status}</p>
                    ) : null}
                  </>
                ) : (
                  <p className="muted">No code yet.</p>
                )}
              </div>
              <div className="card-box">
                <p className="muted">Execution (if run)</p>
                {agentData.exec ? (
                  <>
                    <p className="muted">stdout</p>
                    <pre className="code-block">{agentData.exec.stdout || '(empty)'}</pre>
                    <p className="muted">stderr</p>
                    <pre className="code-block">{agentData.exec.stderr || '(empty)'}</pre>
                  </>
                ) : (
                  <p className="muted">No execution yet.</p>
                )}
              </div>
            </div>
          </div>
        </div>
      ) : null}
    </div>
  )

  const renderFraud = () => (
    <div className="panel">
      <h2>Fraud detection</h2>
      <p className="muted">
        Enter inpatient claim details. We will compute the fraud probability with the XGBoost model
        trained on the Kaggle enhanced health insurance claims dataset.
      </p>
      <div className="project-columns">
        <div className="column">
          <form className="card-box" onSubmit={submitFraud}>
            <div className="field-grid">
              {claimFields.map((field) => (
                <div className="field" key={field.name}>
                  <label htmlFor={field.name}>{field.label}</label>
                  <input
                    id={field.name}
                    name={field.name}
                    type={field.type}
                    value={claimInput[field.name]}
                    onChange={handleClaimChange}
                    placeholder={field.type === 'number' ? '0' : ''}
                  />
                </div>
              ))}
            </div>
            {fraudError ? <div className="error">{fraudError}</div> : null}
            <div className="actions-row">
              <button type="submit" className="btn primary" disabled={fraudLoading}>
                {fraudLoading ? 'Scoring...' : 'Score claim'}
              </button>
              <button type="button" className="btn tertiary" onClick={resetFraudForm}>
                Reset
              </button>
            </div>
          </form>
        </div>
        <div className="column">
          <div className="card-box">
            <h4>Model output</h4>
            {fraudResult ? (
              <>
                <p className="muted">Fraud probability</p>
                <div className="prediction-value">
                  {(fraudResult.fraud_probability * 100).toFixed(1)}%
                </div>
                <p className="muted">
                  Decision: <strong>{fraudResult.label.toUpperCase()}</strong>{' '}
                  {fraudResult.threshold !== undefined
                    ? `(threshold ${Math.round(fraudResult.threshold * 100)}%)`
                    : null}
                </p>
              </>
            ) : (
              <p className="muted">No prediction yet.</p>
            )}
          </div>
          <div className="card-box">
            <h4>Signals we use</h4>
            <ul className="note-list">
              {fraudFeatures.length
                ? fraudFeatures.map((feature) => (
                    <li key={feature.name}>
                      <div className="note-text">
                        <strong>{feature.name}</strong> — {feature.reason}
                      </div>
                    </li>
                  ))
                : (
                  <p className="muted">Feature list unavailable.</p>
                )}
            </ul>
          </div>
        </div>
      </div>
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
      {activeTab === 'fraud' ? renderFraud() : null}
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
