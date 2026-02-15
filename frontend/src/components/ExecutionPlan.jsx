import { CheckCircle2, Circle, XCircle, SkipForward, Loader, AlertTriangle, Clock } from 'lucide-react'

const STEP_ICONS = {
  pending:     <Circle size={14} className="text-gray-600" />,
  in_progress: <Loader size={14} className="text-yellow-400 animate-spin" />,
  completed:   <CheckCircle2 size={14} className="text-neon-green" />,
  failed:      <XCircle size={14} className="text-neon-red" />,
  skipped:     <SkipForward size={14} className="text-gray-600" />,
}

const STEP_AGENT_COLORS = {
  monitor:      'text-neon-blue',
  diagnostic:   'text-purple-400',
  fixer:        'text-yellow-400',
  deploy:       'text-neon-green',
  orchestrator: 'text-orange-400',
}

const STEP_BG = {
  pending:     '',
  in_progress: 'bg-yellow-500/5 border-yellow-500/30',
  completed:   'bg-neon-green/5 border-neon-green/20',
  failed:      'bg-red-500/5 border-red-500/30',
  skipped:     'opacity-40',
}

const PLAN_STATUS_STYLES = {
  planning:   'text-gray-400 bg-dark-600',
  executing:  'text-yellow-400 bg-yellow-500/10 animate-pulse',
  completed:  'text-neon-green bg-neon-green/10',
  escalated:  'text-orange-400 bg-orange-500/10',
  failed:     'text-neon-red bg-red-500/10',
  replanned:  'text-purple-400 bg-purple-500/10',
}

function PlanStepRow({ step, isCurrent }) {
  const agentColor = STEP_AGENT_COLORS[step.agent] || 'text-gray-400'
  const bgClass = STEP_BG[step.status] || ''
  const isCondition = step.tool === 'orchestrator.evaluate_confidence'

  return (
    <div className={`flex items-start gap-2.5 px-2.5 py-2 rounded-lg border border-transparent transition-all duration-300 ${bgClass} ${isCurrent ? 'ring-1 ring-yellow-500/40' : ''}`}>
      {/* Step number + icon */}
      <div className="flex items-center gap-1.5 pt-0.5 flex-shrink-0">
        <span className="text-xs font-mono text-gray-600 w-4 text-right">{step.step_num}.</span>
        {STEP_ICONS[step.status]}
      </div>

      {/* Content */}
      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-2 flex-wrap">
          <span className={`text-xs font-semibold ${agentColor}`}>
            [{step.agent}]
          </span>
          <span className="text-xs text-gray-300">{step.action}</span>
          {step.elapsed_ms != null && (
            <span className="text-xs font-mono text-gray-600 ml-auto flex-shrink-0">
              {step.elapsed_ms}ms
            </span>
          )}
        </div>

        <div className="text-xs text-gray-600 font-mono mt-0.5 truncate" title={step.tool}>
          {step.tool}
        </div>

        {step.status === 'in_progress' && step.condition && (
          <div className="text-xs text-yellow-400/70 mt-0.5 truncate">{step.condition}</div>
        )}

        {step.status === 'failed' && step.result?.error && (
          <div className="text-xs text-red-400 mt-0.5 truncate">{step.result.error}</div>
        )}

        {step.status === 'skipped' && step.skip_reason && (
          <div className="text-xs text-gray-600 mt-0.5 truncate">{step.skip_reason}</div>
        )}

        {step.status === 'completed' && isCondition && step.result && (
          <div className={`text-xs mt-0.5 font-semibold ${
            step.result.decision === 'auto_fix' ? 'text-neon-green' : 'text-orange-400'
          }`}>
            Decision: {step.result.decision === 'auto_fix'
              ? `✓ Auto-fix (confidence ${step.result.confidence_pct}%)`
              : `⚠ Escalate (confidence ${step.result.confidence_pct}%)`}
          </div>
        )}
      </div>
    </div>
  )
}

function ProgressBar({ steps }) {
  const total = steps.length
  const done  = steps.filter(s => ['completed', 'skipped'].includes(s.status)).length
  const pct   = total > 0 ? Math.round((done / total) * 100) : 0

  return (
    <div className="space-y-1">
      <div className="flex justify-between text-xs">
        <span className="text-gray-500">{done}/{total} steps</span>
        <span className="text-gray-400 font-mono">{pct}%</span>
      </div>
      <div className="h-1 bg-dark-600 rounded-full overflow-hidden">
        <div
          className="h-full bg-gradient-to-r from-neon-blue to-neon-green rounded-full transition-all duration-700"
          style={{ width: `${pct}%` }}
        />
      </div>
    </div>
  )
}

export default function ExecutionPlan({ executionPlan }) {
  if (!executionPlan) {
    return (
      <div className="text-center py-8 text-gray-600 text-xs">
        No active execution plan — simulate an incident to see the TaskPlanner in action
      </div>
    )
  }

  const { plan_id, status, steps, replanned_reason, replanned_count, total_elapsed_ms, created_at, current_step_num } = executionPlan
  const statusStyle = PLAN_STATUS_STYLES[status] || PLAN_STATUS_STYLES.planning

  return (
    <div className="space-y-3">
      {/* Plan header */}
      <div className="flex items-center justify-between flex-wrap gap-2">
        <div className="flex items-center gap-2">
          <Clock size={12} className="text-gray-500" />
          <span className="text-xs font-mono text-gray-500">{plan_id}</span>
        </div>
        <div className="flex items-center gap-2">
          {replanned_count > 0 && (
            <span className="text-xs px-2 py-0.5 rounded-full bg-purple-500/10 text-purple-400">
              Re-planned ×{replanned_count}
            </span>
          )}
          <span className={`text-xs px-2 py-0.5 rounded-full font-semibold ${statusStyle}`}>
            {status}
          </span>
          {total_elapsed_ms != null && (
            <span className="text-xs font-mono text-gray-500">
              {(total_elapsed_ms / 1000).toFixed(1)}s total
            </span>
          )}
        </div>
      </div>

      {/* Replan notice */}
      {replanned_reason && (
        <div className="flex items-start gap-2 px-3 py-2 rounded-lg bg-purple-500/5 border border-purple-500/20">
          <AlertTriangle size={12} className="text-purple-400 mt-0.5 flex-shrink-0" />
          <div>
            <span className="text-xs font-semibold text-purple-400">Plan modified: </span>
            <span className="text-xs text-gray-400">{replanned_reason}</span>
          </div>
        </div>
      )}

      {/* Progress bar */}
      {steps.length > 0 && <ProgressBar steps={steps} />}

      {/* Steps */}
      <div className="space-y-0.5">
        {steps.map(step => (
          <PlanStepRow
            key={step.step_num}
            step={step}
            isCurrent={step.step_num === current_step_num && step.status === 'in_progress'}
          />
        ))}
      </div>
    </div>
  )
}
