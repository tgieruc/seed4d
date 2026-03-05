import type { Config, Job, CameraRig, DatasetNode } from './types'

const BASE = ''

async function fetchJSON<T>(url: string, init?: RequestInit): Promise<T> {
  const res = await fetch(BASE + url, init)
  if (!res.ok) throw new Error(`${res.status} ${res.statusText}`)
  return res.json()
}

// Configs
export const listConfigs = () => fetchJSON<Config[]>('/api/configs')
export const getConfig = (id: string) => fetchJSON<Config>(`/api/configs/${id}`)
export const createConfig = (name: string, yaml_content: string) =>
  fetchJSON<Config>('/api/configs', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ name, yaml_content }),
  })
export const updateConfig = (id: string, name: string, yaml_content: string) =>
  fetchJSON<Config>(`/api/configs/${id}`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ name, yaml_content }),
  })
export const deleteConfig = (id: string) =>
  fetch(`/api/configs/${id}`, { method: 'DELETE' })
export const validateConfig = (id: string) =>
  fetchJSON<{ valid: boolean; errors: string[] }>(`/api/configs/${id}/validate`, { method: 'POST' })

// Filesystem configs (existing YAML files in config/)
export const listFilesystemConfigs = () =>
  fetchJSON<{ name: string; filename: string; path: string; content: string }[]>('/api/configs/filesystem')

// References
export const listMaps = () => fetchJSON<string[]>('/api/maps')
export const listWeathers = () => fetchJSON<string[]>('/api/weathers')
export const listVehicles = () => fetchJSON<string[]>('/api/vehicles')
export const listCameraRigs = () => fetchJSON<CameraRig[]>('/api/camera-rigs')

// Jobs
export const listJobs = (status?: string) =>
  fetchJSON<Job[]>(`/api/jobs${status ? `?status=${status}` : ''}`)
export const getJob = (id: string) => fetchJSON<Job>(`/api/jobs/${id}`)
export const submitJob = (config_id: string) =>
  fetchJSON<Job>('/api/jobs', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ config_id }),
  })
export const cancelJob = (id: string) =>
  fetch(`/api/jobs/${id}/cancel`, { method: 'POST' })
export const rerunJob = (id: string) =>
  fetchJSON<Job>(`/api/jobs/${id}/rerun`, { method: 'POST' })

// Datasets
export const listDatasets = () => fetchJSON<DatasetNode[]>('/api/datasets')
export const getTransforms = (path: string) =>
  fetchJSON<Record<string, unknown>>(`/api/datasets/${path}/transforms`)

// WebSocket
export function connectJobWS(jobId: string, onMessage: (msg: Record<string, unknown>) => void): WebSocket {
  const proto = window.location.protocol === 'https:' ? 'wss' : 'ws'
  const ws = new WebSocket(`${proto}://${window.location.host}/ws/jobs/${jobId}`)
  ws.onmessage = (e) => onMessage(JSON.parse(e.data))
  return ws
}
