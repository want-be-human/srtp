"use client"

import { useState, useRef, useEffect, useCallback } from 'react'
import { Canvas, useFrame, useThree } from '@react-three/fiber'
import { OrbitControls } from '@react-three/drei'
import * as THREE from 'three'
import { RotateCw, ZoomIn, ZoomOut, Maximize, Camera, Play, Radio } from 'lucide-react'

interface DetectionScores {
  totalScore: number
  smoothness: number
  width: number
  defectType: number
  defectTypeName?: string
}

interface GaussianSplatViewerProps {
  modelUrl: string
  detectionScores?: DetectionScores | null
  // mini：控制中心迷你预览框用，跳过 idle/processing 直接 reveal，无工具栏/HUD/帮助，
  // OrbitControls 禁鼠标交互只留 autoRotate
  mini?: boolean
}

const SH_C0 = 0.28209479177387814

const VERTEX_SHADER = `
  varying vec3 vColor;
  uniform float uSize;
  void main() {
    vec4 mv = modelViewMatrix * vec4(position, 1.0);
    gl_PointSize = uSize * (200.0 / -mv.z);
    gl_PointSize = clamp(gl_PointSize, 0.3, 30.0);
    gl_Position = projectionMatrix * mv;
    vColor = color;
  }
`

const FRAGMENT_SHADER = `
  varying vec3 vColor;
  void main() {
    float d = length(gl_PointCoord - 0.5) * 2.0;
    if (d > 1.0) discard;
    float a = 1.0 - d * d;
    gl_FragColor = vec4(vColor, a * 0.6);
  }
`

const REVEAL_BATCH_COUNT = 20
const REVEAL_BATCH_INTERVAL = 100

const PIPELINE_STAGES = [
  {
    label: '正在从 3DGS 摄像头采集环绕视频',
    duration: 4000,
    getDetail: (elapsed: number, total: number) => {
      const angle = Math.min(24, Math.floor(elapsed / total * 24) + 1)
      return `角度 ${angle} / 24`
    },
  },
  {
    label: '提取多角度图像序列',
    duration: 2000,
    getDetail: (elapsed: number, total: number) => {
      const frame = Math.min(24, Math.floor(elapsed / total * 24) + 1)
      return `${frame} / 24 帧`
    },
  },
  {
    label: 'COLMAP 运动恢复结构重建中...',
    duration: 3000,
    getDetail: () => '',
  },
  {
    label: '3D 高斯泼溅训练',
    duration: 4000,
    getDetail: (elapsed: number, total: number) => {
      const iter = Math.min(7000, Math.floor(elapsed / total * 7000))
      return `迭代 ${iter.toLocaleString()} / 7,000`
    },
  },
  {
    label: '优化模型细节',
    duration: 2000,
    getDetail: () => '',
  },
]

type ViewState = 'idle' | 'processing' | 'revealing' | 'ready' | 'error'

interface LoadState {
  stage: 'idle' | 'fetching' | 'parsing' | 'ready' | 'error'
  message: string
  progress: number
  count: number
  splatCenter: [number, number, number]
}

interface ParsedData {
  positions: Float32Array
  colors: Float32Array
  count: number
  center: [number, number, number]
}

// 切走再回不要重新 fetch + parse 这 1.99MB PLY，太磨叽
const _splatCache = new Map<string, ParsedData>()

// viewer unmount 时 React state 全丢，重新挂回去会跳回 idle 让用户再点一次"开始"。
// 这里按 (mini, url) 把运行时 state 留住，重挂时续上。mini 和 detection 分开存，
// 不然 dashboard 看完 mini 的 ready 会让 detection 第一次进来跳过 pipeline 动画。
interface ViewerStateSnapshot {
  viewState: ViewState
  reveal: boolean
  autoRotate: boolean
  splatCount: number
  totalSplats: number
  pipelineStage: number
  pipelineProgress: number
}
const _viewerStateCache = new Map<string, ViewerStateSnapshot>()
const cacheKey = (mini: boolean, modelUrl: string) => `${mini ? 'mini' : 'full'}:${modelUrl}`

