import { useMemo } from 'react'
import { Canvas } from '@react-three/fiber'
import { OrbitControls, Grid } from '@react-three/drei'
import * as THREE from 'three'
import { useConfigStore } from '../store/configStore'
import { useQuery } from '@tanstack/react-query'
import { listCameraRigs } from '../api'

function CarModel() {
  return (
    <group>
      {/* Solid body with low opacity */}
      <mesh position={[0, 0.5, 0]}>
        <boxGeometry args={[1.8, 1.0, 4.2]} />
        <meshStandardMaterial color="#3b82f6" transparent opacity={0.15} />
      </mesh>
      {/* Wireframe outline */}
      <mesh position={[0, 0.5, 0]}>
        <boxGeometry args={[1.8, 1.0, 4.2]} />
        <meshStandardMaterial color="#3b82f6" wireframe transparent opacity={0.5} />
      </mesh>
      {/* Cabin */}
      <mesh position={[0, 1.15, -0.2]}>
        <boxGeometry args={[1.6, 0.7, 2.2]} />
        <meshStandardMaterial color="#3b82f6" transparent opacity={0.1} />
      </mesh>
      <mesh position={[0, 1.15, -0.2]}>
        <boxGeometry args={[1.6, 0.7, 2.2]} />
        <meshStandardMaterial color="#3b82f6" wireframe transparent opacity={0.3} />
      </mesh>
    </group>
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
  // Frustum length scaled to be visually readable
  const length = 0.6
  const halfFov = (fov * Math.PI) / 360
  const halfW = Math.tan(halfFov) * length
  const halfH = halfW * 0.5625 // 16:9 aspect

  const geometry = useMemo(() => {
    // Frustum points along local -Z (Three.js camera convention: looks down -Z)
    const points = [
      new THREE.Vector3(0, 0, 0),
      new THREE.Vector3(-halfW, -halfH, -length),
      new THREE.Vector3(halfW, -halfH, -length),
      new THREE.Vector3(halfW, halfH, -length),
      new THREE.Vector3(-halfW, halfH, -length),
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

  // Camera config angles are in radians.
  // CARLA applies: yaw_deg = -(yaw_rad * 180/π + 90), pitch_deg = -pitch_rad * 180/π
  // CARLA coords: x=forward, y=right, z=up → Three.js: carla_y→x, carla_z→y, carla_x→-z
  // Three.js frustum looks down -Z. CARLA yaw=0° = Three.js -Z = no rotation.
  // Mapping: three_yaw = -(yaw_rad + π/2), three_pitch = pitch_rad
  const rotation = useMemo(() => {
    const threeYaw = -(yaw + Math.PI / 2)
    return new THREE.Euler(pitch, threeYaw, 0, 'YXZ')
  }, [pitch, yaw])

  return (
    <group position={position} rotation={rotation}>
      <lineSegments geometry={geometry}>
        <lineBasicMaterial color={color} />
      </lineSegments>
      <mesh>
        <sphereGeometry args={[0.06, 8, 8]} />
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
        return rig.content.coordinates.map((coord, ci) => {
          // Camera config coords: [x, y, z] in CARLA (x=forward, y=right, z=up)
          // Three.js: x=right, y=up, z=backward
          const threePos: [number, number, number] = [coord[1], coord[2], -coord[0]]
          return (
            <CameraFrustum
              key={`${di}-${ci}`}
              position={threePos}
              pitch={rig.content.pitchs[ci]}
              yaw={rig.content.yaws[ci]}
              fov={rig.content.fov?.[ci] ?? ds.fov}
              color={colors[di % colors.length]}
            />
          )
        })
      })}
    </>
  )
}

export default function ScenePreview() {
  return (
    <Canvas camera={{ position: [6, 4, 6], fov: 50 }}>
      <ambientLight intensity={0.5} />
      <directionalLight position={[10, 10, 5]} intensity={1} />
      <Grid
        args={[20, 20]}
        cellSize={1}
        cellColor="#1e293b"
        sectionSize={5}
        sectionColor="#334155"
        fadeDistance={25}
        position={[0, 0, 0]}
      />
      <CarModel />
      <CameraRigDisplay />
      <OrbitControls />
      <axesHelper args={[2]} />
    </Canvas>
  )
}
