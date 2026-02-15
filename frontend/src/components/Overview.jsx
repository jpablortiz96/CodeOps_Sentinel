import { useMemo } from 'react'
import {
  Activity, AlertTriangle, CheckCircle, Clock,
  Cpu, TrendingUp, Zap, Shield,
} from 'lucide-react'
import AnimatedNumber from './common/AnimatedNumber'
import StatusBadge from './common/StatusBadge'
import GlowCard from './common/GlowCard'
import { formatDuration, formatTime, formatRelative, formatSeverity } from '../utils/formatters'

/* ─── Stat Card ─────────────────────────────────────────────────────────────── */
function StatCard({ icon: Icon, label, value, suffix = '', color = 'blue', trend, sub }) {
  const colorMap = {
    blue:   { text: 'text-neon-blue',   ring: 'stroke-neon-blue',   glow: 'glow-blue',   bg: 'bg-neon-blue/10'   },
    green:  { text: 'text-neon-green',  ring: 'stroke-neon-green',  glow: 'glow-green',  bg: 'bg-neon-green/10'  },
    red:    { text: 'text-neon-red',    ring: 'stroke-neon-red',    glow: 'glow-red',    bg: 'bg-neon-red/10'    },
    yellow: { text: 'text-yellow-400',  ring: 'stroke-yellow-400',  glow: 'glow-yellow', bg: 'bg-yellow-400/10'  },
    purple: { text: 'text-purple-400',  ring: 'stroke-purple-400',  glow: 'glow-purple', bg: 'bg-purple-400/10'  },
  }
  const c = colorMap[color] ?? colorMap.blue

  return (
    <GlowCard hover color={color} className="flex items-start gap-4">
      <div className={`p-2.5 rounded-xl ${c.bg} ${c.glow} flex-shrink-0`}>
        <Icon size={18} className={c.text} />
      </div>
      <div className="min-w-0 flex-1">
        <p className="metric-label mb-1">{label}</p>
        <p className={`metric-value ${c.text} text-glow-${color}`}>
          <AnimatedNumber value={typeof value === 'number' ? value : 0} suffix={suffix} />
        </p>
        {sub && <p className="text-xs text-gray-600 mt-0.5">{sub}</p>}
      </div>
      {trend != null && (
        <span className={`text-xs font-mono mt-1 flex-shrink-0 ${trend >= 0 ? 'text-neon-green' : 'text-neon-red'}`}>
          {trend >= 0 ? '+' : ''}{trend}%
        </span>
      )}
    </GlowCard>
  )
}

/* ─── Agent Pipeline ─────────────────────────────────────────────────────────── */
const AGENTS = [
  { key: 'monitor',     label: 'Monitor',     icon: Activity, color: 'text-neon-blue'   },
  { key: 'diagnostic',  label: 'Diagnostic',  icon: AlertTriangle, color: 'text-yellow-400' },
  { key: 'fixer',       label: 'Fixer',       icon: Zap,      color: 'text-neon-green'  },
  { key: 'deploy',      label: 'Deploy',      icon: Shield,   color: 'text-purple-400'  },
]

function AgentPipelineNode({ agent, isActive, isDone, isError }) {
  const status = isError ? 'error' : isDone ? 'done' : isActive ? 'working' : 'idle'
  const borderMap = {
    error:   'border-neon-red/50 bg-neon-red/10',
    done:    'border-neon-green/50 bg-neon-green/10',
    working: 'border-neon-blue/60 bg-neon-blue/10 animate-pulse',
    idle:    'border-dark-400 bg-dark-700',
  }
  const Icon = agent.icon

  return (
    <div className={`relative flex flex-col items-center gap-2 px-4 py-3 rounded-xl border transition-all duration-500 ${borderMap[status]}`}>
      {isActive && (
        <span className="absolute -top-1.5 -right-1.5 w-3 h-3 rounded-full bg-neon-blue animate-ping" />
      )}
      <Icon size={20} className={agent.color} />
      <span className="text-xs font-semibold text-gray-300">{agent.label}</span>
      <StatusBadge status={status} variant="dot" />
    </div>
  )
}

function PipelineConnector({ active }) {
  return (
    <div className="flex-1 flex items-center relative min-w-[24px]">
      <div className={`pipeline-connector w-full ${active ? 'active' : ''}`} />
      {active && <div className="pipeline-particle" style={{ animationDelay: '0s' }} />}
    </div>
  )
}

/* ─── Live Activity Feed ─────────────────────────────────────────────────────── */
function ActivityFeed({ events = [] }) {
  const typeStyle = (type) => {
    switch (type) {
      case 'mcp_call':        return 'log-mcp'
      case 'agent_activity':  return 'log-info'
      case 'state_transition': return 'log-success'
      case 'error':           return 'log-error'
      default:                return 'log-info'
    }
  }

  const typePrefix = (type) => {
    switch (type) {
      case 'mcp_call':        return '[MCP]'
      case 'agent_activity':  return '[AGT]'
      case 'state_transition':return '[STA]'
      case 'plan_step_update':return '[PLN]'
      default:                return '[SYS]'
    }
  }

  return (
    <div className="font-mono text-xs space-y-0.5 overflow-y-auto scrollbar-thin max-h-48">
      {events.length === 0 ? (
        <p className="text-gray-600 py-4 text-center">Awaiting events…</p>
      ) : (
        events.slice(-50).reverse().map((ev, i) => (
          <div key={i} className="log-entry mcp-row-enter">
            <span className="log-ts">{formatTime(ev.timestamp ?? new Date().toISOString())}</span>
            <span className={`flex-shrink-0 ${typeStyle(ev.type)}`}>{typePrefix(ev.type)}</span>
            <span className="text-gray-400 truncate">
              {ev.message ?? ev.tool_name ?? ev.action ?? ev.type}
            </span>
          </div>
        ))
      )}
    </div>
  )
}

