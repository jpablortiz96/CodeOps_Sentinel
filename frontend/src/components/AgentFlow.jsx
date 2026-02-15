import { useRef, useEffect } from 'react'
import { Activity, Search, Wrench, Rocket, ArrowRight } from 'lucide-react'
import StatusBadge from './common/StatusBadge'
import { formatDuration, formatTime } from '../utils/formatters'

/* ─── Config ─────────────────────────────────────────────────────────────────── */
const AGENTS = [
  { id: 'orchestrator', label: 'Orchestrator', icon: Activity,  color: '#00d4ff', shortId: 'ORCH' },
  { id: 'monitor',      label: 'Monitor',      icon: Activity,  color: '#00d4ff', shortId: 'MON'  },
  { id: 'diagnostic',   label: 'Diagnostic',   icon: Search,    color: '#aa66ff', shortId: 'DIAG' },
  { id: 'fixer',        label: 'Fixer',        icon: Wrench,    color: '#ffaa00', shortId: 'FIX'  },
  { id: 'deploy',       label: 'Deploy',       icon: Rocket,    color: '#00ff88', shortId: 'DEP'  },
]

const AGENT_MAP = Object.fromEntries(AGENTS.map(a => [a.id, a]))

/* ─── Arrow component ────────────────────────────────────────────────────────── */
function SequenceArrow({ from, to, label, status, payload, elapsed }) {
  const fromIdx = AGENTS.findIndex(a => a.id === from)
  const toIdx   = AGENTS.findIndex(a => a.id === to)
  if (fromIdx === -1 || toIdx === -1) return null

  const colW    = 100 / AGENTS.length
  const fromPct = colW * fromIdx + colW / 2
  const toPct   = colW * toIdx   + colW / 2
  const isRight = toPct > fromPct
  const minX    = Math.min(fromPct, toPct)
  const width   = Math.abs(toPct - fromPct)
  const midPct  = minX + width / 2

  const statusColor = status === 'success'     ? '#00ff88'
                    : status === 'error'        ? '#ff3366'
                    : status === 'in_progress'  ? '#00d4ff'
                    : '#4a5568'

  return (
    <div
      className="relative group"
      style={{ height: 36, marginBottom: 2 }}
    >
      {/* Arrow line */}
      <svg
        className="absolute inset-0 w-full h-full overflow-visible"
        style={{ pointerEvents: 'none' }}
      >
        <defs>
          <marker id={`arrow-${from}-${to}`} markerWidth="6" markerHeight="6"
            refX="5" refY="3" orient="auto">
            <path d="M0,0 L0,6 L6,3 z" fill={statusColor} />
          </marker>
        </defs>
        {/* Connecting line */}
        <line
          x1={`${fromPct}%`} y1="18"
          x2={`${toPct}%`}   y2="18"
          stroke={statusColor}
          strokeWidth={status === 'in_progress' ? 2 : 1.5}
          strokeDasharray={status === 'in_progress' ? '4 3' : 'none'}
          markerEnd={isRight ? `url(#arrow-${from}-${to})` : undefined}
          markerStart={!isRight ? `url(#arrow-${from}-${to})` : undefined}
          className={status === 'in_progress' ? 'animate-pulse' : ''}
        />
        {/* Traveling dot for in-progress */}
        {status === 'in_progress' && (
          <circle r="3" fill={statusColor} opacity="0.9">
            <animate
              attributeName="cx"
              from={`${fromPct}%`}
              to={`${toPct}%`}
              dur="1.2s"
              repeatCount="indefinite"
            />
            <animateTransform
              attributeName="transform"
              type="translate"
              values="0,18; 0,18"
              dur="1.2s"
              repeatCount="indefinite"
            />
            <animate attributeName="cy" values="18;18" dur="1.2s" repeatCount="indefinite" />
          </circle>
        )}
      </svg>

      {/* Label above line */}
      <div
        className="absolute -top-0.5 text-center pointer-events-none"
        style={{ left: `${midPct}%`, transform: 'translateX(-50%)', maxWidth: 120 }}
      >
        <span
          className="text-[10px] font-mono px-1.5 py-0.5 rounded whitespace-nowrap"
          style={{ color: statusColor, background: 'rgba(10,10,15,0.85)' }}
        >
          {label}
        </span>
      </div>

      {/* Tooltip on hover */}
      {payload && (
        <div
          className="absolute bottom-full mb-2 hidden group-hover:block z-50"
          style={{ left: `${midPct}%`, transform: 'translateX(-50%)' }}
        >
          <div className="bg-dark-600 border border-dark-400 rounded-lg p-2 text-xs font-mono text-gray-300 max-w-xs shadow-xl whitespace-pre-wrap">
            {elapsed && <p className="text-gray-500 mb-1">⏱ {formatDuration(elapsed)}</p>}
            <p className="truncate max-w-[220px]">
              {typeof payload === 'string' ? payload : JSON.stringify(payload, null, 2).slice(0, 200)}
            </p>
          </div>
        </div>
      )}
    </div>
  )
}

