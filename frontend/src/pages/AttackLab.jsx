import React, { useState, useEffect } from 'react'
import { getAttackScenarios, runAttackSuite } from '../api'
import Spinner from '../components/Spinner'

const CATEGORY_COLORS = {
  prompt_injection:   { bg: 'bg-red-900/30',    border: 'border-red-700',    text: 'text-red-300',    dot: 'bg-red-400' },
  permission:         { bg: 'bg-orange-900/30', border: 'border-orange-700', text: 'text-orange-300', dot: 'bg-orange-400' },
  path_traversal:     { bg: 'bg-yellow-900/30', border: 'border-yellow-700', text: 'text-yellow-300', dot: 'bg-yellow-400' },
  rate_abuse:         { bg: 'bg-purple-900/30', border: 'border-purple-700', text: 'text-purple-300', dot: 'bg-purple-400' },
  token_replay:       { bg: 'bg-blue-900/30',   border: 'border-blue-700',   text: 'text-blue-300',   dot: 'bg-blue-400' },
  encoded_injection:  { bg: 'bg-pink-900/30',   border: 'border-pink-700',   text: 'text-pink-300',   dot: 'bg-pink-400' },
}

function categoryStyle(cat) {
  return CATEGORY_COLORS[cat] || { bg: 'bg-gray-800', border: 'border-gray-600', text: 'text-gray-300', dot: 'bg-gray-400' }
}

function InterceptBadge({ intercepted }) {
  return intercepted
    ? <span className="inline-flex items-center gap-1 bg-green-900/40 text-green-300 border border-green-700 text-xs font-bold px-2 py-0.5 rounded-full">✅ INTERCEPTED</span>
    : <span className="inline-flex items-center gap-1 bg-red-900/40 text-red-300 border border-red-700 text-xs font-bold px-2 py-0.5 rounded-full">❌ BYPASSED</span>
}

function ScenarioCard({ scenario }) {
  const style = categoryStyle(scenario.category)
  return (
    <div className={`rounded-lg border ${style.border} ${style.bg} p-4`}>
      <div className="flex items-start justify-between gap-2 mb-2">
        <div>
          <span className={`text-xs font-mono font-bold ${style.text}`}>{scenario.id}</span>
          <h3 className="text-white font-semibold text-sm mt-0.5">{scenario.name}</h3>
        </div>
        <span className={`flex items-center gap-1 text-xs px-2 py-0.5 rounded-full border ${style.border} ${style.text}`}>
          <span className={`w-1.5 h-1.5 rounded-full ${style.dot}`}></span>
          {scenario.category.replace(/_/g, ' ')}
        </span>
      </div>
      <p className="text-gray-400 text-xs">{scenario.description}</p>
    </div>
  )
}

function ResultRow({ result, index }) {
  const intercepted = result.intercepted
  const style = categoryStyle(result.category)
  return (
    <tr className={`border-b border-gray-800 ${intercepted ? '' : 'bg-red-950/20'}`}>
      <td className="px-3 py-2.5 text-xs font-mono text-gray-400">{index + 1}</td>
      <td className="px-3 py-2.5">
        <span className={`text-xs font-mono font-bold ${style.text}`}>{result.id}</span>
      </td>
      <td className="px-3 py-2.5 text-sm text-white">{result.name}</td>
      <td className="px-3 py-2.5">
        <span className={`text-xs px-2 py-0.5 rounded border ${style.border} ${style.text}`}>
          {result.category.replace(/_/g, ' ')}
        </span>
      </td>
      <td className="px-3 py-2.5">
        <span className={`text-xs font-mono font-bold ${result.expected === result.actual ? 'text-green-400' : 'text-red-400'}`}>
          {result.actual}
        </span>
        {result.expected !== result.actual && (
          <span className="text-gray-500 text-xs ml-1">(expected {result.expected})</span>
        )}
      </td>
      <td className="px-3 py-2.5">
        <InterceptBadge intercepted={intercepted} />
      </td>
      <td className="px-3 py-2.5">
        <span className={`text-sm font-bold font-mono ${result.risk_score >= 70 ? 'text-red-400' : result.risk_score >= 40 ? 'text-orange-400' : 'text-green-400'}`}>
          {result.risk_score}
        </span>
      </td>
      <td className="px-3 py-2.5 text-xs text-gray-400 max-w-48 truncate" title={result.reason}>
        {result.reason}
      </td>
    </tr>
  )
}

