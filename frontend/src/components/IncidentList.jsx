import { AlertTriangle, CheckCircle2, RotateCcw, Loader2, Clock, Users, AlertCircle } from 'lucide-react'

const SEVERITY_CONFIG = {
  critical: { class: 'badge-critical', dot: 'bg-red-500' },
  high: { class: 'badge-high', dot: 'bg-orange-400' },
  medium: { class: 'badge-medium', dot: 'bg-yellow-400' },
  low: { class: 'badge-low', dot: 'bg-blue-400' },
}

const STATUS_CONFIG = {
  DETECTED: { icon: AlertCircle, color: 'text-orange-400', label: 'Detected' },
  DIAGNOSING: { icon: Loader2, color: 'text-neon-blue', label: 'Diagnosing', spin: true },
  FIXING: { icon: Loader2, color: 'text-yellow-400', label: 'Fixing', spin: true },
  DEPLOYING: { icon: Loader2, color: 'text-purple-400', label: 'Deploying', spin: true },
  RESOLVED: { icon: CheckCircle2, color: 'text-neon-green', label: 'Resolved' },
  ROLLED_BACK: { icon: RotateCcw, color: 'text-orange-400', label: 'Rolled Back' },
  FAILED: { icon: AlertTriangle, color: 'text-neon-red', label: 'Failed' },
}

function IncidentRow({ incident, isActive, onClick }) {
  const sev = SEVERITY_CONFIG[incident.severity] || SEVERITY_CONFIG.medium
  const status = STATUS_CONFIG[incident.status] || STATUS_CONFIG.DETECTED
  const StatusIcon = status.icon
  const isInProgress = ['DIAGNOSING', 'FIXING', 'DEPLOYING'].includes(incident.status)

  const duration = incident.resolved_at
    ? Math.round((new Date(incident.resolved_at) - new Date(incident.detected_at)) / 1000)
    : Math.round((Date.now() - new Date(incident.detected_at)) / 1000)

  return (
    <div
      onClick={onClick}
      className={`
        p-3 rounded-lg border cursor-pointer transition-all duration-200 animate-slide-up
        ${isActive
          ? 'border-neon-blue/50 bg-neon-blue/5'
          : 'border-dark-400/50 bg-dark-600/30 hover:border-dark-400 hover:bg-dark-600/60'
        }
        ${isInProgress ? 'border-opacity-60' : ''}
      `}
    >
      <div className="flex items-start justify-between gap-2">
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 mb-1 flex-wrap">
            <span className={sev.class}>{incident.severity}</span>
            <span className="text-xs text-gray-500 font-mono">{incident.id}</span>
          </div>
          <p className="text-xs font-semibold text-gray-200 leading-snug truncate">
            {incident.title}
          </p>
          <p className="text-xs text-gray-500 mt-0.5 font-mono">{incident.service}</p>
        </div>

        <div className="flex flex-col items-end gap-1.5 shrink-0">
          <div className={`flex items-center gap-1 ${status.color}`}>
            <StatusIcon size={12} className={status.spin ? 'animate-spin' : ''} />
            <span className="text-xs font-semibold">{status.label}</span>
          </div>
          <span className="text-xs text-gray-600 font-mono">{duration}s</span>
        </div>
      </div>

      {/* Progress bar for in-progress incidents */}
      {isInProgress && (
        <div className="mt-2 h-0.5 bg-dark-400 rounded-full overflow-hidden">
          <div
            className="h-full bg-neon-blue/60 rounded-full animate-pulse"
            style={{ width: incident.status === 'DIAGNOSING' ? '33%' : incident.status === 'FIXING' ? '66%' : '90%' }}
          />
        </div>
      )}

      {/* Stats row */}
      {(incident.affected_users > 0 || incident.error_count > 0) && (
        <div className="flex items-center gap-3 mt-2 pt-2 border-t border-dark-400/30">
          {incident.affected_users > 0 && (
            <div className="flex items-center gap-1 text-xs text-gray-500">
              <Users size={9} />
              <span>{incident.affected_users.toLocaleString()} affected</span>
            </div>
          )}
          {incident.error_count > 0 && (
            <div className="flex items-center gap-1 text-xs text-gray-500">
              <AlertTriangle size={9} />
              <span>{incident.error_count.toLocaleString()} errors</span>
            </div>
          )}
        </div>
      )}
    </div>
  )
}

export default function IncidentList({ incidents, activeIncident, onSelectIncident }) {
  const sorted = [...incidents].sort((a, b) => new Date(b.detected_at) - new Date(a.detected_at))
  const active = sorted.filter(i => !['RESOLVED', 'ROLLED_BACK', 'FAILED'].includes(i.status))
  const resolved = sorted.filter(i => ['RESOLVED', 'ROLLED_BACK', 'FAILED'].includes(i.status))

  if (incidents.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center py-12 text-center">
        <CheckCircle2 size={40} className="text-neon-green/30 mb-3" />
        <p className="text-sm text-gray-500 font-semibold">All Systems Nominal</p>
        <p className="text-xs text-gray-600 mt-1">No active incidents detected</p>
        <p className="text-xs text-gray-700 mt-3">Click "Simulate Incident" to demo the pipeline</p>
      </div>
    )
  }

  return (
    <div className="space-y-4 overflow-y-auto max-h-96">
      {active.length > 0 && (
        <div>
          <div className="flex items-center gap-2 mb-2">
            <span className="relative flex h-2 w-2">
              <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-orange-400 opacity-75"></span>
              <span className="relative inline-flex rounded-full h-2 w-2 bg-orange-400"></span>
            </span>
            <span className="text-xs font-bold text-gray-400 uppercase tracking-wider">Active ({active.length})</span>
          </div>
          <div className="space-y-2">
            {active.map(i => (
              <IncidentRow
                key={i.id}
                incident={i}
                isActive={activeIncident?.id === i.id}
                onClick={() => onSelectIncident(i)}
              />
            ))}
          </div>
        </div>
      )}

      {resolved.length > 0 && (
        <div>
          <div className="flex items-center gap-2 mb-2">
            <span className="h-2 w-2 rounded-full bg-gray-600"></span>
            <span className="text-xs font-bold text-gray-500 uppercase tracking-wider">History ({resolved.length})</span>
          </div>
          <div className="space-y-2">
            {resolved.slice(0, 5).map(i => (
              <IncidentRow
                key={i.id}
                incident={i}
                isActive={activeIncident?.id === i.id}
                onClick={() => onSelectIncident(i)}
              />
            ))}
          </div>
        </div>
      )}
    </div>
  )
}
