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

    const handleSubmit = async (e: React.FormEvent) => {
        e.preventDefault()
        setError('')
        setLoading(true)

        try {
            if (isLogin) {
                const data = await api.post('/auth/login', { username, password })
                setAuth(data.access_token, data.user)
                router.push('/')
            } else {
                await api.post('/auth/register', { username, password })
                // 注册成功后自动登录
                const data = await api.post('/auth/login', { username, password })
                setAuth(data.access_token, data.user)
                router.push('/')
            }
        } catch (err: any) {
            setError(err.message)
        } finally {
            setLoading(false)
        }
    }

    return (
        <div className="min-h-screen bg-gradient-to-br from-blue-50 to-indigo-100 flex items-center justify-center p-4">
            <div className="w-full max-w-md">
                {/* Logo */}
                <div className="text-center mb-8">
                    <div className="text-5xl mb-2">📈</div>
                    <h1 className="text-2xl font-bold text-gray-900">股债轮动系统</h1>
                    <p className="text-gray-500 mt-1">A股 ETF 月频轮动策略</p>
                </div>

                {/* 表单 */}
                <div className="bg-white rounded-2xl shadow-xl p-8">
                    {/* 切换标签 */}
                    <div className="flex mb-6 bg-gray-100 rounded-lg p-1">
                        <button
                            className={`flex-1 py-2 rounded-md text-sm font-medium transition-colors ${isLogin ? 'bg-white shadow text-blue-600' : 'text-gray-500'
                                }`}
                            onClick={() => setIsLogin(true)}
                        >
                            登录
                        </button>
                        <button
                            className={`flex-1 py-2 rounded-md text-sm font-medium transition-colors ${!isLogin ? 'bg-white shadow text-blue-600' : 'text-gray-500'
                                }`}
                            onClick={() => setIsLogin(false)}
                        >
                            注册
                        </button>
                    </div>

                    <form onSubmit={handleSubmit} className="space-y-4">
                        <div>
                            <label className="label">用户名</label>
                            <input
                                type="text"
                                className="input mt-1"
                                value={username}
                                onChange={(e) => setUsername(e.target.value)}
                                placeholder="请输入用户名"
                                required
                            />
                        </div>
                        <div>
                            <label className="label">密码</label>
                            <input
                                type="password"
                                className="input mt-1"
                                value={password}
                                onChange={(e) => setPassword(e.target.value)}
                                placeholder="请输入密码"
                                required
                            />
                        </div>

                        {error && (
                            <div className="text-red-500 text-sm bg-red-50 p-3 rounded-lg">
                                {error}
                            </div>
                        )}

                        <button
                            type="submit"
                            className="btn btn-primary w-full h-11"
                            disabled={loading}
                        >
                            {loading ? '处理中...' : isLogin ? '登录' : '注册'}
                        </button>
                    </form>
                </div>

                {/* 版权 */}
                <div className="text-center mt-6 text-sm text-gray-400">
                    © 2026 Zong Youcheng. All rights reserved.
                </div>
            </div>
        </div>
    )
}
