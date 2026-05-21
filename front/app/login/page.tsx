"use client"

import { useEffect, useState } from "react"
import type { FormEvent } from "react"
import { useRouter } from "next/navigation"
import Image from "next/image"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { LogIn } from "lucide-react"
import { useAuth } from "@/contexts/AuthContext"

export default function LoginPage() {
  const router = useRouter()
  const { currentUser, isHydrated, login } = useAuth()
  const [studentId, setStudentId] = useState("")
  const [password, setPassword] = useState("")
  const [submitting, setSubmitting] = useState(false)
  const [errorMessage, setErrorMessage] = useState("")

  useEffect(() => {
    if (isHydrated && currentUser) {
      router.replace("/")
    }
  }, [currentUser, isHydrated, router])

  const handleSubmit = async (event: FormEvent) => {
    event.preventDefault()
    const trimmedId = studentId.trim()
    if (!trimmedId || !password) {
      setErrorMessage("请输入学号和密码")
      return
    }
    setSubmitting(true)
    setErrorMessage("")
    const result = await login(trimmedId, password)
    setSubmitting(false)
    if (result.ok) {
      router.replace("/")
    } else {
      setErrorMessage(result.error)
      setPassword("")
    }
  }

  return (
    <div className="min-h-screen flex items-center justify-center bg-gradient-to-br from-slate-900 via-blue-900 to-slate-800 px-4">
      <Card className="w-full max-w-md bg-slate-800/70 border-slate-600 backdrop-blur shadow-2xl">
        <CardHeader className="text-center space-y-3">
          <div className="flex items-center justify-center">
            <Image
              src="/images/swjtu-logo.png"
              alt="SWJTU"
              width={48}
              height={48}
              className="rounded"
            />
          </div>
          <CardTitle className="text-2xl text-white">焊育智眸</CardTitle>
          <p className="text-sm text-gray-400">请使用学号和密码登录</p>
        </CardHeader>
        <CardContent>
          <form onSubmit={handleSubmit} className="space-y-4">
            <div className="space-y-2">
              <Label htmlFor="student_id" className="text-gray-300">
                学号
              </Label>
              <Input
                id="student_id"
                autoComplete="username"
                inputMode="numeric"
                placeholder="例如 2024001"
                value={studentId}
                onChange={(event) => setStudentId(event.target.value)}
                disabled={submitting}
                className="bg-slate-900/60 border-slate-600 text-white placeholder:text-gray-500"
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="password" className="text-gray-300">
                密码
              </Label>
              <Input
                id="password"
                type="password"
                autoComplete="current-password"
                placeholder="初始密码请联系老师"
                value={password}
                onChange={(event) => setPassword(event.target.value)}
                disabled={submitting}
                className="bg-slate-900/60 border-slate-600 text-white placeholder:text-gray-500"
              />
            </div>
            {errorMessage && (
              <div className="px-3 py-2 rounded bg-red-500/10 text-red-300 text-sm border border-red-500/30">
                {errorMessage}
              </div>
            )}
            <Button type="submit" className="w-full" disabled={submitting}>
              <LogIn className="w-4 h-4 mr-2" />
              {submitting ? "登录中..." : "登录"}
            </Button>
          </form>
          <p className="text-xs text-gray-500 text-center mt-6">
            账号由学校预设；忘记密码请联系老师重置。
          </p>
        </CardContent>
      </Card>
    </div>
  )
}