export default function AttackLab() {
  const [scenarios, setScenarios] = useState([])
  const [results, setResults] = useState(null)
  const [summary, setSummary] = useState(null)
  const [loading, setLoading] = useState(false)
  const [scenariosLoading, setScenariosLoading] = useState(true)
  const [error, setError] = useState(null)

  useEffect(() => {
    getAttackScenarios()
      .then(r => setScenarios(r.data?.scenarios || []))
      .catch(() => setError('Failed to load scenarios'))
      .finally(() => setScenariosLoading(false))
  }, [])

  const runSuite = async () => {
    setLoading(true)
    setError(null)
    setResults(null)
    setSummary(null)
    try {
      const r = await runAttackSuite()
      setResults(r.data?.results || [])
      setSummary(r.data?.summary || null)
    } catch (e) {
      setError('Attack suite failed: ' + (e?.response?.data?.detail || e.message))
    } finally {
      setLoading(false)
    }
  }

  const interceptRate = summary
    ? Math.round((summary.intercepted / summary.total) * 100)
    : null

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-start justify-between">
        <div>
          <h1 className="text-2xl font-bold text-white flex items-center gap-2">
            ⚔️ Attack Lab
          </h1>
          <p className="text-gray-400 text-sm mt-1">
            Adversarial test suite — verifies AgentShield intercepts real attacks before execution
          </p>
        </div>
        <button
          onClick={runSuite}
          disabled={loading}
          className="flex items-center gap-2 bg-red-700 hover:bg-red-600 disabled:bg-gray-700 text-white font-bold px-5 py-2.5 rounded-lg text-sm transition-colors"
        >
          {loading ? <><Spinner /> Running…</> : '🚀 Run Attack Suite'}
        </button>
      </div>

      {/* Summary bar */}
      {summary && (
        <div className="bg-gray-900 border border-gray-700 rounded-xl p-5">
          <div className="flex items-center justify-between mb-3">
            <h2 className="text-white font-semibold">Suite Results</h2>
            <span className={`text-2xl font-bold font-mono ${interceptRate === 100 ? 'text-green-400' : interceptRate >= 75 ? 'text-yellow-400' : 'text-red-400'}`}>
              {interceptRate}% intercepted
            </span>
          </div>
          <div className="w-full bg-gray-800 rounded-full h-3 overflow-hidden">
            <div
              className={`h-3 rounded-full transition-all duration-700 ${interceptRate === 100 ? 'bg-green-500' : interceptRate >= 75 ? 'bg-yellow-500' : 'bg-red-500'}`}
              style={{ width: `${interceptRate}%` }}
            />
          </div>
          <div className="flex gap-6 mt-3 text-sm">
            <span className="text-gray-400">Total: <span className="text-white font-bold">{summary.total}</span></span>
            <span className="text-green-400">Intercepted: <span className="font-bold">{summary.intercepted}</span></span>
            <span className="text-red-400">Bypassed: <span className="font-bold">{summary.total - summary.intercepted}</span></span>
            <span className="text-gray-400">Avg Risk: <span className="text-orange-400 font-bold">{summary.avg_risk_score?.toFixed(1)}</span></span>
          </div>
        </div>
      )}

      {/* Error */}
      {error && (
        <div className="bg-red-900/20 border border-red-700 text-red-300 rounded-lg px-4 py-3 text-sm">{error}</div>
      )}

      {/* Results table */}
      {results && results.length > 0 && (
        <div className="bg-gray-900 border border-gray-700 rounded-xl overflow-hidden">
          <div className="px-5 py-3 border-b border-gray-700">
            <h2 className="text-white font-semibold text-sm">Attack Results</h2>
          </div>
          <div className="overflow-x-auto">
            <table className="w-full text-left">
              <thead>
                <tr className="border-b border-gray-800 text-gray-500 text-xs uppercase tracking-wider">
                  <th className="px-3 py-2.5">#</th>
                  <th className="px-3 py-2.5">ID</th>
                  <th className="px-3 py-2.5">Attack Name</th>
                  <th className="px-3 py-2.5">Category</th>
                  <th className="px-3 py-2.5">Decision</th>
                  <th className="px-3 py-2.5">Status</th>
                  <th className="px-3 py-2.5">Risk</th>
                  <th className="px-3 py-2.5">Reason</th>
                </tr>
              </thead>
              <tbody>
                {results.map((r, i) => <ResultRow key={r.id} result={r} index={i} />)}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* Scenario cards (pre-run view) */}
      {!results && (
        <div>
          <h2 className="text-gray-300 font-semibold text-sm mb-3">
            {scenariosLoading ? 'Loading scenarios…' : `${scenarios.length} Attack Scenarios Ready`}
          </h2>
          {scenariosLoading ? (
            <div className="flex items-center gap-2 text-gray-400 text-sm"><Spinner /> Loading…</div>
          ) : (
            <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
              {scenarios.map(s => <ScenarioCard key={s.id} scenario={s} />)}
            </div>
          )}
        </div>
      )}
    </div>
  )
}

