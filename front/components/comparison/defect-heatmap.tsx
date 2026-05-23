"use client"

import React, { useEffect, useMemo, useRef, useState } from "react"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Activity, Loader2 } from "lucide-react"
import { API_ENDPOINTS } from "@/lib/api"

export interface HeatmapPoint {
  cx: number
  cy: number
  w: number
  h: number
  label: string
  conf: number
}

interface HeatmapResponse {
  status: string
  student_id: string
  record_count: number
  point_count: number
  points: HeatmapPoint[]
  by_label: Record<string, number>
}

interface Props {
  studentId: string | null
  studentName?: string | null
  canvasWidth?: number
  canvasHeight?: number
  className?: string
}

// 同一缺陷在多份记录里反复出现 → 高斯核叠加成热区
const KERNEL_SIGMA_PX = 14
const KERNEL_RADIUS_PX = KERNEL_SIGMA_PX * 3
const RAMP_STOPS = [
  { t: 0.0, color: [0, 0, 0, 0] },
  { t: 0.15, color: [30, 64, 175, 80] },
  { t: 0.35, color: [37, 99, 235, 140] },
  { t: 0.55, color: [16, 185, 129, 180] },
  { t: 0.75, color: [234, 179, 8, 210] },
  { t: 1.0, color: [220, 38, 38, 240] },
]

function rampColor(t: number): [number, number, number, number] {
  const clamped = Math.max(0, Math.min(1, t))
  for (let i = 1; i < RAMP_STOPS.length; i++) {
    const a = RAMP_STOPS[i - 1]
    const b = RAMP_STOPS[i]
    if (clamped <= b.t) {
      const span = b.t - a.t || 1
      const k = (clamped - a.t) / span
      return [
        Math.round(a.color[0] + (b.color[0] - a.color[0]) * k),
        Math.round(a.color[1] + (b.color[1] - a.color[1]) * k),
        Math.round(a.color[2] + (b.color[2] - a.color[2]) * k),
        Math.round(a.color[3] + (b.color[3] - a.color[3]) * k),
      ]
    }
  }
  return RAMP_STOPS[RAMP_STOPS.length - 1].color as [number, number, number, number]
}

function drawHeatmap(canvas: HTMLCanvasElement, points: HeatmapPoint[]) {
  const ctx = canvas.getContext("2d")
  if (!ctx) return
  const W = canvas.width
  const H = canvas.height

  ctx.fillStyle = "#050816"
  ctx.fillRect(0, 0, W, H)

  // 焊缝区域示意：中心横带
  ctx.fillStyle = "rgba(148, 163, 184, 0.07)"
  ctx.fillRect(0, H * 0.35, W, H * 0.3)
  ctx.strokeStyle = "rgba(148, 163, 184, 0.25)"
  ctx.lineWidth = 1
  ctx.setLineDash([4, 4])
  ctx.beginPath()
  ctx.moveTo(0, H * 0.5)
  ctx.lineTo(W, H * 0.5)
  ctx.stroke()
  ctx.setLineDash([])

  if (points.length === 0) {
    ctx.fillStyle = "rgba(148, 163, 184, 0.7)"
    ctx.font = "13px system-ui, sans-serif"
    ctx.textAlign = "center"
    ctx.fillText("暂无缺陷分布数据", W / 2, H / 2)
    return
  }

  // 第一遍累加密度
  const density = new Float32Array(W * H)
  let dmax = 0
  const r = KERNEL_RADIUS_PX
  const sigma2 = KERNEL_SIGMA_PX * KERNEL_SIGMA_PX
  for (const p of points) {
    const px = Math.round(p.cx * W)
    const py = Math.round(p.cy * H)
    const weight = 0.4 + 0.6 * Math.max(0, Math.min(1, p.conf))
    const x0 = Math.max(0, px - r)
    const x1 = Math.min(W - 1, px + r)
    const y0 = Math.max(0, py - r)
    const y1 = Math.min(H - 1, py + r)
    for (let y = y0; y <= y1; y++) {
      const dy = y - py
      const row = y * W
      for (let x = x0; x <= x1; x++) {
        const dx = x - px
        const d2 = dx * dx + dy * dy
        if (d2 > r * r) continue
        const v = weight * Math.exp(-d2 / (2 * sigma2))
        const idx = row + x
        const nv = density[idx] + v
        density[idx] = nv
        if (nv > dmax) dmax = nv
      }
    }
  }

  if (dmax > 0) {
    const img = ctx.createImageData(W, H)
    const data = img.data
    for (let i = 0; i < density.length; i++) {
      const t = density[i] / dmax
      if (t <= 0) continue
      const [r0, g0, b0, a0] = rampColor(t)
      const j = i * 4
      data[j] = r0
      data[j + 1] = g0
      data[j + 2] = b0
      data[j + 3] = a0
    }
    ctx.putImageData(img, 0, 0)
  }

  // 散点叠层：每个 bbox 中心画个小点
  ctx.fillStyle = "rgba(255, 255, 255, 0.85)"
  for (const p of points) {
    const px = p.cx * W
    const py = p.cy * H
    ctx.beginPath()
    ctx.arc(px, py, 1.5, 0, Math.PI * 2)
    ctx.fill()
  }
}

