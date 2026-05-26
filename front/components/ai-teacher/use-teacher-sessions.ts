"use client"

// AI 教师多会话状态钩子：按学号分桶，每桶下多个 session，每个 session 独立 messages。
// 所有状态走 localStorage，没后端表。切学号时自动加载对应桶，避免老师/学生互窜历史。

import { useCallback, useEffect, useMemo, useRef, useState } from "react"
import { getJSON, getTeacherHistoryKey, remove, setJSON } from "@/lib/storage"

export interface TeacherMessage {
  id: string
  role: "user" | "assistant"
  content: string
  timestamp: string
  errorCategory?: string
}

export interface TeacherSession {
  id: string
  createdAt: string
  updatedAt: string
  // 自动用首条用户消息前 20 字，没消息时空串，由 UI 显示 "新对话"
  title: string
  messages: TeacherMessage[]
}

interface HistoryBucket {
  sessions: TeacherSession[]
  activeSessionId: string | null
}

const EMPTY_BUCKET: HistoryBucket = { sessions: [], activeSessionId: null }
const TITLE_MAX_CHARS = 20

function isValidBucket(value: unknown): value is HistoryBucket {
  if (!value || typeof value !== "object") return false
  const b = value as Partial<HistoryBucket>
  return Array.isArray(b.sessions)
}

function makeSessionId(): string {
  // 不引 uuid 包，时间戳 + 随机后缀够用且可读
  return `s_${Date.now().toString(36)}_${Math.random().toString(36).slice(2, 6)}`
}

function deriveTitle(messages: TeacherMessage[]): string {
  const firstUser = messages.find((m) => m.role === "user")
  if (!firstUser) return ""
  const text = firstUser.content.trim().replace(/\s+/g, " ")
  return text.length > TITLE_MAX_CHARS ? text.slice(0, TITLE_MAX_CHARS) + "…" : text
}

export interface TeacherSessionsApi {
  sessions: TeacherSession[]
  activeSessionId: string | null
  activeSession: TeacherSession | null
  createSession: () => string
  selectSession: (id: string) => void
  deleteSession: (id: string) => void
  clearAll: () => void
  appendMessages: (id: string, msgs: TeacherMessage[]) => void
}

export function useTeacherSessions(studentKey: string | null): TeacherSessionsApi {
  const storageKey = getTeacherHistoryKey(studentKey)
  const [bucket, setBucket] = useState<HistoryBucket>(EMPTY_BUCKET)
  // 切学号过渡期间禁止写回，防止用新桶（暂时空）覆盖旧桶
  const hydratedRef = useRef(false)

  useEffect(() => {
    hydratedRef.current = false
    const raw = getJSON<unknown>(storageKey, null)
    setBucket(isValidBucket(raw) ? raw : EMPTY_BUCKET)
    queueMicrotask(() => {
      hydratedRef.current = true
    })
  }, [storageKey])

  useEffect(() => {
    if (!hydratedRef.current) return
    if (bucket.sessions.length === 0 && bucket.activeSessionId === null) {
      // 整桶空了就把 key 删掉，免得 localStorage 残留空记录
      remove(storageKey)
      return
    }
    setJSON(storageKey, bucket)
  }, [bucket, storageKey])

  // updatedAt 倒序展示，最新的 session 永远顶端
  const sessions = useMemo(
    () =>
      [...bucket.sessions].sort((a, b) =>
        b.updatedAt.localeCompare(a.updatedAt),
      ),
    [bucket.sessions],
  )

  const activeSession = useMemo(
    () => bucket.sessions.find((s) => s.id === bucket.activeSessionId) ?? null,
    [bucket.sessions, bucket.activeSessionId],
  )

  const createSession = useCallback((): string => {
    const id = makeSessionId()
    const now = new Date().toISOString()
    setBucket((prev) => ({
      sessions: [
        ...prev.sessions,
        { id, createdAt: now, updatedAt: now, title: "", messages: [] },
      ],
      activeSessionId: id,
    }))
    return id
  }, [])

  const selectSession = useCallback((id: string) => {
    setBucket((prev) =>
      prev.sessions.some((s) => s.id === id)
        ? { ...prev, activeSessionId: id }
        : prev,
    )
  }, [])

  const deleteSession = useCallback((id: string) => {
    setBucket((prev) => {
      const next = prev.sessions.filter((s) => s.id !== id)
      let nextActive = prev.activeSessionId
      if (prev.activeSessionId === id) {
        // 删的是当前会话，自动跳到最近用过的（updatedAt 最大），全删光就清空
        const newest = next.reduce<TeacherSession | null>(
          (acc, s) => (!acc || s.updatedAt > acc.updatedAt ? s : acc),
          null,
        )
        nextActive = newest?.id ?? null
      }
      return { sessions: next, activeSessionId: nextActive }
    })
  }, [])

  const clearAll = useCallback(() => {
    setBucket(EMPTY_BUCKET)
  }, [])

  const appendMessages = useCallback((id: string, msgs: TeacherMessage[]) => {
    if (msgs.length === 0) return
    setBucket((prev) => {
      const idx = prev.sessions.findIndex((s) => s.id === id)
      if (idx === -1) return prev
      const session = prev.sessions[idx]
      const nextMessages = [...session.messages, ...msgs]
      const updated: TeacherSession = {
        ...session,
        messages: nextMessages,
        updatedAt: new Date().toISOString(),
        title: session.title || deriveTitle(nextMessages),
      }
      const nextSessions = [...prev.sessions]
      nextSessions[idx] = updated
      return { ...prev, sessions: nextSessions }
    })
  }, [])

  return {
    sessions,
    activeSessionId: bucket.activeSessionId,
    activeSession,
    createSession,
    selectSession,
    deleteSession,
    clearAll,
    appendMessages,
  }
}
