import { StorageKey, getString, setString, remove } from "@/lib/storage"

export type CameraChoice =
  | { mode: "usb"; index: number; name: string }
  | { mode: "url"; url: string }
  | { mode: "default" }

export function readCameraChoice(): CameraChoice {
  const idxStr = getString(StorageKey.CAMERA_INDEX, "")
  if (idxStr !== "") {
    const idx = Number(idxStr)
    if (Number.isInteger(idx) && idx >= 0) {
      return { mode: "usb", index: idx, name: `摄像头 ${idx}` }
    }
  }
  const url = getString(StorageKey.CAMERA_URL, "")
  if (url) return { mode: "url", url }
  return { mode: "default" }
}

// 用户从没显式选过时，env 里配的 URL 仍作兜底（保留以前 .env.local 的语义）
export function envFallbackChoice(): CameraChoice {
  const envUrl = process.env.NEXT_PUBLIC_CAMERA_URL || ""
  if (envUrl) return { mode: "url", url: envUrl }
  return { mode: "default" }
}

export function describeChoice(c: CameraChoice): string {
  if (c.mode === "usb") return `${c.name} (index ${c.index})`
  if (c.mode === "url") return c.url
  return "本地默认摄像头 (index 0)"
}

// 选择翻译成 /start-yolo 的请求体；default 模式发空对象让后端走 camera_id=0
export function buildStartBody(choice: CameraChoice): Record<string, unknown> {
  if (choice.mode === "usb") return { camera_id: choice.index }
  if (choice.mode === "url") return { camera_url: choice.url }
  return {}
}

export function persistChoice(choice: CameraChoice): void {
  if (choice.mode === "usb") {
    setString(StorageKey.CAMERA_INDEX, String(choice.index))
    // USB 模式下清掉旧 URL，否则后端逻辑优先 URL 会忽略 index
    remove(StorageKey.CAMERA_URL)
  } else if (choice.mode === "url") {
    setString(StorageKey.CAMERA_URL, choice.url)
    remove(StorageKey.CAMERA_INDEX)
  } else {
    remove(StorageKey.CAMERA_INDEX)
    remove(StorageKey.CAMERA_URL)
  }
}
