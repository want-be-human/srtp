"use client"

import type React from "react"

import { useEffect, useRef, useState } from "react"
import {
  Send,
  GraduationCap,
  User,
  Loader2,
  Sparkles,
  ShieldCheck,
} from "lucide-react"
import ReactMarkdown from "react-markdown"
import remarkGfm from "remark-gfm"
import { API_ENDPOINTS } from "@/lib/api"
import { useAuth } from "@/contexts/AuthContext"
import { SessionListSidebar } from "./session-list-sidebar"
import { useTeacherSessions, type TeacherMessage } from "./use-teacher-sessions"

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

// Welcome 不入库——每个空 session 第一屏由组件运行时注入，避免每条 session 都存
// 同一份冗余文案。
const WELCOME_MESSAGE: TeacherMessage = {
  id: "welcome",
  role: "assistant",
  content:
    "您好！我是您的 AI 焊接技术专家。焊接知识库已准备就绪，您可以针对当前的焊接检测数据，询问任何关于缺陷分析、工艺优化或手法改进的问题。",
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

export function AITeacherChatContent({
  lastDetectionResult,
}: {
  lastDetectionResult: DetectionResult | null
}) {
  const { currentUser } = useAuth()
  const studentKey = currentUser?.student_id ?? null
  const {
    sessions,
    activeSessionId,
    activeSession,
    createSession,
    selectSession,
    deleteSession,
    clearAll,
    appendMessages,
  } = useTeacherSessions(studentKey)

  const [inputMessage, setInputMessage] = useState("")
  const [isLoading, setIsLoading] = useState(false)
  const [errorBanner, setErrorBanner] = useState<string | null>(null)
  const messagesEndRef = useRef<HTMLDivElement>(null)
  const textareaRef = useRef<HTMLTextAreaElement>(null)

  // 当前显示的消息：welcome 永远首条，活跃 session 的真消息接在后面
  const storedMessages = activeSession?.messages ?? []
  const displayMessages: TeacherMessage[] = [WELCOME_MESSAGE, ...storedMessages]

  // 切 session、追加消息、loading 起落都重新滚到底；用 length 做 dep 而不是
  // displayMessages 本身，避免 derived array 每次 render 都引用变化触发 effect
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" })
  }, [activeSessionId, displayMessages.length, isLoading])

  // 从检测页点 "咨询AI教师" 跳过来时，给个示例 prompt 让用户改了直接发。
  // 只在第一次拿到检测结果时预填，用户已经动过键盘就别打断了。
  useEffect(() => {
    if (!lastDetectionResult) return
    if (storedMessages.length > 0 || inputMessage) return
    setInputMessage("请针对本次焊接结果中的气孔缺陷给出专业的改进建议。")
    // 故意只依赖 lastDetectionResult；inputMessage 和 storedMessages 变更
    // 不需要重新触发，否则用户清空输入又会被覆盖
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [lastDetectionResult])

  const adjustTextareaHeight = () => {
    const textarea = textareaRef.current
    if (textarea) {
      textarea.style.height = "auto"
      textarea.style.height = Math.min(textarea.scrollHeight, 150) + "px"
    }
  }

  const handleCreateSession = () => {
    createSession()
    setErrorBanner(null)
    setInputMessage("")
  }

  const handleSelectSession = (id: string) => {
    selectSession(id)
    setErrorBanner(null)
  }

  const handleDeleteSession = (id: string) => {
    deleteSession(id)
    setErrorBanner(null)
  }

  const handleClearAll = () => {
    clearAll()
    setErrorBanner(null)
    setInputMessage("")
  }

  const sendMessage = async () => {
    if (!inputMessage.trim()) return

    // 没活跃 session 就先开一个，否则消息没地方落
    const targetId = activeSessionId ?? createSession()

    const userMessage: TeacherMessage = {
      id: Date.now().toString(),
      role: "user",
      content: inputMessage,
      timestamp: new Date().toISOString(),
    }

    appendMessages(targetId, [userMessage])
    setInputMessage("")
    setIsLoading(true)
    setErrorBanner(null)

    if (textareaRef.current) textareaRef.current.style.height = "48px"

    try {
      // 上下文用追加前的快照（不含刚发的这条）
      const history = storedMessages.map((m) => ({
        role: m.role,
        content: m.content,
      }))
      // 只在 session 首问时把检测结果带给后端，后续对话不再重复携带
      const context = storedMessages.length === 0 ? lastDetectionResult : null

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
          console.warn(
            "[ai-teacher] backend reported error:",
            data.error_category,
            data.error_detail,
          )
        }
      }

      const aiMessage: TeacherMessage = {
        id: (Date.now() + 1).toString(),
        role: "assistant",
        content: data.response,
        timestamp: new Date().toISOString(),
        errorCategory: data.error_category,
      }

      appendMessages(targetId, [aiMessage])
    } catch (error) {
      setErrorBanner("无法连接到诊断系统，请确认后端服务运行正常。")
      const aiMessage: TeacherMessage = {
        id: (Date.now() + 1).toString(),
        role: "assistant",
        content:
          "诊断系统通信中断。请确认分析服务已在后台正确运行，再重试当前指令。",
        timestamp: new Date().toISOString(),
        errorCategory: "network",
      }
      appendMessages(targetId, [aiMessage])
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

  return (
    <div className="h-full flex bg-gradient-to-br from-slate-950 via-slate-900 to-slate-950 text-slate-300">
      <SessionListSidebar
        sessions={sessions}
        activeSessionId={activeSessionId}
        onCreate={handleCreateSession}
        onSelect={handleSelectSession}
        onDelete={handleDeleteSession}
        onClearAll={handleClearAll}
      />

      <div className="flex-1 flex flex-col min-w-0">
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
                  {activeSession
                    ? `当前会话 · ${activeSession.title || "新对话"} · ${activeSession.messages.length} 条`
                    : "焊接知识库已装载 · 等待开始对话"}
                </span>
              </div>
            </div>
          </div>

          <div className="hidden md:flex items-center px-4 py-2 bg-white/[0.02] border border-white/[0.05] rounded-xl">
            <span className="text-[11px] text-slate-400 font-medium">
              当前分析环境: <span className="text-orange-300/80">教学标准 V3.2</span>
            </span>
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
          {displayMessages.map((message) => (
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
                    {message.role === "user" ? (
                      <div className="whitespace-pre-wrap">{message.content}</div>
                    ) : (
                      // assistant 走 markdown：DeepSeek 回复常带表格 / 列表 / 标题 /
                      // emoji，纯 whitespace-pre-wrap 会把 ## 和 |...| 都当源码显示
                      <div className="markdown-content">
                        <ReactMarkdown
                          remarkPlugins={[remarkGfm]}
                          components={{
                            h1: (props) => <h1 className="text-lg font-bold text-orange-200 mt-3 mb-2 first:mt-0" {...props} />,
                            h2: (props) => <h2 className="text-base font-bold text-orange-200 mt-3 mb-2 first:mt-0" {...props} />,
                            h3: (props) => <h3 className="text-sm font-bold text-orange-100/90 mt-2 mb-1.5 first:mt-0" {...props} />,
                            p: (props) => <p className="my-2 first:mt-0 last:mb-0" {...props} />,
                            ul: (props) => <ul className="list-disc pl-5 my-2 space-y-1" {...props} />,
                            ol: (props) => <ol className="list-decimal pl-5 my-2 space-y-1" {...props} />,
                            li: (props) => <li className="leading-relaxed" {...props} />,
                            strong: (props) => <strong className="text-orange-100 font-semibold" {...props} />,
                            em: (props) => <em className="text-slate-300 italic" {...props} />,
                            code: ({ className, children, ...props }) => {
                              const isBlock = className?.startsWith("language-")
                              if (isBlock) {
                                return (
                                  <code className="block bg-slate-950/60 border border-white/[0.05] rounded-md px-3 py-2 my-2 text-[13px] font-mono overflow-x-auto" {...props}>
                                    {children}
                                  </code>
                                )
                              }
                              return (
                                <code className="bg-slate-950/60 border border-white/[0.05] rounded px-1.5 py-0.5 text-[13px] font-mono text-orange-200" {...props}>
                                  {children}
                                </code>
                              )
                            },
                            pre: (props) => <pre className="my-2 overflow-x-auto" {...props} />,
                            table: (props) => (
                              <div className="my-3 overflow-x-auto">
                                <table className="border-collapse text-[13px] w-auto" {...props} />
                              </div>
                            ),
                            thead: (props) => <thead className="bg-slate-800/60" {...props} />,
                            th: (props) => <th className="border border-white/10 px-3 py-1.5 text-left font-semibold text-orange-100" {...props} />,
                            td: (props) => <td className="border border-white/10 px-3 py-1.5 align-top" {...props} />,
                            blockquote: (props) => <blockquote className="border-l-2 border-orange-500/50 pl-3 my-2 text-slate-400 italic" {...props} />,
                            a: (props) => <a className="text-orange-300 hover:text-orange-200 underline" target="_blank" rel="noreferrer" {...props} />,
                            hr: () => <hr className="my-3 border-white/10" />,
                          }}
                        >
                          {message.content}
                        </ReactMarkdown>
                      </div>
                    )}
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
                  placeholder={activeSession ? "在此输入您的技术疑问..." : "直接输入即可自动开启新对话..."}
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

      <style dangerouslySetInnerHTML={{__html: `
        .custom-scrollbar::-webkit-scrollbar { width: 4px; }
        .custom-scrollbar::-webkit-scrollbar-track { background: transparent; }
        .custom-scrollbar::-webkit-scrollbar-thumb { background: rgba(100, 100, 100, 0.3); border-radius: 4px; }
      `}} />
    </div>
  )
}
