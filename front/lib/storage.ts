// 焊育智眸前端 localStorage 命名空间封装。
// 统一 `srtp:` 前缀，避免和宿主页面、其它工具的 localStorage key 冲突。
// SSR 安全：在服务端渲染期间，window 不存在时所有 get 返回 fallback、所有 set 静默丢弃。

const NS = "srtp:"

export const StorageKey = {
  CAMERA_URL: `${NS}camera_url`,
  AUTH_USER: `${NS}auth_user`,
  DATA_TREE: `${NS}data_tree`,
  // 后续 Phase D 用到的键统一在这里登记
  // DEMO_SAFE_MODE: `${NS}demo_safe_mode`,
  // TTS_MUTED: `${NS}tts_muted`,
} as const

// JSON helper：方便存复杂对象。失败时静默返回 fallback。
export function getJSON<T>(key: string, fallback: T): T {
  const raw = getString(key, "")
  if (!raw) return fallback
  try {
    return JSON.parse(raw) as T
  } catch {
    return fallback
  }
}

export function setJSON(key: string, value: unknown): void {
  try {
    setString(key, JSON.stringify(value))
  } catch {
    // JSON 序列化失败（含循环引用等）：静默忽略
  }
}

function hasStorage(): boolean {
  return typeof window !== "undefined" && typeof window.localStorage !== "undefined"
}

export function getString(key: string, fallback = ""): string {
  if (!hasStorage()) return fallback
  try {
    const raw = window.localStorage.getItem(key)
    return raw === null ? fallback : raw
  } catch {
    return fallback
  }
}

export function setString(key: string, value: string): void {
  if (!hasStorage()) return
  try {
    window.localStorage.setItem(key, value)
  } catch {
    // 配额超限 / 隐私模式：静默忽略，调用方不应因此崩溃
  }
}

export function remove(key: string): void {
  if (!hasStorage()) return
  try {
    window.localStorage.removeItem(key)
  } catch {
    // 同上
  }
}
