"use client"

import type React from "react"

import { useState, useRef } from "react"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { PieChart, TrendingUp, FileText, Calendar, Download, ImageIcon, FileDown } from "lucide-react"

export function DataAnalysisContent() {
  const [isExporting, setIsExporting] = useState(false)
  const reportRef = useRef<HTMLDivElement>(null)

  // 为每个图表创建ref
  const qualityChartRef = useRef<HTMLDivElement>(null)
  const trendChartRef = useRef<HTMLDivElement>(null)
  const recentRecordsRef = useRef<HTMLDivElement>(null)

  // 模拟数据
  const detectionStats = {
    total: 156,
    excellent: 89,
    good: 45,
    poor: 22,
    todayDetections: 23,
  }

  const reportData = {
    totalDetections: 156,
    averageScore: 84.2,
    excellentRate: 57.1,
    improvementRate: 12.3,
    defectReduction: 23.5,
    studentProgress: 89.4,
  }

  const recentDetections = [
    { id: 1, time: "14:30", filename: "weld_001.jpg", score: 92, grade: "优", defects: "无明显缺陷" },
    { id: 2, time: "14:15", filename: "weld_002.jpg", score: 78, grade: "良", defects: "轻微气孔" },
    { id: 3, time: "14:00", filename: "weld_003.jpg", score: 65, grade: "差", defects: "焊缝不均匀" },
    { id: 4, time: "13:45", filename: "weld_004.jpg", score: 88, grade: "优", defects: "质量良好" },
    { id: 5, time: "13:30", filename: "weld_005.jpg", score: 82, grade: "良", defects: "边缘略粗糙" },
  ]

  const weeklyTrend = [
    { day: "周一", detections: 18, score: 85 },
    { day: "周二", detections: 25, score: 88 },
    { day: "周三", detections: 22, score: 82 },
    { day: "周四", detections: 30, score: 91 },
    { day: "周五", detections: 28, score: 87 },
    { day: "周六", detections: 20, score: 89 },
    { day: "周日", detections: 13, score: 86 },
  ]

  const exportOptions = [
    {
      title: "完整分析报告",
      description: "包含所有图表和数据的综合报告",
      format: "PDF",
      icon: FileDown,
      color: "bg-red-600 hover:bg-red-700",
    },
    {
      title: "数据统计表格",
      description: "原始数据和统计结果的表格文件",
      format: "Excel",
      icon: Download,
      color: "bg-green-600 hover:bg-green-700",
    },
  ]

  // 导出单个图表为图片
  const exportChartAsImage = async (elementRef: React.RefObject<HTMLDivElement>, filename: string) => {
    if (!elementRef.current) return

    try {
      setIsExporting(true)

      // 动态导入html2canvas
      const html2canvas = (await import("html2canvas")).default

      const canvas = await html2canvas(elementRef.current, {
        backgroundColor: "#0f172a", // 深色背景
        scale: 2, // 高分辨率
        useCORS: true,
        allowTaint: true,
      })

      // 创建下载链接
      const link = document.createElement("a")
      link.download = `${filename}_${new Date().toISOString().split("T")[0]}.png`
      link.href = canvas.toDataURL("image/png")
      link.click()
    } catch (error) {
      console.error("导出图片失败:", error)
      alert("导出图片失败，请重试")
    } finally {
      setIsExporting(false)
    }
  }

  // 导出所有图表为PDF
  const exportAllChartsAsPDF = async () => {
    try {
      setIsExporting(true)

      // 动态导入所需库
      const [{ default: html2canvas }, { default: jsPDF }] = await Promise.all([import("html2canvas"), import("jspdf")])

      const pdf = new jsPDF("p", "mm", "a4")
      const pageWidth = pdf.internal.pageSize.getWidth()
      const pageHeight = pdf.internal.pageSize.getHeight()

      // 添加标题页
      pdf.setFontSize(20)
      pdf.setTextColor(59, 130, 246) // 蓝色
      pdf.text("焊缝智能检测教学AI系统", pageWidth / 2, 30, { align: "center" })

      pdf.setFontSize(16)
      pdf.setTextColor(0, 0, 0)
      pdf.text("数据分析报告", pageWidth / 2, 45, { align: "center" })

      pdf.setFontSize(12)
      pdf.text(`生成时间: ${new Date().toLocaleString("zh-CN")}`, pageWidth / 2, 60, { align: "center" })

      // 添加统计概览
      pdf.setFontSize(14)
      pdf.text("数据概览", 20, 80)
      pdf.setFontSize(10)
      pdf.text(`总检测次数: ${reportData.totalDetections}`, 20, 95)
      pdf.text(`平均分数: ${reportData.averageScore}`, 20, 105)
      pdf.text(`优秀率: ${reportData.excellentRate}%`, 20, 115)
      pdf.text(`技能提升率: ${reportData.improvementRate}%`, 20, 125)
      pdf.text(`缺陷减少率: ${reportData.defectReduction}%`, 20, 135)
      pdf.text(`学生进步率: ${reportData.studentProgress}%`, 20, 145)

      const charts = [
        { ref: qualityChartRef, title: "焊缝质量分布" },
        { ref: trendChartRef, title: "本周检测趋势" },
        { ref: recentRecordsRef, title: "最近检测记录" },
      ]

      for (let i = 0; i < charts.length; i++) {
        const chart = charts[i]
        if (!chart.ref.current) continue

        // 为每个图表添加新页面
        if (i > 0 || true) {
          // 第一个图表也新开页面
          pdf.addPage()
        }

        // 添加图表标题
        pdf.setFontSize(16)
        pdf.setTextColor(59, 130, 246)
        pdf.text(chart.title, pageWidth / 2, 20, { align: "center" })

        try {
          const canvas = await html2canvas(chart.ref.current, {
            backgroundColor: "#0f172a",
            scale: 1.5,
            useCORS: true,
            allowTaint: true,
          })

          const imgData = canvas.toDataURL("image/png")
          const imgWidth = pageWidth - 40 // 左右边距各20mm
          const imgHeight = (canvas.height * imgWidth) / canvas.width

          // 如果图片太高，调整尺寸
          const maxHeight = pageHeight - 60 // 上下边距
          const finalHeight = Math.min(imgHeight, maxHeight)
          const finalWidth = (canvas.width * finalHeight) / canvas.height

          pdf.addImage(imgData, "PNG", (pageWidth - finalWidth) / 2, 30, finalWidth, finalHeight)
        } catch (error) {
          console.error(`导出图表 ${chart.title} 失败:`, error)
          pdf.setFontSize(12)
          pdf.setTextColor(255, 0, 0)
          pdf.text(`图表导出失败: ${chart.title}`, 20, 50)
        }
      }

      // 保存PDF
      pdf.save(`焊缝检测数据分析报告_${new Date().toISOString().split("T")[0]}.pdf`)
    } catch (error) {
      console.error("导出PDF失败:", error)
      alert("导出PDF失败，请重试")
    } finally {
      setIsExporting(false)
    }
  }

  // 导出数据为Excel格式的CSV
  const exportDataAsCSV = () => {
    try {
      setIsExporting(true)

      let csvContent = "\uFEFF" // BOM for UTF-8

      // 添加标题
      csvContent += "焊缝智能检测教学AI系统 - 数据分析报告\n"
      csvContent += `生成时间,${new Date().toLocaleString("zh-CN")}\n\n`

      // 添加统计概览
      csvContent += "数据概览\n"
      csvContent += "指标,数值,占比\n"
      csvContent += `总检测次数,${reportData.totalDetections},100%\n`
      csvContent += `平均分数,${reportData.averageScore},-\n`
      csvContent += `优秀率,${reportData.excellentRate}%,-\n`
      csvContent += `技能提升率,${reportData.improvementRate}%,-\n`
      csvContent += `缺陷减少率,${reportData.defectReduction}%,-\n`
      csvContent += `学生进步率,${reportData.studentProgress}%,-\n\n`

      // 添加最近检测记录
      csvContent += "最近检测记录\n"
      csvContent += "时间,文件名,分数,等级,缺陷描述\n"
      recentDetections.forEach((record) => {
        csvContent += `${record.time},"${record.filename}",${record.score},"${record.grade}","${record.defects}"\n`
      })

      // 创建下载链接
      const blob = new Blob([csvContent], { type: "text/csv;charset=utf-8;" })
      const link = document.createElement("a")
      link.href = URL.createObjectURL(blob)
      link.download = `焊缝检测数据分析_${new Date().toISOString().split("T")[0]}.csv`
      link.click()

      URL.revokeObjectURL(link.href)
    } catch (error) {
      console.error("导出CSV失败:", error)
      alert("导出数据失败，请重试")
    } finally {
      setIsExporting(false)
    }
  }

  // 导出功能
  const handleExport = async (type: string) => {
    if (type === "完整分析报告") {
      await exportAllChartsAsPDF()
    } else if (type === "数据统计表格") {
      exportDataAsCSV()
    }
  }

  // 优化的饼图组件
  const PieChartComponent = ({ data, title }: { data: any[]; title: string }) => {
    const total = data.reduce((sum, item) => sum + item.value, 0)
    let currentAngle = 0

    return (
      <div className="flex flex-col items-center">
        <h4 className="text-white font-semibold mb-6 text-lg">{title}</h4>
        <div className="relative w-56 h-56">
          <svg className="w-full h-full transform -rotate-90" viewBox="0 0 100 100">
            {/* 外圈装饰 */}
            <circle cx="50" cy="50" r="42" fill="none" stroke="#374151" strokeWidth="0.5" opacity="0.3" />

            {data.map((item, index) => {
              const percentage = (item.value / total) * 100
              const angle = (percentage / 100) * 360
              const x1 = 50 + 38 * Math.cos((currentAngle * Math.PI) / 180)
              const y1 = 50 + 38 * Math.sin((currentAngle * Math.PI) / 180)
              const x2 = 50 + 38 * Math.cos(((currentAngle + angle) * Math.PI) / 180)
              const y2 = 50 + 38 * Math.sin(((currentAngle + angle) * Math.PI) / 180)

              const largeArcFlag = angle > 180 ? 1 : 0
              const pathData = `M 50 50 L ${x1} ${y1} A 38 38 0 ${largeArcFlag} 1 ${x2} ${y2} Z`

              const result = (
                <path
                  key={index}
                  d={pathData}
                  fill={item.color}
                  className="hover:opacity-80 transition-all duration-300 cursor-pointer"
                  style={{ filter: "drop-shadow(0 2px 4px rgba(0,0,0,0.3))" }}
                />
              )

              currentAngle += angle
              return result
            })}
          </svg>
          <div className="absolute inset-0 flex items-center justify-center">
            <div className="text-center bg-slate-800/80 rounded-full w-20 h-20 flex flex-col items-center justify-center">
              <div className="text-2xl font-bold text-white">{total}</div>
              <div className="text-gray-400 text-xs">总计</div>
            </div>
          </div>
        </div>
        <div className="mt-6 grid grid-cols-1 gap-3 w-full">
          {data.map((item, index) => (
            <div key={index} className="flex items-center justify-between p-3 bg-slate-700/30 rounded-lg">
              <div className="flex items-center space-x-3">
                <div className={`w-4 h-4 rounded-full shadow-lg`} style={{ backgroundColor: item.color }}></div>
                <span className="text-gray-200 font-medium">{item.label}</span>
              </div>
              <div className="text-right">
                <div className="text-white font-bold">{item.value}</div>
                <div className="text-gray-400 text-xs">{Math.round((item.value / total) * 100)}%</div>
              </div>
            </div>
          ))}
        </div>
      </div>
    )
  }

  // 优化的柱状图组件
  const BarChartComponent = ({ data, title, colors }: { data: any[]; title: string; colors: string[] }) => {
    const maxValue = Math.max(...data.map((item) => item.value))

    return (
      <div className="flex flex-col h-full">
        <h4 className="text-white font-semibold mb-6 text-lg">{title}</h4>
        <div className="flex-1 flex items-end justify-center">
          <div className="flex items-end space-x-4 h-64 w-full max-w-md">
            {data.map((item, index) => (
              <div key={index} className="flex flex-col items-center flex-1 group">
                <div className="flex items-end h-52 w-full justify-center">
                  <div
                    className={`rounded-t-lg transition-all duration-700 hover:opacity-80 cursor-pointer shadow-lg`}
                    style={{
                      height: `${(item.value / maxValue) * 100}%`,
                      background: `linear-gradient(to top, ${colors[index % colors.length]}, ${colors[index % colors.length]}dd)`,
                      width: "32px",
                      minHeight: "8px",
                    }}
                  ></div>
                </div>
                <div className="mt-3 text-center">
                  <div className="text-white font-bold text-lg">{item.value}</div>
                  <div className="text-gray-400 text-sm font-medium">{item.label}</div>
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>
    )
  }

  // 优化的折线图组件
  const LineChartComponent = ({ data, title }: { data: any[]; title: string }) => {
    const maxDetections = Math.max(...data.map((item) => item.detections))
    const maxScore = Math.max(...data.map((item) => item.score))
    const minScore = Math.min(...data.map((item) => item.score))

    const getDetectionY = (value: number) => 140 - (value / maxDetections) * 120
    const getScoreY = (value: number) => 140 - ((value - minScore) / (maxScore - minScore)) * 120

    return (
      <div className="flex flex-col">
        <div className="flex items-center justify-between mb-6">
          <h4 className="text-white font-semibold text-lg">{title}</h4>
          {/* 图例移到右上角 */}
          <div className="flex space-x-6">
            <div className="flex items-center space-x-2">
              <div className="w-4 h-4 bg-gradient-to-r from-cyan-400 to-cyan-500 rounded-full shadow-lg"></div>
              <span className="text-gray-300 font-medium">检测次数</span>
            </div>
            <div className="flex items-center space-x-2">
              <div className="w-4 h-4 bg-gradient-to-r from-amber-400 to-amber-500 rounded-full shadow-lg"></div>
              <span className="text-gray-300 font-medium">平均分数</span>
            </div>
          </div>
        </div>

        <div className="relative h-48 bg-gradient-to-br from-slate-900/80 to-slate-800/80 rounded-xl p-6 border border-slate-700/50">
          <svg className="w-full h-full" viewBox="0 0 400 140">
            {/* 优化的网格线 */}
            {[0, 1, 2, 3, 4].map((i) => (
              <line
                key={i}
                x1="0"
                y1={i * 35}
                x2="400"
                y2={i * 35}
                stroke="#475569"
                strokeWidth="0.5"
                opacity="0.4"
                strokeDasharray="2,2"
              />
            ))}

            {/* 检测次数区域填充 */}
            <defs>
              <linearGradient id="detectionGradient" x1="0%" y1="0%" x2="0%" y2="100%">
                <stop offset="0%" stopColor="#06b6d4" stopOpacity="0.3" />
                <stop offset="100%" stopColor="#06b6d4" stopOpacity="0.05" />
              </linearGradient>
            </defs>

            <polygon
              points={`0,140 ${data
                .map((item, index) => `${(index * 400) / (data.length - 1)},${getDetectionY(item.detections)}`)
                .join(" ")} 400,140`}
              fill="url(#detectionGradient)"
            />

            {/* 检测次数折线 */}
            <polyline
              points={data
                .map((item, index) => `${(index * 400) / (data.length - 1)},${getDetectionY(item.detections)}`)
                .join(" ")}
              fill="none"
              stroke="#06b6d4"
              strokeWidth="3"
              style={{ filter: "drop-shadow(0 2px 4px rgba(6, 182, 212, 0.3))" }}
            />

            {/* 平均分数折线 */}
            <polyline
              points={data
                .map((item, index) => `${(index * 400) / (data.length - 1)},${getScoreY(item.score)}`)
                .join(" ")}
              fill="none"
              stroke="#f59e0b"
              strokeWidth="3"
              style={{ filter: "drop-shadow(0 2px 4px rgba(245, 158, 11, 0.3))" }}
            />

            {/* 数据点 */}
            {data.map((item, index) => (
              <g key={index}>
                <circle
                  cx={(index * 400) / (data.length - 1)}
                  cy={getDetectionY(item.detections)}
                  r="4"
                  fill="#06b6d4"
                  stroke="#ffffff"
                  strokeWidth="2"
                  className="cursor-pointer hover:r-6 transition-all"
                />
                <circle
                  cx={(index * 400) / (data.length - 1)}
                  cy={getScoreY(item.score)}
                  r="4"
                  fill="#f59e0b"
                  stroke="#ffffff"
                  strokeWidth="2"
                  className="cursor-pointer hover:r-6 transition-all"
                />
              </g>
            ))}
          </svg>

          {/* X轴标签 */}
          <div className="flex justify-between mt-4">
            {data.map((item, index) => (
              <span key={index} className="text-sm text-gray-400 font-medium">
                {item.day}
              </span>
            ))}
          </div>
        </div>
      </div>
    )
  }

  return (
    <div className="h-full p-6 space-y-8">
      {/* 页面标题 */}
      <div className="text-center">
        <h2 className="text-4xl font-bold text-white mb-4">分析报告导出中心</h2>
        <p className="text-gray-400 text-lg">一键导出各类数据分析报告，支持多种格式</p>
      </div>

      {/* 标题和导出按钮 */}
      <div className="flex justify-between items-center">
        <h2 className="text-3xl font-bold text-white">数据分析总览</h2>
        <div className="flex items-center space-x-4">
          {/* 导出按钮组 */}
          <div className="flex space-x-2">
            {exportOptions.map((option, index) => (
              <Button
                key={index}
                onClick={() => handleExport(option.title)}
                disabled={isExporting}
                className={`w-full ${option.color} text-white font-medium`}
              >
                {isExporting ? (
                  <div className="flex items-center">
                    <div className="animate-spin rounded-full h-4 w-4 border-b-2 border-white mr-2"></div>
                    导出中...
                  </div>
                ) : (
                  `导出${option.format}`
                )}
              </Button>
            ))}
          </div>
        </div>
      </div>

      {/* 数据概览卡片 */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
        <Card className="bg-gradient-to-br from-blue-800/80 to-blue-700/80 border-blue-600/50 backdrop-blur-sm">
          <CardContent className="p-6 text-center">
            <div className="text-3xl font-bold text-blue-400 mb-2">{reportData.totalDetections}</div>
            <div className="text-gray-300 font-medium">总检测次数</div>
          </CardContent>
        </Card>

        <Card className="bg-gradient-to-br from-green-800/80 to-green-700/80 border-green-600/50 backdrop-blur-sm">
          <CardContent className="p-6 text-center">
            <div className="text-3xl font-bold text-green-400 mb-2">{reportData.averageScore}</div>
            <div className="text-gray-300 font-medium">平均分数</div>
          </CardContent>
        </Card>

        <Card className="bg-gradient-to-br from-purple-800/80 to-purple-700/80 border-purple-600/50 backdrop-blur-sm">
          <CardContent className="p-6 text-center">
            <div className="text-3xl font-bold text-purple-400 mb-2">{reportData.excellentRate}%</div>
            <div className="text-gray-300 font-medium">优秀率</div>
          </CardContent>
        </Card>
      </div>

      {/* 焊缝质量分布 */}
      <Card
        className="bg-gradient-to-br from-slate-800/80 to-slate-700/80 border-slate-600/50 backdrop-blur-sm"
        ref={qualityChartRef}
      >
        <CardHeader className="flex flex-row items-center justify-between">
          <CardTitle className="text-white flex items-center text-xl">
            <PieChart className="w-7 h-7 mr-3 text-emerald-400" />
            焊缝质量分布
          </CardTitle>
          <Button
            onClick={() => exportChartAsImage(qualityChartRef, "焊缝质量分布")}
            disabled={isExporting}
            variant="outline"
            size="sm"
            className="border-slate-600 text-gray-300 hover:bg-slate-700"
          >
            <ImageIcon className="w-4 h-4 mr-2" />
            导出图片
          </Button>
        </CardHeader>
        <CardContent className="p-8">
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-12">
            {/* 左侧柱状图 */}
            <div>
              <BarChartComponent
                data={[
                  { label: "优秀", value: detectionStats.excellent },
                  { label: "良好", value: detectionStats.good },
                  { label: "待改进", value: detectionStats.poor },
                ]}
                title="质量分布统计"
                colors={["#10b981", "#f59e0b", "#ef4444"]}
              />
            </div>

            {/* 右侧饼图 */}
            <div>
              <PieChartComponent
                data={[
                  { label: "优秀 (90-100分)", value: detectionStats.excellent, color: "#10b981" },
                  { label: "良好 (75-89分)", value: detectionStats.good, color: "#f59e0b" },
                  { label: "待改进 (60-74分)", value: detectionStats.poor, color: "#ef4444" },
                ]}
                title="质量分布占比"
              />
            </div>
          </div>
        </CardContent>
      </Card>

      {/* 检测趋势折线图 */}
      <Card
        className="bg-gradient-to-br from-slate-800/80 to-slate-700/80 border-slate-600/50 backdrop-blur-sm"
        ref={trendChartRef}
      >
        <CardHeader className="flex flex-row items-center justify-between">
          <CardTitle className="text-white flex items-center text-xl">
            <TrendingUp className="w-7 h-7 mr-3 text-purple-400" />
            本周检测趋势
          </CardTitle>
          <Button
            onClick={() => exportChartAsImage(trendChartRef, "本周检测趋势")}
            disabled={isExporting}
            variant="outline"
            size="sm"
            className="border-slate-600 text-gray-300 hover:bg-slate-700"
          >
            <ImageIcon className="w-4 h-4 mr-2" />
            导出图片
          </Button>
        </CardHeader>
        <CardContent className="p-8">
          <LineChartComponent data={weeklyTrend} title="检测次数与平均分数趋势" />
        </CardContent>
      </Card>

      {/* 最近检测记录 */}
      <Card
        className="bg-gradient-to-br from-slate-800/80 to-slate-700/80 border-slate-600/50 backdrop-blur-sm"
        ref={recentRecordsRef}
      >
        <CardHeader className="flex flex-row items-center justify-between">
          <CardTitle className="text-white flex items-center text-xl">
            <Calendar className="w-7 h-7 mr-3 text-cyan-400" />
            最近检测记录
          </CardTitle>
          <Button
            onClick={() => exportChartAsImage(recentRecordsRef, "最近检测记录")}
            disabled={isExporting}
            variant="outline"
            size="sm"
            className="border-slate-600 text-gray-300 hover:bg-slate-700"
          >
            <ImageIcon className="w-4 h-4 mr-2" />
            导出图片
          </Button>
        </CardHeader>
        <CardContent className="p-6">
          <div className="space-y-4">
            {recentDetections.map((detection) => (
              <div
                key={detection.id}
                className="flex items-center justify-between p-4 bg-slate-700/40 rounded-lg border border-slate-600/30 hover:bg-slate-700/60 transition-all"
              >
                <div className="flex items-center space-x-4">
                  <div className="w-14 h-14 bg-gradient-to-br from-slate-600 to-slate-700 rounded-xl flex items-center justify-center shadow-lg">
                    <FileText className="w-7 h-7 text-gray-300" />
                  </div>
                  <div>
                    <div className="text-white font-semibold text-lg">{detection.filename}</div>
                    <div className="text-gray-400 text-sm">检测时间: {detection.time}</div>
                    <div className="text-gray-500 text-xs mt-1">{detection.defects}</div>
                  </div>
                </div>
                <div className="text-right">
                  <div
                    className={`text-2xl font-bold ${
                      detection.grade === "优"
                        ? "text-green-400"
                        : detection.grade === "良"
                          ? "text-yellow-400"
                          : "text-red-400"
                    }`}
                  >
                    {detection.score}分
                  </div>
                  <div
                    className={`text-sm font-medium ${
                      detection.grade === "优"
                        ? "text-green-400"
                        : detection.grade === "良"
                          ? "text-yellow-400"
                          : "text-red-400"
                    }`}
                  >
                    {detection.grade}
                  </div>
                </div>
              </div>
            ))}
          </div>
        </CardContent>
      </Card>

      {/* 报告预览 */}
      <Card className="bg-gradient-to-br from-slate-800/80 to-slate-700/80 border-slate-600/50 backdrop-blur-sm">
        <CardHeader>
          <CardTitle className="text-white text-xl">报告内容预览</CardTitle>
        </CardHeader>
        <CardContent className="p-6">
          <div ref={reportRef} className="space-y-6">
            {/* 关键指标展示 */}
            <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
              <div className="bg-slate-700/30 rounded-lg p-4 text-center">
                <div className="text-2xl font-bold text-cyan-400">{reportData.improvementRate}%</div>
                <div className="text-gray-400 text-sm">技能提升率</div>
              </div>
              <div className="bg-slate-700/30 rounded-lg p-4 text-center">
                <div className="text-2xl font-bold text-green-400">{reportData.defectReduction}%</div>
                <div className="text-gray-400 text-sm">缺陷减少率</div>
              </div>
              <div className="bg-slate-700/30 rounded-lg p-4 text-center">
                <div className="text-2xl font-bold text-yellow-400">{reportData.studentProgress}%</div>
                <div className="text-gray-400 text-sm">学生进步率</div>
              </div>
              <div className="bg-slate-700/30 rounded-lg p-4 text-center">
                <div className="text-2xl font-bold text-purple-400">A+</div>
                <div className="text-gray-400 text-sm">系统评级</div>
              </div>
            </div>

            {/* 报告内容说明 */}
            <div className="bg-slate-700/20 rounded-lg p-6">
              <h4 className="text-white font-semibold mb-4">报告将包含以下内容：</h4>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4 text-gray-300 text-sm">
                <div className="space-y-2">
                  <div>• 焊缝质量分布统计</div>
                  <div>• 学生技能发展趋势</div>
                  <div>• 检测准确率评估</div>
                </div>
                <div className="space-y-2">
                  <div>• 缺陷类型分布分析</div>
                  <div>• 教学效果评估报告</div>
                  <div>• 系统使用情况统计</div>
                  <div>• 改进建议与展望</div>
                </div>
              </div>
            </div>
          </div>
        </CardContent>
      </Card>
    </div>
  )
}