/* ─── Current Incident Banner ────────────────────────────────────────────────── */
function IncidentBanner({ incident }) {
  if (!incident) return (
    <div className="flex items-center gap-3 py-4">
      <CheckCircle size={20} className="text-neon-green" />
      <div>
        <p className="text-sm font-semibold text-neon-green">All Systems Operational</p>
        <p className="text-xs text-gray-500">No active incidents detected</p>
      </div>
    </div>
  )

  const sev = formatSeverity(incident.severity)

  return (
    <div className={`flex items-start gap-3 p-3 rounded-xl border ${sev.border} ${sev.bg} incident-flash`}>
      <AlertTriangle size={18} className={`${sev.text} flex-shrink-0 mt-0.5`} />
      <div className="min-w-0 flex-1">
        <div className="flex items-center gap-2 flex-wrap">
          <p className={`text-sm font-bold ${sev.text}`}>{incident.title ?? incident.type}</p>
          <StatusBadge status={incident.severity} />
          <StatusBadge status={incident.status} />
        </div>
        <p className="text-xs text-gray-400 mt-0.5 truncate">{incident.description}</p>
        <p className="text-xs text-gray-600 mt-1">
          {formatRelative(incident.detected_at ?? incident.timestamp)}
          {incident.service && ` · ${incident.service}`}
        </p>
      </div>
    </div>
  )
}

/* ─── Overview ───────────────────────────────────────────────────────────────── */
export default function Overview({ incidents = [], currentIncident, registryAgents = [], wsEvents = [] }) {
  const stats = useMemo(() => {
    const total     = incidents.length
    const resolved  = incidents.filter(i => i.status === 'resolved').length
    const avgMs     = incidents.filter(i => i.resolution_time_ms).reduce((a, b) => a + b.resolution_time_ms, 0)
                      / Math.max(1, incidents.filter(i => i.resolution_time_ms).length)
    const autoFixed = incidents.filter(i => i.outcome === 'auto_fixed').length
    const rate      = total > 0 ? Math.round((autoFixed / total) * 100) : 0

    return { total, resolved, avgMs, rate }
  }, [incidents])

  // Determine active agents from registry
  const activeAgent = useMemo(() => {
    return registryAgents.find(a => a.status === 'working')?.name ?? null
  }, [registryAgents])

  const agentStates = useMemo(() => {
    const map = {}
    registryAgents.forEach(a => { map[a.name] = a.status })
    return map
  }, [registryAgents])

  return (
    <div className="space-y-6">

      {/* ── Stat Cards ── */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        <StatCard
          icon={AlertTriangle}
          label="Total Incidents"
          value={stats.total}
          color="blue"
          sub="All time"
        />
        <StatCard
          icon={CheckCircle}
          label="Resolved"
          value={stats.resolved}
          color="green"
          sub={`${stats.total > 0 ? Math.round((stats.resolved/stats.total)*100) : 0}% success rate`}
        />
        <StatCard
          icon={Zap}
          label="Auto-Fix Rate"
          value={stats.rate}
          suffix="%"
          color="yellow"
          sub="AI-resolved"
        />
        <StatCard
          icon={Clock}
          label="Avg Resolution"
          value={stats.avgMs > 0 ? parseFloat((stats.avgMs/1000).toFixed(1)) : 0}
          suffix="s"
          color="purple"
          sub="Mean time to resolve"
        />
      </div>

      {/* ── Current Incident ── */}
      <GlowCard color={currentIncident ? 'red' : 'green'}>
        <p className="section-title mb-3">Current Status</p>
        <IncidentBanner incident={currentIncident} />
      </GlowCard>

      {/* ── Agent Pipeline ── */}
      <GlowCard color="blue">
        <div className="flex items-center justify-between mb-4">
          <p className="section-title">Agent Pipeline</p>
          {activeAgent && (
            <span className="text-xs text-neon-blue font-mono animate-pulse">
              ● {activeAgent} executing
            </span>
          )}
        </div>
        <div className="flex items-center gap-2">
          {AGENTS.map((agent, i) => {
            const status  = agentStates[agent.key]
            const isActive = status === 'working'
            const isDone   = status === 'done'
            const isError  = status === 'error'
            return (
              <div key={agent.key} className="flex items-center flex-1 min-w-0">
                <AgentPipelineNode agent={agent} isActive={isActive} isDone={isDone} isError={isError} />
                {i < AGENTS.length - 1 && <PipelineConnector active={isActive || isDone} />}
              </div>
            )
          })}
        </div>
      </GlowCard>

      {/* ── Live Activity Feed ── */}
      <GlowCard>
        <div className="flex items-center justify-between mb-3">
          <p className="section-title">Live Activity</p>
          <span className="text-xs text-gray-600 font-mono">{wsEvents.length} events</span>
        </div>
        <ActivityFeed events={wsEvents} />
      </GlowCard>

    </div>
  )
}
