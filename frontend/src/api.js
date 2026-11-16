import axios from 'axios'

const API_BASE = 'http://localhost:8000'

const api = axios.create({
  baseURL: API_BASE,
  timeout: 15000,
  headers: { 'Content-Type': 'application/json' },
})

// ─── Dashboard ───────────────────────────────────────────────────────────────
export const getDashboardStats = () => api.get('/api/dashboard/stats')

// ─── Agents ──────────────────────────────────────────────────────────────────
export const getAgents       = ()       => api.get('/api/agents')
export const registerAgent   = (data)   => api.post('/api/agents', data)
export const killAgent       = (id)     => api.post(`/api/agents/${id}/kill`)
export const reactivateAgent = (id)     => api.post(`/api/agents/${id}/reactivate`)

// ─── Actions ─────────────────────────────────────────────────────────────────
export const getActions      = ()       => api.get('/api/actions')
export const authorizeAction = (data)   => api.post('/api/actions/authorize', data)

// ─── Approvals ───────────────────────────────────────────────────────────────
export const getPendingApprovals   = ()          => api.get('/api/approvals/pending')
export const getCompletedApprovals = ()          => api.get('/api/approvals/completed')
export const approveAction         = (action_id) => api.post(`/api/approvals/${action_id}/approve`)
export const rejectAction          = (action_id) => api.post(`/api/approvals/${action_id}/reject`)

// ─── Audit ────────────────────────────────────────────────────────────────────
export const getAuditLogs = (params) => api.get('/api/audit', { params })

// ─── Demo ────────────────────────────────────────────────────────────────────
export const runScenario = (scenario) =>
  api.post('/api/demo/run-scenario', { scenario })
export const resetDemo = () => api.get('/api/demo/reset')

// ── Chat (AI Agent — Live Build) ───────────────────────────────────────────────
export const chatWithAgent = (message, agent_name) =>
  api.post('/api/chat', { message, agent_name })

export default api

