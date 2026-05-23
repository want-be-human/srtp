"use client"

import { useEffect, useState } from "react"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog"
import { Camera, RefreshCw, Wifi } from "lucide-react"
import { API_ENDPOINTS } from "@/lib/api"
import {
  type CameraChoice,
  readCameraChoice,
  persistChoice,
} from "@/lib/camera-config"

interface CameraInfo {
  index: number
  name: string
}

interface CameraSelectorProps {
  open: boolean
  onOpenChange: (open: boolean) => void
  onSaved?: (choice: CameraChoice) => void
}

export function CameraSelector({ open, onOpenChange, onSaved }: CameraSelectorProps) {
  const [cameras, setCameras] = useState<CameraInfo[]>([])
  const [loading, setLoading] = useState(false)
  const [err, setErr] = useState("")
  const [draft, setDraft] = useState<CameraChoice>({ mode: "default" })
  const [urlInput, setUrlInput] = useState<string>("")

  const refresh = async () => {
    setLoading(true)
    setErr("")
    try {
      const r = await fetch(API_ENDPOINTS.LIST_CAMERAS)
      if (!r.ok) throw new Error(`HTTP ${r.status}`)
      const data = await r.json()
      setCameras(Array.isArray(data.cameras) ? data.cameras : [])
    } catch (e: any) {
      setErr(`枚举摄像头失败：${e.message || e}。可手动填网络摄像头 URL。`)
      setCameras([])
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    if (!open) return
    refresh()
    const cur = readCameraChoice()
    setDraft(cur)
    setUrlInput(cur.mode === "url" ? cur.url : "")
  }, [open])

  const isUsbActive = (idx: number) => draft.mode === "usb" && draft.index === idx
  const isUrlActive = draft.mode === "url"

  const handleSave = () => {
    let next: CameraChoice = draft
    if (draft.mode === "url") {
      const trimmed = urlInput.trim()
      if (!trimmed) {
        setErr("请填写摄像头 URL")
        return
      }
      next = { mode: "url", url: trimmed }
    }
    persistChoice(next)
    onSaved?.(next)
    onOpenChange(false)
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-md bg-slate-900 text-white border-slate-700">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            <Camera className="w-5 h-5 text-blue-400" />
            选择摄像头
          </DialogTitle>
          <DialogDescription className="text-slate-400">
            选中后点保存，下次开始检测会用这个设备。
          </DialogDescription>
        </DialogHeader>

        <div className="space-y-2 max-h-72 overflow-y-auto pr-1">
          {loading && <div className="text-sm text-slate-400">枚举中…</div>}
          {!loading && cameras.length === 0 && !err && (
            <div className="text-sm text-slate-400">未检测到 USB 摄像头</div>
          )}
          {cameras.map((cam) => {
            const active = isUsbActive(cam.index)
            return (
              <button
                key={cam.index}
                type="button"
                onClick={() => setDraft({ mode: "usb", index: cam.index, name: cam.name })}
                className={`w-full text-left px-3 py-2 rounded-md border transition flex items-center justify-between ${
                  active
                    ? "border-blue-500 bg-blue-500/10"
                    : "border-slate-700 hover:border-slate-500"
                }`}
              >
                <div className="flex items-center gap-2">
                  <Camera className="w-4 h-4 text-slate-300" />
                  <span>{cam.name}</span>
                </div>
                <span className="text-xs text-slate-500">index {cam.index}</span>
              </button>
            )
          })}

          <button
            type="button"
            onClick={() => setDraft({ mode: "url", url: urlInput })}
            className={`w-full text-left px-3 py-2 rounded-md border transition flex items-center gap-2 ${
              isUrlActive
                ? "border-blue-500 bg-blue-500/10"
                : "border-slate-700 hover:border-slate-500"
            }`}
          >
            <Wifi className="w-4 h-4 text-slate-300" />
            网络摄像头（手动填 URL）
          </button>
          {isUrlActive && (
            <Input
              autoFocus
              value={urlInput}
              onChange={(e) => setUrlInput(e.target.value)}
              placeholder="http://用户名:密码@IP:端口/"
              className="bg-slate-800 border-slate-700 text-white"
            />
          )}
        </div>

        {err && <div className="text-sm text-red-400">{err}</div>}

        <DialogFooter className="gap-2 sm:gap-2">
          <Button
            variant="outline"
            size="sm"
            onClick={refresh}
            disabled={loading}
            className="bg-slate-800 border-slate-600 text-white hover:bg-slate-700"
          >
            <RefreshCw className={`w-4 h-4 mr-1 ${loading ? "animate-spin" : ""}`} />
            刷新
          </Button>
          <Button
            variant="outline"
            size="sm"
            onClick={() => onOpenChange(false)}
            className="bg-slate-800 border-slate-600 text-white hover:bg-slate-700"
          >
            取消
          </Button>
          <Button size="sm" onClick={handleSave} className="bg-blue-600 hover:bg-blue-700">
            保存
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
