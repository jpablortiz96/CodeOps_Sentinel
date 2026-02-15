import { useState } from 'react'
import { Database, Cpu, Wrench, Rocket, Network, ChevronDown, ChevronRight, Play, CheckCircle2 } from 'lucide-react'

const AGENT_ICONS = {
  monitor:      <Network size={16} />,
  diagnostic:   <Cpu size={16} />,
  fixer:        <Wrench size={16} />,
  deploy:       <Rocket size={16} />,
  orchestrator: <Database size={16} />,
}

const AGENT_COLORS = {
  monitor:      { text: 'text-neon-blue',   bg: 'bg-neon-blue/10',   border: 'border-neon-blue/30'   },
  diagnostic:   { text: 'text-purple-400',  bg: 'bg-purple-500/10',  border: 'border-purple-500/30'  },
  fixer:        { text: 'text-yellow-400',  bg: 'bg-yellow-500/10',  border: 'border-yellow-500/30'  },
  deploy:       { text: 'text-neon-green',  bg: 'bg-neon-green/10',  border: 'border-neon-green/30'  },
  orchestrator: { text: 'text-orange-400',  bg: 'bg-orange-500/10',  border: 'border-orange-500/30'  },
}

const STATUS_STYLES = {
  idle:    'text-gray-500 bg-dark-600',
  working: 'text-yellow-400 bg-yellow-500/10 animate-pulse',
  error:   'text-neon-red bg-red-500/10',
  offline: 'text-gray-600 bg-dark-700',
}

function ToolBadge({ toolName, onTrigger }) {
  const [triggered, setTriggered] = useState(false)
  const [loading, setLoading] = useState(false)

  const namespace = toolName.split('.')[0]
  const action = toolName.split('.').slice(1).join('.')
  const colors = AGENT_COLORS[namespace] || AGENT_COLORS.orchestrator

  const handleTrigger = async () => {
    setLoading(true)
    try {
      await onTrigger(toolName)
      setTriggered(true)
      setTimeout(() => setTriggered(false), 2000)
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className={`flex items-center gap-1.5 px-2 py-1 rounded-lg border ${colors.bg} ${colors.border} group`}>
      <span className={`text-xs font-mono ${colors.text}`}>{action}</span>
      <button
        onClick={handleTrigger}
        disabled={loading}
        className={`opacity-0 group-hover:opacity-100 transition-opacity ml-1 ${colors.text} hover:opacity-100`}
        title={`Call ${toolName}`}
      >
        {loading ? (
          <div className="h-3 w-3 rounded-full border border-current border-t-transparent animate-spin" />
        ) : triggered ? (
          <CheckCircle2 size={10} />
        ) : (
          <Play size={10} />
        )}
      </button>
    </div>
  )
}

function AgentCard({ agent, onTriggerTool }) {
  const [expanded, setExpanded] = useState(false)
  const colors = AGENT_COLORS[agent.name] || AGENT_COLORS.orchestrator
  const statusStyle = STATUS_STYLES[agent.status] || STATUS_STYLES.idle
  const icon = AGENT_ICONS[agent.name]

  return (
    <div className={`rounded-xl border transition-all duration-200 ${colors.border} overflow-hidden`}>
      {/* Agent header */}
      <button
        className={`w-full flex items-center gap-3 p-3 text-left hover:bg-dark-600/30 transition-colors`}
        onClick={() => setExpanded(!expanded)}
      >
        {/* Icon */}
        <div className={`p-1.5 rounded-lg ${colors.bg} ${colors.text} flex-shrink-0`}>
          {icon}
        </div>

        {/* Name + status */}
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2">
            <span className={`text-sm font-bold capitalize ${colors.text}`}>{agent.name}</span>
            <span className={`text-xs px-1.5 py-0.5 rounded-full ${statusStyle}`}>
              {agent.status}
            </span>
          </div>
          {agent.current_task ? (
            <div className="text-xs text-gray-500 truncate mt-0.5">{agent.current_task}</div>
          ) : (
            <div className="text-xs text-gray-600 mt-0.5">
              {agent.incidents_handled} incidents handled
            </div>
          )}
        </div>

        {/* Tools count + expand */}
        <div className="flex items-center gap-2 flex-shrink-0">
          {agent.tools?.length > 0 && (
            <span className={`text-xs px-1.5 py-0.5 rounded-full ${colors.bg} ${colors.text}`}>
              {agent.tools.length} tools
            </span>
          )}
          {expanded ? (
            <ChevronDown size={12} className="text-gray-500" />
          ) : (
            <ChevronRight size={12} className="text-gray-500" />
          )}
        </div>
      </button>

      {/* Expanded details */}
      {expanded && (
        <div className={`px-3 pb-3 pt-1 border-t ${colors.border} bg-dark-700/30`}>
          <p className="text-xs text-gray-500 mb-2 leading-relaxed">{agent.description}</p>

          {/* Capabilities */}
          {agent.capabilities?.length > 0 && (
            <div className="mb-2">
              <div className="text-xs font-semibold text-gray-600 mb-1 uppercase tracking-wider">
                Capabilities
              </div>
              <div className="flex flex-wrap gap-1">
                {agent.capabilities.map(cap => (
                  <span
                    key={cap}
                    className="text-xs px-1.5 py-0.5 rounded bg-dark-600 text-gray-500 font-mono"
                  >
                    {cap.replace(/_/g, ' ')}
                  </span>
                ))}
              </div>
            </div>
          )}

          {/* MCP Tools */}
          {agent.tools?.length > 0 && (
            <div>
              <div className="text-xs font-semibold text-gray-600 mb-1 uppercase tracking-wider">
                MCP Tools
              </div>
              <div className="flex flex-wrap gap-1">
                {agent.tools.map(tool => (
                  <ToolBadge
                    key={tool}
                    toolName={tool}
                    onTrigger={onTriggerTool}
                  />
                ))}
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  )
}

export default function AgentRegistry({ registryAgents, onTriggerTool }) {
  const totalTools = (registryAgents || []).reduce((sum, a) => sum + (a.tools?.length || 0), 0)
  const activeCount = (registryAgents || []).filter(a => a.status === 'working').length

  if (!registryAgents || registryAgents.length === 0) {
    return (
      <div className="text-center py-8 text-gray-600 text-xs">
        Loading agent registry...
      </div>
    )
  }

  return (
    <div className="space-y-3">
      {/* Registry stats */}
      <div className="flex items-center gap-4 text-xs">
        <div>
          <span className="text-gray-500">Agents: </span>
          <span className="text-gray-300 font-semibold">{registryAgents.length}</span>
        </div>
        <div>
          <span className="text-gray-500">MCP Tools: </span>
          <span className="text-neon-blue font-semibold">{totalTools}</span>
        </div>
        {activeCount > 0 && (
          <div>
            <span className="text-yellow-400 font-semibold animate-pulse">
              {activeCount} active
            </span>
          </div>
        )}
        <div className="ml-auto text-gray-600">
          Hover tool → click ▶ to trigger
        </div>
      </div>

      {/* Agent cards */}
      <div className="space-y-2">
        {registryAgents.map(agent => (
          <AgentCard
            key={agent.name}
            agent={agent}
            onTriggerTool={onTriggerTool}
          />
        ))}
      </div>
    </div>
  )
}
