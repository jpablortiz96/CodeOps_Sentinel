import { useMemo, useState, useEffect } from 'react'
import {
  Activity, AlertTriangle, CheckCircle, Clock,
  Cpu, TrendingUp, Zap, Shield, MemoryStick, Gauge, Radio,
  GitPullRequest, ExternalLink,
} from 'lucide-react'
import AnimatedNumber from './common/AnimatedNumber'
import StatusBadge from './common/StatusBadge'
import GlowCard from './common/GlowCard'
import { formatDuration, formatTime, formatRelative, formatSeverity } from '../utils/formatters'

/* ─── Demo App Gauge ────────────────────────────────────────────────────────── */
function DemoAppGauge({ label, value, max, unit = '', color = 'blue', icon: Icon }) {
  const pct = max > 0 ? Math.min(100, (value / max) * 100) : 0
  const colorMap = {
    blue:   { text: 'text-neon-blue',   bar: 'bg-neon-blue',   glow: 'shadow-neon-blue/40'  },
    green:  { text: 'text-neon-green',  bar: 'bg-neon-green',  glow: 'shadow-neon-green/40' },
    red:    { text: 'text-neon-red',    bar: 'bg-neon-red',    glow: 'shadow-neon-red/40'   },
    yellow: { text: 'text-yellow-400',  bar: 'bg-yellow-400',  glow: 'shadow-yellow-400/40' },
    orange: { text: 'text-orange-400',  bar: 'bg-orange-400',  glow: 'shadow-orange-400/40' },
  }
  const c = colorMap[color] ?? colorMap.blue

  return (
    <div className="flex flex-col gap-1.5">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-1.5">
          {Icon && <Icon size={13} className={`${c.text} flex-shrink-0`} />}
          <span className="text-xs text-gray-400 font-mono">{label}</span>
        </div>
        <span className={`text-xs font-bold font-mono ${c.text}`}>
          {typeof value === 'number' ? value.toFixed(value < 10 ? 2 : 1) : '—'}{unit}
        </span>
      </div>
      <div className="h-1.5 rounded-full bg-dark-600 overflow-hidden">
        <div
          className={`h-full rounded-full transition-all duration-700 ${c.bar}`}
          style={{ width: `${pct}%`, boxShadow: pct > 70 ? `0 0 6px var(--tw-shadow-color)` : 'none' }}
        />
      </div>
    </div>
  )
}

