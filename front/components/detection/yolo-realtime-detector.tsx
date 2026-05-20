"use client"

import { useState, useEffect, useRef } from 'react'
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Camera, CameraOff, Settings, TrendingUp, Upload, Image as ImageIcon } from "lucide-react"
import { API_ENDPOINTS } from "@/lib/api"
import { StorageKey, getString, setString, remove } from "@/lib/storage"
import { useDataTree } from '@/components/data-tree/data-tree-context'
import { convertYOLOToTreeData } from '@/components/data-tree/data-adapter'
import { useAuth } from "@/contexts/AuthContext"

// 摄像头来源优先级：localStorage(srtp:camera_url) → NEXT_PUBLIC_CAMERA_URL → 空字符串
// 空字符串告诉后端 fallback 到 camera_id=0（本地 USB / 有线相机）
function resolveCameraUrl(): string {
  const fromStorage = getString(StorageKey.CAMERA_URL, "")
  if (fromStorage) return fromStorage
  return process.env.NEXT_PUBLIC_CAMERA_URL || ""
}

// YOLO检测结果的类型定义
interface YOLODetectionResult {
  smoothness: number;      // 光滑度评分
  width: number;          // 宽度评分
  defectType: number;     // 缺陷类型评分
  totalScore: number;     // 总评分
  timestamp: string;      // 时间戳

  // 详细信息（用于显示）
  actualWidth?: number;   // 实际宽度值(mm)
  defectTypeName?: string; // 缺陷类型名称
  detectedDefects?: string[]; // 检测到的缺陷列表
}

interface YOLORealtimeDetectorProps {
  onScoreUpdate?: (scores: YOLODetectionResult) => void;
  onSendData?: (scores: YOLODetectionResult) => void;
  onConsultTeacher?: (scores: YOLODetectionResult) => void;
}

