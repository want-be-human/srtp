"use client"

import type React from "react"

import { useState, useRef, useEffect } from "react"
import { Button } from "@/components/ui/button"
import { Send, Paperclip, ImageIcon, GraduationCap, User, Loader2, X, Camera, FileText } from "lucide-react"

interface Message {
  id: string
  role: "user" | "assistant"
  content: string
  timestamp: Date
  attachments?: {
    type: "image" | "file"
    name: string
    url: string
    size?: number
  }[]
}

// 从 page.tsx 复制过来的类型定义
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

export function AITeacherChatContent({ lastDetectionResult }: { lastDetectionResult: DetectionResult | null }) {
  const [messages, setMessages] = useState<Message[]>([
    {
      id: "welcome",
      role: "assistant",
      content:
        "您好！我是您的AI焊接教学助手。我可以帮助您解答焊接技术问题、分析焊缝质量、提供改进建议。请随时向我提问！",
      timestamp: new Date(),
    },
  ])
  const [inputMessage, setInputMessage] = useState("")
  const [isLoading, setIsLoading] = useState(false)
  const [attachments, setAttachments] = useState<File[]>([])
  const messagesEndRef = useRef<HTMLDivElement>(null)
  const fileInputRef = useRef<HTMLInputElement>(null)
  const textareaRef = useRef<HTMLTextAreaElement>(null)

  // 自动滚动到底部
  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" })
  }

  useEffect(() => {
    scrollToBottom()
  }, [messages])

  // 当组件加载且有检测结果时，自动填充一个初始问题
  useEffect(() => {
    if (lastDetectionResult) {
      setInputMessage("请帮我分析一下这次的检测结果，我应该如何改进？")
    }
  }, [lastDetectionResult]);

  // 自动调整输入框高度
  const adjustTextareaHeight = () => {
    const textarea = textareaRef.current
    if (textarea) {
      textarea.style.height = "auto"
      textarea.style.height = Math.min(textarea.scrollHeight, 120) + "px"
    }
  }

  // 处理文件上传
  const handleFileSelect = (event: React.ChangeEvent<HTMLInputElement>) => {
    const files = Array.from(event.target.files || [])
    setAttachments((prev) => [...prev, ...files])
  }

  // 移除附件
  const removeAttachment = (index: number) => {
    setAttachments((prev) => prev.filter((_, i) => i !== index))
  }

  // 发送消息
  const sendMessage = async () => {
    if (!inputMessage.trim() && attachments.length === 0) return

    const userMessage: Message = {
      id: Date.now().toString(),
      role: "user",
      content: inputMessage,
      timestamp: new Date(),
      attachments: attachments.map((file) => ({
        type: file.type.startsWith("image/") ? "image" : "file",
        name: file.name,
        url: URL.createObjectURL(file),
        size: file.size,
      })),
    }

    setMessages((prev) => [...prev, userMessage])
    setInputMessage("")
    setAttachments([])
    setIsLoading(true)

    try {
      // 从消息历史中提取对话上下文
      const history = messages.slice(1).map(msg => {
        if (msg.role === 'user') {
          return { user: msg.content, assistant: '' };
        }
        // Find the corresponding assistant message
        const assistantMsg = messages.find(m => m.id === (parseInt(msg.id, 10) + 1).toString() && m.role === 'assistant');
        if (assistantMsg) {
          return { user: '', assistant: assistantMsg.content };
        }
        return null;
      }).filter(item => item && (item.user || item.assistant));


      // 仅在第一次用户消息时发送上下文
      const context = messages.length === 1 ? lastDetectionResult : null;
      
      const requestBody = {
        message: inputMessage,
        history: messages.slice(1, -1).map(m => ({
          role: m.role,
          content: m.content
        })),
        context: context,
      };

      console.log("Sending request to AI Teacher:", JSON.stringify(requestBody, null, 2));

      const response = await fetch("http://127.0.0.1:8000/api/v1/teacher/chat", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify(requestBody),
      });

      if (!response.ok) {
        throw new Error("AI教师服务网络响应错误");
      }

      const data = await response.json();

      const aiMessage: Message = {
        id: (Date.now() + 1).toString(),
        role: "assistant",
        content: data.response,
        timestamp: new Date(),
      };

      setMessages((prev) => [...prev, aiMessage]);
    } catch (error) {
      console.error("与AI教师通信失败:", error);
      const errorMessage: Message = {
        id: (Date.now() + 1).toString(),
        role: "assistant",
        content: "抱歉，我现在有点忙，请稍后再试。",
        timestamp: new Date(),
      };
      setMessages((prev) => [...prev, errorMessage]);
    } finally {
      setIsLoading(false);
    }
  }

  // 处理键盘事件
  const handleKeyPress = (e: React.KeyboardEvent) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault()
      sendMessage()
    }
  }

  // 格式化文件大小
  const formatFileSize = (bytes: number) => {
    if (bytes === 0) return "0 Bytes"
    const k = 1024
    const sizes = ["Bytes", "KB", "MB", "GB"]
    const i = Math.floor(Math.log(bytes) / Math.log(k))
    return Number.parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + " " + sizes[i]
  }

  return (
    <div className="h-full flex flex-col">
      {/* 聊天头部 */}
      <div className="flex-shrink-0 p-6 border-b border-slate-700/50 bg-slate-800/30 backdrop-blur-sm">
        <div className="flex items-center space-x-4">
          <div className="w-12 h-12 bg-gradient-to-br from-orange-500 to-orange-600 rounded-full flex items-center justify-center shadow-lg">
            <GraduationCap className="w-6 h-6 text-white" />
          </div>
          <div>
            <h2 className="text-xl font-bold text-white">AI焊接教师</h2>
            <p className="text-orange-300 text-sm">专业焊接技术指导 • 24小时在线</p>
          </div>
          <div className="ml-auto flex items-center space-x-2">
            <div className="w-2 h-2 bg-green-400 rounded-full animate-pulse"></div>
            <span className="text-green-400 text-sm font-medium">在线</span>
          </div>
        </div>
      </div>

      {/* 消息列表 */}
      <div className="flex-1 overflow-y-auto p-6 space-y-6">
        {messages.map((message) => (
          <div key={message.id} className={`flex ${message.role === "user" ? "justify-end" : "justify-start"}`}>
            <div
              className={`flex space-x-3 max-w-4xl ${message.role === "user" ? "flex-row-reverse space-x-reverse" : ""}`}
            >
              {/* 头像 */}
              <div
                className={`w-8 h-8 rounded-full flex items-center justify-center flex-shrink-0 ${
                  message.role === "user"
                    ? "bg-gradient-to-br from-blue-500 to-blue-600"
                    : "bg-gradient-to-br from-orange-500 to-orange-600"
                }`}
              >
                {message.role === "user" ? (
                  <User className="w-4 h-4 text-white" />
                ) : (
                  <GraduationCap className="w-4 h-4 text-white" />
                )}
              </div>

              {/* 消息内容 */}
              <div className={`flex flex-col space-y-2 ${message.role === "user" ? "items-end" : "items-start"}`}>
                <div
                  className={`rounded-2xl px-4 py-3 max-w-2xl ${
                    message.role === "user"
                      ? "bg-blue-600 text-white"
                      : "bg-slate-700/80 text-gray-100 border border-slate-600/50"
                  }`}
                >
                  {/* 附件显示 */}
                  {message.attachments && message.attachments.length > 0 && (
                    <div className="mb-3 space-y-2">
                      {message.attachments.map((attachment, index) => (
                        <div key={index} className="flex items-center space-x-2 p-2 bg-slate-800/50 rounded-lg">
                          {attachment.type === "image" ? (
                            <div className="flex items-center space-x-2">
                              <img
                                src={attachment.url || "/placeholder.svg"}
                                alt={attachment.name}
                                className="w-16 h-16 object-cover rounded"
                              />
                              <div>
                                <div className="text-sm font-medium">{attachment.name}</div>
                                {attachment.size && (
                                  <div className="text-xs text-gray-400">{formatFileSize(attachment.size)}</div>
                                )}
                              </div>
                            </div>
                          ) : (
                            <div className="flex items-center space-x-2">
                              <FileText className="w-4 h-4 text-gray-400" />
                              <div>
                                <div className="text-sm font-medium">{attachment.name}</div>
                                {attachment.size && (
                                  <div className="text-xs text-gray-400">{formatFileSize(attachment.size)}</div>
                                )}
                              </div>
                            </div>
                          )}
                        </div>
                      ))}
                    </div>
                  )}

                  {/* 文本内容 */}
                  <div className="whitespace-pre-wrap text-sm leading-relaxed">{message.content}</div>
                </div>

                {/* 时间戳 */}
                <div className="text-xs text-gray-400 px-2">
                  {message.timestamp.toLocaleTimeString("zh-CN", {
                    hour: "2-digit",
                    minute: "2-digit",
                  })}
                </div>
              </div>
            </div>
          </div>
        ))}

        {/* 加载指示器 */}
        {isLoading && (
          <div className="flex justify-start">
            <div className="flex space-x-3 max-w-4xl">
              <div className="w-8 h-8 bg-gradient-to-br from-orange-500 to-orange-600 rounded-full flex items-center justify-center">
                <GraduationCap className="w-4 h-4 text-white" />
              </div>
              <div className="bg-slate-700/80 border border-slate-600/50 rounded-2xl px-4 py-3">
                <div className="flex items-center space-x-2">
                  <Loader2 className="w-4 h-4 animate-spin text-orange-400" />
                  <span className="text-gray-300 text-sm">AI教师正在思考...</span>
                </div>
              </div>
            </div>
          </div>
        )}

        <div ref={messagesEndRef} />
      </div>

      {/* 输入区域 */}
      <div className="flex-shrink-0 p-6 border-t border-slate-700/50 bg-slate-800/30 backdrop-blur-sm">
        {/* 附件预览 */}
        {attachments.length > 0 && (
          <div className="mb-4 flex flex-wrap gap-2">
            {attachments.map((file, index) => (
              <div key={index} className="relative group">
                <div className="flex items-center space-x-2 bg-slate-700/50 rounded-lg p-2 pr-8">
                  {file.type.startsWith("image/") ? (
                    <ImageIcon className="w-4 h-4 text-blue-400" />
                  ) : (
                    <FileText className="w-4 h-4 text-gray-400" />
                  )}
                  <span className="text-sm text-gray-300 max-w-32 truncate">{file.name}</span>
                </div>
                <button
                  onClick={() => removeAttachment(index)}
                  className="absolute -top-1 -right-1 w-5 h-5 bg-red-500 rounded-full flex items-center justify-center opacity-0 group-hover:opacity-100 transition-opacity"
                >
                  <X className="w-3 h-3 text-white" />
                </button>
              </div>
            ))}
          </div>
        )}

        {/* 输入框 */}
        <div className="flex items-end space-x-3">
          {/* 附件按钮 */}
          <div className="flex space-x-1">
            <input
              ref={fileInputRef}
              type="file"
              multiple
              accept="image/*,.pdf,.doc,.docx,.txt"
              onChange={handleFileSelect}
              className="hidden"
            />
            <Button
              variant="ghost"
              size="sm"
              onClick={() => fileInputRef.current?.click()}
              className="text-gray-400 hover:text-white hover:bg-slate-700"
            >
              <Paperclip className="w-4 h-4" />
            </Button>
            <Button
              variant="ghost"
              size="sm"
              onClick={() => {
                if (fileInputRef.current) {
                  fileInputRef.current.accept = "image/*"
                  fileInputRef.current.click()
                }
              }}
              className="text-gray-400 hover:text-white hover:bg-slate-700"
            >
              <Camera className="w-4 h-4" />
            </Button>
          </div>

          {/* 输入框容器 */}
          <div className="flex-1 relative">
            <textarea
              ref={textareaRef}
              value={inputMessage}
              onChange={(e) => {
                setInputMessage(e.target.value)
                adjustTextareaHeight()
              }}
              onKeyPress={handleKeyPress}
              placeholder="向AI教师提问焊接技术问题..."
              className="w-full bg-slate-700/50 border border-slate-600 rounded-xl px-4 py-3 pr-12 text-white placeholder-gray-400 resize-none focus:outline-none focus:ring-2 focus:ring-orange-500 focus:border-transparent min-h-[48px] max-h-[120px]"
              rows={1}
            />
            <Button
              onClick={sendMessage}
              disabled={(!inputMessage.trim() && attachments.length === 0) || isLoading}
              className="absolute right-2 bottom-2 w-8 h-8 p-0 bg-orange-600 hover:bg-orange-700 disabled:bg-slate-600 disabled:cursor-not-allowed rounded-lg"
            >
              <Send className="w-4 h-4" />
            </Button>
          </div>
        </div>

        {/* 提示文本 */}
        <div className="mt-2 text-xs text-gray-500 text-center">
          按 Enter 发送消息，Shift + Enter 换行 • 支持上传图片和文档
        </div>
      </div>
    </div>
  )
}
