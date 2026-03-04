import { Canvas } from '@react-three/fiber'
import { OrbitControls } from '@react-three/drei'
import * as THREE from 'three'
import { useQuery } from '@tanstack/react-query'
import { getTransforms } from '../api'

function CameraFrustum({ matrix }: { matrix: number[][] }) {
  const mat = new THREE.Matrix4()
  mat.set(
    matrix[0][0], matrix[0][1], matrix[0][2], matrix[0][3],
    matrix[1][0], matrix[1][1], matrix[1][2], matrix[1][3],
    matrix[2][0], matrix[2][1], matrix[2][2], matrix[2][3],
    matrix[3][0], matrix[3][1], matrix[3][2], matrix[3][3],
  )

  const pos = new THREE.Vector3()
  const quat = new THREE.Quaternion()
  const scale = new THREE.Vector3()
  mat.decompose(pos, quat, scale)

  // Draw a small cone to represent camera look direction
  const forward = new THREE.Vector3(0, 0, -1).applyQuaternion(quat)
  const conePos = pos.clone().add(forward.multiplyScalar(0.5))

  return (
    <group>
      <mesh position={pos}>
        <sphereGeometry args={[0.2]} />
        <meshStandardMaterial color="#ef4444" />
      </mesh>
      <mesh position={conePos} quaternion={quat}>
        <coneGeometry args={[0.15, 0.4, 8]} />
        <meshStandardMaterial color="#3b82f6" opacity={0.7} transparent />
      </mesh>
      {/* Label */}
      <group position={[pos.x, pos.y + 0.4, pos.z]}>
        <sprite scale={[0.5, 0.25, 1]}>
          <spriteMaterial color="#9ca3af" opacity={0.8} transparent />
        </sprite>
      </group>
    </group>
  )
}

function TransformFrustums({ path, step }: { path: string; step: string }) {
  const { data, isLoading } = useQuery({
    queryKey: ['transforms-3d', path, step],
    queryFn: () => getTransforms(`${path}/${step}/ego_vehicle/nuscenes`),
  })

  if (isLoading || !data) return null

  const frames = (data as any).frames || []
  return (
    <>
      {frames.map((frame: any, i: number) => {
        const m = frame.transform_matrix
        if (!m || m.length < 4) return null
        return <CameraFrustum key={i} matrix={m} />
      })}
    </>
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
      <Canvas camera={{ position: [10, 8, 10], fov: 50 }}>
        <ambientLight intensity={0.5} />
        <directionalLight position={[10, 10, 5]} intensity={0.8} />
        <gridHelper args={[50, 50, '#1e293b', '#334155']} />
        <axesHelper args={[3]} />
        <EgoVehicle />
        <TransformFrustums path={path} step={step} />
        <OrbitControls />
      </Canvas>
    </div>
  )
}
