'use client'

import { useMemo } from 'react'
import dynamic from 'next/dynamic'
import { AccountData, AdviceData, TradeAction, NavHistoryItem } from '@/hooks/useTrading'

const ReactECharts = dynamic(() => import('echarts-for-react'), { ssr: false })

interface TradingPanelProps {
    account: AccountData
    advice: AdviceData | undefined
    navHistory?: NavHistoryItem[]
    onOpenTrade: (type: 'buy' | 'sell', symbol?: string, amount?: string) => void
    onOpenRebalance: () => void
    onRefreshAdvice?: () => void
    isRefreshingAdvice?: boolean
}

export function TradingPanel({
    account,
    advice,
    navHistory,
    onOpenTrade,
    onOpenRebalance,
    onRefreshAdvice,
    isRefreshingAdvice,
}: TradingPanelProps) {
    const summaryCards = [
        { label: '总资产', value: `¥${account.total_value?.toLocaleString()}`, color: 'text-blue-600', bg: 'bg-blue-50' },
        { label: '可用现金', value: `¥${account.cash?.toLocaleString()}`, color: '', bg: 'bg-gray-50' },
        { label: '持仓市值', value: `¥${account.positions_value?.toLocaleString()}`, color: '', bg: 'bg-gray-50' },
        { label: '累计盈亏', value: `${account.total_pnl >= 0 ? '+' : ''}¥${account.total_pnl?.toLocaleString()}`, color: account.total_pnl >= 0 ? 'text-red-600' : 'text-green-600', bg: 'bg-gray-50' },
        { label: '收益率', value: `${account.total_pnl_pct >= 0 ? '+' : ''}${account.total_pnl_pct}%`, color: account.total_pnl_pct >= 0 ? 'text-red-600' : 'text-green-600', bg: 'bg-gray-50' }
    ]

    // 收益曲线图配置
    const navChartOption = useMemo(() => {
        if (!navHistory || navHistory.length === 0) return null

        const dates = navHistory.map(h => h.date)
        const values = navHistory.map(h => h.value)
        const initialValue = 100000 // 初始资金
        const navNormed = values.map(v => (v / initialValue * 100))

        return {
            tooltip: {
                trigger: 'axis',
                formatter: (params: any) => {
                    const data = params[0]
                    const value = values[data.dataIndex]
                    const pnl = value - initialValue
                    const pnlPct = ((value / initialValue - 1) * 100).toFixed(2)
                    return `${data.axisValue}<br/>
                        净值: ¥${value.toLocaleString()}<br/>
                        盈亏: ${pnl >= 0 ? '+' : ''}¥${pnl.toLocaleString()} (${pnl >= 0 ? '+' : ''}${pnlPct}%)`
                }
            },
            grid: { left: 50, right: 30, top: 40, bottom: 30 },
            xAxis: {
                type: 'category',
                data: dates,
                axisLabel: { interval: Math.max(0, Math.floor(dates.length / 6) - 1) }
            },
            yAxis: {
                type: 'value',
                scale: true,
                name: '净值指数',
                axisLabel: { formatter: (v: number) => v.toFixed(0) }
            },
            series: [{
                name: '我的组合',
                type: 'line',
                data: navNormed,
                smooth: true,
                lineStyle: { width: 3, color: '#3b82f6' },
                areaStyle: {
                    color: {
                        type: 'linear',
                        x: 0, y: 0, x2: 0, y2: 1,
                        colorStops: [
                            { offset: 0, color: 'rgba(59, 130, 246, 0.3)' },
                            { offset: 1, color: 'rgba(59, 130, 246, 0.05)' }
                        ]
                    }
                },
                itemStyle: { color: '#3b82f6' }
            }]
        }
    }, [navHistory])

    // 获取偏离度等级的颜色
    const getDeviationColor = (level?: string) => {
        switch (level) {
            case 'low': return 'text-green-600 bg-green-50'
            case 'medium': return 'text-yellow-600 bg-yellow-50'
            case 'high': return 'text-red-600 bg-red-50'
            default: return 'text-gray-600 bg-gray-50'
        }
    }

    return (
        <>
            {/* 资产概览卡片 */}
            <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-5 gap-3">
                {summaryCards.map((item) => (
                    <div key={item.label} className={`text-center p-4 rounded-lg ${item.bg}`}>
                        <div className={`text-xl font-bold ${item.color}`}>{item.value}</div>
                        <div className="text-sm text-gray-500">{item.label}</div>
                    </div>
                ))}
            </div>

            {/* 收益曲线图 */}
            {navChartOption && (
                <div className="card">
                    <h3 className="font-semibold mb-3">📈 收益曲线</h3>
                    <ReactECharts option={navChartOption} style={{ height: 280 }} />
                    <p className="text-xs text-gray-400 mt-2 text-center">
                        初始资金 ¥100,000 为基准（100），每次交易后更新净值
                    </p>
                </div>
            )}

            {/* 用户干预提示 */}
            {advice && advice.user_intervention_detected && advice.suggestion_mode !== 'auto' && (
                <div className={`card border-l-4 ${advice.deviation_level === 'low' ? 'border-green-500 bg-green-50' :
                    advice.deviation_level === 'medium' ? 'border-yellow-500 bg-yellow-50' :
                        'border-red-500 bg-red-50'
                    }`}>
                    <div className="flex items-start justify-between gap-4">
                        <div className="flex-1">
                            <div className="flex items-center gap-2 mb-2">
                                <span className="text-lg">⚠️</span>
                                <span className="font-semibold">检测到手动交易</span>
                                <span className={`px-2 py-0.5 rounded text-xs ${getDeviationColor(advice.deviation_level)}`}>
                                    偏离度 {advice.deviation_pct}%
                                </span>
                            </div>
                            <p className="text-sm text-gray-600">{advice.suggestion_message}</p>
                            {advice.last_trade_time && (
                                <p className="text-xs text-gray-400 mt-1">
                                    最近交易时间: {new Date(advice.last_trade_time).toLocaleString('zh-CN')}
                                </p>
                            )}
                        </div>
                        {onRefreshAdvice && (
                            <button
                                onClick={onRefreshAdvice}
                                disabled={isRefreshingAdvice}
                                className="btn btn-sm btn-primary whitespace-nowrap"
                            >
                                {isRefreshingAdvice ? '刷新中...' : '🔄 刷新建议'}
                            </button>
                        )}
                    </div>
                </div>
            )}

            {/* 操作建议 */}
            {advice && !advice.error && (
                <div className="card">
                    <div className="flex justify-between items-center mb-3">
                        <div className="flex items-center gap-3">
                            <h3 className="font-semibold">🎯 本月操作建议</h3>
                            {advice.suggestion_mode === 'auto' && onRefreshAdvice && (
                                <button
                                    onClick={onRefreshAdvice}
                                    disabled={isRefreshingAdvice}
                                    className="text-sm text-gray-400 hover:text-blue-600 transition-colors"
                                    title="重新计算建议"
                                >
                                    🔄
                                </button>
                            )}
                        </div>
                        <button
                            className="btn btn-sm btn-primary bg-gradient-to-r from-blue-600 to-indigo-600 border-none shadow-md hover:shadow-lg transition-all"
                            onClick={onOpenRebalance}
                        >
                            ⚡ 一键调仓
                        </button>
                    </div>
                    <p className="text-sm text-gray-500 mb-3">根据策略信号和您的持仓，系统建议：</p>
                    <div className="overflow-x-auto">
                        <table className="table">
                            <thead>
                                <tr>
                                    <th>操作</th>
                                    <th>代码</th>
                                    <th>名称</th>
                                    <th>数量/金额</th>
                                    <th>原因</th>
                                    <th></th>
                                </tr>
                            </thead>
                            <tbody>
                                {advice.actions?.map((action, i) => (
                                    <tr key={i} className={action.action === 'hold' ? 'bg-gray-50' : ''}>
                                        <td>
                                            <span className={`badge ${action.action === 'buy' ? 'badge-green' : action.action === 'sell' ? 'badge-red' : 'badge-blue'}`}>
                                                {action.action_text}
                                            </span>
                                        </td>
                                        <td className="font-mono">{action.code}</td>
                                        <td>{action.name}</td>
                                        <td className="font-medium">
                                            {action.action === 'buy'
                                                ? `¥${action.amount?.toLocaleString()} (${action.shares}股)`
                                                : action.action === 'sell'
                                                    ? `${action.shares}股`
                                                    : '-'}
                                        </td>
                                        <td className="text-gray-500 text-sm">{action.reason}</td>
                                        <td>
                                            {action.action !== 'hold' && (
                                                <button
                                                    className={`btn btn-sm ${action.action === 'buy' ? 'btn-primary' : 'btn-destructive'}`}
                                                    onClick={() => onOpenTrade(
                                                        action.action as 'buy' | 'sell',
                                                        action.code,
                                                        action.action === 'buy' ? String(action.amount) : String(action.shares)
                                                    )}
                                                >
                                                    执行
                                                </button>
                                            )}
                                        </td>
                                    </tr>
                                ))}
                            </tbody>
                        </table>
                    </div>
                </div>
            )}

            {/* 当前持仓 */}
            <div className="card">
                <div className="flex justify-between items-center mb-3">
                    <h3 className="font-semibold">📋 当前持仓</h3>
                    <button
                        className="btn btn-sm btn-primary"
                        onClick={() => onOpenTrade('buy')}
                    >
                        + 手动交易
                    </button>
                </div>
                {account.positions?.length > 0 ? (
                    <div className="overflow-x-auto">
                        <table className="table">
                            <thead>
                                <tr>
                                    <th>代码</th>
                                    <th>名称</th>
                                    <th>持仓</th>
                                    <th>成本</th>
                                    <th>现价</th>
                                    <th>市值</th>
                                    <th>盈亏</th>
                                    <th></th>
                                </tr>
                            </thead>
                            <tbody>
                                {account.positions.map((pos) => (
                                    <tr key={pos.symbol}>
                                        <td className="font-mono">{pos.symbol}</td>
                                        <td>{pos.name}</td>
                                        <td>{pos.shares}股</td>
                                        <td>¥{pos.avg_cost}</td>
                                        <td>¥{pos.current_price}</td>
                                        <td>¥{pos.value?.toLocaleString()}</td>
                                        <td className={pos.pnl >= 0 ? 'text-red-600' : 'text-green-600'}>
                                            {pos.pnl >= 0 ? '+' : ''}¥{pos.pnl} ({pos.pnl_pct}%)
                                        </td>
                                        <td>
                                            <button
                                                className="btn btn-sm btn-destructive"
                                                onClick={() => onOpenTrade('sell', pos.symbol, String(pos.shares))}
                                            >
                                                卖出
                                            </button>
                                        </td>
                                    </tr>
                                ))}
                            </tbody>
                        </table>
                    </div>
                ) : (
                    <div className="text-center py-6 text-gray-500">暂无持仓</div>
                )}
            </div>
        </>
    )
}

