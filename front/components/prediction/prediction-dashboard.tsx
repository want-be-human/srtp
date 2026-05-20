"use client"

import React, { useState, useEffect } from "react"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer, RadarChart, Radar, PolarGrid, PolarAngleAxis, PolarRadiusAxis } from "recharts"
import { API_ENDPOINTS } from "@/lib/api"
import { getPredictionCacheKey } from "@/lib/storage"
import { useAuth } from "@/contexts/AuthContext"

interface PredictionData {
  history: Record<string, number>;
  forecast: Record<string, number>;
  skill_stats: Record<string, number>;
  defect_stats: Record<string, number>;
  total_detections: number;  // 总检测次数
}

interface RadarData {
  defect_radar: Record<string, number>;
  skill_radar: Record<string, number>;
  ai_summary: string;
}

// 前端内置的示例数据（fallback）— 仅当后端没有返回真实数据时显示
// TODO:replace-with-backend 真实聚合见 Phase C：删 /predict/ai-radar-data mock，改 DB 聚合
const DEFAULT_MOCK_DEFECT_DATA = {
  "夹渣": 68, "气孔": 52, "焊瘤": 35, "咬边": 32, "未熔合": 28, "裂纹": 18
}

const DEFAULT_MOCK_SKILL_DATA = {
  "光滑度": 82, "间距控制": 78, "缺陷控制": 85, "焊缝宽度": 76, "熔深控制": 80, "焊接速度": 83
}

function MockBadge() {
  return (
    <span className="absolute top-2 right-3 text-[10px] px-1.5 py-0.5 rounded bg-yellow-500/20 text-yellow-300 border border-yellow-500/30">
      示例数据
    </span>
  )
}

// 预测图表组件
function PredictionChart({ historyData, forecastData }: {
  historyData: Record<string, number> | null;
  forecastData: Record<string, number> | null;
}) {
  if (!historyData || !forecastData) {
    return (
      <div className="flex items-center justify-center h-80 text-gray-400">
        正在加载预测图表...
      </div>
    )
  }

  // 转换数据格式为 Recharts 需要的格式 - 使用检测次数而不是时间
  const historyPoints = Object.entries(historyData).map(([date, score], index) => ({
    detection: `第${index + 1}次`,
    detectionNumber: index + 1,
    historyScore: score,
    forecastScore: null
  }))

  const forecastPoints = Object.entries(forecastData).map(([date, score], index) => ({
    detection: `预测${index + 1}`,
    detectionNumber: historyPoints.length + index + 1,
    historyScore: null,
    forecastScore: score
  }))

  const chartData = [...historyPoints, ...forecastPoints]

  return (
    <div className="w-full h-80">
      <ResponsiveContainer width="100%" height="100%">
        <LineChart data={chartData}>
          <CartesianGrid strokeDasharray="3 3" stroke="#374151" />
          <XAxis
            dataKey="detection"
            stroke="#9CA3AF"
            tick={{ fill: '#9CA3AF' }}
            angle={-45}
            textAnchor="end"
            height={80}
          />
          <YAxis
            stroke="#9CA3AF"
            tick={{ fill: '#9CA3AF' }}
          />
          <Tooltip
            contentStyle={{
              backgroundColor: '#1F2937',
              border: '1px solid #374151',
              borderRadius: '8px',
              color: '#F3F4F6'
            }}
          />
          <Legend />
          <Line
            type="monotone"
            dataKey="historyScore"
            stroke="#3B82F6"
            strokeWidth={2}
            dot={{ r: 4 }}
            name="历史数据"
            connectNulls={false}
          />
          <Line
            type="monotone"
            dataKey="forecastScore"
            stroke="#F59E0B"
            strokeWidth={2}
            strokeDasharray="5 5"
            dot={{ r: 4, fill: '#F59E0B' }}
            name="预测数据"
            connectNulls={false}
          />
        </LineChart>
      </ResponsiveContainer>
    </div>
  )
}

