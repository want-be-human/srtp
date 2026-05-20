"use client"

import React, { useState, useEffect, useMemo, useRef } from 'react'
import { Canvas, useFrame, useThree } from '@react-three/fiber'
import { OrbitControls, Html } from '@react-three/drei'
import * as THREE from 'three'
import { X } from 'lucide-react'
import { useDataTree, TreeData } from './data-tree-context'

// --- 粒子生成逻辑（从data-tree-receiver复制）---
const TRUNK_COUNT = 7000
const LEAF_COUNT = 22000
const TOTAL_PARTICLES = TRUNK_COUNT + LEAF_COUNT

interface Particle {
  position: [number, number, number];
  type: 'trunk' | 'leaf' | 'flower';
  score: number;
  baseSize: number;
  windFactor: number;
  growthOrder: number;
  colorVariation: number;
  fallPhase: number;
}

const generateParticles = (): Particle[] => {
  const pts: Particle[] = []

  const ROOT_COUNT = 2950
  const MAIN_TRUNK_COUNT = 1950
  const BRANCH_COUNT = 2400

  // 1. Winding Roots
  const rootConfigs = Array.from({length: 12}, (_, i) => ({
    baseAngle: (i / 12) * Math.PI * 2 + (Math.random() - 0.5) * 0.4,
    thickness: Math.random() * 1.0 + 0.6,
    length: Math.random() * 4.5 + 4.0,
    depthVariation: Math.random() * 2.5 - 1.0,
    waviness: Math.random() * 2.0 + 1.0
  }))

  for (let i = 0; i < ROOT_COUNT; i++) {
    const root = rootConfigs[Math.floor(Math.random() * rootConfigs.length)]
    const progress = Math.random()
    
    const r = progress * root.length
    const angle = root.baseAngle + Math.sin(progress * root.waviness * Math.PI) * 0.6
    
    const spread = (1.0 - progress) * root.thickness * 0.9
    const offsetX = (Math.random() - 0.5) * spread
    const offsetZ = (Math.random() - 0.5) * spread
    
    const x = r * Math.cos(angle) + offsetX
    const z = r * Math.sin(angle) + offsetZ
    
    const verticalSpread = (Math.random() - 0.5) * root.thickness * (1.0 - progress)
    const y = 1.5 - progress * 1.5 + Math.sin(progress * Math.PI * 2) * 0.4 + verticalSpread - root.depthVariation * progress
    
    const size = (Math.random() * 0.2 + 0.1) * root.thickness
    const growthOrder = progress * 3.0
    
    pts.push({
      position: [x, y, z],
      type: 'trunk',
      score: Math.max(0, (y + 2.0) / 8.0 * 15),
      baseSize: size,
      windFactor: 0,
      growthOrder: growthOrder + Math.random() * 1.0,
      colorVariation: Math.random(),
      fallPhase: -1.0
    })
  }

  // 2. Main Trunk
  for (let i = 0; i < MAIN_TRUNK_COUNT; i++) {
    const y = 1.0 + Math.random() * 7.0
    const baseR = 0.9 + 1.5 * Math.exp(-(y - 1.0) * 1.2)
    const angle = Math.random() * Math.PI * 2
    const r = Math.sqrt(Math.random()) * baseR
    let x = r * Math.cos(angle)
    let z = r * Math.sin(angle)

    const twist = y * 0.15
    const tx = x * Math.cos(twist) - z * Math.sin(twist)
    const tz = x * Math.sin(twist) + z * Math.cos(twist)

    const isSurface = Math.random() > 0.3
    x = isSurface ? tx : tx * Math.random()
    z = isSurface ? tz : tz * Math.random()
    
    const size = Math.random() * 0.2 + 0.1
    const growthOrder = 1.0 + (y - 1.0) * 1.2

    pts.push({
      position: [x, y, z],
      type: 'trunk',
      score: (y / 7.5) * 25,
      baseSize: size,
      windFactor: 0,
      growthOrder: growthOrder + Math.random() * 1.0,
      colorVariation: Math.random(),
      fallPhase: -1.0
    })
  }

  // Canopy Clusters
  const clusters = [
    { cx: 0, cy: 13.5, cz: 0, r: 5.5 },
    { cx: 0, cy: 9.0, cz: 0, r: 6.5 },
    { cx: 0, cy: 11.0, cz: 0, r: 5.5 },
    { cx: 5.5, cy: 8.5, cz: 3.5, r: 5.0 },
    { cx: -5.5, cy: 8.5, cz: -3.5, r: 5.0 },
    { cx: 3.5, cy: 9.0, cz: -5.5, r: 5.0 },
    { cx: -3.5, cy: 9.0, cz: 5.5, r: 5.0 },
    { cx: 7.5, cy: 7.0, cz: -2.0, r: 4.0 },
    { cx: -7.5, cy: 7.5, cz: 2.5, r: 4.0 },
    { cx: 3.0, cy: 7.0, cz: 7.5, r: 4.0 },
    { cx: -3.0, cy: 7.5, cz: -7.5, r: 4.0 },
    { cx: 4.5, cy: 12.0, cz: 3.0, r: 3.5 },
    { cx: -4.5, cy: 12.0, cz: -3.0, r: 3.5 },
    { cx: -6.0, cy: 10.0, cz: -1.5, r: 4.5 },
    { cx: 6.0, cy: 10.0, cz: 1.5, r: 4.5 },
    { cx: -2.0, cy: 11.5, cz: -5.0, r: 4.0 },
    { cx: 2.0, cy: 11.5, cz: 5.0, r: 4.0 },
    { cx: -5.0, cy: 6.0, cz: 5.0, r: 4.5 },
    { cx: 5.0, cy: 6.0, cz: -5.0, r: 4.5 },
  ]

  // 3. Branches
  const branchClusters = clusters.filter(c => Math.abs(c.cx) > 1.0 || Math.abs(c.cz) > 1.0 || c.cy > 11.0)
  for (let i = 0; i < BRANCH_COUNT; i++) {
    const cluster = branchClusters[Math.floor(Math.random() * branchClusters.length)]
    const progress = Math.random()
    
    const startY = 4.0 + Math.random() * 3.0
    const startX = Math.cos(Math.atan2(cluster.cz, cluster.cx)) * 0.7
    const startZ = Math.sin(Math.atan2(cluster.cz, cluster.cx)) * 0.7
    
    const endX = cluster.cx
    const endY = cluster.cy - cluster.r * 0.3
    const endZ = cluster.cz
    
    const curve = Math.sin(progress * Math.PI) * -1.0
    
    const baseX = startX + (endX - startX) * progress
    const baseY = startY + (endY - startY) * progress + curve
    const baseZ = startZ + (endZ - startZ) * progress
    
    const thickness = (cluster.r / 4.5) * 1.2 * (1.0 - progress * 0.5)
    const offsetX = (Math.random() - 0.5) * thickness
    const offsetY = (Math.random() - 0.5) * thickness
    const offsetZ = (Math.random() - 0.5) * thickness
    
    const x = baseX + offsetX
    const y = baseY + offsetY
    const z = baseZ + offsetZ
    
    const size = Math.random() * 0.18 + 0.1
    const growthOrder = 2.5 + progress * 3.0 + (startY - 3.5)

    pts.push({
      position: [x, y, z],
      type: 'trunk',
      score: 15 + (progress * 15),
      baseSize: size,
      windFactor: 0,
      growthOrder: growthOrder + Math.random() * 1.0,
      colorVariation: Math.random(),
      fallPhase: -1.0
    })
  }

  // 4. Leaves (Canopy)
  for (let i = 0; i < LEAF_COUNT; i++) {
    const cluster = clusters[Math.floor(Math.random() * clusters.length)]
    const u = Math.random()
    const v = Math.random()
    const theta = u * 2.0 * Math.PI
    const phi = Math.acos(2.0 * v - 1.0)
    const r = Math.pow(Math.random(), 0.55) * cluster.r

    let x = cluster.cx + r * Math.sin(phi) * Math.cos(theta)
    let y = cluster.cy + r * Math.cos(phi)
    let z = cluster.cz + r * Math.sin(phi) * Math.sin(theta)

    y = cluster.cy + (y - cluster.cy) * 0.75

    const distFromCenter = Math.sqrt(x * x + (y - 8) * (y - 8) + z * z)
    const score = 30 + ((y - 4.0) / 7.0) * 50 + (1 - distFromCenter / 12) * 20
    
    const growthOrder = 5.0 + (y - 4.0) * 0.8 + r * 0.5
    
    const lightExposure = Math.max(0, Math.min(1, (y - 4.0) / 8.0 + (distFromCenter / cluster.r) * 0.5))
    const colorVar = lightExposure * 0.7 + Math.random() * 0.3

    const isFlower = Math.random() < 0.06
    const isFalling = isFlower && Math.random() < 0.083
    const particleSize = isFlower ? (Math.random() * 0.45 + 0.25) : (Math.random() * 0.15 + 0.15)

    pts.push({
      position: [x, y, z],
      type: isFlower ? 'flower' : 'leaf',
      score: Math.min(100, Math.max(0, score)),
      baseSize: particleSize,
      windFactor: Math.random() * 0.8 + 0.2,
      growthOrder: growthOrder + Math.random() * 2.0,
      colorVariation: colorVar,
      fallPhase: isFalling ? Math.random() * 100.0 : -1.0
    })
  }

  // 降序：index 0 = 最高 score = 树冠最显眼的叶子；
  // 数据按 slot 0,1,2... 分配时，前几条记录落在视觉中心而非看不见的深根
  pts.sort((a, b) => b.score - a.score)
  return pts
}

