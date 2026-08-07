import { useMemo, useRef } from "react";
import { Canvas, useFrame } from "@react-three/fiber";
import * as THREE from "three";

const STRAND_POINTS = 42;
const HELIX_RADIUS = 1.6;
const HELIX_HEIGHT = 6;
const TWISTS = 3;

/** Builds the same double-helix point set used for the brand's Lottie mark,
 * in 3D. `phase` (0 -> 1) morphs it into a neural network by fading in
 * cross-strand "synapse" connections and shifting color from teal to cyan —
 * same point cloud reinterpreted, not a geometry swap, which keeps the
 * "DNA becomes the network" idea literal rather than a random transition. */
function useHelixGeometry() {
  return useMemo(() => {
    const strandA = [];
    const strandB = [];
    for (let i = 0; i < STRAND_POINTS; i++) {
      const t = i / (STRAND_POINTS - 1);
      const angle = t * Math.PI * 2 * TWISTS;
      const y = (t - 0.5) * HELIX_HEIGHT;
      strandA.push(new THREE.Vector3(Math.cos(angle) * HELIX_RADIUS, y, Math.sin(angle) * HELIX_RADIUS));
      strandB.push(new THREE.Vector3(Math.cos(angle + Math.PI) * HELIX_RADIUS, y, Math.sin(angle + Math.PI) * HELIX_RADIUS));
    }
    return { strandA, strandB };
  }, []);
}

function HelixPoints({ strandA, strandB }) {
  const positions = useMemo(() => {
    const arr = new Float32Array((strandA.length + strandB.length) * 3);
    [...strandA, ...strandB].forEach((v, i) => v.toArray(arr, i * 3));
    return arr;
  }, [strandA, strandB]);

  return (
    <points>
      <bufferGeometry>
        <bufferAttribute attach="attributes-position" args={[positions, 3]} />
      </bufferGeometry>
      <pointsMaterial color="#00D4FF" size={0.055} sizeAttenuation transparent opacity={0.9} />
    </points>
  );
}

function BackboneLines({ strandA, strandB, color }) {
  const positions = useMemo(() => {
    const segs = [];
    for (let i = 0; i < strandA.length - 1; i++) segs.push(strandA[i], strandA[i + 1]);
    for (let i = 0; i < strandB.length - 1; i++) segs.push(strandB[i], strandB[i + 1]);
    // rungs every few steps, classic ladder look
    for (let i = 0; i < strandA.length; i += 4) segs.push(strandA[i], strandB[i]);
    const arr = new Float32Array(segs.length * 3);
    segs.forEach((v, i) => v.toArray(arr, i * 3));
    return arr;
  }, [strandA, strandB]);

  return (
    <lineSegments>
      <bufferGeometry>
        <bufferAttribute attach="attributes-position" args={[positions, 3]} />
      </bufferGeometry>
      <lineBasicMaterial color={color} transparent opacity={0.55} />
    </lineSegments>
  );
}

/** Cross-strand "synapse" connections, faded in via `phase` — this is what
 * reads as the neural network once it dominates over the backbone lines. */
function NetworkLines({ strandA, strandB, phase }) {
  const all = useMemo(() => [...strandA, ...strandB], [strandA, strandB]);
  const positions = useMemo(() => {
    const segs = [];
    const rand = mulberry32(7);
    for (let i = 0; i < all.length; i++) {
      const connections = 1 + Math.floor(rand() * 2);
      for (let c = 0; c < connections; c++) {
        const j = Math.floor(rand() * all.length);
        if (j !== i) segs.push(all[i], all[j]);
      }
    }
    const arr = new Float32Array(segs.length * 3);
    segs.forEach((v, i) => v.toArray(arr, i * 3));
    return arr;
  }, [all]);

  const materialRef = useRef();
  useFrame(() => {
    if (materialRef.current) materialRef.current.opacity = phase.current * 0.5;
  });

  return (
    <lineSegments>
      <bufferGeometry>
        <bufferAttribute attach="attributes-position" args={[positions, 3]} />
      </bufferGeometry>
      <lineBasicMaterial ref={materialRef} color="#7C3AED" transparent opacity={0} />
    </lineSegments>
  );
}

function mulberry32(seed) {
  return function () {
    seed |= 0;
    seed = (seed + 0x6d2b79f5) | 0;
    let t = Math.imul(seed ^ (seed >>> 15), 1 | seed);
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

function Scene({ phase }) {
  const { strandA, strandB } = useHelixGeometry();
  const groupRef = useRef();

  useFrame((_, delta) => {
    if (groupRef.current) {
      // Rotation speeds up as the network phase takes over.
      groupRef.current.rotation.y += delta * (0.15 + phase.current * 0.35);
    }
  });

  return (
    <group ref={groupRef}>
      <HelixPoints strandA={strandA} strandB={strandB} />
      <BackboneLines strandA={strandA} strandB={strandB} color="#00D4FF" />
      <NetworkLines strandA={strandA} strandB={strandB} phase={phase} />
    </group>
  );
}

/** `phase` is a ref (0..1) so the parent's timeline can drive it every frame
 * without triggering React re-renders of the whole 3D tree. */
export default function DnaNetworkScene({ phase, className }) {
  return (
    <div className={className}>
      <Canvas
        camera={{ position: [0, 0, 8], fov: 45 }}
        dpr={[1, 1.5]}
        gl={{ antialias: true, alpha: true }}
      >
        <ambientLight intensity={0.6} />
        <pointLight position={[5, 5, 5]} intensity={40} color="#00D4FF" />
        <Scene phase={phase} />
      </Canvas>
    </div>
  );
}