export function DefectHeatmap({
  studentId,
  studentName,
  canvasWidth = 480,
  canvasHeight = 270,
  className,
}: Props) {
  const canvasRef = useRef<HTMLCanvasElement>(null)
  const [points, setPoints] = useState<HeatmapPoint[]>([])
  const [byLabel, setByLabel] = useState<Record<string, number>>({})
  const [recordCount, setRecordCount] = useState(0)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    if (!studentId) {
      setPoints([])
      setByLabel({})
      setRecordCount(0)
      setError(null)
      return
    }
    let cancelled = false
    setLoading(true)
    setError(null)
    const url = `${API_ENDPOINTS.DETECTION_HEATMAP}?student_id=${encodeURIComponent(studentId)}&limit=200`
    fetch(url)
      .then((r) => {
        if (!r.ok) throw new Error(`HTTP ${r.status}`)
        return r.json() as Promise<HeatmapResponse>
      })
      .then((data) => {
        if (cancelled) return
        if (data.status !== "success") throw new Error("接口返回 status != success")
        setPoints(data.points || [])
        setByLabel(data.by_label || {})
        setRecordCount(data.record_count || 0)
      })
      .catch((err) => {
        if (!cancelled) setError(err instanceof Error ? err.message : "未知错误")
      })
      .finally(() => {
        if (!cancelled) setLoading(false)
      })
    return () => {
      cancelled = true
    }
  }, [studentId])

  useEffect(() => {
    const canvas = canvasRef.current
    if (!canvas) return
    drawHeatmap(canvas, points)
  }, [points, canvasWidth, canvasHeight])

  const legend = useMemo(() => {
    return Object.entries(byLabel)
      .sort((a, b) => b[1] - a[1])
      .slice(0, 6)
  }, [byLabel])

  return (
    <Card className={`bg-slate-800/50 border-slate-600 overflow-hidden ${className ?? ""}`}>
      <CardHeader className="pb-2">
        <CardTitle className="text-white text-base flex items-center justify-between">
          <span className="flex items-center">
            <Activity className="w-5 h-5 mr-2 text-rose-400" />
            缺陷分布热图{studentName ? ` · ${studentName}` : ""}
          </span>
          <span className="text-xs text-gray-500">
            {studentId ? `${recordCount} 条记录 · ${points.length} 个缺陷框` : "未选择学生"}
          </span>
        </CardTitle>
      </CardHeader>
      <CardContent className="p-4">
        <div className="relative w-full" style={{ aspectRatio: `${canvasWidth} / ${canvasHeight}` }}>
          <canvas
            ref={canvasRef}
            width={canvasWidth}
            height={canvasHeight}
            className="absolute inset-0 w-full h-full rounded border border-slate-700"
          />
          {loading && (
            <div className="absolute inset-0 flex items-center justify-center bg-black/40 rounded">
              <Loader2 className="w-5 h-5 animate-spin text-rose-300" />
            </div>
          )}
        </div>
        {error && (
          <div className="text-xs text-red-300 mt-2">加载热图失败：{error}</div>
        )}
        {legend.length > 0 && (
          <div className="flex flex-wrap gap-x-3 gap-y-1 mt-3 text-xs text-gray-300">
            {legend.map(([label, count]) => (
              <span key={label} className="flex items-center">
                <span className="w-2 h-2 rounded-full bg-rose-400 mr-1.5" />
                {label} × {count}
              </span>
            ))}
          </div>
        )}
        <p className="text-[11px] text-gray-500 mt-2 leading-relaxed">
          以画面归一化坐标聚合学生历次按键时检测到的缺陷框，高斯核叠加近似 KDE 密度。
          中心横带为常见焊缝区域参考。
        </p>
      </CardContent>
    </Card>
  )
}
