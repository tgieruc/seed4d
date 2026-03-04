import { useState } from 'react'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { useConfigStore, type SensorDataset } from '../store/configStore'
import { listMaps, listWeathers, listVehicles, listCameraRigs, listFilesystemConfigs, listConfigs, createConfig, submitJob } from '../api'
import ScenePreview from '../components/ScenePreview'
import { useToastStore } from '../store/toastStore'

const SENSOR_TYPES = [
  'sensor.camera.rgb',
  'sensor.camera.depth',
  'sensor.camera.semantic_segmentation',
  'sensor.camera.instance_segmentation',
  'sensor.lidar.ray_cast',
  'sensor.lidar.ray_cast_semantic',
]

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <section className="bg-gray-900 border border-gray-800 rounded-lg p-4 space-y-3">
      <h2 className="text-sm font-semibold text-gray-300 uppercase tracking-wide">{title}</h2>
      {children}
    </section>
  )
}

function Label({ text, children }: { text: string; children: React.ReactNode }) {
  return (
    <label className="flex flex-col gap-1">
      <span className="text-xs text-gray-400">{text}</span>
      {children}
    </label>
  )
}

const inputCls = 'bg-gray-800 border border-gray-700 rounded px-3 py-1.5 text-sm focus:outline-none focus:border-blue-500'
const selectCls = inputCls

function ImportSection() {
  const loadFromYAML = useConfigStore((s) => s.loadFromYAML)
  const addToast = useToastStore((s) => s.addToast)
  const [showDropdown, setShowDropdown] = useState(false)
  const { data: fsConfigs = [] } = useQuery({
    queryKey: ['filesystem-configs'],
    queryFn: listFilesystemConfigs,
    enabled: showDropdown,
  })
  const { data: savedConfigs = [] } = useQuery({
    queryKey: ['configs'],
    queryFn: listConfigs,
    enabled: showDropdown,
  })

  function handleImportFS(content: string, name: string) {
    loadFromYAML(content)
    setShowDropdown(false)
    addToast(`Loaded config: ${name}`, 'success')
  }

  function handleImportSaved(yamlContent: string, name: string) {
    loadFromYAML(yamlContent)
    setShowDropdown(false)
    addToast(`Loaded config: ${name}`, 'success')
  }

  return (
    <div className="relative">
      <button
        onClick={() => setShowDropdown(!showDropdown)}
        className="bg-gray-800 hover:bg-gray-700 border border-gray-700 text-sm px-4 py-2 rounded flex items-center gap-2"
      >
        <span>Import Config</span>
        <span className="text-gray-500">{showDropdown ? '▴' : '▾'}</span>
      </button>
      {showDropdown && (
        <div className="absolute top-full left-0 mt-1 w-96 bg-gray-900 border border-gray-700 rounded-lg shadow-xl z-50 max-h-80 overflow-y-auto">
          {fsConfigs.length > 0 && (
            <>
              <div className="px-3 py-2 text-xs font-semibold text-gray-500 uppercase border-b border-gray-800">
                Existing Config Files
              </div>
              {fsConfigs.map((cfg) => (
                <button
                  key={cfg.path}
                  onClick={() => handleImportFS(cfg.content, cfg.name)}
                  className="w-full text-left px-3 py-2 text-sm hover:bg-gray-800 flex justify-between items-center"
                >
                  <span className="text-gray-200">{cfg.name}</span>
                  <span className="text-gray-500 text-xs">{cfg.filename}</span>
                </button>
              ))}
            </>
          )}
          {savedConfigs.length > 0 && (
            <>
              <div className="px-3 py-2 text-xs font-semibold text-gray-500 uppercase border-b border-gray-800">
                Saved Configs
              </div>
              {savedConfigs.map((cfg) => (
                <button
                  key={cfg.id}
                  onClick={() => handleImportSaved(cfg.yaml_content, cfg.name)}
                  className="w-full text-left px-3 py-2 text-sm hover:bg-gray-800 flex justify-between items-center"
                >
                  <span className="text-gray-200">{cfg.name}</span>
                  <span className="text-gray-500 text-xs">{new Date(cfg.updated_at).toLocaleDateString()}</span>
                </button>
              ))}
            </>
          )}
          {fsConfigs.length === 0 && savedConfigs.length === 0 && (
            <div className="px-3 py-4 text-sm text-gray-500 text-center">No configs found</div>
          )}
        </div>
      )}
    </div>
  )
}

