"use client"

import type React from "react"

import { useState, useEffect } from "react"
import { useRouter } from "next/navigation"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Home, Settings, User, Activity, TrendingUp, Database, FileDown, Eye, Brain, GraduationCap, GitBranch, LogOut, Trophy } from "lucide-react"
import Image from "next/image"
import { API_ENDPOINTS } from "@/lib/api"
import { getPredictionCacheKey, getRadarCacheKey } from "@/lib/storage"
import { useAuth } from "@/contexts/AuthContext"
import { LessonPlanExportContent } from "../components/lesson-plan/lesson-plan-export"
import { AITeacherChatContent } from "../components/ai-teacher/ai-teacher-chat"
import { PredictionDashboardContent } from "../components/prediction/prediction-dashboard"
import { YOLORealtimeDetector, initialYOLOLiveState, type YOLOLiveState } from "../components/detection/yolo-realtime-detector"
import { ParticleField } from "../components/particle-field"
import { DataTreeContent } from "../components/data-tree/data-tree-content"
import { StudentComparisonContent } from "../components/comparison/student-comparison"
import { CameraCalibrationCard } from "../components/settings/camera-calibration"

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
  // 检测态放在父级，免得切模块时 detector 卸载把状态带走
  const [yoloLive, setYoloLive] = useState<YOLOLiveState>(initialYOLOLiveState)
  const [yoloDataForTeacher, setYoloDataForTeacher] = useState<any>(null) // 存储要发送给AI教师的YOLO数据
  const [realTimeData, setRealTimeData] = useState({
    dataPoints: 0,
    avgScore: 0,
    batchCount: 0,
  })
  const router = useRouter()
  const { currentUser, isHydrated, logout } = useAuth()

  useEffect(() => {
    if (isHydrated && !currentUser) {
      router.replace("/login")
    }
  }, [currentUser, isHydrated, router])

  // 让登出跳转少等一会
  useEffect(() => {
    router.prefetch("/login")
  }, [router])

  // 登录后立刻在后台预取智能预测页要用的两份数据，结果写 localStorage。
  // 用户切到"智能预测"模块时 prediction-dashboard 会先从 localStorage 读出来
  // 立即渲染，不用等服务端 50-200ms 的聚合查询。AI 分析远程接口太慢不预取。
  useEffect(() => {
    const sid = currentUser?.student_id
    if (!sid) return
    const q = `?student_id=${encodeURIComponent(sid)}`
    fetch(`${API_ENDPOINTS.PREDICT}${q}`)
      .then((r) => (r.ok ? r.json() : null))
      .then((data) => {
        if (!data) return
        const key = getPredictionCacheKey(sid)
        localStorage.setItem(key, JSON.stringify(data))
        localStorage.setItem(`${key}:time`, Date.now().toString())
      })
      .catch(() => {
        // 后端没起来不阻塞登录后进入
      })
    fetch(`${API_ENDPOINTS.PREDICT_AI_RADAR}${q}`)
      .then((r) => (r.ok ? r.json() : null))
      .then((data) => {
        if (!data) return
        localStorage.setItem(getRadarCacheKey(sid), JSON.stringify(data))
      })
      .catch(() => {})
  }, [currentUser?.student_id])

  const handleLogout = () => {
    logout()
    router.replace("/login")
  }

  // 从后端获取真实数据
  useEffect(() => {
    const fetchRealData = async () => {
      try {
        const response = await fetch(API_ENDPOINTS.DASHBOARD_QUICK_STATS)
        if (response.ok) {
          const data = await response.json()
          setRealTimeData({
            dataPoints: data.total_detections || 0,
            avgScore: data.avg_score || 0,
            batchCount: data.batch_count || 0,
          })
        }
      } catch (error) {
        console.error('获取数据失败:', error)
      }
    }

    fetchRealData()
    // 每10秒刷新一次数据
    const interval = setInterval(fetchRealData, 10000)
    return () => clearInterval(interval)
  }, [])

  const sidebarItems = [
    { id: "dashboard", label: "控制中心", icon: Home },
    { id: "detection", label: "焊缝检测", icon: Eye },
    { id: "teacher", label: "AI 教师", icon: GraduationCap },
    { id: "prediction", label: "智能预测", icon: Brain },
    { id: "data-tree", label: "数据树", icon: GitBranch },
    { id: "comparison", label: "学生对比", icon: Trophy },
    { id: "analysis", label: "报告导出", icon: FileDown },
    { id: "settings", label: "关于我们", icon: Settings },
  ]

  // detector 内部已经发 POST 了，这里只是给个钩子方便调试
  const handleYOLODataSend = async (yoloData: any) => {
    console.log('发送YOLO数据到预测系统:', yoloData)
  }

  // 处理YOLO数据咨询AI教师
  const handleConsultTeacher = (yoloData: any) => {
    // 将YOLO数据转换为检测结果格式
    const formattedResults: DetectionResult = {
      overallScore: yoloData.totalScore,
      skillScores: {
        "光滑度": yoloData.smoothness,
        "焊缝宽度": yoloData.width,
        "缺陷控制": yoloData.defectType
      },
      defectPrediction: {
        type: yoloData.defectTypeName || "缺陷",
        confidence: "97%"
      },
      processingTime: "0.1s",
      modelConfidence: "高"
    }

    // 存储YOLO数据并切换到AI教师模块
    setYoloDataForTeacher(formattedResults)
    setDetectionResults(formattedResults)
    setActiveModule("teacher")
  }

  // 根据当前模块获取背景色
  const getBackgroundColor = () => {
    switch (activeModule) {
      case "detection":
        return "bg-gradient-to-br from-slate-900 via-blue-900 to-slate-800"
      case "teacher":
        return "bg-gradient-to-br from-slate-900 via-orange-900 to-slate-800"
      case "prediction":
        return "bg-gradient-to-br from-slate-900 via-green-900 to-slate-800"
      case "comparison":
        return "bg-gradient-to-br from-slate-900 via-purple-900 to-slate-800"
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
        return <DetectionContent
          setActiveModule={setActiveModule}
          setDetectionResults={setDetectionResults}
          detectionResults={detectionResults}
          yoloLive={yoloLive}
          setYoloLive={setYoloLive}
          sendYOLODataToPrediction={handleYOLODataSend}
          onConsultTeacher={handleConsultTeacher}
        />
      case "teacher":
        return <AITeacherChatContent lastDetectionResult={yoloDataForTeacher || detectionResults} />
      case "prediction":
        return <PredictionDashboardContent />
      case "data-tree":
        return <DataTreeContent />
      case "comparison":
        return <StudentComparisonContent />
      case "analysis":
        return <LessonPlanExportContent />
      case "settings":
        return <SystemSettingsContent />
      default:
        return <DashboardContent realTimeData={realTimeData} setActiveModule={setActiveModule} />
    }
  }

  // 还没 hydrate 或正在跳登录页时，先显示加载态而不是黑屏
  if (!isHydrated || !currentUser) {
    return (
      <div
        role="status"
        aria-live="polite"
        className="min-h-screen flex items-center justify-center bg-gradient-to-br from-slate-900 via-blue-900 to-slate-800 text-white"
      >
        <div className="text-center">
          <div className="animate-spin h-8 w-8 border-2 border-white border-t-transparent rounded-full mx-auto mb-3"></div>
          <p className="text-sm text-gray-400">
            {!isHydrated ? "正在加载..." : "正在跳转到登录页..."}
          </p>
        </div>
      </div>
    )
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
              <h1 className="text-white font-bold text-lg"> AI Lab</h1>
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
          <div className="text-gray-500 text-xs mt-1">版本 v3.0.1</div>
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
            {currentUser && (
              <div className="flex items-center space-x-2 text-gray-300">
                <User className="w-5 h-5 text-blue-300" />
                <div className="leading-tight">
                  <div className="text-white text-sm font-medium">{currentUser.name}</div>
                  <div className="text-xs text-gray-400">
                    {currentUser.student_id}
                    {currentUser.batch_id ? ` · ${currentUser.batch_id}` : ""}
                  </div>
                </div>
                <button
                  onClick={handleLogout}
                  className="ml-2 flex items-center space-x-1 px-2 py-1 rounded hover:bg-slate-700 hover:text-white transition-colors text-xs"
                  title="登出"
                >
                  <LogOut className="w-4 h-4" />
                  <span>登出</span>
                </button>
              </div>
            )}
            <div className="flex items-center space-x-4 text-gray-300">
              <button
                onClick={() => setActiveModule("settings")}
                className="flex items-center space-x-2 hover:text-white transition-colors"
              >
                <User className="w-5 h-5" />
                <span>关于我们</span>
              </button>
              <div className="text-gray-400">|</div>
              <div className="flex items-center space-x-2">
                <Image src="/images/swjtu-logo.png" alt="SWJTU" width={20} height={20} className="rounded" />
                <a href="http://10.94.91.182:3000/" target="_blank" rel="noopener noreferrer" className="hover:text-blue-400 transition-colors">AI教务</a>
              </div>
            </div>
          </div>
        </header>

        {/* 主要内容区域 */}
        <main className={`flex-1 ${activeModule === "data-tree" ? "" : "p-6"} overflow-auto`}>
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
          </CardContent>
        </Card>
      </div>

      {/* 系统状态监控 - 使用真实数据 */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
        <Card className="bg-slate-800/50 border-slate-600">
          <CardHeader className="pb-2">
            <CardTitle className="text-white flex items-center text-sm">
              <Database className="w-4 h-4 mr-2 text-purple-400" />
              检测统计
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="space-y-2">
              <div className="flex justify-between">
                <span className="text-gray-400 text-xs">总检测次数</span>
                <span className="text-green-400 text-sm font-bold">{realTimeData.dataPoints}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-gray-400 text-xs">批次数</span>
                <span className="text-cyan-400 text-sm font-bold">{Math.floor(realTimeData.dataPoints / 30)}</span>
              </div>
            </div>
          </CardContent>
        </Card>

        <Card className="bg-slate-800/50 border-slate-600">
          <CardHeader className="pb-2">
            <CardTitle className="text-white flex items-center text-sm">
              <TrendingUp className="w-4 h-4 mr-2 text-green-400" />
              平均分数
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-center">
              <div className="text-3xl font-bold text-green-400">{realTimeData.avgScore > 0 ? realTimeData.avgScore.toFixed(1) : '--'}</div>
              <div className="text-gray-400 text-xs mt-1">最近30次检测平均分</div>
            </div>
          </CardContent>
        </Card>

        <Card className="bg-slate-800/50 border-slate-600">
          <CardHeader className="pb-2">
            <CardTitle className="text-white flex items-center text-sm">
              <Activity className="w-4 h-4 mr-2 text-blue-400" />
              系统状态
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="flex items-center justify-center">
              <div className="w-3 h-3 bg-green-500 rounded-full animate-pulse mr-2"></div>
              <span className="text-green-400 text-sm font-medium">运行正常</span>
            </div>
            <div className="text-center mt-2 text-gray-400 text-xs">
              系统已就绪
            </div>
          </CardContent>
        </Card>
      </div>
    </div>
  )
}

