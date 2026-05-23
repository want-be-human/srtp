"use client"

import React, { useEffect, useRef, useState } from "react"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { API_ENDPOINTS } from "@/lib/api"

interface CalibrationStatus {
  calibrated: boolean
  pixels_per_mm?: number
  ref_distance_pixels?: number
  ref_distance_mm?: number
  image_width?: number
  image_height?: number
  calibrated_at?: string
}

interface Snapshot {
  dataUrl: string
  width: number
  height: number
}

const CAMERA_ID = "default"
// 给两个手点位的画布尺寸；超大原图会缩放到这个宽度，保留比例
const CANVAS_MAX_WIDTH = 720

export function CameraCalibrationCard() {
  const [status, setStatus] = useState<CalibrationStatus | null>(null)
  const [snapshot, setSnapshot] = useState<Snapshot | null>(null)
  const [points, setPoints] = useState<Array<{ x: number; y: number }>>([])
  const [refMm, setRefMm] = useState<string>("50")
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [okMsg, setOkMsg] = useState<string | null>(null)
  const canvasRef = useRef<HTMLCanvasElement | null>(null)
  // displayScale = 画布显示宽 / 原图宽，回算点击像素时还原到原图坐标
  const displayScaleRef = useRef<number>(1)

  const loadStatus = async () => {
    try {
      const r = await fetch(`${API_ENDPOINTS.CALIBRATION_CURRENT}?camera_id=${CAMERA_ID}`)
      if (r.ok) {
        setStatus(await r.json())
      }
    } catch (e) {
      // 后端未起来不影响页面渲染
    }
  }

  useEffect(() => {
    loadStatus()
  }, [])

  const grabSnapshot = async () => {
    setError(null)
    setOkMsg(null)
    setPoints([])
    try {
      const r = await fetch(API_ENDPOINTS.SNAPSHOT)
      if (!r.ok) {
        const detail = await r.json().catch(() => ({ detail: "抓图失败" }))
        throw new Error(detail.detail || "抓图失败")
      }
      const data = await r.json()
      setSnapshot({
        dataUrl: `data:image/jpeg;base64,${data.image_base64}`,
        width: data.width,
        height: data.height,
      })
    } catch (e: any) {
      setError(e.message || "抓图失败，确保已开启实时检测")
    }
  }

  // 画布上画图 + 已选点
  useEffect(() => {
    if (!snapshot || !canvasRef.current) return
    const canvas = canvasRef.current
    const ctx = canvas.getContext("2d")
    if (!ctx) return

    const img = new Image()
    img.onload = () => {
      const scale = Math.min(1, CANVAS_MAX_WIDTH / snapshot.width)
      displayScaleRef.current = scale
      canvas.width = Math.round(snapshot.width * scale)
      canvas.height = Math.round(snapshot.height * scale)
      ctx.drawImage(img, 0, 0, canvas.width, canvas.height)

      // 点和连线（用原图坐标 × scale）
      ctx.strokeStyle = "#22d3ee"
      ctx.fillStyle = "#22d3ee"
      ctx.lineWidth = 2
      points.forEach((p) => {
        ctx.beginPath()
        ctx.arc(p.x * scale, p.y * scale, 6, 0, Math.PI * 2)
        ctx.fill()
      })
      if (points.length === 2) {
        ctx.beginPath()
        ctx.moveTo(points[0].x * scale, points[0].y * scale)
        ctx.lineTo(points[1].x * scale, points[1].y * scale)
        ctx.stroke()
      }
    }
    img.src = snapshot.dataUrl
  }, [snapshot, points])

  const onCanvasClick = (e: React.MouseEvent<HTMLCanvasElement>) => {
    if (!snapshot) return
    const rect = e.currentTarget.getBoundingClientRect()
    const xDisp = e.clientX - rect.left
    const yDisp = e.clientY - rect.top
    const scale = displayScaleRef.current || 1
    const x = xDisp / scale
    const y = yDisp / scale
    setPoints((prev) => (prev.length >= 2 ? [{ x, y }] : [...prev, { x, y }]))
  }

  const pixelDistance = points.length === 2
    ? Math.hypot(points[1].x - points[0].x, points[1].y - points[0].y)
    : 0

  const canSave = points.length === 2 && parseFloat(refMm) > 0 && snapshot && !saving

  const submit = async () => {
    if (!canSave || !snapshot) return
    setSaving(true)
    setError(null)
    setOkMsg(null)
    try {
      const r = await fetch(API_ENDPOINTS.CALIBRATION_SAVE, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          camera_id: CAMERA_ID,
          point1_x: points[0].x,
          point1_y: points[0].y,
          point2_x: points[1].x,
          point2_y: points[1].y,
          ref_distance_mm: parseFloat(refMm),
          image_width: snapshot.width,
          image_height: snapshot.height,
        }),
      })
      if (!r.ok) {
        const detail = await r.json().catch(() => ({ detail: "保存失败" }))
        throw new Error(detail.detail || "保存失败")
      }
      const saved = await r.json()
      setStatus(saved)
      setOkMsg(`已保存：${saved.pixels_per_mm.toFixed(3)} px/mm。重启实时检测后生效`)
      setPoints([])
    } catch (e: any) {
      setError(e.message || "保存失败")
    } finally {
      setSaving(false)
    }
  }

  return (
    <Card className="bg-slate-800/50 border-slate-600">
      <CardHeader>
        <CardTitle className="text-white">摄像头标定</CardTitle>
      </CardHeader>
      <CardContent className="space-y-4 text-gray-300 text-sm">
        <div className="bg-slate-900/40 rounded p-3 flex items-center justify-between">
          <div>
            <div className="font-medium">当前标定状态</div>
            {status?.calibrated ? (
              <div className="text-xs text-gray-400 mt-1">
                {status.pixels_per_mm?.toFixed(3)} px/mm · 参考 {status.ref_distance_mm}mm
                {status.image_width ? ` · 分辨率 ${status.image_width}×${status.image_height}` : ""}
              </div>
            ) : (
              <div className="text-xs text-yellow-400 mt-1">未标定，宽度 mm 值为估算</div>
            )}
          </div>
          <Button variant="outline" size="sm" onClick={loadStatus}>刷新</Button>
        </div>

        <ol className="list-decimal pl-5 space-y-1 text-xs text-gray-400">
          <li>先在「实时检测」开启检测，让摄像头出画面</li>
          <li>把标定卡或钢直尺放在焊缝位置，点「抓取当前画面」</li>
          <li>在画面上点击参考物两端（再点会重新开始）</li>
          <li>输入两点之间的真实长度，点「保存标定」</li>
          <li>停止后重新启动实时检测，新标定生效</li>
        </ol>

        <div className="flex gap-2">
          <Button onClick={grabSnapshot}>抓取当前画面</Button>
          {snapshot && (
            <Button variant="outline" onClick={() => { setPoints([]); setSnapshot(null) }}>
              取消
            </Button>
          )}
        </div>

        {error && <div className="text-sm text-red-400">{error}</div>}
        {okMsg && <div className="text-sm text-green-400">{okMsg}</div>}

        {snapshot && (
          <div className="space-y-3">
            <div className="overflow-auto bg-black/40 rounded">
              <canvas
                ref={canvasRef}
                onClick={onCanvasClick}
                className="cursor-crosshair block"
              />
            </div>
            <div className="text-xs text-gray-400">
              已点 {points.length}/2 点
              {points.length === 2 && ` · 像素距离 ${pixelDistance.toFixed(1)} px`}
            </div>
            <div className="flex items-center gap-2">
              <span className="text-sm">参考物真实长度</span>
              <Input
                type="number"
                value={refMm}
                onChange={(e) => setRefMm(e.target.value)}
                className="w-28"
                step="0.1"
                min="0.1"
              />
              <span className="text-sm">mm</span>
              <Button onClick={submit} disabled={!canSave}>
                {saving ? "保存中..." : "保存标定"}
              </Button>
            </div>
          </div>
        )}
      </CardContent>
    </Card>
  )
}
