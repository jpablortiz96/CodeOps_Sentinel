import { Activity, Search, Wrench, Rocket, ChevronRight } from 'lucide-react'

const AGENTS = [
  { id: 'monitor', label: 'Monitor', icon: Activity, color: '#00d4ff', desc: 'Azure Monitor' },
  { id: 'diagnostic', label: 'Diagnostic', icon: Search, color: '#bf5af2', desc: 'Azure OpenAI' },
  { id: 'fixer', label: 'Fixer', icon: Wrench, color: '#ffcc00', desc: 'GitHub Copilot' },
  { id: 'deploy', label: 'Deploy', icon: Rocket, color: '#00ff88', desc: 'Azure DevOps' },
]

const STATUS_TO_ACTIVE = {
  DETECTED: 'monitor',
  DIAGNOSING: 'diagnostic',
  FIXING: 'fixer',
  DEPLOYING: 'deploy',
  RESOLVED: 'deploy',
  ROLLED_BACK: 'deploy',
}

export default function AgentFlow({ activeIncident, agentStatuses }) {
  const activeAgent = activeIncident ? STATUS_TO_ACTIVE[activeIncident.status] : null
  const isResolved = activeIncident?.status === 'RESOLVED'
  const isRolledBack = activeIncident?.status === 'ROLLED_BACK'

  const getAgentState = (agentId) => {
    if (!activeIncident) return 'idle'
    const order = ['monitor', 'diagnostic', 'fixer', 'deploy']
    const activeIdx = order.indexOf(activeAgent)
    const agentIdx = order.indexOf(agentId)

    if (isResolved) return 'done'
    if (isRolledBack && agentId === 'deploy') return 'error'
    if (agentId === activeAgent) return agentStatuses[agentId]?.status === 'working' ? 'active' : 'done'
    if (agentIdx < activeIdx) return 'done'
    return 'idle'
  }

  return (
    <div className="card">
      <div className="flex items-center justify-between mb-4">
        <h3 className="text-xs font-bold text-gray-400 uppercase tracking-widest">Agent Pipeline</h3>
        {activeIncident && (
          <span className="text-xs text-gray-500 font-mono">{activeIncident.id}</span>
        )}
      </div>

      <div className="flex items-center justify-between">
        {AGENTS.map((agent, idx) => {
          const Icon = agent.icon
          const state = getAgentState(agent.id)
          const isActive = state === 'active'
          const isDone = state === 'done'
          const isError = state === 'error'
          const isIdle = state === 'idle'

          return (
            <div key={agent.id} className="flex items-center flex-1">
              {/* Agent Node */}
              <div className="flex flex-col items-center gap-2 flex-1">
                <div
                  className={`
                    relative w-14 h-14 rounded-xl flex items-center justify-center border-2 transition-all duration-500
                    ${isActive ? 'animate-pulse-glow' : ''}
                    ${isDone ? 'border-opacity-80' : ''}
                    ${isIdle ? 'opacity-40' : ''}
                  `}
                  style={{
                    borderColor: isIdle ? '#30363d' : isError ? '#ff3366' : agent.color,
                    backgroundColor: isIdle ? 'rgba(22,27,34,0.5)' : `${agent.color}15`,
                    boxShadow: isActive
                      ? `0 0 20px ${agent.color}60, 0 0 40px ${agent.color}30`
                      : isDone
                      ? `0 0 8px ${agent.color}30`
                      : 'none',
                  }}
                >
                  <Icon size={22} style={{ color: isIdle ? '#4a5568' : isError ? '#ff3366' : agent.color }} />

                  {/* Working indicator */}
                  {isActive && (
                    <span
                      className="absolute inset-0 rounded-xl animate-ping opacity-20"
                      style={{ backgroundColor: agent.color }}
                    />
                  )}

                  {/* Done checkmark */}
                  {isDone && !isError && (
                    <div
                      className="absolute -top-1.5 -right-1.5 w-4 h-4 rounded-full flex items-center justify-center text-dark-900 text-xs font-bold"
                      style={{ backgroundColor: agent.color, fontSize: '9px' }}
                    >
                      ✓
                    </div>
                  )}

                  {/* Error indicator */}
                  {isError && (
                    <div className="absolute -top-1.5 -right-1.5 w-4 h-4 rounded-full bg-neon-red flex items-center justify-center text-dark-900 text-xs font-bold" style={{ fontSize: '9px' }}>
                      ✕
                    </div>
                  )}
                </div>

                <div className="text-center">
                  <div
                    className="text-xs font-bold"
                    style={{ color: isIdle ? '#4a5568' : isError ? '#ff3366' : agent.color }}
                  >
                    {agent.label}
                  </div>
                  <div className="text-xs text-gray-600">{agent.desc}</div>
                </div>
              </div>

              {/* Connector arrow */}
              {idx < AGENTS.length - 1 && (
                <div className="flex items-center px-1 mb-6">
                  <ChevronRight
                    size={20}
                    style={{
                      color: getAgentState(AGENTS[idx + 1].id) !== 'idle' || isDone ? '#30363d' : '#1c2333',
                    }}
                  />
                </div>
              )}
            </div>
          )
        })}
      </div>

      {/* Status bar */}
      {activeIncident && (
        <div className="mt-4 pt-3 border-t border-dark-400/50">
          <div className="flex items-center gap-2">
            <div
              className={`w-2 h-2 rounded-full ${
                isResolved ? 'bg-neon-green' :
                isRolledBack ? 'bg-neon-red' :
                'bg-neon-blue animate-ping'
              }`}
            />
            <span className="text-xs text-gray-400">
              {isResolved ? 'Remediation complete — all systems nominal' :
               isRolledBack ? 'Rolled back to stable version — manual review required' :
               `Processing: ${activeIncident.status.toLowerCase().replace('_', ' ')}...`}
            </span>
          </div>
        </div>
      )}
    </div>
  )
}
