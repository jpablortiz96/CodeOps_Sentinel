import { useState, useMemo } from 'react'
import { ChevronDown, ChevronUp, Filter, Search, Clock, CheckCircle, AlertTriangle, ArrowUpDown } from 'lucide-react'
import StatusBadge from './common/StatusBadge'
import { formatTimestamp, formatDuration, formatSeverity, truncate } from '../utils/formatters'

/* ─── Filter bar ─────────────────────────────────────────────────────────────── */
function FilterBar({ search, onSearch, severityFilter, onSeverity, statusFilter, onStatus }) {
  const SEVERITIES = ['all', 'critical', 'high', 'medium', 'low']
  const STATUSES   = ['all', 'open', 'resolved', 'escalated']

  return (
    <div className="flex flex-wrap items-center gap-3 mb-4">
      {/* Search */}
      <div className="relative flex-1 min-w-[180px]">
        <Search size={13} className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-600" />
        <input
          value={search}
          onChange={e => onSearch(e.target.value)}
          placeholder="Search incidents…"
          className="w-full bg-dark-700 border border-dark-400/60 rounded-xl pl-8 pr-3 py-2
                     text-xs text-gray-300 placeholder-gray-600
                     focus:outline-none focus:border-neon-blue/40 focus:bg-dark-600 transition-colors"
        />
      </div>

      {/* Severity filter pills */}
      <div className="flex gap-1 flex-wrap">
        {SEVERITIES.map(s => (
          <button
            key={s}
            onClick={() => onSeverity(s)}
            className={`px-3 py-1 rounded-lg text-xs font-semibold border transition-all duration-150 capitalize
              ${severityFilter === s
                ? 'bg-neon-blue/15 border-neon-blue/40 text-neon-blue'
                : 'bg-dark-700 border-dark-400/50 text-gray-500 hover:text-gray-300 hover:border-dark-400'}`}
          >
            {s}
          </button>
        ))}
      </div>

      {/* Status filter pills */}
      <div className="flex gap-1 flex-wrap">
        {STATUSES.map(s => (
          <button
            key={s}
            onClick={() => onStatus(s)}
            className={`px-3 py-1 rounded-lg text-xs font-semibold border transition-all duration-150 capitalize
              ${statusFilter === s
                ? 'bg-neon-purple/15 border-neon-purple/40 text-purple-300'
                : 'bg-dark-700 border-dark-400/50 text-gray-500 hover:text-gray-300 hover:border-dark-400'}`}
          >
            {s}
          </button>
        ))}
      </div>
    </div>
  )
}

/* ─── Expanded row detail ─────────────────────────────────────────────────────── */
function ExpandedDetail({ incident }) {
  return (
    <div className="px-4 pb-4 pt-2 border-t border-dark-400/30 bg-dark-800/60">
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4 text-xs">
        <div>
          <p className="text-gray-600 mb-1 uppercase tracking-wide text-[10px]">Service</p>
          <p className="text-gray-300 font-mono">{incident.service ?? '—'}</p>
        </div>
        <div>
          <p className="text-gray-600 mb-1 uppercase tracking-wide text-[10px]">Outcome</p>
          <p className={`font-semibold ${
            incident.outcome === 'auto_fixed'  ? 'text-neon-green' :
            incident.outcome === 'escalated'   ? 'text-orange-400' :
            incident.outcome === 'rolled_back' ? 'text-red-400'    : 'text-gray-400'
          }`}>{incident.outcome?.replace('_', ' ') ?? '—'}</p>
        </div>
        <div>
          <p className="text-gray-600 mb-1 uppercase tracking-wide text-[10px]">Resolution Time</p>
          <p className="text-gray-300 font-mono">{formatDuration(incident.resolution_time_ms)}</p>
        </div>
        <div>
          <p className="text-gray-600 mb-1 uppercase tracking-wide text-[10px]">Confidence</p>
          <p className={`font-mono ${
            (incident.confidence ?? 0) >= 70 ? 'text-neon-green' : 'text-yellow-400'
          }`}>{incident.confidence != null ? `${incident.confidence}%` : '—'}</p>
        </div>
      </div>
      {incident.description && (
        <p className="text-xs text-gray-500 mt-3 leading-relaxed">{incident.description}</p>
      )}
      {incident.fix_applied && (
        <div className="mt-3">
          <p className="text-[10px] text-gray-600 uppercase tracking-wide mb-1">Fix Applied</p>
          <pre className="text-xs text-neon-green font-mono bg-dark-800 rounded-lg p-2 overflow-x-auto">
            {incident.fix_applied}
          </pre>
        </div>
      )}
    </div>
  )
}