function WorldSection() {
  const { map, weather, vehicle, set } = useConfigStore()
  const { data: maps = [] } = useQuery({ queryKey: ['maps'], queryFn: listMaps })
  const { data: weathers = [] } = useQuery({ queryKey: ['weathers'], queryFn: listWeathers })
  const { data: vehicles = [] } = useQuery({ queryKey: ['vehicles'], queryFn: listVehicles })

  return (
    <Section title="World">
      <div className="grid grid-cols-3 gap-3">
        <Label text="Map">
          <select className={selectCls} value={map} onChange={(e) => set('map', e.target.value)}>
            {maps.map((m) => <option key={m} value={m}>{m}</option>)}
          </select>
        </Label>
        <Label text="Weather">
          <select className={selectCls} value={weather} onChange={(e) => set('weather', e.target.value)}>
            {weathers.map((w) => <option key={w} value={w}>{w}</option>)}
          </select>
        </Label>
        <Label text="Vehicle">
          <select className={selectCls} value={vehicle} onChange={(e) => set('vehicle', e.target.value)}>
            {vehicles.map((v) => <option key={v} value={v}>{v}</option>)}
          </select>
        </Label>
      </div>
    </Section>
  )
}

function SpawnPointsSection() {
  const { spawn_points, set } = useConfigStore()
  const [input, setInput] = useState(spawn_points.join(', '))

  function handleBlur() {
    const parsed = input
      .split(/[,\s]+/)
      .map(Number)
      .filter((n) => !isNaN(n) && n >= 0)
    set('spawn_points', parsed.length > 0 ? parsed : [1])
  }

  return (
    <Section title="Spawn Points">
      <Label text="Spawn point IDs (comma-separated)">
        <input
          className={inputCls}
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onBlur={handleBlur}
          placeholder="1, 2, 3"
        />
      </Label>
      <p className="text-xs text-gray-500">{spawn_points.length} spawn point(s) selected</p>
    </Section>
  )
}

function SimulationSection() {
  const { steps, min_distance, synchronous_mode, fixed_delta_seconds, timeout, set } = useConfigStore()

  return (
    <Section title="Simulation">
      <div className="grid grid-cols-3 gap-3">
        <Label text="Steps per spawn point">
          <input type="number" className={inputCls} value={steps} min={1}
            onChange={(e) => set('steps', parseInt(e.target.value) || 1)} />
        </Label>
        <Label text="Min distance (m)">
          <input type="number" className={inputCls} value={min_distance} min={0} step={0.1}
            onChange={(e) => set('min_distance', parseFloat(e.target.value) || 0)} />
        </Label>
        <Label text="Timeout (s)">
          <input type="number" className={inputCls} value={timeout} min={1}
            onChange={(e) => set('timeout', parseFloat(e.target.value) || 720)} />
        </Label>
      </div>
      <div className="flex gap-6 items-center mt-2">
        <label className="flex items-center gap-2 text-sm">
          <input type="checkbox" checked={synchronous_mode}
            onChange={(e) => set('synchronous_mode', e.target.checked)} />
          Synchronous mode
        </label>
        <Label text="Delta seconds">
          <input type="number" className={inputCls + ' w-24'} value={fixed_delta_seconds} step={0.01} min={0.01}
            onChange={(e) => set('fixed_delta_seconds', parseFloat(e.target.value) || 0.1)} />
        </Label>
      </div>
    </Section>
  )
}

function TrafficSection() {
  const { number_of_vehicles, number_of_walkers, large_vehicles, sort_spawnpoints, set } = useConfigStore()

  return (
    <Section title="Traffic">
      <div className="grid grid-cols-2 gap-3">
        <Label text="NPC Vehicles">
          <input type="range" min={0} max={100} value={number_of_vehicles}
            onChange={(e) => set('number_of_vehicles', parseInt(e.target.value))} />
          <span className="text-xs text-gray-400">{number_of_vehicles}</span>
        </Label>
        <Label text="Walkers">
          <input type="range" min={0} max={100} value={number_of_walkers}
            onChange={(e) => set('number_of_walkers', parseInt(e.target.value))} />
          <span className="text-xs text-gray-400">{number_of_walkers}</span>
        </Label>
      </div>
      <div className="flex gap-6 mt-2">
        <label className="flex items-center gap-2 text-sm">
          <input type="checkbox" checked={large_vehicles}
            onChange={(e) => set('large_vehicles', e.target.checked)} />
          Allow large vehicles
        </label>
        <label className="flex items-center gap-2 text-sm">
          <input type="checkbox" checked={sort_spawnpoints}
            onChange={(e) => set('sort_spawnpoints', e.target.checked)} />
          Sort spawn points
        </label>
      </div>
    </Section>
  )
}

