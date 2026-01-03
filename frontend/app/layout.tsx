import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "A股ETF轮动控制台",
  description: "个人周频A股ETF轮动（仅研究学习）"
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="zh-CN">
      <body className="min-h-screen bg-slate-50 text-slate-900">
        <div className="mx-auto flex min-h-screen max-w-5xl flex-col px-4">
          <header className="flex items-center justify-between py-6">
            <div className="text-lg font-semibold">A股ETF轮动控制台</div>
            <div className="text-sm text-slate-500">个人自用（周频）</div>
          </header>
          <main className="flex-1">{children}</main>
          <footer className="py-6 text-xs text-slate-500">
            <div>姓名：Zong Youcheng</div>
            <div>© 2026 Zong Youcheng。仅供个人学习研究自用，不构成投资建议，不用于商业用途。</div>
            <div>行情数据来自公开来源（AKShare 聚合），相关版权归原平台所有。</div>
          </footer>
        </div>
      </body>
    </html>
  );
}

