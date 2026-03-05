import { useMemo } from 'react'
import { Canvas } from '@react-three/fiber'
import { OrbitControls } from '@react-three/drei'
import * as THREE from 'three'
import { useQuery } from '@tanstack/react-query'
import { getTransforms } from '../api'

const FRUSTUM_LENGTH = 0.8
const FRUSTUM_COLORS = ['#ef4444', '#f59e0b', '#22c55e', '#3b82f6', '#a855f7', '#06b6d4', '#ec4899']

function CameraFrustum({ matrix, color, fov }: { matrix: number[][]; color: string; fov?: number }) {
  const { position, quaternion, geometry } = useMemo(() => {
    const mat = new THREE.Matrix4()
    // Three.js Matrix4.set() takes row-major order
    mat.set(
      matrix[0][0], matrix[0][1], matrix[0][2], matrix[0][3],
      matrix[1][0], matrix[1][1], matrix[1][2], matrix[1][3],
      matrix[2][0], matrix[2][1], matrix[2][2], matrix[2][3],
      matrix[3][0], matrix[3][1], matrix[3][2], matrix[3][3],
    )

    const pos = new THREE.Vector3()
    const quat = new THREE.Quaternion()
    const scl = new THREE.Vector3()
    mat.decompose(pos, quat, scl)

    // Build frustum wireframe along local -Z
    const halfAngle = ((fov ?? 90) * Math.PI) / 360
    const halfW = Math.tan(halfAngle) * FRUSTUM_LENGTH
    const halfH = halfW * 0.5625

    const pts = [
      new THREE.Vector3(0, 0, 0),
      new THREE.Vector3(-halfW, -halfH, -FRUSTUM_LENGTH),
      new THREE.Vector3(halfW, -halfH, -FRUSTUM_LENGTH),
      new THREE.Vector3(halfW, halfH, -FRUSTUM_LENGTH),
      new THREE.Vector3(-halfW, halfH, -FRUSTUM_LENGTH),
    ]
    const edges: [number, number][] = [
      [0, 1], [0, 2], [0, 3], [0, 4],
      [1, 2], [2, 3], [3, 4], [4, 1],
    ]
    const linePoints: THREE.Vector3[] = []
    for (const [a, b] of edges) {
      linePoints.push(pts[a], pts[b])
    }
    const geo = new THREE.BufferGeometry().setFromPoints(linePoints)

    return { position: pos, quaternion: quat, geometry: geo }
  }, [matrix, fov])

  return (
    <group position={position} quaternion={quaternion}>
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

function TransformFrustums({ path, step }: { path: string; step: string }) {
  const { data, isLoading } = useQuery({
    queryKey: ['transforms-3d', path, step],
    queryFn: () => getTransforms(`${path}/${step}/ego_vehicle/nuscenes`),
  })

  const { frames, centroid } = useMemo(() => {
    const rawFrames = ((data as any)?.frames || []) as any[]
    if (rawFrames.length === 0) return { frames: rawFrames, centroid: new THREE.Vector3() }

    // Compute centroid of all camera positions to center the scene
    const center = new THREE.Vector3()
    for (const frame of rawFrames) {
      const m = frame.transform_matrix
      if (!m || m.length < 4) continue
      center.x += m[0][3]
      center.y += m[1][3]
      center.z += m[2][3]
    }
    center.divideScalar(rawFrames.length)

    return { frames: rawFrames, centroid: center }
  }, [data])

  if (isLoading || !data) return null

  return (
    <group position={[-centroid.x, -centroid.y, -centroid.z]}>
      {frames.map((frame: any, i: number) => {
        const m = frame.transform_matrix
        if (!m || m.length < 4) return null
        return (
          <CameraFrustum
            key={i}
            matrix={m}
            color={FRUSTUM_COLORS[i % FRUSTUM_COLORS.length]}
            fov={(data as any).fl_x ? undefined : 90}
          />
        )
      })}
    </group>
  )
}

function EgoVehicle() {
  return (
    <mesh position={[0, 0, 0]}>
      <boxGeometry args={[1.8, 0.8, 4.5]} />
      <meshStandardMaterial color="#22c55e" opacity={0.4} transparent wireframe />
    </mesh>
  )
}

export default function DataViewer3D({ path, step }: { path: string; step: string }) {
  return (
    <div className="h-[600px] border border-gray-700 rounded-lg overflow-hidden">
      <Canvas camera={{ position: [5, 4, 5], fov: 50 }}>
        <ambientLight intensity={0.5} />
        <directionalLight position={[10, 10, 5]} intensity={0.8} />
        <gridHelper args={[20, 20, '#1e293b', '#334155']} />
        <axesHelper args={[2]} />
        <EgoVehicle />
        <TransformFrustums path={path} step={step} />
        <OrbitControls />
      </Canvas>
    </div>
  )
}
