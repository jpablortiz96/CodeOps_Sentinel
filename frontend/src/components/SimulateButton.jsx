import { useState, useEffect } from 'react'
import {
  Zap, X, AlertTriangle, Database, Cpu, Globe,
  HardDrive, StopCircle, Loader, Server,
} from 'lucide-react'
import { API_URL } from '../config'

/* ── Experimentos reales → ShopDemo ──────────────────────────────────────────── */
const CHAOS_EXPERIMENTS = [
  {
    id: 'memory-leak',
    emoji: '🧠',
    label: 'Memory Leak',
    icon: HardDrive,
    desc: '~1 MB/s alloc hasta OOM',
    accent: '#f97316',
    glow: 'rgba(249,115,22,0.35)',
  },
  {
    id: 'cpu-spike',
    emoji: '🔥',
    label: 'CPU Spike',
    icon: Cpu,
    desc: '2 burn threads → ~100% CPU',
    accent: '#ef4444',
    glow: 'rgba(239,68,68,0.35)',
  },
  {
    id: 'latency',
    emoji: '🐌',
    label: 'High Latency',
    icon: Globe,
    desc: '3-5s delay en cada request',
    accent: '#eab308',
    glow: 'rgba(234,179,8,0.35)',
  },
  {
    id: 'error-rate',
    emoji: '❌',
    label: 'Error Rate',
    icon: AlertTriangle,
    desc: '50 % de /products → 500',
    accent: '#f97316',
    glow: 'rgba(249,115,22,0.35)',
  },
  {
    id: 'db-connection',
    emoji: '🔌',
    label: 'DB Connection',
    icon: Database,
    desc: 'Todos los /orders → 503',
    accent: '#a855f7',
    glow: 'rgba(168,85,247,0.35)',
  },
]

/* ── Scenarios simulados (mock pipeline) ─────────────────────────────────────── */
const MOCK_SCENARIOS = [
  {
    id: 'k8s_crashloop',
    emoji: '💥',
    label: 'CrashLoop',
    icon: Server,
    desc: 'OOMKilled exit 137',
    accent: '#ef4444',
    scenarioIndex: 5,
  },
  {
    id: 'api_gateway_502',
    emoji: '🌐',
    label: '502 Gateway',
    icon: Globe,
    desc: 'Upstream timeout cascade',
    accent: '#f97316',
    scenarioIndex: 6,
  },
  {
    id: 'db_replication_lag',
    emoji: '🗄️',
    label: 'Repl. Lag',
    icon: Database,
    desc: '47 s behind primary',
    accent: '#eab308',
    scenarioIndex: 7,
  },
]

/* ── Toast con auto-dismiss ──────────────────────────────────────────────────── */
function Toast({ result, onDismiss }) {
  const [visible, setVisible] = useState(true)

  useEffect(() => {
    if (!result) return
    setVisible(true)
    const t1 = setTimeout(() => setVisible(false), 3600)   // start fade
    const t2 = setTimeout(() => onDismiss(), 4000)          // remove
    return () => { clearTimeout(t1); clearTimeout(t2) }
  }, [result, onDismiss])

  if (!result) return null

  return (
    <div
      onClick={onDismiss}
      style={{
        position: 'fixed',
        bottom: 112,
        right: 24,
        zIndex: 60,
        maxWidth: 280,
        cursor: 'pointer',
        transition: 'opacity 0.4s ease',
        opacity: visible ? 1 : 0,
        backdropFilter: 'blur(12px)',
        background: result.ok
          ? 'rgba(0,255,136,0.08)'
          : 'rgba(255,50,90,0.10)',
        border: `1px solid ${result.ok ? 'rgba(0,255,136,0.35)' : 'rgba(255,50,90,0.35)'}`,
        borderRadius: 12,
        padding: '10px 14px',
        boxShadow: result.ok
          ? '0 0 16px rgba(0,255,136,0.12)'
          : '0 0 16px rgba(255,50,90,0.12)',
      }}
    >
      <p style={{
        fontFamily: 'monospace',
        fontSize: 11,
        color: result.ok ? '#00ff88' : '#ff3366',
        lineHeight: 1.4,
        margin: 0,
      }}>
        {result.ok ? '✓ ' : '✕ '}{result.msg}
      </p>
    </div>
  )
}

