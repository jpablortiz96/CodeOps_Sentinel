import { useEffect, useRef, useState } from 'react'

/**
 * Animates a number from its previous value to `value`.
 * Props:
 *   value      — target number
 *   duration   — animation ms (default 600)
 *   decimals   — decimal places (default 0)
 *   prefix     — string prepended (e.g. "$")
 *   suffix     — string appended (e.g. "%")
 *   className  — extra classes on the <span>
 */
export default function AnimatedNumber({
  value,
  duration = 600,
  decimals = 0,
  prefix = '',
  suffix = '',
  className = '',
}) {
  const [display, setDisplay] = useState(value ?? 0)
  const prevRef  = useRef(display)
  const rafRef   = useRef(null)

  useEffect(() => {
    if (value == null) return
    const from  = prevRef.current
    const to    = value
    const start = performance.now()

    const tick = (now) => {
      const elapsed = now - start
      const progress = Math.min(elapsed / duration, 1)
      // ease-out cubic
      const ease = 1 - Math.pow(1 - progress, 3)
      setDisplay(from + (to - from) * ease)
      if (progress < 1) {
        rafRef.current = requestAnimationFrame(tick)
      } else {
        prevRef.current = to
        setDisplay(to)
      }
    }
    rafRef.current = requestAnimationFrame(tick)
    return () => cancelAnimationFrame(rafRef.current)
  }, [value, duration])

  const formatted = typeof display === 'number'
    ? display.toFixed(decimals)
    : display

  return (
    <span className={`tabular-nums ${className}`}>
      {prefix}{formatted}{suffix}
    </span>
  )
}