function SensorDatasetEditor({ dataset, index }: { dataset: SensorDataset; index: number }) {
  const { setDataset, removeDataset } = useConfigStore()
  const { data: rigs = [] } = useQuery({ queryKey: ['camera-rigs'], queryFn: listCameraRigs })

  function update<K extends keyof SensorDataset>(key: K, value: SensorDataset[K]) {
    setDataset(index, { ...dataset, [key]: value })
  }

  function toggleSensorType(type: string) {
    const types = dataset.sensor_types.includes(type)
      ? dataset.sensor_types.filter((t) => t !== type)
      : [...dataset.sensor_types, type]
    update('sensor_types', types)
  }

  return (
    <div className="bg-gray-800 border border-gray-700 rounded p-3 space-y-3">
      <div className="flex justify-between items-center">
        <Label text="Dataset name">
          <input className={inputCls} value={dataset.name}
            onChange={(e) => update('name', e.target.value)} />
        </Label>
        <button onClick={() => removeDataset(index)}
          className="text-red-400 hover:text-red-300 text-xs mt-4">Remove</button>
      </div>

      <label className="flex items-center gap-2 text-sm">
        <input type="checkbox" checked={dataset.attached_to_vehicle}
          onChange={(e) => update('attached_to_vehicle', e.target.checked)} />
        Attached to vehicle
      </label>

      <div>
        <span className="text-xs text-gray-400">Sensor Types</span>
        <div className="flex flex-wrap gap-2 mt-1">
          {SENSOR_TYPES.map((type) => (
            <label key={type} className="flex items-center gap-1 text-xs">
              <input type="checkbox" checked={dataset.sensor_types.includes(type)}
                onChange={() => toggleSensorType(type)} />
              {type.split('.').pop()}
            </label>
          ))}
        </div>
      </div>

      <div className="grid grid-cols-3 gap-3">
        <Label text="FOV">
          <input type="number" className={inputCls} value={dataset.fov} min={1} max={180}
            onChange={(e) => update('fov', parseInt(e.target.value) || 90)} />
        </Label>
        <Label text="Width">
          <input type="number" className={inputCls} value={dataset.width} min={1}
            onChange={(e) => update('width', parseInt(e.target.value) || 800)} />
        </Label>
        <Label text="Height">
          <input type="number" className={inputCls} value={dataset.height} min={1}
            onChange={(e) => update('height', parseInt(e.target.value) || 600)} />
        </Label>
      </div>

      <Label text="Camera Rig">
        <select className={selectCls} value={dataset.camera_rig_file}
          onChange={(e) => update('camera_rig_file', e.target.value)}>
          {rigs.map((r) => (
            <option key={r.file} value={r.file}>{r.name}/{r.filename} ({r.num_cameras} cams)</option>
          ))}
        </select>
      </Label>
    </div>
  )
}

function SensorDatasetsSection() {
  const { datasets, addDataset } = useConfigStore()

  return (
    <Section title="Sensor Datasets">
      <div className="space-y-3">
        {datasets.map((ds, i) => (
          <SensorDatasetEditor key={i} dataset={ds} index={i} />
        ))}
      </div>
      <button onClick={addDataset}
        className="text-sm text-blue-400 hover:text-blue-300 mt-2">
        + Add Dataset
      </button>
    </Section>
  )
}

function OptionsSection() {
  const { bev_camera, invisible_ego, three_d_boundingbox, set } = useConfigStore()

  return (
    <Section title="Options">
      <div className="flex flex-wrap gap-6">
        <label className="flex items-center gap-2 text-sm">
          <input type="checkbox" checked={bev_camera}
            onChange={(e) => set('bev_camera', e.target.checked)} />
          BEV Camera
        </label>
        <label className="flex items-center gap-2 text-sm">
          <input type="checkbox" checked={invisible_ego}
            onChange={(e) => set('invisible_ego', e.target.checked)} />
          Invisible ego vehicle
        </label>
        <label className="flex items-center gap-2 text-sm">
          <input type="checkbox" checked={three_d_boundingbox}
            onChange={(e) => set('three_d_boundingbox', e.target.checked)} />
          3D Bounding boxes
        </label>
      </div>
    </Section>
  )
}

