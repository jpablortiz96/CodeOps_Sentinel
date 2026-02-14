import { Activity, Search, Wrench, Rocket, Cpu, CheckCircle2, AlertTriangle, Info } from 'lucide-react'

const AGENT_ICONS = {
  monitor: Activity,
  diagnostic: Search,
  fixer: Wrench,
  deploy: Rocket,
  orchestrator: Cpu,
}

const AGENT_COLORS = {
  monitor: '#00d4ff',
  diagnostic: '#bf5af2',
  fixer: '#ffcc00',
  deploy: '#00ff88',
  orchestrator: '#8b949e',
}

const STATUS_ICONS = {
  success: CheckCircle2,
  error: AlertTriangle,
  warning: AlertTriangle,
  info: Info,
}

const STATUS_COLORS = {
  success: 'text-neon-green',
  error: 'text-neon-red',
  warning: 'text-yellow-400',
  info: 'text-gray-400',
}

function TimelineEvent({ event, isLast }) {
  const AgentIcon = AGENT_ICONS[event.agent] || Cpu
  const agentColor = AGENT_COLORS[event.agent] || '#8b949e'
  const StatusIcon = STATUS_ICONS[event.status] || Info
  const statusColor = STATUS_COLORS[event.status] || 'text-gray-400'

  return (
    <div className="flex gap-3 group">
      {/* Line + dot */}
      <div className="flex flex-col items-center">
        <div
          className="w-7 h-7 rounded-lg flex items-center justify-center shrink-0 border"
          style={{
            backgroundColor: `${agentColor}15`,
            borderColor: `${agentColor}40`,
          }}
        >
          <AgentIcon size={13} style={{ color: agentColor }} />
        </div>
        {!isLast && <div className="w-px flex-1 bg-dark-400/50 mt-1" />}
      </div>

      {/* Content */}
      <div className={`pb-4 flex-1 min-w-0 ${isLast ? '' : ''}`}>
        <div className="flex items-center justify-between gap-2 mb-1">
          <div className="flex items-center gap-1.5">
            <StatusIcon size={11} className={statusColor} />
            <span className="text-xs font-bold text-gray-200">{event.action}</span>
          </div>
          <span className="text-xs text-gray-600 font-mono shrink-0">
            {new Date(event.timestamp).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' })}
          </span>
        </div>
        <p className="text-xs text-gray-400 leading-relaxed">{event.details}</p>
        <span
          className="inline-block mt-1 text-xs px-1.5 py-0.5 rounded font-mono"
          style={{ color: agentColor, backgroundColor: `${agentColor}10`, fontSize: '10px' }}
        >
          {event.agent}
        </span>
      </div>
    </div>
  )
}

export default function Timeline({ incident }) {
  if (!incident) {
    return (
      <div className="flex items-center justify-center py-8">
        <p className="text-xs text-gray-600">Select an incident to view timeline</p>
      </div>
    )
  }

  const events = [...(incident.timeline || [])].reverse()

  return (
    <div>
      <div className="flex items-center justify-between mb-4">
        <div>
          <h3 className="text-xs font-bold text-gray-300 uppercase tracking-wider">
            Remediation Timeline
          </h3>
          <p className="text-xs text-gray-600 mt-0.5 font-mono truncate max-w-xs">{incident.title}</p>
        </div>
        <div className="text-right">
          <div className="text-xs text-gray-500">{events.length} events</div>
          {incident.resolved_at && (
            <div className="text-xs text-neon-green font-mono">
              MTTR: {Math.round((new Date(incident.resolved_at) - new Date(incident.detected_at)) / 1000)}s
            </div>
          )}
        </div>
      </div>

      {/* Diagnosis card */}
      {incident.diagnosis && (
        <div className="mb-4 p-3 rounded-lg bg-purple-400/5 border border-purple-400/20">
          <div className="text-xs font-bold text-purple-400 mb-1">Root Cause Analysis</div>
          <p className="text-xs text-gray-300 leading-relaxed">{incident.diagnosis.root_cause}</p>
          <div className="flex items-center gap-3 mt-2 text-xs text-gray-500">
            <span>Confidence: <span className="text-purple-400">{Math.round(incident.diagnosis.confidence * 100)}%</span></span>
            <span>•</span>
            <span>Services: <span className="text-purple-400">{incident.diagnosis.affected_services?.join(', ')}</span></span>
          </div>
        </div>
      )}

      {/* Fix card */}
      {incident.fix && (
        <div className="mb-4 p-3 rounded-lg bg-yellow-400/5 border border-yellow-400/20">
          <div className="text-xs font-bold text-yellow-400 mb-1">Applied Fix</div>
          <p className="text-xs text-gray-300">{incident.fix.description}</p>
          <div className="flex items-center gap-3 mt-2">
            <span className="text-xs font-mono text-gray-500">{incident.fix.file_path}</span>
            {incident.fix.pr_url && (
              <a
                href={incident.fix.pr_url}
                target="_blank"
                rel="noopener noreferrer"
                className="text-xs text-neon-blue hover:underline font-mono"
              >
                PR #{incident.fix.pr_number} ↗
              </a>
            )}
          </div>
        </div>
      )}

      {/* Timeline events */}
      <div className="overflow-y-auto max-h-72">
        {events.length === 0 ? (
          <p className="text-xs text-gray-600 text-center py-4">No timeline events yet...</p>
        ) : (
          events.map((event, idx) => (
            <TimelineEvent key={idx} event={event} isLast={idx === events.length - 1} />
          ))
        )}
      </div>
    </div>
  )
}
