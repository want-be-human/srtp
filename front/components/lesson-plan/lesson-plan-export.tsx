"use client"

import type React from "react"

import { useState, useEffect } from "react"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Users, Target, TrendingUp, FileText, Download, Loader2, RefreshCw } from "lucide-react"
import { API_ENDPOINTS } from "@/lib/api"

// 进度条组件
function ProgressBar({ progress, status }: { progress: number; status: string }) {
  return (
    <div className="w-full mt-4">
      <div className="flex justify-between text-sm text-gray-400 mb-2">
        <span>{status}</span>
        <span>{Math.round(progress)}%</span>
      </div>
      <div className="w-full h-2 bg-slate-700 rounded-full overflow-hidden">
        <div
          className="h-full bg-gradient-to-r from-orange-500 to-orange-400 transition-all duration-300 ease-out"
          style={{ width: `${progress}%` }}
        />
      </div>
    </div>
  )
}

// 自动滚动列表组件 - 显示4条
function AutoScrollList({ items, interval = 3000 }: { items: string[]; interval?: number }) {
  const [currentIndex, setCurrentIndex] = useState(0)
  const [isTransitioning, setIsTransitioning] = useState(false)

  useEffect(() => {
    const timer = setInterval(() => {
      setIsTransitioning(true)
      setTimeout(() => {
        setCurrentIndex((prev) => (prev + 1) % items.length)
        setIsTransitioning(false)
      }, 300)
    }, interval)

    return () => clearInterval(timer)
  }, [items.length, interval])

  // 显示当前项和后续3项（共4条）
  const displayItems = []
  for (let i = 0; i < 4; i++) {
    const idx = (currentIndex + i) % items.length
    displayItems.push(items[idx])
  }

  return (
    <div className="space-y-1.5 h-[180px] overflow-hidden">
      {displayItems.map((item, i) => (
        <div
          key={`${currentIndex}-${i}`}
          className={`p-2 bg-slate-700/40 rounded-lg transition-all duration-300 ${
            isTransitioning && i === 0 ? 'opacity-0 -translate-y-4' : 'opacity-100 translate-y-0'
          }`}
          style={{ transitionDelay: `${i * 50}ms` }}
        >
          <p className="text-sm text-gray-300">• {item}</p>
        </div>
      ))}
    </div>
  )
}

// 下节课计划滚动组件 - 显示完整信息
function AutoScrollLessonPlan({ plans, interval = 5000 }: { plans: any[]; interval?: number }) {
  const [currentIndex, setCurrentIndex] = useState(0)
  const [isTransitioning, setIsTransitioning] = useState(false)

  useEffect(() => {
    const timer = setInterval(() => {
      setIsTransitioning(true)
      setTimeout(() => {
        setCurrentIndex((prev) => (prev + 1) % plans.length)
        setIsTransitioning(false)
      }, 300)
    }, interval)

    return () => clearInterval(timer)
  }, [plans.length, interval])

  const plan = plans[currentIndex]

  return (
    <div className={`space-y-1.5 h-[180px] overflow-hidden transition-all duration-300 ${isTransitioning ? 'opacity-0' : 'opacity-100'}`}>
      <div className="p-2 bg-slate-700/40 rounded-lg">
        <p className="text-sm font-medium text-blue-400">主题</p>
        <p className="text-sm text-gray-300">{plan.主题}</p>
      </div>
      <div className="p-2 bg-slate-700/40 rounded-lg">
        <p className="text-sm font-medium text-green-400">目标</p>
        <p className="text-sm text-gray-300">{plan.目标}</p>
      </div>
      <div className="p-2 bg-slate-700/40 rounded-lg">
        <p className="text-sm font-medium text-yellow-400">重点难点</p>
        <p className="text-sm text-gray-300">{plan.重点难点}</p>
      </div>
      <div className="p-2 bg-slate-700/40 rounded-lg">
        <p className="text-sm font-medium text-purple-400">教学方法</p>
        <p className="text-sm text-gray-300">{plan.教学方法}</p>
      </div>
    </div>
  )
}

// 教学建议轮播文案（暂时写死，后续接后端规则库）
const MOCK_TEACHING_RECOMMENDATIONS = [
  "加强焊接基础知识学习，掌握焊接工艺原理和操作规范",
  "定期进行焊接技能考核，及时发现并改进不足之处",
  "多观摩优秀焊工的操作视频，学习先进的焊接技巧",
  "重视焊接参数的合理选择，根据材料特性调整工艺",
  "加强焊接缺陷识别能力训练，提高质量判断水平",
  "建立科学的评价体系，客观评估学生学习效果",
  "加强焊接安全防护意识，做好个人防护措施",
  "加强焊接变形控制技术的学习和实践",
  "培养学生创新思维，鼓励探索新方法新技术",
  "加强焊接新技术新材料的学习研究",
]

