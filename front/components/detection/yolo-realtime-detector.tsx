"use client"

import { useState, useEffect, useRef } from 'react'
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Camera, CameraOff, Settings, TrendingUp, Upload, Image as ImageIcon } from "lucide-react"
import { API_ENDPOINTS } from "@/lib/api"
import { getPredictionCacheKey } from "@/lib/storage"
import { useDataTree } from '@/components/data-tree/data-tree-context'
import { convertYOLOToTreeData } from '@/components/data-tree/data-adapter'
import { useAuth } from "@/contexts/AuthContext"
import { CameraSelector } from "./camera-selector"
import {
  type CameraChoice,
  readCameraChoice,
  envFallbackChoice,
  describeChoice,
  buildStartBody,
} from "@/lib/camera-config"

export interface YOLODetectionResult {
  smoothness: number;
  width: number;
  defectType: number;
  totalScore: number;
  timestamp: string;
  actualWidth?: number;
  defectTypeName?: string;
  detectedDefects?: string[];
  // 后端在 YOLO 不可用 / 推理失败兜底时会带 is_mock=true，前端用它显示"YOLO 离线"
  isMock?: boolean;
}

// 切模块时检测组件会被卸载，下面这几项必须由父级保活
export interface YOLOLiveState {
  isDetecting: boolean
  currentScores: YOLODetectionResult | null
  videoStreamUrl: string
  uploadedImage: string | null
}

export const initialYOLOLiveState: YOLOLiveState = {
  isDetecting: false,
  currentScores: null,
  videoStreamUrl: '',
  uploadedImage: null,
}

interface YOLORealtimeDetectorProps {
  liveState: YOLOLiveState
  setLiveState: React.Dispatch<React.SetStateAction<YOLOLiveState>>
  onSendData?: (scores: YOLODetectionResult) => void;
  onConsultTeacher?: (scores: YOLODetectionResult) => void;
}

export function YOLORealtimeDetector({ liveState, setLiveState, onSendData, onConsultTeacher }: YOLORealtimeDetectorProps) {
  const { isDetecting, currentScores, videoStreamUrl, uploadedImage } = liveState
  const setIsDetecting = (v: boolean) => setLiveState((s) => ({ ...s, isDetecting: v }))
  const setCurrentScores = (v: YOLODetectionResult | null) => setLiveState((s) => ({ ...s, currentScores: v }))
  const setVideoStreamUrl = (v: string) => setLiveState((s) => ({ ...s, videoStreamUrl: v }))
  const setUploadedImage = (v: string | null) => setLiveState((s) => ({ ...s, uploadedImage: v }))

  // 这几项重进就重置即可，不用保活
  const [error, setError] = useState<string>('')
  const [isUploading, setIsUploading] = useState(false)
  const [cameraChoice, setCameraChoice] = useState<CameraChoice>({ mode: "default" })
  const [selectorOpen, setSelectorOpen] = useState(false)
  const fileInputRef = useRef<HTMLInputElement>(null)
  const { addTreeData } = useDataTree()
  const { currentUser } = useAuth()

  // 还原用户上次的选择；没有就看 env 兜底
  useEffect(() => {
    const stored = readCameraChoice()
    setCameraChoice(stored.mode === "default" ? envFallbackChoice() : stored)
  }, [])

  const startYOLODetection = async () => {
    try {
      setError('')
      // 旧的 <img> 若还在挂着 MJPEG，先卸载一次浏览器才会真的断开 socket。
      // React 18 在 await 之后会打断 setState batch，让"无 <img>"那一帧真的渲染出来。
      setVideoStreamUrl('')
      await new Promise((r) => setTimeout(r, 0))
      const body = buildStartBody(cameraChoice)
      const response = await fetch(API_ENDPOINTS.START_YOLO, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(body),
      })

      const result = await response.json()
      if (result.status === 'success' || result.status === 'already_running') {
        // 加 t= 时间戳让浏览器认为是新 URL，触发 <img> 重新连接 MJPEG
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

  const stopYOLODetection = async () => {
    try {
      await fetch(API_ENDPOINTS.STOP_YOLO, { method: 'POST' })
      setVideoStreamUrl('')
    } catch (err) {
      console.error('停止YOLO失败:', err)
    }
  }

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
          detectedDefects: result.data.detected_defects || [],
          isMock: result.data.is_mock === true,
        }
      }
      return null
    } catch (err) {
      console.error('获取YOLO数据失败:', err)
      return null
    }
  }

  const toggleDetection = async () => {
    if (!isDetecting) {
      const success = await startYOLODetection()
      if (success) {
        setIsDetecting(true)
      }
    } else {
      await stopYOLODetection()
      setIsDetecting(false)
    }
  }

  // 定期拉取后端的检测结果。切走模块时 interval 自动清掉，回来时再起一个。
  useEffect(() => {
    let interval: NodeJS.Timeout | null = null

    if (isDetecting) {
      interval = setInterval(async () => {
        const newScores = await fetchYOLOData()
        if (newScores) {
          setCurrentScores(newScores)
        }
      }, 1500)
    }

    return () => {
      if (interval) {
        clearInterval(interval)
      }
    }
  }, [isDetecting])

  // 同时发往预测系统后端和前端数据树（双轨保存）
  const handleSendData = async () => {
    if (!currentScores) {
      alert('暂无检测数据可发送，请先启动检测')
      return
    }

    try {
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

        // 把这个学生的预测缓存清掉，下一次刷新就能看到最新数据
        const ckey = getPredictionCacheKey(currentUser?.student_id)
        localStorage.removeItem(ckey)
        localStorage.removeItem(`${ckey}:time`)

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

  const handleImageUpload = async (event: React.ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0]
    if (!file) return

    setIsUploading(true)
    setError('')

    try {
      const reader = new FileReader()
      reader.onload = async (e) => {
        const base64Image = e.target?.result as string
        setUploadedImage(base64Image)
        // 上传图片走静态检测路径，先把 MJPEG 流停掉
        setVideoStreamUrl('')

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
              detectedDefects: result.data.detected_defects || [],
              isMock: result.data.is_mock === true,
            }
            setCurrentScores(scores)
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

  const switchToRealtimeMode = () => {
    setUploadedImage(null)
    setCurrentScores(null)
  }

  // unmount 时不自动 stop，切走模块也要让检测继续跑。
  // 代价是关 tab 后后端线程不会自停，得手动调 /stop-yolo。

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
      <CameraSelector
        open={selectorOpen}
        onOpenChange={setSelectorOpen}
        onSaved={setCameraChoice}
      />
      <div className="lg:col-span-2">
        <Card className="bg-slate-800/50 border-slate-600 h-full">
          <CardHeader>
            <CardTitle className="text-white flex items-center justify-between">
              <div className="flex items-center">
                <Camera className="w-6 h-6 mr-2 text-blue-400" />
                YOLO实时检测
              </div>
              <div className="flex items-center space-x-2">
                {currentScores?.isMock && (
                  <span
                    className="px-2 py-0.5 text-xs rounded-full bg-red-500/20 text-red-300 border border-red-500/40"
                    title="后端 YOLO 模型未加载，当前数据为随机演示值"
                  >
                    YOLO 离线 · 演示数据
                  </span>
                )}
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
                  onClick={() => setSelectorOpen(true)}
                  title={`当前: ${describeChoice(cameraChoice)}`}
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
                  key={videoStreamUrl}
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