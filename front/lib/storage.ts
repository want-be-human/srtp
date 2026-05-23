// localStorage 用 srtp: 前缀做命名空间。
// SSR 期间 window 不存在，get 直接返回 fallback，set 静默忽略。

const NS = "srtp:"

export const StorageKey = {
  CAMERA_URL: `${NS}camera_url`,
  CAMERA_INDEX: `${NS}camera_index`,
  AUTH_USER: `${NS}auth_user`,
  DATA_TREE: `${NS}data_tree`,
  PREDICTION_CACHE: `${NS}prediction_cache`,
} as const

/** 按学生分桶的预测缓存 key，没有学生时落到 guest 槽 */
export function getPredictionCacheKey(studentId?: string | null): string {
  return `${StorageKey.PREDICTION_CACHE}:${studentId || "guest"}`
}

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
    // 序列化失败，比如循环引用，忽略
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
    // 容量满 / 隐私模式等
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
