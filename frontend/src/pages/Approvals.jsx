import React, { useEffect, useState, useCallback } from 'react'
import { getPendingApprovals, getCompletedApprovals, approveAction, rejectAction } from '../api'
import Spinner from '../components/Spinner'
import { DecisionBadge } from '../components/Badges'
import { useToast } from '../ToastContext'

function RiskPill({ score }) {
  const color = score >= 70 ? 'text-red-400 bg-red-900/30 border-red-700'
              : score >= 30 ? 'text-amber-400 bg-amber-900/30 border-amber-700'
              :               'text-green-400 bg-green-900/30 border-green-700'
  return (
    <span className={`border text-xs font-bold px-2 py-0.5 rounded-full ${color}`}>
      Risk {score}/100
    </span>
  )
}

function PendingCard({ approval, onApprove, onReject, acting }) {
  const params = approval.params || {}
  return (
    <div className="card border-amber-800 bg-amber-900/5">
      <div className="flex flex-wrap items-start justify-between gap-3 mb-4">
        <div>
          <div className="text-white font-semibold">{approval.agent_name || `Agent #${approval.agent_id}`}</div>
          <div className="text-gray-400 text-sm mt-0.5">{approval.action_type}</div>
        </div>
        <div className="flex items-center gap-2">
          <RiskPill score={approval.risk_score} />
          <span className="badge-review">PENDING</span>
        </div>
      </div>

      <div className="grid grid-cols-2 gap-3 mb-4 text-sm">
        {params.amount !== undefined && (
          <div>
            <div className="text-gray-500 text-xs">Amount</div>
            <div className="text-white font-semibold">₹{params.amount?.toLocaleString()}</div>
          </div>
        )}
        {params.recipient && (
          <div>
            <div className="text-gray-500 text-xs">Recipient</div>
            <div className="text-white">{params.recipient}</div>
          </div>
        )}
        {approval.reason && (
          <div className="col-span-2">
            <div className="text-gray-500 text-xs">Reason for Review</div>
            <div className="text-amber-300 text-xs mt-0.5">{approval.reason}</div>
          </div>
        )}
      </div>

      <div className="flex gap-3">
        <button
          onClick={() => onApprove(approval.action_id)}
          disabled={acting}
          className="btn-success flex-1 flex items-center justify-center gap-2 text-sm"
        >
          {acting === 'approving' ? <Spinner /> : '✅'} Approve
        </button>
        <button
          onClick={() => onReject(approval.action_id)}
          disabled={acting}
          className="btn-danger flex-1 flex items-center justify-center gap-2 text-sm"
        >
          {acting === 'rejecting' ? <Spinner /> : '❌'} Reject
        </button>
      </div>
    </div>
  )
}

export default function Approvals() {
  const toast     = useToast()
  const [pending,    setPending]    = useState([])
  const [completed,  setCompleted]  = useState([])
  const [loading,    setLoading]    = useState(true)
  const [acting,     setActing]     = useState({})

  const fetchData = useCallback(async () => {
    try {
      const [pRes, cRes] = await Promise.all([
        getPendingApprovals(),
        getCompletedApprovals(),
      ])
      setPending(pRes.data || [])
      setCompleted(cRes.data || [])
    } catch {}
    setLoading(false)
  }, [])

  useEffect(() => {
    fetchData()
    const interval = setInterval(fetchData, 3000)
    return () => clearInterval(interval)
  }, [fetchData])

  const handleApprove = async (action_id) => {
    setActing(a => ({ ...a, [action_id]: 'approving' }))
    try {
      await approveAction(action_id)
      toast('✅ Action approved', 'success')
      await fetchData()
    } catch (err) {
      toast(err?.response?.data?.detail || 'Approval failed', 'error')
    } finally {
      setActing(a => ({ ...a, [action_id]: null }))
    }
  }

  const handleReject = async (action_id) => {
    setActing(a => ({ ...a, [action_id]: 'rejecting' }))
    try {
      await rejectAction(action_id)
      toast('❌ Action rejected', 'warning')
      await fetchData()
    } catch (err) {
      toast(err?.response?.data?.detail || 'Rejection failed', 'error')
    } finally {
      setActing(a => ({ ...a, [action_id]: null }))
    }
  }

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-white flex items-center gap-2">
          ✅ Approval Center
          {pending.length > 0 && (
            <span className="bg-amber-500 text-black text-sm font-bold px-2 py-0.5 rounded-full">
              {pending.length}
            </span>
          )}
        </h1>
        <p className="text-gray-400 text-sm mt-1">
          Human-in-the-loop review for medium-risk agent actions. Auto-refreshes every 3s.
        </p>
      </div>

      {loading ? (
        <div className="flex justify-center py-16"><Spinner size="lg" /></div>
      ) : (
        <>
          {/* Pending */}
          <div>
            <h2 className="text-lg font-semibold text-amber-400 mb-4">
              ⏳ Pending Approvals ({pending.length})
            </h2>
            {pending.length === 0 ? (
              <div className="card text-center text-gray-500 py-8">
                No pending approvals. All caught up! 🎉
              </div>
            ) : (
              <div className="grid grid-cols-1 lg:grid-cols-2 xl:grid-cols-3 gap-4">
                {pending.map(a => (
                  <PendingCard
                    key={a.action_id}
                    approval={a}
                    onApprove={handleApprove}
                    onReject={handleReject}
                    acting={acting[a.action_id]}
                  />
                ))}
              </div>
            )}
          </div>

          {/* Completed */}
          {completed.length > 0 && (
            <div>
              <h2 className="text-lg font-semibold text-gray-400 mb-4">
                📋 Completed ({completed.length})
              </h2>
              <div className="card overflow-auto">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="text-gray-400 border-b border-gray-800">
                      <th className="text-left pb-3 pr-4">Agent</th>
                      <th className="text-left pb-3 pr-4">Action</th>
                      <th className="text-left pb-3 pr-4">Decision</th>
                      <th className="text-left pb-3 pr-4">Risk</th>
                      <th className="text-left pb-3">Resolved At</th>
                    </tr>
                  </thead>
                  <tbody>
                    {completed.map(a => (
                      <tr key={a.action_id} className="border-b border-gray-800 last:border-0">
                        <td className="py-2.5 pr-4 text-gray-300">{a.agent_name || `#${a.agent_id}`}</td>
                        <td className="py-2.5 pr-4 text-gray-400">{a.action_type}</td>
                        <td className="py-2.5 pr-4">
                          <DecisionBadge decision={a.approval_status === 'approved' ? 'ALLOW' : 'BLOCK'} />
                        </td>
                        <td className="py-2.5 pr-4">
                          <RiskPill score={a.risk_score} />
                        </td>
                        <td className="py-2.5 text-gray-500 text-xs">
                          {a.resolved_at ? new Date(a.resolved_at).toLocaleString() : '—'}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}
        </>
      )}
    </div>
  )
}

