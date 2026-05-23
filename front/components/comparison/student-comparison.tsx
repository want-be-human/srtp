"use client"

import React, { useEffect, useMemo, useState } from "react"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Trophy, User, Swords, RefreshCw, Info } from "lucide-react"
import {
  RadarChart,
  Radar,
  PolarGrid,
  PolarAngleAxis,
  PolarRadiusAxis,
  ResponsiveContainer,
  Legend,
  Tooltip,
} from "recharts"
import { API_ENDPOINTS } from "@/lib/api"
import { useAuth } from "@/contexts/AuthContext"
import type { TreeData } from "@/components/data-tree/data-tree-context"
import { DataTreeViewer } from "@/components/data-tree/data-tree-viewer"
import { convertYOLOToTreeData } from "@/components/data-tree/data-adapter"
import { DefectHeatmap } from "@/components/comparison/defect-heatmap"

interface StudentStats {
  student_id: string
  student_name: string
  batch_id: string | null
  detection_count: number
  avg_total_score: number
  avg_smoothness: number
  avg_width: number
  avg_defect: number
  max_score: number
  min_score: number
}

interface ComparisonResponse {
  status: string
  comparison_data: StudentStats[]
}

interface ScoreRecord {
  id: number
  timestamp: string
  student_id: string | null
  student_name: string | null
  total_score: number
  smoothness_score: number
  width_score: number
  defect_score: number
  actual_width: number | null
  defect_type_name: string | null
}

interface RecentScoresResponse {
  status: string
  scores: ScoreRecord[]
}

// DB 里只有 3 项真实分数，剩下 3 维（间距控制/熔深控制/焊接速度）用真实分数估算出来
const RADAR_AXES = ["光滑度", "间距控制", "缺陷控制", "焊缝宽度", "熔深控制", "焊接速度"] as const

function buildSixDimRadar(s: StudentStats | null): Record<(typeof RADAR_AXES)[number], number> {
  if (!s) {
    return { 光滑度: 0, 间距控制: 0, 缺陷控制: 0, 焊缝宽度: 0, 熔深控制: 0, 焊接速度: 0 }
  }
  const smooth = s.avg_smoothness
  const width = s.avg_width
  const defect = s.avg_defect
  const total = s.avg_total_score
  return {
    光滑度: smooth,
    焊缝宽度: width,
    缺陷控制: defect,
    间距控制: smooth * 0.5 + width * 0.5,
    熔深控制: defect * 0.6 + smooth * 0.4,
    焊接速度: total * 0.92,
  }
}

function recordsToTreeMap(records: ScoreRecord[]): Map<number, TreeData> {
  const m = new Map<number, TreeData>()
  records.forEach((r, idx) => {
    const td = convertYOLOToTreeData({
      total_score: r.total_score,
      smoothness_score: r.smoothness_score,
      width_score: r.width_score,
      defect_score: r.defect_score,
      timestamp: r.timestamp,
      actual_width: r.actual_width ?? undefined,
      defect_type_name: r.defect_type_name ?? undefined,
    })
    m.set(idx, td)
  })
  return m
}

const RECORDS_LIMIT = 200
const RADAR_COLORS = { self: "#3B82F6", opponent: "#F59E0B" } as const

