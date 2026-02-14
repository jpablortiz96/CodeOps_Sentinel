import { useState, useEffect, useCallback, useRef } from 'react'
import Dashboard from './components/Dashboard.jsx'

const WS_URL = 'ws://localhost:8000/ws'
const API_URL = 'http://localhost:8000/api'

export default function App() {
  const [incidents, setIncidents] = useState([])
  const [agentStatuses, setAgentStatuses] = useState({
    monitor: { agent_name: 'monitor', status: 'idle', last_action: null, incidents_handled: 0 },
    diagnostic: { agent_name: 'diagnostic', status: 'idle', last_action: null, incidents_handled: 0 },
    fixer: { agent_name: 'fixer', status: 'idle', last_action: null, incidents_handled: 0 },
    deploy: { agent_name: 'deploy', status: 'idle', last_action: null, incidents_handled: 0 },
  })
  const [wsConnected, setWsConnected] = useState(false)
  const [events, setEvents] = useState([])
  const [activeIncident, setActiveIncident] = useState(null)
  const wsRef = useRef(null)
  const reconnectTimer = useRef(null)

  const addEvent = useCallback((event) => {
    setEvents(prev => [event, ...prev].slice(0, 100))
  }, [])

  const fetchInitialData = useCallback(async () => {
    try {
      const [incidentsRes, agentsRes] = await Promise.all([
        fetch(`${API_URL}/incidents`),
        fetch(`${API_URL}/agents/status`),
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
    } catch (e) {
      console.warn('Could not fetch initial data:', e.message)
    }
  }, [])

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
  }, [addEvent])

  const handleWsMessage = useCallback((msg) => {
    addEvent({
      type: msg.event_type,
      agent: msg.agent,
      incident_id: msg.incident_id,
      message: msg.data?.message || msg.data?.action || msg.event_type,
      data: msg.data,
      timestamp: msg.timestamp,
    })

    if (msg.event_type === 'state_transition' && msg.data?.incident) {
      const updated = msg.data.incident
      setIncidents(prev => {
        const idx = prev.findIndex(i => i.id === updated.id)
        if (idx >= 0) {
          const next = [...prev]
          next[idx] = updated
          return next
        }
        return [updated, ...prev]
      })
      setActiveIncident(updated)
    }

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

      // Reset to idle after a delay
      setTimeout(() => {
        setAgentStatuses(prev => ({
          ...prev,
          [agentName]: { ...prev[agentName], status: 'idle' },
        }))
      }, 3000)
    }
  }, [addEvent])

  useEffect(() => {
    fetchInitialData()
    connectWS()
    return () => {
      if (reconnectTimer.current) clearTimeout(reconnectTimer.current)
      wsRef.current?.close()
    }
  }, [fetchInitialData, connectWS])

  const simulateIncident = async (scenarioIndex = null) => {
    try {
      const url = scenarioIndex !== null
        ? `${API_URL}/incidents/simulate?scenario_index=${scenarioIndex}`
        : `${API_URL}/incidents/simulate`
      const res = await fetch(url, { method: 'POST' })
      if (res.ok) {
        const incident = await res.json()
        setIncidents(prev => {
          const idx = prev.findIndex(i => i.id === incident.id)
          if (idx >= 0) {
            const next = [...prev]; next[idx] = incident; return next
          }
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
      setAgentStatuses(prev => Object.fromEntries(
        Object.entries(prev).map(([k, v]) => [k, { ...v, status: 'idle', last_action: null }])
      ))
    } catch (e) {
      console.warn('Clear failed:', e)
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
    />
  )
}
