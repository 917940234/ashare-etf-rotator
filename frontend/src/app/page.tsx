'use client'

import { useState, useEffect, useCallback, Suspense } from 'react'
import { useRouter, useSearchParams } from 'next/navigation'
import { useQueryClient, useQuery } from '@tanstack/react-query'
import { useAuthStore } from '@/lib/store'

// Hooks
import {
    useToast,
    useSignal,
    usePrices,
    useBacktest,
    useAccount,
    useAdvice,
    useRefreshAdvice,
    useTrade,
    useBatchTrade,
    useUpdateData,
    useNavHistory,
} from '@/hooks'

// Components
import { Toast } from '@/components/ui/Toast'
import { TradeModal, RebalanceWizard, ProfileModal, GuideModal } from '@/components/modals'
import { StrategyPanel, BacktestPanel, TradingPanel, AdminPanel, LeaderboardPanel, MessagePanel } from '@/components/panels'

type TabType = 'signal' | 'backtest' | 'trading' | 'leaderboard' | 'messages' | 'admin'
const VALID_TABS: TabType[] = ['signal', 'backtest', 'trading', 'leaderboard', 'messages', 'admin']

// 加载占位组件
function DashboardLoading() {
    return (
        <div className="min-h-screen bg-gray-50 flex items-center justify-center">
            <div className="text-center">
                <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600 mx-auto mb-4"></div>
                <p className="text-gray-500">加载中...</p>
            </div>
        </div>
    )
}

// 主组件入口（用 Suspense 包裹）
export default function Dashboard() {
    return (
        <Suspense fallback={<DashboardLoading />}>
            <DashboardContent />
        </Suspense>
    )
}

