"use client"

// 登录身份 Context（C1）
//
// - currentUser 来自 localStorage `srtp:auth_user`；首次挂载时 hydrate，避免
//   SSR 水合不一致。
// - login(student_id, password) 异步调用 /api/v1/auth/login，成功才写入
//   Context + localStorage；失败返回结构化错误信息供 UI 显示。
// - logout() 清空 Context + localStorage，由调用方决定后续跳转。
// - 没有 token / session：演示阶段不强制鉴权后端其它端点，前端 gate 是软的。

import { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react"
import type { ReactNode } from "react"
import { API_ENDPOINTS } from "@/lib/api"
import { StorageKey, getJSON, remove, setJSON } from "@/lib/storage"

export interface CurrentUser {
  student_id: string
  name: string
  batch_id?: string | null
}

export type LoginResult = { ok: true } | { ok: false; error: string }

interface AuthContextValue {
  currentUser: CurrentUser | null
  /** true 之后才能信任 currentUser 的值（避免 SSR 期间用空值 gate 跳转） */
  isHydrated: boolean
  login: (student_id: string, password: string) => Promise<LoginResult>
  logout: () => void
}

const AuthContext = createContext<AuthContextValue | null>(null)

export function AuthProvider({ children }: { children: ReactNode }) {
  const [currentUser, setCurrentUser] = useState<CurrentUser | null>(null)
  const [isHydrated, setIsHydrated] = useState(false)

  useEffect(() => {
    setCurrentUser(getJSON<CurrentUser | null>(StorageKey.AUTH_USER, null))
    setIsHydrated(true)
  }, [])

  const login = useCallback(
    async (student_id: string, password: string): Promise<LoginResult> => {
      try {
        const res = await fetch(API_ENDPOINTS.AUTH_LOGIN, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ student_id, password }),
        })
        if (res.status === 401) {
          return { ok: false, error: "学号或密码错误" }
        }
        if (!res.ok) {
          return { ok: false, error: `登录失败（HTTP ${res.status}）` }
        }
        const user = (await res.json()) as CurrentUser
        setCurrentUser(user)
        setJSON(StorageKey.AUTH_USER, user)
        return { ok: true }
      } catch (err) {
        return {
          ok: false,
          error: err instanceof Error ? `网络错误：${err.message}` : "网络错误",
        }
      }
    },
    [],
  )

  const logout = useCallback(() => {
    setCurrentUser(null)
    remove(StorageKey.AUTH_USER)
  }, [])

  const value = useMemo<AuthContextValue>(
    () => ({ currentUser, isHydrated, login, logout }),
    [currentUser, isHydrated, login, logout],
  )

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}

export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext)
  if (!ctx) {
    throw new Error("useAuth 必须在 <AuthProvider> 内调用")
  }
  return ctx
}
