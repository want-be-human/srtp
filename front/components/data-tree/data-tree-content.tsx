"use client"

import React, { useState } from 'react'
import { Button } from "@/components/ui/button"
import { GitBranch as TreeIcon, Moon, Sun, RefreshCw, Trophy } from "lucide-react"
import { DataTreeViewer } from './data-tree-viewer'
import { StudentComparisonContent } from '@/components/comparison/student-comparison'

type ViewMode = 'tree' | 'pk'

export function DataTreeContent() {
  const [theme, setTheme] = useState<'dark' | 'light'>('dark')
  const [growthKey, setGrowthKey] = useState(0)
  const [mode, setMode] = useState<ViewMode>('tree')

  const handleResetGrowth = () => {
    setGrowthKey(prev => prev + 1)
  }

  return (
    <div className="h-full flex flex-col">
      <div className="flex items-center justify-between p-3 border-b border-slate-700 bg-slate-900/90 backdrop-blur-sm">
        <div>
          <h2 className="text-white text-xl font-bold flex items-center">
            {mode === 'tree' ? (
              <>
                <TreeIcon className="w-6 h-6 mr-2 text-green-400" />
                数据树可视化
              </>
            ) : (
              <>
                <Trophy className="w-6 h-6 mr-2 text-yellow-400" />
                学生对比 / PK
              </>
            )}
          </h2>
          <p className="text-gray-400 text-xs mt-1">
            {mode === 'tree'
              ? '实时检测数据以3D树形结构可视化展示，每个亮点代表一次检测记录'
              : '选一个同学并排看数据树和六维雷达，找差距'}
          </p>
        </div>
        <div className="flex items-center space-x-3">
          {mode === 'tree' && (
            <>
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
            </>
          )}
          <Button
            onClick={() => setMode(m => m === 'tree' ? 'pk' : 'tree')}
            variant="default"
            size="sm"
            className={`${mode === 'pk' ? 'bg-green-600 hover:bg-green-700' : 'bg-yellow-600 hover:bg-yellow-700'} text-white text-xs px-3`}
            title={mode === 'tree' ? '切到学生对比视图' : '切回数据树'}
          >
            {mode === 'tree' ? (
              <>
                <Trophy className="w-3 h-3 mr-1" />
                PK 对比
              </>
            ) : (
              <>
                <TreeIcon className="w-3 h-3 mr-1" />
                数据树
              </>
            )}
          </Button>
        </div>
      </div>

      {mode === 'tree' ? (
        <div className="flex-1 relative">
          <DataTreeViewer key={growthKey} theme={theme} />
        </div>
      ) : (
        <div className="flex-1 overflow-y-auto p-6">
          <StudentComparisonContent />
        </div>
      )}

      <style dangerouslySetInnerHTML={{__html: `
        .custom-scrollbar::-webkit-scrollbar { width: 4px; }
        .custom-scrollbar::-webkit-scrollbar-track { background: transparent; }
        .custom-scrollbar::-webkit-scrollbar-thumb { background: rgba(100, 100, 100, 0.3); border-radius: 4px; }
      `}} />
    </div>
  )
}
