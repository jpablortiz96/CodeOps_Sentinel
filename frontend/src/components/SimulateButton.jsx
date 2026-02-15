import { useState } from 'react'
import { Zap, X, ChevronRight, AlertTriangle, Server, Database, Cpu, Globe, HardDrive } from 'lucide-react'

const SCENARIOS = [
  {
    id: 'cpu_spike',
    label: 'CPU Spike',
    icon: Cpu,
    severity: 'critical',
    color: 'text-red-400',
    desc: 'Sudden CPU utilization spike to 98% on prod node',
  },
  {
    id: 'memory_leak',
    label: 'Memory Leak',
    icon: HardDrive,
    severity: 'high',
    color: 'text-orange-400',
    desc: 'Gradual memory climb, OOM imminent on API pods',
  },
  {
    id: 'service_down',
    label: 'Service Down',
    icon: Server,
    severity: 'critical',
    color: 'text-red-400',
    desc: 'Payment service health check returning 503',
  },
  {
    id: 'high_error_rate',
    label: 'High Error Rate',
    icon: AlertTriangle,
    severity: 'high',
    color: 'text-orange-400',
    desc: '5xx error rate spiked to 34% — SLO breach',
  },
  {
    id: 'slow_queries',
    label: 'Slow Queries',
    icon: Database,
    severity: 'medium',
    color: 'text-yellow-400',
    desc: 'P99 query latency exceeds 2s threshold',
  },
  {
    id: 'network_latency',
    label: 'Network Latency',
    icon: Globe,
    severity: 'medium',
    color: 'text-yellow-400',
    desc: 'Cross-AZ latency spikes — inter-service impact',
  },
  {
    id: 'crash_loop',
    label: 'CrashLoopBackOff',
    icon: Server,
    severity: 'critical',
    color: 'text-red-400',
    desc: 'auth-service pod restart loop — CrashLoopBackOff',
  },
  {
    id: 'gateway_502',
    label: '502 Gateway',
    icon: Globe,
    severity: 'high',
    color: 'text-orange-400',
    desc: 'API gateway returning 502 Bad Gateway upstream',
  },
]

const SEV_COLORS = {
  critical: 'border-red-500/30 bg-red-500/8 hover:border-red-500/60 hover:bg-red-500/15',
  high:     'border-orange-500/30 bg-orange-500/8 hover:border-orange-500/60 hover:bg-orange-500/15',
  medium:   'border-yellow-500/30 bg-yellow-500/8 hover:border-yellow-500/60 hover:bg-yellow-500/15',
}

export default function SimulateButton({ onSimulate, isRunning = false }) {
  const [open, setOpen] = useState(false)

  const handleSelect = (scenario) => {
    setOpen(false)
    onSimulate?.(scenario.id)
  }

  return (
    <>
      {/* Floating trigger button */}
      <button
        onClick={() => setOpen(true)}
        disabled={isRunning}
        className={`
          fixed bottom-10 right-6 z-40
          flex items-center gap-2 px-4 py-3 rounded-2xl
          font-bold text-sm border transition-all duration-300
          ${isRunning
            ? 'bg-dark-700 border-dark-400 text-gray-500 cursor-not-allowed'
            : 'bg-gradient-to-r from-neon-blue/20 to-neon-purple/20 border-neon-blue/40 text-white hover:from-neon-blue/30 hover:to-neon-purple/30 hover:border-neon-blue/70 hover:scale-105'}
        `}
        style={!isRunning ? { boxShadow: '0 0 24px rgba(0,212,255,0.25), 0 4px 16px rgba(0,0,0,0.4)' } : {}}
      >
        <Zap size={16} className={isRunning ? '' : 'text-neon-blue'} />
        {isRunning ? 'Running…' : 'Simulate'}
      </button>

      {/* Modal overlay */}
      {open && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center p-4"
          style={{ background: 'rgba(6,7,13,0.85)', backdropFilter: 'blur(8px)' }}
          onClick={() => setOpen(false)}
        >
          <div
            className="w-full max-w-lg"
            onClick={e => e.stopPropagation()}
            style={{
              background: 'rgba(13,17,23,0.95)',
              border: '1px solid rgba(0,212,255,0.2)',
              borderRadius: 20,
              boxShadow: '0 0 40px rgba(0,212,255,0.12), 0 20px 60px rgba(0,0,0,0.6)',
            }}
          >
            {/* Modal header */}
            <div className="flex items-center justify-between px-5 py-4 border-b border-dark-400/40">
              <div className="flex items-center gap-3">
                <div className="p-2 rounded-xl bg-neon-blue/10 border border-neon-blue/20">
                  <Zap size={16} className="text-neon-blue" />
                </div>
                <div>
                  <h2 className="text-sm font-bold text-white">Simulate Incident</h2>
                  <p className="text-xs text-gray-500">Select a failure scenario to trigger</p>
                </div>
              </div>
              <button
                onClick={() => setOpen(false)}
                className="p-1.5 rounded-lg hover:bg-dark-600 text-gray-500 hover:text-gray-300 transition-colors"
              >
                <X size={16} />
              </button>
            </div>

            {/* Scenario grid */}
            <div className="p-4 grid grid-cols-1 gap-2 max-h-96 overflow-y-auto scrollbar-thin">
              {SCENARIOS.map(scenario => {
                const Icon = scenario.icon
                return (
                  <button
                    key={scenario.id}
                    onClick={() => handleSelect(scenario)}
                    className={`
                      flex items-center gap-3 p-3 rounded-xl border text-left
                      transition-all duration-200 group
                      ${SEV_COLORS[scenario.severity] ?? SEV_COLORS.medium}
                    `}
                  >
                    <Icon size={16} className={`${scenario.color} flex-shrink-0`} />
                    <div className="min-w-0 flex-1">
                      <div className="flex items-center gap-2">
                        <span className="text-sm font-semibold text-gray-200">{scenario.label}</span>
                        <span className={`text-xs uppercase font-bold ${scenario.color}`}>
                          {scenario.severity}
                        </span>
                      </div>
                      <p className="text-xs text-gray-500 truncate mt-0.5">{scenario.desc}</p>
                    </div>
                    <ChevronRight size={14} className="text-gray-600 group-hover:text-gray-300 flex-shrink-0 transition-colors" />
                  </button>
                )
              })}
            </div>

            {/* Footer */}
            <div className="px-5 py-3 border-t border-dark-400/30">
              <p className="text-xs text-gray-600 text-center font-mono">
                Azure MCP Server · Microsoft Agent Framework · Real-time orchestration
              </p>
            </div>
          </div>
        </div>
      )}
    </>
  )
}
