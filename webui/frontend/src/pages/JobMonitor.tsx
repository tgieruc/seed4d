import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { useState, useEffect, useRef } from 'react'
import { listJobs, cancelJob, rerunJob, connectJobWS } from '../api'
import type { Job } from '../types'

const STATUS_COLORS: Record<Job['status'], string> = {
  queued: 'bg-yellow-500',
  running: 'bg-blue-500 animate-pulse',
  completed: 'bg-green-500',
  failed: 'bg-red-500',
  cancelled: 'bg-gray-500',
}

const STATUS_LABELS: Record<Job['status'], string> = {
  queued: 'Queued',
  running: 'Running',
  completed: 'Completed',
  failed: 'Failed',
  cancelled: 'Cancelled',
}

function formatDuration(job: Job): string {
  const start = job.started_at ? new Date(job.started_at).getTime() : null
  const end = job.completed_at
    ? new Date(job.completed_at).getTime()
    : job.started_at
      ? Date.now()
      : null
  if (!start || !end) return '-'
  const secs = Math.floor((end - start) / 1000)
  if (secs < 60) return `${secs}s`
  const mins = Math.floor(secs / 60)
  const remSecs = secs % 60
  return `${mins}m ${remSecs}s`
}

function formatTime(iso: string): string {
  return new Date(iso).toLocaleString(undefined, {
    month: 'short',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  })
}

function ProgressBar({ job }: { job: Job }) {
  if (!job.progress) return null
  const { step, total_steps, spawn_point, total_spawn_points } = job.progress
  if (total_steps == null || total_spawn_points == null) return null

  const spawnDone = (spawn_point ?? 0) * total_steps
  const stepDone = step ?? 0
  const total = total_spawn_points * total_steps
  const current = spawnDone + stepDone
  const pct = total > 0 ? Math.round((current / total) * 100) : 0

  return (
    <div>
      <div className="flex justify-between text-xs text-gray-400 mb-1">
        <span>
          Spawn {(spawn_point ?? 0) + 1}/{total_spawn_points} &middot; Step{' '}
          {stepDone}/{total_steps}
        </span>
        <span>{pct}%</span>
      </div>
      <div className="w-full bg-gray-700 rounded-full h-2">
        <div
          className="bg-blue-500 h-2 rounded-full transition-all duration-300"
          style={{ width: `${pct}%` }}
        />
      </div>
    </div>
  )
}

function StatusFilter({
  value,
  onChange,
}: {
  value: string
  onChange: (v: string) => void
}) {
  const options = ['all', 'queued', 'running', 'completed', 'failed', 'cancelled']
  return (
    <div className="flex gap-1 mb-3">
      {options.map((opt) => (
        <button
          key={opt}
          onClick={() => onChange(opt)}
          className={`px-2 py-1 text-xs rounded ${
            value === opt
              ? 'bg-blue-600 text-white'
              : 'bg-gray-800 text-gray-400 hover:text-gray-200'
          }`}
        >
          {opt.charAt(0).toUpperCase() + opt.slice(1)}
        </button>
      ))}
    </div>
  )
}

function JobList({
  jobs,
  selectedId,
  onSelect,
}: {
  jobs: Job[]
  selectedId: string | null
  onSelect: (id: string) => void
}) {
  return (
    <table className="w-full text-sm">
      <thead>
        <tr className="text-gray-500 text-left border-b border-gray-800">
          <th className="pb-2 pl-2 w-8"></th>
          <th className="pb-2">Config</th>
          <th className="pb-2">Status</th>
          <th className="pb-2">Created</th>
          <th className="pb-2">Duration</th>
        </tr>
      </thead>
      <tbody>
        {jobs.length === 0 && (
          <tr>
            <td colSpan={5} className="text-gray-500 text-center py-8">
              No jobs found
            </td>
          </tr>
        )}
        {jobs.map((job) => (
          <tr
            key={job.id}
            onClick={() => onSelect(job.id)}
            className={`cursor-pointer border-b border-gray-800/50 hover:bg-gray-900 ${
              selectedId === job.id ? 'bg-gray-900' : ''
            }`}
          >
            <td className="py-2 pl-2">
              <span
                className={`inline-block w-2.5 h-2.5 rounded-full ${STATUS_COLORS[job.status]}`}
              />
            </td>
            <td className="py-2 font-medium">{job.config_name}</td>
            <td className="py-2 text-gray-400">{STATUS_LABELS[job.status]}</td>
            <td className="py-2 text-gray-400">{formatTime(job.created_at)}</td>
            <td className="py-2 text-gray-400">{formatDuration(job)}</td>
          </tr>
        ))}
      </tbody>
    </table>
  )
}

