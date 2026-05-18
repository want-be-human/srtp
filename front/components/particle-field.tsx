"use client"

import React, { useEffect, useRef, useState, useMemo } from 'react'

/**
 * ---------------------------------------------------------------------------
 * 粒子特效核心配置 (物理参数)
 * 如果你觉得速度快慢、幅度大小不合适，修改这里：
 * ---------------------------------------------------------------------------
 */
const PARTICLE_COUNT = 5500    // 粒子数量
const FOCAL_LENGTH = 850      // 透视焦距
const MORPH_INTERVAL = 10000  // 文字切换间隔 (10秒)
const DAMPING = 0.94          // 运动阻尼 (越接近1越丝滑)
const STEER_STRENGTH = 0.055  // 转向力度
const SWAY_SPEED = 0.0006     // 自动摆动频率
const SWAY_AMPLITUDE = 0.45   // 自动摆动幅度 (约25度)

interface Vec3 {
  x: number
  y: number
  z: number
}

/**
 * 工具函数：文字转点云像素点
 */
function createTextPoints(text: string, size: number, count: number): Vec3[] {
  const canvas = document.createElement('canvas')
  const ctx = canvas.getContext('2d')
  if (!ctx) return []

  const width = 1000
  const height = 400
  canvas.width = width
  canvas.height = height

  ctx.fillStyle = 'white'
  ctx.font = `bold ${size}px "Inter", "Source Han Sans CN", "Microsoft YaHei", sans-serif`
  ctx.textAlign = 'center'
  ctx.textBaseline = 'middle'
  ctx.fillText(text, width / 2, height / 2)

  const imageData = ctx.getImageData(0, 0, width, height)
  const pixels: {x: number, y: number}[] = []

  for (let y = 0; y < height; y += 1) {
    for (let x = 0; x < width; x += 1) {
      if (imageData.data[(y * width + x) * 4] > 150) {
        pixels.push({ x: x - width / 2, y: y - height / 2 })
      }
    }
  }

  const result: Vec3[] = []
  if (pixels.length === 0) return Array(count).fill(0).map(() => ({ x: 0, y: 0, z: 0 }))

  for (let i = 0; i < count; i++) {
    const p = pixels[Math.floor(Math.random() * pixels.length)]
    result.push({ x: p.x, y: p.y, z: (Math.random() - 0.5) * 50 })
  }
  return result
}

/**
 * 粒子逻辑类
 */
class Particle {
  pos: Vec3
  target: Vec3
  vel: Vec3
  acc: Vec3
  size: number
  baseOpacity: number

  constructor() {
    const r = 2000
    this.pos = { x: (Math.random()-0.5)*r, y: (Math.random()-0.5)*r, z: (Math.random()-0.5)*r }
    this.target = { ...this.pos }
    this.vel = { x: 0, y: 0, z: 0 }
    this.acc = { x: 0, y: 0, z: 0 }
    this.size = Math.random() * 1.5 + 0.5
    this.baseOpacity = Math.random() * 0.7 + 0.3
  }

  update(mouseX: number, mouseY: number) {
    this.acc.x = (this.target.x - this.pos.x) * STEER_STRENGTH
    this.acc.y = (this.target.y - this.pos.y) * STEER_STRENGTH
    this.acc.z = (this.target.z - this.pos.z) * STEER_STRENGTH

    const dx = this.pos.x - mouseX
    const dy = this.pos.y - mouseY
    const distSq = dx * dx + dy * dy

    if (distSq < 8000) {
      const dist = Math.sqrt(distSq)
      const push = (90 - dist) * 0.12
      this.acc.x += (dx / dist) * push
      this.acc.y += (dy / dist) * push
      this.acc.z += push * 2
    }

    this.vel.x = (this.vel.x + this.acc.x) * DAMPING
    this.vel.y = (this.vel.y + this.acc.y) * DAMPING
    this.vel.z = (this.vel.z + this.acc.z) * DAMPING

    this.pos.x += this.vel.x
    this.pos.y += this.vel.y
    this.pos.z += this.vel.z
  }

  render(ctx: CanvasRenderingContext2D, width: number, height: number, rx: number, ry: number) {
    let nx = this.pos.x, ny = this.pos.y, nz = this.pos.z

    const cy = Math.cos(ry), sy = Math.sin(ry)
    const x1 = nx * cy - nz * sy
    const z1 = nx * sy + nz * cy
    nx = x1; nz = z1

    const cx = Math.cos(rx), sx = Math.sin(rx)
    const y2 = ny * cx - nz * sx
    const z2 = ny * sx + nz * cx
    ny = y2; nz = z2

    const scale = FOCAL_LENGTH / (FOCAL_LENGTH + nz)
    if (nz < -FOCAL_LENGTH + 50) return

    const px = nx * scale + width / 2
    const py = ny * scale + height / 2
    const alpha = Math.max(0, Math.min(1, (1.3 - nz / 600) * this.baseOpacity))
    const s = Math.max(0.4, this.size * scale)

    ctx.fillStyle = `rgba(255, 255, 255, ${alpha})`
    ctx.beginPath()
    ctx.arc(px, py, s, 0, Math.PI * 2)
    ctx.fill()
  }
}

