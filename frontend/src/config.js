/**
 * Runtime environment configuration.
 *
 * In development (Vite dev server):
 *   - API calls go to http://localhost:8000
 *   - WebSocket connects to ws://localhost:8000/ws
 *
 * In production (Azure Static Web Apps):
 *   - API calls use the full backend URL (CORS cross-origin, no nginx proxy)
 *   - WebSocket uses wss:// to the same backend host
 *   - Override at build time via VITE_API_URL / VITE_WS_URL env vars
 */

const isProd = import.meta.env.PROD  // true when built with `vite build`

// Production backend deployed on Azure Container Apps
const PRODUCTION_BACKEND = 'https://codeops-sentinel-api.wonderfulocean-93fc426c.eastus.azurecontainerapps.io'

// ── API base URL ──────────────────────────────────────────────────────────────
export const API_URL = isProd
  ? (import.meta.env.VITE_API_URL ?? 'https://codeops-sentinel-api.wonderfulocean-93fc426c.eastus.azurecontainerapps.io')
  : (import.meta.env.VITE_API_URL ?? 'http://localhost:8000')

// ── WebSocket URL ─────────────────────────────────────────────────────────────
export const WS_URL = isProd
  ? (import.meta.env.VITE_WS_URL ?? 'wss://codeops-sentinel-api.wonderfulocean-93fc426c.eastus.azurecontainerapps.io/ws')
  : (import.meta.env.VITE_WS_URL ?? 'ws://localhost:8000/ws')

// ── App metadata ──────────────────────────────────────────────────────────────
export const APP_VERSION = '2.0.0'
export const APP_ENV     = isProd ? 'production' : 'development'
