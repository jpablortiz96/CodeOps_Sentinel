import { useEffect, useRef, useCallback, useState } from 'react'

const INITIAL_BACKOFF = 1000   // 1s
const MAX_BACKOFF     = 30000  // 30s
const BACKOFF_MULT    = 1.5

/**
 * useWebSocket — auto-reconnect WebSocket with exponential backoff.
 *
 * @param {string} url        — ws:// or wss:// URL
 * @param {object} handlers   — { onMessage, onOpen, onClose, onError }
 * @param {boolean} enabled   — set false to disconnect
 *
 * Returns { status, send, disconnect, reconnect }
 * status: 'connecting' | 'open' | 'closed' | 'error'
 */
export function useWebSocket(url, handlers = {}, enabled = true) {
  const [status, setStatus]     = useState('closed')
  const wsRef                   = useRef(null)
  const backoffRef               = useRef(INITIAL_BACKOFF)
  const retryTimerRef            = useRef(null)
  const mountedRef               = useRef(true)
  const handlersRef              = useRef(handlers)

  // Keep handlers ref up-to-date without re-triggering effect
  useEffect(() => { handlersRef.current = handlers })

  const connect = useCallback(() => {
    if (!mountedRef.current || !enabled) return
    if (wsRef.current?.readyState === WebSocket.OPEN) return

    setStatus('connecting')
    const ws = new WebSocket(url)
    wsRef.current = ws

    ws.onopen = () => {
      if (!mountedRef.current) return
      backoffRef.current = INITIAL_BACKOFF
      setStatus('open')
      handlersRef.current.onOpen?.()
    }

    ws.onmessage = (evt) => {
      if (!mountedRef.current) return
      try {
        const data = JSON.parse(evt.data)
        handlersRef.current.onMessage?.(data)
      } catch {
        handlersRef.current.onMessage?.({ raw: evt.data })
      }
    }

    ws.onclose = (evt) => {
      if (!mountedRef.current) return
      setStatus('closed')
      handlersRef.current.onClose?.(evt)
      if (enabled) scheduleReconnect()
    }

    ws.onerror = (evt) => {
      if (!mountedRef.current) return
      setStatus('error')
      handlersRef.current.onError?.(evt)
      ws.close()
    }
  }, [url, enabled])

  const scheduleReconnect = useCallback(() => {
    clearTimeout(retryTimerRef.current)
    const delay = backoffRef.current
    backoffRef.current = Math.min(backoffRef.current * BACKOFF_MULT, MAX_BACKOFF)
    retryTimerRef.current = setTimeout(() => {
      if (mountedRef.current && enabled) connect()
    }, delay)
  }, [connect, enabled])

  const send = useCallback((data) => {
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      wsRef.current.send(typeof data === 'string' ? data : JSON.stringify(data))
    }
  }, [])

  const disconnect = useCallback(() => {
    clearTimeout(retryTimerRef.current)
    wsRef.current?.close()
  }, [])

  const reconnect = useCallback(() => {
    disconnect()
    backoffRef.current = INITIAL_BACKOFF
    connect()
  }, [disconnect, connect])

  useEffect(() => {
    mountedRef.current = true
    if (enabled) connect()
    return () => {
      mountedRef.current = false
      clearTimeout(retryTimerRef.current)
      wsRef.current?.close()
    }
  }, [connect, enabled])

  return { status, send, disconnect, reconnect }
}