/* ─── Table Row ──────────────────────────────────────────────────────────────── */
function IncidentRow({ incident, expanded, onToggle }) {
  const sev = formatSeverity(incident.severity)

  return (
    <>
      <tr
        className={`border-b border-dark-400/20 cursor-pointer transition-colors
          ${expanded ? 'bg-dark-700/60' : 'hover:bg-dark-700/30'}`}
        onClick={onToggle}
      >
        <td className="py-3 pl-4 pr-2">
          <div className="flex items-center gap-2">
            <span className={`w-1.5 h-1.5 rounded-full flex-shrink-0 ${sev.dot}`} />
            <span className="text-xs font-mono text-gray-400 whitespace-nowrap">{incident.id?.slice(0,8)}</span>
          </div>
        </td>
        <td className="py-3 px-2">
          <p className="text-xs font-semibold text-gray-200 truncate max-w-[180px]">
            {incident.title ?? incident.type ?? '—'}
          </p>
        </td>
        <td className="py-3 px-2">
          <StatusBadge status={incident.severity} />
        </td>
        <td className="py-3 px-2">
          <StatusBadge status={incident.status} />
        </td>
        <td className="py-3 px-2">
          <span className={`text-xs font-mono ${
            incident.outcome === 'auto_fixed' ? 'text-neon-green' :
            incident.outcome === 'escalated'  ? 'text-orange-400' :
            incident.outcome === 'rolled_back'? 'text-red-400'    : 'text-gray-500'
          }`}>{incident.outcome?.replace('_', ' ') ?? '—'}</span>
        </td>
        <td className="py-3 px-2">
          <span className="text-xs font-mono text-gray-500">
            {formatDuration(incident.resolution_time_ms)}
          </span>
        </td>
        <td className="py-3 px-2 pr-4">
          <span className="text-xs text-gray-600 font-mono whitespace-nowrap">
            {formatTimestamp(incident.detected_at ?? incident.timestamp)}
          </span>
        </td>
        <td className="py-3 pr-4">
          {expanded
            ? <ChevronUp size={14} className="text-gray-500" />
            : <ChevronDown size={14} className="text-gray-600" />}
        </td>
      </tr>
      {expanded && (
        <tr>
          <td colSpan={8} className="p-0">
            <ExpandedDetail incident={incident} />
          </td>
        </tr>
      )}
    </>
  )
}

/* ─── IncidentHistory ────────────────────────────────────────────────────────── */
export default function IncidentHistory({ incidents = [] }) {
  const [search, setSearch]           = useState('')
  const [severityFilter, setSeverity] = useState('all')
  const [statusFilter, setStatus]     = useState('all')
  const [sortBy, setSortBy]           = useState('timestamp')
  const [sortDir, setSortDir]         = useState('desc')
  const [expanded, setExpanded]       = useState(null)

  const toggleExpand = (id) => setExpanded(prev => prev === id ? null : id)

  const toggleSort = (col) => {
    if (sortBy === col) setSortDir(d => d === 'asc' ? 'desc' : 'asc')
    else { setSortBy(col); setSortDir('desc') }
  }

  const filtered = useMemo(() => {
    let list = [...incidents]

    if (search) {
      const q = search.toLowerCase()
      list = list.filter(i =>
        (i.title ?? i.type ?? '').toLowerCase().includes(q) ||
        (i.id ?? '').toLowerCase().includes(q) ||
        (i.service ?? '').toLowerCase().includes(q)
      )
    }
    if (severityFilter !== 'all') list = list.filter(i => i.severity === severityFilter)
    if (statusFilter   !== 'all') list = list.filter(i => i.status   === statusFilter)

    list.sort((a, b) => {
      let av, bv
      if (sortBy === 'timestamp')     { av = new Date(a.detected_at ?? a.timestamp ?? 0); bv = new Date(b.detected_at ?? b.timestamp ?? 0) }
      else if (sortBy === 'severity') { const o = {critical:0,high:1,medium:2,low:3}; av = o[a.severity]??4; bv = o[b.severity]??4 }
      else if (sortBy === 'duration') { av = a.resolution_time_ms ?? 0; bv = b.resolution_time_ms ?? 0 }
      else { av = a[sortBy] ?? ''; bv = b[sortBy] ?? '' }
      return sortDir === 'asc' ? (av > bv ? 1 : -1) : (av < bv ? 1 : -1)
    })

    return list
  }, [incidents, search, severityFilter, statusFilter, sortBy, sortDir])

  const SortHeader = ({ col, children }) => (
    <th
      className="py-2 px-2 text-left text-[10px] font-bold uppercase tracking-widest text-gray-600 cursor-pointer hover:text-gray-400 whitespace-nowrap"
      onClick={() => toggleSort(col)}
    >
      <span className="flex items-center gap-1">
        {children}
        {sortBy === col && (
          sortDir === 'asc'
            ? <ChevronUp size={10} className="text-neon-blue" />
            : <ChevronDown size={10} className="text-neon-blue" />
        )}
      </span>
    </th>
  )

  return (
    <div className="card p-0 overflow-hidden">
      {/* Header */}
      <div className="px-4 pt-4 pb-3 border-b border-dark-400/30">
        <div className="flex items-center justify-between mb-3">
          <h3 className="section-title">Incident History</h3>
          <span className="text-xs font-mono text-gray-600">{filtered.length} records</span>
        </div>
        <FilterBar
          search={search} onSearch={setSearch}
          severityFilter={severityFilter} onSeverity={setSeverity}
          statusFilter={statusFilter} onStatus={setStatus}
        />
      </div>

      {/* Table */}
      <div className="overflow-x-auto scrollbar-thin">
        {filtered.length === 0 ? (
          <div className="py-16 text-center text-gray-600">
            <AlertTriangle size={28} className="mx-auto mb-3 opacity-30" />
            <p className="text-sm">No incidents match your filters</p>
          </div>
        ) : (
          <table className="w-full min-w-[700px]">
            <thead className="border-b border-dark-400/30 bg-dark-800/40">
              <tr>
                <SortHeader col="id">ID</SortHeader>
                <SortHeader col="title">Title</SortHeader>
                <SortHeader col="severity">Severity</SortHeader>
                <SortHeader col="status">Status</SortHeader>
                <th className="py-2 px-2 text-left text-[10px] font-bold uppercase tracking-widest text-gray-600">Outcome</th>
                <SortHeader col="duration">Duration</SortHeader>
                <SortHeader col="timestamp">Detected</SortHeader>
                <th className="py-2 pr-4 w-6" />
              </tr>
            </thead>
            <tbody>
              {filtered.map(incident => (
                <IncidentRow
                  key={incident.id}
                  incident={incident}
                  expanded={expanded === incident.id}
                  onToggle={() => toggleExpand(incident.id)}
                />
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  )
}
