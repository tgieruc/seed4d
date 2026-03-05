import { BrowserRouter, Routes, Route, NavLink } from 'react-router-dom'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import ConfigBuilder from './pages/ConfigBuilder'
import JobMonitor from './pages/JobMonitor'
import DataViewer from './pages/DataViewer'
import { useToastStore } from './store/toastStore'

const queryClient = new QueryClient()

const TOAST_COLORS = {
  success: 'bg-green-600 border-green-500',
  error: 'bg-red-600 border-red-500',
  info: 'bg-blue-600 border-blue-500',
}

function Toasts() {
  const { toasts, removeToast } = useToastStore()
  if (toasts.length === 0) return null
  return (
    <div className="fixed bottom-4 right-4 z-50 flex flex-col gap-2">
      {toasts.map((t) => (
        <div
          key={t.id}
          className={`${TOAST_COLORS[t.type]} border rounded-lg px-4 py-2.5 text-sm text-white shadow-lg flex items-center gap-3 animate-in slide-in-from-right`}
        >
          <span>{t.message}</span>
          <button onClick={() => removeToast(t.id)} className="text-white/60 hover:text-white">x</button>
        </div>
      ))}
    </div>
  )
}

function Layout({ children }: { children: React.ReactNode }) {
  return (
    <div className="min-h-screen bg-gray-950 text-gray-100">
      <nav className="border-b border-gray-800 px-6 py-3 flex gap-6 items-center">
        <span className="font-bold text-lg tracking-tight">SEED4D</span>
        <NavLink to="/config" className={({ isActive }) =>
          isActive ? 'text-blue-400' : 'text-gray-400 hover:text-gray-200'
        }>Config Builder</NavLink>
        <NavLink to="/jobs" className={({ isActive }) =>
          isActive ? 'text-blue-400' : 'text-gray-400 hover:text-gray-200'
        }>Jobs</NavLink>
        <NavLink to="/viewer" className={({ isActive }) =>
          isActive ? 'text-blue-400' : 'text-gray-400 hover:text-gray-200'
        }>Data Viewer</NavLink>
      </nav>
      <main className="p-6">{children}</main>
      <Toasts />
    </div>
  )
}

export default function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        <Layout>
          <Routes>
            <Route path="/" element={<ConfigBuilder />} />
            <Route path="/config" element={<ConfigBuilder />} />
            <Route path="/jobs" element={<JobMonitor />} />
            <Route path="/viewer" element={<DataViewer />} />
          </Routes>
        </Layout>
      </BrowserRouter>
    </QueryClientProvider>
  )
}