function SplatRenderer({
  modelUrl,
  reveal,
  mini = false,
  onRevealProgress,
  onRevealComplete,
  onLoadUpdate,
}: {
  modelUrl: string
  reveal: boolean
  mini?: boolean
  onRevealProgress?: (ratio: number, revealed: number) => void
  onRevealComplete?: () => void
  onLoadUpdate: (state: LoadState) => void
}) {
  const { scene, camera } = useThree()
  const dataRef = useRef<ParsedData | null>(null)
  const loadedRef = useRef(false)
  const batchedPointsRef = useRef<THREE.Points[]>([])
  const sharedMatRef = useRef<THREE.ShaderMaterial | null>(null)
  const centerRef = useRef(new THREE.Vector3())
  const revealRequestedRef = useRef(false)
  const revealingRef = useRef(false)
  const revealIntervalRef = useRef<ReturnType<typeof setInterval> | null>(null)

  useEffect(() => {
    let cancelled = false
    if (loadedRef.current) return

    async function load() {
      const cached = _splatCache.get(modelUrl)
      if (cached) {
        centerRef.current.set(cached.center[0], cached.center[1], cached.center[2])
        dataRef.current = cached
        loadedRef.current = true
        onLoadUpdate({
          stage: 'ready',
          message: '就绪',
          progress: 100,
          count: cached.count,
          splatCenter: cached.center,
        })
        // 这里不能用 revealRequestedRef.current，那个 ref 由另一个 useEffect 写，
        // 跟 load 这个 useEffect 是并行 schedule，第一次 mount 时基本还没赋值。
        // 直接看 prop reveal 才能正确触发 instant
        if (reveal && !revealingRef.current) {
          startReveal(true)
        }
        return
      }

      onLoadUpdate({ stage: 'fetching', message: '准备模型数据...', progress: 0, count: 0, splatCenter: [0, 0, 0] })

      try {
        const resp = await fetch(modelUrl)
        if (!resp.ok) throw new Error(`HTTP ${resp.status}`)

        const contentLength = resp.headers.get('content-length')
        const total = contentLength ? parseInt(contentLength) : 0

        const reader = resp.body!.getReader()
        const chunks: Uint8Array[] = []
        let received = 0

        while (true) {
          const { done, value } = await reader.read()
          if (done) break
          if (cancelled) return
          chunks.push(value)
          received += value.length
          if (total > 0) {
            onLoadUpdate({ stage: 'fetching', message: `加载中... ${Math.round(received / total * 100)}%`, progress: Math.round(received / total * 50), count: 0, splatCenter: [0, 0, 0] })
          }
        }

        const buf = await new Blob(chunks as BlobPart[]).arrayBuffer()
        if (cancelled) return

        onLoadUpdate({ stage: 'parsing', message: '解析模型数据...', progress: 55, count: 0, splatCenter: [0, 0, 0] })

        const raw = new Uint8Array(buf)
        const headerEndMarker = new TextEncoder().encode('end_header\n')
        let headerEnd = 0
        for (let i = 0; i < raw.length - headerEndMarker.length; i++) {
          let match = true
          for (let j = 0; j < headerEndMarker.length; j++) {
            if (raw[i + j] !== headerEndMarker[j]) { match = false; break }
          }
          if (match) { headerEnd = i + headerEndMarker.length; break }
        }

        const floats = new Float32Array(buf.slice(headerEnd))
        const vertexFloats = 62
        const totalVerts = Math.floor(floats.length / vertexFloats)
        const count = totalVerts

        if (cancelled) return

        const pos = new Float32Array(count * 3)
        const col = new Float32Array(count * 3)
        let sumX = 0, sumY = 0, sumZ = 0

        for (let i = 0; i < count; i++) {
          const o = i * vertexFloats
          const x = floats[o], y = floats[o + 1], z = floats[o + 2]
          pos[i * 3] = x; pos[i * 3 + 1] = y; pos[i * 3 + 2] = z
          col[i * 3]     = Math.min(1, Math.max(0, 0.5 + SH_C0 * floats[o + 6]))
          col[i * 3 + 1] = Math.min(1, Math.max(0, 0.5 + SH_C0 * floats[o + 7]))
          col[i * 3 + 2] = Math.min(1, Math.max(0, 0.5 + SH_C0 * floats[o + 8]))
          sumX += x; sumY += y; sumZ += z
        }

        if (cancelled) return

        const cx = sumX / count, cy = sumY / count, cz = sumZ / count
        centerRef.current.set(cx, cy, cz)
        const parsed: ParsedData = { positions: pos, colors: col, count, center: [cx, cy, cz] }
        dataRef.current = parsed
        loadedRef.current = true
        _splatCache.set(modelUrl, parsed)

        onLoadUpdate({ stage: 'ready', message: '就绪', progress: 100, count, splatCenter: [cx, cy, cz] })

        if (revealRequestedRef.current && !revealingRef.current) {
          startReveal()
        }
      } catch (err: any) {
        if (!cancelled) {
          onLoadUpdate({ stage: 'error', message: `加载失败: ${err.message}`, progress: 0, count: 0, splatCenter: [0, 0, 0] })
        }
      }
    }

    load()

    return () => {
      cancelled = true
    }
  }, [modelUrl])

  function startReveal(instant = false) {
    const data = dataRef.current
    if (!data || revealingRef.current) return
    revealingRef.current = true

    const { positions, colors, count } = data
    const batchSize = Math.ceil(count / REVEAL_BATCH_COUNT)

    const mat = new THREE.ShaderMaterial({
      vertexShader: VERTEX_SHADER,
      fragmentShader: FRAGMENT_SHADER,
      // mini 预览框小，默认点大些让密度看着够；全屏模式保留细颗粒
      uniforms: { uSize: { value: mini ? 0.15 : 0.08 } },
      vertexColors: true,
      transparent: true,
      depthWrite: false,
    })
    sharedMatRef.current = mat

    camera.position.set(data.center[0] + 8, data.center[1] + 3, data.center[2] + 6)
    camera.lookAt(data.center[0], data.center[1], data.center[2])

    if (instant) {
      // 已经看过一次了，一口气把全部点摆出来，不再跑两秒的渐进
      const geom = new THREE.BufferGeometry()
      geom.setAttribute('position', new THREE.BufferAttribute(positions, 3))
      geom.setAttribute('color', new THREE.BufferAttribute(colors, 3))
      const points = new THREE.Points(geom, mat)
      scene.add(points)
      batchedPointsRef.current.push(points)
      onRevealProgress?.(1.0, count)
      onRevealComplete?.()
      return
    }

    let batchIndex = 0
    let totalRevealed = 0

    revealIntervalRef.current = setInterval(() => {
      if (batchIndex >= REVEAL_BATCH_COUNT) {
        if (revealIntervalRef.current) clearInterval(revealIntervalRef.current)
        onRevealComplete?.()
        return
      }

      const start = batchIndex * batchSize
      const end = Math.min(start + batchSize, count)
      const batchCount = end - start

      const batchPos = new Float32Array(batchCount * 3)
      const batchCol = new Float32Array(batchCount * 3)
      for (let i = 0; i < batchCount; i++) {
        const src = start + i
        batchPos[i * 3] = positions[src * 3]
        batchPos[i * 3 + 1] = positions[src * 3 + 1]
        batchPos[i * 3 + 2] = positions[src * 3 + 2]
        batchCol[i * 3] = colors[src * 3]
        batchCol[i * 3 + 1] = colors[src * 3 + 1]
        batchCol[i * 3 + 2] = colors[src * 3 + 2]
      }

      const geom = new THREE.BufferGeometry()
      geom.setAttribute('position', new THREE.BufferAttribute(batchPos, 3))
      geom.setAttribute('color', new THREE.BufferAttribute(batchCol, 3))

      const points = new THREE.Points(geom, mat)
      scene.add(points)
      batchedPointsRef.current.push(points)

      batchIndex++
      totalRevealed += batchCount
      onRevealProgress?.(batchIndex / REVEAL_BATCH_COUNT, totalRevealed)
    }, REVEAL_BATCH_INTERVAL)
  }

  useEffect(() => {
    revealRequestedRef.current = reveal
    if (reveal && dataRef.current && !revealingRef.current) {
      startReveal()
    }
  }, [reveal])

  useEffect(() => {
    const controls = {
      resetView: () => {
        const c = centerRef.current
        camera.position.set(c.x + 8, c.y + 3, c.z + 6)
        camera.lookAt(c)
        if (sharedMatRef.current) sharedMatRef.current.uniforms.uSize.value = 0.08
      },
      topView: () => {
        const c = centerRef.current
        camera.position.set(c.x, c.y + 15, c.z)
        camera.lookAt(c)
      },
      frontView: () => {
        const c = centerRef.current
        camera.position.set(c.x, c.y, c.z + 8)
        camera.lookAt(c)
      },
      sideView: () => {
        const c = centerRef.current
        camera.position.set(c.x + 8, c.y, c.z)
        camera.lookAt(c)
      },
      changeSize: (factor: number) => {
        if (sharedMatRef.current) {
          const cur = sharedMatRef.current.uniforms.uSize.value
          sharedMatRef.current.uniforms.uSize.value = Math.max(0.005, Math.min(1, cur * factor))
        }
      },
    }
    ;(window as any).__splatControls = controls
    return () => { delete (window as any).__splatControls }
  }, [])

  useFrame(() => {
    if (sharedMatRef.current) {
      const c = camera.position
      ;(window as any).__splatCamera = {
        x: c.x.toFixed(1), y: c.y.toFixed(1), z: c.z.toFixed(1),
        dist: centerRef.current.distanceTo(c).toFixed(1),
        size: sharedMatRef.current.uniforms.uSize.value.toFixed(3)
      }
    }
  })

  useEffect(() => {
    return () => {
      if (revealIntervalRef.current) clearInterval(revealIntervalRef.current)
      batchedPointsRef.current.forEach(p => {
        p.geometry.dispose()
        scene.remove(p)
      })
      batchedPointsRef.current = []
      sharedMatRef.current?.dispose()
      sharedMatRef.current = null
    }
  }, [])

  return null
}