/* ── Card de scenario simulado ───────────────────────────────────────────────── */
function MockCard({ scenario, disabled, onClick }) {
  const [hov, setHov] = useState(false)
  return (
    <button
      onClick={onClick}
      onMouseEnter={() => setHov(true)}
      onMouseLeave={() => setHov(false)}
      style={{
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        gap: 5,
        padding: '10px 8px',
        borderRadius: 12,
        border: `1px solid ${hov ? scenario.accent + '60' : 'rgba(255,255,255,0.06)'}`,
        background: hov ? `${scenario.accent}10` : 'rgba(255,255,255,0.02)',
        cursor: disabled ? 'not-allowed' : 'pointer',
        transition: 'all 0.15s ease',
        opacity: disabled ? 0.45 : 0.8,
      }}
    >
      <span style={{ fontSize: 16 }}>{scenario.emoji}</span>
      <span style={{
        fontSize: 9,
        fontWeight: 600,
        color: hov ? scenario.accent : '#9ca3af',
        fontFamily: 'monospace',
        textAlign: 'center',
        lineHeight: 1.2,
      }}>
        {scenario.label}
      </span>
    </button>
  )
}

/* ── Card de experimento ─────────────────────────────────────────────────────── */
function ExpCard({ exp, busy, disabled, onClick }) {
  const [hovered, setHovered] = useState(false)

  return (
    <button
      onClick={onClick}
      disabled={disabled}
      onMouseEnter={() => setHovered(true)}
      onMouseLeave={() => setHovered(false)}
      style={{
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'flex-start',
        gap: 6,
        padding: '12px 14px',
        borderRadius: 14,
        border: `1px solid ${hovered && !disabled ? exp.accent + '80' : 'rgba(255,255,255,0.07)'}`,
        background: hovered && !disabled
          ? `${exp.accent}12`
          : 'rgba(255,255,255,0.03)',
        cursor: disabled ? 'not-allowed' : 'pointer',
        opacity: disabled && !busy ? 0.45 : 1,
        transition: 'all 0.18s ease',
        boxShadow: hovered && !disabled ? `0 0 12px ${exp.glow}` : 'none',
        textAlign: 'left',
        width: '100%',
      }}
    >
      <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
        {busy
          ? <Loader size={16} style={{ color: '#00d4ff', animation: 'spin 1s linear infinite' }} />
          : <span style={{ fontSize: 18, lineHeight: 1 }}>{exp.emoji}</span>
        }
        <span style={{
          fontSize: 12,
          fontWeight: 700,
          color: hovered && !disabled ? exp.accent : '#e5e7eb',
          transition: 'color 0.18s',
        }}>
          {exp.label}
        </span>
      </div>
      <p style={{
        fontSize: 10,
        color: '#6b7280',
        margin: 0,
        lineHeight: 1.3,
        fontFamily: 'monospace',
      }}>
        {exp.desc}
      </p>
    </button>
  )
}

