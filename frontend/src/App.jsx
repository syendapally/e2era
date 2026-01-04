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
    body: 'Account is a placeholder for future auth flows.',
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
  const [activeTab, setActiveTab] = useState('overview')
  const [apiMessage, setApiMessage] = useState('Checking backend...')
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
        <div className="badge">{apiMessage}</div>
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

      <section className="panel">
        <h2>{currentTab.label}</h2>
        <p>{currentTab.body}</p>
      </section>
    </div>
  )
}

export default App
