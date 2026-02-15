import { useState } from 'react'
import { Shield, Wifi, WifiOff, Play, Trash2, Zap, LayoutDashboard, GitBranch, ListChecks, Users } from 'lucide-react'
import AgentCard from './AgentCard.jsx'
import AgentFlow from './AgentFlow.jsx'
import IncidentList from './IncidentList.jsx'
import Timeline from './Timeline.jsx'
import MCPFlowView from './MCPFlowView.jsx'
import ExecutionPlan from './ExecutionPlan.jsx'
import AgentRegistry from './AgentRegistry.jsx'

const SCENARIOS = [
  { label: 'CPU Spike',    index: 0 },
  { label: 'Memory Leak',  index: 1 },
  { label: 'High Errors',  index: 2 },
  { label: 'Latency',      index: 3 },
  { label: 'DB Pool',      index: 4 },
  { label: 'CrashLoop',    index: 5 },
  { label: '502 Gateway',  index: 6 },
  { label: 'DB Replica',   index: 7 },
]

const TABS = [
  { id: 'overview',   label: 'Overview',      icon: <LayoutDashboard size={13} /> },
  { id: 'agent-flow', label: 'Agent Flow',    icon: <GitBranch size={13} /> },
  { id: 'plan',       label: 'Exec Plan',     icon: <ListChecks size={13} /> },
  { id: 'registry',   label: 'Registry',      icon: <Users size={13} /> },
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
  // New props for MCP/Framework
  mcpEvents,
  executionPlan,
  registryAgents,
  onTriggerTool,
  resolvedCount,
  avgMttrSec,
}) {
  const resolved   = incidents.filter(i => i.status === 'RESOLVED').length
  const active     = incidents.filter(i => !['RESOLVED', 'ROLLED_BACK', 'FAILED'].includes(i.status)).length
  const rolledBack = incidents.filter(i => i.status === 'ROLLED_BACK').length
  const critical   = incidents.filter(i => i.severity === 'critical').length

  // Default to "Agent Flow" tab when there's an active incident, else "Overview"
  const defaultTab = activeIncident && !['RESOLVED', 'ROLLED_BACK', 'FAILED'].includes(activeIncident.status)
    ? 'agent-flow'
    : 'overview'
  const [activeTab, setActiveTab] = useState(defaultTab)

  // Count active MCP calls
  const activeMcpCalls = (mcpEvents || []).filter(e => e.status === 'in_progress').length

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
            <p className="text-xs text-gray-500">Multi-Agent Auto-Remediation • MCP + Agent Framework</p>
          </div>
        </div>

        <div className="flex items-center gap-3">
          {activeMcpCalls > 0 && (
            <div className="flex items-center gap-1.5 px-2.5 py-1.5 rounded-full border bg-yellow-500/10 border-yellow-500/30 text-xs font-semibold text-yellow-400 animate-pulse">
              <span className="h-1.5 w-1.5 rounded-full bg-yellow-400" />
              {activeMcpCalls} MCP
            </div>
          )}
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
      <div className="grid grid-cols-4 gap-3 mb-5">
        <StatBadge label="Total"    value={incidents.length} color="text-gray-300" />
        <StatBadge label="Active"   value={active}   color={active > 0 ? 'text-orange-400' : 'text-gray-500'} />
        <StatBadge label="Resolved" value={resolved} color={resolved > 0 ? 'text-neon-green' : 'text-gray-500'} />
        <StatBadge label="Critical" value={critical} color={critical > 0 ? 'text-neon-red' : 'text-gray-500'} />
      </div>

      {/* Agent Cards */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mb-5">
        {Object.keys(agentStatuses).map(agentName => (
          <AgentCard key={agentName} agentName={agentName} agentStatus={agentStatuses[agentName]} />
        ))}
      </div>

      {/* Tabs */}
      <div className="flex items-center gap-1 mb-4 border-b border-dark-500">
        {TABS.map(tab => {
          const hasAlert = tab.id === 'agent-flow' && activeMcpCalls > 0
          return (
            <button
              key={tab.id}
              onClick={() => setActiveTab(tab.id)}
              className={`flex items-center gap-1.5 px-3 py-2 text-xs font-semibold border-b-2 transition-colors -mb-px ${
                activeTab === tab.id
                  ? 'border-neon-blue text-neon-blue'
                  : 'border-transparent text-gray-500 hover:text-gray-300'
              }`}
            >
              {tab.icon}
              {tab.label}
              {hasAlert && (
                <span className="h-1.5 w-1.5 rounded-full bg-yellow-400 animate-pulse" />
              )}
            </button>
          )
        })}
      </div>

      {/* Tab content */}
      {activeTab === 'overview' && (
        <div className="space-y-4">
          {/* Agent Flow pipeline */}
          <div className="mb-2">
            <AgentFlow activeIncident={activeIncident} agentStatuses={agentStatuses} />
          </div>

          {/* Incidents + Timeline */}
          <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
            <div className="card lg:col-span-1">
              <div className="flex items-center justify-between mb-3">
                <h2 className="text-xs font-bold text-gray-400 uppercase tracking-widest">Incidents</h2>
                {active > 0 && (
                  <span className="flex items-center gap-1 text-xs text-orange-400">
                    <span className="relative flex h-1.5 w-1.5">
                      <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-orange-400 opacity-75" />
                      <span className="relative inline-flex rounded-full h-1.5 w-1.5 bg-orange-400" />
                    </span>
                    {active} active
                  </span>
                )}
              </div>
              <IncidentList incidents={incidents} activeIncident={activeIncident} onSelectIncident={onSelectIncident} />
            </div>
            <div className="card lg:col-span-2">
              <Timeline incident={activeIncident} />
            </div>
          </div>
        </div>
      )}

      {activeTab === 'agent-flow' && (
        <div className="card">
          <div className="flex items-center justify-between mb-4">
            <h2 className="text-xs font-bold text-gray-400 uppercase tracking-widest">
              MCP Agent Communication
            </h2>
            <div className="flex items-center gap-2 text-xs text-gray-500">
              <span>{(mcpEvents || []).length} calls total</span>
              {activeIncident && <span className="text-gray-600">| {activeIncident.id}</span>}
            </div>
          </div>
          <MCPFlowView
            mcpEvents={mcpEvents || []}
            agentStatuses={agentStatuses}
            activeIncident={activeIncident}
          />
        </div>
      )}

      {activeTab === 'plan' && (
        <div className="card">
          <div className="flex items-center justify-between mb-4">
            <h2 className="text-xs font-bold text-gray-400 uppercase tracking-widest">
              Execution Plan — TaskPlanner
            </h2>
            {executionPlan && (
              <span className="text-xs text-gray-500 font-mono">{executionPlan.plan_id}</span>
            )}
          </div>
          <ExecutionPlan executionPlan={executionPlan} />

          {/* Also show timeline for context */}
          {activeIncident && (
            <div className="mt-4 pt-4 border-t border-dark-500">
              <h3 className="text-xs font-bold text-gray-400 uppercase tracking-widest mb-3">
                Agent Timeline
              </h3>
              <Timeline incident={activeIncident} />
            </div>
          )}
        </div>
      )}

      {activeTab === 'registry' && (
        <div className="card">
          <div className="flex items-center justify-between mb-4">
            <h2 className="text-xs font-bold text-gray-400 uppercase tracking-widest">
              Agent Registry — Capabilities & MCP Tools
            </h2>
          </div>
          <AgentRegistry
            registryAgents={registryAgents || []}
            onTriggerTool={onTriggerTool}
          />
        </div>
      )}

      {/* Simulate controls */}
      <div className="card mt-4">
        <div className="flex flex-wrap items-center gap-3">
          <div className="flex items-center gap-2">
            <Zap size={14} className="text-neon-blue" />
            <span className="text-xs font-bold text-gray-400 uppercase tracking-wider">Simulate</span>
          </div>
          <button onClick={() => onSimulate(null)} className="btn-primary flex items-center gap-1.5">
            <Play size={12} />
            Random
          </button>
          <div className="flex items-center gap-1.5 flex-wrap">
            {SCENARIOS.map(s => (
              <button
                key={s.index}
                onClick={() => onSimulate(s.index)}
                className="px-2.5 py-1.5 rounded-lg bg-dark-600 border border-dark-400 hover:border-gray-500 text-xs text-gray-400 hover:text-gray-200 transition-colors"
              >
                {s.label}
              </button>
            ))}
          </div>
          {events.length > 0 && (
            <div className="ml-auto text-xs text-gray-600 font-mono max-w-xs truncate">
              ▶ {events[0]?.message}
            </div>
          )}
        </div>
      </div>

      <footer className="mt-4 text-center text-xs text-gray-700">
        CodeOps Sentinel v2.0 • Azure MCP Server + Microsoft Agent Framework + Azure AI Foundry
      </footer>
    </div>
  )
}
