import { useEffect, useRef, useState } from 'react'
import { ArrowRight, Zap, CheckCircle2, XCircle, Clock, Activity } from 'lucide-react'

// Agent positions in the flow diagram
const AGENTS = [
  { id: 'monitor',      label: 'Monitor',    color: 'neon-blue',   icon: '📡' },
  { id: 'diagnostic',   label: 'Diagnostic', color: 'purple-400',  icon: '🔍' },
  { id: 'fixer',        label: 'Fixer',      color: 'yellow-400',  icon: '🔧' },
  { id: 'deploy',       label: 'Deploy',     color: 'neon-green',  icon: '🚀' },
]

const AGENT_COLORS = {
  monitor:    { bg: 'bg-neon-blue/10',   border: 'border-neon-blue/40',   text: 'text-neon-blue',   dot: 'bg-neon-blue' },
  diagnostic: { bg: 'bg-purple-500/10',  border: 'border-purple-500/40',  text: 'text-purple-400',  dot: 'bg-purple-400' },
  fixer:      { bg: 'bg-yellow-500/10',  border: 'border-yellow-500/40',  text: 'text-yellow-400',  dot: 'bg-yellow-400' },
  deploy:     { bg: 'bg-neon-green/10',  border: 'border-neon-green/40',  text: 'text-neon-green',  dot: 'bg-neon-green' },
  orchestrator: { bg: 'bg-orange-500/10', border: 'border-orange-500/40', text: 'text-orange-400',  dot: 'bg-orange-400' },
}

const STATUS_COLORS = {
  in_progress: 'text-yellow-400 animate-pulse',
  success:     'text-neon-green',
  error:       'text-neon-red',
}

function CallArrow({ call, agentStatuses }) {
  const from = call.from_agent
  const to = call.to_agent
  const isActive = call.status === 'in_progress'
  const isError = call.status === 'error'
  const fromColor = AGENT_COLORS[from] || AGENT_COLORS.orchestrator
  const toColor = AGENT_COLORS[to] || AGENT_COLORS.orchestrator

  return (
    <div className={`flex items-start gap-2 py-1.5 px-2 rounded-lg transition-all duration-300 ${
      isActive ? 'bg-yellow-500/5 border border-yellow-500/20' :
      isError  ? 'bg-red-500/5 border border-red-500/20' :
                 'hover:bg-dark-600/30'
    }`}>
      {/* Status icon */}
      <div className="mt-0.5 flex-shrink-0">
        {isActive && <Clock size={11} className="text-yellow-400 animate-spin" />}
        {call.status === 'success' && <CheckCircle2 size={11} className="text-neon-green" />}
        {isError && <XCircle size={11} className="text-neon-red" />}
      </div>

      {/* Flow: from → tool → to */}
      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-1 flex-wrap">
          <span className={`text-xs font-semibold ${fromColor.text}`}>{from}</span>
          <ArrowRight size={10} className="text-gray-600 flex-shrink-0" />
          <span className="text-xs font-mono text-gray-300 truncate max-w-[160px]" title={call.tool_name}>
            {call.tool_name}
          </span>
          <ArrowRight size={10} className="text-gray-600 flex-shrink-0" />
          <span className={`text-xs font-semibold ${toColor.text}`}>{to}</span>
        </div>

        <div className="flex items-center gap-2 mt-0.5">
          <span className={`text-xs font-mono ${
            isActive ? 'text-yellow-400' : isError ? 'text-red-400' : 'text-gray-600'
          }`}>
            {call.elapsed_ms != null ? `${call.elapsed_ms}ms` : '...'}
          </span>
          <span className={`text-xs px-1.5 rounded ${
            isActive ? 'bg-yellow-500/20 text-yellow-400' :
            isError  ? 'bg-red-500/20 text-red-400' :
                       'bg-neon-green/10 text-neon-green'
          }`}>
            {call.status}
          </span>
          <span className="text-xs text-gray-700 font-mono truncate">
            {call.call_id}
          </span>
        </div>
      </div>
    </div>
  )
}

function AgentNode({ agent, isActive, callCount }) {
  const colors = AGENT_COLORS[agent.id] || AGENT_COLORS.orchestrator
  return (
    <div className={`flex flex-col items-center gap-1.5 p-2.5 rounded-xl border transition-all duration-300 ${
      colors.bg} ${colors.border} ${isActive ? 'shadow-lg scale-105' : ''
    }`}
      style={{ minWidth: 80 }}
    >
      <span className="text-lg">{agent.icon}</span>
      <span className={`text-xs font-bold ${colors.text}`}>{agent.label}</span>
      {callCount > 0 && (
        <span className={`text-xs font-mono px-1.5 py-0.5 rounded-full ${colors.bg} ${colors.text}`}>
          {callCount}
        </span>
      )}
      {isActive && (
        <span className="relative flex h-1.5 w-1.5">
          <span className={`animate-ping absolute inline-flex h-full w-full rounded-full ${colors.dot} opacity-75`} />
          <span className={`relative inline-flex rounded-full h-1.5 w-1.5 ${colors.dot}`} />
        </span>
      )}
    </div>
  )
}

