import './globals.css'
import type { Metadata } from 'next'
import { Providers } from './providers'

export const metadata: Metadata = {
    title: 'QuantRotator | 量化轮动投资系统',
    description: '基于股债轮动策略的A股ETF月频量化投资系统，支持策略回测与模拟交易',
}

export default function RootLayout({
    children,
}: {
    children: React.ReactNode
}) {
    return (
        <html lang="zh-CN">
            <body className="min-h-screen bg-gray-50">
                <Providers>
                    {children}
                </Providers>
            </body>
        </html>
    )
}
