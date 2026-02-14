import { Shield, Wifi, WifiOff, Play, Trash2, Zap, AlertTriangle, CheckCircle2, RotateCcw } from 'lucide-react'
import AgentCard from './AgentCard.jsx'
import AgentFlow from './AgentFlow.jsx'
import IncidentList from './IncidentList.jsx'
import Timeline from './Timeline.jsx'

const SCENARIOS = [
  { label: 'CPU Spike', index: 0 },
  { label: 'Memory Leak', index: 1 },
  { label: 'DB Pool', index: 2 },
  { label: 'Latency', index: 3 },
  { label: 'CI/CD Fail', index: 4 },
]

function StatBadge({ label, value, color }) {
  return (
    <div className="text-center px-3 py-2 rounded-lg bg-dark-600/50 border border-dark-400/50">
      <div className={`text-lg font-bold font-mono ${color}`}>{value}</div>
      <div className="text-xs text-gray-500">{label}</div>
    </div>
  )
}

export default function Dashboard({
  incidents,
  agentStatuses,
  wsConnected,
  events,
  activeIncident,
  onSelectIncident,
  onSimulate,
  onClear,
}) {
  const resolved = incidents.filter(i => i.status === 'RESOLVED').length
  const active = incidents.filter(i => !['RESOLVED', 'ROLLED_BACK', 'FAILED'].includes(i.status)).length
  const rolledBack = incidents.filter(i => i.status === 'ROLLED_BACK').length
  const critical = incidents.filter(i => i.severity === 'critical').length

  return (
    <div className="min-h-screen bg-dark-900 p-4 md:p-6">
      {/* Header */}
      <header className="flex items-center justify-between mb-6">
        <div className="flex items-center gap-3">
          <div className="p-2.5 rounded-xl bg-neon-blue/10 border border-neon-blue/30 glow-blue">
            <Shield size={22} className="text-neon-blue" />
          </div>
          <div>
            <h1 className="text-lg font-bold text-white tracking-tight">
              CodeOps <span className="text-neon-blue text-glow-blue">Sentinel</span>
            </h1>
            <p className="text-xs text-gray-500">Multi-Agent Auto-Remediation Platform</p>
          </div>
        </div>

        <div className="flex items-center gap-3">
          {/* WS Status */}
          <div className={`flex items-center gap-1.5 px-3 py-1.5 rounded-full border text-xs font-semibold ${
            wsConnected
              ? 'bg-neon-green/10 border-neon-green/30 text-neon-green'
              : 'bg-red-500/10 border-red-500/30 text-red-400'
          }`}>
            {wsConnected ? <Wifi size={11} /> : <WifiOff size={11} />}
            {wsConnected ? 'Live' : 'Offline'}
          </div>

          <button onClick={onClear} className="btn-danger flex items-center gap-1.5">
            <Trash2 size={13} />
            Clear
          </button>
        </div>
      </header>

      {/* Stats row */}
      <div className="grid grid-cols-4 gap-3 mb-6">
        <StatBadge label="Total" value={incidents.length} color="text-gray-300" />
        <StatBadge label="Active" value={active} color={active > 0 ? 'text-orange-400' : 'text-gray-500'} />
        <StatBadge label="Resolved" value={resolved} color={resolved > 0 ? 'text-neon-green' : 'text-gray-500'} />
        <StatBadge label="Critical" value={critical} color={critical > 0 ? 'text-neon-red' : 'text-gray-500'} />
      </div>

      {/* Agent Cards */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mb-6">
        {Object.keys(agentStatuses).map(agentName => (
          <AgentCard
            key={agentName}
            agentName={agentName}
            agentStatus={agentStatuses[agentName]}
          />
        ))}
      </div>

      {/* Agent Flow */}
      <div className="mb-6">
        <AgentFlow activeIncident={activeIncident} agentStatuses={agentStatuses} />
      </div>

      {/* Main content: 3-column grid */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4 mb-6">
        {/* Incidents */}
        <div className="card lg:col-span-1">
          <div className="flex items-center justify-between mb-3">
            <h2 className="text-xs font-bold text-gray-400 uppercase tracking-widest">Incidents</h2>
            {active > 0 && (
              <span className="flex items-center gap-1 text-xs text-orange-400">
                <span className="relative flex h-1.5 w-1.5">
                  <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-orange-400 opacity-75"></span>
                  <span className="relative inline-flex rounded-full h-1.5 w-1.5 bg-orange-400"></span>
                </span>
                {active} active
              </span>
            )}
          </div>
          <IncidentList
            incidents={incidents}
            activeIncident={activeIncident}
            onSelectIncident={onSelectIncident}
          />
        </div>

        {/* Timeline */}
        <div className="card lg:col-span-2">
          <Timeline incident={activeIncident} />
        </div>
      </div>

      {/* Simulate controls */}
      <div className="card">
        <div className="flex flex-wrap items-center gap-3">
          <div className="flex items-center gap-2">
            <Zap size={14} className="text-neon-blue" />
            <span className="text-xs font-bold text-gray-400 uppercase tracking-wider">Simulate Incident</span>
          </div>

          <button
            onClick={() => onSimulate(null)}
            className="btn-primary flex items-center gap-1.5"
          >
            <Play size={12} />
            Random
          </button>

          <div className="flex items-center gap-2 flex-wrap">
            {SCENARIOS.map(s => (
              <button
                key={s.index}
                onClick={() => onSimulate(s.index)}
                className="px-3 py-1.5 rounded-lg bg-dark-600 border border-dark-400 hover:border-gray-500 text-xs text-gray-400 hover:text-gray-200 transition-colors"
              >
                {s.label}
              </button>
            ))}
          </div>

          {/* Live event log */}
          {events.length > 0 && (
            <div className="ml-auto text-xs text-gray-600 font-mono max-w-xs truncate">
              ▶ {events[0]?.message}
            </div>
          )}
        </div>
      </div>

      {/* Footer */}
      <footer className="mt-4 text-center text-xs text-gray-700">
        CodeOps Sentinel v1.0 • Built with FastAPI + React + Azure AI Foundry + GitHub Copilot
      </footer>
    </div>
  )
}
