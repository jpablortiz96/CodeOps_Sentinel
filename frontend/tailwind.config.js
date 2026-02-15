/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{js,jsx,ts,tsx}'],
  theme: {
    extend: {
      colors: {
        neon: {
          green:  '#00ff88',
          blue:   '#00d4ff',
          red:    '#ff3366',
          yellow: '#ffaa00',
          purple: '#aa66ff',
          cyan:   '#00ffee',
        },
        dark: {
          950: '#06070d',
          900: '#0a0a0f',
          800: '#0d1117',
          700: '#111827',
          600: '#1a2235',
          500: '#1e2d3d',
          400: '#2d3748',
          300: '#4a5568',
        },
      },
      fontFamily: {
        sans: ['Inter', 'system-ui', '-apple-system', 'sans-serif'],
        mono: ['JetBrains Mono', 'Fira Code', 'monospace'],
      },
      boxShadow: {
        'glow-blue':   '0 0 20px rgba(0,212,255,0.4), 0 0 40px rgba(0,212,255,0.15)',
        'glow-green':  '0 0 20px rgba(0,255,136,0.4), 0 0 40px rgba(0,255,136,0.15)',
        'glow-red':    '0 0 20px rgba(255,51,102,0.4), 0 0 40px rgba(255,51,102,0.15)',
        'glow-purple': '0 0 20px rgba(170,102,255,0.4), 0 0 40px rgba(170,102,255,0.15)',
        'glow-yellow': '0 0 20px rgba(255,170,0,0.4), 0 0 40px rgba(255,170,0,0.15)',
        'glass':       '0 8px 32px rgba(0,0,0,0.4), inset 0 1px 0 rgba(255,255,255,0.05)',
        'card':        '0 4px 24px rgba(0,0,0,0.3)',
      },
      animation: {
        'pulse-glow':    'pulse-glow 2s ease-in-out infinite',
        'pulse-slow':    'pulse 3s ease-in-out infinite',
        'scan':          'scan 2.5s linear infinite',
        'fade-in':       'fade-in 0.25s ease-out',
        'slide-up':      'slide-up 0.3s ease-out',
        'slide-right':   'slide-right 0.3s ease-out',
        'float':         'float 3s ease-in-out infinite',
        'shimmer':       'shimmer 2s linear infinite',
        'particle':      'particle 2s ease-in-out infinite',
        'ping-slow':     'ping 2s cubic-bezier(0,0,0.2,1) infinite',
        'arrow-travel':  'arrow-travel 0.8s ease-in-out forwards',
        'flash-red':     'flash-red 1.5s ease-out forwards',
        'count-up':      'count-up 0.6s ease-out forwards',
        'resolve-flash': 'resolve-flash 2s ease-out forwards',
      },
      keyframes: {
        'pulse-glow': {
          '0%,100%': { boxShadow: '0 0 5px currentColor, 0 0 10px currentColor' },
          '50%':     { boxShadow: '0 0 25px currentColor, 0 0 50px currentColor' },
        },
        scan: {
          '0%':   { transform: 'translateY(-100%)' },
          '100%': { transform: 'translateY(100vh)' },
        },
        'fade-in': {
          from: { opacity: 0 },
          to:   { opacity: 1 },
        },
        'slide-up': {
          from: { opacity: 0, transform: 'translateY(12px)' },
          to:   { opacity: 1, transform: 'translateY(0)' },
        },
        'slide-right': {
          from: { opacity: 0, transform: 'translateX(-16px)' },
          to:   { opacity: 1, transform: 'translateX(0)' },
        },
        float: {
          '0%,100%': { transform: 'translateY(0)' },
          '50%':     { transform: 'translateY(-6px)' },
        },
        shimmer: {
          '0%':   { backgroundPosition: '-200% center' },
          '100%': { backgroundPosition:  '200% center' },
        },
        particle: {
          '0%':   { transform: 'translateX(0) scale(1)',   opacity: 1   },
          '50%':  { opacity: 0.8 },
          '100%': { transform: 'translateX(100%) scale(0)', opacity: 0  },
        },
        'arrow-travel': {
          from: { strokeDashoffset: '100%' },
          to:   { strokeDashoffset: '0%' },
        },
        'flash-red': {
          '0%,20%': { boxShadow: '0 0 0 3px rgba(255,51,102,0.6)', borderColor: 'rgba(255,51,102,0.8)' },
          '100%':   { boxShadow: 'none', borderColor: 'transparent' },
        },
        'resolve-flash': {
          '0%':   { boxShadow: '0 0 0 0 rgba(0,255,136,0.8)' },
          '30%':  { boxShadow: '0 0 40px 20px rgba(0,255,136,0.3)' },
          '100%': { boxShadow: '0 0 0 0 rgba(0,255,136,0)' },
        },
      },
      backdropBlur: {
        xs: '2px',
      },
    },
  },
  plugins: [],
}
