import { Activity, AlertCircle, CheckCircle2, Clock, Cpu, Search, Wrench, Rocket } from 'lucide-react'

const AGENT_CONFIG = {
  monitor: {
    icon: Activity,
    label: 'Monitor Agent',
    subtitle: 'Azure Monitor • Metrics',
    color: 'neon-blue',
    colorClass: 'text-neon-blue',
    borderClass: 'border-neon-blue/30',
    bgClass: 'bg-neon-blue/5',
    glowClass: 'glow-blue',
  },
  diagnostic: {
    icon: Search,
    label: 'Diagnostic Agent',
    subtitle: 'Azure OpenAI • Log Analysis',
    color: 'neon-purple',
    colorClass: 'text-purple-400',
    borderClass: 'border-purple-400/30',
    bgClass: 'bg-purple-400/5',
    glowClass: '',
  },
  fixer: {
    icon: Wrench,
    label: 'Fixer Agent',
    subtitle: 'GitHub Copilot • Code Gen',
    color: 'neon-yellow',
    colorClass: 'text-yellow-400',
    borderClass: 'border-yellow-400/30',
    bgClass: 'bg-yellow-400/5',
    glowClass: '',
  },
  deploy: {
    icon: Rocket,
    label: 'Deploy Agent',
    subtitle: 'Azure DevOps • K8s',
    color: 'neon-green',
    colorClass: 'text-neon-green',
    borderClass: 'border-neon-green/30',
    bgClass: 'bg-neon-green/5',
    glowClass: 'glow-green',
  },
}

const StatusIndicator = ({ status, colorClass }) => {
  if (status === 'working') {
    return (
      <div className="flex items-center gap-1.5">
        <span className="relative flex h-2.5 w-2.5">
          <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-neon-blue opacity-75"></span>
          <span className="relative inline-flex rounded-full h-2.5 w-2.5 bg-neon-blue"></span>
        </span>
        <span className="text-neon-blue text-xs font-semibold uppercase tracking-wider">Working</span>
      </div>
    )
  }
  if (status === 'done') {
    return (
      <div className="flex items-center gap-1.5">
        <CheckCircle2 size={12} className="text-neon-green" />
        <span className="text-neon-green text-xs font-semibold uppercase tracking-wider">Done</span>
      </div>
    )
  }
  if (status === 'error') {
    return (
      <div className="flex items-center gap-1.5">
        <AlertCircle size={12} className="text-neon-red" />
        <span className="text-neon-red text-xs font-semibold uppercase tracking-wider">Error</span>
      </div>
    )
  }
  return (
    <div className="flex items-center gap-1.5">
      <span className="h-2.5 w-2.5 rounded-full bg-gray-600"></span>
      <span className="text-gray-500 text-xs font-semibold uppercase tracking-wider">Idle</span>
    </div>
  )
}

export default function AgentCard({ agentName, agentStatus }) {
  const config = AGENT_CONFIG[agentName] || AGENT_CONFIG.monitor
  const Icon = config.icon
  const isWorking = agentStatus?.status === 'working'

  return (
    <div
      className={`relative overflow-hidden rounded-xl border p-4 transition-all duration-500 ${config.borderClass} ${config.bgClass} ${isWorking ? config.glowClass : ''}`}
      style={isWorking ? { borderColor: 'currentColor' } : {}}
    >
      {/* Scan line animation when working */}
      {isWorking && <div className="scan-line" />}

      <div className="flex items-start justify-between mb-3">
        <div className="flex items-center gap-2.5">
          <div className={`p-2 rounded-lg ${config.bgClass} border ${config.borderClass}`}>
            <Icon size={16} className={config.colorClass} />
          </div>
          <div>
            <div className={`text-sm font-bold ${config.colorClass}`}>{config.label}</div>
            <div className="text-xs text-gray-500 mt-0.5">{config.subtitle}</div>
          </div>
        </div>
        <StatusIndicator status={agentStatus?.status || 'idle'} colorClass={config.colorClass} />
      </div>

      {/* Last action */}
      <div className="min-h-[2.5rem]">
        {agentStatus?.last_action ? (
          <p className="text-xs text-gray-400 leading-relaxed line-clamp-2">
            {agentStatus.last_action}
          </p>
        ) : (
          <p className="text-xs text-gray-600 italic">Awaiting incident...</p>
        )}
      </div>

      {/* Stats footer */}
      <div className="flex items-center justify-between mt-3 pt-3 border-t border-dark-400/50">
        <div className="flex items-center gap-1 text-xs text-gray-500">
          <Clock size={10} />
          <span>{agentStatus?.last_action_time
            ? new Date(agentStatus.last_action_time).toLocaleTimeString()
            : 'Never'}
          </span>
        </div>
        <div className={`text-xs font-mono ${config.colorClass}`}>
          {agentStatus?.incidents_handled || 0} handled
        </div>
      </div>
    </div>
  )
}
