import type { Metadata } from 'next'
import './globals.css'
import { DataTreeProvider } from '@/components/data-tree/data-tree-context'

export const metadata: Metadata = {
  title: '智能检测教学',
  description: '焊缝智能检测教学AI系统 - 智能检测 · 精准教学 · 技能提升',
}

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode
}>) {
  return (
    <html lang="en">
      <body>
        <DataTreeProvider>
          {children}
        </DataTreeProvider>
      </body>
    </html>
  )
}