function JobDetail({ job }: { job: Job }) {
  const queryClient = useQueryClient()
  const [logLines, setLogLines] = useState<string[]>([])
  const logRef = useRef<HTMLDivElement>(null)

  const cancelMutation = useMutation({
    mutationFn: () => cancelJob(job.id),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['jobs'] }),
  })

  const rerunMutation = useMutation({
    mutationFn: () => rerunJob(job.id),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['jobs'] }),
  })

  useEffect(() => {
    if (job.status !== 'running') {
      setLogLines(job.log ? job.log.split('\n').filter(Boolean) : [])
      return
    }
    // Start with existing log lines
    setLogLines(job.log ? job.log.split('\n').filter(Boolean) : [])
    const ws = connectJobWS(job.id, (msg) => {
      if (msg.type === 'log') {
        setLogLines((prev) => [...prev, msg.line as string])
      }
      if (msg.type === 'status') {
        queryClient.invalidateQueries({ queryKey: ['jobs'] })
      }
    })
    return () => ws.close()
  }, [job.id, job.status, job.log, queryClient])

  // Auto-scroll log
  useEffect(() => {
    logRef.current?.scrollTo(0, logRef.current.scrollHeight)
  }, [logLines])

  return (
    <div className="space-y-4">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-lg font-bold">{job.config_name}</h2>
          <p className="text-xs text-gray-500 font-mono">{job.id}</p>
        </div>
        <span
          className={`px-2 py-1 text-xs font-medium rounded ${STATUS_COLORS[job.status]} text-white`}
        >
          {STATUS_LABELS[job.status]}
        </span>
      </div>

      {/* Progress */}
      {job.status === 'running' && <ProgressBar job={job} />}

      {/* Error */}
      {job.error && (
        <div className="bg-red-900/30 border border-red-800 rounded p-3 text-sm text-red-300">
          {job.error}
        </div>
      )}

      {/* Timestamps */}
      <div className="grid grid-cols-2 gap-2 text-xs text-gray-400">
        <div>
          <span className="text-gray-500">Created:</span>{' '}
          {formatTime(job.created_at)}
        </div>
        {job.started_at && (
          <div>
            <span className="text-gray-500">Started:</span>{' '}
            {formatTime(job.started_at)}
          </div>
        )}
        {job.completed_at && (
          <div>
            <span className="text-gray-500">Finished:</span>{' '}
            {formatTime(job.completed_at)}
          </div>
        )}
        <div>
          <span className="text-gray-500">Duration:</span>{' '}
          {formatDuration(job)}
        </div>
      </div>

      {/* Data path */}
      {job.data_path && (
        <div className="text-xs text-gray-400">
          <span className="text-gray-500">Output:</span>{' '}
          <span className="font-mono">{job.data_path}</span>
        </div>
      )}

      {/* Log viewer */}
      <div>
        <h3 className="text-sm font-medium text-gray-300 mb-1">Log Output</h3>
        <div
          ref={logRef}
          className="h-64 overflow-y-auto bg-black rounded border border-gray-800 p-2 font-mono text-xs text-gray-300"
        >
          {logLines.length === 0 ? (
            <p className="text-gray-600">No log output yet</p>
          ) : (
            logLines.map((line, i) => (
              <div key={i} className="whitespace-pre-wrap break-all leading-5">
                {line}
              </div>
            ))
          )}
        </div>
      </div>

      {/* Actions */}
      <div className="flex gap-2 pt-2">
        {(job.status === 'queued' || job.status === 'running') && (
          <button
            onClick={() => cancelMutation.mutate()}
            disabled={cancelMutation.isPending}
            className="px-3 py-1.5 text-sm bg-red-600 hover:bg-red-700 disabled:opacity-50 rounded"
          >
            {cancelMutation.isPending ? 'Cancelling...' : 'Cancel'}
          </button>
        )}
        {(job.status === 'completed' ||
          job.status === 'failed' ||
          job.status === 'cancelled') && (
          <button
            onClick={() => rerunMutation.mutate()}
            disabled={rerunMutation.isPending}
            className="px-3 py-1.5 text-sm bg-blue-600 hover:bg-blue-700 disabled:opacity-50 rounded"
          >
            {rerunMutation.isPending ? 'Submitting...' : 'Re-run'}
          </button>
        )}
      </div>
    </div>
  )
}

export default function JobMonitor() {
  const [selectedId, setSelectedId] = useState<string | null>(null)
  const [statusFilter, setStatusFilter] = useState('all')

  const { data: jobs = [] } = useQuery({
    queryKey: ['jobs'],
    queryFn: () => listJobs(),
    refetchInterval: 3000,
  })

  const filteredJobs =
    statusFilter === 'all'
      ? jobs
      : jobs.filter((j) => j.status === statusFilter)

  const selected = jobs.find((j) => j.id === selectedId) ?? null

  return (
    <div className="flex gap-6 h-[calc(100vh-5rem)]">
      <div className="flex-1 overflow-y-auto">
        <h1 className="text-2xl font-bold mb-4">Job Monitor</h1>
        <StatusFilter value={statusFilter} onChange={setStatusFilter} />
        <JobList
          jobs={filteredJobs}
          selectedId={selectedId}
          onSelect={setSelectedId}
        />
      </div>
      <div className="w-[600px] border border-gray-800 rounded-lg bg-gray-900 p-4 overflow-y-auto">
        {selected ? (
          <JobDetail job={selected} />
        ) : (
          <p className="text-gray-500 text-center mt-20">
            Select a job to view details
          </p>
        )}
      </div>
    </div>
  )
}
