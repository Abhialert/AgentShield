import React, { useEffect, useRef, useState, useCallback } from 'react'
import { getDashboardStats, getActions } from '../api'
import { DecisionBadge, ThreatBadge, StatusBadge } from '../components/Badges'
import AnimatedNumber from '../components/AnimatedNumber'
import Spinner from '../components/Spinner'
import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer
} from 'recharts'

function StatCard({ label, value, color = 'text-white', icon }) {
  return (
    <div className="card flex flex-col gap-2">
      <div className="text-gray-400 text-sm flex items-center gap-2">
        <span>{icon}</span>{label}
      </div>
      <div className={`text-3xl font-bold ${color}`}>
        <AnimatedNumber value={value || 0} />
      </div>
    </div>
  )
}

export default function Dashboard() {
  const [stats, setStats]       = useState(null)
  const [actions, setActions]   = useState([])
  const [loading, setLoading]   = useState(true)
  const wsRef                   = useRef(null)
  const reconnectRef            = useRef(null)

  const fetchData = useCallback(async () => {
    try {
      const [sRes, aRes] = await Promise.all([getDashboardStats(), getActions()])
      setStats(sRes.data)
      setActions(aRes.data?.slice(0, 10) || [])
    } catch {
      // silent — backend may not be ready
    } finally {
      setLoading(false)
    }
  }, [])

  // WebSocket
  const connectWS = useCallback(() => {
    if (wsRef.current?.readyState === WebSocket.OPEN) return
    try {
      const ws = new WebSocket('ws://localhost:8000/ws/live')
      wsRef.current = ws

      ws.onmessage = (e) => {
        try {
          const event = JSON.parse(e.data)
          if (event.event === 'action') {
            fetchData()
          }
        } catch {}
      }

      ws.onclose = () => {
        reconnectRef.current = setTimeout(connectWS, 3000)
      }
    } catch {}
  }, [fetchData])

  useEffect(() => {
    fetchData()
    connectWS()
    const interval = setInterval(fetchData, 5000)
    return () => {
      clearInterval(interval)
      clearTimeout(reconnectRef.current)
      wsRef.current?.close()
    }
  }, [fetchData, connectWS])

  // Build chart data from actions
  const chartData = (() => {
    const hours = {}
    actions.forEach(a => {
      const h = new Date(a.created_at).getHours()
      const key = `${h}:00`
      if (!hours[key]) hours[key] = { time: key, ALLOW: 0, BLOCK: 0, REVIEW: 0 }
      hours[key][a.decision] = (hours[key][a.decision] || 0) + 1
    })
    return Object.values(hours)
  })()

  const threatColor = {
    LOW:      'border-green-700 bg-green-900/20',
    MEDIUM:   'border-amber-700 bg-amber-900/20',
    HIGH:     'border-orange-700 bg-orange-900/20',
    CRITICAL: 'border-red-700 bg-red-900/20',
  }[stats?.threat_level] || 'border-cyan-800 bg-cyan-900/10'

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className={`card border-2 ${threatColor} flex items-center justify-between`}>
        <div className="flex items-center gap-3">
          <span className="text-4xl">🛡</span>
          <div>
            <h1 className="text-2xl font-bold text-white">AgentShield</h1>
            <p className="text-gray-400 text-sm">AI Agent Security Firewall — Live Monitor</p>
          </div>
        </div>
        <div className="flex items-center gap-4">
          {loading && <Spinner />}
          <ThreatBadge level={stats?.threat_level || 'LOW'} />
        </div>
      </div>

      {/* Stats Row */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        <StatCard label="Total Actions"   value={stats?.total_actions}  icon="⚡" color="text-cyan-400" />
        <StatCard label="Blocked"         value={stats?.blocked}        icon="🚫" color="text-red-400" />
        <StatCard label="Allowed"         value={stats?.allowed}        icon="✅" color="text-green-400" />
        <StatCard label="Pending Review"  value={stats?.review}         icon="⏳" color="text-amber-400" />
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Live Activity Feed */}
        <div className="card lg:col-span-2">
          <h2 className="text-lg font-semibold text-gray-200 mb-4 flex items-center gap-2">
            <span className="w-2 h-2 bg-green-400 rounded-full animate-pulse inline-block"></span>
            Live Activity Feed
          </h2>
          {actions.length === 0 ? (
            <div className="text-gray-500 text-sm text-center py-8">
              No actions yet. Run a demo to see activity.
            </div>
          ) : (
            <div className="space-y-2">
              {actions.map((a, i) => (
                <div key={a.id || i} className="flex items-center gap-3 py-2 border-b border-gray-800 last:border-0">
                  <DecisionBadge decision={a.decision} />
                  <span className="text-gray-300 text-sm flex-1 truncate">
                    <span className="text-cyan-400">{a.agent_name || a.agent_id}</span>
                    {' · '}{a.action_type}
                  </span>
                  <span className="text-gray-500 text-xs">
                    Risk <span className={a.risk_score >= 70 ? 'text-red-400' : a.risk_score >= 30 ? 'text-amber-400' : 'text-green-400'}>
                      {a.risk_score}
                    </span>
                  </span>
                  <span className="text-gray-600 text-xs">
                    {a.created_at ? new Date(a.created_at).toLocaleTimeString() : ''}
                  </span>
                </div>
              ))}
            </div>
          )}
        </div>

        {/* Active Agents */}
        <div className="card">
          <h2 className="text-lg font-semibold text-gray-200 mb-4">Active Agents</h2>
          {!stats?.agents || stats.agents.length === 0 ? (
            <div className="text-gray-500 text-sm">No agents registered.</div>
          ) : (
            <div className="space-y-3">
              {stats.agents.map(agent => (
                <div key={agent.id} className="flex items-center gap-3 py-2 border-b border-gray-800 last:border-0">
                  <span className={`w-2.5 h-2.5 rounded-full flex-shrink-0 ${
                    agent.status === 'active' ? 'bg-green-400' : 'bg-red-500'
                  }`} />
                  <div className="flex-1 min-w-0">
                    <div className="text-sm text-gray-200 truncate">{agent.name}</div>
                    <div className="text-xs text-gray-500">{agent.status}</div>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>

      {/* Bar Chart */}
      {chartData.length > 0 && (
        <div className="card">
          <h2 className="text-lg font-semibold text-gray-200 mb-4">Actions Over Time</h2>
          <ResponsiveContainer width="100%" height={200}>
            <BarChart data={chartData}>
              <CartesianGrid strokeDasharray="3 3" stroke="#1f2937" />
              <XAxis dataKey="time" stroke="#6b7280" tick={{ fontSize: 12 }} />
              <YAxis stroke="#6b7280" tick={{ fontSize: 12 }} />
              <Tooltip
                contentStyle={{ background: '#111827', border: '1px solid #374151', borderRadius: 8 }}
                labelStyle={{ color: '#e5e7eb' }}
              />
              <Bar dataKey="ALLOW"  fill="#16a34a" radius={[3,3,0,0]} />
              <Bar dataKey="BLOCK"  fill="#dc2626" radius={[3,3,0,0]} />
              <Bar dataKey="REVIEW" fill="#d97706" radius={[3,3,0,0]} />
            </BarChart>
          </ResponsiveContainer>
          <div className="flex gap-4 mt-2 text-xs text-gray-400 justify-center">
            <span className="flex items-center gap-1"><span className="w-3 h-3 bg-green-600 rounded"></span> Allow</span>
            <span className="flex items-center gap-1"><span className="w-3 h-3 bg-red-600 rounded"></span> Block</span>
            <span className="flex items-center gap-1"><span className="w-3 h-3 bg-amber-600 rounded"></span> Review</span>
          </div>
        </div>
      )}
    </div>
  )
}