/* ─── Monitored App Panel ────────────────────────────────────────────────────── */
function MonitoredApp({ metrics }) {
  const statusColor = {
    healthy:  'text-neon-green border-neon-green/30 bg-neon-green/10',
    degraded: 'text-yellow-400 border-yellow-400/30 bg-yellow-400/10',
    critical: 'text-neon-red border-neon-red/30 bg-neon-red/10 animate-pulse',
    unknown:  'text-gray-500 border-dark-400 bg-dark-700',
  }

  const status  = metrics?.status ?? 'unknown'
  const memory  = metrics?.memory_usage_mb  ?? null
  const cpu     = metrics?.cpu_percent      ?? null
  const errRate = metrics?.error_rate       ?? null   // already %
  const latency = metrics?.avg_latency_ms   ?? null
  const chaos   = metrics?.active_chaos     ?? []

  const memColor  = memory  > 400 ? 'red' : memory  > 200 ? 'orange' : 'green'
  const cpuColor  = cpu     > 85  ? 'red' : cpu     > 60  ? 'orange' : 'blue'
  const errColor  = errRate > 30  ? 'red' : errRate > 10  ? 'orange' : 'green'
  const latColor  = latency > 2000? 'red' : latency > 500 ? 'orange' : 'blue'

  return (
    <GlowCard color={status === 'critical' ? 'red' : status === 'degraded' ? 'yellow' : 'green'}>
      <div className="flex items-center justify-between mb-4">
        <div className="flex items-center gap-2">
          <Radio size={14} className="text-neon-blue animate-pulse" />
          <p className="section-title">Monitored App — ShopDemo</p>
        </div>
        <span className={`text-xs font-bold font-mono px-2 py-0.5 rounded-lg border ${statusColor[status] ?? statusColor.unknown}`}>
          {status.toUpperCase()}
        </span>
      </div>

      {metrics ? (
        <>
          <div className="grid grid-cols-2 gap-x-6 gap-y-3 mb-3">
            <DemoAppGauge label="Memory"     value={memory}  max={600}  unit=" MB" color={memColor}  icon={MemoryStick} />
            <DemoAppGauge label="CPU"        value={cpu}     max={100}  unit="%"   color={cpuColor}  icon={Cpu} />
            <DemoAppGauge label="Error Rate" value={errRate} max={100}  unit="%"   color={errColor}  icon={AlertTriangle} />
            <DemoAppGauge label="Latency"    value={latency} max={5000} unit=" ms" color={latColor}  icon={Gauge} />
          </div>

          {chaos.length > 0 && (
            <div className="mt-2 flex flex-wrap gap-1.5">
              {chaos.map(exp => (
                <span
                  key={exp}
                  className="text-xs font-mono px-2 py-0.5 rounded-md border border-neon-red/40 bg-neon-red/10 text-neon-red"
                >
                  ⚡ {exp.replace(/_active$/, '').replace(/_/g, '-')}
                </span>
              ))}
            </div>
          )}

          <p className="text-xs text-gray-600 font-mono mt-3">
            req count: {metrics.request_count ?? '—'} · polled {metrics.polled_at ? new Date(metrics.polled_at).toLocaleTimeString() : '—'}
          </p>
        </>
      ) : (
        <div className="flex items-center gap-2 py-3 text-gray-500">
          <Activity size={14} className="animate-pulse" />
          <span className="text-xs font-mono">Waiting for first poll…</span>
        </div>
      )}
    </GlowCard>
  )
}

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
      case 'mcp_call':          return 'log-mcp'
      case 'agent_activity':    return 'log-info'
      case 'state_transition':  return 'log-success'
      case 'github_pr_created': return 'log-success'
      case 'error':             return 'log-error'
      default:                  return 'log-info'
    }
  }

  const typePrefix = (type) => {
    switch (type) {
      case 'mcp_call':           return '[MCP]'
      case 'agent_activity':     return '[AGT]'
      case 'state_transition':   return '[STA]'
      case 'plan_step_update':   return '[PLN]'
      case 'github_pr_created':  return '[PR]'
      default:                   return '[SYS]'
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
            <span className={`flex-shrink-0 ${typeStyle(ev.type ?? ev.event_type)}`}>{typePrefix(ev.type ?? ev.event_type)}</span>
            {(ev.type === 'github_pr_created' || ev.event_type === 'github_pr_created') ? (
              <span className="text-purple-400 truncate">
                🤖 Fixer Agent created{' '}
                <a
                  href={ev.data?.pr_url ?? ev.pr_url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="text-purple-300 underline hover:text-purple-200"
                >
                  PR #{ev.data?.pr_number ?? ev.pr_number}
                </a>
                {': '}{ev.data?.title ?? ''}
              </span>
            ) : (
              <span className="text-gray-400 truncate">
                {ev.message ?? ev.data?.message ?? ev.tool_name ?? ev.action ?? ev.type}
              </span>
            )}
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
        {incident.github_pr_url && (
          <a
            href={incident.github_pr_url}
            target="_blank"
            rel="noopener noreferrer"
            className="inline-flex items-center gap-1.5 mt-1.5 px-2.5 py-1 rounded-lg
                       bg-purple-500/10 border border-purple-500/30
                       text-purple-400 text-xs font-semibold font-mono
                       hover:bg-purple-500/20 hover:border-purple-500/50
                       transition-all duration-200 group"
          >
            <GitPullRequest size={12} />
            PR #{incident.github_pr_number}
            <ExternalLink size={10} className="opacity-50 group-hover:opacity-100 transition-opacity" />
          </a>
        )}
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
  // Extract latest demo_app_metrics from the WebSocket event stream
  const demoMetrics = useMemo(() => {
    for (let i = wsEvents.length - 1; i >= 0; i--) {
      if (wsEvents[i].type === 'demo_app_metrics' || wsEvents[i].event_type === 'demo_app_metrics') {
        return wsEvents[i].data ?? wsEvents[i]
      }
    }
    return null
  }, [wsEvents])
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

      {/* ── Monitored App ── */}
      <MonitoredApp metrics={demoMetrics} />

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
