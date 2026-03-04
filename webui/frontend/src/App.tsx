import { BrowserRouter, Routes, Route, NavLink } from 'react-router-dom'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import ConfigBuilder from './pages/ConfigBuilder'
import JobMonitor from './pages/JobMonitor'

const queryClient = new QueryClient()

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
    </div>
  )
}

function DataViewer() {
  return <div><h1 className="text-2xl font-bold">Data Viewer</h1><p className="text-gray-400 mt-2">Coming soon...</p></div>
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