/**
 * ---------------------------------------------------------------------------
 * 粒子场组件 - 可直接在卡片中使用
 * ---------------------------------------------------------------------------
 */
export const ParticleField: React.FC = () => {
  const canvasRef = useRef<HTMLCanvasElement>(null)
  const containerRef = useRef<HTMLDivElement>(null)
  const particles = useRef<Particle[]>([])
  const mouse = useRef({ x: -2000, y: -2000 })
  const rot = useRef({ x: 0, y: 0 })
  const [shapeIndex, setShapeIndex] = useState(0)

  const shapeList = [
    { label: "SWJTU", size: 180 },
    { label: "竢实扬华", size: 160 },
    { label: "自强不息", size: 160 },
    { label: "1896", size: 200 },
    { label: "AGENT", size: 180 },
    { label: "2026", size: 200 },
    { label: "AI LAB", size: 160 },
  ]

  const shapes = useMemo(() => {
    return shapeList.map(item => createTextPoints(item.label, item.size, PARTICLE_COUNT))
  }, [])

  useEffect(() => {
    const canvas = canvasRef.current
    if (!canvas) return
    const ctx = canvas.getContext('2d', { alpha: false })
    if (!ctx) return

    if (particles.current.length === 0) {
      for (let i = 0; i < PARTICLE_COUNT; i++) particles.current.push(new Particle())
    }

    const resize = () => {
      if (!containerRef.current) return
      const dpr = window.devicePixelRatio || 1
      const rect = containerRef.current.getBoundingClientRect()
      canvas.width = rect.width * dpr
      canvas.height = rect.height * dpr
      ctx.scale(dpr, dpr)
    }

    resize()
    window.addEventListener('resize', resize)

    let frameId: number
    const loop = () => {
      const rect = containerRef.current?.getBoundingClientRect()
      if (!rect) return

      ctx.fillStyle = '#010101'
      ctx.fillRect(0, 0, rect.width, rect.height)

      const now = Date.now()
      rot.current.y = Math.sin(now * SWAY_SPEED) * SWAY_AMPLITUDE
      rot.current.x = Math.sin(now * 0.0002) * 0.08

      const currentTarget = shapes[shapeIndex % shapes.length]
      particles.current.forEach((p, i) => {
        const t = currentTarget[i % currentTarget.length]
        p.target = t
        p.update(mouse.current.x - rect.width / 2, mouse.current.y - rect.height / 2)
        p.render(ctx, rect.width, rect.height, rot.current.x, rot.current.y)
      })

      frameId = requestAnimationFrame(loop)
    }

    frameId = requestAnimationFrame(loop)
    const timer = setInterval(() => setShapeIndex(v => v + 1), MORPH_INTERVAL)

    return () => {
      window.removeEventListener('resize', resize)
      cancelAnimationFrame(frameId)
      clearInterval(timer)
    }
  }, [shapeIndex, shapes])

  return (
    <div
      ref={containerRef}
      onPointerMove={(e) => {
        const rect = containerRef.current?.getBoundingClientRect()
        if (rect) mouse.current = { x: e.clientX - rect.left, y: e.clientY - rect.top }
      }}
      onPointerLeave={() => mouse.current = { x: -2000, y: -2000 }}
      className="relative w-full h-full bg-[#010101] overflow-hidden rounded-[3rem] border border-white/5 cursor-crosshair group"
    >
      <canvas ref={canvasRef} className="w-full h-full block" />

      {/* 覆盖在画布上的 UI 装饰 */}
      <div className="absolute top-12 left-12 flex flex-col gap-3 pointer-events-none opacity-40 group-hover:opacity-100 transition-all duration-700">
        <div className="flex items-center gap-4">
          <div className="w-1.5 h-1.5 bg-white rounded-full shadow-[0_0_10px_white] animate-pulse" />
          <span className="text-white text-[11px] tracking-[0.5em] font-bold">竢实扬华 自强不息</span>
        </div>
        <div className="h-[1px] w-48 bg-gradient-to-r from-white/40 to-transparent" />
      </div>

      <div className="absolute bottom-12 left-12 flex flex-col pointer-events-none">
        <p className="text-white/10 text-[8px] font-mono tracking-[0.5em] uppercase italic">Visual Tracking</p>
        <div className="text-white/90 text-4xl font-extralight tracking-[0.1em]">
          {shapeList[shapeIndex % shapeList.length].label}
        </div>
      </div>
    </div>
  )
}
