import { useState, useEffect, useCallback, useRef } from 'react'
import Dashboard from './components/Dashboard.jsx'

const WS_URL  = 'ws://localhost:8000/ws'
const API_URL = 'http://localhost:8000/api'

export default function App() {
  const [incidents, setIncidents]         = useState([])
  const [agentStatuses, setAgentStatuses] = useState({
    monitor:    { agent_name: 'monitor',    status: 'idle', last_action: null, incidents_handled: 0 },
    diagnostic: { agent_name: 'diagnostic', status: 'idle', last_action: null, incidents_handled: 0 },
    fixer:      { agent_name: 'fixer',      status: 'idle', last_action: null, incidents_handled: 0 },
    deploy:     { agent_name: 'deploy',     status: 'idle', last_action: null, incidents_handled: 0 },
  })
  const [wsConnected, setWsConnected]     = useState(false)
  const [events, setEvents]               = useState([])
  const [activeIncident, setActiveIncident] = useState(null)

  // ── New state for MCP + Agent Framework ──────────────────────────────────────
  // MCP call events (mcp_call + mcp_response from WebSocket)
  const [mcpEvents, setMcpEvents]         = useState([])
  // Current execution plan (from plan_created / plan_step_update events)
  const [executionPlan, setExecutionPlan] = useState(null)
  // Agent registry data (fetched from /agents/registry)
  const [registryAgents, setRegistryAgents] = useState([])

  const wsRef = useRef(null)
  const reconnectTimer = useRef(null)

  const addEvent = useCallback((event) => {
    setEvents(prev => [event, ...prev].slice(0, 100))
  }, [])

  // ── MCP event handlers ────────────────────────────────────────────────────────

  const handleMcpCall = useCallback((msg) => {
    const data = msg.data || {}
    // Add to MCP events list; mcp_call creates entry, mcp_response updates it
    if (msg.event_type === 'mcp_call') {
      setMcpEvents(prev => {
        // Don't add duplicate call_ids
        if (prev.find(e => e.call_id === data.call_id)) return prev
        return [...prev, data].slice(-200)  // keep last 200
      })
    } else if (msg.event_type === 'mcp_response') {
      setMcpEvents(prev =>
        prev.map(e => e.call_id === data.call_id ? { ...e, ...data } : e)
      )
    }
  }, [])

  const handlePlanEvent = useCallback((msg) => {
    if (msg.event_type === 'plan_created') {
      setExecutionPlan(msg.data)
    } else if (msg.event_type === 'plan_step_update') {
      const { plan_id, step, plan_status, current_step_num } = msg.data
      setExecutionPlan(prev => {
        if (!prev || prev.plan_id !== plan_id) return prev
        return {
          ...prev,
          status: plan_status,
          current_step_num,
          steps: prev.steps.map(s => s.step_num === step.step_num ? step : s),
        }
      })
    }
  }, [])

  // ── Data fetching ─────────────────────────────────────────────────────────────

  const fetchInitialData = useCallback(async () => {
    try {
      const [incidentsRes, agentsRes, registryRes] = await Promise.all([
        fetch(`${API_URL}/incidents`),
        fetch(`${API_URL}/agents/status`),
        fetch(`${API_URL}/agents/registry`),
      ])
      if (incidentsRes.ok) {
        const data = await incidentsRes.json()
        setIncidents(data)
        if (data.length > 0) setActiveIncident(data[data.length - 1])
      }
      if (agentsRes.ok) {
        const agents = await agentsRes.json()
        const statusMap = {}
        agents.forEach(a => { statusMap[a.agent_name] = a })
        setAgentStatuses(prev => ({ ...prev, ...statusMap }))
      }
      if (registryRes.ok) {
        const data = await registryRes.json()
        setRegistryAgents(data.agents || [])
      }
    } catch (e) {
      console.warn('Could not fetch initial data:', e.message)
    }
  }, [])

  const fetchRegistry = useCallback(async () => {
    try {
      const res = await fetch(`${API_URL}/agents/registry`)
      if (res.ok) {
        const data = await res.json()
        setRegistryAgents(data.agents || [])
      }
    } catch (e) {
      console.warn('Registry fetch failed:', e.message)
    }
  }, [])

  // ── WebSocket ─────────────────────────────────────────────────────────────────

  const handleWsMessage = useCallback((msg) => {
    // General event log — normalize to consistent shape for activity feed
    addEvent({
      type:        msg.event_type,
      agent:       msg.agent,
      incident_id: msg.incident_id,
      message:     msg.data?.message || msg.data?.action || msg.event_type,
      tool_name:   msg.data?.tool_name,
      action:      msg.data?.action,
      data:        msg.data,
      timestamp:   msg.timestamp || new Date().toISOString(),
    })

    // State transition → update incident list
    if (msg.event_type === 'state_transition' && msg.data?.incident) {
      const updated = msg.data.incident
      setIncidents(prev => {
        const idx = prev.findIndex(i => i.id === updated.id)
        if (idx >= 0) {
          const next = [...prev]; next[idx] = updated; return next
        }
        return [updated, ...prev]
      })
      setActiveIncident(updated)
    }

    // Agent activity → update agent status card
    if (msg.event_type === 'agent_activity' && msg.data?.agent) {
      const agentName = msg.data.agent
      setAgentStatuses(prev => ({
        ...prev,
        [agentName]: {
          ...prev[agentName],
          agent_name: agentName,
          status: 'working',
          last_action: msg.data.action,
          last_action_time: msg.timestamp,
        },
      }))
      setTimeout(() => {
        setAgentStatuses(prev => ({
          ...prev,
          [agentName]: { ...prev[agentName], status: 'idle' },
        }))
      }, 3000)
    }

    // MCP call/response → update MCP flow view
    if (msg.event_type === 'mcp_call' || msg.event_type === 'mcp_response') {
      handleMcpCall(msg)
    }

    // Execution plan → update plan view
    if (msg.event_type === 'plan_created' || msg.event_type === 'plan_step_update') {
      handlePlanEvent(msg)
    }
  }, [addEvent, handleMcpCall, handlePlanEvent])

  const connectWS = useCallback(() => {
    if (wsRef.current?.readyState === WebSocket.OPEN) return
    const ws = new WebSocket(WS_URL)
    wsRef.current = ws

    ws.onopen = () => {
      setWsConnected(true)
      addEvent({ type: 'system', message: 'Connected to CodeOps Sentinel', timestamp: new Date().toISOString() })
      if (reconnectTimer.current) clearTimeout(reconnectTimer.current)
    }
    ws.onclose = () => {
      setWsConnected(false)
      addEvent({ type: 'system', message: 'WebSocket disconnected. Reconnecting...', timestamp: new Date().toISOString() })
      reconnectTimer.current = setTimeout(connectWS, 3000)
    }
    ws.onerror = () => {
      addEvent({ type: 'error', message: 'WebSocket connection error', timestamp: new Date().toISOString() })
    }
    ws.onmessage = (e) => {
      try {
        const msg = JSON.parse(e.data)
        handleWsMessage(msg)
      } catch (err) {
        console.warn('WS parse error:', err)
      }
    }
  }, [addEvent, handleWsMessage])

  useEffect(() => {
    fetchInitialData()
    connectWS()
    return () => {
      if (reconnectTimer.current) clearTimeout(reconnectTimer.current)
      wsRef.current?.close()
    }
  }, [fetchInitialData, connectWS])

  // ── Actions ───────────────────────────────────────────────────────────────────

  // Map SimulateButton string IDs → backend scenario indices
  const SCENARIO_ID_MAP = {
    cpu_spike:       0,
    memory_leak:     1,
    service_down:    2,
    high_error_rate: 2,
    slow_queries:    4,
    network_latency: 3,
    crash_loop:      5,
    gateway_502:     6,
    db_replica:      7,
  }

  const simulateIncident = async (scenarioArg = null) => {
    // Accept either a string scenario ID or a numeric index
    const scenarioIndex = typeof scenarioArg === 'string'
      ? (SCENARIO_ID_MAP[scenarioArg] ?? null)
      : scenarioArg

    // Clear previous MCP events and plan when starting a new incident
    setMcpEvents([])
    setExecutionPlan(null)

    try {
      const url = scenarioIndex !== null
        ? `${API_URL}/incidents/simulate?scenario_index=${scenarioIndex}`
        : `${API_URL}/incidents/simulate`
      const res = await fetch(url, { method: 'POST' })
      if (res.ok) {
        const incident = await res.json()
        setIncidents(prev => {
          const idx = prev.findIndex(i => i.id === incident.id)
          if (idx >= 0) { const next = [...prev]; next[idx] = incident; return next }
          return [incident, ...prev]
        })
        setActiveIncident(incident)
        addEvent({ type: 'simulate', message: `Simulating: ${incident.title}`, timestamp: new Date().toISOString() })
      }
    } catch (e) {
      addEvent({ type: 'error', message: `Failed to simulate: ${e.message}`, timestamp: new Date().toISOString() })
    }
  }

  const clearAll = async () => {
    try {
      await fetch(`${API_URL}/incidents`, { method: 'DELETE' })
      setIncidents([])
      setActiveIncident(null)
      setEvents([])
      setMcpEvents([])
      setExecutionPlan(null)
      setAgentStatuses(prev =>
        Object.fromEntries(Object.entries(prev).map(([k, v]) => [k, { ...v, status: 'idle', last_action: null }]))
      )
    } catch (e) {
      console.warn('Clear failed:', e)
    }
  }

  const triggerMcpTool = async (toolName) => {
    try {
      const res = await fetch(
        `${API_URL}/mcp/call?tool_name=${encodeURIComponent(toolName)}&from_agent=dashboard`,
        {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ service: 'test' }),
        }
      )
      if (res.ok) {
        addEvent({
          type: 'mcp_call',
          message: `Manual MCP call: ${toolName}`,
          timestamp: new Date().toISOString(),
        })
        // Refresh registry after manual trigger
        await fetchRegistry()
      }
    } catch (e) {
      console.warn('MCP tool trigger failed:', e.message)
    }
  }

  return (
    <Dashboard
      incidents={incidents}
      agentStatuses={agentStatuses}
      wsConnected={wsConnected}
      events={events}
      activeIncident={activeIncident}
      onSelectIncident={setActiveIncident}
      onSimulate={simulateIncident}
      onClear={clearAll}
      mcpEvents={mcpEvents}
      executionPlan={executionPlan}
      registryAgents={registryAgents}
      onTriggerTool={triggerMcpTool}
    />
  )
}
