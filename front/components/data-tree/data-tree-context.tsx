"use client"

// 数据树 Context：按登录学生隔离 + 持久化到 localStorage。
// 切换账号时 selectedParticle 必须重置——否则旧索引可能落在新学生的空槽上。

import React, {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useRef,
  useState,
  type ReactNode,
} from "react"
import { useAuth } from "@/contexts/AuthContext"
import { StorageKey, getJSON, setJSON } from "@/lib/storage"

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

// 落盘形态：student_id → [particle_index, TreeData][]（Map 不能直接 JSON 序列化）
type StoredAll = Record<string, Array<[number, TreeData]>>

interface DataTreeContextType {
  treeData: Map<number, TreeData>
  addTreeData: (data: TreeData) => void
  clearTreeData: () => void
  selectedParticle: number | null
  setSelectedParticle: (index: number | null) => void
}

const DataTreeContext = createContext<DataTreeContextType | undefined>(undefined)

// 与 data-tree-viewer 的 TOTAL_PARTICLES (7000 trunk + 22000 leaf) 对齐
const MAX_PARTICLES = 29000

export function DataTreeProvider({ children }: { children: ReactNode }) {
  const { currentUser, isHydrated } = useAuth()
  const [allStudents, setAllStudents] = useState<StoredAll>({})
  const [selectedParticle, setSelectedParticle] = useState<number | null>(null)
  const loadedRef = useRef(false)

  // 等 AuthContext hydrate 完再加载，避免 SSR 期间空读
  useEffect(() => {
    if (!isHydrated) return
    setAllStudents(getJSON<StoredAll>(StorageKey.DATA_TREE, {}))
    loadedRef.current = true
  }, [isHydrated])

  const studentKey = currentUser?.student_id ?? null
  useEffect(() => {
    setSelectedParticle(null)
  }, [studentKey])

  const treeData = useMemo<Map<number, TreeData>>(() => {
    if (!studentKey) return new Map()
    return new Map(allStudents[studentKey] ?? [])
  }, [allStudents, studentKey])

  const addTreeData = useCallback(
    (data: TreeData) => {
      if (!studentKey || !loadedRef.current) return
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
    [studentKey],
  )

  const clearTreeData = useCallback(() => {
    if (!studentKey || !loadedRef.current) return
    setAllStudents((prev) => {
      const next = { ...prev, [studentKey]: [] }
      setJSON(StorageKey.DATA_TREE, next)
      return next
    })
    setSelectedParticle(null)
  }, [studentKey])

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
