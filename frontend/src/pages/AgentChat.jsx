import React, { useState, useRef, useEffect } from 'react'
import Spinner from '../components/Spinner'
import { DecisionBadge } from '../components/Badges'
import api from '../api'

/**
 * AgentChat — Live AI Agent Interface
 * ⚡ LIVE BUILD PAGE (Nov 21, 12:00–05:45 PM)
 *
 * This page connects to /api/chat and streams real-time LLM responses
 * through the AgentShield security gateway. The backend ai_agent.py
 * will be completed during the hackathon sprint.
 */

const AGENT_OPTIONS = [
  { id: 'agent_payment',  label: '💳 Payment Agent',  desc: 'Can transfer money (limit ₹5,000)' },
  { id: 'agent_email',    label: '📧 Email Agent',    desc: 'Can read/delete emails, access files' },
  { id: 'agent_calendar', label: '📅 Calendar Agent', desc: 'Can create/read calendar events' },
]

const SAMPLE_PROMPTS = [
  'Pay my electricity bill of ₹2,500',
  'Transfer ₹10,000 to unknown_account',       // should be BLOCKED
  'Read my last 5 emails',
  'Delete all emails from spam@evil.com',       // should require REVIEW
  'Schedule a team meeting tomorrow at 3pm',
  // ⚡ LIVE BUILD: add more prompts that demonstrate prompt injection
]

function Message({ msg }) {
  const isUser = msg.role === 'user'
  return (
    <div className={`flex gap-3 ${isUser ? 'flex-row-reverse' : ''}`}>
      <div className={`w-8 h-8 rounded-full flex items-center justify-center text-sm flex-shrink-0 ${
        isUser ? 'bg-cyan-700 text-white' : 'bg-gray-700 text-gray-200'
      }`}>
        {isUser ? '👤' : '🤖'}
      </div>
      <div className={`max-w-lg rounded-xl px-4 py-3 text-sm ${
        isUser ? 'bg-cyan-900/40 text-cyan-100 rounded-tr-none' : 'bg-gray-800 text-gray-200 rounded-tl-none'
      }`}>
        <p>{msg.content}</p>
        {msg.decision && (
          <div className="mt-2 flex items-center gap-2 border-t border-gray-700 pt-2">
            <DecisionBadge decision={msg.decision} />
            {msg.risk_score !== undefined && (
              <span className="text-xs text-gray-400">Risk: {msg.risk_score}/100</span>
            )}
          </div>
        )}
      </div>
    </div>
  )
}

export default function AgentChat() {
  const [messages, setMessages]       = useState([])
  const [input, setInput]             = useState('')
  const [loading, setLoading]         = useState(false)
  const [selectedAgent, setAgent]     = useState('agent_payment')
  const bottomRef                     = useRef(null)

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  const sendMessage = async (text) => {
    const userMsg = text || input.trim()
    if (!userMsg || loading) return
    setInput('')

    setMessages(prev => [...prev, { role: 'user', content: userMsg }])
    setLoading(true)

    try {
      // ⚡ LIVE BUILD: switch to streaming endpoint for real-time output
      const res = await api.post('/api/chat', {
        message: userMsg,
        agent_name: selectedAgent,
      })
      const { response, decision, risk_score, action_id } = res.data
      setMessages(prev => [...prev, {
        role: 'assistant',
        content: response,
        decision,
        risk_score,
        action_id,
      }])
    } catch (err) {
      setMessages(prev => [...prev, {
        role: 'assistant',
        content: `Error: ${err?.response?.data?.detail || 'Could not reach AgentShield backend.'}`,
      }])
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="flex flex-col h-[calc(100vh-5rem)]">
      {/* Header */}
      <div className="card mb-4 flex items-center justify-between">
        <div>
          <h1 className="text-xl font-bold text-white flex items-center gap-2">
            🤖 Agent Chat
            <span className="text-xs bg-amber-900/40 text-amber-400 border border-amber-700 rounded px-2 py-0.5 font-normal">
              ⚡ Live Build — Nov 21
            </span>
          </h1>
          <p className="text-gray-400 text-sm mt-0.5">
            Chat with an AI agent — every action is intercepted by AgentShield
          </p>
        </div>
        {/* Agent selector */}
        <select
          value={selectedAgent}
          onChange={e => setAgent(e.target.value)}
          className="bg-gray-800 border border-gray-700 text-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:border-cyan-600"
        >
          {AGENT_OPTIONS.map(o => (
            <option key={o.id} value={o.id}>{o.label}</option>
          ))}
        </select>
      </div>

      {/* Agent info */}
      <div className="bg-gray-900 border border-gray-800 rounded-lg px-4 py-2 mb-4 text-sm text-gray-400 flex items-center gap-2">
        <span>Active agent:</span>
        <span className="text-cyan-400 font-medium">
          {AGENT_OPTIONS.find(o => o.id === selectedAgent)?.label}
        </span>
        <span>—</span>
        <span>{AGENT_OPTIONS.find(o => o.id === selectedAgent)?.desc}</span>
      </div>

      {/* Chat messages */}
      <div className="flex-1 overflow-y-auto space-y-4 mb-4 pr-1">
        {messages.length === 0 && (
          <div className="text-center py-12">
            <div className="text-5xl mb-4">🛡</div>
            <div className="text-gray-400 text-sm mb-6">
              Send a message to the AI agent. AgentShield will intercept every action it tries to take.
            </div>
            <div className="grid grid-cols-2 gap-2 max-w-lg mx-auto">
              {SAMPLE_PROMPTS.map((p, i) => (
                <button
                  key={i}
                  onClick={() => sendMessage(p)}
                  className="text-left text-xs bg-gray-800 hover:bg-gray-700 border border-gray-700 rounded-lg px-3 py-2 text-gray-300 transition-colors"
                >
                  {p}
                </button>
              ))}
            </div>
          </div>
        )}
        {messages.map((msg, i) => (
          <Message key={i} msg={msg} />
        ))}
        {loading && (
          <div className="flex gap-3">
            <div className="w-8 h-8 rounded-full bg-gray-700 flex items-center justify-center text-sm flex-shrink-0">🤖</div>
            <div className="bg-gray-800 rounded-xl rounded-tl-none px-4 py-3 flex items-center gap-2">
              <Spinner size="sm" />
              <span className="text-gray-400 text-sm">AgentShield evaluating...</span>
            </div>
          </div>
        )}
        <div ref={bottomRef} />
      </div>

      {/* Input */}
      <div className="flex gap-2">
        <input
          type="text"
          value={input}
          onChange={e => setInput(e.target.value)}
          onKeyDown={e => e.key === 'Enter' && !e.shiftKey && sendMessage()}
          placeholder="Tell the AI agent what to do..."
          className="flex-1 bg-gray-800 border border-gray-700 text-gray-200 rounded-xl px-4 py-3 text-sm focus:outline-none focus:border-cyan-600 placeholder-gray-500"
          disabled={loading}
        />
        <button
          onClick={() => sendMessage()}
          disabled={loading || !input.trim()}
          className="bg-cyan-700 hover:bg-cyan-600 disabled:opacity-40 disabled:cursor-not-allowed text-white rounded-xl px-5 py-3 text-sm font-semibold transition-colors"
        >
          Send
        </button>
      </div>
    </div>
  )
}
