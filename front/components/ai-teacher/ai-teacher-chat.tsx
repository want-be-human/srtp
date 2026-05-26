"use client"

import type React from "react"

import { useState, useRef, useEffect } from "react"
import {
  Send,
  GraduationCap,
  User,
  Loader2,
  Sparkles,
  ShieldCheck,
  Trash2,
  History,
} from "lucide-react"
import { API_ENDPOINTS } from "@/lib/api"
import { useAuth } from "@/contexts/AuthContext"
import { getJSON, getTeacherHistoryKey, remove, setJSON } from "@/lib/storage"

interface Message {
  id: string
  role: "user" | "assistant"
  content: string
  timestamp: string
  errorCategory?: string
}

interface DetectionResult {
  overallScore: number
  skillScores: {
    [key: string]: number
  }
  defectPrediction: {
    type: string
    confidence: string
  }
  processingTime: string
  modelConfidence: string
}

const WELCOME_MESSAGE: Message = {
  id: "welcome",
  role: "assistant",
  content: "您好！我是您的 AI 焊接技术专家。焊接知识库已准备就绪，您可以针对当前的焊接检测数据，询问任何关于缺陷分析、工艺优化或手法改进的问题。",
  timestamp: new Date().toISOString(),
}

// 后端 error_category 翻成用户能看懂的文案；刻意不带 env / key 名，免得演示时露后台。
const ERROR_HINTS: Record<string, string> = {
  not_configured: "AI 服务尚未配置，请联系老师或管理员开启。",
  auth: "AI 服务认证失败，请联系管理员检查授权。",
  timeout: "AI 响应超时，可能是模型负载较高，请稍后重试。",
  rate_limit: "AI 调用次数被限流，请稍等片刻再发送。",
  network: "AI 服务连接失败，请检查网络后重试。",
  unknown: "AI 调用失败，已切换到本地兜底建议。",
}

