import { useState } from 'react'
import {
  Shield, Wifi, WifiOff, Trash2,
  LayoutDashboard, GitBranch, ListChecks, Users, History,
} from 'lucide-react'
import AgentCard from './AgentCard.jsx'
import AgentFlow from './AgentFlow.jsx'
import IncidentList from './IncidentList.jsx'
import Timeline from './Timeline.jsx'
import MCPFlowView from './MCPFlowView.jsx'
import ExecutionPlan from './ExecutionPlan.jsx'
import AgentRegistry from './AgentRegistry.jsx'
import Overview from './Overview.jsx'
import IncidentHistory from './IncidentHistory.jsx'
import SimulateButton from './SimulateButton.jsx'
import StatusBadge from './common/StatusBadge.jsx'

/* ─── Nav config ─────────────────────────────────────────────────────────────── */
const NAV = [
  { id: 'overview',   label: 'Overview',    icon: LayoutDashboard },
  { id: 'agent-flow', label: 'Agent Flow',  icon: GitBranch       },
  { id: 'plan',       label: 'Exec Plan',   icon: ListChecks      },
  { id: 'registry',   label: 'Registry',    icon: Users           },
  { id: 'history',    label: 'History',     icon: History         },
]

/* ─── Sidebar ────────────────────────────────────────────────────────────────── */
function Sidebar({ activeTab, onTab, hasAlert }) {
  return (
    <aside className="app-sidebar flex flex-col items-center py-3 gap-1 border-r border-dark-400/40 bg-dark-900/80 backdrop-blur-sm">
      {/* Logo */}
      <div className="p-2 mb-3">
        <div className="w-8 h-8 rounded-xl bg-neon-blue/15 border border-neon-blue/30 flex items-center justify-center glow-blue">
          <Shield size={16} className="text-neon-blue" />
        </div>
      </div>

      {/* Nav items */}
      {NAV.map(item => {
        const Icon    = item.icon
        const isAlert = item.id === 'agent-flow' && hasAlert
        return (
          <button
            key={item.id}
            onClick={() => onTab(item.id)}
            className={`nav-item ${activeTab === item.id ? 'active' : ''}`}
            data-tooltip={item.label}
          >
            <Icon size={17} />
            {isAlert && (
              <span className="absolute top-1 right-1 w-2 h-2 rounded-full bg-yellow-400 animate-pulse" />
            )}
          </button>
        )
      })}
    </aside>
  )
}

/* ─── Header ─────────────────────────────────────────────────────────────────── */
function Header({ wsConnected, activeMcpCalls, onClear, activeTabLabel }) {
  return (
    <header className="app-header flex items-center justify-between px-5 border-b border-dark-400/30 bg-dark-900/60 backdrop-blur-sm">
      <div className="flex items-center gap-3">
        <h1 className="text-sm font-bold text-white tracking-tight hidden sm:block">
          CodeOps <span className="text-neon-blue text-glow-blue">Sentinel</span>
        </h1>
        <span className="text-xs text-gray-600">·</span>
        <span className="text-xs font-semibold text-gray-400">{activeTabLabel}</span>
      </div>

      <div className="flex items-center gap-2">
        {activeMcpCalls > 0 && (
          <div className="flex items-center gap-1.5 px-2.5 py-1 rounded-full border bg-yellow-500/10 border-yellow-500/30 text-xs font-semibold text-yellow-400 animate-pulse">
            <span className="h-1.5 w-1.5 rounded-full bg-yellow-400" />
            {activeMcpCalls} MCP
          </div>
        )}

        <div className={`flex items-center gap-1.5 px-2.5 py-1 rounded-full border text-xs font-semibold ${
          wsConnected
            ? 'bg-neon-green/10 border-neon-green/30 text-neon-green'
            : 'bg-red-500/10 border-red-500/30 text-red-400'
        }`}>
          {wsConnected ? <Wifi size={10} /> : <WifiOff size={10} />}
          {wsConnected ? 'Live' : 'Offline'}
        </div>

        <button
          onClick={onClear}
          className="flex items-center gap-1.5 px-3 py-1.5 rounded-xl
                     bg-neon-red/8 hover:bg-neon-red/15
                     border border-neon-red/20 hover:border-neon-red/40
                     text-neon-red text-xs font-semibold transition-all duration-200"
        >
          <Trash2 size={12} />
          Clear
        </button>
      </div>
    </header>
  )
}

/* ─── Footer ─────────────────────────────────────────────────────────────────── */
function Footer({ incidentCount, resolvedCount }) {
  return (
    <footer className="app-footer flex items-center justify-between px-5 border-t border-dark-400/20 bg-dark-950/80">
      <span className="text-[10px] text-gray-700 font-mono">
        CodeOps Sentinel v2.0 · Azure MCP Server · Microsoft Agent Framework
      </span>
      <span className="text-[10px] text-gray-700 font-mono">
        {resolvedCount}/{incidentCount} resolved
      </span>
    </footer>
  )
}