const INITIAL_PARTICLES = generateParticles()

// --- 粒子树组件 ---
function ParticleTree({
  resetGrowth = false,
  onGrowthTimeUpdate,
  treeDataOverride,
}: {
  resetGrowth?: boolean
  onGrowthTimeUpdate?: (time: number) => void
  treeDataOverride?: Map<number, TreeData>
}) {
  const geometryRef = useRef<THREE.BufferGeometry>(null)
  const materialRef = useRef<THREE.ShaderMaterial>(null)
  const [growthStarted, setGrowthStarted] = useState(false)
  const ctx = useDataTree()
  // PK 视图传入对比对象的 treeData；不传则走 Context（数据树主页面）
  const treeData = treeDataOverride ?? ctx.treeData
  const selectedParticle = treeDataOverride ? null : ctx.selectedParticle
  const setSelectedParticle = treeDataOverride ? () => {} : ctx.setSelectedParticle
  
  const { positions, colors, sizes, windFactors, growthOrders, colorVariations, fallPhases } = useMemo(() => {
    const pos = new Float32Array(INITIAL_PARTICLES.length * 3)
    const col = new Float32Array(INITIAL_PARTICLES.length * 3)
    const siz = new Float32Array(INITIAL_PARTICLES.length)
    const wind = new Float32Array(INITIAL_PARTICLES.length)
    const growth = new Float32Array(INITIAL_PARTICLES.length)
    const colorVar = new Float32Array(INITIAL_PARTICLES.length)
    const fall = new Float32Array(INITIAL_PARTICLES.length)
    
    for (let i = 0; i < INITIAL_PARTICLES.length; i++) {
      pos[i * 3] = INITIAL_PARTICLES[i].position[0]
      pos[i * 3 + 1] = INITIAL_PARTICLES[i].position[1]
      pos[i * 3 + 2] = INITIAL_PARTICLES[i].position[2]
      wind[i] = INITIAL_PARTICLES[i].windFactor
      growth[i] = INITIAL_PARTICLES[i].growthOrder
      colorVar[i] = INITIAL_PARTICLES[i].colorVariation
      fall[i] = INITIAL_PARTICLES[i].fallPhase
    }
    return { positions: pos, colors: col, sizes: siz, windFactors: wind, growthOrders: growth, colorVariations: colorVar, fallPhases: fall }
  }, [])

  useEffect(() => {
    const timer = setTimeout(() => setGrowthStarted(true), 300)
    return () => clearTimeout(timer)
  }, [])
  
  // 当 resetGrowth 变化时，重置生长状态
  useEffect(() => {
    if (resetGrowth && materialRef.current) {
      materialRef.current.uniforms.growthTime.value = 0.0
      setGrowthStarted(false)
      const timer = setTimeout(() => setGrowthStarted(true), 300)
      return () => clearTimeout(timer)
    }
  }, [resetGrowth])

  // 当选中粒子变化时，更新其大小
  useEffect(() => {
    if (!geometryRef.current) return
    
    // 重置所有粒子大小
    for (let i = 0; i < INITIAL_PARTICLES.length; i++) {
      const baseSize = INITIAL_PARTICLES[i].baseSize
      sizes[i] = baseSize
    }
    
    // 如果有选中的粒子，将其放大
    if (selectedParticle !== null && selectedParticle < INITIAL_PARTICLES.length) {
      sizes[selectedParticle] = INITIAL_PARTICLES[selectedParticle].baseSize * 2.0
    }
    
    geometryRef.current.attributes.size.needsUpdate = true
  }, [selectedParticle, sizes])

  useFrame((state) => {
    if (materialRef.current && geometryRef.current) {
      materialRef.current.uniforms.time.value = state.clock.elapsedTime
      
      if (growthStarted) {
        const currentGrowth = materialRef.current.uniforms.growthTime.value
        // 设置生长到85%的粒子点亮（growthTime达到21.25时停止）
        if (currentGrowth < 21.25) {
          materialRef.current.uniforms.growthTime.value += 0.08
        }
        // 传递生长时间给父组件，用于相机运镜
        if (onGrowthTimeUpdate) {
          onGrowthTimeUpdate(currentGrowth)
        }
      }
      
      // 每帧更新粒子颜色和大小
      // 配色规则：
      //   trunk（树根/主干/树枝）= 时间驱动的棕色骨架，始终展示（与数据无关）
      //   leaf（树冠叶子）= 数据驱动；按 totalScore 分档 90+ 绿 / 70-89 黄 / <70 红，尺寸红>黄>绿
      //   flower（leaf 池里 6% 预分配）= 有数据时显示粉色「花朵」
      //   无数据的 leaf/flower 不显示（颜色 0 + size 收成 ~0）
      const currentGrowthTime = materialRef.current.uniforms.growthTime.value
      const trunkBase = new THREE.Color('#D2B48C')
      const trunkVariant = new THREE.Color('#DEB887')
      const flowerBase = new THREE.Color('#ffb7c5')
      const flowerVariant = new THREE.Color('#ff91a4')
      const scoreHigh = new THREE.Color('#4ADE80')  // 绿
      const scoreMid = new THREE.Color('#FACC15')   // 黄
      const scoreLow = new THREE.Color('#EF4444')   // 红
      const dimWhite = new THREE.Color('#ffffff')
      const tempColor = new THREE.Color()

      for (let i = 0; i < INITIAL_PARTICLES.length; i++) {
        const particle = INITIAL_PARTICLES[i]
        const growthState = Math.max(0, Math.min(1, (currentGrowthTime - particle.growthOrder) / 1.0))
        let size = particle.baseSize

        if (particle.type === 'trunk') {
          // 树干类：时间驱动，与 treeData 无关
          if (growthState > 0.1) {
            tempColor.copy(trunkBase).lerp(trunkVariant, particle.colorVariation)
            const growthFactor = Math.min(1.0, growthState * 1.5)
            size *= (0.8 + growthFactor * 0.5)
          } else {
            tempColor.copy(dimWhite).multiplyScalar(0.15 * growthState)
            size *= 0.5
          }
        } else {
          // leaf / flower：数据驱动
          const data = treeData.get(i)
          const hasData = data !== undefined && growthState > 0.1
          if (hasData) {
            if (particle.type === 'flower') {
              tempColor.copy(flowerBase).lerp(flowerVariant, particle.colorVariation)
              size *= 2.0
            } else {
              const score = data!.totalScore ?? data!.finalScore ?? 0
              if (score >= 90) {
                tempColor.copy(scoreHigh)
                size *= 1.5
              } else if (score >= 70) {
                tempColor.copy(scoreMid)
                size *= 2.5
              } else {
                tempColor.copy(scoreLow)
                size *= 3.5
              }
            }
            if (i === selectedParticle) size *= 2.0
          } else {
            // 无数据的 leaf/flower 隐去
            tempColor.setRGB(0, 0, 0)
            size *= 0.01
          }
        }

        colors[i * 3] = tempColor.r
        colors[i * 3 + 1] = tempColor.g
        colors[i * 3 + 2] = tempColor.b
        sizes[i] = size
      }
      
      geometryRef.current.attributes.color.needsUpdate = true
      geometryRef.current.attributes.size.needsUpdate = true
    }
  })

  const shaderMaterial = useMemo(() => new THREE.ShaderMaterial({
    uniforms: {
      time: { value: 0 },
      growthTime: { value: 0.0 }
    },
    vertexShader: `
      uniform float time;
      uniform float growthTime;
      attribute vec3 color;
      attribute float size;
      attribute float windFactor;
      attribute float growthOrder;
      attribute float colorVariation;
      attribute float fallPhase;
      
      varying vec3 vColor;
      varying float vGrowth;
      
      void main() {
        vColor = color;
        vec3 pos = position;
        float fallScale = 1.0;
        
        vGrowth = clamp(growthTime - growthOrder, 0.0, 1.0);
        
        if (vGrowth > 0.0) {
          float isLeaf = step(0.01, windFactor);
          float heightFactor = smoothstep(0.0, 12.0, pos.y);
          
          float trunkSwayX = sin(time * 0.8 + pos.y * 0.2) * heightFactor * 0.08;
          float trunkSwayZ = cos(time * 0.9 + pos.y * 0.2) * heightFactor * 0.08;

          if (fallPhase >= 0.0) {
            float speed = 0.5 + colorVariation * 0.4;
            float dropDist = position.y + 1.0;
            float fallDuration = dropDist / speed;
            float waitDuration = 8.0 + colorVariation * 12.0;
            float totalCycle = fallDuration + waitDuration;
            float localTime = mod(time + fallPhase, totalCycle);
            
            if (localTime < waitDuration) {
              float waitPct = localTime / waitDuration;
              if (waitPct < 0.05) fallScale = waitPct / 0.05;
              
              float leafPhase = colorVariation * 6.28 + pos.x + pos.y;
              pos.x += trunkSwayX + sin(time * 1.5 + leafPhase) * windFactor * 0.12;
              pos.y += cos(time * 1.8 + leafPhase) * windFactor * 0.06;
              pos.z += trunkSwayZ + sin(time * 1.3 + leafPhase) * windFactor * 0.12;
            } else {
              float fallTime = localTime - waitDuration;
              pos.y -= fallTime * speed;
              pos.x += sin(fallTime * 1.5 + fallPhase) * 1.5 * (fallTime / fallDuration);
              pos.z += cos(fallTime * 1.2 + fallPhase) * 1.5 * (fallTime / fallDuration);
              
              float lifePct = fallTime / fallDuration;
              if (lifePct > 0.8) fallScale = (1.0 - lifePct) / 0.2;
            }
          } else {
            float leafPhase = colorVariation * 6.28 + pos.x + pos.y;
            float leafSwayX = sin(time * 1.5 + leafPhase) * windFactor * 0.12;
            float leafSwayY = cos(time * 1.8 + leafPhase) * windFactor * 0.06;
            float leafSwayZ = sin(time * 1.3 + leafPhase) * windFactor * 0.12;

            pos.x += trunkSwayX + leafSwayX * isLeaf;
            pos.y += leafSwayY * isLeaf;
            pos.z += trunkSwayZ + leafSwayZ * isLeaf;
          }
        }
        
        vec4 mvPosition = modelViewMatrix * vec4(pos, 1.0);
        
        float pop = smoothstep(0.0, 0.2, vGrowth) * (1.0 + 0.8 * smoothstep(0.2, 0.0, vGrowth));
        
        gl_PointSize = size * pop * fallScale * (250.0 / -mvPosition.z);
        gl_Position = projectionMatrix * mvPosition;
      }
    `,
    fragmentShader: `
      varying vec3 vColor;
      varying float vGrowth;
      
      void main() {
        if (vGrowth <= 0.0) discard;
        
        vec2 xy = gl_PointCoord.xy - vec2(0.5);
        float ll = length(xy);
        if (ll > 0.5) discard;
        
        float alpha = smoothstep(0.5, 0.1, ll) * smoothstep(0.0, 0.2, vGrowth);
        gl_FragColor = vec4(vColor, alpha);
      }
    `,
    transparent: true,
    depthWrite: false,
    blending: THREE.AdditiveBlending
  }), [])

  return (
    <points 
      onClick={(e: any) => {
        e.stopPropagation()
        if (treeData.has(e.index!)) {
          setSelectedParticle(e.index!)
        }
      }}
      onPointerMissed={() => setSelectedParticle(null)}
    >
      <bufferGeometry ref={geometryRef}>
        <bufferAttribute attach="attributes-position" count={INITIAL_PARTICLES.length} array={positions} itemSize={3} />
        <bufferAttribute attach="attributes-color" count={INITIAL_PARTICLES.length} array={colors} itemSize={3} />
        <bufferAttribute attach="attributes-size" count={INITIAL_PARTICLES.length} array={sizes} itemSize={1} />
        <bufferAttribute attach="attributes-windFactor" count={INITIAL_PARTICLES.length} array={windFactors} itemSize={1} />
        <bufferAttribute attach="attributes-growthOrder" count={INITIAL_PARTICLES.length} array={growthOrders} itemSize={1} />
        <bufferAttribute attach="attributes-colorVariation" count={INITIAL_PARTICLES.length} array={colorVariations} itemSize={1} />
        <bufferAttribute attach="attributes-fallPhase" count={INITIAL_PARTICLES.length} array={fallPhases} itemSize={1} />
      </bufferGeometry>
      <primitive object={shaderMaterial} ref={materialRef} attach="material" />
      
      {selectedParticle !== null && treeData.has(selectedParticle) && (
        <Html position={INITIAL_PARTICLES[selectedParticle].position} center zIndexRange={[100, 0]}>
          <div className="relative">
            <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-10 h-10 rounded-full border-2 border-white animate-ping opacity-80 pointer-events-none"></div>
            
            <div className="absolute bottom-8 left-1/2 -translate-x-1/2 p-4 rounded-xl shadow-2xl text-xs w-64 bg-black/80 text-white border border-gray-600 backdrop-blur-xl">
              <button 
                onClick={(e) => { e.stopPropagation(); setSelectedParticle(null); }}
                className="absolute top-2 right-2 opacity-50 hover:opacity-100"
              >
                <X size={14} />
              </button>
              <div className="flex items-center gap-2 font-bold mb-3 border-b pb-2 border-gray-500/30">
                <Database size={14} className="text-blue-500" />
                <span>Record ID: {treeData.get(selectedParticle)!.id}</span>
              </div>
              <div className="space-y-1.5">
                <div className="flex justify-between"><span className="opacity-60">Defect Type</span> <span className="font-medium">{treeData.get(selectedParticle)!.defectType}</span></div>
                <div className="flex justify-between"><span className="opacity-60">Total Score</span> <span className="font-medium">{treeData.get(selectedParticle)!.totalScore.toFixed(2)}</span></div>
                <div className="flex justify-between"><span className="opacity-60">Defect Score</span> <span className="font-medium">{treeData.get(selectedParticle)!.defectScore.toFixed(2)}</span></div>
                <div className="flex justify-between"><span className="opacity-60">Width Score</span> <span className="font-medium">{treeData.get(selectedParticle)!.widthScore.toFixed(2)}</span></div>
                <div className="flex justify-between"><span className="opacity-60">Smoothness</span> <span className="font-medium">{treeData.get(selectedParticle)!.smoothnessScore.toFixed(2)}</span></div>
                <div className="flex justify-between pt-2 mt-2 border-t border-gray-500/30">
                  <span className="opacity-80 font-bold">Calculated Rating</span> 
                  <span className="font-bold text-blue-500 text-sm">{treeData.get(selectedParticle)!.finalScore.toFixed(2)}</span>
                </div>
              </div>
              <div className="mt-3 text-[10px] opacity-40 text-center font-mono">
                {new Date(treeData.get(selectedParticle)!.time).toLocaleString()}
              </div>
            </div>
          </div>
        </Html>
      )}
    </points>
  )
}

