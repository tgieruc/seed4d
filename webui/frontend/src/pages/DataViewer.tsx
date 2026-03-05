import { useQuery } from '@tanstack/react-query'
import { lazy, Suspense, useEffect, useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import { listDatasets, getTransforms } from '../api'
import type { DatasetNode } from '../types'

const DataViewer3D = lazy(() => import('../components/DataViewer3D'))

function TreeNode({
  node,
  depth,
  onSelect,
  selectedPath,
}: {
  node: DatasetNode
  depth: number
  onSelect: (path: string, steps: string[], sensorGroups: string[]) => void
  selectedPath: string | null
}) {
  const [open, setOpen] = useState(depth < 1)
  const hasChildren = node.children && node.children.length > 0
  const isSelectable = node.type === 'spawn_point' && node.path
  const isSelected = isSelectable && node.path === selectedPath

  const typeColors: Record<string, string> = {
    map: 'text-blue-400',
    weather: 'text-amber-400',
    vehicle: 'text-green-400',
    spawn_point: 'text-purple-400',
  }

  return (
    <div>
      <button
        onClick={() => {
          if (isSelectable) {
            onSelect(node.path!, node.steps || [], node.sensor_groups || [])
          } else if (hasChildren) {
            setOpen(!open)
          }
        }}
        className={`flex items-center gap-1.5 w-full text-left py-0.5 px-1 rounded text-sm hover:bg-gray-800 ${
          isSelected ? 'bg-gray-800 text-white' : ''
        }`}
        style={{ paddingLeft: `${depth * 12 + 4}px` }}
      >
        {hasChildren && (
          <span className="text-gray-500 w-3 text-xs">{open ? '▾' : '▸'}</span>
        )}
        {isSelectable && <span className="w-3" />}
        <span className={typeColors[node.type] || 'text-gray-300'}>{node.name}</span>
        {node.steps && (
          <span className="text-gray-600 text-xs ml-auto">{node.steps.length} steps</span>
        )}
      </button>
      {open && hasChildren && (
        <div>
          {node.children!.map((child) => (
            <TreeNode
              key={child.name}
              node={child}
              depth={depth + 1}
              onSelect={onSelect}
              selectedPath={selectedPath}
            />
          ))}
        </div>
      )}
    </div>
  )
}

function DatasetTree({
  nodes,
  onSelect,
  selectedPath,
}: {
  nodes: DatasetNode[]
  onSelect: (path: string, steps: string[], sensorGroups: string[]) => void
  selectedPath: string | null
}) {
  if (nodes.length === 0) {
    return <p className="text-gray-500 text-sm">No datasets found. Run a job to generate data.</p>
  }
  return (
    <div>
      {nodes.map((node) => (
        <TreeNode
          key={node.name}
          node={node}
          depth={0}
          onSelect={onSelect}
          selectedPath={selectedPath}
        />
      ))}
    </div>
  )
}

function StepSelector({
  steps,
  selected,
  onSelect,
}: {
  steps: string[]
  selected: string
  onSelect: (step: string) => void
}) {
  if (steps.length === 0) return null
  return (
    <div className="flex items-center gap-2">
      <label className="text-sm text-gray-400">Step:</label>
      <select
        value={selected}
        onChange={(e) => onSelect(e.target.value)}
        className="bg-gray-800 border border-gray-700 rounded px-2 py-1 text-sm"
      >
        {steps.map((s) => (
          <option key={s} value={s}>{s}</option>
        ))}
      </select>
    </div>
  )
}

function ImageGallery({ path, step, sensorGroup }: { path: string; step: string; sensorGroup: string }) {
  const basePath = `${path}/${step}/ego_vehicle/${sensorGroup}`
  const { data: transforms, isLoading } = useQuery({
    queryKey: ['transforms', basePath],
    queryFn: () => getTransforms(basePath),
  })

  if (isLoading) return <p className="text-gray-500">Loading transforms...</p>
  if (!transforms) return <p className="text-gray-500">No transform data available.</p>

  const frames = (transforms as any).frames || []
  if (frames.length === 0) return <p className="text-gray-500">No frames found.</p>

  return (
    <div className="grid grid-cols-3 gap-4">
      {frames.map((frame: any, i: number) => {
        const filename = frame.file_path.split('/').pop()
        return (
          <div key={i} className="border border-gray-700 rounded overflow-hidden">
            <img
              src={`/api/datasets/${basePath}/images/${filename}`}
              alt={`Camera ${i}`}
              className="w-full bg-gray-900"
              loading="lazy"
            />
            <p className="text-xs text-gray-400 p-1.5">Camera {i} &mdash; {filename}</p>
          </div>
        )
      })}
    </div>
  )
}

function BevViewer({ path }: { path: string }) {
  return (
    <div>
      <img
        src={`/api/datasets/${path}/bev`}
        alt="Bird's Eye View"
        className="max-w-lg rounded border border-gray-700"
        onError={(e) => {
          ;(e.target as HTMLImageElement).style.display = 'none'
          ;(e.target as HTMLImageElement).insertAdjacentHTML(
            'afterend',
            '<p class="text-gray-500">BEV GIF not available for this dataset.</p>'
          )
        }}
      />
    </div>
  )
}

export default function DataViewer() {
  const [searchParams] = useSearchParams()
  const { data: datasets = [] } = useQuery({ queryKey: ['datasets'], queryFn: listDatasets })
  const [selectedPath, setSelectedPath] = useState<string | null>(null)
  const [availableSteps, setAvailableSteps] = useState<string[]>([])
  const [selectedStep, setSelectedStep] = useState<string>('step_0')
  const [sensorGroups, setSensorGroups] = useState<string[]>([])
  const [selectedGroup, setSelectedGroup] = useState<string>('')
  const [activeTab, setActiveTab] = useState<'gallery' | '3d' | 'bev'>('gallery')

  // Auto-select dataset from URL query param (e.g., from Job Monitor "View Data" button)
  useEffect(() => {
    const pathParam = searchParams.get('path')
    if (pathParam && !selectedPath) {
      setSelectedPath(pathParam)
    }
  }, [searchParams, selectedPath])

  const handleSelect = (path: string, steps: string[], groups: string[]) => {
    setSelectedPath(path)
    setAvailableSteps(steps)
    setSensorGroups(groups)
    if (steps.length > 0 && !steps.includes(selectedStep)) {
      setSelectedStep(steps[0])
    }
    if (groups.length > 0 && !groups.includes(selectedGroup)) {
      setSelectedGroup(groups[0])
    }
  }

  const tabs = [
    { key: 'gallery' as const, label: 'Image Gallery' },
    { key: '3d' as const, label: '3D Viewer' },
    { key: 'bev' as const, label: 'BEV Playback' },
  ]

  return (
    <div className="flex gap-6 h-[calc(100vh-5rem)]">
      <div className="w-64 shrink-0 overflow-y-auto border-r border-gray-800 pr-4">
        <h2 className="text-lg font-bold mb-3">Datasets</h2>
        <DatasetTree
          nodes={datasets}
          onSelect={handleSelect}
          selectedPath={selectedPath}
        />
      </div>
      <div className="flex-1 overflow-y-auto">
        <div className="flex gap-2 mb-4 border-b border-gray-800 pb-2">
          {tabs.map(({ key, label }) => (
            <button
              key={key}
              onClick={() => setActiveTab(key)}
              className={`px-3 py-1 rounded text-sm ${
                activeTab === key ? 'bg-blue-600 text-white' : 'bg-gray-800 text-gray-300 hover:bg-gray-700'
              }`}
            >
              {label}
            </button>
          ))}
        </div>
        {selectedPath ? (
          <>
            {activeTab !== 'bev' && (
              <div className="flex items-center gap-4 mb-4">
                <StepSelector steps={availableSteps} selected={selectedStep} onSelect={setSelectedStep} />
                {sensorGroups.length > 1 && (
                  <div className="flex items-center gap-2">
                    <label className="text-sm text-gray-400">Sensor Group:</label>
                    <select
                      value={selectedGroup}
                      onChange={(e) => setSelectedGroup(e.target.value)}
                      className="bg-gray-800 border border-gray-700 rounded px-2 py-1 text-sm"
                    >
                      {sensorGroups.map((g) => (
                        <option key={g} value={g}>{g}</option>
                      ))}
                    </select>
                  </div>
                )}
              </div>
            )}
            {activeTab === 'gallery' && selectedGroup && (
              <ImageGallery path={selectedPath} step={selectedStep} sensorGroup={selectedGroup} />
            )}
            {activeTab === '3d' && selectedGroup && (
              <Suspense fallback={<p className="text-gray-500">Loading 3D viewer...</p>}>
                <DataViewer3D path={selectedPath} step={selectedStep} sensorGroup={selectedGroup} />
              </Suspense>
            )}
            {activeTab === 'bev' && <BevViewer path={selectedPath} />}
          </>
        ) : (
          <p className="text-gray-500 mt-10">Select a dataset from the sidebar to browse images, view 3D transforms, or play BEV animations.</p>
        )}
      </div>
    </div>
  )
}