export function GaussianSplatViewer({ modelUrl, detectionScores, mini = false }: GaussianSplatViewerProps) {
  const stateCacheKey = cacheKey(mini, modelUrl)
  const snap = _viewerStateCache.get(stateCacheKey)
  // 之前在 processing 或 revealing 切走，那俩 timer 已经死了没法接着跑。干脆当
  // 完成态续上：让 load 命中 PLY cache 后一次 instant reveal，用户切回看到的
  // 就是完整模型，不必从头再走一遍 pipeline + 渐进。idle / error 不值得续。
  let resumable: ViewerStateSnapshot | undefined
  if (snap && snap.viewState !== 'idle' && snap.viewState !== 'error') {
    resumable = snap.viewState === 'ready'
      ? snap
      : { ...snap, viewState: 'ready', reveal: true, splatCount: snap.totalSplats }
  }
  const [viewState, setViewState] = useState<ViewState>(resumable?.viewState ?? (mini ? 'revealing' : 'idle'))
  const [pipelineStage, setPipelineStage] = useState(resumable?.pipelineStage ?? -1)
  const [pipelineDetail, setPipelineDetail] = useState('')
  const [pipelineProgress, setPipelineProgress] = useState(resumable?.pipelineProgress ?? 0)
  const [splatCount, setSplatCount] = useState(resumable?.splatCount ?? 0)
  const [totalSplats, setTotalSplats] = useState(resumable?.totalSplats ?? 0)
  const [reveal, setReveal] = useState(resumable?.reveal ?? mini)
  const [autoRotate, setAutoRotate] = useState(resumable?.autoRotate ?? mini)
  const [hud, setHud] = useState({ x: '0', y: '0', z: '0', dist: '0', size: '0.080' })
  const pipelineTimerRef = useRef<ReturnType<typeof setInterval> | null>(null)

  useEffect(() => {
    _viewerStateCache.set(stateCacheKey, {
      viewState, reveal, autoRotate, splatCount, totalSplats, pipelineStage, pipelineProgress,
    })
  }, [stateCacheKey, viewState, reveal, autoRotate, splatCount, totalSplats, pipelineStage, pipelineProgress])

  useEffect(() => {
    // mini 模式不渲染 HUD，500ms 轮询 + setHud 重渲一律省掉
    if (mini) return
    const interval = setInterval(() => {
      const cam = (window as any).__splatCamera
      if (cam) setHud(cam)
    }, 500)
    return () => clearInterval(interval)
  }, [mini])

  const handleStart = useCallback(() => {
    setViewState('processing')
    if (pipelineTimerRef.current) clearInterval(pipelineTimerRef.current)

    const totalDuration = PIPELINE_STAGES.reduce((sum, s) => sum + s.duration, 0)
    const startTime = Date.now()

    pipelineTimerRef.current = setInterval(() => {
      const elapsed = Date.now() - startTime
      const overallProgress = Math.min(100, Math.round(elapsed / totalDuration * 100))
      setPipelineProgress(overallProgress)

      let cumDuration = 0
      let currentStage = 0
      for (let i = 0; i < PIPELINE_STAGES.length; i++) {
        cumDuration += PIPELINE_STAGES[i].duration
        if (elapsed < cumDuration) {
          currentStage = i
          break
        }
        if (i === PIPELINE_STAGES.length - 1) currentStage = i
      }

      setPipelineStage(currentStage)

      const stageStart = currentStage === 0 ? 0 : PIPELINE_STAGES.slice(0, currentStage).reduce((s, st) => s + st.duration, 0)
      const stageElapsed = elapsed - stageStart
      const stage = PIPELINE_STAGES[currentStage]
      setPipelineDetail(stage.getDetail(stageElapsed, stage.duration))

      if (overallProgress >= 100) {
        if (pipelineTimerRef.current) clearInterval(pipelineTimerRef.current)
        setViewState('revealing')
        setReveal(true)
      }
    }, 50)
  }, [])

  const handleRevealProgress = useCallback((_ratio: number, revealed: number) => {
    setSplatCount(revealed)
  }, [])

  const handleRevealComplete = useCallback(() => {
    setViewState('ready')
  }, [])

  const handleLoadUpdate = useCallback((state: LoadState) => {
    if (state.count > 0) {
      setTotalSplats(state.count)
    }
  }, [])

  const handleReset = () => (window as any).__splatControls?.resetView()
  const handleTop = () => (window as any).__splatControls?.topView()
  const handleFront = () => (window as any).__splatControls?.frontView()
  const handleSide = () => (window as any).__splatControls?.sideView()
  const handleZoomIn = () => (window as any).__splatControls?.changeSize(1.1)
  const handleZoomOut = () => (window as any).__splatControls?.changeSize(0.9)

  return (
    <div className="relative w-full h-full bg-[#0a0a10] rounded-lg overflow-hidden">
      <Canvas
        camera={{ position: [8, 3, 6], fov: 60, near: 0.01, far: 300 }}
        gl={{ antialias: false, powerPreference: 'high-performance' }}
        onCreated={({ raycaster }) => { (raycaster.params.Points as any).threshold = 0.5 }}
      >
        <SplatRenderer
          modelUrl={modelUrl}
          reveal={reveal}
          mini={mini}
          onRevealProgress={handleRevealProgress}
          onRevealComplete={handleRevealComplete}
          onLoadUpdate={handleLoadUpdate}
        />
        <OrbitControls
          enablePan={!mini}
          enableZoom={!mini}
          enableRotate={!mini}
          autoRotate={autoRotate}
          autoRotateSpeed={mini ? 0.4 : 0.8}
          minDistance={0.3}
          maxDistance={80}
        />
      </Canvas>

      {/* ── Idle State ── */}
      {viewState === 'idle' && (
        <div className="absolute inset-0 z-50 flex flex-col items-center justify-center bg-gradient-to-b from-black/70 via-black/60 to-black/80">
          <div className="text-center space-y-8">
            {/* Radar icon */}
            <div className="relative mx-auto w-24 h-24">
              <div className="absolute inset-0 rounded-full border border-blue-500/20" />
              <div className="absolute inset-2 rounded-full border border-blue-400/15" />
              <div className="absolute inset-4 rounded-full border border-blue-300/10" />
              <div className="absolute inset-0 flex items-center justify-center animate-pulse">
                <Radio className="w-8 h-8 text-blue-400" />
              </div>
              <div className="absolute top-0 left-1/2 -translate-x-1/2 w-1 h-1 bg-blue-400 rounded-full animate-ping" />
            </div>

            <div>
              <h3 className="text-xl font-bold text-white mb-2">3D 高斯泼溅重构</h3>
              <p className="text-sm text-gray-400 max-w-xs">
                环绕采集焊板视频，系统自动完成运动恢复结构与三维高斯重建，实时展示焊板立体形貌
              </p>
            </div>

            <button
              onClick={handleStart}
              className="group relative inline-flex items-center gap-2.5 px-8 py-3.5 bg-blue-600 hover:bg-blue-500 text-white rounded-xl font-medium text-sm transition-all hover:shadow-lg hover:shadow-blue-500/25 active:scale-95"
            >
              <span className="absolute inset-0 rounded-xl bg-blue-400/20 blur-xl group-hover:bg-blue-400/30 transition-all" />
              <span className="relative flex items-center gap-2.5">
                <Play className="w-4 h-4" />
                开始三维重建
              </span>
            </button>
          </div>
        </div>
      )}

      {/* ── Processing State ── */}
      {viewState === 'processing' && (
        <div className="absolute inset-0 z-50 flex flex-col items-center justify-center bg-black/85">
          <div className="w-80 space-y-8">
            <div className="text-center space-y-2">
              <p className="text-white font-semibold text-sm">
                {pipelineStage >= 0 ? PIPELINE_STAGES[pipelineStage].label : '初始化重建管线...'}
              </p>
              {pipelineDetail && (
                <p className="text-blue-400 text-xs font-mono tracking-wide">{pipelineDetail}</p>
              )}
            </div>

            <div className="space-y-2">
              <div className="w-full h-2.5 bg-slate-700/80 rounded-full overflow-hidden">
                <div
                  className="h-full bg-gradient-to-r from-blue-600 via-purple-500 to-cyan-400 transition-all duration-200 rounded-full"
                  style={{ width: `${pipelineProgress}%` }}
                />
              </div>
              <div className="flex justify-between text-[11px] text-gray-600">
                <span>3D 高斯泼溅重建</span>
                <span className="font-mono">{pipelineProgress}%</span>
              </div>
            </div>

            {/* Stage dots */}
            <div className="flex justify-center gap-2">
              {PIPELINE_STAGES.map((_, i) => (
                <div
                  key={i}
                  className={`w-1.5 h-1.5 rounded-full transition-all duration-300 ${
                    i < pipelineStage
                      ? 'bg-cyan-400'
                      : i === pipelineStage
                      ? 'bg-blue-400 animate-pulse'
                      : 'bg-slate-700'
                  }`}
                />
              ))}
            </div>
          </div>
        </div>
      )}

      {/* ── Revealing State ── */}
      {viewState === 'revealing' && !mini && (
        <div className="absolute bottom-8 left-1/2 -translate-x-1/2 z-40">
          <div className="bg-black/75 backdrop-blur px-5 py-3 rounded-xl text-center border border-slate-700/50">
            <p className="text-white text-xs font-medium">
              渲染高斯点: <span className="text-blue-400 font-mono">{splatCount.toLocaleString()}</span>
              <span className="text-gray-500"> / {totalSplats.toLocaleString() || '...'}</span>
            </p>
            <div className="w-48 h-1.5 bg-slate-700/80 rounded-full overflow-hidden mt-2">
              <div
                className="h-full bg-gradient-to-r from-blue-400 to-cyan-300 transition-all duration-100 rounded-full"
                style={{ width: `${totalSplats > 0 ? Math.round(splatCount / totalSplats * 100) : 0}%` }}
              />
            </div>
          </div>
        </div>
      )}

      {/* ── Ready: Detection Scores ── */}
      {viewState === 'ready' && detectionScores && !mini && (
        <div className="absolute top-3 left-3 z-40 bg-black/70 text-white px-3 py-2 rounded-lg text-xs pointer-events-none">
          <div className="flex items-center gap-2 mb-1">
            <Camera className="w-3 h-3 text-blue-400" />
            <span className="font-bold">检测结果</span>
          </div>
          <div className="space-y-0.5">
            <div>总分: <span className="text-green-400 font-bold">{detectionScores.totalScore.toFixed(1)}</span></div>
            <div>光滑度: {detectionScores.smoothness} | 宽度: {detectionScores.width} | 缺陷: {detectionScores.defectType}</div>
            {detectionScores.defectTypeName && (
              <div>类型: <span className="text-orange-300">{detectionScores.defectTypeName}</span></div>
            )}
          </div>
        </div>
      )}

      {/* ── Toolbar ── */}
      {(viewState === 'revealing' || viewState === 'ready') && !mini && (
        <div className="absolute bottom-4 left-1/2 -translate-x-1/2 z-40 flex gap-1 flex-wrap justify-center">
          <ToolBtn onClick={handleReset} title="重置视角"><Maximize className="w-3 h-3" /></ToolBtn>
          <ToolBtn onClick={handleTop} title="俯视">↑</ToolBtn>
          <ToolBtn onClick={handleFront} title="正视">⊙</ToolBtn>
          <ToolBtn onClick={handleSide} title="侧视">⊳</ToolBtn>
          <ToolBtn onClick={() => setAutoRotate(!autoRotate)} active={autoRotate} title="自动旋转">
            <RotateCw className="w-3 h-3" />
          </ToolBtn>
          <ToolBtn onClick={handleZoomIn} title="放大点"><ZoomIn className="w-3 h-3" /></ToolBtn>
          <ToolBtn onClick={handleZoomOut} title="缩小点"><ZoomOut className="w-3 h-3" /></ToolBtn>
        </div>
      )}

      {/* ── HUD ── */}
      {viewState === 'ready' && !mini && (
        <div className="absolute top-3 right-3 z-40 text-[10px] font-mono text-gray-400 pointer-events-none opacity-60">
          <div>{totalSplats.toLocaleString()} pts</div>
          <div>dist:{hud.dist} size:{hud.size}</div>
        </div>
      )}

      {/* ── Help ── */}
      {(viewState === 'revealing' || viewState === 'ready') && !mini && (
        <div className="absolute bottom-10 left-1/2 -translate-x-1/2 z-10 text-[10px] text-gray-500 pointer-events-none">
          拖拽旋转 | 滚轮缩放 | 右键平移 | R键重置
        </div>
      )}

      {/* ── Error ── */}
      {viewState === 'error' && (
        <div className="absolute inset-0 z-50 flex flex-col items-center justify-center bg-black/70">
          <p className="text-red-400 text-sm">模型加载失败</p>
          <button
            className="mt-4 px-4 py-2 bg-slate-700 hover:bg-slate-600 text-white rounded text-sm"
            onClick={() => window.location.reload()}
          >
            重试
          </button>
        </div>
      )}
    </div>
  )
}

function ToolBtn({ onClick, title, active, children }: {
  onClick: () => void
  title: string
  active?: boolean
  children: React.ReactNode
}) {
  return (
    <button
      onClick={onClick}
      title={title}
      className={`w-7 h-7 flex items-center justify-center rounded text-xs transition-colors ${
        active
          ? 'bg-blue-600 text-white border border-blue-400'
          : 'bg-slate-800/80 text-gray-400 border border-slate-600/50 hover:bg-slate-700 hover:text-white'
      }`}
    >
      {children}
    </button>
  )
}