// --- 相机运镜组件（优化版）---
function CameraRig({ growthTime }: { growthTime: number }) {
  const { camera } = useThree()
  
  useFrame(() => {
    // 根据生长时间自动调整相机位置，实现运镜效果
    const growthProgress = Math.min(1.0, growthTime / 21.25) // 21.25是85%生长完成的时间
    
    // 使用缓动函数让运镜更自然
    const easeOutCubic = (t: number) => 1 - Math.pow(1 - t, 3)
    const easedProgress = easeOutCubic(growthProgress)
    
    // 初始位置：[0, 5, 14] - 较近，聚焦细节
    // 最终位置：[0, 10, 30] - 更高更远，看到完整树的全貌
    const targetY = 5 + easedProgress * 5  // 从5到10（上升5单位）
    const targetZ = 14 + easedProgress * 16 // 从14到30（远离16单位）
    
    // 更平滑的插值
    camera.position.y += (targetY - camera.position.y) * 0.015
    camera.position.z += (targetZ - camera.position.z) * 0.015
    
    // 相机看向点：从树的中部到上部
    const lookAtY = 6 + easedProgress * 4 // 从6到10
    camera.lookAt(0, lookAtY, 0)
    
    // 根据生长进度调整FOV，实现"拉远镜头"效果
    // 开始时较窄（聚焦细节），结束时较宽（看到全貌）
    camera.fov = 50 + easedProgress * 20 // 从50到70（视野更宽）
    camera.updateProjectionMatrix()
    
    // 添加轻微的相机旋转，增加电影感
    if (growthProgress > 0.3) {
      const rotationAmount = (growthProgress - 0.3) * 0.1
      camera.position.x = Math.sin(growthTime * 0.01) * rotationAmount
    }
  })
  
  return null
}

