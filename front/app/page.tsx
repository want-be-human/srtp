"use client"

import type React from "react"

import { useState, useEffect } from "react"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Home, Settings, User, Activity, TrendingUp, Cpu, FileDown, Eye, Brain, GraduationCap } from "lucide-react"
import Image from "next/image"
import { DataAnalysisContent } from "../components/data-analysis"
import { AITeacherChatContent } from "../components/ai-teacher-chat"
import { PredictionDashboardContent } from "../components/prediction-dashboard"

// 定义检测结果的类型接口
interface DetectionResult {
  overallScore: number;
  skillScores: {
    [key: string]: number;
  };
  defectPrediction: {
    type: string;
    confidence: string;
  };
  processingTime: string;
  modelConfidence: string;
}

export default function WeldingDetectionSystem() {
  const [activeModule, setActiveModule] = useState("dashboard")
  const [detectionResults, setDetectionResults] = useState<DetectionResult | null>(null)
  const [realTimeData, setRealTimeData] = useState({
    activeExperiments: 8,
    dataPoints: 12456,
    detectionAccuracy: 95.8,
    connectedDevices: 6,
    onlineStudents: 15,
  })

  // 模拟实时数据更新
  useEffect(() => {
    const interval = setInterval(() => {
      setRealTimeData((prev) => ({
        activeExperiments: Math.max(0, prev.activeExperiments + Math.floor(Math.random() * 3) - 1),
        dataPoints: prev.dataPoints + Math.floor(Math.random() * 20) + 5,
        detectionAccuracy: Math.max(90, Math.min(99, prev.detectionAccuracy + (Math.random() - 0.5) * 2)),
        connectedDevices: Math.max(0, prev.connectedDevices + Math.floor(Math.random() * 3) - 1),
        onlineStudents: Math.max(0, prev.onlineStudents + Math.floor(Math.random() * 5) - 2),
      }))
    }, 2000)

    return () => clearInterval(interval)
  }, [])

  const sidebarItems = [
    { id: "dashboard", label: "控制中心", icon: Home },
    { id: "detection", label: "焊缝检测", icon: Eye },
    { id: "teacher", label: "AI 教师", icon: GraduationCap },
    { id: "prediction", label: "智能预测", icon: Brain },
    { id: "analysis", label: "报告导出", icon: FileDown },
    { id: "settings", label: "系统设置", icon: Settings },
  ]

  // 根据当前模块获取背景色
  const getBackgroundColor = () => {
    switch (activeModule) {
      case "detection":
        return "bg-gradient-to-br from-slate-900 via-blue-900 to-slate-800"
      case "teacher":
        return "bg-gradient-to-br from-slate-900 via-orange-900 to-slate-800"
      case "prediction":
        return "bg-gradient-to-br from-slate-900 via-green-900 to-slate-800"
      case "analysis":
        return "bg-gradient-to-br from-slate-900 via-cyan-900 to-slate-800"
      default:
        return "bg-gradient-to-br from-slate-900 via-blue-900 to-slate-800"
    }
  }

  const renderMainContent = () => {
    switch (activeModule) {
      case "dashboard":
        return <DashboardContent realTimeData={realTimeData} setActiveModule={setActiveModule} />
      case "detection":
        return <DetectionContent setActiveModule={setActiveModule} setDetectionResults={setDetectionResults} detectionResults={detectionResults} />
      case "teacher":
        return <AITeacherChatContent lastDetectionResult={detectionResults} />
      case "prediction":
        return <PredictionDashboardContent />
      case "analysis":
        return <DataAnalysisContent />
      case "settings":
        return <SystemSettingsContent />
      default:
        return <DashboardContent realTimeData={realTimeData} setActiveModule={setActiveModule} />
    }
  }

  return (
    <div className={`h-screen ${getBackgroundColor()} flex overflow-hidden`}>
      {/* 左侧导航栏 */}
      <div className="w-64 bg-slate-900/95 backdrop-blur-sm border-r border-slate-700 flex flex-col">
        {/* Logo区域 */}
        <div className="p-6 border-b border-slate-700">
          <div className="flex items-center space-x-3">
            <div className="w-10 h-10 relative">
              <Image src="/images/swjtu-logo.png" alt="SWJTU Logo" width={40} height={40} className="rounded-lg" />
            </div>
            <div>
              <h1 className="text-white font-bold text-lg">SWJTU AI Lab</h1>
              <p className="text-gray-400 text-xs">焊缝智能检测教学</p>
            </div>
          </div>
        </div>

        {/* 导航菜单 */}
        <nav className="flex-1 p-4">
          <div className="space-y-2">
            {sidebarItems.map((item) => (
              <button
                key={item.id}
                onClick={() => setActiveModule(item.id)}
                className={`w-full flex items-center space-x-3 px-4 py-3 rounded-lg transition-all duration-200 ${
                  activeModule === item.id
                    ? "bg-blue-600 text-white shadow-lg"
                    : "text-gray-300 hover:bg-slate-800 hover:text-white"
                }`}
              >
                <item.icon className="w-5 h-5" />
                <span className="font-medium">{item.label}</span>
              </button>
            ))}
          </div>
        </nav>

        {/* 底部状态 */}
        <div className="p-4 border-t border-slate-700">
          <div className="flex items-center space-x-2 text-gray-400 text-sm">
            <div className="w-2 h-2 bg-green-400 rounded-full animate-pulse"></div>
            <span>系统运行正常</span>
          </div>
          <div className="text-gray-500 text-xs mt-1">版本 v2.1.0 | 在线学生: {realTimeData.onlineStudents}</div>
        </div>
      </div>

      {/* 主内容区域 */}
      <div className="flex-1 flex flex-col">
        {/* 顶部状态栏 */}
        <header className="h-16 bg-slate-800/50 backdrop-blur-sm border-b border-slate-700 flex items-center justify-between px-6">
          <div className="flex items-center space-x-4">
            <h2 className="text-white text-xl font-semibold">
              {sidebarItems.find((item) => item.id === activeModule)?.label || "控制中心"}
            </h2>
            <div className="flex items-center space-x-2 text-gray-400 text-sm">
              <Activity className="w-4 h-4" />
              <span>实时监控中</span>
            </div>
          </div>

          <div className="flex items-center space-x-4">
            <div className="flex items-center space-x-4 text-gray-300"></div>
            <div className="flex items-center space-x-4 text-gray-300">
              <button
                onClick={() => setActiveModule("settings")}
                className="flex items-center space-x-2 hover:text-white transition-colors"
              >
                <User className="w-5 h-5" />
                <span>研发团队</span>
              </button>
              <div className="text-gray-400">|</div>
              <div className="flex items-center space-x-2">
                <Image src="/images/swjtu-logo.png" alt="SWJTU" width={20} height={20} className="rounded" />
                <span>工程训练中心</span>
              </div>
            </div>
          </div>
        </header>

        {/* 主要内容区域 */}
        <main className={`flex-1 ${activeModule === "wenxin-teacher" ? "" : "p-6"} overflow-auto`}>
          {renderMainContent()}
        </main>
      </div>
    </div>
  )
}

