import React, { useEffect, useState, useCallback } from 'react'
import { getAuditLogs, getAgents } from '../api'
import { DecisionBadge } from '../components/Badges'
import Spinner from '../components/Spinner'

function rowBg(decision) {
  if (decision === 'BLOCK')  return 'bg-red-900/10 hover:bg-red-900/20'
  if (decision === 'ALLOW')  return 'bg-green-900/10 hover:bg-green-900/20'
  if (decision === 'REVIEW') return 'bg-amber-900/10 hover:bg-amber-900/20'
  return 'hover:bg-gray-800/50'
}

export default function AuditLogs() {
  const [logs,      setLogs]      = useState([])
  const [agents,    setAgents]    = useState([])
  const [loading,   setLoading]   = useState(true)
  const [filterAgent,    setFilterAgent]    = useState('')
  const [filterDecision, setFilterDecision] = useState('')
  const [expanded,  setExpanded]  = useState(null)

  const fetchLogs = useCallback(async () => {
    try {
      const params = {}
      if (filterAgent)    params.agent_id  = filterAgent
      if (filterDecision) params.decision  = filterDecision
      const res = await getAuditLogs(params)
      setLogs(res.data || [])
    } catch {}
    setLoading(false)
  }, [filterAgent, filterDecision])

  useEffect(() => {
    getAgents().then(r => setAgents(r.data || [])).catch(() => {})
  }, [])

  useEffect(() => {
    fetchLogs()
    const interval = setInterval(fetchLogs, 5000)
    return () => clearInterval(interval)
  }, [fetchLogs])

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-white">📋 Audit Logs</h1>
          <p className="text-gray-400 text-sm mt-1">Complete audit trail of all agent actions. Auto-refreshes every 5s.</p>
        </div>
        <div className="flex gap-3 flex-wrap">
          {/* Agent filter */}
          <select
            value={filterAgent}
            onChange={e => setFilterAgent(e.target.value)}
            className="bg-gray-800 border border-gray-700 text-sm text-gray-200 rounded-lg px-3 py-2 focus:border-cyan-600 outline-none"
          >
            <option value="">All Agents</option>
            {agents.map(a => (
              <option key={a.id} value={a.id}>{a.name}</option>
            ))}
          </select>
          {/* Decision filter */}
          <select
            value={filterDecision}
            onChange={e => setFilterDecision(e.target.value)}
            className="bg-gray-800 border border-gray-700 text-sm text-gray-200 rounded-lg px-3 py-2 focus:border-cyan-600 outline-none"
          >
            <option value="">All Decisions</option>
            <option value="ALLOW">ALLOW</option>
            <option value="BLOCK">BLOCK</option>
            <option value="REVIEW">REVIEW</option>
          </select>
          <button onClick={fetchLogs} className="btn-secondary text-sm">↻ Refresh</button>
        </div>
      </div>

      <div className="card overflow-auto p-0">
        {loading ? (
          <div className="flex justify-center py-16"><Spinner size="lg" /></div>
        ) : logs.length === 0 ? (
          <div className="text-center text-gray-500 py-12 p-6">
            No audit logs found. Run a demo to generate activity.
          </div>
        ) : (
          <table className="w-full text-sm">
            <thead className="border-b border-gray-800">
              <tr className="text-gray-400">
                <th className="text-left p-4 pr-4">Timestamp</th>
                <th className="text-left p-4 pr-4">Agent</th>
                <th className="text-left p-4 pr-4">Event Type</th>
                <th className="text-left p-4 pr-4">Decision</th>
                <th className="text-left p-4">Details</th>
              </tr>
            </thead>
            <tbody>
              {logs.map((log, i) => (
                <React.Fragment key={log.id || i}>
                  <tr
                    className={`border-b border-gray-800/50 cursor-pointer transition-colors ${rowBg(log.decision)}`}
                    onClick={() => setExpanded(expanded === i ? null : i)}
                  >
                    <td className="p-4 pr-4 text-gray-500 text-xs whitespace-nowrap">
                      {log.created_at ? new Date(log.created_at).toLocaleString() : '—'}
                    </td>
                    <td className="p-4 pr-4 text-cyan-400 font-medium">
                      {log.agent_name || `Agent #${log.agent_id}`}
                    </td>
                    <td className="p-4 pr-4 text-gray-300">
                      {log.event_type || log.action_type || '—'}
                    </td>
                    <td className="p-4 pr-4">
                      {log.decision ? <DecisionBadge decision={log.decision} /> : (
                        <span className="text-gray-500 text-xs">{log.event_type || '—'}</span>
                      )}
                    </td>
                    <td className="p-4 text-gray-400 text-xs max-w-xs truncate">
                      {log.reason || log.details || '—'}
                    </td>
                  </tr>
                  {expanded === i && (
                    <tr className="bg-gray-800/40">
                      <td colSpan={5} className="px-6 py-3">
                        <div className="text-xs text-gray-300 font-mono whitespace-pre-wrap">
                          {JSON.stringify(log.details_json || log, null, 2)}
                        </div>
                      </td>
                    </tr>
                  )}
                </React.Fragment>
              ))}
            </tbody>
          </table>
        )}
      </div>

      <div className="text-xs text-gray-600 text-right">
        Showing {logs.length} entries · Click a row to expand details
      </div>
    </div>
  )
}