export function AITeacherChatContent({ lastDetectionResult }: { lastDetectionResult: DetectionResult | null }) {
  const { currentUser } = useAuth()
  const studentKey = currentUser?.student_id ?? null
  const storageKey = getTeacherHistoryKey(studentKey)

  const [messages, setMessages] = useState<Message[]>([WELCOME_MESSAGE])
  const [inputMessage, setInputMessage] = useState("")
  const [isLoading, setIsLoading] = useState(false)
  const [errorBanner, setErrorBanner] = useState<string | null>(null)
  const messagesEndRef = useRef<HTMLDivElement>(null)
  const textareaRef = useRef<HTMLTextAreaElement>(null)
  const hydratedRef = useRef(false)

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" })
  }

  useEffect(() => {
    scrollToBottom()
  }, [messages, isLoading])

  // 切学生时重新从对应桶加载历史；welcome 已经在初值里，没历史就保持欢迎语
  useEffect(() => {
    hydratedRef.current = false
    const saved = getJSON<Message[]>(storageKey, [])
    if (saved.length > 0) {
      setMessages(saved)
    } else {
      setMessages([WELCOME_MESSAGE])
    }
    setErrorBanner(null)
    // 下一个 effect 周期再放行写回，避免刚切学生就把空数组写覆盖了旧记录
    queueMicrotask(() => {
      hydratedRef.current = true
    })
  }, [storageKey])

  // 把消息持久化到 localStorage；只有欢迎语时不写，避免新用户立刻占一行
  useEffect(() => {
    if (!hydratedRef.current) return
    if (messages.length <= 1) {
      remove(storageKey)
      return
    }
    setJSON(storageKey, messages)
  }, [messages, storageKey])

  useEffect(() => {
    if (lastDetectionResult && messages.length === 1) {
      setInputMessage("请针对本次焊接结果中的气孔缺陷给出专业的改进建议。")
    }
  }, [lastDetectionResult, messages.length])

  const adjustTextareaHeight = () => {
    const textarea = textareaRef.current
    if (textarea) {
      textarea.style.height = "auto"
      textarea.style.height = Math.min(textarea.scrollHeight, 150) + "px"
    }
  }

  const handleClearHistory = () => {
    setMessages([WELCOME_MESSAGE])
    setErrorBanner(null)
    remove(storageKey)
  }

  const sendMessage = async () => {
    if (!inputMessage.trim()) return

    const userMessage: Message = {
      id: Date.now().toString(),
      role: "user",
      content: inputMessage,
      timestamp: new Date().toISOString(),
    }

    setMessages((prev) => [...prev, userMessage])
    setInputMessage("")
    setIsLoading(true)
    setErrorBanner(null)

    if (textareaRef.current) textareaRef.current.style.height = "48px"

    try {
      const history = messages.slice(1).map((m) => ({
        role: m.role,
        content: m.content,
      }))

      const context = messages.length === 1 ? lastDetectionResult : null

      const response = await fetch(API_ENDPOINTS.TEACHER_CHAT, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          message: userMessage.content,
          history,
          context,
        }),
      })

      if (!response.ok) {
        throw new Error(`HTTP ${response.status}`)
      }

      const data = await response.json()

      if (data.fallback && data.error_category) {
        setErrorBanner(ERROR_HINTS[data.error_category] ?? ERROR_HINTS.unknown)
        if (data.error_detail) {
          console.warn("[ai-teacher] backend reported error:", data.error_category, data.error_detail)
        }
      }

      const aiMessage: Message = {
        id: (Date.now() + 1).toString(),
        role: "assistant",
        content: data.response,
        timestamp: new Date().toISOString(),
        errorCategory: data.error_category,
      }

      setMessages((prev) => [...prev, aiMessage])
    } catch (error) {
      setErrorBanner("无法连接到诊断系统，请确认后端服务运行正常。")
      const aiMessage: Message = {
        id: (Date.now() + 1).toString(),
        role: "assistant",
        content: "诊断系统通信中断。请确认分析服务已在后台正确运行，再重试当前指令。",
        timestamp: new Date().toISOString(),
        errorCategory: "network",
      }
      setMessages((prev) => [...prev, aiMessage])
    } finally {
      setIsLoading(false)
    }
  }

  const handleKeyPress = (e: React.KeyboardEvent) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault()
      sendMessage()
    }
  }

  const persistedCount = Math.max(messages.length - 1, 0)

  return (
    <div className="h-full flex flex-col bg-gradient-to-br from-slate-950 via-slate-900 to-slate-950 text-slate-300">
      <header className="flex-shrink-0 px-8 py-6 flex items-center justify-between bg-slate-900/30 backdrop-blur-md">
        <div className="flex items-center gap-4">
          <div className="relative group">
            <div className="absolute -inset-1 bg-gradient-to-tr from-orange-600 to-amber-400 rounded-2xl blur opacity-25 group-hover:opacity-40 transition duration-500"></div>
            <div className="relative w-11 h-11 bg-slate-800 border border-white/10 rounded-xl flex items-center justify-center shadow-inner">
              <GraduationCap className="w-6 h-6 text-orange-500" />
            </div>
          </div>
          <div>
            <div className="flex items-center gap-2.5">
              <h2 className="text-lg font-bold tracking-tight text-white">AI 焊接技术专家</h2>
              <div className="flex items-center gap-1 px-2 py-0.5 rounded-full bg-orange-500/10 border border-orange-500/20">
                <ShieldCheck className="w-3 h-3 text-orange-400" />
                <span className="text-[9px] text-orange-400 font-bold uppercase tracking-widest">Enterprise</span>
              </div>
            </div>
            <div className="flex items-center gap-1.5 mt-0.5">
              <span className="w-1.5 h-1.5 rounded-full bg-orange-500 animate-pulse"></span>
              <span className="text-slate-500 text-[11px] font-medium tracking-wide">
                焊接知识库已装载 · 本地保留 {persistedCount} 条历史
              </span>
            </div>
          </div>
        </div>

        <div className="flex items-center gap-3">
          <div className="hidden md:flex items-center px-4 py-2 bg-white/[0.02] border border-white/[0.05] rounded-xl">
            <span className="text-[11px] text-slate-400 font-medium">
              当前分析环境: <span className="text-orange-300/80">教学标准 V3.2</span>
            </span>
          </div>
          <button
            onClick={handleClearHistory}
            disabled={persistedCount === 0}
            className="flex items-center gap-1.5 px-3 py-2 rounded-xl border border-white/[0.05] bg-white/[0.02] hover:bg-red-500/10 hover:border-red-500/30 hover:text-red-300 transition-colors text-[11px] text-slate-400 font-medium disabled:opacity-40 disabled:cursor-not-allowed disabled:hover:bg-white/[0.02] disabled:hover:border-white/[0.05] disabled:hover:text-slate-400"
            title="清空本机保存的对话历史"
          >
            <Trash2 className="w-3 h-3" />
            清空历史
          </button>
          <div
            className="hidden lg:flex items-center gap-1.5 px-3 py-2 rounded-xl border border-white/[0.05] bg-white/[0.02] text-[11px] text-slate-500 font-medium"
            title="历史按学号分桶，只存在当前浏览器"
          >
            <History className="w-3 h-3" />
            按学号本地保留
          </div>
        </div>
      </header>

      {errorBanner && (
        <div className="mx-6 md:mx-12 mt-2 px-4 py-2.5 rounded-xl bg-red-500/10 border border-red-500/30 text-red-300 text-[12px] flex items-start gap-2">
          <span className="mt-0.5 w-1.5 h-1.5 rounded-full bg-red-400 flex-shrink-0"></span>
          <div className="flex-1">{errorBanner}</div>
          <button
            onClick={() => setErrorBanner(null)}
            className="text-red-300/60 hover:text-red-300 text-[11px] underline"
          >
            关闭
          </button>
        </div>
      )}

      <div className="flex-1 overflow-y-auto px-6 md:px-12 py-10 space-y-10 scroll-smooth">
        {messages.map((message) => (
          <div
            key={message.id}
            className={`flex ${message.role === "user" ? "justify-end" : "justify-start"}`}
          >
            <div className={`flex gap-5 max-w-[85%] md:max-w-[80%] ${message.role === "user" ? "flex-row-reverse" : "flex-row"}`}>
              <div className={`w-9 h-9 rounded-xl flex items-center justify-center flex-shrink-0 shadow-lg border ${
                message.role === "user"
                  ? "bg-slate-700 border-slate-600 text-white"
                  : "bg-gradient-to-br from-slate-800 to-slate-900 border-white/10 text-orange-400"
              }`}>
                {message.role === "user" ? <User className="w-5 h-5" /> : <Sparkles className="w-4 h-4" />}
              </div>

              <div className={`flex flex-col gap-2.5 ${message.role === "user" ? "items-end" : "items-start"}`}>
                <div className={`px-6 py-4 rounded-2xl leading-relaxed text-[15px] transition-all duration-300 ${
                  message.role === "user"
                    ? "bg-orange-600 text-white rounded-tr-none shadow-[0_8px_30px_rgb(234,88,12,0.15)] border border-orange-500/30 font-medium"
                    : message.errorCategory
                      ? "bg-[#1e1417] border border-red-500/20 text-slate-200 rounded-tl-none shadow-[0_10px_40px_rgba(0,0,0,0.3)]"
                      : "bg-[#161d2b] border border-white/[0.06] text-slate-200 rounded-tl-none shadow-[0_10px_40px_rgba(0,0,0,0.3)]"
                }`}>
                  <div className="whitespace-pre-wrap">{message.content}</div>
                </div>

                <span className="text-[10px] text-slate-500 font-bold uppercase tracking-widest px-1 opacity-60">
                  {new Date(message.timestamp).toLocaleTimeString("zh-CN", { hour: "2-digit", minute: "2-digit" })}
                </span>
              </div>
            </div>
          </div>
        ))}

        {isLoading && (
          <div className="flex justify-start">
            <div className="flex gap-5 items-start">
              <div className="w-9 h-9 rounded-xl bg-slate-800 border border-white/5 flex items-center justify-center">
                <Loader2 className="w-4 h-4 animate-spin text-orange-500/60" />
              </div>
              <div className="px-6 py-5 rounded-2xl bg-white/[0.02] border border-white/[0.05] rounded-tl-none flex flex-col gap-2">
                <div className="flex gap-1.5">
                  <div className="w-1.5 h-1.5 bg-orange-500/40 rounded-full animate-bounce"></div>
                  <div className="w-1.5 h-1.5 bg-orange-500/60 rounded-full animate-bounce [animation-delay:0.2s]"></div>
                  <div className="w-1.5 h-1.5 bg-orange-500/80 rounded-full animate-bounce [animation-delay:0.4s]"></div>
                </div>
                <span className="text-[11px] text-slate-500 font-bold uppercase tracking-widest">正在查阅焊接知识库...</span>
              </div>
            </div>
          </div>
        )}
        <div ref={messagesEndRef} />
      </div>

      <footer className="flex-shrink-0 p-8 pt-0">
        <div className="max-w-4xl mx-auto">
          <div className="relative group">
            <div className="absolute -inset-1 bg-gradient-to-r from-orange-500/10 to-transparent rounded-[26px] blur-lg group-focus-within:from-orange-500/20 transition-all duration-500 opacity-0 group-focus-within:opacity-100"></div>

            <div className="relative flex items-end gap-3 bg-slate-800/50 backdrop-blur-xl border border-orange-500/20 rounded-[24px] p-2.5 transition-all duration-300 focus-within:border-orange-500/50 focus-within:bg-slate-900/70 shadow-2xl">
              <textarea
                ref={textareaRef}
                value={inputMessage}
                onChange={(e) => {
                  setInputMessage(e.target.value)
                  adjustTextareaHeight()
                }}
                onKeyDown={handleKeyPress}
                placeholder="在此输入您的技术疑问..."
                className="flex-1 bg-transparent py-3 px-4 text-[15px] placeholder-slate-600 resize-none outline-none max-h-[160px] min-h-[48px] text-white font-medium"
                rows={1}
              />
              <div className="pb-1 pr-1">
                <button
                  onClick={sendMessage}
                  disabled={isLoading || !inputMessage.trim()}
                  className={`w-12 h-12 rounded-2xl transition-all flex items-center justify-center shadow-lg ${
                    isLoading || !inputMessage.trim()
                      ? "bg-slate-700/50 text-slate-500 cursor-not-allowed"
                      : "bg-gradient-to-br from-orange-500 to-amber-600 text-white hover:scale-105 active:scale-95 shadow-orange-600/20"
                  }`}
                >
                  <Send className="w-5 h-5" />
                </button>
              </div>
            </div>
          </div>

          <div className="mt-4 flex items-center justify-center gap-6 text-[10px] text-slate-600 font-bold uppercase tracking-[0.15em]">
            <div className="flex items-center gap-1.5">
              <div className="w-4 h-4 rounded border border-white/10 flex items-center justify-center text-[8px] font-sans">↩</div>
              发送
            </div>
            <div className="w-1 h-1 bg-slate-800 rounded-full"></div>
            <div className="flex items-center gap-1.5">
              <div className="w-7 h-4 rounded border border-white/10 flex items-center justify-center text-[8px] font-sans">SHIFT</div>
              换行
            </div>
          </div>
        </div>
      </footer>
    </div>
  )
}
