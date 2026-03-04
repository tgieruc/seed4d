import { create } from 'zustand'
import yaml from 'js-yaml'

export interface SensorDataset {
  name: string
  attached_to_vehicle: boolean
  sensor_types: string[]
  fov: number
  width: number
  height: number
  camera_rig_file: string
  channels?: number
  points_per_second?: number
  rotation_frequency?: number
  range?: number
}

export interface ConfigFormState {
  // World
  map: string
  weather: string
  vehicle: string
  // Spawn
  spawn_points: number[]
  // Simulation
  steps: number
  min_distance: number
  synchronous_mode: boolean
  fixed_delta_seconds: number
  timeout: number
  // Traffic
  number_of_vehicles: number
  number_of_walkers: number
  large_vehicles: boolean
  sort_spawnpoints: boolean
  // Sensors
  datasets: SensorDataset[]
  // Options
  bev_camera: boolean
  invisible_ego: boolean
  three_d_boundingbox: boolean
  // Post-processing
  normalize_coords: boolean
  vehicle_masks: boolean
  combine_transforms: boolean
  generate_map: boolean
}

interface ConfigStore extends ConfigFormState {
  set: <K extends keyof ConfigFormState>(key: K, value: ConfigFormState[K]) => void
  setDataset: (index: number, dataset: SensorDataset) => void
  addDataset: () => void
  removeDataset: (index: number) => void
  toYAML: () => string
  reset: () => void
  loadFromYAML: (yamlStr: string) => void
}

const DEFAULT_DATASET: SensorDataset = {
  name: 'nuscenes',
  attached_to_vehicle: true,
  sensor_types: ['sensor.camera.rgb'],
  fov: 90,
  width: 1600,
  height: 900,
  camera_rig_file: 'camera/nuscenes/nuscenes_adjusted.json',
}

const DEFAULTS: ConfigFormState = {
  map: 'Town01',
  weather: 'ClearNoon',
  vehicle: 'vehicle.mini.cooper_s',
  spawn_points: [1],
  steps: 5,
  min_distance: 0.0,
  synchronous_mode: true,
  fixed_delta_seconds: 0.1,
  timeout: 720.0,
  number_of_vehicles: 5,
  number_of_walkers: 0,
  large_vehicles: false,
  sort_spawnpoints: false,
  datasets: [{ ...DEFAULT_DATASET }],
  bev_camera: true,
  invisible_ego: false,
  three_d_boundingbox: true,
  normalize_coords: true,
  vehicle_masks: true,
  combine_transforms: true,
  generate_map: true,
}

export const useConfigStore = create<ConfigStore>((set, get) => ({
  ...DEFAULTS,

  set: (key, value) => set({ [key]: value }),

  setDataset: (index, dataset) =>
    set((s) => {
      const datasets = [...s.datasets]
      datasets[index] = dataset
      return { datasets }
    }),

  addDataset: () =>
    set((s) => ({ datasets: [...s.datasets, { ...DEFAULT_DATASET, name: `dataset_${s.datasets.length}` }] })),

  removeDataset: (index) =>
    set((s) => ({ datasets: s.datasets.filter((_, i) => i !== index) })),

  toYAML: () => {
    const s = get()
    const dataset: Record<string, unknown> = {}
    for (const ds of s.datasets) {
      const sensor_info: Record<string, unknown> = {
        type: ds.sensor_types,
        fov: ds.fov,
        width: ds.width,
        height: ds.height,
      }
      dataset[ds.name] = {
        attached_to_vehicle: ds.attached_to_vehicle,
        sensor_info,
        transform_file_cams: ds.camera_rig_file,
      }
    }
    const config: Record<string, unknown> = {
      map: s.map,
      vehicle: s.vehicle,
      weather: s.weather,
      spawn_point: s.spawn_points,
      steps: s.steps,
      min_distance: s.min_distance,
      number_of_vehicles: s.number_of_vehicles,
      number_of_walkers: s.number_of_walkers,
      large_vehicles: s.large_vehicles,
      sort_spawnpoints: s.sort_spawnpoints,
      BEVCamera: s.bev_camera,
      invisible_ego: s.invisible_ego,
      '3Dboundingbox': s.three_d_boundingbox,
      data_dir: 'data',
      carla: {
        host: 'localhost',
        port: 2000,
        synchronous_mode: s.synchronous_mode,
        fixed_delta_seconds: s.fixed_delta_seconds,
        timeout: s.timeout,
      },
      dataset,
    }
    return yaml.dump(config)
  },

  reset: () => set(DEFAULTS),

  loadFromYAML: (_yamlStr: string) => {
    // TODO: parse YAML and populate form
  },
}))
