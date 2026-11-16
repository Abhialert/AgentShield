import React from 'react'
import { NavLink } from 'react-router-dom'

const links = [
  { to: '/dashboard',  label: 'Dashboard',      icon: '📊' },
  { to: '/demo',       label: 'Demo Center',     icon: '🎯', highlight: true },
  { to: '/attack-lab', label: 'Attack Lab',      icon: '⚔️', highlight: true },
  { to: '/chat',       label: 'Agent Chat',      icon: '💬', livebuild: true },
  { to: '/agents',     label: 'Agents',          icon: '🤖' },
  { to: '/approvals',  label: 'Approval Center', icon: '✅', badge: true },
  { to: '/audit',      label: 'Audit Logs',      icon: '📋' },
]

export default function Sidebar({ pendingCount = 0 }) {
  return (
    <aside className="fixed left-0 top-0 h-full w-56 bg-gray-900 border-r border-gray-800 flex flex-col z-40">
      {/* Logo */}
      <div className="px-5 py-5 border-b border-gray-800">
        <div className="flex items-center gap-2">
          <span className="text-2xl">🛡</span>
          <div>
            <div className="text-cyan-400 font-bold text-lg leading-tight">AgentShield</div>
            <div className="text-gray-500 text-xs">AI Security Firewall</div>
          </div>
        </div>
      </div>

      {/* Nav */}
      <nav className="flex-1 px-3 py-4 space-y-1 overflow-y-auto">
        {links.map(link => (
          <NavLink
            key={link.to}
            to={link.to}
            className={({ isActive }) =>
              `flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium transition-colors ${
                isActive
                  ? 'bg-cyan-900/40 text-cyan-300 border border-cyan-800'
                  : link.highlight
                  ? 'text-orange-300 hover:bg-orange-900/20 border border-dashed border-orange-800/50'
                  : link.livebuild
                  ? 'text-amber-400 hover:bg-amber-900/20 border border-dashed border-amber-800/50'
                  : 'text-gray-400 hover:bg-gray-800 hover:text-gray-200'
              }`
            }
          >
            <span className="text-base">{link.icon}</span>
            <span className="flex-1">{link.label}</span>
            {link.badge && pendingCount > 0 && (
              <span className="bg-amber-500 text-black text-xs font-bold w-5 h-5 rounded-full flex items-center justify-center">
                {pendingCount > 9 ? '9+' : pendingCount}
              </span>
            )}
          </NavLink>
        ))}
      </nav>

      {/* Footer */}
      <div className="px-4 py-3 border-t border-gray-800 text-xs text-gray-600">
        v1.0.0 · Hackathon 2024
      </div>
    </aside>
  )
}