export function YOLORealtimeDetector({ onScoreUpdate, onSendData, onConsultTeacher }: YOLORealtimeDetectorProps) {
  const [isDetecting, setIsDetecting] = useState(false)
  const [currentScores, setCurrentScores] = useState<YOLODetectionResult | null>(null)
  const [error, setError] = useState<string>('')
  const [videoStreamUrl, setVideoStreamUrl] = useState<string>('')
  const [uploadedImage, setUploadedImage] = useState<string | null>(null)
  const [isUploading, setIsUploading] = useState(false)
  const [cameraUrl, setCameraUrl] = useState<string>('')  // 当前生效的摄像头源
  const fileInputRef = useRef<HTMLInputElement>(null)
  const { addTreeData } = useDataTree()
  const { currentUser } = useAuth()

  // 客户端挂载后再读 localStorage / env，避免 SSR 水合不一致
  useEffect(() => {
    setCameraUrl(resolveCameraUrl())
  }, [])

  // 打开 prompt 让用户改摄像头源；保存到 localStorage，空字符串时回退到 env / 后端默认相机
  const handleConfigureCamera = () => {
    const current = resolveCameraUrl()
    const next = window.prompt(
      "摄像头地址（留空使用本地 USB / 有线相机）\n例：http://用户名:密码@IP:端口/",
      current,
    )
    if (next === null) return  // 用户取消
    const trimmed = next.trim()
    if (trimmed) {
      setString(StorageKey.CAMERA_URL, trimmed)
    } else {
      remove(StorageKey.CAMERA_URL)
    }
    setCameraUrl(resolveCameraUrl())
  }

  // 启动后端YOLO检测
  const startYOLODetection = async () => {
    try {
      setError('')
      const activeUrl = resolveCameraUrl()
      // 空字符串时不传 camera_url 字段，让后端走 camera_id=0 默认
      const body: Record<string, unknown> = {}
      if (activeUrl) body.camera_url = activeUrl
      const response = await fetch(API_ENDPOINTS.START_YOLO, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(body),
      })

      const result = await response.json()
      if (result.status === 'success' || result.status === 'already_running') {
        console.log('YOLO检测启动成功:', result.message)
        // 设置视频流URL
        setVideoStreamUrl(`${API_ENDPOINTS.VIDEO_STREAM}?t=${Date.now()}`)
        return true
      } else {
        throw new Error(result.message || '启动YOLO失败')
      }
    } catch (err) {
      console.error('启动YOLO失败:', err)
      setError('无法启动YOLO检测服务')
      return false
    }
  }

  // 停止YOLO检测
  const stopYOLODetection = async () => {
    try {
      const response = await fetch(API_ENDPOINTS.STOP_YOLO, {
        method: 'POST'
      })
      const result = await response.json()
      console.log('YOLO检测停止:', result.message)
      setVideoStreamUrl('')
    } catch (err) {
      console.error('停止YOLO失败:', err)
    }
  }

  // 获取YOLO检测数据
  const fetchYOLOData = async (): Promise<YOLODetectionResult | null> => {
    try {
      const response = await fetch(API_ENDPOINTS.YOLO_DATA)
      const result = await response.json()

      if (result.status === 'success' && result.data) {
        return {
          smoothness: result.data.smoothness,
          width: result.data.width,
          defectType: result.data.defect_type,
          totalScore: result.data.total_score,
          timestamp: new Date(result.data.timestamp * 1000).toISOString(),
          actualWidth: result.data.actual_width,
          defectTypeName: result.data.defect_type_name,
          detectedDefects: result.data.detected_defects || []
        }
      }
      return null
    } catch (err) {
      console.error('获取YOLO数据失败:', err)
      return null
    }
  }

  // 开始/停止检测
  const toggleDetection = async () => {
    if (!isDetecting) {
      // 启动YOLO检测
      const success = await startYOLODetection()
      if (success) {
        setIsDetecting(true)
      }
    } else {
      // 停止检测
      await stopYOLODetection()
      setIsDetecting(false)
    }
  }

  // 检测循环 - 定期获取检测数据
  useEffect(() => {
    let interval: NodeJS.Timeout | null = null

    if (isDetecting) {
      interval = setInterval(async () => {
        const newScores = await fetchYOLOData()
        if (newScores) {
          setCurrentScores(newScores)
          // 回调给父组件
          if (onScoreUpdate) {
            onScoreUpdate(newScores)
          }
        }
      }, 1500) // 每1.5秒获取一次数据（优化API负载）
    }

    return () => {
      if (interval) {
        clearInterval(interval)
      }
    }
  }, [isDetecting, onScoreUpdate])

  // 发送当前数据到后端和数据树
  const handleSendData = async () => {
    if (!currentScores) {
      alert('暂无检测数据可发送，请先启动检测')
      return
    }

    try {
      // 1. 发送到预测系统后端
      const response = await fetch(API_ENDPOINTS.PREDICT_YOLO_DATA, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          total_score: currentScores.totalScore,
          smoothness_score: currentScores.smoothness,
          width_score: currentScores.width,
          defect_score: currentScores.defectType,
          timestamp: currentScores.timestamp,
          actual_width: currentScores.actualWidth,
          defect_type_name: currentScores.defectTypeName,
          student_id: currentUser?.student_id ?? null,
          student_name: currentUser?.name ?? null,
          batch_id: currentUser?.batch_id ?? null,
        })
      })

      if (response.ok) {
        const result = await response.json()

        // 清除前端缓存，确保折线图下次刷新时获取最新数据
        localStorage.removeItem('prediction_cache')
        localStorage.removeItem('prediction_cache_time')
        console.log('已清除预测缓存，折线图将实时更新')

        // 2. 同时发送到数据树
        const treeData = convertYOLOToTreeData({
          total_score: currentScores.totalScore,
          smoothness_score: currentScores.smoothness,
          width_score: currentScores.width,
          defect_score: currentScores.defectType,
          timestamp: currentScores.timestamp,
          actual_width: currentScores.actualWidth,
          defect_type_name: currentScores.defectTypeName
        })
        addTreeData(treeData)

        alert(`✅ 检测数据发送成功！\n• 已存储${result.data_count || 1}条数据到预测系统\n• 数据已添加到3D数据树可视化`)

        // 如果有回调，也调用一下（保持兼容性）
        if (onSendData) {
          onSendData(currentScores)
        }
      } else {
        throw new Error('发送失败')
      }
    } catch (error) {
      console.error('发送数据失败:', error)
      alert('发送数据失败，请检查网络连接')
    }
  }

  // 处理图片上传检测
  const handleImageUpload = async (event: React.ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0]
    if (!file) return

    setIsUploading(true)
    setError('')

    try {
      // 显示上传的图片预览
      const reader = new FileReader()
      reader.onload = async (e) => {
        const base64Image = e.target?.result as string
        setUploadedImage(base64Image)
        setVideoStreamUrl('') // 清除视频流

        // 发送图片到后端检测
        try {
          const response = await fetch(API_ENDPOINTS.DETECT_IMAGE, {
            method: 'POST',
            headers: {
              'Content-Type': 'application/json',
            },
            body: JSON.stringify({
              image_data: base64Image
            })
          })

          const result = await response.json()

          if (result.status === 'success' && result.data) {
            const scores: YOLODetectionResult = {
              smoothness: result.data.smoothness,
              width: result.data.width,
              defectType: result.data.defect_type,
              totalScore: result.data.total_score,
              timestamp: new Date().toISOString(),
              actualWidth: result.data.actual_width,
              defectTypeName: result.data.defect_type_name,
              detectedDefects: result.data.detected_defects || []
            }
            setCurrentScores(scores)
            if (onScoreUpdate) {
              onScoreUpdate(scores)
            }
          } else {
            throw new Error(result.message || '检测失败')
          }
        } catch (err) {
          console.error('图片检测失败:', err)
          setError('图片检测失败，请重试')
        }
      }
      reader.readAsDataURL(file)
    } catch (error) {
      console.error('图片上传失败:', error)
      setError('图片上传失败')
    } finally {
      setIsUploading(false)
    }
  }

  // 切换到实时检测模式
  const switchToRealtimeMode = () => {
    setUploadedImage(null)
    setCurrentScores(null)
  }

  // 组件卸载时清理资源
  useEffect(() => {
    return () => {
      if (isDetecting) {
        stopYOLODetection()
      }
    }
  }, [])

  const getScoreColor = (score: number) => {
    if (score >= 90) return "from-green-500 to-emerald-500"
    if (score >= 80) return "from-blue-500 to-cyan-500"
    if (score >= 70) return "from-yellow-500 to-orange-500"
    return "from-red-500 to-pink-500"
  }

  const getScoreGrade = (score: number) => {
    if (score >= 90) return { text: "优秀", color: "text-green-400" }
    if (score >= 80) return { text: "良好", color: "text-blue-400" }
    if (score >= 70) return { text: "合格", color: "text-yellow-400" }
    return { text: "需改进", color: "text-red-400" }
  }

  return (
    <div className="grid grid-cols-1 lg:grid-cols-3 gap-6 h-full">
      {/* 左侧：摄像头检测区域 */}
      <div className="lg:col-span-2">
        <Card className="bg-slate-800/50 border-slate-600 h-full">
          <CardHeader>
            <CardTitle className="text-white flex items-center justify-between">
              <div className="flex items-center">
                <Camera className="w-6 h-6 mr-2 text-blue-400" />
                YOLO实时检测
              </div>
              <div className="flex items-center space-x-2">
                {isDetecting && (
                  <div className="flex items-center text-green-400 text-sm">
                    <div className="w-2 h-2 bg-green-400 rounded-full animate-pulse mr-2"></div>
                    检测中...
                  </div>
                )}
                <input
                  type="file"
                  ref={fileInputRef}
                  accept="image/*"
                  onChange={handleImageUpload}
                  className="hidden"
                />
                <Button
                  size="sm"
                  className="bg-slate-700 hover:bg-slate-600 text-white border border-slate-500"
                  onClick={handleConfigureCamera}
                  title={cameraUrl ? `当前摄像头: ${cameraUrl}` : "当前: 本地 USB / 有线相机"}
                >
                  <Settings className="w-4 h-4" />
                </Button>
                <Button
                  size="sm"
                  className="bg-slate-700 hover:bg-slate-600 text-white border border-slate-500"
                  onClick={() => fileInputRef.current?.click()}
                  disabled={isUploading}
                >
                  <Upload className="w-4 h-4 mr-1" />
                  {isUploading ? '上传中...' : '上传图片'}
                </Button>
                <Button
                  size="sm"
                  className="bg-slate-700 hover:bg-slate-600 text-white border border-slate-500"
                  onClick={toggleDetection}
                >
                  {isDetecting ? (
                    <>
                      <CameraOff className="w-4 h-4 mr-1" />
                      停止
                    </>
                  ) : (
                    <>
                      <Camera className="w-4 h-4 mr-1" />
                      开始
                    </>
                  )}
                </Button>
              </div>
            </CardTitle>
          </CardHeader>
          <CardContent className="h-[calc(100%-80px)]">
            <div className="relative h-full bg-slate-900 rounded-lg overflow-hidden">
              {uploadedImage ? (
                // 显示上传的图片
                <div className="relative h-full">
                  <img
                    src={uploadedImage}
                    alt="上传的图片"
                    className="w-full h-full object-contain"
                  />
                  {currentScores && (
                    <div className="absolute top-2 left-2 bg-black/70 text-white px-3 py-2 rounded-lg text-sm">
                      <div className="font-bold text-lg">{currentScores.totalScore.toFixed(1)}分</div>
                      <div className="text-xs text-gray-300">图片检测结果</div>
                    </div>
                  )}
                  <Button
                    size="sm"
                    variant="outline"
                    className="absolute top-2 right-2"
                    onClick={switchToRealtimeMode}
                  >
                    <Camera className="w-4 h-4 mr-1" />
                    切换实时
                  </Button>
                </div>
              ) : videoStreamUrl ? (
                <img
                  src={videoStreamUrl}
                  alt="YOLO实时检测视频流"
                  className="w-full h-full object-contain"
                  onError={() => {
                    console.error('视频流加载失败')
                    setError('视频流连接失败')
                  }}
                />
              ) : (
                <div className="flex flex-col items-center justify-center h-full text-gray-400">
                  <Camera className="w-16 h-16 mb-4" />
                  {error ? (
                    <div className="text-center">
                      <p className="text-red-400 mb-2">{error}</p>
                      <Button onClick={toggleDetection} size="sm">重试</Button>
                    </div>
                  ) : (
                    <div className="text-center">
                      <p className="mb-2">点击开始按钮启动实时检测</p>
                      <p className="mb-2 text-sm">或</p>
                      <p className="text-sm text-gray-500">点击上传图片按钮进行图片检测</p>
                    </div>
                  )}
                </div>
              )}
            </div>
          </CardContent>
        </Card>
      </div>

      {/* 右侧：实时检测结果 */}
      <div className="lg:col-span-1">
        <Card className="bg-slate-800/50 border-slate-600 h-full">
          <CardHeader>
            <CardTitle className="text-white flex items-center">
              <TrendingUp className="w-6 h-6 mr-2 text-green-400" />
              实时检测结果
            </CardTitle>
          </CardHeader>
          <CardContent className="h-[calc(100%-80px)] flex flex-col">
            {currentScores ? (
              <div className="space-y-4 flex-1">
                {/* 总分显示 */}
                <div className="text-center bg-slate-900/50 rounded-lg p-4">
                  <div className="relative">
                    <div className={`text-4xl font-bold text-transparent bg-gradient-to-r ${getScoreColor(currentScores.totalScore)} bg-clip-text`}>
                      {currentScores.totalScore}
                      <span className="text-lg text-gray-400 ml-1">分</span>
                    </div>
                  </div>
                  <div className={`text-lg font-bold mt-2 ${getScoreGrade(currentScores.totalScore).color}`}>
                    {getScoreGrade(currentScores.totalScore).text}
                  </div>
                </div>

                {/* 详细分数 */}
                <div className="space-y-3">
                  <div className="bg-slate-900/50 rounded-lg p-3">
                    <div className="flex justify-between items-center">
                      <span className="text-gray-300 text-sm">光滑度</span>
                      <span className={`font-bold ${getScoreGrade(currentScores.smoothness).color}`}>
                        {currentScores.smoothness}
                      </span>
                    </div>
                    <div className="w-full bg-slate-700 rounded-full h-2 mt-2">
                      <div
                        className={`h-2 rounded-full bg-gradient-to-r ${getScoreColor(currentScores.smoothness)}`}
                        style={{ width: `${currentScores.smoothness}%` }}
                      ></div>
                    </div>
                  </div>

                  <div className="bg-slate-900/50 rounded-lg p-3">
                    <div className="flex justify-between items-center">
                      <span className="text-gray-300 text-sm">焊缝宽度</span>
                      <div className="text-right">
                        <div className={`font-bold ${getScoreGrade(currentScores.width).color}`}>
                          {currentScores.width}分
                        </div>
                        <div className="text-xs text-gray-400">
                          {currentScores.actualWidth?.toFixed(1)}mm
                        </div>
                      </div>
                    </div>
                    <div className="w-full bg-slate-700 rounded-full h-2 mt-2">
                      <div
                        className={`h-2 rounded-full bg-gradient-to-r ${getScoreColor(currentScores.width)}`}
                        style={{ width: `${currentScores.width}%` }}
                      ></div>
                    </div>
                  </div>

                  <div className="bg-slate-900/50 rounded-lg p-3">
                    <div className="flex justify-between items-center">
                      <span className="text-gray-300 text-sm">缺陷控制</span>
                      <div className="text-right">
                        <div className={`font-bold ${getScoreGrade(currentScores.defectType).color}`}>
                          {currentScores.defectType}分
                        </div>
                        <div className="text-xs text-gray-400">
                          {currentScores.defectTypeName}
                        </div>
                      </div>
                    </div>
                    <div className="w-full bg-slate-700 rounded-full h-2 mt-2">
                      <div
                        className={`h-2 rounded-full bg-gradient-to-r ${getScoreColor(currentScores.defectType)}`}
                        style={{ width: `${currentScores.defectType}%` }}
                      ></div>
                    </div>
                  </div>
                </div>

                {/* 操作按钮区域 */}
                <div className="border-t border-slate-700 pt-4 space-y-2">
                  <div className="text-green-400 text-sm mb-2 flex items-center">
                    <div className="w-2 h-2 bg-green-400 rounded-full mr-2"></div>
                    实时检测数据已准备
                  </div>
                  <Button
                    className="w-full bg-gradient-to-r from-orange-600 to-pink-600 hover:from-orange-700 hover:to-pink-700"
                    onClick={() => {
                      if (currentScores && onConsultTeacher) {
                        onConsultTeacher(currentScores)
                      } else {
                        alert('暂无检测数据，请先启动检测')
                      }
                    }}
                    disabled={!currentScores}
                  >
                    咨询AI教师
                  </Button>
                  <Button
                    className="w-full bg-gradient-to-r from-green-600 to-teal-600 hover:from-green-700 hover:to-teal-700"
                    onClick={handleSendData}
                    disabled={!currentScores}
                  >
                    发送当前数据到预测系统
                  </Button>
                </div>
              </div>
            ) : (
              <div className="flex-1 flex items-center justify-center text-center text-gray-400">
                <div>
                  <div className="w-16 h-16 border-4 border-slate-600 rounded-full flex items-center justify-center mx-auto mb-4">
                    <TrendingUp className="w-8 h-8" />
                  </div>
                  <p>等待检测数据...</p>
                  <p className="text-sm text-gray-500 mt-2">启动检测后将显示实时分数</p>
                </div>
              </div>
            )}
          </CardContent>
        </Card>
      </div>
    </div>
  )
}