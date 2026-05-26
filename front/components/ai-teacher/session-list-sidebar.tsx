"use client"

import { useState } from "react"
import { MessageSquarePlus, Trash2, Sparkles, X } from "lucide-react"
import type { TeacherSession } from "./use-teacher-sessions"

interface Props {
  sessions: TeacherSession[]
  activeSessionId: string | null
  onCreate: () => void
  onSelect: (id: string) => void
  onDelete: (id: string) => void
  onClearAll: () => void
}

// 时间显示规则：今天 hh:mm、昨天 hh:mm、再早就直接 MM-dd。
// 不引日期库，自己算够用。
function formatSessionTime(iso: string): string {
  const t = new Date(iso)
  const now = new Date()
  const sameDay =
    t.getFullYear() === now.getFullYear() &&
    t.getMonth() === now.getMonth() &&
    t.getDate() === now.getDate()
  const hhmm = `${String(t.getHours()).padStart(2, "0")}:${String(t.getMinutes()).padStart(2, "0")}`
  if (sameDay) return `今天 ${hhmm}`

  const yesterday = new Date(now)
  yesterday.setDate(now.getDate() - 1)
  if (
    t.getFullYear() === yesterday.getFullYear() &&
    t.getMonth() === yesterday.getMonth() &&
    t.getDate() === yesterday.getDate()
  ) {
    return `昨天 ${hhmm}`
  }
  return `${String(t.getMonth() + 1).padStart(2, "0")}-${String(t.getDate()).padStart(2, "0")} ${hhmm}`
}

export function SessionListSidebar({
  sessions,
  activeSessionId,
  onCreate,
  onSelect,
  onDelete,
  onClearAll,
}: Props) {
  const [confirmClearAll, setConfirmClearAll] = useState(false)

  const handleClearAllClick = () => {
    if (confirmClearAll) {
      onClearAll()
      setConfirmClearAll(false)
    } else {
      setConfirmClearAll(true)
      // 5 秒不点就自动取消确认态，免得用户半天后误删
      window.setTimeout(() => setConfirmClearAll(false), 5000)
    }
  }

  return (
    <aside className="w-72 flex-shrink-0 flex flex-col bg-slate-900/40 border-r border-white/[0.05]">
      <div className="px-4 py-5 border-b border-white/[0.05] space-y-3">
        <button
          onClick={onCreate}
          className="w-full flex items-center justify-center gap-2 px-3 py-2.5 rounded-xl bg-gradient-to-br from-orange-500 to-amber-600 text-white text-sm font-medium hover:scale-[1.01] active:scale-[0.99] transition-transform shadow-lg shadow-orange-600/20"
        >
          <MessageSquarePlus className="w-4 h-4" />
          新建对话
        </button>
        <div className="flex items-center justify-between text-[10px] text-slate-500 font-bold uppercase tracking-widest px-1">
          <span>历史会话 · {sessions.length}</span>
          {sessions.length > 0 && (
            <button
              onClick={handleClearAllClick}
              className={`flex items-center gap-1 px-1.5 py-0.5 rounded transition-colors ${
                confirmClearAll
                  ? "bg-red-500/20 text-red-300"
                  : "hover:bg-white/[0.05] text-slate-500 hover:text-red-300"
              }`}
              title={confirmClearAll ? "再点一次确认清空" : "清空所有会话"}
            >
              <Trash2 className="w-3 h-3" />
              {confirmClearAll ? "确认清空" : "清空"}
            </button>
          )}
        </div>
      </div>

      <div className="flex-1 overflow-y-auto custom-scrollbar px-2 py-2 space-y-1">
        {sessions.length === 0 ? (
          <div className="px-4 py-8 text-center text-slate-600 text-xs leading-relaxed">
            <Sparkles className="w-5 h-5 mx-auto mb-2 opacity-40" />
            点上方<span className="text-orange-400">新建对话</span>开始第一段
            <br />
            历史只保存在本机
          </div>
        ) : (
          sessions.map((s) => {
            const isActive = s.id === activeSessionId
            const displayTitle = s.title || "新对话"
            return (
              <div
                key={s.id}
                onClick={() => onSelect(s.id)}
                className={`group relative px-3 py-2.5 rounded-lg cursor-pointer transition-colors ${
                  isActive
                    ? "bg-orange-500/10 border border-orange-500/30"
                    : "border border-transparent hover:bg-white/[0.03]"
                }`}
              >
                <div className="pr-6">
                  <div
                    className={`text-sm truncate ${
                      isActive ? "text-orange-100 font-medium" : "text-slate-300"
                    }`}
                  >
                    {displayTitle}
                  </div>
                  <div className="text-[10px] text-slate-500 mt-0.5 flex items-center gap-2">
                    <span>{formatSessionTime(s.updatedAt)}</span>
                    <span>·</span>
                    <span>{s.messages.length} 条</span>
                  </div>
                </div>
                <button
                  onClick={(e) => {
                    e.stopPropagation()
                    onDelete(s.id)
                  }}
                  className="absolute top-1/2 right-2 -translate-y-1/2 p-1 rounded opacity-0 group-hover:opacity-100 text-slate-500 hover:text-red-400 hover:bg-red-500/10 transition-all"
                  title="删除这条会话"
                >
                  <X className="w-3.5 h-3.5" />
                </button>
              </div>
            )
          })
        )}
      </div>

      <div className="px-4 py-3 border-t border-white/[0.05] text-[10px] text-slate-600 leading-relaxed">
        会话按学号分桶存在本机浏览器，换设备或清缓存会丢
      </div>
    </aside>
  )
}