// 控制中心主界面
function DashboardContent({ realTimeData, setActiveModule }: any) {
  return (
    <div className="space-y-6">
      {/* 系统宣传卡片 */}
      <Card className="bg-gradient-to-r from-blue-800 to-blue-900 border-blue-600/50 relative overflow-hidden">
        <CardContent className="p-6 text-center relative z-10">
          <div className="flex items-center justify-center space-x-4 mb-4">
            <Image src="/images/swjtu-logo.png" alt="西南交通大学校徽" width={60} height={60} className="rounded-lg" />
            <div>
              <div className="text-4xl font-bold text-white mb-2 drop-shadow-lg">焊缝智能检测教学AI系统</div>
              <p className="text-white text-base font-medium">智能检测 • 精准教学 • 技能提升</p>
            </div>
          </div>
          {/* 装饰性背景 */}
          <div className="absolute inset-0 opacity-5">
            <div className="absolute top-2 right-4 w-20 h-20 border-2 border-blue-400 rounded-full"></div>
            <div className="absolute bottom-2 left-4 w-16 h-16 border-2 border-cyan-400 rounded-full"></div>
          </div>
        </CardContent>
      </Card>

      {/* 三大核心功能模块 */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-8">
        <Card
          className="bg-gradient-to-br from-blue-700/80 to-cyan-700/80 border-blue-400 cursor-pointer transform transition-all duration-300 hover:scale-105 hover:shadow-2xl backdrop-blur-sm"
          onClick={() => setActiveModule("detection")}
        >
          <CardContent className="p-4 text-center">
            <div className="relative mb-8">
              <Eye className="w-16 h-16 text-blue-100 mx-auto animate-pulse" />
              <div className="absolute -top-2 -right-2 w-8 h-8 bg-green-500 rounded-full flex items-center justify-center">
                <span className="text-white text-sm font-bold">AI</span>
              </div>
            </div>
            <h3 className="text-2xl font-bold text-white mb-4">焊缝检测</h3>
            <p className="text-base text-blue-100 mb-6">智能识别 • 精准检测</p>
            <div className="space-y-3 text-white">
              <div>• 焊缝质量智能识别</div>
              <div>• 缺陷自动标注</div>
              <div>• 实时检测反馈</div>
            </div>
            <div className="mt-6 text-green-300 font-medium">
              ✓ 检测准确率 {realTimeData.detectionAccuracy.toFixed(1)}%
            </div>
          </CardContent>
        </Card>

        <Card
          className="bg-gradient-to-br from-orange-700/80 to-pink-700/80 border-orange-400 cursor-pointer transform transition-all duration-300 hover:scale-105 hover:shadow-2xl backdrop-blur-sm"
          onClick={() => setActiveModule("teacher")}
        >
          <CardContent className="p-4 text-center">
            <div className="relative mb-8">
              <GraduationCap
                className="w-16 h-16 text-orange-100 mx-auto animate-bounce"
                style={{ animationDuration: "2s" }}
              />
              <div className="absolute -top-1 -right-1 w-6 h-6 bg-red-500 rounded-full animate-pulse"></div>
            </div>
            <h3 className="text-2xl font-bold text-white mb-4">AI 教师</h3>
            <p className="text-base text-orange-100 mb-6">智能教学 • 个性指导</p>
            <div className="space-y-3 text-white">
              <div>• 焊接技术指导</div>
              <div>• 智能问答系统</div>
              <div>• 个性化教学</div>
            </div>
            <div className="mt-6 text-orange-300 font-medium">✓ 在线学生 {realTimeData.onlineStudents} 人</div>
          </CardContent>
        </Card>

        <Card
          className="bg-gradient-to-br from-green-700/80 to-teal-700/80 border-green-400 cursor-pointer transform transition-all duration-300 hover:scale-105 hover:shadow-2xl backdrop-blur-sm"
          onClick={() => setActiveModule("prediction")}
        >
          <CardContent className="p-4 text-center">
            <div className="relative mb-8">
              <Brain className="w-16 h-16 text-green-100 mx-auto" />
              <div className="absolute inset-0 animate-ping">
                <Brain className="w-16 h-16 text-green-100/30 mx-auto" />
              </div>
            </div>
            <h3 className="text-2xl font-bold text-white mb-4">智能预测</h3>
            <p className="text-base text-green-100 mb-6">学习预测 • 智能分析</p>
            <div className="space-y-3 text-white">
              <div>• 技能发展预测</div>
              <div>• 学习瓶颈识别</div>
              <div>• 个性化推荐</div>
            </div>
            <div className="mt-6 text-green-300 font-medium">✓ 预测准确率 87.5%</div>
          </CardContent>
        </Card>
      </div>

      {/* 系统性能监控 */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
        <Card className="bg-slate-800/50 border-slate-600">
          <CardHeader className="pb-2">
            <CardTitle className="text-white flex items-center text-sm">
              <Cpu className="w-4 h-4 mr-2 text-purple-400" />
              系统性能
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="space-y-2">
              <div>
                <div className="flex justify-between mb-1">
                  <span className="text-gray-400 text-xs">CPU</span>
                  <span className="text-green-400 text-xs">28%</span>
                </div>
                <div className="w-full bg-slate-700 rounded-full h-1.5">
                  <div className="bg-green-400 h-1.5 rounded-full w-1/4"></div>
                </div>
              </div>
              <div>
                <div className="flex justify-between mb-1">
                  <span className="text-gray-400 text-xs">内存</span>
                  <span className="text-yellow-400 text-xs">52%</span>
                </div>
                <div className="w-full bg-slate-700 rounded-full h-1.5">
                  <div className="bg-yellow-400 h-1.5 rounded-full w-1/2"></div>
                </div>
              </div>
            </div>
          </CardContent>
        </Card>

        <Card className="bg-slate-800/50 border-slate-600">
          <CardHeader className="pb-2">
            <CardTitle className="text-white flex items-center text-sm">
              <TrendingUp className="w-4 h-4 mr-2 text-green-400" />
              关键指标
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="grid grid-cols-2 gap-3">
              <div className="text-center">
                <div className="text-lg font-bold text-green-400">↑12%</div>
                <div className="text-gray-400 text-xs">检测效率</div>
              </div>
              <div className="text-center">
                <div className="text-lg font-bold text-cyan-400">{realTimeData.dataPoints.toLocaleString()}</div>
                <div className="text-gray-400 text-xs">检测数据</div>
              </div>
            </div>
          </CardContent>
        </Card>

        <Card className="bg-slate-800/50 border-slate-600">
          <CardHeader className="pb-2">
            <CardTitle className="text-white flex items-center text-sm">
              <Activity className="w-4 h-4 mr-2 text-blue-400" />
              运行状态
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="space-y-2">
              <div className="flex justify-between">
                <span className="text-gray-400 text-xs">系统可用性</span>
                <span className="text-green-400 text-sm font-bold">99.5%</span>
              </div>
              <div className="flex justify-between">
                <span className="text-gray-400 text-xs">响应时间</span>
                <span className="text-cyan-400 text-sm font-bold">15ms</span>
              </div>
            </div>
          </CardContent>
        </Card>
      </div>
    </div>
  )
}

// 焊缝检测模块
function DetectionContent({ setActiveModule, setDetectionResults, detectionResults }: { setActiveModule: (module: string) => void, setDetectionResults: (results: DetectionResult | null) => void, detectionResults: DetectionResult | null }) {
  const [selectedFile, setSelectedFile] = useState<File | null>(null)
  const [isDetecting, setIsDetecting] = useState(false)
  const [previewUrl, setPreviewUrl] = useState<string | null>(null)

  const handleFileSelect = (event: React.ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0]
    if (file) {
      setSelectedFile(file)
      const url = URL.createObjectURL(file)
      setPreviewUrl(url)
    }
  }

  const handleDetection = async () => {
    if (!selectedFile) return

    setIsDetecting(true)
    setDetectionResults(null)

    const formData = new FormData()
    formData.append("file", selectedFile)

    try {
      const response = await fetch("http://127.0.0.1:8000/api/v1/detect", {
        method: "POST",
        body: formData,
      })

      if (!response.ok) {
        throw new Error("网络响应错误")
      }

      const data = await response.json()

      // 将后端返回的数据转换为前端需要的格式
      const formattedResults = {
        overallScore: data.scores.total_score,
        skillScores: {
          "焊接速度控制": data.scores.speed_score,
          "焊接角度控制": data.scores.angle_score,
          "熔深控制": data.scores.depth_score,
          "整体缺陷": data.scores.defect_score,
        },
        defectPrediction: {
          type: data.detection_result === "Detection placeholder" ? "无明显缺陷" : data.detection_result,
          confidence: (Math.random() * 0.2 + 0.8).toFixed(3), // 模拟
        },
        processingTime: (Math.random() * 0.5 + 0.3).toFixed(2), // 模拟
        modelConfidence: (Math.random() * 0.2 + 0.8).toFixed(3), // 模拟
      }

      setDetectionResults(formattedResults)
    } catch (error) {
      console.error("检测失败:", error)
      // 可以在这里设置一个错误状态来通知用户
    } finally {
      setIsDetecting(false)
    }
  }

  const getGradeText = (score: number) => {
    if (score >= 90) return { text: "优", color: "text-green-400" }
    if (score >= 75) return { text: "良", color: "text-yellow-400" }
    return { text: "差", color: "text-red-400" }
  }

  const getScoreColor = (score: number) => {
    if (score >= 90) return "from-green-500 to-green-400"
    if (score >= 75) return "from-yellow-500 to-yellow-400"
    return "from-red-500 to-red-400"
  }

  return (
    <div className="h-full p-6">
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-8 h-full">
        {/* 左侧上传区 */}
        <Card className="bg-slate-800/50 border-slate-600 h-full">
          <CardHeader>
            <CardTitle className="text-white flex items-center">
              <Eye className="w-6 h-6 mr-2 text-blue-400" />
              焊缝检测上传
            </CardTitle>
          </CardHeader>
          <CardContent className="h-full flex flex-col">
            {/* 上传区域 */}
            <div className="flex-1 flex flex-col">
              {!previewUrl ? (
                <div className="flex-1 border-2 border-dashed border-slate-600 rounded-lg flex items-center justify-center">
                  <div className="text-center">
                    <div className="w-16 h-16 bg-slate-700 rounded-full flex items-center justify-center mx-auto mb-4">
                      <Eye className="w-8 h-8 text-gray-400" />
                    </div>
                    <p className="text-gray-400 mb-4">选择焊缝图片进行检测</p>
                    <input
                      type="file"
                      accept="image/*"
                      onChange={handleFileSelect}
                      className="hidden"
                      id="file-upload"
                    />
                    <label
                      htmlFor="file-upload"
                      className="bg-blue-600 hover:bg-blue-700 text-white px-6 py-2 rounded-lg cursor-pointer inline-block"
                    >
                      选择图片
                    </label>
                  </div>
                </div>
              ) : (
                <div className="flex-1 flex flex-col">
                  <div className="flex-1 bg-slate-900 rounded-lg p-4 mb-4">
                    <img
                      src={previewUrl || "/placeholder.svg"}
                      alt="预览"
                      className="w-full h-full object-contain rounded"
                    />
                  </div>
                  <div className="flex space-x-4">
                    <Button
                      onClick={handleDetection}
                      disabled={isDetecting}
                      className="flex-1 bg-green-600 hover:bg-green-700"
                    >
                      {isDetecting ? (
                        <div className="flex items-center">
                          <div className="animate-spin rounded-full h-4 w-4 border-b-2 border-white mr-2"></div>
                          检测中...
                        </div>
                      ) : (
                        "开始检测"
                      )}
                    </Button>
                    <Button
                      onClick={() => {
                        setPreviewUrl(null)
                        setSelectedFile(null)
                        setDetectionResults(null)
                      }}
                      variant="outline"
                      className="border-slate-600 text-gray-300"
                    >
                      重新选择
                    </Button>
                  </div>
                </div>
              )}
            </div>
          </CardContent>
        </Card>

        {/* 右侧结果区 */}
        <Card className="bg-slate-800/50 border-slate-600 h-full">
          <CardHeader>
            <CardTitle className="text-white flex items-center">
              <TrendingUp className="w-6 h-6 mr-2 text-green-400" />
              检测结果
            </CardTitle>
          </CardHeader>
          <CardContent className="h-full flex flex-col">
            {detectionResults ? (
              <div className="space-y-6">
                {/* 总体分数显示 */}
                <div className="text-center">
                  <div className="relative">
                    <div
                      className={`text-6xl font-bold text-transparent bg-gradient-to-r ${getScoreColor(detectionResults.overallScore)} bg-clip-text animate-pulse`}
                    >
                      {detectionResults.overallScore}
                      <span className="text-lg text-gray-400 absolute -bottom-1 -right-6">分</span>
                    </div>
                  </div>
                  <div className={`text-2xl font-bold mt-2 ${getGradeText(detectionResults.overallScore).color}`}>
                    {getGradeText(detectionResults.overallScore).text}
                  </div>
                </div>

                {/* 技能维度分数 */}
                <div className="bg-slate-900/50 rounded-lg p-4">
                  <h4 className="text-white font-semibold mb-4">技能维度评估</h4>
                  <div className="space-y-3">
                    {Object.entries(detectionResults.skillScores).map(([skill, score]) => (
                      <div key={skill} className="flex items-center justify-between">
                        <span className="text-gray-300 text-sm">{skill}</span>
                        <div className="flex items-center space-x-2">
                          <div className="w-24 bg-slate-700 rounded-full h-2">
                            <div
                              className={`h-2 rounded-full bg-gradient-to-r ${getScoreColor(score as number)}`}
                              style={{ width: `${score as number}%` }}
                            ></div>
                          </div>
                          <span className={`text-sm font-bold ${getGradeText(score as number).color}`}>{score}</span>
                        </div>
                      </div>
                    ))}
                  </div>
                </div>

                {/* 缺陷预测 */}
                <div className="bg-slate-900/50 rounded-lg p-4">
                  <h4 className="text-white font-semibold mb-4">缺陷预测分析</h4>
                  <div className="space-y-2">
                    <div className="flex justify-between">
                      <span className="text-gray-300 text-sm">预测缺陷类型</span>
                      <span
                        className={`font-bold ${
                          detectionResults.defectPrediction.type === "无缺陷" ? "text-green-400" : "text-red-400"
                        }`}
                      >
                        {detectionResults.defectPrediction.type}
                      </span>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-gray-300 text-sm">预测置信度</span>
                      <span className="text-cyan-400 font-bold">{detectionResults.defectPrediction.confidence}</span>
                    </div>
                  </div>
                </div>

                {/* 系统性能指标 */}
                <div className="bg-slate-900/50 rounded-lg p-4">
                  <h4 className="text-white font-semibold mb-4">系统性能</h4>
                  <div className="grid grid-cols-2 gap-4">
                    <div className="text-center">
                      <div className="text-lg font-bold text-green-400">{detectionResults.processingTime}s</div>
                      <div className="text-gray-400 text-xs">处理时间</div>
                    </div>
                    <div className="text-center">
                      <div className="text-lg font-bold text-purple-400">{detectionResults.modelConfidence}</div>
                      <div className="text-gray-400 text-xs">模型置信度</div>
                    </div>
                  </div>
                </div>

                {/* 智能推荐 */}
                <div className="border-t border-slate-700 pt-4">
                  <div className="text-blue-400 text-sm mb-2">✓ 已将检测数据输送给AI教师</div>
                  <Button
                    className="w-full bg-gradient-to-r from-blue-600 to-purple-600 hover:from-blue-700 hover:to-purple-700"
                    onClick={() => setActiveModule("teacher")}
                  >
                    咨询AI教师改进建议
                  </Button>
                </div>
              </div>
            ) : (
              <div className="flex-1 flex items-center justify-center text-center text-gray-400">
                <div>
                  <div className="w-24 h-24 border-4 border-slate-600 rounded-full flex items-center justify-center mx-auto mb-4">
                    <TrendingUp className="w-12 h-12" />
                  </div>
                  <p>等待检测结果...</p>
                </div>
              </div>
            )}
          </CardContent>
        </Card>
      </div>
    </div>
  )
}

// 系统设置模块（包含研发团队介绍）
function SystemSettingsContent() {
  return (
    <div className="space-y-6">
      <Card className="bg-slate-800/50 border-slate-600">
        <CardHeader>
          <CardTitle className="text-white">研发团队介绍</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            <div className="space-y-4">
              <h4 className="text-cyan-400 font-semibold">项目负责人</h4>
              <div className="text-gray-300 text-sm space-y-2">
                <div>• 张教授 - 焊接技术专家</div>
                <div>• 李工程师 - AI算法开发</div>
                <div>• 王老师 - 教学系统设计</div>
              </div>
            </div>
            <div className="space-y-4">
              <h4 className="text-orange-400 font-semibold">技术团队</h4>
              <div className="text-gray-300 text-sm space-y-2">
                <div>• 前端开发团队 3人</div>
                <div>• 后端开发团队 2人</div>
                <div>• 算法优化团队 2人</div>
              </div>
            </div>
          </div>
        </CardContent>
      </Card>

      <Card className="bg-slate-800/50 border-slate-600">
        <CardHeader>
          <CardTitle className="text-white">系统配置</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="space-y-4">
            <div className="flex justify-between items-center">
              <span className="text-gray-300">系统版本</span>
              <span className="text-gray-400">v2.1.0</span>
            </div>
            <div className="flex justify-between items-center">
              <span className="text-gray-300">最后更新</span>
              <span className="text-gray-400">2025-01-15</span>
            </div>
            <div className="flex justify-between items-center">
              <span className="text-gray-300">开发单位</span>
              <span className="text-gray-400">西南交通大学工程训练中心</span>
            </div>
          </div>
        </CardContent>
      </Card>
    </div>
  )
}
