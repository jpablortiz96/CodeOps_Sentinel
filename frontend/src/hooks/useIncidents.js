import { useState, useCallback, useRef } from 'react'

const API = '/api'

/**
 * useIncidents — manages incident state and fetching.
 *
 * Returns:
 *   incidents        — array of incident objects
 *   currentIncident  — latest/active incident
 *   isLoading
 *   fetchIncidents()
 *   fetchIncident(id)
 *   addOrUpdate(incident)   — upsert by id
 *   clearAll()
 */
export function useIncidents() {
  const [incidents, setIncidents]             = useState([])
  const [currentIncident, setCurrentIncident] = useState(null)
  const [isLoading, setIsLoading]             = useState(false)
  const abortRef                              = useRef(null)

  const fetchIncidents = useCallback(async () => {
    setIsLoading(true)
    try {
      const res  = await fetch(`${API}/incidents`)
      const data = await res.json()
      const list = Array.isArray(data) ? data : (data.incidents ?? [])
      setIncidents(list)
      // set currentIncident to latest open one, or most recent
      const open = list.find(i => i.status === 'open')
      setCurrentIncident(open ?? list[0] ?? null)
    } catch (err) {
      console.error('[useIncidents] fetchIncidents error:', err)
    } finally {
      setIsLoading(false)
    }
  }, [])

  const fetchIncident = useCallback(async (id) => {
    abortRef.current?.abort()
    abortRef.current = new AbortController()
    try {
      const res  = await fetch(`${API}/incidents/${id}`, { signal: abortRef.current.signal })
      const data = await res.json()
      setCurrentIncident(data)
      return data
    } catch (err) {
      if (err.name !== 'AbortError') console.error('[useIncidents] fetchIncident error:', err)
      return null
    }
  }, [])

  const addOrUpdate = useCallback((incident) => {
    if (!incident?.id) return
    setIncidents(prev => {
      const idx = prev.findIndex(i => i.id === incident.id)
      if (idx === -1) return [incident, ...prev]
      const next = [...prev]
      next[idx] = { ...next[idx], ...incident }
      return next
    })
    setCurrentIncident(prev => {
      if (!prev || prev.id === incident.id) return { ...(prev ?? {}), ...incident }
      return prev
    })
  }, [])

  const clearAll = useCallback(() => {
    setIncidents([])
    setCurrentIncident(null)
  }, [])

  return {
    incidents,
    currentIncident,
    isLoading,
    fetchIncidents,
    fetchIncident,
    addOrUpdate,
    clearAll,
  }
}