/* ─── Lifeline Headers ───────────────────────────────────────────────────────── */
function LifelineHeaders({ agentStatuses = {} }) {
  return (
    <div className="flex" style={{ marginBottom: 8 }}>
      {AGENTS.map(agent => {
        const Icon    = agent.icon
        const status  = agentStatuses[agent.id]?.status ?? 'idle'
        const isActive = status === 'working'
        return (
          <div key={agent.id} className="flex flex-col items-center flex-1 gap-1">
            <div
              className={`w-12 h-12 rounded-xl border-2 flex items-center justify-center transition-all duration-500
                ${isActive ? 'animate-pulse' : ''}`}
              style={{
                borderColor: isActive ? agent.color : 'rgba(45,55,72,0.8)',
                backgroundColor: isActive ? `${agent.color}18` : 'rgba(17,24,39,0.6)',
                boxShadow: isActive ? `0 0 18px ${agent.color}50` : 'none',
              }}
            >
              <Icon size={18} style={{ color: isActive ? agent.color : '#4a5568' }} />
            </div>
            <span
              className="text-[11px] font-bold"
              style={{ color: isActive ? agent.color : '#6b7280' }}
            >
              {agent.label}
            </span>
            <StatusBadge status={status} variant="dot" />
          </div>
        )
      })}
    </div>
  )
}

/* ─── Lifeline Lines ─────────────────────────────────────────────────────────── */
function LifelineLines({ height = 400 }) {
  return (
    <div className="absolute inset-x-0 top-0 pointer-events-none" style={{ height }}>
      {AGENTS.map((agent, i) => {
        const pct = (100 / AGENTS.length) * i + (100 / AGENTS.length) / 2
        return (
          <div
            key={agent.id}
            className="absolute top-0 bottom-0"
            style={{
              left: `${pct}%`,
              width: 1,
              background: 'linear-gradient(to bottom, rgba(45,55,72,0.6) 0%, rgba(45,55,72,0.2) 100%)',
            }}
          />
        )
      })}
    </div>
  )
}

/* ─── Empty State ────────────────────────────────────────────────────────────── */
function EmptyState() {
  return (
    <div className="flex flex-col items-center justify-center py-16 text-gray-600">
      <Activity size={32} className="mb-3 opacity-30" />
      <p className="text-sm">No MCP calls yet</p>
      <p className="text-xs mt-1">Trigger an incident to see the live agent sequence</p>
    </div>
  )
}

/* ─── AgentFlow ──────────────────────────────────────────────────────────────── */
export default function AgentFlow({ activeIncident, agentStatuses = {}, mcpEvents = [] }) {
  const scrollRef = useRef(null)

  // Auto-scroll to bottom on new events
  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight
    }
  }, [mcpEvents.length])

  // Pair mcp_call + mcp_response events into rows
  const rows = mcpEvents.reduce((acc, ev) => {
    if (ev.type === 'mcp_call') {
      acc.push({ ...ev, status: 'in_progress' })
    } else if (ev.type === 'mcp_response') {
      const idx = acc.findLastIndex(r => r.call_id === ev.call_id)
      if (idx !== -1) {
        acc[idx] = { ...acc[idx], ...ev, status: ev.status ?? 'success' }
      } else {
        acc.push({ ...ev })
      }
    }
    return acc
  }, [])

  const totalCalls   = rows.length
  const successCalls = rows.filter(r => r.status === 'success').length
  const errorCalls   = rows.filter(r => r.status === 'error').length
  const activeCalls  = rows.filter(r => r.status === 'in_progress').length

  return (
    <div className="card flex flex-col gap-0 p-0 overflow-hidden">

      {/* Header */}
      <div className="flex items-center justify-between px-4 py-3 border-b border-dark-400/40">
        <div className="flex items-center gap-3">
          <span className="section-title">MCP Sequence Diagram</span>
          {activeIncident && (
            <span className="text-xs font-mono text-gray-600">{activeIncident.id}</span>
          )}
        </div>
        <div className="flex items-center gap-3 text-xs font-mono">
          {activeCalls > 0 && (
            <span className="text-neon-blue animate-pulse">● {activeCalls} active</span>
          )}
          <span className="text-gray-600">{successCalls}/{totalCalls} ok</span>
          {errorCalls > 0 && (
            <span className="text-neon-red">{errorCalls} err</span>
          )}
        </div>
      </div>

      {/* Diagram */}
      <div className="px-4 pt-4">
        <LifelineHeaders agentStatuses={agentStatuses} />
      </div>

      {/* Scrollable sequence area */}
      <div
        ref={scrollRef}
        className="relative px-4 pb-4 overflow-y-auto scrollbar-thin flex-1"
        style={{ maxHeight: 420, minHeight: 120 }}
      >
        <LifelineLines height={Math.max(rows.length * 38 + 20, 120)} />

        {rows.length === 0 ? (
          <EmptyState />
        ) : (
          <div className="relative pt-2">
            {rows.map((row, i) => (
              <div key={row.call_id ?? i} className="mcp-row-enter">
                <SequenceArrow
                  from={row.from_agent}
                  to={row.to_agent ?? row.agent}
                  label={row.tool_name ?? row.action ?? '…'}
                  status={row.status}
                  payload={row.result ?? row.params}
                  elapsed={row.elapsed_ms}
                />
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Footer status */}
      {activeIncident && (
        <div className="px-4 py-2 border-t border-dark-400/30 flex items-center gap-2">
          <div className={`w-1.5 h-1.5 rounded-full flex-shrink-0
            ${activeIncident.status === 'RESOLVED' ? 'bg-neon-green' :
              activeIncident.status === 'ROLLED_BACK' ? 'bg-neon-red' :
              'bg-neon-blue animate-ping'}`}
          />
          <span className="text-xs text-gray-500">
            {activeIncident.status === 'RESOLVED'     ? 'Remediation complete — all systems nominal' :
             activeIncident.status === 'ROLLED_BACK'  ? 'Rolled back — manual review required' :
             `Processing: ${activeIncident.status?.toLowerCase().replace('_', ' ')}`}
          </span>
        </div>
      )}
    </div>
  )
}
