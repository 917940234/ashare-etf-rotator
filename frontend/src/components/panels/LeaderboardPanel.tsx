'use client'

import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { api } from '@/lib/store'

interface LeaderboardUser {
    rank: number
    user_id: number
    username: string
    avatar: string
    total_value: number
    total_pnl: number
    total_pnl_pct: number
}

export function LeaderboardPanel() {
    const { data: rankings, isLoading } = useQuery<LeaderboardUser[]>({
        queryKey: ['leaderboard'],
        queryFn: () => api.get('/leaderboard'),
    })

    if (isLoading) {
        return (
            <div className="card text-center py-12">
                <div className="animate-spin h-8 w-8 border-4 border-blue-500 border-t-transparent rounded-full mx-auto"></div>
                <p className="mt-4 text-gray-500">加载排行榜...</p>
            </div>
        )
    }

    const getTrophy = (rank: number) => {
        if (rank === 1) return { emoji: '🏆', color: 'from-yellow-400 to-amber-500', textColor: 'text-yellow-600' }
        if (rank === 2) return { emoji: '🥈', color: 'from-gray-300 to-gray-400', textColor: 'text-gray-500' }
        if (rank === 3) return { emoji: '🥉', color: 'from-orange-400 to-orange-500', textColor: 'text-orange-600' }
        return null
    }

    return (
        <div className="space-y-4">
            <div className="card">
                <div className="flex items-center justify-between mb-4">
                    <h2 className="text-xl font-bold">🥬 韭菜排行榜</h2>
                    <span className="text-sm text-gray-500">收益率倒序排名（亏损越多排名越前）</span>
                </div>

                {/* 前三名特殊展示 */}
                {rankings && rankings.length >= 3 && (
                    <div className="grid grid-cols-3 gap-4 mb-6">
                        {/* 第二名 */}
                        <div className="flex flex-col items-center pt-8">
                            <div className="relative">
                                <img
                                    src={rankings[1]?.avatar}
                                    alt={rankings[1]?.username}
                                    className="w-16 h-16 rounded-full border-4 border-gray-300 shadow-lg"
                                />
                                <span className="absolute -bottom-2 -right-2 text-3xl">🥈</span>
                            </div>
                            <p className="mt-3 font-medium text-gray-700">{rankings[1]?.username}</p>
                            <p className={`text-sm font-bold ${rankings[1]?.total_pnl_pct >= 0 ? 'text-green-600' : 'text-red-600'}`}>
                                {rankings[1]?.total_pnl_pct >= 0 ? '+' : ''}{rankings[1]?.total_pnl_pct}%
                            </p>
                        </div>

                        {/* 第一名（最大韭菜） */}
                        <div className="flex flex-col items-center">
                            <div className="relative animate-bounce">
                                <div className="absolute -top-8 left-1/2 -translate-x-1/2 text-4xl">🏆</div>
                                <img
                                    src={rankings[0]?.avatar}
                                    alt={rankings[0]?.username}
                                    className="w-20 h-20 rounded-full border-4 border-yellow-400 shadow-xl ring-4 ring-yellow-200"
                                />
                            </div>
                            <p className="mt-3 font-bold text-lg text-yellow-700">{rankings[0]?.username}</p>
                            <p className={`text-base font-bold ${rankings[0]?.total_pnl_pct >= 0 ? 'text-green-600' : 'text-red-600'}`}>
                                {rankings[0]?.total_pnl_pct >= 0 ? '+' : ''}{rankings[0]?.total_pnl_pct}%
                            </p>
                            <span className="mt-1 px-3 py-1 bg-gradient-to-r from-yellow-400 to-amber-500 text-white text-xs font-bold rounded-full shadow">
                                韭皇
                            </span>
                        </div>

                        {/* 第三名 */}
                        <div className="flex flex-col items-center pt-12">
                            <div className="relative">
                                <img
                                    src={rankings[2]?.avatar}
                                    alt={rankings[2]?.username}
                                    className="w-14 h-14 rounded-full border-4 border-orange-300 shadow-lg"
                                />
                                <span className="absolute -bottom-2 -right-2 text-2xl">🥉</span>
                            </div>
                            <p className="mt-3 font-medium text-gray-600">{rankings[2]?.username}</p>
                            <p className={`text-sm font-bold ${rankings[2]?.total_pnl_pct >= 0 ? 'text-green-600' : 'text-red-600'}`}>
                                {rankings[2]?.total_pnl_pct >= 0 ? '+' : ''}{rankings[2]?.total_pnl_pct}%
                            </p>
                        </div>
                    </div>
                )}

                {/* 完整排行榜列表 */}
                <div className="overflow-x-auto">
                    <table className="table">
                        <thead>
                            <tr>
                                <th>排名</th>
                                <th>用户</th>
                                <th>总资产</th>
                                <th>盈亏</th>
                                <th>收益率</th>
                            </tr>
                        </thead>
                        <tbody>
                            {rankings?.map((user) => {
                                const trophy = getTrophy(user.rank)
                                return (
                                    <tr key={user.user_id} className={user.rank <= 3 ? 'bg-gradient-to-r from-yellow-50 to-transparent' : ''}>
                                        <td>
                                            <span className={`font-bold ${trophy?.textColor || 'text-gray-500'}`}>
                                                {trophy?.emoji || `#${user.rank}`}
                                            </span>
                                        </td>
                                        <td>
                                            <div className="flex items-center gap-2">
                                                <img src={user.avatar} alt={user.username} className="w-8 h-8 rounded-full" />
                                                <span className="font-medium">{user.username}</span>
                                            </div>
                                        </td>
                                        <td>¥{user.total_value.toLocaleString()}</td>
                                        <td className={user.total_pnl >= 0 ? 'text-green-600' : 'text-red-600'}>
                                            {user.total_pnl >= 0 ? '+' : ''}¥{user.total_pnl.toLocaleString()}
                                        </td>
                                        <td className={`font-bold ${user.total_pnl_pct >= 0 ? 'text-green-600' : 'text-red-600'}`}>
                                            {user.total_pnl_pct >= 0 ? '+' : ''}{user.total_pnl_pct}%
                                        </td>
                                    </tr>
                                )
                            })}
                        </tbody>
                    </table>
                </div>
            </div>
        </div>
    )
}
