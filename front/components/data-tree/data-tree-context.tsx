"use client"

import React, { createContext, useContext, useState, ReactNode } from 'react'

// 数据树数据类型
export interface TreeData {
  id: string;
  time: string;
  defectType: string;
  defectScore: number;
  widthScore: number;
  smoothnessScore: number;
  totalScore: number;
  finalScore: number;
}

interface DataTreeContextType {
  treeData: Map<number, TreeData>;
  addTreeData: (data: TreeData) => void;
  clearTreeData: () => void;
  selectedParticle: number | null;
  setSelectedParticle: (index: number | null) => void;
}

const DataTreeContext = createContext<DataTreeContextType | undefined>(undefined)

export function DataTreeProvider({ children }: { children: ReactNode }) {
  const [treeData, setTreeData] = useState<Map<number, TreeData>>(new Map())
  const [selectedParticle, setSelectedParticle] = useState<number | null>(null)

  // 添加数据到数据树
  const addTreeData = (data: TreeData) => {
    setTreeData(prev => {
      const next = new Map(prev)
      // 找到第一个空位
      for (let i = 0; i < 29000; i++) { // 总粒子数
        if (!next.has(i)) {
          next.set(i, data)
          return next
        }
      }
      // 如果没有空位，替换最旧的数据（简单实现：替换第一个）
      if (next.size > 0) {
        const firstKey = Array.from(next.keys())[0]
        next.set(firstKey, data)
      }
      return next
    })
  }

  // 清空数据树
  const clearTreeData = () => {
    setTreeData(new Map())
    setSelectedParticle(null)
  }

  return (
    <DataTreeContext.Provider value={{
      treeData,
      addTreeData,
      clearTreeData,
      selectedParticle,
      setSelectedParticle
    }}>
      {children}
    </DataTreeContext.Provider>
  )
}

export function useDataTree() {
  const context = useContext(DataTreeContext)
  if (context === undefined) {
    throw new Error('useDataTree must be used within a DataTreeProvider')
  }
  return context
}