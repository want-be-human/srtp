"use client"

import React, { useState, useEffect } from "react"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"

interface PredictionData {
  history: any;
  forecast: any;
  line_chart: string;
  defect_radar: string;
  skill_radar: string;
}

// 预测图表组件
function PredictionChart({ chartData }: { chartData: string | null }) {
  if (!chartData) {
    return (
      <div className="flex items-center justify-center h-80 text-gray-400">
        正在加载预测图表...
      </div>
    )
  }

  return (
    <div className="w-full h-80 flex items-center justify-center">
      <img 
        src={`data:image/png;base64,${chartData}`} 
        alt="预测趋势图表" 
        className="max-w-full max-h-full object-contain"
      />
    </div>
  )
}

// 缺陷雷达图组件
function DefectRadar({ radarData }: { radarData: string | null }) {
  if (!radarData) {
    return (
      <div className="flex items-center justify-center h-64 text-gray-400">
        正在加载缺陷分析...
      </div>
    )
  }

  return (
    <div className="w-full h-64 flex items-center justify-center">
      <img 
        src={`data:image/png;base64,${radarData}`} 
        alt="缺陷雷达图" 
        className="max-w-full max-h-full object-contain"
      />
    </div>
  )
}

// 技能雷达图组件
function SkillRadar({ radarData }: { radarData: string | null }) {
  if (!radarData) {
    return (
      <div className="flex items-center justify-center h-64 text-gray-400">
        正在加载技能分析...
      </div>
    )
  }

  return (
    <div className="w-full h-64 flex items-center justify-center">
      <img 
        src={`data:image/png;base64,${radarData}`} 
        alt="技能雷达图" 
        className="max-w-full max-h-full object-contain"
      />
    </div>
  )
}

// AI输出框组件
function AIOutputBox() {
  return (
    <div className="bg-slate-800 border border-slate-600 rounded-lg p-4 h-full">
      <h3 className="text-lg font-semibold text-white mb-4">AI 分析结果</h3>
      <div className="space-y-3 text-gray-300">
        <div className="p-3 bg-slate-700/40 rounded-lg">
          <p className="text-sm">基于当前数据分析，预测未来五天焊接质量趋势整体向好。</p>
        </div>
        <div className="p-3 bg-slate-700/40 rounded-lg">
          <p className="text-sm">建议重点关注角度控制和熔深技术的练习，这将显著提升整体得分。</p>
        </div>
        <div className="p-3 bg-slate-700/40 rounded-lg">
          <p className="text-sm">缺陷分析显示，当前主要风险集中在气孔和夹渣问题，需要加强预防措施。</p>
        </div>
      </div>
    </div>
  )
}

export function PredictionDashboardContent() {
  const [predictionData, setPredictionData] = useState<PredictionData | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    const fetchPredictionData = async () => {
      try {
        setLoading(true)
        setError(null)
        
        const response = await fetch("http://127.0.0.1:8000/api/v1/predict")
        if (!response.ok) {
          throw new Error(`HTTP error! status: ${response.status}`)
        }
        
        const data = await response.json()
        setPredictionData(data)
      } catch (error) {
        console.error("获取预测数据失败:", error)
        setError(error instanceof Error ? error.message : "未知错误")
      } finally {
        setLoading(false)
      }
    }

    fetchPredictionData()
  }, [])

  if (loading) {
    return (
      <div className="h-full p-6 flex items-center justify-center">
        <div className="text-center text-gray-400">
          <div className="text-xl mb-2">正在加载预测数据...</div>
          <div className="text-sm">请稍候，正在生成智能分析结果</div>
        </div>
      </div>
    )
  }

  if (error) {
    return (
      <div className="h-full p-6 flex items-center justify-center">
        <div className="text-center text-red-400">
          <div className="text-xl mb-2">加载失败</div>
          <div className="text-sm">错误信息: {error}</div>
        </div>
      </div>
    )
  }

  return (
    <div className="h-full p-6 space-y-6">
      {/* 顶部标题 */}
      <div className="flex justify-between items-center">
        <h2 className="text-3xl font-bold text-white">智能焊接预测分析</h2>
      </div>

      {/* 上方：预测图表 */}
      <Card className="bg-gradient-to-br from-gray-900 to-slate-800 border-slate-700 backdrop-blur-sm">
        <CardHeader>
          <CardTitle className="text-white text-xl">
            未来五天质量趋势预测
          </CardTitle>
        </CardHeader>
        <CardContent className="p-6">
          <PredictionChart chartData={predictionData?.line_chart || null} />
        </CardContent>
      </Card>

      {/* 下方：左侧雷达图 + 右侧AI输出 */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* 缺陷雷达图 */}
        <Card className="bg-gradient-to-br from-gray-900 to-slate-800 border-slate-700 backdrop-blur-sm">
          <CardHeader>
            <CardTitle className="text-white text-lg">
              缺陷类型分析
            </CardTitle>
          </CardHeader>
          <CardContent className="p-6">
            <DefectRadar radarData={predictionData?.defect_radar || null} />
          </CardContent>
        </Card>

        {/* 技能雷达图 */}
        <Card className="bg-gradient-to-br from-gray-900 to-slate-800 border-slate-700 backdrop-blur-sm">
          <CardHeader>
            <CardTitle className="text-white text-lg">
              技能水平评估
            </CardTitle>
          </CardHeader>
          <CardContent className="p-6">
            <SkillRadar radarData={predictionData?.skill_radar || null} />
          </CardContent>
        </Card>

        {/* AI输出框 */}
        <Card className="bg-gradient-to-br from-gray-900 to-slate-800 border-slate-700 backdrop-blur-sm">
          <CardContent className="p-6">
            <AIOutputBox />
          </CardContent>
        </Card>
      </div>
    </div>
  )
}
