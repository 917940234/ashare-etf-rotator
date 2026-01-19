'use client'

import { useState } from 'react'
import { useRouter } from 'next/navigation'
import { useAuthStore, api } from '@/lib/store'

export default function LoginPage() {
    const router = useRouter()
    const { setAuth } = useAuthStore()

    const [isLogin, setIsLogin] = useState(true)
    const [username, setUsername] = useState('')
    const [password, setPassword] = useState('')
    const [error, setError] = useState('')
    const [loading, setLoading] = useState(false)

    // 前端验证
    const validateInput = (): string | null => {
        if (!username.trim()) {
            return '请输入用户名'
        }
        if (!password) {
            return '请输入密码'
        }
        if (!isLogin) {
            // 注册时的额外验证
            if (username.trim().length < 2) {
                return '用户名至少需要2个字符'
            }
            if (password.length < 6) {
                return '密码至少需要6个字符'
            }
        }
        return null
    }

    const handleSubmit = async (e: React.FormEvent) => {
        e.preventDefault()

        // 前端验证
        const validationError = validateInput()
        if (validationError) {
            setError(validationError)
            return
        }

        setError('')
        setLoading(true)

        try {
            if (isLogin) {
                const data = await api.post('/auth/login', { username: username.trim(), password })
                setAuth(data.access_token, data.user)
                router.push('/')
            } else {
                await api.post('/auth/register', { username: username.trim(), password })
                // 注册成功后自动登录
                const data = await api.post('/auth/login', { username: username.trim(), password })
                setAuth(data.access_token, data.user)
                router.push('/')
            }
        } catch (err: any) {
            // 解析错误信息，提供更友好的提示
            const errorMsg = err.message || '操作失败，请稍后重试'
            setError(errorMsg)
        } finally {
            setLoading(false)
        }
    }

    return (
        <div className="min-h-screen bg-gradient-to-br from-slate-900 via-slate-800 to-slate-900 flex items-center justify-center p-4 relative overflow-hidden">
            {/* 背景装饰 - 金融数据流效果 */}
            <div className="absolute inset-0 overflow-hidden pointer-events-none">
                <div className="absolute top-1/4 left-1/4 w-96 h-96 bg-amber-500/5 rounded-full blur-3xl" />
                <div className="absolute bottom-1/4 right-1/4 w-96 h-96 bg-amber-600/5 rounded-full blur-3xl" />
                <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-[600px] h-[600px] bg-slate-700/20 rounded-full blur-3xl" />
            </div>

            <div className="w-full max-w-md relative z-10">
                {/* Logo */}
                <div className="text-center mb-8">
                    {/* SVG 图表图标 */}
                    <div className="inline-flex items-center justify-center w-16 h-16 rounded-2xl bg-gradient-to-br from-amber-400 to-amber-600 shadow-lg shadow-amber-500/25 mb-4">
                        <svg className="w-8 h-8 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 7h8m0 0v8m0-8l-8 8-4-4-6 6" />
                        </svg>
                    </div>
                    <h1 className="text-3xl font-bold bg-gradient-to-r from-amber-200 via-yellow-400 to-amber-500 bg-clip-text text-transparent">
                        QuantRotator
                    </h1>
                    <p className="text-slate-400 mt-2 text-sm">A股 ETF 月频轮动策略系统</p>
                </div>

                {/* 表单卡片 - 毛玻璃效果 */}
                <div className="backdrop-blur-xl bg-slate-800/50 rounded-2xl shadow-2xl p-8 border border-slate-700/50">
                    {/* 切换标签 */}
                    <div className="flex mb-6 bg-slate-900/50 rounded-xl p-1">
                        <button
                            className={`flex-1 py-2.5 rounded-lg text-sm font-medium transition-all duration-200 ${isLogin
                                ? 'bg-gradient-to-r from-amber-500 to-amber-600 text-white shadow-lg shadow-amber-500/25'
                                : 'text-slate-400 hover:text-slate-300'
                                }`}
                            onClick={() => { setIsLogin(true); setError('') }}
                        >
                            登录
                        </button>
                        <button
                            className={`flex-1 py-2.5 rounded-lg text-sm font-medium transition-all duration-200 ${!isLogin
                                ? 'bg-gradient-to-r from-amber-500 to-amber-600 text-white shadow-lg shadow-amber-500/25'
                                : 'text-slate-400 hover:text-slate-300'
                                }`}
                            onClick={() => { setIsLogin(false); setError('') }}
                        >
                            注册
                        </button>
                    </div>

                    <form onSubmit={handleSubmit} className="space-y-5">
                        <div>
                            <label className="block text-sm font-medium text-slate-300 mb-2">用户名</label>
                            <input
                                type="text"
                                className="w-full h-11 px-4 rounded-xl bg-slate-900/50 border border-slate-600/50 text-slate-100 placeholder-slate-500 focus:outline-none focus:ring-2 focus:ring-amber-500/50 focus:border-amber-500/50 transition-all"
                                value={username}
                                onChange={(e) => setUsername(e.target.value)}
                                placeholder="请输入用户名"
                            />
                            {!isLogin && (
                                <p className="mt-1.5 text-xs text-slate-500">用户名至少2个字符</p>
                            )}
                        </div>
                        <div>
                            <label className="block text-sm font-medium text-slate-300 mb-2">密码</label>
                            <input
                                type="password"
                                className="w-full h-11 px-4 rounded-xl bg-slate-900/50 border border-slate-600/50 text-slate-100 placeholder-slate-500 focus:outline-none focus:ring-2 focus:ring-amber-500/50 focus:border-amber-500/50 transition-all"
                                value={password}
                                onChange={(e) => setPassword(e.target.value)}
                                placeholder="请输入密码"
                            />
                            {!isLogin && (
                                <p className="mt-1.5 text-xs text-slate-500">密码至少6个字符</p>
                            )}
                        </div>

                        {/* 错误提示 - 更醒目的设计 */}
                        {error && (
                            <div className="flex items-start gap-3 p-4 rounded-xl bg-red-500/10 border border-red-500/20">
                                <svg className="w-5 h-5 text-red-400 flex-shrink-0 mt-0.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
                                </svg>
                                <div>
                                    <p className="text-sm font-medium text-red-400">{isLogin ? '登录失败' : '注册失败'}</p>
                                    <p className="text-sm text-red-300/80 mt-0.5">{error}</p>
                                </div>
                            </div>
                        )}

                        <button
                            type="submit"
                            className="w-full h-12 rounded-xl bg-gradient-to-r from-amber-500 to-amber-600 text-white font-semibold shadow-lg shadow-amber-500/25 hover:from-amber-400 hover:to-amber-500 focus:outline-none focus:ring-2 focus:ring-amber-500/50 disabled:opacity-50 disabled:cursor-not-allowed transition-all duration-200"
                            disabled={loading}
                        >
                            {loading ? (
                                <span className="flex items-center justify-center gap-2">
                                    <svg className="animate-spin h-5 w-5" fill="none" viewBox="0 0 24 24">
                                        <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                                        <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
                                    </svg>
                                    处理中...
                                </span>
                            ) : isLogin ? '登录' : '注册'}
                        </button>
                    </form>

                    {/* 提示信息 */}
                    <div className="mt-6 pt-6 border-t border-slate-700/50">
                        <p className="text-center text-xs text-slate-500">
                            {isLogin ? '还没有账号？点击上方"注册"创建账号' : '已有账号？点击上方"登录"进入系统'}
                        </p>
                    </div>
                </div>

                {/* 版权 */}
                <div className="text-center mt-8 text-sm text-slate-500">
                    <p>© 2026 Zong Youcheng. All rights reserved.</p>
                    <p className="mt-1 text-xs text-slate-600">⚠️ 本系统仅供学习研究，不构成投资建议</p>
                </div>
            </div>
        </div>
    )
}
