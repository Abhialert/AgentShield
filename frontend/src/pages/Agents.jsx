import React, { useEffect, useState, useRef } from 'react'
import { getAgents, killAgent, reactivateAgent, registerAgent } from '../api'
import { StatusBadge } from '../components/Badges'
import Spinner from '../components/Spinner'
import { useToast } from '../ToastContext'

function RegisterModal({ onClose, onSuccess }) {
  const toast = useToast()
  const [form, setForm] = useState({
    name: '',
    permissions: 'transfer_money,email_read',
    max_amount: 5000,
    approved_recipients: 'electricity_board,water_dept',
  })
  const [loading, setLoading] = useState(false)

  const handleSubmit = async (e) => {
    e.preventDefault()
    setLoading(true)
    try {
      await registerAgent({
        name: form.name,
        permissions: form.permissions.split(',').map(s => s.trim()),
        max_amount: Number(form.max_amount),
        approved_recipients: form.approved_recipients.split(',').map(s => s.trim()),
      })
      toast('Agent registered successfully', 'success')
      onSuccess()
      onClose()
    } catch (err) {
      toast(err?.response?.data?.detail || 'Failed to register agent', 'error')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="fixed inset-0 bg-black/70 flex items-center justify-center z-50 p-4">
      <div className="card w-full max-w-md border-cyan-800">
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-lg font-bold text-white">Register New Agent</h2>
          <button onClick={onClose} className="text-gray-400 hover:text-white text-xl">&times;</button>
        </div>
        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label className="block text-sm text-gray-400 mb-1">Agent Name</label>
            <input
              className="w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-white text-sm focus:border-cyan-600 outline-none"
              value={form.name}
              onChange={e => setForm(f => ({ ...f, name: e.target.value }))}
              placeholder="agent_payment_v2"
              required
            />
          </div>
          <div>
            <label className="block text-sm text-gray-400 mb-1">Permissions (comma-separated)</label>
            <input
              className="w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-white text-sm focus:border-cyan-600 outline-none"
              value={form.permissions}
              onChange={e => setForm(f => ({ ...f, permissions: e.target.value }))}
            />
          </div>
          <div>
            <label className="block text-sm text-gray-400 mb-1">Max Transfer Amount</label>
            <input
              type="number"
              className="w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-white text-sm focus:border-cyan-600 outline-none"
              value={form.max_amount}
              onChange={e => setForm(f => ({ ...f, max_amount: e.target.value }))}
            />
          </div>
          <div>
            <label className="block text-sm text-gray-400 mb-1">Approved Recipients (comma-separated)</label>
            <input
              className="w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-white text-sm focus:border-cyan-600 outline-none"
              value={form.approved_recipients}
              onChange={e => setForm(f => ({ ...f, approved_recipients: e.target.value }))}
            />
          </div>
          <div className="flex gap-3 pt-2">
            <button type="submit" disabled={loading} className="btn-primary flex-1 flex items-center justify-center gap-2">
              {loading ? <Spinner /> : '✅'} Register
            </button>
            <button type="button" onClick={onClose} className="btn-secondary flex-1">Cancel</button>
          </div>
        </form>
      </div>
    </div>
  )
}

export default function Agents() {
  const toast     = useToast()
  const [agents, setAgents]       = useState([])
  const [loading, setLoading]     = useState(true)
  const [showModal, setShowModal] = useState(false)
  const [flashRow, setFlashRow]   = useState(null)
  const [acting, setActing]       = useState({})

  const fetchAgents = async () => {
    try {
      const res = await getAgents()
      setAgents(res.data || [])
    } catch {}
    setLoading(false)
  }

  useEffect(() => { fetchAgents() }, [])

  const handleKill = async (agent) => {
    if (!window.confirm(`⚠️ Kill agent "${agent.name}"? This will block all its ongoing actions.`)) return
    setActing(a => ({ ...a, [agent.id]: 'killing' }))
    setFlashRow(agent.id)
    try {
      await killAgent(agent.id)
      toast(`🔴 Agent "${agent.name}" killed`, 'error')
      await fetchAgents()
    } catch (err) {
      toast(err?.response?.data?.detail || 'Failed to kill agent', 'error')
    } finally {
      setActing(a => ({ ...a, [agent.id]: null }))
      setTimeout(() => setFlashRow(null), 600)
    }
  }

  const handleReactivate = async (agent) => {
    setActing(a => ({ ...a, [agent.id]: 'reactivating' }))
    try {
      await reactivateAgent(agent.id)
      toast(`✅ Agent "${agent.name}" reactivated`, 'success')
      await fetchAgents()
    } catch (err) {
      toast(err?.response?.data?.detail || 'Failed to reactivate', 'error')
    } finally {
      setActing(a => ({ ...a, [agent.id]: null }))
    }
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-white">🤖 Agents</h1>
          <p className="text-gray-400 text-sm mt-1">Manage registered AI agents and their permissions</p>
        </div>
        <button onClick={() => setShowModal(true)} className="btn-primary">
          + Register New Agent
        </button>
      </div>

      {showModal && (
        <RegisterModal onClose={() => setShowModal(false)} onSuccess={fetchAgents} />
      )}

      <div className="card overflow-auto">
        {loading ? (
          <div className="flex justify-center py-12"><Spinner size="lg" /></div>
        ) : agents.length === 0 ? (
          <div className="text-center text-gray-500 py-12">No agents registered.</div>
        ) : (
          <table className="w-full text-sm">
            <thead>
              <tr className="text-gray-400 border-b border-gray-800">
                <th className="text-left pb-3 pr-4">Agent</th>
                <th className="text-left pb-3 pr-4">Status</th>
                <th className="text-left pb-3 pr-4">Allowed Actions</th>
                <th className="text-left pb-3 pr-4">Created At</th>
                <th className="text-left pb-3">Controls</th>
              </tr>
            </thead>
            <tbody>
              {agents.map(agent => (
                <tr
                  key={agent.id}
                  className={`border-b border-gray-800 last:border-0 transition-colors ${
                    flashRow === agent.id ? 'kill-flash' : ''
                  }`}
                >
                  <td className="py-3 pr-4">
                    <div className="font-medium text-white">{agent.name}</div>
                    <div className="text-gray-500 text-xs">#{agent.id}</div>
                  </td>
                  <td className="py-3 pr-4">
                    <StatusBadge status={agent.status} />
                  </td>
                  <td className="py-3 pr-4">
                    <div className="flex flex-wrap gap-1 max-w-xs">
                      {(agent.permissions || []).map(p => (
                        <span key={p} className="bg-gray-800 text-gray-300 text-xs px-2 py-0.5 rounded">
                          {p}
                        </span>
                      ))}
                    </div>
                  </td>
                  <td className="py-3 pr-4 text-gray-400 text-xs">
                    {agent.created_at ? new Date(agent.created_at).toLocaleString() : '—'}
                  </td>
                  <td className="py-3">
                    <div className="flex gap-2">
                      {agent.status !== 'killed' && agent.status !== 'suspended' && (
                        <button
                          onClick={() => handleKill(agent)}
                          disabled={acting[agent.id] === 'killing'}
                          className="btn-danger text-xs px-3 py-1.5 flex items-center gap-1"
                        >
                          {acting[agent.id] === 'killing' ? <Spinner /> : '🔴'} Kill
                        </button>
                      )}
                      {agent.status === 'suspended' && (
                        <>
                          <button
                            onClick={() => handleKill(agent)}
                            disabled={acting[agent.id]}
                            className="btn-danger text-xs px-3 py-1.5 flex items-center gap-1"
                          >
                            {acting[agent.id] === 'killing' ? <Spinner /> : '☠️'} Kill
                          </button>
                          <button
                            onClick={() => handleReactivate(agent)}
                            disabled={acting[agent.id]}
                            className="btn-success text-xs px-3 py-1.5 flex items-center gap-1"
                          >
                            {acting[agent.id] === 'reactivating' ? <Spinner /> : '✅'} Reactivate
                          </button>
                        </>
                      )}
                      {agent.status === 'killed' && (
                        <span className="text-gray-600 text-xs italic">No actions available</span>
                      )}
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  )
}

