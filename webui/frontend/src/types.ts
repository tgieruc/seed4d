export interface Config {
  id: string
  name: string
  yaml_content: string
  created_at: string
  updated_at: string
}

export interface Job {
  id: string
  config_id: string
  config_name: string
  status: 'queued' | 'running' | 'completed' | 'failed' | 'cancelled'
  progress: { spawn_point?: number; step?: number; total_spawn_points?: number; total_steps?: number } | null
  log: string
  created_at: string
  started_at: string | null
  completed_at: string | null
  error: string | null
  data_path: string | null
}

export interface CameraRig {
  name: string
  file: string
  filename: string
  num_cameras: number
  content: {
    coordinates: number[][]
    pitchs: number[]
    yaws: number[]
    fov?: number[]
  }
}

export interface DatasetNode {
  name: string
  type: 'map' | 'weather' | 'vehicle' | 'spawn_point'
  children?: DatasetNode[]
  steps?: string[]
  sensor_groups?: string[]
  path?: string
}
