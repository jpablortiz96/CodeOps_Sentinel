/**
 * StatusBadge — versatile status/severity pill.
 *
 * Props:
 *   status   — key used to look up color  (e.g. 'critical', 'idle', 'completed')
 *   label    — display text (defaults to status)
 *   variant  — 'pill' | 'dot' | 'outline'  (default 'pill')
 *   size     — 'xs' | 'sm' (default 'xs')
 *   pulse    — boolean: show pulsing animation on dot
 *   className
 */

const STATUS_MAP = {
  // Severities
  critical:  { text: 'text-red-400',    bg: 'bg-red-500/15',    border: 'border-red-500/30',    dot: 'bg-red-400'    },
  high:      { text: 'text-orange-400', bg: 'bg-orange-500/15', border: 'border-orange-500/30', dot: 'bg-orange-400' },
  medium:    { text: 'text-yellow-400', bg: 'bg-yellow-500/15', border: 'border-yellow-500/30', dot: 'bg-yellow-400' },
  low:       { text: 'text-blue-400',   bg: 'bg-blue-500/15',   border: 'border-blue-500/30',   dot: 'bg-blue-400'   },
  // Incident / plan statuses
  open:      { text: 'text-red-400',    bg: 'bg-red-500/15',    border: 'border-red-500/30',    dot: 'bg-red-400'    },
  resolved:  { text: 'text-neon-green', bg: 'bg-neon-green/10', border: 'border-neon-green/20', dot: 'bg-neon-green' },
  escalated: { text: 'text-orange-400', bg: 'bg-orange-500/15', border: 'border-orange-500/30', dot: 'bg-orange-400' },
  completed: { text: 'text-neon-green', bg: 'bg-neon-green/10', border: 'border-neon-green/20', dot: 'bg-neon-green' },
  executing: { text: 'text-yellow-400', bg: 'bg-yellow-500/10', border: 'border-yellow-500/20', dot: 'bg-yellow-400' },
  failed:    { text: 'text-red-400',    bg: 'bg-red-500/15',    border: 'border-red-500/30',    dot: 'bg-red-400'    },
  planning:  { text: 'text-gray-400',   bg: 'bg-dark-600',      border: 'border-dark-400',      dot: 'bg-gray-500'   },
  replanned: { text: 'text-purple-400', bg: 'bg-purple-500/10', border: 'border-purple-500/20', dot: 'bg-purple-400' },
  // Agent statuses
  idle:      { text: 'text-gray-500',   bg: 'bg-dark-600',      border: 'border-dark-400',      dot: 'bg-gray-500'   },
  working:   { text: 'text-neon-blue',  bg: 'bg-neon-blue/10',  border: 'border-neon-blue/20',  dot: 'bg-neon-blue'  },
  done:      { text: 'text-neon-green', bg: 'bg-neon-green/10', border: 'border-neon-green/20', dot: 'bg-neon-green' },
  // MCP call statuses
  in_progress: { text: 'text-yellow-400', bg: 'bg-yellow-500/10', border: 'border-yellow-500/20', dot: 'bg-yellow-400' },
  success:   { text: 'text-neon-green', bg: 'bg-neon-green/10', border: 'border-neon-green/20', dot: 'bg-neon-green' },
  error:     { text: 'text-red-400',    bg: 'bg-red-500/15',    border: 'border-red-500/30',    dot: 'bg-red-400'    },
}

const FALLBACK = { text: 'text-gray-400', bg: 'bg-dark-600', border: 'border-dark-400', dot: 'bg-gray-500' }

export default function StatusBadge({
  status = '',
  label,
  variant = 'pill',
  size = 'xs',
  pulse = false,
  className = '',
}) {
  const colors = STATUS_MAP[status?.toLowerCase()] ?? FALLBACK
  const displayLabel = label ?? status

  const textSize = size === 'sm' ? 'text-sm' : 'text-xs'

  if (variant === 'dot') {
    return (
      <span className={`inline-flex items-center gap-1.5 ${textSize} ${colors.text} ${className}`}>
        <span className="relative flex-shrink-0" style={{ width: 6, height: 6 }}>
          {pulse && (
            <span className={`absolute inset-0 rounded-full ${colors.dot} animate-ping opacity-70`} />
          )}
          <span className={`relative block w-full h-full rounded-full ${colors.dot}`} />
        </span>
        {displayLabel}
      </span>
    )
  }

  if (variant === 'outline') {
    return (
      <span className={`inline-flex items-center gap-1 ${textSize} font-semibold uppercase tracking-wide
        px-2 py-0.5 rounded-full border ${colors.text} ${colors.border} ${className}`}>
        {displayLabel}
      </span>
    )
  }

  // default: 'pill'
  return (
    <span className={`inline-flex items-center gap-1 ${textSize} font-bold uppercase tracking-wide
      px-2 py-0.5 rounded-full border ${colors.text} ${colors.bg} ${colors.border} ${className}`}>
      {pulse && (
        <span className="relative flex-shrink-0" style={{ width: 5, height: 5 }}>
          <span className={`absolute inset-0 rounded-full ${colors.dot} animate-ping opacity-75`} />
          <span className={`relative block w-full h-full rounded-full ${colors.dot}`} />
        </span>
      )}
      {displayLabel}
    </span>
  )
}
