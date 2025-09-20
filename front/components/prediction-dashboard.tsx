"use client"

import React, { useState, useEffect } from "react"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { TrendingUp, Brain, Target, AlertTriangle, BarChart3, Activity, Zap } from "lucide-react"
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer, ReferenceLine, Label, Area } from 'recharts';

export function PredictionDashboardContent() {
  const [timeRange, setTimeRange] = useState("week")
  const [selectedStudent, setSelectedStudent] = useState("all")
  const [skillProgressionData, setSkillProgressionData] = useState<any[]>([])
  const [predictedScores, setPredictedScores] = useState<any[]>([])
  const [bottleneckInfo, setBottleneckInfo] = useState<any>(null)

  useEffect(() => {
    const fetchDataAndPredict = async () => {
      try {
        // 1. 获取历史数据
        const historyResponse = await fetch("http://127.0.0.1:8000/api/v1/dashboard/history")
        if (!historyResponse.ok) throw new Error("获取历史数据失败")
        const historyData = await historyResponse.json()

        const formattedData = historyData.map((record: any, index: number) => ({
          week: `第 ${index + 1} 周`,
          "焊接速度控制": record.speed_score,
          "焊接角度控制": record.angle_score,
          "熔深控制": record.depth_score,
          "整体缺陷": record.defect_score,
        }))
        setSkillProgressionData(formattedData)

        // 2. 如果有历史数据, 则进行预测
        if (formattedData.length > 0) {
          const predictionResponse = await fetch("http://127.0.0.1:8000/api/v1/predict", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ history: formattedData }),
          })
          if (!predictionResponse.ok) throw new Error("获取预测数据失败")
          const predictionData = await predictionResponse.json()
          
          setPredictedScores(predictionData.future_scores)
          setBottleneckInfo(predictionData.bottleneck)
        }
      } catch (error) {
        console.error(error)
      }
    }

    fetchDataAndPredict()
  }, [])

  const combinedChartData = [...skillProgressionData, ...predictedScores]

  // 学习瓶颈预测数据 - 改为单用户的不同技能领域
  const bottleneckPrediction = [
    { skillArea: "焊接速度控制", bottleneckProb: 0.15, riskLevel: "低", predictedWeek: "第9周" },
    { skillArea: "焊接角度控制", bottleneckProb: 0.68, riskLevel: "高", predictedWeek: "第7周" },
    { skillArea: "熔深控制", bottleneckProb: 0.42, riskLevel: "中", predictedWeek: "第8周" },
    { skillArea: "整体操作手法", bottleneckProb: 0.23, riskLevel: "低", predictedWeek: "第10周" },
  ]

  // 缺陷预测分布
  const defectPrediction = [
    { type: "无缺陷", probability: 0.45, trend: "上升", color: "#10b981" },
    { type: "气孔", probability: 0.25, trend: "下降", color: "#f59e0b" },
    { type: "夹渣", probability: 0.15, trend: "稳定", color: "#ef4444" },
    { type: "未焊透", probability: 0.1, trend: "下降", color: "#8b5cf6" },
    { type: "咬边", probability: 0.05, trend: "稳定", color: "#06b6d4" },
  ]

  // 个性化推荐数据
  const recommendations = [
    {
      category: "技能提升策略",
      items: [
        "建议加强熔深控制练习，重点关注电流参数调节",
        "推荐进行焊接角度标准化训练，提升操作稳定性",
        "建议观看高级焊接技巧视频教程",
      ],
    },
    {
      category: "缺陷预防方案",
      items: [
        "预防气孔：检查保护气体流量，确保焊接环境清洁",
        "避免夹渣：提高焊接速度，改善熔池流动性",
        "防止未焊透：适当增加焊接电流，控制焊接速度",
      ],
    },
    {
      category: "学习路径规划",
      items: ["第7-8周：重点训练角度控制技能", "第9-10周：综合技能整合练习", "第11-12周：高难度焊接项目实战"],
    },
  ]

  // 技能发展趋势图组件
  const SkillTrendChart = () => {
    const skills = ["焊接速度控制", "焊接角度控制", "熔深控制", "整体缺陷"]
    const colors = ["#3b82f6", "#10b981", "#f59e0b", "#8b5cf6"]

    console.log("Rendering chart with data:", combinedChartData);

    if (combinedChartData.length === 0) {
      return <div className="h-80 w-full flex items-center justify-center text-gray-400">正在加载图表数据...</div>;
    }

    return (
      <div className="h-80 w-full">
        <ResponsiveContainer width="100%" height="100%">
          <LineChart
            data={combinedChartData}
            margin={{ top: 5, right: 30, left: 0, bottom: 5 }}
          >
            <defs>
              {skills.map((skill, index) => (
                <linearGradient key={`gradient-${skill}`} id={`gradient-${index}`} x1="0" y1="0" x2="0" y2="1">
                  <stop offset="5%" stopColor={colors[index]} stopOpacity={0.4}/>
                  <stop offset="95%" stopColor={colors[index]} stopOpacity={0}/>
                </linearGradient>
              ))}
              <filter id="glow" x="-50%" y="-50%" width="200%" height="200%">
                <feGaussianBlur stdDeviation="4" result="coloredBlur"/>
                <feMerge>
                  <feMergeNode in="coloredBlur"/>
                  <feMergeNode in="SourceGraphic"/>
                </feMerge>
              </filter>
            </defs>
            <CartesianGrid strokeDasharray="3 3" stroke="#2d3748" />
            <XAxis dataKey="week" stroke="#718096" fontSize={12} />
            <YAxis stroke="#718096" fontSize={12} domain={[40, 100]} />
            <Tooltip
              contentStyle={{
                backgroundColor: "rgba(17, 24, 39, 0.9)",
                borderColor: "#4a5568",
                color: "#e5e7eb",
                borderRadius: "0.5rem",
                boxShadow: "0 0 15px rgba(0, 0, 0, 0.5)"
              }}
              cursor={{ stroke: '#4a5568', strokeWidth: 1, strokeDasharray: '3 3' }}
            />
            <Legend wrapperStyle={{ fontSize: "14px", color: "#a0aec0" }} />
            {skills.map((skill, index) => (
              <React.Fragment key={`fragment-${skill}`}>
                <Area
                  type="monotone"
                  dataKey={skill}
                  stroke="none"
                  fill={`url(#gradient-${index})`}
                  isAnimationActive={false}
                />
                <Line
                  type="monotone"
                  dataKey={skill}
                  stroke={colors[index]}
                  strokeWidth={3}
                  dot={{ r: 5, stroke: '#1a202c', strokeWidth: 2 }}
                  activeDot={{ r: 8, stroke: colors[index], fill: '#1a202c' }}
                  isAnimationActive={true}
                  animationDuration={1500}
                  style={{filter: 'url(#glow)'}}
                />
              </React.Fragment>
            ))}
            {skillProgressionData.length > 0 && (
               <ReferenceLine
                 x={skillProgressionData[skillProgressionData.length -1]?.week}
                 stroke="#e53e3e"
                 strokeDasharray="4 4"
                 strokeWidth={1}
               >
                  <Label value="预测点" position="insideTop" fill="#e53e3e" fontSize={12} style={{ textShadow: '0 0 5px black' }} />
               </ReferenceLine>
            )}
          </LineChart>
        </ResponsiveContainer>
      </div>
    )
  }

  // 瓶颈预测雷达图组件
  const BottleneckRadarChart = () => {
    return (
      <div className="h-64 flex items-center justify-center">
        <div className="relative w-48 h-48">
          <svg className="w-full h-full" viewBox="0 0 200 200">
            {/* 雷达图背景 */}
            {[1, 2, 3, 4, 5].map((level) => (
              <circle
                key={level}
                cx="100"
                cy="100"
                r={level * 16}
                fill="none"
                stroke="#374151"
                strokeWidth="0.5"
                opacity="0.3"
              />
            ))}

            {/* 雷达图轴线 */}
            {bottleneckPrediction.map((_, index) => {
              const angle = (index * 2 * Math.PI) / bottleneckPrediction.length - Math.PI / 2
              const x2 = 100 + Math.cos(angle) * 80
              const y2 = 100 + Math.sin(angle) * 80
              return (
                <line key={index} x1="100" y1="100" x2={x2} y2={y2} stroke="#374151" strokeWidth="0.5" opacity="0.3" />
              )
            })}

            {/* 数据多边形 */}
            <polygon
              points={bottleneckPrediction
                .map((item, index) => {
                  const angle = (index * 2 * Math.PI) / bottleneckPrediction.length - Math.PI / 2
                  const radius = item.bottleneckProb * 80
                  const x = 100 + Math.cos(angle) * radius
                  const y = 100 + Math.sin(angle) * radius
                  return `${x},${y}`
                })
                .join(" ")}
              fill="rgba(239, 68, 68, 0.2)"
              stroke="#ef4444"
              strokeWidth="2"
            />

            {/* 数据点 */}
            {bottleneckPrediction.map((item, index) => {
              const angle = (index * 2 * Math.PI) / bottleneckPrediction.length - Math.PI / 2
              const radius = item.bottleneckProb * 80
              const x = 100 + Math.cos(angle) * radius
              const y = 100 + Math.sin(angle) * radius
              return (
                <circle
                  key={index}
                  cx={x}
                  cy={y}
                  r="4"
                  fill="#ef4444"
                  stroke="#ffffff"
                  strokeWidth="2"
                  className="cursor-pointer hover:r-6 transition-all"
                />
              )
            })}

            {/* 标签 */}
            {bottleneckPrediction.map((item, index) => {
              const angle = (index * 2 * Math.PI) / bottleneckPrediction.length - Math.PI / 2
              const x = 100 + Math.cos(angle) * 95
              const y = 100 + Math.sin(angle) * 95
              return (
                <text key={index} x={x} y={y} fill="#e5e7eb" fontSize="9" textAnchor="middle" className="font-medium">
                  {item.skillArea}
                </text>
              )
            })}
          </svg>
        </div>
      </div>
    )
  }

  return (
    <div className="h-full p-6 space-y-6">
      {/* 顶部控制栏 */}
      <div className="flex justify-between items-center">
        <h2 className="text-3xl font-bold text-white">智能学习预测</h2>
        <div className="flex items-center space-x-4">
          <div className="flex space-x-2">
            {["week", "month", "semester"].map((range) => (
              <Button
                key={range}
                variant={timeRange === range ? "default" : "outline"}
                size="sm"
                onClick={() => setTimeRange(range)}
                className={
                  timeRange === range
                    ? "bg-green-600 hover:bg-green-700"
                    : "border-slate-600 text-gray-300 hover:bg-slate-700"
                }
              >
                {range === "week" ? "本周" : range === "month" ? "本月" : "本学期"}
              </Button>
            ))}
          </div>
        </div>
      </div>

      {/* 核心指标卡片 */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-6">
        <Card className="bg-gradient-to-br from-blue-800/80 to-blue-700/80 border-blue-600/50 backdrop-blur-sm">
          <CardContent className="p-6 text-center">
            <div className="w-14 h-14 bg-gradient-to-br from-blue-500 to-blue-600 rounded-xl flex items-center justify-center mx-auto mb-4 shadow-lg">
              <Brain className="w-7 h-7 text-white" />
            </div>
            <div className="text-3xl font-bold text-blue-400 mb-2">87.5%</div>
            <div className="text-gray-300 font-medium">平均技能预测准确率</div>
          </CardContent>
        </Card>

        <Card className="bg-gradient-to-br from-green-800/80 to-green-700/80 border-green-600/50 backdrop-blur-sm">
          <CardContent className="p-6 text-center">
            <div className="w-14 h-14 bg-gradient-to-br from-green-500 to-green-600 rounded-xl flex items-center justify-center mx-auto mb-4 shadow-lg">
              <TrendingUp className="w-7 h-7 text-white" />
            </div>
            <div className="text-3xl font-bold text-green-400 mb-2">+12.3%</div>
            <div className="text-gray-300 font-medium">预期技能提升幅度</div>
          </CardContent>
        </Card>

        <Card className="bg-gradient-to-br from-orange-800/80 to-orange-700/80 border-orange-600/50 backdrop-blur-sm">
          <CardContent className="p-6 text-center">
            <div className="w-14 h-14 bg-gradient-to-br from-orange-500 to-orange-600 rounded-xl flex items-center justify-center mx-auto mb-4 shadow-lg">
              <AlertTriangle className="w-7 h-7 text-white" />
            </div>
            <div className="text-3xl font-bold text-orange-400 mb-2">2</div>
            <div className="text-gray-300 font-medium">预测学习瓶颈期</div>
          </CardContent>
        </Card>

        <Card className="bg-gradient-to-br from-purple-800/80 to-purple-700/80 border-purple-600/50 backdrop-blur-sm">
          <CardContent className="p-6 text-center">
            <div className="w-14 h-14 bg-gradient-to-br from-purple-500 to-purple-600 rounded-xl flex items-center justify-center mx-auto mb-4 shadow-lg">
              <Target className="w-7 h-7 text-white" />
            </div>
            <div className="text-3xl font-bold text-purple-400 mb-2">94.2%</div>
            <div className="text-gray-300 font-medium">个性化推荐匹配度</div>
          </CardContent>
        </Card>
      </div>

      {/* 技能发展预测趋势图 */}
      <Card className="bg-gradient-to-br from-gray-900 to-slate-800 border-slate-700 backdrop-blur-sm">
        <CardHeader>
          <CardTitle className="text-white flex items-center text-xl">
            <BarChart3 className="w-7 h-7 mr-3 text-blue-400" />
            多维技能发展预测趋势
          </CardTitle>
        </CardHeader>
        <CardContent className="p-6">
          <SkillTrendChart />
        </CardContent>
      </Card>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* 学习瓶颈预测 */}
        <Card className="bg-gradient-to-br from-gray-900 to-slate-800 border-slate-700 backdrop-blur-sm">
          <CardHeader>
            <CardTitle className="text-white flex items-center text-xl">
              <AlertTriangle className="w-7 h-7 mr-3 text-red-400" />
              学习瓶颈智能预警
            </CardTitle>
          </CardHeader>
          <CardContent className="p-6">
            <BottleneckRadarChart />
            <div className="mt-6 space-y-3">
              {bottleneckInfo ? (
                  <div className="p-3 rounded-lg border-l-4 border-red-500 bg-red-900/20">
                    <div className="flex items-center justify-between">
                      <div>
                        <div className="text-white font-medium">{bottleneckInfo.skillArea}</div>
                        <div className="text-gray-400 text-sm">{bottleneckInfo.suggestion}</div>
                      </div>
                      <div className="text-right">
                        <div className="font-bold text-red-400">{bottleneckInfo.riskLevel}风险</div>
                      </div>
                    </div>
                  </div>
              ) : (
                <div className="text-center text-gray-400">正在分析瓶颈...</div>
              )}
            </div>
          </CardContent>
        </Card>

        {/* 缺陷预测分布 */}
        <Card className="bg-gradient-to-br from-gray-900 to-slate-800 border-slate-700 backdrop-blur-sm">
          <CardHeader>
            <CardTitle className="text-white flex items-center text-xl">
              <Activity className="w-7 h-7 mr-3 text-purple-400" />
              焊接缺陷预测分析
            </CardTitle>
          </CardHeader>
          <CardContent className="p-6">
            <div className="space-y-4">
              {defectPrediction.map((defect, index) => (
                <div key={index} className="flex items-center justify-between p-3 bg-slate-700/30 rounded-lg">
                  <div className="flex items-center space-x-3">
                    <div className="w-4 h-4 rounded-full" style={{ backgroundColor: defect.color }}></div>
                    <div>
                      <div className="text-white font-medium">{defect.type}</div>
                      <div className="text-gray-400 text-sm flex items-center space-x-2">
                        <span>趋势: {defect.trend}</span>
                        {defect.trend === "上升" && <TrendingUp className="w-3 h-3 text-green-400" />}
                        {defect.trend === "下降" && <TrendingUp className="w-3 h-3 text-red-400 rotate-180" />}
                        {defect.trend === "稳定" && <Activity className="w-3 h-3 text-yellow-400" />}
                      </div>
                    </div>
                  </div>
                  <div className="text-right">
                    <div className="text-white font-bold text-lg">{(defect.probability * 100).toFixed(1)}%</div>
                    <div className="text-gray-400 text-xs">预测概率</div>
                  </div>
                </div>
              ))}
            </div>
          </CardContent>
        </Card>
      </div>

      {/* 个性化推荐系统 */}
      <Card className="bg-gradient-to-br from-gray-900 to-slate-800 border-slate-700 backdrop-blur-sm">
        <CardHeader>
          <CardTitle className="text-white flex items-center text-xl">
            <Zap className="w-7 h-7 mr-3 text-yellow-400" />
            AI智能推荐系统
          </CardTitle>
        </CardHeader>
        <CardContent className="p-6">
          <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
            {recommendations.map((category, index) => (
              <div key={index} className="space-y-4">
                <h4 className="text-lg font-semibold text-cyan-400 border-b border-slate-600 pb-2">
                  {category.category}
                </h4>
                <div className="space-y-3">
                  {category.items.map((item, itemIndex) => (
                    <div key={itemIndex} className="p-3 bg-slate-700/40 rounded-lg border border-slate-600/30">
                      <div className="text-gray-200 text-sm leading-relaxed">{item}</div>
                    </div>
                  ))}
                </div>
              </div>
            ))}
          </div>
        </CardContent>
      </Card>
    </div>
  )
}