// 缺陷雷达图组件
function DefectRadar({ radarData }: { radarData: RadarData | null }) {
  const isMock = !radarData?.defect_radar
  const displayData = radarData?.defect_radar || DEFAULT_MOCK_DEFECT_DATA

  const data = Object.entries(displayData).map(([type, value]) => ({
    subject: type,
    A: Math.round(value * 100) / 100,
    fullMark: 100
  }))

  return (
    <div className="w-full h-64 relative">
      {isMock && <MockBadge />}
      <ResponsiveContainer width="100%" height="100%">
        <RadarChart data={data}>
          <PolarGrid stroke="#374151" />
          <PolarAngleAxis dataKey="subject" tick={{ fill: '#9CA3AF' }} />
          <PolarRadiusAxis
            angle={90}
            domain={[0, 100]}
            tick={{ fill: '#9CA3AF' }}
          />
          <Radar
            name="缺陷统计"
            dataKey="A"
            stroke="#EF4444"
            fill="#EF4444"
            fillOpacity={0.3}
            strokeWidth={2}
          />
        </RadarChart>
      </ResponsiveContainer>
    </div>
  )
}

// 技能雷达图组件
function SkillRadar({ radarData }: { radarData: RadarData | null }) {
  const isMock = !radarData?.skill_radar
  const displayData = radarData?.skill_radar || DEFAULT_MOCK_SKILL_DATA

  const data = Object.entries(displayData).map(([skill, value]) => ({
    subject: skill,
    A: Math.round(value * 100) / 100,
    fullMark: 100
  }))

  return (
    <div className="w-full h-64 relative">
      {isMock && <MockBadge />}
      <ResponsiveContainer width="100%" height="100%">
        <RadarChart data={data}>
          <PolarGrid stroke="#374151" />
          <PolarAngleAxis dataKey="subject" tick={{ fill: '#9CA3AF' }} />
          <PolarRadiusAxis
            angle={90}
            domain={[0, 100]}
            tick={{ fill: '#9CA3AF' }}
          />
          <Radar
            name="技能评估"
            dataKey="A"
            stroke="#10B981"
            fill="#10B981"
            fillOpacity={0.3}
            strokeWidth={2}
          />
        </RadarChart>
      </ResponsiveContainer>
    </div>
  )
}

// AI输出框组件
function AIOutputBox({ aiAnalysis }: { aiAnalysis?: any }) {
  return (
    <div className="bg-slate-800 border border-slate-600 rounded-lg p-4 h-full">
      <h3 className="text-lg font-semibold text-white mb-4">AI 分析结果</h3>
      <div className="space-y-3 text-gray-300">
        {aiAnalysis?.ai_analysis ? (
          <>
            <div className="p-3 bg-slate-700/40 rounded-lg">
              <p className="text-sm font-medium text-blue-400 mb-1">趋势预测</p>
              <p className="text-sm">{aiAnalysis.ai_analysis.forecast_trend || "基于检测次数分析，预测趋势向好"}</p>
            </div>
            {aiAnalysis.ai_analysis.improvement_suggestions?.slice(0, 2).map((suggestion: string, index: number) => (
              <div key={index} className="p-3 bg-slate-700/40 rounded-lg">
                <p className="text-sm">{suggestion}</p>
              </div>
            ))}
            {aiAnalysis.ai_analysis.risk_analysis?.slice(0, 1).map((risk: string, index: number) => (
              <div key={index} className="p-3 bg-red-700/20 rounded-lg border border-red-800/30">
                <p className="text-sm text-red-300">{risk}</p>
              </div>
            ))}
          </>
        ) : (
          <>
            <div className="p-3 bg-slate-700/40 rounded-lg">
              <p className="text-sm">基于当前数据分析，预测未来5次检测焊接质量趋势整体向好。</p>
            </div>
            <div className="p-3 bg-slate-700/40 rounded-lg">
              <p className="text-sm">建议重点关注角度控制和熔深技术的练习，这将显著提升整体得分。</p>
            </div>
            <div className="p-3 bg-slate-700/40 rounded-lg">
              <p className="text-sm">缺陷分析显示，当前主要风险集中在气孔和夹渣问题，需要加强预防措施。</p>
            </div>
          </>
        )}
      </div>
    </div>
  )
}