// 实际内容组件
function DashboardContent() {
    const router = useRouter()
    const searchParams = useSearchParams()
    const queryClient = useQueryClient()
    const { user, isLoggedIn, logout } = useAuthStore()

    // 从 URL 读取初始 Tab 状态
    const getInitialTab = (): TabType => {
        const urlTab = searchParams.get('tab') as TabType
        return VALID_TABS.includes(urlTab) ? urlTab : 'signal'
    }

    // 状态
    const [mounted, setMounted] = useState(false)
    const [activeTab, setActiveTab] = useState<TabType>(getInitialTab())
    const [showUserMenu, setShowUserMenu] = useState(false)

    // Tab 切换时同步到 URL
    const handleTabChange = useCallback((tab: TabType) => {
        setActiveTab(tab)
        const params = new URLSearchParams(searchParams.toString())
        params.set('tab', tab)
        router.push(`?${params.toString()}`, { scroll: false })
    }, [router, searchParams])

    // 弹窗状态
    const [showTradeModal, setShowTradeModal] = useState(false)
    const [showRebalanceWizard, setShowRebalanceWizard] = useState(false)
    const [showProfileModal, setShowProfileModal] = useState(false)
    const [showGuide, setShowGuide] = useState(false)

    // 交易表单状态
    const [tradeType, setTradeType] = useState<'buy' | 'sell'>('buy')
    const [tradeSymbol, setTradeSymbol] = useState('')
    const [tradeAmount, setTradeAmount] = useState('')

    // Toast
    const { toast, showToast } = useToast()

    // 数据查询
    const { data: signal } = useSignal(mounted && isLoggedIn())
    const { data: prices } = usePrices(mounted && isLoggedIn())
    const { data: account } = useAccount(mounted && isLoggedIn() && activeTab === 'trading')
    const { data: advice } = useAdvice(mounted && isLoggedIn() && activeTab === 'trading')
    const { data: navHistory } = useNavHistory(mounted && isLoggedIn() && activeTab === 'trading')

    // Admin 数据状态查询
    const { data: dataStatus } = useQuery({
        queryKey: ['dataStatus'],
        queryFn: () => import('@/lib/store').then(m => m.api.get('/data/status')),
        enabled: mounted && isLoggedIn() && activeTab === 'admin',
    })

    // Mutations
    const backtestMutation = useBacktest({
        onSuccess: () => showToast('success', '✅ 回测完成'),
        onError: (err) => showToast('error', err.message),
    })

    const updateDataMutation = useUpdateData({
        onSuccess: () => showToast('success', '🔄 数据更新已开始'),
    })

    const tradeMutation = useTrade({
        onSuccess: () => {
            showToast('success', `✅ ${tradeType === 'buy' ? '买入' : '卖出'}成功`)
            setShowTradeModal(false)
        },
        onError: (err) => showToast('error', err.message),
    })

    const batchTradeMutation = useBatchTrade({
        onSuccess: (data) => {
            const successCount = data.results.filter((r: any) => r.success).length
            showToast('success', `✅ 批量执行完成：成功 ${successCount}/${data.results.length} 笔`)
            setShowRebalanceWizard(false)
        },
        onError: (err) => showToast('error', '批量执行失败：' + err.message),
    })

    const refreshAdviceMutation = useRefreshAdvice()

    // Effects
    useEffect(() => { setMounted(true) }, [])
    useEffect(() => {
        if (mounted && !isLoggedIn()) router.push('/login')
    }, [mounted, isLoggedIn, router])
    useEffect(() => {
        if (mounted && isLoggedIn() && !localStorage.getItem('v5_guide_done')) {
            setShowGuide(true)
        }
    }, [mounted, isLoggedIn])

    // Handlers
    const handleOpenTrade = useCallback((type: 'buy' | 'sell', symbol?: string, amount?: string) => {
        setTradeType(type)
        setTradeSymbol(symbol || '')
        setTradeAmount(amount || '')
        setShowTradeModal(true)
    }, [])

    const handleTrade = useCallback((type: 'buy' | 'sell', symbol: string, amount: number) => {
        if (type === 'buy') {
            tradeMutation.mutate({ type, symbol, amount })
        } else {
            tradeMutation.mutate({ type, symbol, shares: amount })
        }
    }, [tradeMutation])

    if (!mounted || !isLoggedIn()) return null

    return (
        <div className="min-h-screen bg-gray-50">
            {/* 导航栏 */}
            <nav className="bg-white border-b border-gray-200 px-6 py-3 sticky top-0 z-40">
                <div className="max-w-7xl mx-auto flex items-center justify-between">
                    <div className="flex items-center gap-3">
                        <h1 className="text-xl font-bold bg-gradient-to-r from-blue-600 via-indigo-600 to-purple-600 bg-clip-text text-transparent flex items-center gap-2">
                            <span className="text-2xl">📊</span>
                            QuantRotator
                        </h1>
                        <span className="badge badge-blue text-xs">v5.0</span>
                    </div>
                    <div className="flex items-center gap-6">

                        {/* 用户菜单 */}
                        <div className="relative">
                            <button
                                className="flex items-center gap-2 px-3 py-2 rounded-lg hover:bg-gray-100 transition-colors"
                                onClick={() => setShowUserMenu(!showUserMenu)}
                            >
                                <img
                                    src={user?.avatar || `https://api.dicebear.com/7.x/avataaars/svg?seed=${user?.username}`}
                                    alt={user?.username}
                                    className="w-8 h-8 rounded-full"
                                />
                                <span className="text-sm text-gray-700">{user?.username}</span>
                                {user?.is_admin && <span className="badge badge-red text-xs">管理员</span>}
                                <svg className={`w-4 h-4 text-gray-400 transition-transform ${showUserMenu ? 'rotate-180' : ''}`} fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
                                </svg>
                            </button>
                            {showUserMenu && (
                                <>
                                    <div className="fixed inset-0 z-40" onClick={() => setShowUserMenu(false)} />
                                    <div className="absolute right-0 mt-2 w-48 bg-white rounded-lg shadow-lg border border-gray-100 py-1 z-50">
                                        <div className="px-4 py-2 border-b border-gray-100">
                                            <p className="text-sm font-medium text-gray-900">{user?.username}</p>
                                            <p className="text-xs text-gray-500">{user?.is_admin ? '管理员账户' : '普通用户'}</p>
                                        </div>
                                        <button
                                            className="w-full text-left px-4 py-2 text-sm text-gray-700 hover:bg-gray-50"
                                            onClick={() => { setShowProfileModal(true); setShowUserMenu(false) }}
                                        >
                                            ⚙️ 账户设置
                                        </button>
                                        {user?.is_admin && (
                                            <button
                                                className="w-full text-left px-4 py-2 text-sm text-gray-700 hover:bg-gray-50"
                                                onClick={() => { handleTabChange('admin'); setShowUserMenu(false) }}
                                            >
                                                🛠️ 系统管理
                                            </button>
                                        )}
                                        <div className="border-t border-gray-100 mt-1" />
                                        <button
                                            className="w-full text-left px-4 py-2 text-sm text-red-600 hover:bg-red-50"
                                            onClick={() => { logout(); router.push('/login') }}
                                        >
                                            🚪 退出登录
                                        </button>
                                    </div>
                                </>
                            )}
                        </div>
                    </div>
                </div>
            </nav>

            {/* Toast */}
            <Toast toast={toast} />

            {/* Tab 切换 */}
            <div className="max-w-7xl mx-auto px-6 mt-4">
                <div className="flex gap-1 bg-gray-100 p-1 rounded-lg w-fit flex-wrap">
                    {[
                        { key: 'signal', label: '📊 策略信号' },
                        { key: 'backtest', label: '📈 回测分析' },
                        { key: 'trading', label: '💰 模拟交易' },
                        { key: 'leaderboard', label: '🥬 韭菜排行' },
                        { key: 'messages', label: '💬 留言墙' },
                    ].map((tab) => (
                        <button
                            key={tab.key}
                            onClick={() => handleTabChange(tab.key as TabType)}
                            className={`px-4 py-2 rounded-md text-sm font-medium transition-colors ${activeTab === tab.key ? 'bg-white shadow text-blue-600' : 'text-gray-600 hover:text-gray-900'}`}
                        >
                            {tab.label}
                        </button>
                    ))}
                </div>
            </div>

            {/* 主内容区 */}
            <main className="max-w-7xl mx-auto px-6 py-4 space-y-4">
                {activeTab === 'signal' && signal && !signal.error && (
                    <StrategyPanel signal={signal} />
                )}

                {activeTab === 'backtest' && (
                    <BacktestPanel
                        backtest={backtestMutation.data}
                        isLoading={backtestMutation.isPending}
                        onRunBacktest={() => backtestMutation.mutate()}
                    />
                )}

                {activeTab === 'trading' && account && (
                    <TradingPanel
                        account={account}
                        advice={advice}
                        navHistory={navHistory}
                        onOpenTrade={handleOpenTrade}
                        onOpenRebalance={() => setShowRebalanceWizard(true)}
                        onRefreshAdvice={() => refreshAdviceMutation.mutate()}
                        isRefreshingAdvice={refreshAdviceMutation.isPending}
                    />
                )}

                {activeTab === 'leaderboard' && (
                    <LeaderboardPanel />
                )}

                {activeTab === 'messages' && (
                    <MessagePanel />
                )}

                {activeTab === 'admin' && user?.is_admin && (
                    <AdminPanel dataStatus={dataStatus} toast={showToast} />
                )}
            </main>

            {/* Footer */}
            <footer className="footer">
                <p className="text-sm">
                    © 2026 Zong Youcheng. All rights reserved. &nbsp;|&nbsp;
                    <span className="text-gray-400">⚠️ 风险提示：本系统仅供学习研究，不构成投资建议。</span>
                </p>
            </footer>

            {/* Modals */}
            <TradeModal
                isOpen={showTradeModal}
                onClose={() => setShowTradeModal(false)}
                tradeType={tradeType}
                initialSymbol={tradeSymbol}
                initialAmount={tradeAmount}
                prices={prices}
                onTrade={handleTrade}
                isPending={tradeMutation.isPending}
            />

            <RebalanceWizard
                isOpen={showRebalanceWizard}
                onClose={() => setShowRebalanceWizard(false)}
                actions={advice?.actions || []}
                onExecute={(actions) => batchTradeMutation.mutate(actions)}
                isPending={batchTradeMutation.isPending}
            />

            <ProfileModal
                isOpen={showProfileModal}
                onClose={() => setShowProfileModal(false)}
                user={user}
                onSuccess={() => showToast('success', '密码修改成功')}
                onError={(msg) => showToast('error', msg)}
            />

            <GuideModal
                isOpen={showGuide}
                onClose={() => setShowGuide(false)}
            />
        </div>
    )
}