export function StudentComparisonContent() {
  const { currentUser } = useAuth()

  const [allStudents, setAllStudents] = useState<StudentStats[]>([])
  const [opponentId, setOpponentId] = useState<string>("")
  const [opponentTree, setOpponentTree] = useState<Map<number, TreeData> | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [refreshKey, setRefreshKey] = useState(0)

  useEffect(() => {
    if (!currentUser) return
    let cancelled = false
    setLoading(true)
    setError(null)
    fetch(API_ENDPOINTS.STUDENT_COMPARISON)
      .then((r) => {
        if (!r.ok) throw new Error(`HTTP ${r.status}`)
        return r.json() as Promise<ComparisonResponse>
      })
      .then((data) => {
        if (cancelled) return
        if (data.status !== "success") throw new Error("接口返回 status != success")
        setAllStudents(data.comparison_data)
      })
      .catch((err) => {
        if (!cancelled) setError(err instanceof Error ? err.message : "未知错误")
      })
      .finally(() => {
        if (!cancelled) setLoading(false)
      })
    return () => {
      cancelled = true
    }
  }, [currentUser, refreshKey])

  useEffect(() => {
    if (!opponentId) {
      setOpponentTree(null)
      return
    }
    let cancelled = false
    const url = `${API_ENDPOINTS.RECENT_SCORES}?student_id=${encodeURIComponent(opponentId)}&limit=${RECORDS_LIMIT}`
    fetch(url)
      .then((r) => {
        if (!r.ok) throw new Error(`HTTP ${r.status}`)
        return r.json() as Promise<RecentScoresResponse>
      })
      .then((data) => {
        if (cancelled) return
        if (data.status !== "success") throw new Error("接口返回 status != success")
        setOpponentTree(recordsToTreeMap(data.scores))
      })
      .catch((err) => {
        if (cancelled) return
        console.warn("[comparison] 拉取对比学生记录失败", err)
        setOpponentTree(new Map())
      })
    return () => {
      cancelled = true
    }
  }, [opponentId, refreshKey])

  const selfStats = useMemo(
    () => allStudents.find((s) => s.student_id === currentUser?.student_id) ?? null,
    [allStudents, currentUser],
  )
  const opponentStats = useMemo(
    () => allStudents.find((s) => s.student_id === opponentId) ?? null,
    [allStudents, opponentId],
  )
  const opponents = useMemo(
    () => allStudents.filter((s) => s.student_id !== currentUser?.student_id),
    [allStudents, currentUser],
  )

  const radarData = useMemo(() => {
    const selfRow = buildSixDimRadar(selfStats)
    const oppRow = buildSixDimRadar(opponentStats)
    return RADAR_AXES.map((axis) => ({
      subject: axis,
      self: Number(selfRow[axis].toFixed(1)),
      opponent: Number(oppRow[axis].toFixed(1)),
    }))
  }, [selfStats, opponentStats])

  if (!currentUser) {
    return <div className="text-gray-400 p-6">请先登录后再进入学生对比。</div>
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between flex-wrap gap-3">
        <h2 className="text-2xl font-bold text-white flex items-center">
          <Trophy className="w-7 h-7 mr-3 text-yellow-400" />
          学生对比 / PK
        </h2>
        <Button
          size="sm"
          variant="outline"
          className="border-slate-600 text-gray-200 hover:bg-slate-700"
          onClick={() => setRefreshKey((k) => k + 1)}
          disabled={loading}
          title="刷新"
        >
          <RefreshCw className={`w-4 h-4 ${loading ? "animate-spin" : ""}`} />
        </Button>
      </div>

      {error && (
        <Card className="bg-red-500/10 border-red-500/40">
          <CardContent className="p-4 text-red-300 text-sm">加载学生列表失败：{error}</CardContent>
        </Card>
      )}

      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <Card className="bg-slate-800/50 border-slate-600">
          <CardContent className="p-4 flex items-center justify-between">
            <div className="flex items-center text-white">
              <div className="w-10 h-10 rounded-full flex items-center justify-center mr-3" style={{ background: RADAR_COLORS.self }}>
                <User className="w-5 h-5" />
              </div>
              <div>
                <div className="text-sm text-gray-400">我</div>
                <div className="font-semibold">
                  {currentUser.name} · {currentUser.student_id}
                </div>
                {selfStats && (
                  <div className="text-xs text-gray-400 mt-0.5">
                    检测 {selfStats.detection_count} 次 · 平均 {selfStats.avg_total_score.toFixed(1)}
                  </div>
                )}
              </div>
            </div>
            <Swords className="w-6 h-6 text-gray-500" />
          </CardContent>
        </Card>

        <Card className="bg-slate-800/50 border-slate-600">
          <CardContent className="p-4 flex items-center justify-between">
            <div className="flex items-center text-white">
              <div className="w-10 h-10 rounded-full flex items-center justify-center mr-3" style={{ background: RADAR_COLORS.opponent }}>
                <User className="w-5 h-5" />
              </div>
              <div className="flex-1">
                <div className="text-sm text-gray-400">对比对象</div>
                <select
                  value={opponentId}
                  onChange={(e) => setOpponentId(e.target.value)}
                  disabled={opponents.length === 0}
                  className="bg-slate-900 border border-slate-600 text-white text-sm rounded px-2 py-1 mt-0.5 min-w-[12rem] focus:outline-none focus:border-amber-400 disabled:opacity-60"
                >
                  <option value="">
                    {opponents.length === 0 ? "暂无其他学生数据" : "选择学生..."}
                  </option>
                  {opponents.map((s) => (
                    <option key={s.student_id} value={s.student_id}>
                      {s.student_name} · {s.student_id}
                    </option>
                  ))}
                </select>
                {opponentStats && (
                  <div className="text-xs text-gray-400 mt-1">
                    检测 {opponentStats.detection_count} 次 · 平均 {opponentStats.avg_total_score.toFixed(1)}
                  </div>
                )}
              </div>
            </div>
          </CardContent>
        </Card>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <Card className="bg-slate-800/50 border-slate-600 overflow-hidden">
          <CardHeader className="pb-2">
            <CardTitle className="text-white text-base flex items-center">
              <span className="w-2 h-2 rounded-full mr-2" style={{ background: RADAR_COLORS.self }}></span>
              {currentUser.name} 的数据树
            </CardTitle>
          </CardHeader>
          <CardContent className="p-0 h-[460px]">
            <DataTreeViewer />
          </CardContent>
        </Card>

        <Card className="bg-slate-800/50 border-slate-600 overflow-hidden">
          <CardHeader className="pb-2">
            <CardTitle className="text-white text-base flex items-center">
              <span className="w-2 h-2 rounded-full mr-2" style={{ background: RADAR_COLORS.opponent }}></span>
              {opponentStats ? `${opponentStats.student_name} 的数据树` : "对比对象的数据树"}
            </CardTitle>
          </CardHeader>
          <CardContent className="p-0 h-[460px]">
            {opponentId ? (
              <DataTreeViewer treeData={opponentTree ?? new Map()} />
            ) : (
              <div className="h-full flex items-center justify-center text-center text-gray-400 text-sm bg-[#050505]">
                选择上方对比对象后显示
              </div>
            )}
          </CardContent>
        </Card>
      </div>

      <Card className="bg-slate-800/50 border-slate-600">
        <CardHeader className="pb-2">
          <CardTitle className="text-white text-base flex items-center justify-between">
            <span className="flex items-center">
              <Trophy className="w-5 h-5 mr-2 text-yellow-400" />
              六维技能雷达
            </span>
            <span className="text-xs text-gray-500 flex items-center">
              <Info className="w-3.5 h-3.5 mr-1" />
              间距/熔深/速度为真实分数代理估算
            </span>
          </CardTitle>
        </CardHeader>
        <CardContent className="p-4">
          <div className="h-72">
            <ResponsiveContainer width="100%" height="100%">
              <RadarChart data={radarData}>
                <PolarGrid stroke="#374151" />
                <PolarAngleAxis dataKey="subject" tick={{ fill: "#9CA3AF" }} />
                <PolarRadiusAxis angle={90} domain={[0, 100]} tick={{ fill: "#9CA3AF" }} />
                <Radar
                  name={currentUser.name}
                  dataKey="self"
                  stroke={RADAR_COLORS.self}
                  fill={RADAR_COLORS.self}
                  fillOpacity={0.3}
                  strokeWidth={2}
                />
                {opponentStats && (
                  <Radar
                    name={opponentStats.student_name}
                    dataKey="opponent"
                    stroke={RADAR_COLORS.opponent}
                    fill={RADAR_COLORS.opponent}
                    fillOpacity={0.3}
                    strokeWidth={2}
                  />
                )}
                <Legend wrapperStyle={{ color: "#E5E7EB", fontSize: 12 }} />
                <Tooltip
                  contentStyle={{ background: "#1F2937", border: "1px solid #374151" }}
                  labelStyle={{ color: "#F3F4F6" }}
                />
              </RadarChart>
            </ResponsiveContainer>
          </div>
        </CardContent>
      </Card>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <DefectHeatmap
          studentId={currentUser.student_id}
          studentName={currentUser.name}
        />
        <DefectHeatmap
          studentId={opponentId || null}
          studentName={opponentStats?.student_name ?? null}
        />
      </div>
    </div>
  )
}
