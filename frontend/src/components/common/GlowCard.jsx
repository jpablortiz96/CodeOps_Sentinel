/**
 * GlowCard — glassmorphism base card with optional glow border.
 *
 * Props:
 *   color     — 'blue' | 'green' | 'red' | 'yellow' | 'purple' (default none)
 *   hover     — boolean: enable glow-on-hover
 *   glass     — boolean: use backdrop-blur glass style (default true)
 *   padding   — tailwind padding class (default 'p-4')
 *   className
 *   children
 */
export default function GlowCard({
  color,
  hover = false,
  glass = true,
  padding = 'p-4',
  className = '',
  children,
  ...props
}) {
  const glowMap = {
    blue:   'border-neon-blue/30 shadow-glow-blue',
    green:  'border-neon-green/30 shadow-glow-green',
    red:    'border-neon-red/30 shadow-glow-red',
    yellow: 'border-yellow-400/30 shadow-glow-yellow',
    purple: 'border-purple-400/30 shadow-glow-purple',
  }

  const hoverMap = {
    blue:   'hover:border-neon-blue/50 hover:shadow-glow-blue',
    green:  'hover:border-neon-green/50 hover:shadow-glow-green',
    red:    'hover:border-neon-red/50 hover:shadow-glow-red',
    yellow: 'hover:border-yellow-400/50 hover:shadow-glow-yellow',
    purple: 'hover:border-purple-400/50 hover:shadow-glow-purple',
  }

  const baseStyle = glass
    ? 'card-glass'
    : 'bg-dark-700 border border-dark-400/60 rounded-2xl shadow-card'

  const colorStyle = color ? glowMap[color] ?? '' : 'border-dark-400/40'
  const hoverStyle = hover && color ? `transition-all duration-300 ${hoverMap[color] ?? ''}` : ''

  return (
    <div
      className={`${baseStyle} ${colorStyle} ${hoverStyle} ${padding} ${className}`}
      {...props}
    >
      {children}
    </div>
  )
}