// 下节课计划（同上，等接后端规则库）
const MOCK_LESSON_PLANS = [
  { 主题: "光滑度技能强化训练", 目标: "提升学生光滑度技能至90分以上", 重点难点: "焊缝表面成型质量控制，避免咬边和焊瘤", 教学方法: "演示教学+分组练习+现场指导" },
  { 主题: "缺陷识别与预防训练", 目标: "提升缺陷识别能力，降低缺陷率", 重点难点: "准确识别各类缺陷特征及成因分析", 教学方法: "案例教学+实物展示+小组讨论" },
  { 主题: "全位置焊接综合训练", 目标: "提升学生全位置焊接能力", 重点难点: "平立横仰各位置的操作要领差异", 教学方法: "轮换练习+考核评分+重点辅导" },
  { 主题: "气孔缺陷预防训练", 目标: "减少气孔缺陷的产生", 重点难点: "气体保护效果和焊接参数优化", 教学方法: "原理讲解+参数调整+效果验证" },
  { 主题: "焊接参数优化训练", 目标: "学会根据材料选择最佳焊接参数", 重点难点: "电流电压速度三者的协调配合", 教学方法: "参数试验+数据记录+效果对比" },
]

// 报告数据接口
interface LessonPlanData {
  total_students: number;
  total_detections: number;
  average_score: number;
  skill_analysis: Record<string, number>;
  skill_trends: Record<string, number[]>;
  common_defects: Array<{type: string; frequency: number; severity: string; improvement: string}>;
  defect_trends: Record<string, number>;
  student_progress: Record<string, any>;
  weekly_performance: Array<{week: string; avg_score: number; detections: number; improvement: string}>;
  teaching_recommendations: string[];
  focus_areas: string[];
  next_lesson_plan: {
    主题: string;
    目标: string;
    内容: string[];
    重点: string;
    时长: string;
    评估方式: string;
  };
  generated_at: string;
  report_period: string;
}