// --- 主数据树查看器组件 ---
export function DataTreeViewer({
  theme = 'dark',
  resetGrowth = false,
  treeData: treeDataOverride,
}: {
  theme?: 'dark' | 'light'
  resetGrowth?: boolean
  /** PK 模式下显式传入另一个学生的 treeData；不传则用 Context 的当前学生切片 */
  treeData?: Map<number, TreeData>
}) {
  const cameraRef = useRef<any>(null)
  const [growthTime, setGrowthTime] = useState(0)

  return (
    <div className={`w-full h-full relative overflow-hidden ${theme === 'dark' ? 'bg-[#050505]' : 'bg-gray-100'}`}>
      {/* 3D Canvas - 完全填充 */}
      <Canvas 
        camera={{ position: [0, 5, 14], fov: 50 }}
        onCreated={({ camera, raycaster }: any) => { 
          cameraRef.current = camera
          ;(raycaster.params.Points as any).threshold = 0.5
        }}
        className="absolute inset-0"
        style={{ width: '100%', height: '100%' }}
      >
        <CameraRig growthTime={growthTime} />
        <OrbitControls 
          enablePan={true} 
          enableZoom={true} 
          enableRotate={true}
          target={[0, 6, 0]}
          maxDistance={45}  // 增加最大距离，让用户可以拉得更远
          minDistance={5}   // 增加最小距离，避免太近
          autoRotate={false}
          rotateSpeed={0.8} // 稍微降低旋转速度，更平滑
          zoomSpeed={0.8}   // 稍微降低缩放速度
        />
        <group scale={[1.8, 1.8, 1.8]} position={[0, -4, 0]}>
          <ParticleTree
            resetGrowth={resetGrowth}
            onGrowthTimeUpdate={setGrowthTime}
            treeDataOverride={treeDataOverride}
          />
        </group>
      </Canvas>



      <style dangerouslySetInnerHTML={{__html: `
        .custom-scrollbar::-webkit-scrollbar { width: 6px; }
        .custom-scrollbar::-webkit-scrollbar-track { background: transparent; }
        .custom-scrollbar::-webkit-scrollbar-thumb { background: rgba(150, 150, 150, 0.3); border-radius: 10px; }
        .custom-scrollbar::-webkit-scrollbar-thumb:hover { background: rgba(150, 150, 150, 0.5); }
      `}} />
    </div>
  )
}