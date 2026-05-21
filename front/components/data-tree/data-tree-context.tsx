"use client"

// 数据树状态按学号分槽存到 localStorage，切学号时把 selectedParticle 清掉，
// 防止旧索引落到新学生的空槽上。

import React, {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from "react"
import { useAuth } from "@/contexts/AuthContext"
import { API_ENDPOINTS } from "@/lib/api"
import { StorageKey, getJSON, setJSON } from "@/lib/storage"
import { convertYOLOToTreeData } from "./data-adapter"

export interface TreeData {
  id: string
  time: string
  defectType: string
  defectScore: number
  widthScore: number
  smoothnessScore: number
  totalScore: number
  finalScore: number
}

// Map 不能直接 JSON 序列化，所以存成 [index, TreeData] 数组
type StoredAll = Record<string, Array<[number, TreeData]>>

interface RecentScoreRow {
  total_score?: number
  smoothness_score?: number
  width_score?: number
  spacing_score?: number
  defect_score?: number
  defect_type_score?: number
  timestamp?: string
  actual_width?: number | null
  defect_type_name?: string | null
}

async function fetchTreeFromDb(studentId: string): Promise<Array<[number, TreeData]>> {
  const url = `${API_ENDPOINTS.RECENT_SCORES}?student_id=${encodeURIComponent(studentId)}&limit=200`
  const res = await fetch(url)
  if (!res.ok) throw new Error(`HTTP ${res.status}`)
  const data: { status: string; scores: RecentScoreRow[] } = await res.json()
  if (data.status !== "success" || !data.scores?.length) return []
  return data.scores.map((r, i) => [
    i,
    convertYOLOToTreeData({
      total_score: r.total_score ?? 0,
      smoothness_score: r.smoothness_score ?? 0,
      width_score: r.width_score ?? r.spacing_score ?? 0,
      defect_score: r.defect_score ?? r.defect_type_score ?? 0,
      timestamp: r.timestamp ?? new Date().toISOString(),
      actual_width: r.actual_width ?? undefined,
      defect_type_name: r.defect_type_name ?? undefined,
    }),
  ])
}

interface DataTreeContextType {
  treeData: Map<number, TreeData>
  addTreeData: (data: TreeData) => void
  clearTreeData: () => void
  selectedParticle: number | null
  setSelectedParticle: (index: number | null) => void
}

const DataTreeContext = createContext<DataTreeContextType | undefined>(undefined)

// 跟 data-tree-viewer 里 TOTAL_PARTICLES 对齐
const MAX_PARTICLES = 29000

export function DataTreeProvider({ children }: { children: ReactNode }) {
  const { currentUser, isHydrated } = useAuth()
  const [allStudents, setAllStudents] = useState<StoredAll>({})
  const [selectedParticle, setSelectedParticle] = useState<number | null>(null)

  useEffect(() => {
    if (!isHydrated) return
    setAllStudents(getJSON<StoredAll>(StorageKey.DATA_TREE, {}))
  }, [isHydrated])

  const studentKey = currentUser?.student_id ?? null
  useEffect(() => {
    setSelectedParticle(null)
  }, [studentKey])

  // 学生本地没有数据时从 DB 拉一次填进来，否则数据树空白
  useEffect(() => {
    if (!isHydrated || !studentKey) return
    let cancelled = false
    fetchTreeFromDb(studentKey)
      .then((entries) => {
        if (cancelled || entries.length === 0) return
        setAllStudents((prev) => {
          if ((prev[studentKey]?.length ?? 0) > 0) return prev
          const next = { ...prev, [studentKey]: entries }
          setJSON(StorageKey.DATA_TREE, next)
          return next
        })
      })
      .catch((err) => console.warn("[data-tree] DB 拉取历史失败", err))
    return () => {
      cancelled = true
    }
  }, [studentKey, isHydrated])

  const treeData = useMemo<Map<number, TreeData>>(() => {
    if (!studentKey) return new Map()
    return new Map(allStudents[studentKey] ?? [])
  }, [allStudents, studentKey])

  const addTreeData = useCallback(
    (data: TreeData) => {
      if (!studentKey || !isHydrated) return
      setAllStudents((prev) => {
        const slice = new Map(prev[studentKey] ?? [])
        let slot = -1
        for (let i = 0; i < MAX_PARTICLES; i++) {
          if (!slice.has(i)) {
            slot = i
            break
          }
        }
        if (slot === -1) {
          console.warn(`[data-tree] ${studentKey} 已用满 ${MAX_PARTICLES} 个槽位，丢弃新记录`)
          return prev
        }
        slice.set(slot, data)
        const next = { ...prev, [studentKey]: Array.from(slice.entries()) }
        setJSON(StorageKey.DATA_TREE, next)
        return next
      })
    },
    [studentKey, isHydrated],
  )

  const clearTreeData = useCallback(() => {
    if (!studentKey || !isHydrated) return
    setAllStudents((prev) => {
      const next = { ...prev, [studentKey]: [] }
      setJSON(StorageKey.DATA_TREE, next)
      return next
    })
    setSelectedParticle(null)
  }, [studentKey, isHydrated])

  const value = useMemo<DataTreeContextType>(
    () => ({
      treeData,
      addTreeData,
      clearTreeData,
      selectedParticle,
      setSelectedParticle,
    }),
    [treeData, addTreeData, clearTreeData, selectedParticle],
  )

  return <DataTreeContext.Provider value={value}>{children}</DataTreeContext.Provider>
}

export function useDataTree() {
  const context = useContext(DataTreeContext)
  if (context === undefined) {
    throw new Error("useDataTree must be used within a DataTreeProvider")
  }
  return context
}