export function LessonPlanExportContent() {
  const [lessonData, setLessonData] = useState<LessonPlanData | null>(null)
  const [loading, setLoading] = useState(false)
  const [isExporting, setIsExporting] = useState(false)
  const [exportProgress, setExportProgress] = useState(0)
  const [exportStatus, setExportStatus] = useState("")
  const [isRefreshing, setIsRefreshing] = useState(false)

  // 获取报告数据 - 先显示缓存数据，后台刷新最新数据
  const fetchLessonData = async (showRefreshing = false) => {
    if (showRefreshing) {
      setIsRefreshing(true)
    }

    // 先尝试从本地缓存读取，立即显示（提升用户体验）
    const cachedData = localStorage.getItem('lesson_plan_cache')
    if (cachedData && !showRefreshing) {
      try {
        setLessonData(JSON.parse(cachedData))
        setLoading(false)
      } catch (e) {
        console.warn('报告缓存数据解析失败')
      }
    } else {
      setLoading(true)
    }

    // 无论是否有缓存，都在后台获取最新数据
    try {
      const response = await fetch(API_ENDPOINTS.LESSON_PLAN)
      if (response.ok) {
        const data = await response.json()
        setLessonData(data)
        // 保存到本地缓存
        localStorage.setItem('lesson_plan_cache', JSON.stringify(data))
        localStorage.setItem('lesson_plan_cache_time', Date.now().toString())
      } else {
        console.error("获取报告数据失败:", response.statusText)
      }
    } catch (error) {
      console.error("获取报告数据失败:", error)
    } finally {
      setLoading(false)
      setIsRefreshing(false)
    }
  }

  // 组件加载时获取数据
  useEffect(() => {
    fetchLessonData()

    // 每5秒自动刷新数据（保持数据实时性）
    const refreshInterval = setInterval(() => {
      fetchLessonData(false) // 后台静默刷新
    }, 5000)

    return () => clearInterval(refreshInterval)
  }, [])

  // 生成报告PDF - 异步方式（启动任务 -> 轮询状态 -> 下载）
  const generateEnhancedPDF = async () => {
    if (!lessonData) {
      alert("报告数据未加载，请刷新数据后重试")
      return
    }

    try {
      setIsExporting(true)
      setExportProgress(0)
      setExportStatus("正在启动生成任务...")

      // 1. 启动PDF生成任务
      const startResponse = await fetch(API_ENDPOINTS.LESSON_PLAN_PDF, {
        method: "POST",
        headers: { "Content-Type": "application/json" }
      })

      if (!startResponse.ok) {
        throw new Error("启动PDF生成任务失败")
      }

      const startData = await startResponse.json()
      const taskId = startData.task_id

      if (!taskId) {
        throw new Error("未获取到任务ID")
      }

      setExportStatus("正在生成PDF报告...")

      // 2. 轮询任务状态
      let completed = false
      let pollCount = 0
      const maxPolls = 120 // 最多轮询2分钟（每秒一次）

      while (!completed && pollCount < maxPolls) {
        await new Promise(resolve => setTimeout(resolve, 1000)) // 每秒轮询一次
        pollCount++

        const statusResponse = await fetch(API_ENDPOINTS.PDF_STATUS(taskId))
        if (!statusResponse.ok) {
          throw new Error("查询任务状态失败")
        }

        const statusData = await statusResponse.json()

        // 更新进度
        setExportProgress(statusData.progress || 0)
        setExportStatus(statusData.message || "处理中...")

        if (statusData.status === "completed") {
          completed = true
          setExportProgress(100)
          setExportStatus("正在下载文件...")

          // 3. 下载PDF文件
          const downloadResponse = await fetch(API_ENDPOINTS.PDF_DOWNLOAD(taskId))
          if (!downloadResponse.ok) {
            throw new Error("下载PDF文件失败")
          }

          const blob = await downloadResponse.blob()
          const url = window.URL.createObjectURL(blob)
          const a = document.createElement("a")
          a.href = url
          a.download = `焊接质量分析报告_${new Date().toISOString().slice(0, 10)}.pdf`
          document.body.appendChild(a)
          a.click()
          window.URL.revokeObjectURL(url)
          document.body.removeChild(a)

          setExportStatus("下载完成！")
          setTimeout(() => {
            alert("✅ PDF生成成功！文件已下载")
          }, 300)

        } else if (statusData.status === "failed") {
          throw new Error(statusData.error || "PDF生成失败")
        }
      }

      if (!completed) {
        throw new Error("PDF生成超时（超过2分钟）")
      }

    } catch (error) {
      console.error("生成PDF失败:", error)
      const errorMessage = error instanceof Error ? error.message : "生成PDF失败"
      alert(`❌ ${errorMessage}`)
      setExportProgress(0)
      setExportStatus("")
    } finally {
      setIsExporting(false)
    }
  }

  return (
    <div className="h-full p-6 space-y-6 bg-gradient-to-br from-slate-900 via-blue-900 to-slate-800">
      {/* 页面标题 */}
      <div className="text-center">
        <h2 className="text-4xl font-bold text-white mb-4">数据可视化报告生成中心</h2>
        <p className="text-gray-400 text-lg">自动生成数据可视化报告</p>
      </div>

      {/* 操作按钮区域 - 只保留核心功能 */}
      <div className="flex flex-wrap gap-4 justify-center">
        <Button
          onClick={() => fetchLessonData(true)}
          disabled={loading || isRefreshing}
          className="bg-blue-600 hover:bg-blue-700 text-white px-8 py-4 text-lg"
        >
          {loading || isRefreshing ? (
            <>
              <Loader2 className="mr-2 h-6 w-6 animate-spin" />
              刷新数据中...
            </>
          ) : (
            <>
              <RefreshCw className="mr-2 h-6 w-6" />
              刷新数据
            </>
          )}
        </Button>

        <Button
          onClick={generateEnhancedPDF}
          disabled={isExporting || !lessonData}
          className="bg-gradient-to-r from-orange-600 to-orange-500 hover:from-orange-700 hover:to-orange-600 text-white px-8 py-4 text-lg shadow-lg"
        >
          {isExporting ? (
            <>
              <Loader2 className="mr-2 h-6 w-6 animate-spin" />
              生成PDF中...
            </>
          ) : (
            <>
              <Download className="mr-2 h-6 w-6" />
              生成PDF
            </>
          )}
        </Button>
      </div>

      {/* 进度条显示 */}
      {isExporting && (
        <div className="max-w-md mx-auto">
          <ProgressBar progress={exportProgress} status={exportStatus} />
        </div>
      )}

      {/* 数据概览 - 使用真实数据 */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
        <Card className="bg-gradient-to-br from-gray-900 to-slate-800 border-slate-700">
          <CardContent className="p-6">
            <div className="flex items-center">
              <Users className="h-8 w-8 text-blue-400" />
              <div className="ml-4">
                <p className="text-sm font-medium text-gray-400">学生总数</p>
                <p className="text-2xl font-bold text-white">{lessonData?.total_students ?? 0}</p>
              </div>
            </div>
          </CardContent>
        </Card>

        <Card className="bg-gradient-to-br from-gray-900 to-slate-800 border-slate-700">
          <CardContent className="p-6">
            <div className="flex items-center">
              <Target className="h-8 w-8 text-green-400" />
              <div className="ml-4">
                <p className="text-sm font-medium text-gray-400">检测总数</p>
                <p className="text-2xl font-bold text-white">{lessonData?.total_detections ?? 0}</p>
              </div>
            </div>
          </CardContent>
        </Card>

        <Card className="bg-gradient-to-br from-gray-900 to-slate-800 border-slate-700">
          <CardContent className="p-6">
            <div className="flex items-center">
              <TrendingUp className="h-8 w-8 text-yellow-400" />
              <div className="ml-4">
                <p className="text-sm font-medium text-gray-400">平均得分</p>
                <p className="text-2xl font-bold text-white">{lessonData?.average_score?.toFixed(1) ?? 0}</p>
              </div>
            </div>
          </CardContent>
        </Card>

        <Card className="bg-gradient-to-br from-gray-900 to-slate-800 border-slate-700">
          <CardContent className="p-6">
            <div className="flex items-center">
              <FileText className="h-8 w-8 text-purple-400" />
              <div className="ml-4">
                <p className="text-sm font-medium text-gray-400">教学建议库</p>
                <p className="text-2xl font-bold text-white">{MOCK_TEACHING_RECOMMENDATIONS.length}条</p>
              </div>
            </div>
          </CardContent>
        </Card>
      </div>

      {/* 教学建议预览 - 自动滚动 */}
      {lessonData && (
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          <Card className="bg-gradient-to-br from-gray-900 to-slate-800 border-slate-700 relative overflow-hidden">
            <div className="absolute top-3 right-3 z-10">
              <span className="px-3 py-1 text-xs font-semibold bg-gradient-to-r from-cyan-500 to-blue-500 text-white rounded-full shadow-lg animate-pulse">
                Agent生成
              </span>
            </div>
            <CardHeader>
              <CardTitle className="text-white text-xl">教学建议预览</CardTitle>
            </CardHeader>
            <CardContent className="p-4">
              <AutoScrollList items={MOCK_TEACHING_RECOMMENDATIONS} interval={12000} />
            </CardContent>
          </Card>

          <Card className="bg-gradient-to-br from-gray-900 to-slate-800 border-slate-700 relative overflow-hidden">
            <div className="absolute top-3 right-3 z-10">
              <span className="px-3 py-1 text-xs font-semibold bg-gradient-to-r from-yellow-500 to-orange-500 text-white rounded-full shadow-lg animate-pulse">
                Agent生成
              </span>
            </div>
            <CardHeader>
              <CardTitle className="text-white text-xl">下节课计划</CardTitle>
            </CardHeader>
            <CardContent className="p-4">
              <AutoScrollLessonPlan plans={MOCK_LESSON_PLANS} interval={18000} />
            </CardContent>
          </Card>
        </div>
      )}

      {/* 加载状态 */}
      {loading && !lessonData && (
        <div className="flex items-center justify-center py-12">
          <div className="text-center">
            <Loader2 className="h-8 w-8 animate-spin text-blue-400 mx-auto mb-4" />
            <p className="text-gray-400">正在加载报告数据...</p>
          </div>
        </div>
      )}

      {/* 无数据状态 */}
      {!loading && !lessonData && (
        <div className="flex items-center justify-center py-12">
          <div className="text-center">
            <FileText className="h-12 w-12 text-gray-500 mx-auto mb-4" />
            <p className="text-gray-400 mb-4">暂无报告数据</p>
            <Button onClick={() => fetchLessonData(true)} className="bg-blue-600 hover:bg-blue-700">
              点击加载数据
            </Button>
          </div>
        </div>
      )}

      {/* 提示信息 */}
      {lessonData && (
        <div className="text-center mt-6">
          <p className="text-gray-400 text-sm">
            生成的PDF文件将自动下载到浏览器默认下载目录
          </p>
          <p className="text-gray-500 text-xs mt-2">
            文件名格式: 焊接质量分析报告_日期.pdf
          </p>
        </div>
      )}
    </div>
  )
}