function PostProcessingSection() {
  const { normalize_coords, vehicle_masks, combine_transforms, generate_map, set } = useConfigStore()

  return (
    <Section title="Post-processing">
      <div className="flex flex-wrap gap-6">
        <label className="flex items-center gap-2 text-sm">
          <input type="checkbox" checked={normalize_coords}
            onChange={(e) => set('normalize_coords', e.target.checked)} />
          Normalize coordinates
        </label>
        <label className="flex items-center gap-2 text-sm">
          <input type="checkbox" checked={vehicle_masks}
            onChange={(e) => set('vehicle_masks', e.target.checked)} />
          Vehicle masks
        </label>
        <label className="flex items-center gap-2 text-sm">
          <input type="checkbox" checked={combine_transforms}
            onChange={(e) => set('combine_transforms', e.target.checked)} />
          Combine transforms
        </label>
        <label className="flex items-center gap-2 text-sm">
          <input type="checkbox" checked={generate_map}
            onChange={(e) => set('generate_map', e.target.checked)} />
          Generate map
        </label>
      </div>
    </Section>
  )
}

function ActionsSection() {
  const toYAML = useConfigStore((s) => s.toYAML)
  const reset = useConfigStore((s) => s.reset)
  const map = useConfigStore((s) => s.map)
  const weather = useConfigStore((s) => s.weather)
  const queryClient = useQueryClient()
  const addToast = useToastStore((s) => s.addToast)
  const [saving, setSaving] = useState(false)
  const [yamlPreview, setYamlPreview] = useState<string | null>(null)

  async function handleSave() {
    setSaving(true)
    try {
      const yamlContent = toYAML()
      const name = `${map}_${weather}_${new Date().toISOString().slice(0, 16)}`
      await createConfig(name, yamlContent)
      queryClient.invalidateQueries({ queryKey: ['configs'] })
      addToast('Config saved successfully', 'success')
    } catch (e) {
      addToast(`Failed to save: ${e instanceof Error ? e.message : 'Unknown error'}`, 'error')
    } finally {
      setSaving(false)
    }
  }

  async function handleSaveAndRun() {
    setSaving(true)
    try {
      const yamlContent = toYAML()
      const name = `${map}_${weather}_${new Date().toISOString().slice(0, 16)}`
      const config = await createConfig(name, yamlContent)
      await submitJob(config.id)
      queryClient.invalidateQueries({ queryKey: ['configs'] })
      queryClient.invalidateQueries({ queryKey: ['jobs'] })
      addToast('Job submitted successfully', 'success')
    } catch (e) {
      addToast(`Failed to submit: ${e instanceof Error ? e.message : 'Unknown error'}`, 'error')
    } finally {
      setSaving(false)
    }
  }

  return (
    <Section title="Actions">
      <div className="flex gap-3">
        <button onClick={handleSave} disabled={saving}
          className="bg-gray-700 hover:bg-gray-600 text-sm px-4 py-2 rounded disabled:opacity-50">
          Save Config
        </button>
        <button onClick={handleSaveAndRun} disabled={saving}
          className="bg-blue-600 hover:bg-blue-500 text-sm px-4 py-2 rounded disabled:opacity-50">
          Save & Run
        </button>
        <button onClick={() => setYamlPreview(yamlPreview ? null : toYAML())}
          className="bg-gray-700 hover:bg-gray-600 text-sm px-4 py-2 rounded">
          {yamlPreview ? 'Hide' : 'Preview'} YAML
        </button>
        <button onClick={reset}
          className="text-gray-400 hover:text-gray-200 text-sm px-4 py-2">
          Reset
        </button>
      </div>
      {yamlPreview && (
        <pre className="bg-gray-800 border border-gray-700 rounded p-3 text-xs mt-3 overflow-x-auto max-h-64 overflow-y-auto">
          {yamlPreview}
        </pre>
      )}
    </Section>
  )
}

export default function ConfigBuilder() {
  return (
    <div className="flex gap-6 h-[calc(100vh-5rem)]">
      <div className="flex-1 overflow-y-auto space-y-4 pr-4">
        <div className="flex items-center justify-between">
          <h1 className="text-2xl font-bold">Config Builder</h1>
          <ImportSection />
        </div>
        <WorldSection />
        <SpawnPointsSection />
        <SimulationSection />
        <TrafficSection />
        <SensorDatasetsSection />
        <OptionsSection />
        <PostProcessingSection />
        <ActionsSection />
      </div>
      <div className="w-[500px] border border-gray-800 rounded-lg bg-gray-900 overflow-hidden">
        <ScenePreview />
      </div>
    </div>
  )
}
