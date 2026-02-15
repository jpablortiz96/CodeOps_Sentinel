/** Utility formatters for CodeOps Sentinel dashboard */

/**
 * Format milliseconds into a human-readable duration.
 * < 1s  → "820ms"
 * < 60s → "4.2s"
 * < 1h  → "3m 12s"
 * else  → "1h 4m"
 */
export function formatDuration(ms) {
  if (ms == null) return '—'
  if (ms < 1000)  return `${Math.round(ms)}ms`
  const s = ms / 1000
  if (s < 60)     return `${s.toFixed(1)}s`
  const m = Math.floor(s / 60)
  const rs = Math.floor(s % 60)
  if (m < 60)     return `${m}m ${rs}s`
  const h = Math.floor(m / 60)
  const rm = m % 60
  return `${h}h ${rm}m`
}

/**
 * Format an ISO timestamp to a short local time string.
 * "14:03:07"
 */
export function formatTime(iso) {
  if (!iso) return ''
  const d = new Date(iso)
  return d.toLocaleTimeString('en-US', { hour12: false, hour: '2-digit', minute: '2-digit', second: '2-digit' })
}

/**
 * Format an ISO timestamp to a relative "X ago" string.
 */
export function formatRelative(iso) {
  if (!iso) return ''
  const diff = Date.now() - new Date(iso).getTime()
  if (diff < 5_000)    return 'just now'
  if (diff < 60_000)   return `${Math.floor(diff / 1000)}s ago`
  if (diff < 3_600_000) return `${Math.floor(diff / 60_000)}m ago`
  return `${Math.floor(diff / 3_600_000)}h ago`
}

/**
 * Format an ISO timestamp to a full human-readable string.
 * "Feb 14, 14:03:07"
 */
export function formatTimestamp(iso) {
  if (!iso) return ''
  const d = new Date(iso)
  return d.toLocaleString('en-US', {
    month: 'short', day: 'numeric',
    hour: '2-digit', minute: '2-digit', second: '2-digit',
    hour12: false,
  })
}

/**
 * Return Tailwind color classes for a severity level.
 */
export function formatSeverity(severity) {
  const map = {
    critical: { text: 'text-red-400',    bg: 'bg-red-500/15',    border: 'border-red-500/30',    dot: 'bg-red-400'    },
    high:     { text: 'text-orange-400', bg: 'bg-orange-500/15', border: 'border-orange-500/30', dot: 'bg-orange-400' },
    medium:   { text: 'text-yellow-400', bg: 'bg-yellow-500/15', border: 'border-yellow-500/30', dot: 'bg-yellow-400' },
    low:      { text: 'text-blue-400',   bg: 'bg-blue-500/15',   border: 'border-blue-500/30',   dot: 'bg-blue-400'   },
  }
  return map[severity?.toLowerCase()] ?? map.medium
}

/**
 * Return Tailwind color classes for an agent status.
 */
export function formatAgentStatus(status) {
  const map = {
    idle:     { text: 'text-gray-500',   dot: 'bg-gray-500',   label: 'Idle'    },
    working:  { text: 'text-neon-blue',  dot: 'bg-neon-blue',  label: 'Working' },
    done:     { text: 'text-neon-green', dot: 'bg-neon-green', label: 'Done'    },
    error:    { text: 'text-neon-red',   dot: 'bg-neon-red',   label: 'Error'   },
    escalated:{ text: 'text-orange-400', dot: 'bg-orange-400', label: 'Escalated' },
  }
  return map[status?.toLowerCase()] ?? map.idle
}

/**
 * Truncate a string with an ellipsis.
 */
export function truncate(str, maxLen = 40) {
  if (!str) return ''
  return str.length > maxLen ? str.slice(0, maxLen - 1) + '…' : str
}

/**
 * Format a number with K/M suffix.
 * 1500 → "1.5K"
 */
export function formatNumber(n) {
  if (n == null) return '—'
  if (n >= 1_000_000) return `${(n / 1_000_000).toFixed(1)}M`
  if (n >= 1_000)     return `${(n / 1_000).toFixed(1)}K`
  return String(n)
}

/**
 * Format a success rate (0–1) to a percentage string.
 */
export function formatRate(r) {
  if (r == null) return '—'
  return `${Math.round(r * 100)}%`
}
