"use client"

import React, { useState, useRef } from 'react'
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Database, Info, GitBranch as TreeIcon, Moon, Sun, RefreshCw } from "lucide-react"
import { DataTreeViewer } from './data-tree-viewer'
import { useDataTree } from './data-tree-context'

export function DataTreeContent() {
  const { treeData } = useDataTree()
  const [theme, setTheme] = useState<'dark' | 'light'>('dark')
  const [growthKey, setGrowthKey] = useState(0) // 用于重置生长动画
  const logEntries = Array.from(treeData.entries()).reverse().slice(0, 5) // 只显示最近5条
  
  const handleResetGrowth = () => {
    setGrowthKey(prev => prev + 1) // 改变key以强制重新挂载组件
  }

  return (
    <div className="h-full flex flex-col">
      {/* 标题栏 - 固定在顶部，更紧凑 */}
      <div className="flex items-center justify-between p-3 border-b border-slate-700 bg-slate-900/90 backdrop-blur-sm">
        <div>
          <h2 className="text-white text-xl font-bold flex items-center">
            <TreeIcon className="w-6 h-6 mr-2 text-green-400" />
            数据树可视化
          </h2>
          <p className="text-gray-400 text-xs mt-1">
            实时检测数据以3D树形结构可视化展示，每个亮点代表一次检测记录
          </p>
        </div>
        <div className="flex items-center space-x-3">
          <div className="flex items-center space-x-2 text-xs text-gray-400">
            <div className="w-2 h-2 bg-green-400 rounded-full animate-pulse"></div>
            <span>数据接收正常</span>
          </div>
          <div className="text-xs text-gray-300">
            <span className="text-blue-400 font-bold">可容纳 29,000 个检测记录</span>
          </div>
          <Button
            onClick={handleResetGrowth}
            variant="default"
            size="sm"
            className="bg-amber-600 hover:bg-amber-700 text-white text-xs px-2"
            title="重新播放生长动画"
          >
            <RefreshCw className="w-3 h-3 mr-1" />
            重播动画
          </Button>
          <Button
            onClick={() => setTheme(t => t === 'dark' ? 'light' : 'dark')}
            variant="default"
            size="sm"
            className="bg-orange-600 hover:bg-orange-700 text-white text-xs px-2"
          >
            {theme === 'dark' ? (
              <>
                <Sun className="w-3 h-3 mr-1" />
                亮色模式
              </>
            ) : (
              <>
                <Moon className="w-3 h-3 mr-1" />
                暗色模式
              </>
            )}
          </Button>
        </div>
      </div>

      {/* 主内容区域 - 全屏3D数据树，移除所有内边距 */}
      <div className="flex-1 relative">
        <DataTreeViewer key={growthKey} theme={theme} />
      </div>

      <style dangerouslySetInnerHTML={{__html: `
        .custom-scrollbar::-webkit-scrollbar { width: 4px; }
        .custom-scrollbar::-webkit-scrollbar-track { background: transparent; }
        .custom-scrollbar::-webkit-scrollbar-thumb { background: rgba(100, 100, 100, 0.3); border-radius: 4px; }
      `}} />
    </div>
  )
}