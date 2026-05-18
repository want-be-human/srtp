"use client"

import type React from "react"

import { useState, useRef, useEffect } from "react"
import {
  Send,
  GraduationCap,
  User,
  Loader2,
  Sparkles,
  ShieldCheck
} from "lucide-react"
import { API_ENDPOINTS } from "@/lib/api"

// Message 接口定义
interface Message {
  id: string
  role: "user" | "assistant"
  content: string
  timestamp: Date
}

// DetectionResult 接口定义（从 page.tsx 复制）
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
      content: "您好！我是您的 AI 焊接技术专家。焊接知识库已准备就绪，您可以针对当前的焊接检测数据，询问任何关于缺陷分析、工艺优化或手法改进的问题。",
      timestamp: new Date(),
    },
  ]);
  const [inputMessage, setInputMessage] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages, isLoading]);

  useEffect(() => {
    if (lastDetectionResult && messages.length === 1) {
      // 自动提示引导，增强交互体验
      setInputMessage("请针对本次焊接结果中的气孔缺陷给出专业的改进建议。");
    }
  }, [lastDetectionResult]);

  const adjustTextareaHeight = () => {
    const textarea = textareaRef.current;
    if (textarea) {
      textarea.style.height = "auto";
      textarea.style.height = Math.min(textarea.scrollHeight, 150) + "px";
    }
  };

  const sendMessage = async () => {
    if (!inputMessage.trim()) return;

    const userMessage: Message = {
      id: Date.now().toString(),
      role: "user",
      content: inputMessage,
      timestamp: new Date(),
    };

    setMessages((prev) => [...prev, userMessage]);
    setInputMessage("");
    setIsLoading(true);

    if (textareaRef.current) textareaRef.current.style.height = "48px";

    try {
      const history = messages.slice(1).map(m => ({
        role: m.role,
        content: m.content
      }));

      const context = messages.length === 1 ? lastDetectionResult : null;

      const requestBody = {
        message: userMessage.content,
        history: history,
        context: context,
      };

      const response = await fetch(API_ENDPOINTS.TEACHER_CHAT, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(requestBody),
      });

      if (!response.ok) throw new Error("AI教师服务暂时不可用");

      const data = await response.json();

      const aiMessage: Message = {
        id: (Date.now() + 1).toString(),
        role: "assistant",
        content: data.response,
        timestamp: new Date(),
      };

      setMessages((prev) => [...prev, aiMessage]);
    } catch (error) {
      const aiMessage: Message = {
        id: (Date.now() + 1).toString(),
        role: "assistant",
        content: "⚠️ 诊断系统通信中断。请确认分析服务已在后台正确运行。您可以尝试重新发送当前指令。",
        timestamp: new Date(),
      };
      setMessages((prev) => [...prev, aiMessage]);
    } finally {
      setIsLoading(false);
    }
  };

  const handleKeyPress = (e: React.KeyboardEvent) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      sendMessage();
    }
  };

  return (
    <div className="h-full flex flex-col bg-gradient-to-br from-slate-950 via-slate-900 to-slate-950 text-slate-300">
      {/* Refined Header - Industrial High-End Style */}
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
              <span className="text-slate-500 text-[11px] font-medium tracking-wide">焊接知识库已装载</span>
            </div>
          </div>
        </div>

        <div className="hidden md:flex items-center px-4 py-2 bg-white/[0.02] border border-white/[0.05] rounded-xl">
           <span className="text-[11px] text-slate-400 font-medium">当前分析环境: <span className="text-orange-300/80">教学标准 V3.2</span></span>
        </div>
      </header>

      {/* Chat Area - Subtle Gradients and High Contrast */}
      <div className="flex-1 overflow-y-auto px-6 md:px-12 py-10 space-y-10 scroll-smooth">
        {messages.map((message) => (
          <div
            key={message.id}
            className={`flex ${message.role === "user" ? "justify-end" : "justify-start"}`}
          >
            <div className={`flex gap-5 max-w-[85%] md:max-w-[80%] ${message.role === "user" ? "flex-row-reverse" : "flex-row"}`}>
              {/* Simplified Avatars */}
              <div className={`w-9 h-9 rounded-xl flex items-center justify-center flex-shrink-0 shadow-lg border ${
                message.role === "user"
                  ? "bg-slate-700 border-slate-600 text-white"
                  : "bg-gradient-to-br from-slate-800 to-slate-900 border-white/10 text-orange-400"
              }`}>
                {message.role === "user" ? <User className="w-5 h-5" /> : <Sparkles className="w-4 h-4" />}
              </div>

              {/* Message Bubble Design */}
              <div className={`flex flex-col gap-2.5 ${message.role === "user" ? "items-end" : "items-start"}`}>
                <div className={`px-6 py-4 rounded-2xl leading-relaxed text-[15px] transition-all duration-300 ${
                  message.role === "user"
                    ? "bg-orange-600 text-white rounded-tr-none shadow-[0_8px_30px_rgb(234,88,12,0.15)] border border-orange-500/30 font-medium"
                    : "bg-[#161d2b] border border-white/[0.06] text-slate-200 rounded-tl-none shadow-[0_10px_40px_rgba(0,0,0,0.3)]"
                }`}>
                  <div className="whitespace-pre-wrap">{message.content}</div>
                </div>

                <span className="text-[10px] text-slate-500 font-bold uppercase tracking-widest px-1 opacity-60">
                  {message.timestamp.toLocaleTimeString("zh-CN", { hour: "2-digit", minute: "2-digit" })}
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

      {/* Modern Floating Input Field */}
      <footer className="flex-shrink-0 p-8 pt-0">
        <div className="max-w-4xl mx-auto">
          <div className="relative group">
            {/* Ambient Background Glow */}
            <div className="absolute -inset-1 bg-gradient-to-r from-orange-500/10 to-transparent rounded-[26px] blur-lg group-focus-within:from-orange-500/20 transition-all duration-500 opacity-0 group-focus-within:opacity-100"></div>

            <div className="relative flex items-end gap-3 bg-slate-800/50 backdrop-blur-xl border border-orange-500/20 rounded-[24px] p-2.5 transition-all duration-300 focus-within:border-orange-500/50 focus-within:bg-slate-900/70 shadow-2xl">
              <textarea
                ref={textareaRef}
                value={inputMessage}
                onChange={(e) => {
                  setInputMessage(e.target.value);
                  adjustTextareaHeight();
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
  );
}