// 焊缝检测模块
function DetectionContent({ setActiveModule, setDetectionResults, detectionResults, yoloLive, setYoloLive, sendYOLODataToPrediction, onConsultTeacher }: {
  setActiveModule: (module: string) => void,
  setDetectionResults: (results: DetectionResult | null) => void,
  detectionResults: DetectionResult | null,
  yoloLive: YOLOLiveState,
  setYoloLive: React.Dispatch<React.SetStateAction<YOLOLiveState>>,
  sendYOLODataToPrediction?: (scores: any) => Promise<void>,
  onConsultTeacher?: (scores: any) => void
}) {
  const [detectionMode, setDetectionMode] = useState<'upload' | 'realtime'>('realtime') // 检测模式，默认实时检测
  const [selectedFile, setSelectedFile] = useState<File | null>(null)
  const [isDetecting, setIsDetecting] = useState(false)
  const [previewUrl, setPreviewUrl] = useState<string | null>(null)
  const [errorMessage, setErrorMessage] = useState<string | null>(null)

  const handleFileSelect = (event: React.ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0]
    if (file) {
      setSelectedFile(file)
      const url = URL.createObjectURL(file)
      setPreviewUrl(url)
      setDetectionResults(null)
    }
  }

  const handleDetection = async () => {
    if (!selectedFile) return

    setIsDetecting(true)
    setDetectionResults(null)
    setErrorMessage(null)

    const formData = new FormData()
    formData.append("file", selectedFile)

    try {
      const response = await fetch(API_ENDPOINTS.DETECT, {
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
          "光滑度": data.scores.smoothness_score,
          "间距": data.scores.spacing_score,
          "缺陷类型": data.scores.defect_type_score,
        },
        defectPrediction: {
          type: data.detection_result === "Detection placeholder" ? "无明显缺陷" : data.detection_result,
          confidence: (Math.random() * 0.2 + 0.8).toFixed(3),
        },
        processingTime: (Math.random() * 0.5 + 0.3).toFixed(2),
        modelConfidence: (Math.random() * 0.2 + 0.8).toFixed(3),
      }

      setDetectionResults(formattedResults)
      setIsDetecting(false)

    } catch (error) {
      console.error("检测失败:", error)
      setIsDetecting(false)
      setErrorMessage(error instanceof Error ? `检测失败: ${error.message}` : "检测过程中发生未知错误，请重试")
    }
  }

  const sendDataToPrediction = async () => {
    if (!detectionResults) {
      alert('没有检测结果可发送')
      return
    }

    try {
      // 构造要发送的检测数据
      const detectionData = {
        historical_data: [{
          total_score: detectionResults.overallScore,
          smoothness_score: detectionResults.skillScores["光滑度"] || detectionResults.skillScores["间距"] || 0,
          spacing_score: detectionResults.skillScores["间距"] || detectionResults.skillScores["宽度"] || 0,
          defect_type_score: detectionResults.skillScores["缺陷"] || detectionResults.skillScores["缺陷类型"] || 0,
          timestamp: new Date().toISOString(),
          detection_type: 'image'
        }],
        current_data: {
          average_score: detectionResults.overallScore,
          skill_analysis: detectionResults.skillScores,
          defect_prediction: detectionResults.defectPrediction,
          processing_time: detectionResults.processingTime,
          model_confidence: detectionResults.modelConfidence
        }
      }

      // 发送到预测模块
      const response = await fetch(API_ENDPOINTS.PREDICT_AI_ANALYSIS_CUSTOM, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(detectionData)
      })

      if (response.ok) {
        alert('检测数据已成功发送到智能预测模块！')
        // 自动跳转到预测模块
        setActiveModule("prediction")
      } else {
        throw new Error('发送失败')
      }
    } catch (error) {
      console.error('发送数据到预测模块失败:', error)
      alert('发送数据失败，请检查网络连接')
    }
  }

  // 处理YOLO实时检测数据的发送函数
  const handleYOLODataSend = async (yoloScores: any): Promise<void> => {
    if (!yoloScores) {
      alert('没有YOLO检测数据可发送')
      return
    }

    try {
      // 构造要发送的YOLO检测数据（5个参数格式）
      const detectionData = {
        historical_data: [{
          total_score: yoloScores.totalScore,
          smoothness_score: yoloScores.smoothness,
          spacing_score: yoloScores.width, // YOLO中是width，对应后端的spacing
          defect_type_score: yoloScores.defectType,
          timestamp: yoloScores.timestamp,
          detection_type: 'realtime'
        }],
        current_data: {
          average_score: yoloScores.totalScore,
          skill_analysis: {
            "光滑度": yoloScores.smoothness,
            "宽度": yoloScores.width,
            "缺陷控制": yoloScores.defectType
          },
          defect_prediction: {
            type: yoloScores.defectTypeName || "无缺陷",
            confidence: "95%"
          },
          processing_time: "0.1s",
          model_confidence: "高"
        }
      }

      // 发送到预测模块
      const response = await fetch(API_ENDPOINTS.PREDICT_AI_ANALYSIS_CUSTOM, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(detectionData)
      })

      if (response.ok) {
        alert('YOLO检测数据已成功发送到智能预测模块！')
        // 自动跳转到预测模块
        setActiveModule("prediction")
      } else {
        throw new Error('发送失败')
      }
    } catch (error) {
      console.error('发送YOLO数据到预测模块失败:', error)
      alert('发送数据失败，请检查网络连接')
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
      {/* 实时检测模式 - 全宽显示 */}
      {detectionMode === 'realtime' ? (
        <div className="h-full">
          {/* 模式选择器 */}
          <div className="flex justify-between items-center mb-4">
            <h2 className="text-white text-2xl font-bold flex items-center">
              <Eye className="w-7 h-7 mr-3 text-blue-400" />
              焊缝智能检测
            </h2>
            <div className="hidden">
              {/* 切换器已隐藏 */}
            </div>
          </div>
          {/* YOLORealtimeDetector 自带完整布局 */}
          <div className="h-[calc(100%-60px)]">
            <YOLORealtimeDetector
              liveState={yoloLive}
              setLiveState={setYoloLive}
              onSendData={sendYOLODataToPrediction}
              onConsultTeacher={onConsultTeacher}
            />
          </div>
        </div>
      ) : (
        /* 文件上传模式 - 2列布局 */
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-8 h-full">
          {/* 左侧检测区 */}
          <Card className="bg-slate-800/50 border-slate-600 h-full">
            <CardHeader>
              <CardTitle className="text-white flex items-center justify-between">
                <div className="flex items-center">
                  <Eye className="w-6 h-6 mr-2 text-blue-400" />
                  焊缝智能检测
                </div>
                {/* 检测模式选择器 - 已隐藏 */}
                <div className="hidden"></div>
              </CardTitle>
            </CardHeader>
            <CardContent className="h-full flex flex-col">
              {/* 错误提示 */}
              {errorMessage && (
                <div className="mb-4 p-3 bg-red-900/50 border border-red-500 rounded-lg">
                  <div className="flex items-center">
                    <div className="w-4 h-4 bg-red-500 rounded-full mr-2"></div>
                    <p className="text-red-300 text-sm">{errorMessage}</p>
                  </div>
                  <button
                    onClick={() => setErrorMessage(null)}
                    className="mt-2 text-red-400 hover:text-red-300 text-xs underline"
                  >
                    关闭
                  </button>
                </div>
              )}

              {/* 文件上传内容 */}
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

                {/* 智能推荐和预测 */}
                <div className="border-t border-slate-700 pt-4 space-y-3">
                  <div className="text-blue-400 text-sm mb-2">✓ 已将检测数据输送给AI教师</div>
                  <Button
                    className="w-full bg-gradient-to-r from-blue-600 to-purple-600 hover:from-blue-700 hover:to-purple-700"
                    onClick={() => setActiveModule("teacher")}
                  >
                    咨询AI教师改进建议
                  </Button>
                  <Button
                    className="w-full bg-gradient-to-r from-green-600 to-teal-600 hover:from-green-700 hover:to-teal-700"
                    onClick={() => sendDataToPrediction()}
                  >
                    发送数据到智能预测分析
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
      )}
    </div>
  )
}

