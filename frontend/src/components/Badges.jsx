import React from 'react'

export function DecisionBadge({ decision }) {
  if (!decision) return null
  const cls = {
    ALLOW:  'badge-allow',
    BLOCK:  'badge-block',
    REVIEW: 'badge-review',
  }[decision] || 'badge-review'
  return <span className={cls}>{decision}</span>
}

export function StatusBadge({ status }) {
  if (!status) return null
  const cls = {
    active:    'badge-active',
    suspended: 'badge-suspended',
    killed:    'badge-killed',
  }[status] || 'badge-killed'
  return <span className={cls}>{status.toUpperCase()}</span>
}

export function ThreatBadge({ level }) {
  const map = {
    LOW:      { cls: 'bg-green-900 text-green-300 border-green-700',  icon: '🟢' },
    MEDIUM:   { cls: 'bg-amber-900 text-amber-300 border-amber-700',  icon: '🟡' },
    HIGH:     { cls: 'bg-orange-900 text-orange-300 border-orange-700', icon: '🟠' },
    CRITICAL: { cls: 'bg-red-900 text-red-300 border-red-700',        icon: '🔴' },
  }
  const { cls, icon } = map[level] || map.LOW
  return (
    <span className={`inline-flex items-center gap-1 border text-xs font-bold px-2.5 py-1 rounded-full ${cls}`}>
      {icon} {level || 'LOW'}
    </span>
  )
}