export function PredictionDashboardContent() {
  const { currentUser } = useAuth()
  const [predictionData, setPredictionData] = useState<PredictionData | null>(null)
  const [radarData, setRadarData] = useState<RadarData | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [aiAnalysis, setAiAnalysis] = useState<any>(null)
  const [aiLoading, setAiLoading] = useState(false)

  // 给 endpoint 拼上 student_id 过滤；localStorage 缓存 key 按学生分桶，避免切账号串味
  const studentId = currentUser?.student_id ?? null
  const studentQuery = studentId ? `?student_id=${encodeURIComponent(studentId)}` : ""
  const cacheKey = getPredictionCacheKey(studentId)

  const fetchPredictionData = async (isBackground = false) => {
    try {
      if (!isBackground) setError(null)

      if (!isBackground) {
        const cachedData = localStorage.getItem(cacheKey)
        if (cachedData) {
          try {
            setPredictionData(JSON.parse(cachedData))
            setLoading(false)
            console.log('立即显示缓存数据')
          } catch (e) {
            console.warn('缓存数据解析失败')
          }
        } else {
          setLoading(true)
        }
      }

      const response = await fetch(`${API_ENDPOINTS.PREDICT}${studentQuery}`)
      if (!response.ok) {
        if (localStorage.getItem(cacheKey) && !isBackground) {
          console.warn('后端暂不可用，继续显示缓存数据')
          setLoading(false)
          return
        }
        throw new Error(`后端服务未启动或响应错误 (status: ${response.status})`)
      }

      const data = await response.json()
      setPredictionData(data)
      localStorage.setItem(cacheKey, JSON.stringify(data))
      localStorage.setItem(`${cacheKey}:time`, Date.now().toString())
      setLoading(false)
      if (!isBackground) {
        console.log('数据更新完成，total_detections:', data.total_detections, 'history点数:', Object.keys(data.history || {}).length)
      }

      if (!isBackground) {
        setTimeout(async () => {
          try {
            setAiLoading(true)

            const aiResponse = await fetch(`${API_ENDPOINTS.PREDICT_AI_ANALYSIS}${studentQuery}`)
            if (aiResponse.ok) {
              const aiData = await aiResponse.json()
              setAiAnalysis(aiData)
            }

            // 雷达端点目前是 mock 数据（D2 才会接入真实统计），先不拼 student_id
            const radarResponse = await fetch(API_ENDPOINTS.PREDICT_AI_RADAR)
            if (radarResponse.ok) {
              const radarResult = await radarResponse.json()
              setRadarData(radarResult)
            }
          } catch (aiError) {
            console.warn("获取AI分析失败（不影响主功能）:", aiError)
          } finally {
            setAiLoading(false)
          }
        }, 100)
      }
    } catch (error) {
      console.error("获取预测数据失败:", error)
      if (!predictionData) {
        setError(error instanceof Error ? error.message : "未知错误")
      }
      setLoading(false)
    }
  }

  useEffect(() => {
    fetchPredictionData(false)
    // 5 秒静默刷新；studentId 变化会重启 effect，确保切学生时立即拉新数据
    const interval = setInterval(() => {
      fetchPredictionData(true)
    }, 5000)
    return () => clearInterval(interval)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [studentId])

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
            基于检测次数的质量趋势预测
          </CardTitle>
        </CardHeader>
        <CardContent className="p-6">
          <PredictionChart
            historyData={predictionData?.history || null}
            forecastData={predictionData?.forecast || null}
          />
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
            <DefectRadar radarData={radarData} />
          </CardContent>
        </Card>

        {/* 技能雷达图 */}
        <Card className="bg-gradient-to-br from-gray-900 to-slate-800 border-slate-700 backdrop-blur-sm">
          <CardHeader className="flex flex-row items-center justify-between">
            <CardTitle className="text-white text-lg">
              技能水平评估
            </CardTitle>
            <span className="text-xs text-gray-500">（待接入数字焊枪）</span>
          </CardHeader>
          <CardContent className="p-6">
            <SkillRadar radarData={radarData} />
          </CardContent>
        </Card>

        {/* AI输出框 */}
        <Card className="bg-gradient-to-br from-gray-900 to-slate-800 border-slate-700 backdrop-blur-sm">
          <CardContent className="p-6">
            <AIOutputBox aiAnalysis={aiAnalysis} />
          </CardContent>
        </Card>
      </div>
    </div>
  )
}