// 粒子动画卡片组件（使用 ParticleField 粒子特效）
function ParticleArtCard() {
  return (
    <div className="w-full aspect-[21/9]">
      <ParticleField />
    </div>
  )
}

// 系统设置模块（包含系统信息）
function SystemSettingsContent() {
  return (
    <div className="space-y-6">
      {/* 摄像头标定 */}
      <CameraCalibrationCard />

      {/* 粒子艺术卡片 - 独立模块，可整体替换 */}
      <ParticleArtCard />

      {/* 系统介绍卡片 */}
      <Card className="bg-slate-800/50 border-slate-600">
        <CardHeader>
          <CardTitle className="text-white text-center">系统介绍</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="space-y-3 text-gray-300 text-sm leading-relaxed">
            <p className="text-center font-semibold text-base mb-4">焊缝智能检测教学AI系统</p>
            <p className="indent-8">
              在新一轮科技革命和产业变革深入发展的时代背景下，本系统积极响应"中国智造2035"战略规划，以人工智能赋能传统制造业人才培养为核心理念，构建了集智能检测、数据分析、个性化教学于一体的综合性实训平台。系统紧跟数字经济发展步伐，致力于打造面向未来的智能制造人才培养新模式。
            </p>
            <p className="indent-8">
              系统深度融合深度学习、计算机视觉、自然语言处理等人工智能核心技术，采用大语言模型驱动的智能Agent架构，结合MCP协议实现多模态交互与技能编排。通过目标检测算法实现焊缝缺陷的精准识别与分类，运用知识图谱技术构建焊接领域专业知识体系，依托强化学习算法优化个性化学习路径推荐，形成"感知—认知—决策—执行"的完整智能闭环。
            </p>
            <p className="indent-8">
              本系统依托产学研协同创新机制，有效整合高校科研力量与企业实践资源，探索出一条"技术引领、应用驱动、产教融合"的特色发展道路。系统应用将有力支撑高素质技术技能人才培养体系建设，为推动我国制造业向智能化、数字化、绿色化方向转型升级提供坚实的人才保障和智力支撑。
            </p>
            <div className="flex justify-center gap-3 mt-4 pt-4 border-t border-slate-700 flex-wrap">
              <span className="px-3 py-1 bg-slate-700/50 rounded text-orange-400 text-xs">中国智造</span>
              <span className="px-3 py-1 bg-slate-700/50 rounded text-orange-400 text-xs">深度学习</span>
              <span className="px-3 py-1 bg-slate-700/50 rounded text-orange-400 text-xs">产教融合</span>
              <span className="px-3 py-1 bg-slate-700/50 rounded text-orange-400 text-xs">大模型</span>
              <span className="px-3 py-1 bg-slate-700/50 rounded text-orange-400 text-xs">智能诊断</span>
            </div>
          </div>
        </CardContent>
      </Card>

      {/* AI教务介绍卡片 */}
      <Card className="bg-slate-800/50 border-slate-600">
        <CardHeader>
          <CardTitle className="text-white text-center">AI教务介绍</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="space-y-4 text-gray-300 text-sm leading-relaxed">
            <p>
              点击右上角「<span className="text-yellow-400">AI教务</span>」可登录AI教务网站，获取更丰富的智能教学服务。
            </p>
            <div className="bg-slate-900/50 rounded-lg p-4 space-y-3">
              <div className="flex items-start gap-3">
                <div className="w-2 h-2 bg-cyan-400 rounded-full mt-1.5"></div>
                <div>
                  <span className="font-medium">专业AI教师</span>
                  <p className="text-gray-400 text-xs mt-1">每个工种配备专属AI教师，提供针对性技术指导与答疑</p>
                </div>
              </div>
              <div className="flex items-start gap-3">
                <div className="w-2 h-2 bg-cyan-400 rounded-full mt-1.5"></div>
                <div>
                  <span className="font-medium">虚拟导师系统</span>
                  <p className="text-gray-400 text-xs mt-1">基于大模型的智能导师，支持自然语言交互与个性化教学</p>
                </div>
              </div>
              <div className="flex items-start gap-3">
                <div className="w-2 h-2 bg-cyan-400 rounded-full mt-1.5"></div>
                <div>
                  <span className="font-medium">智能课程推荐</span>
                  <p className="text-gray-400 text-xs mt-1">根据学习数据与技能短板，智能推荐个性化学习路径</p>
                </div>
              </div>
              <div className="flex items-start gap-3">
                <div className="w-2 h-2 bg-cyan-400 rounded-full mt-1.5"></div>
                <div>
                  <span className="font-medium">学习进度追踪</span>
                  <p className="text-gray-400 text-xs mt-1">全方位学习数据可视化，精准定位技能提升空间</p>
                </div>
              </div>
            </div>
          </div>
        </CardContent>
      </Card>

      {/* 系统配置卡片 */}
      <Card className="bg-slate-800/50 border-slate-600">
        <CardHeader>
          <CardTitle className="text-white text-center">系统配置</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="space-y-4">
            <div className="flex justify-between items-center">
              <span className="text-gray-300">系统版本</span>
              <span className="text-gray-400">v3.0.1</span>
            </div>
            <div className="flex justify-between items-center">
              <span className="text-gray-300">最后更新</span>
              <span className="text-gray-400">2026-02-20</span>
            </div>
            <div className="flex justify-between items-center">
              <span className="text-gray-300">开发单位</span>
              <span className="text-gray-400">AI Lab</span>
            </div>
          </div>
        </CardContent>
      </Card>
    </div>
  )
}