export default function MCPFlowView({ mcpEvents, agentStatuses, activeIncident }) {
  const scrollRef = useRef(null)
  const [filter, setFilter] = useState('all')   // all | in_progress | success | error

  // Auto-scroll to latest event
  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight
    }
  }, [mcpEvents])

  // Count calls per agent
  const callCounts = {}
  mcpEvents.forEach(e => {
    if (e.from_agent) callCounts[e.from_agent] = (callCounts[e.from_agent] || 0) + 1
    if (e.to_agent)   callCounts[e.to_agent]   = (callCounts[e.to_agent]   || 0) + 1
  })

  // Active agents (have in-progress calls)
  const activeAgents = new Set(
    mcpEvents.filter(e => e.status === 'in_progress').flatMap(e => [e.from_agent, e.to_agent])
  )

  const filteredEvents = filter === 'all'
    ? mcpEvents
    : mcpEvents.filter(e => e.status === filter)

  const inProgressCount = mcpEvents.filter(e => e.status === 'in_progress').length
  const successCount    = mcpEvents.filter(e => e.status === 'success').length
  const errorCount      = mcpEvents.filter(e => e.status === 'error').length

  return (
    <div className="space-y-3">
      {/* Agent topology row */}
      <div className="flex items-center gap-2 justify-center flex-wrap">
        {AGENTS.map((agent, i) => (
          <div key={agent.id} className="flex items-center gap-2">
            <AgentNode
              agent={agent}
              isActive={activeAgents.has(agent.id)}
              callCount={callCounts[agent.id] || 0}
            />
            {i < AGENTS.length - 1 && (
              <div className="flex flex-col items-center gap-0.5">
                <ArrowRight size={14} className="text-gray-600" />
                <span className="text-xs text-gray-700">MCP</span>
              </div>
            )}
          </div>
        ))}
      </div>

      {/* Stats bar */}
      <div className="flex items-center gap-3 text-xs flex-wrap">
        <div className="flex items-center gap-1.5">
          <Activity size={11} className="text-neon-blue" />
          <span className="text-gray-400 font-semibold">MCP Call Log</span>
        </div>
        <span className="text-gray-600">|</span>
        <button
          onClick={() => setFilter('all')}
          className={`px-2 py-0.5 rounded transition-colors ${
            filter === 'all' ? 'bg-dark-500 text-gray-200' : 'text-gray-500 hover:text-gray-300'
          }`}
        >
          All ({mcpEvents.length})
        </button>
        <button
          onClick={() => setFilter('in_progress')}
          className={`px-2 py-0.5 rounded transition-colors ${
            filter === 'in_progress' ? 'bg-yellow-500/20 text-yellow-400' : 'text-gray-500 hover:text-gray-300'
          }`}
        >
          Active ({inProgressCount})
        </button>
        <button
          onClick={() => setFilter('success')}
          className={`px-2 py-0.5 rounded transition-colors ${
            filter === 'success' ? 'bg-neon-green/10 text-neon-green' : 'text-gray-500 hover:text-gray-300'
          }`}
        >
          Success ({successCount})
        </button>
        {errorCount > 0 && (
          <button
            onClick={() => setFilter('error')}
            className={`px-2 py-0.5 rounded transition-colors ${
              filter === 'error' ? 'bg-red-500/10 text-red-400' : 'text-gray-500 hover:text-gray-300'
            }`}
          >
            Errors ({errorCount})
          </button>
        )}
        {activeIncident && (
          <span className="ml-auto text-gray-600 font-mono truncate">
            {activeIncident.id}
          </span>
        )}
      </div>

      {/* Call log */}
      <div
        ref={scrollRef}
        className="space-y-0.5 max-h-52 overflow-y-auto pr-1 scrollbar-thin"
      >
        {filteredEvents.length === 0 ? (
          <div className="text-center py-8 text-gray-600 text-xs">
            {mcpEvents.length === 0
              ? 'No MCP calls yet — simulate an incident to see agent communication'
              : 'No calls match the current filter'}
          </div>
        ) : (
          filteredEvents.map((call, i) => (
            <CallArrow key={call.call_id || i} call={call} agentStatuses={agentStatuses} />
          ))
        )}
      </div>
    </div>
  )
}
