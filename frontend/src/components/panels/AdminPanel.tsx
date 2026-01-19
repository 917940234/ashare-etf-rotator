'use client'

import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { api } from '@/lib/store'

interface AdminPanelProps {
    dataStatus: any
    toast: (type: 'success' | 'error', message: string) => void
}

export function AdminPanel({ dataStatus, toast }: AdminPanelProps) {
    const queryClient = useQueryClient()
    const { data: users, refetch: refetchUsers } = useQuery({ queryKey: ['adminUsers'], queryFn: () => api.get('/admin/users') })
    const { data: etfPool, refetch: refetchPool } = useQuery({ queryKey: ['etfPool'], queryFn: () => api.get('/etf/pool') })
    const [searchKeyword, setSearchKeyword] = useState('')
    const [searchResults, setSearchResults] = useState<any[]>([])
    const [showAddModal, setShowAddModal] = useState(false)
    const [addForm, setAddForm] = useState({ code: '', name: '' })

    const resetMutation = useMutation({
        mutationFn: (userId: number) => api.post(`/admin/reset-account/${userId}`),
        onSuccess: () => { toast('success', '✅ 模拟账户已重置'); refetchUsers() }
    })

    const deleteMutation = useMutation({
        mutationFn: (userId: number) => api.post(`/admin/delete-user/${userId}`),
        onSuccess: () => { toast('success', '✅ 用户已删除'); refetchUsers() },
        onError: () => toast('error', '删除失败')
    })

    const removeAssetMutation = useMutation({
        mutationFn: (code: string) => api.post(`/etf/remove/${code}`),
        onSuccess: () => { toast('success', '✅ 已移除'); refetchPool() },
        onError: (e: any) => toast('error', e.message)
    })

    const addAssetMutation = useMutation({
        mutationFn: () => api.post('/etf/add', { code: addForm.code, name: addForm.name || null }),
        onSuccess: (data: any) => {
            toast('success', data.message || '✅ 已添加')
            refetchPool()
            setShowAddModal(false)
            setAddForm({ code: '', name: '' })
        },
        onError: (e: any) => toast('error', e.message)
    })

    const updateNamesMutation = useMutation({
        mutationFn: () => api.post('/etf/update-names'),
        onSuccess: (data: any) => { toast('success', `✅ 已更新 ${data.count} 个名称`); refetchPool() }
    })

    const handleSearch = async () => {
        if (!searchKeyword.trim()) return
        try {
            const results = await api.get(`/etf/search?keyword=${encodeURIComponent(searchKeyword)}`)
            setSearchResults(results)
        } catch {
            toast('error', '搜索失败')
        }
    }

    return (
        <div className="space-y-4">
            {/* 用户管理 */}
            <div className="card">
                <h2 className="font-semibold mb-3">👥 用户管理</h2>
                <div className="overflow-x-auto">
                    <table className="table">
                        <thead>
                            <tr><th>ID</th><th>用户名</th><th>角色</th><th>注册时间</th><th>操作</th></tr>
                        </thead>
                        <tbody>
                            {users?.map((u: any) => (
                                <tr key={u.id}>
                                    <td>{u.id}</td>
                                    <td>{u.username}</td>
                                    <td>{u.is_admin ? <span className="badge badge-red">管理员</span> : <span className="badge badge-blue">用户</span>}</td>
                                    <td className="text-sm text-gray-500">{u.created_at?.slice(0, 10)}</td>
                                    <td className="space-x-2">
                                        <button
                                            className="text-orange-600 text-sm hover:underline"
                                            onClick={() => { if (confirm('确认重置该用户的模拟交易资金为初始值？')) resetMutation.mutate(u.id) }}
                                        >
                                            重置模拟资金
                                        </button>
                                        {!u.is_admin && (
                                            <button
                                                className="text-red-600 text-sm hover:underline"
                                                onClick={() => { if (confirm('确认删除该用户？')) deleteMutation.mutate(u.id) }}
                                            >
                                                删除用户
                                            </button>
                                        )}
                                    </td>
                                </tr>
                            ))}
                        </tbody>
                    </table>
                </div>
            </div>

            {/* ETF 资产池管理 */}
            <div className="card">
                <div className="flex justify-between items-center mb-3">
                    <h2 className="font-semibold">📊 ETF 资产池管理</h2>
                    <div className="flex gap-2">
                        <button
                            className="btn btn-sm btn-secondary"
                            onClick={() => updateNamesMutation.mutate()}
                            disabled={updateNamesMutation.isPending}
                        >
                            {updateNamesMutation.isPending ? (
                                <span className="flex items-center gap-2">
                                    <svg className="animate-spin h-4 w-4" viewBox="0 0 24 24">
                                        <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" fill="none" />
                                        <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
                                    </svg>
                                    更新中...
                                </span>
                            ) : '🔄 联网更新名称'}
                        </button>
                        <button className="btn btn-sm btn-primary" onClick={() => setShowAddModal(true)}>
                            + 添加 ETF
                        </button>
                    </div>
                </div>

                <div className="space-y-3">
                    <div>
                        <h4 className="text-sm font-medium text-gray-500 mb-2">📈 股票类（动量轮动）</h4>
                        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-2">
                            {etfPool?.risk?.map((a: any) => (
                                <div key={a.code} className="flex items-center justify-between p-2 bg-blue-50 rounded-lg">
                                    <div>
                                        <span className="font-mono text-sm">{a.code}</span>
                                        <span className="ml-2">{a.name}</span>
                                    </div>
                                    <button
                                        className="text-red-500 text-sm hover:underline"
                                        onClick={() => { if (confirm(`确认移除 ${a.name}？`)) removeAssetMutation.mutate(a.code) }}
                                    >
                                        移除
                                    </button>
                                </div>
                            ))}
                        </div>
                    </div>
                    <div>
                        <h4 className="text-sm font-medium text-gray-500 mb-2">🛡️ 债券类（防守配置）</h4>
                        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-2">
                            {etfPool?.defensive?.map((a: any) => (
                                <div key={a.code} className="flex items-center justify-between p-2 bg-green-50 rounded-lg">
                                    <div>
                                        <span className="font-mono text-sm">{a.code}</span>
                                        <span className="ml-2">{a.name}</span>
                                        <span className="ml-2 text-xs text-gray-500">({(a.weight * 100).toFixed(0)}%)</span>
                                    </div>
                                    <button
                                        className="text-red-500 text-sm hover:underline"
                                        onClick={() => { if (confirm(`确认移除 ${a.name}？`)) removeAssetMutation.mutate(a.code) }}
                                    >
                                        移除
                                    </button>
                                </div>
                            ))}
                        </div>
                    </div>
                </div>
            </div>

            {/* 数据状态 */}
            <div className="card">
                <div className="flex justify-between items-center mb-3">
                    <h2 className="font-semibold">💾 数据状态</h2>
                    {dataStatus?.last_update && (
                        <div className="text-sm text-gray-500">
                            🕐 最后更新: <span className="font-medium text-gray-700">{new Date(dataStatus.last_update).toLocaleString('zh-CN')}</span>
                            {dataStatus.updated_by && <span className="ml-2 badge badge-blue">{dataStatus.updated_by}</span>}
                        </div>
                    )}
                </div>
                <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-2">
                    {dataStatus?.etf_status && Object.entries(dataStatus.etf_status).map(([code, info]: [string, any]) => (
                        <div key={code} className="flex flex-col p-3 bg-gray-50 rounded text-sm">
                            <div className="flex items-center justify-between mb-1">
                                <span className="font-mono font-medium">{code}</span>
                                <span className={`badge ${info.rows > 0 ? 'badge-green' : 'badge-red'}`}>
                                    {info.rows > 0 ? `${info.rows}条` : '无'}
                                </span>
                            </div>
                            <div className="text-xs text-gray-500 truncate" title={info.name}>{info.name}</div>
                            {info.last_date && (
                                <div className="text-xs text-gray-400 mt-1">截至 {info.last_date}</div>
                            )}
                        </div>
                    ))}
                </div>
            </div>

            {/* 添加 ETF 弹窗 */}
            {showAddModal && (
                <div className="dialog-overlay" onClick={() => setShowAddModal(false)}>
                    <div className="dialog-content" onClick={e => e.stopPropagation()}>
                        <h3 className="text-lg font-semibold mb-4">➕ 添加 ETF 到资产池</h3>
                        <div className="space-y-4">
                            <div className="flex gap-2">
                                <input
                                    className="input flex-1"
                                    placeholder="搜索 ETF 代码或名称"
                                    value={searchKeyword}
                                    onChange={e => setSearchKeyword(e.target.value)}
                                    onKeyDown={e => e.key === 'Enter' && handleSearch()}
                                />
                                <button className="btn btn-secondary" onClick={handleSearch}>搜索</button>
                            </div>
                            {searchResults.length > 0 && (
                                <div className="max-h-60 overflow-y-auto border rounded-lg">
                                    {searchResults.map((r: any) => (
                                        <div
                                            key={r.code}
                                            className="flex justify-between items-center p-3 border-b hover:bg-blue-50 cursor-pointer transition-colors"
                                            onClick={() => { setAddForm({ ...addForm, code: r.code, name: r.name }); setSearchResults([]) }}
                                        >
                                            <div>
                                                <span className="font-mono font-medium">{r.code}</span>
                                                <span className="ml-2">{r.name}</span>
                                            </div>
                                            <div className="text-right">
                                                <span className="text-sm text-gray-600">¥{r.price?.toFixed(3)}</span>
                                                {r.change_pct != null && (
                                                    <span className={`ml-2 text-xs ${r.change_pct >= 0 ? 'text-red-500' : 'text-green-500'}`}>
                                                        {r.change_pct >= 0 ? '+' : ''}{r.change_pct?.toFixed(2)}%
                                                    </span>
                                                )}
                                            </div>
                                        </div>
                                    ))}
                                </div>
                            )}
                            {addForm.code && (
                                <div className="bg-blue-50 p-3 rounded-lg border border-blue-200">
                                    <p className="text-sm text-gray-600">已选择：</p>
                                    <p className="font-medium">
                                        <span className="font-mono">{addForm.code}</span> {addForm.name || '(自动获取名称)'}
                                    </p>
                                </div>
                            )}
                            <div className="text-xs text-gray-500 bg-gray-50 p-3 rounded-lg">
                                <p>💡 提示：系统将自动判断 ETF 类型（股票类/债券类）并添加到对应池中。</p>
                            </div>
                            <div className="flex gap-3">
                                <button className="btn btn-secondary flex-1" onClick={() => setShowAddModal(false)}>取消</button>
                                <button
                                    className="btn btn-primary flex-1"
                                    onClick={() => addAssetMutation.mutate()}
                                    disabled={addAssetMutation.isPending || !addForm.code}
                                >
                                    {addAssetMutation.isPending ? '添加中...' : '确认添加'}
                                </button>
                            </div>
                        </div>
                    </div>
                </div>
            )}
        </div>
    )
}