/* ── Componente principal ─────────────────────────────────────────────────────── */
export default function SimulateButton({ onSimulate, isRunning = false, chaosActive = false }) {
  const [open, setOpen]             = useState(false)
  const [injecting, setInjecting]   = useState(null)
  const [stopping, setStopping]     = useState(false)
  const [lastResult, setLastResult] = useState(null)
  // Track local chaos state (turns Stop All visible after inject)
  const [localChaos, setLocalChaos] = useState(chaosActive)

  // Sync with prop
  useEffect(() => { setLocalChaos(chaosActive) }, [chaosActive])

  /* ── Inject chaos ── */
  const handleChaosInject = async (exp) => {
    setInjecting(exp.id)
    setLastResult(null)
    try {
      const resp = await fetch(`${API_URL}/chaos/inject/${exp.id}`, { method: 'POST' })
      const data = await resp.json()
      if (resp.ok) {
        setLocalChaos(true)
        setLastResult({ ok: true, msg: `"${exp.label}" inyectado — incidente ${data.incident_id}` })
      } else {
        setLastResult({ ok: false, msg: data.detail ?? 'Error al inyectar' })
      }
    } catch (err) {
      setLastResult({ ok: false, msg: `Network error: ${err.message}` })
    } finally {
      setInjecting(null)
      setOpen(false)
    }
  }

  /* ── Mock simulate ── */
  const handleMockSimulate = (scenario) => {
    setOpen(false)
    onSimulate?.(scenario.scenarioIndex)
  }

  /* ── Stop all ── */
  const handleStopAll = async () => {
    setStopping(true)
    setLastResult(null)
    try {
      const resp = await fetch(`${API_URL}/chaos/stop`, { method: 'POST' })
      const data = await resp.json()
      if (resp.ok) {
        setLocalChaos(false)
        const stopped = data.stopped ?? []
        setLastResult({
          ok: true,
          msg: stopped.length > 0
            ? `Detenido: ${stopped.join(', ')}`
            : 'No había chaos activo',
        })
      } else {
        setLastResult({ ok: false, msg: data.detail ?? 'Error al detener' })
      }
    } catch (err) {
      setLastResult({ ok: false, msg: `Network error: ${err.message}` })
    } finally {
      setStopping(false)
    }
  }

  const busy = isRunning || !!injecting

  return (
    <>
      {/* ── Toast ── */}
      <Toast result={lastResult} onDismiss={() => setLastResult(null)} />

      {/* ── Popup modal (abre arriba del botón) ── */}
      {open && (
        <>
          {/* Backdrop */}
          <div
            onClick={() => setOpen(false)}
            style={{
              position: 'fixed',
              inset: 0,
              zIndex: 48,
              background: 'rgba(6,7,13,0.7)',
              backdropFilter: 'blur(6px)',
            }}
          />

          {/* Panel — anclado a bottom-right, se expande hacia arriba */}
          <div
            onClick={e => e.stopPropagation()}
            style={{
              position: 'fixed',
              bottom: localChaos ? 136 : 84,  // arriba del stack de botones
              right: 24,
              zIndex: 49,
              width: 340,
              maxHeight: 'calc(100vh - 160px)',
              overflowY: 'auto',
              background: 'rgba(11,13,20,0.97)',
              border: '1px solid rgba(0,212,255,0.18)',
              borderRadius: 20,
              boxShadow: '0 0 40px rgba(0,212,255,0.10), 0 -8px 40px rgba(0,0,0,0.7)',
            }}
          >
            {/* Header */}
            <div style={{
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'space-between',
              padding: '14px 16px 12px',
              borderBottom: '1px solid rgba(255,255,255,0.06)',
            }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                <div style={{
                  padding: '6px 8px',
                  borderRadius: 10,
                  background: 'rgba(0,212,255,0.08)',
                  border: '1px solid rgba(0,212,255,0.18)',
                }}>
                  <Zap size={14} style={{ color: '#00d4ff' }} />
                </div>
                <div>
                  <p style={{ fontSize: 13, fontWeight: 700, color: '#fff', margin: 0 }}>
                    ⚡ Inject Chaos
                  </p>
                  <p style={{ fontSize: 10, color: '#6b7280', margin: 0, fontFamily: 'monospace' }}>
                    Real → ShopDemo · Simulado → mock pipeline
                  </p>
                </div>
              </div>
              <button
                onClick={() => setOpen(false)}
                style={{
                  background: 'transparent',
                  border: 'none',
                  cursor: 'pointer',
                  padding: 6,
                  borderRadius: 8,
                  color: '#6b7280',
                  display: 'flex',
                  alignItems: 'center',
                }}
              >
                <X size={16} />
              </button>
            </div>

            {/* Real chaos grid 2 columns */}
            <div style={{ padding: '12px 14px 8px' }}>
              <p style={{
                fontSize: 9,
                fontWeight: 700,
                color: '#00d4ff',
                letterSpacing: '0.1em',
                textTransform: 'uppercase',
                fontFamily: 'monospace',
                marginBottom: 8,
              }}>
                ● Real — ShopDemo App
              </p>
              <div style={{
                display: 'grid',
                gridTemplateColumns: '1fr 1fr',
                gap: 8,
              }}>
                {CHAOS_EXPERIMENTS.map(exp => (
                  <ExpCard
                    key={exp.id}
                    exp={exp}
                    busy={injecting === exp.id}
                    disabled={!!injecting}
                    onClick={() => handleChaosInject(exp)}
                  />
                ))}
              </div>
            </div>

            {/* Simulated section */}
            <div style={{ padding: '8px 14px 14px' }}>
              <p style={{
                fontSize: 9,
                fontWeight: 700,
                color: '#4b5563',
                letterSpacing: '0.1em',
                textTransform: 'uppercase',
                fontFamily: 'monospace',
                marginBottom: 8,
              }}>
                ○ Simulado — Mock Pipeline
              </p>
              <div style={{
                display: 'grid',
                gridTemplateColumns: '1fr 1fr 1fr',
                gap: 6,
              }}>
                {MOCK_SCENARIOS.map(scenario => (
                  <MockCard
                    key={scenario.id}
                    scenario={scenario}
                    disabled={!!injecting}
                    onClick={() => handleMockSimulate(scenario)}
                  />
                ))}
              </div>
            </div>

            {/* Footer */}
            <div style={{
              padding: '10px 16px',
              borderTop: '1px solid rgba(255,255,255,0.05)',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'space-between',
            }}>
              <span style={{ fontSize: 9, color: '#374151', fontFamily: 'monospace' }}>
                Azure MCP · Agent Framework
              </span>
              <button
                onClick={handleStopAll}
                disabled={stopping}
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  gap: 5,
                  background: 'transparent',
                  border: 'none',
                  cursor: stopping ? 'not-allowed' : 'pointer',
                  color: '#f87171',
                  fontSize: 10,
                  fontFamily: 'monospace',
                  padding: '4px 8px',
                  borderRadius: 6,
                }}
              >
                {stopping ? <Loader size={11} style={{ animation: 'spin 1s linear infinite' }} /> : <StopCircle size={11} />}
                Stop all chaos
              </button>
            </div>
          </div>
        </>
      )}

      {/* ── Stack vertical de botones flotantes ─────────────────────────────── */}
      <div style={{
        position: 'fixed',
        bottom: 24,
        right: 24,
        zIndex: 50,
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'flex-end',
        gap: 12,
      }}>

        {/* Botón Stop All — solo visible cuando hay chaos activo */}
        <div style={{
          overflow: 'hidden',
          maxHeight: localChaos ? 60 : 0,
          opacity: localChaos ? 1 : 0,
          transform: localChaos ? 'translateY(0)' : 'translateY(12px)',
          transition: 'max-height 0.3s ease, opacity 0.3s ease, transform 0.3s ease',
        }}>
          <button
            onClick={handleStopAll}
            disabled={stopping}
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: 8,
              padding: '10px 20px',
              borderRadius: 16,
              border: '1px solid rgba(255,51,102,0.5)',
              background: stopping
                ? 'rgba(40,20,30,0.9)'
                : 'rgba(255,51,102,0.9)',
              color: '#fff',
              fontSize: 13,
              fontWeight: 700,
              cursor: stopping ? 'not-allowed' : 'pointer',
              transition: 'all 0.2s ease',
              boxShadow: localChaos && !stopping
                ? '0 0 20px rgba(255,51,102,0.4), 0 4px 16px rgba(0,0,0,0.4)'
                : '0 4px 16px rgba(0,0,0,0.3)',
              animation: localChaos && !stopping ? 'chaosPulse 2s ease-in-out infinite' : 'none',
              whiteSpace: 'nowrap',
            }}
          >
            {stopping
              ? <Loader size={15} style={{ animation: 'spin 1s linear infinite' }} />
              : <StopCircle size={15} />
            }
            {stopping ? 'Deteniendo…' : '🛑 Stop All'}
          </button>
        </div>

        {/* Botón Inject Chaos — siempre visible */}
        <button
          onClick={() => setOpen(o => !o)}
          disabled={busy}
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: 8,
            padding: '12px 24px',
            borderRadius: 16,
            border: 'none',
            background: busy
              ? 'rgba(30,40,60,0.9)'
              : 'linear-gradient(135deg, #00d4ff 0%, #aa66ff 100%)',
            color: busy ? '#6b7280' : '#fff',
            fontSize: 13,
            fontWeight: 700,
            cursor: busy ? 'not-allowed' : 'pointer',
            transition: 'transform 0.2s ease, box-shadow 0.2s ease, opacity 0.2s ease',
            boxShadow: busy
              ? 'none'
              : open
                ? '0 0 32px rgba(0,212,255,0.5), 0 4px 20px rgba(0,0,0,0.5)'
                : '0 0 24px rgba(0,212,255,0.3), 0 4px 16px rgba(0,0,0,0.4)',
            transform: open ? 'scale(1.04)' : 'scale(1)',
            whiteSpace: 'nowrap',
          }}
          onMouseEnter={e => {
            if (!busy) e.currentTarget.style.transform = 'scale(1.05)'
          }}
          onMouseLeave={e => {
            if (!busy) e.currentTarget.style.transform = open ? 'scale(1.04)' : 'scale(1)'
          }}
        >
          {busy
            ? <Loader size={15} style={{ animation: 'spin 1s linear infinite' }} />
            : <Zap size={15} style={{ animation: 'zapPulse 2s ease-in-out infinite' }} />
          }
          {isRunning ? 'Running…' : injecting ? 'Injecting…' : '⚡ Inject Chaos'}
        </button>
      </div>

      {/* Keyframe animations via <style> tag */}
      <style>{`
        @keyframes chaosPulse {
          0%, 100% { box-shadow: 0 0 20px rgba(255,51,102,0.4), 0 4px 16px rgba(0,0,0,0.4); }
          50%       { box-shadow: 0 0 36px rgba(255,51,102,0.7), 0 4px 20px rgba(0,0,0,0.5); }
        }
        @keyframes zapPulse {
          0%, 100% { opacity: 1;   transform: scale(1); }
          50%       { opacity: 0.8; transform: scale(0.9); }
        }
        @keyframes spin {
          from { transform: rotate(0deg); }
          to   { transform: rotate(360deg); }
        }
      `}</style>
    </>
  )
}
