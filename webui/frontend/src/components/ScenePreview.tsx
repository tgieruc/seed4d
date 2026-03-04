import { useMemo } from 'react'
import { Canvas } from '@react-three/fiber'
import { OrbitControls, Grid } from '@react-three/drei'
import * as THREE from 'three'
import { useConfigStore } from '../store/configStore'
import { useQuery } from '@tanstack/react-query'
import { listCameraRigs } from '../api'

function CarModel() {
  return (
    <mesh position={[0, 0.75, 0]}>
      <boxGeometry args={[2.0, 1.5, 4.5]} />
      <meshStandardMaterial color="#3b82f6" transparent opacity={0.6} />
    </mesh>
  )
}

interface CameraFrustumProps {
  position: [number, number, number]
  pitch: number
  yaw: number
  fov: number
  color: string
}

function CameraFrustum({ position, pitch, yaw, fov, color }: CameraFrustumProps) {
  const length = 1.5
  const halfFov = (fov * Math.PI) / 360
  const halfW = Math.tan(halfFov) * length
  const halfH = halfW * 0.75

  const geometry = useMemo(() => {
    const points = [
      new THREE.Vector3(0, 0, 0),
      new THREE.Vector3(-halfW, -halfH, length),
      new THREE.Vector3(halfW, -halfH, length),
      new THREE.Vector3(halfW, halfH, length),
      new THREE.Vector3(-halfW, halfH, length),
    ]

    const edges: [number, number][] = [
      [0, 1], [0, 2], [0, 3], [0, 4],
      [1, 2], [2, 3], [3, 4], [4, 1],
    ]

    const linePoints: THREE.Vector3[] = []
    for (const [a, b] of edges) {
      linePoints.push(points[a], points[b])
    }

    return new THREE.BufferGeometry().setFromPoints(linePoints)
  }, [halfW, halfH, length])

  return (
    <group position={position} rotation={[pitch, yaw, 0]}>
      <lineSegments geometry={geometry}>
        <lineBasicMaterial color={color} />
      </lineSegments>
      <mesh position={[0, 0, 0.1]}>
        <sphereGeometry args={[0.08, 8, 8]} />
        <meshStandardMaterial color={color} />
      </mesh>
    </group>
  )
}

function CameraRigDisplay() {
  const datasets = useConfigStore((s) => s.datasets)
  const { data: rigs } = useQuery({ queryKey: ['camera-rigs'], queryFn: listCameraRigs })

  if (!rigs) return null

  const colors = ['#ef4444', '#22c55e', '#3b82f6', '#f59e0b', '#a855f7', '#06b6d4']

  return (
    <>
      {datasets.map((ds, di) => {
        const rig = rigs.find((r) => ds.camera_rig_file.includes(r.file))
        if (!rig) return null
        return rig.content.coordinates.map((coord, ci) => (
          <CameraFrustum
            key={`${di}-${ci}`}
            position={[coord[0], coord[2], coord[1]]}
            pitch={rig.content.pitchs[ci]}
            yaw={rig.content.yaws[ci]}
            fov={rig.content.fov?.[ci] ?? ds.fov}
            color={colors[di % colors.length]}
          />
        ))
      })}
    </>
  )
}

export default function ScenePreview() {
  return (
    <Canvas camera={{ position: [8, 6, 8], fov: 50 }}>
      <ambientLight intensity={0.5} />
      <directionalLight position={[10, 10, 5]} intensity={1} />
      <Grid
        args={[50, 50]}
        cellSize={1}
        cellColor="#1e293b"
        sectionSize={5}
        sectionColor="#334155"
        fadeDistance={50}
        position={[0, 0, 0]}
      />
      <CarModel />
      <CameraRigDisplay />
      <OrbitControls />
      <axesHelper args={[3]} />
    </Canvas>
  )
}