/* ─── Dashboard ──────────────────────────────────────────────────────────────── */
export default function Dashboard({
  incidents       = [],
  agentStatuses   = {},
  wsConnected,
  events          = [],
  activeIncident,
  onSelectIncident,
  onSimulate,
  onClear,
  mcpEvents       = [],
  executionPlan,
  registryAgents  = [],
  onTriggerTool,
}) {
  const resolved   = incidents.filter(i => i.status === 'RESOLVED').length
  const active     = incidents.filter(i => !['RESOLVED', 'ROLLED_BACK', 'FAILED'].includes(i.status)).length
  const isRunning  = !!activeIncident && !['RESOLVED', 'ROLLED_BACK', 'FAILED'].includes(activeIncident?.status)

  const defaultTab = isRunning ? 'agent-flow' : 'overview'
  const [activeTab, setActiveTab] = useState(defaultTab)

  const activeMcpCalls = mcpEvents.filter(e => e.status === 'in_progress').length
  const activeTabLabel = NAV.find(n => n.id === activeTab)?.label ?? ''

  // Normalize incidents for overview (uppercase → lowercase status/severity)
  const normalizedIncidents = incidents.map(i => ({
    ...i,
    status:   i.status?.toLowerCase(),
    severity: i.severity?.toLowerCase(),
  }))
  const normalizedCurrent = activeIncident ? {
    ...activeIncident,
    status:   activeIncident.status?.toLowerCase(),
    severity: activeIncident.severity?.toLowerCase(),
  } : null

  // Normalize agentStatuses for registry
  const normalizedAgentStatuses = Object.fromEntries(
    Object.entries(agentStatuses).map(([k, v]) => [k, { ...v, status: v.status?.toLowerCase() }])
  )

  return (
    <div className="app-layout">

      {/* ── Sidebar ── */}
      <Sidebar
        activeTab={activeTab}
        onTab={setActiveTab}
        hasAlert={activeMcpCalls > 0}
      />

      {/* ── Header ── */}
      <Header
        wsConnected={wsConnected}
        activeMcpCalls={activeMcpCalls}
        onClear={onClear}
        activeTabLabel={activeTabLabel}
      />

      {/* ── Main content ── */}
      <main className="app-main px-5 py-5">

        {/* ── OVERVIEW ── */}
        {activeTab === 'overview' && (
          <Overview
            incidents={normalizedIncidents}
            currentIncident={normalizedCurrent}
            registryAgents={registryAgents}
            wsEvents={events}
          />
        )}

        {/* ── AGENT FLOW ── */}
        {activeTab === 'agent-flow' && (
          <div className="space-y-5">
            {/* Agent cards row */}
            <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
              {Object.keys(agentStatuses).map(name => (
                <AgentCard key={name} agentName={name} agentStatus={agentStatuses[name]} />
              ))}
            </div>

            {/* Sequence diagram */}
            <AgentFlow
              activeIncident={activeIncident}
              agentStatuses={normalizedAgentStatuses}
              mcpEvents={mcpEvents}
            />

            {/* MCP flow (detailed call log) */}
            <div className="card p-0 overflow-hidden">
              <div className="px-4 py-3 border-b border-dark-400/30 flex items-center justify-between">
                <span className="section-title">MCP Call Log</span>
                <span className="text-xs font-mono text-gray-600">{mcpEvents.length} total</span>
              </div>
              <div className="p-4">
                <MCPFlowView
                  mcpEvents={mcpEvents}
                  agentStatuses={agentStatuses}
                  activeIncident={activeIncident}
                />
              </div>
            </div>
          </div>
        )}

        {/* ── EXEC PLAN ── */}
        {activeTab === 'plan' && (
          <div className="space-y-5">
            <ExecutionPlan executionPlan={executionPlan} />
            {activeIncident && (
              <div className="card">
                <p className="section-title mb-3">Agent Timeline</p>
                <Timeline incident={activeIncident} />
              </div>
            )}
          </div>
        )}

        {/* ── REGISTRY ── */}
        {activeTab === 'registry' && (
          <AgentRegistry
            registryAgents={registryAgents}
            onTriggerTool={onTriggerTool}
          />
        )}

        {/* ── HISTORY ── */}
        {activeTab === 'history' && (
          <div className="space-y-5">
            <IncidentHistory incidents={normalizedIncidents} />
            {/* Incident list + timeline */}
            <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
              <div className="card lg:col-span-1">
                <div className="flex items-center justify-between mb-3">
                  <p className="section-title">Incidents</p>
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
      </main>

      {/* ── Footer ── */}
      <Footer incidentCount={incidents.length} resolvedCount={resolved} />

      {/* ── Floating simulate button ── */}
      <SimulateButton onSimulate={onSimulate} isRunning={isRunning} />
    </div>
  )
}
