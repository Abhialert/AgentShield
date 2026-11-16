import React, { useEffect, useState } from 'react'
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import Sidebar from './components/Sidebar'
import Dashboard from './pages/Dashboard'
import DemoCenter from './pages/DemoCenter'
import Agents from './pages/Agents'
import Approvals from './pages/Approvals'
import AuditLogs from './pages/AuditLogs'
import AgentChat from './pages/AgentChat'
import { ToastProvider } from './ToastContext'
import { getPendingApprovals } from './api'

function AppLayout() {
  const [pendingCount, setPendingCount] = useState(0)

  useEffect(() => {
    const fetchPending = async () => {
      try {
        const res = await getPendingApprovals()
        setPendingCount(res.data?.length || 0)
      } catch {}
    }
    fetchPending()
    const interval = setInterval(fetchPending, 5000)
    return () => clearInterval(interval)
  }, [])

  return (
    <div className="flex min-h-screen">
      <Sidebar pendingCount={pendingCount} />
      <main className="flex-1 ml-56 p-6 overflow-y-auto min-h-screen">
        <Routes>
          <Route path="/"           element={<Navigate to="/dashboard" replace />} />
          <Route path="/dashboard"  element={<Dashboard />} />
          <Route path="/demo"       element={<DemoCenter />} />
          <Route path="/chat"       element={<AgentChat />} />
          <Route path="/agents"     element={<Agents />} />
          <Route path="/approvals"  element={<Approvals />} />
          <Route path="/audit"      element={<AuditLogs />} />
          <Route path="*"           element={<Navigate to="/dashboard" replace />} />
        </Routes>
      </main>
    </div>
  )
}

export default function App() {
  return (
    <BrowserRouter>
      <ToastProvider>
        <AppLayout />
      </ToastProvider>
    </BrowserRouter>
  )
}
