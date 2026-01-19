'use client'

import { useMemo } from 'react'
import dynamic from 'next/dynamic'
import { SignalData } from '@/hooks/useStrategy'

const ReactECharts = dynamic(() => import('echarts-for-react'), { ssr: false })

interface StrategyPanelProps {
    signal: SignalData
}

export function StrategyPanel({ signal }: StrategyPanelProps) {
    // 饼图配置
    const pieChartOption = useMemo(() => {
        if (!signal?.recommendation) return null
        const colors = ['#3b82f6', '#10b981', '#f59e0b', '#ef4444', '#8b5cf6', '#06b6d4']
        return {
            tooltip: { trigger: 'item', formatter: '{b}: {c}%' },
            series: [{
                type: 'pie',
                radius: ['35%', '60%'],
                center: ['50%', '50%'],
                data: signal.recommendation.map((r, i) => ({
                    name: `${r.name.slice(0, 4)}`,
                    value: r.weight,
                    itemStyle: { color: colors[i % colors.length] }
                })),
                label: { show: true, position: 'outside', formatter: '{b}\n{c}%', fontSize: 10 },
                labelLine: { length: 10, length2: 5 },
                emphasis: { label: { show: true, fontSize: 12, fontWeight: 'bold' } }
            }],
        }
    }, [signal])

    return (
        <>
            <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
                {/* 1. 核心状态卡片 */}
                <div className="card md:col-span-2 bg-gradient-to-br from-white to-gray-50 border-blue-100">
                    <div className="flex flex-col h-full">
                        <h2 className="text-lg font-bold text-gray-800 mb-4 flex items-center gap-2">
                            🌡️ 市场温度与策略状态
                        </h2>
                        <div className="flex-1 flex flex-col md:flex-row items-center justify-between px-4 gap-4">
                            {/* 仪表盘 */}
                            <div className="w-full md:w-2/5 flex-shrink-0" style={{ height: '180px' }}>
                                <ReactECharts
                                    option={{
                                        series: [{
                                            type: 'gauge',
                                            startAngle: 180, endAngle: 0,
                                            min: 0, max: 2,
                                            splitNumber: 2,
                                            radius: '100%',
                                            center: ['50%', '70%'],
                                            itemStyle: { color: signal.risk_on ? '#10b981' : '#ef4444' },
                                            progress: { show: true, width: 12 },
                                            pointer: { length: '55%', width: 4, offsetCenter: [0, '-5%'] },
                                            axisLine: { lineStyle: { width: 12 } },
                                            axisTick: { show: false },
                                            splitLine: { show: false },
                                            axisLabel: { show: false },
                                            anchor: { show: false },
                                            title: { show: false },
                                            detail: {
                                                valueAnimation: true, fontSize: 18, offsetCenter: [0, '25%'],
                                                formatter: () => signal.risk_on ? '🟢 进攻' : '🛡️ 防御',
                                                color: signal.risk_on ? '#10b981' : '#ef4444'
                                            },
                                            data: [{ value: signal.benchmark.raw_ratio || 1.0 }]
                                        }]
                                    }}
                                    style={{ height: '100%', width: '100%' }}
                                />
                            </div>

                            {/* 状态解读 */}
                            <div className="flex-1 md:pl-6 space-y-3">
                                <div>
                                    <div className="text-sm text-gray-500 mb-1">当前市场环境</div>
                                    <div className="text-xl font-bold text-gray-800">
                                        {signal.risk_on ? '🔥 趋势向好' : '🧊 趋势转冷'}
                                    </div>
                                    <div className="text-sm text-gray-600 mt-2 leading-relaxed">
                                        {signal.risk_on
                                            ? `温度计资产 (${signal.benchmark.name}) 位于 10 月均线上方，市场动能充足。策略建议：`
                                            : `温度计资产 (${signal.benchmark.name}) 跌破 10 月均线，市场风险较高。策略建议：`}
                                        <span className={`font-bold ml-1 ${signal.risk_on ? 'text-green-600' : 'text-red-600'}`}>
                                            {signal.risk_on ? '积极持有权益类资产' : '全仓转入债券避险'}
                                        </span>
                                    </div>
                                </div>
                                <div className="bg-white/80 p-3 rounded-lg border border-gray-100 text-xs text-gray-500">
                                    当前价格: <span className="font-mono text-gray-900">{signal.benchmark.current?.toFixed(3)}</span>
                                    <span className="mx-2">|</span>
                                    10月均线: <span className="font-mono text-gray-900">{signal.benchmark.ma?.toFixed(3)}</span>
                                </div>
                            </div>
                        </div>
                    </div>
                </div>

                {/* 2. 目标配置饼图 */}
                <div className="card flex flex-col">
                    <h3 className="text-sm font-semibold mb-2">🎯 本月目标配置</h3>
                    <div className="flex-1 flex items-center justify-center">
                        {pieChartOption && <ReactECharts option={pieChartOption} style={{ height: 220, width: '100%' }} />}
                    </div>
                </div>
            </div>

            {/* 3. 动量排名卡片 */}
            <div className="card mt-6">
                <h3 className="font-semibold mb-4 flex items-center gap-2">
                    🚀 权益资产动量榜 (6个月涨幅)
                    <span className="text-xs font-normal text-gray-400 bg-gray-100 px-2 py-0.5 rounded">数值越高，趋势越强</span>
                </h3>
                <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-4 gap-4">
                    {signal.risk_assets?.map((row, i) => (
                        <div key={row.code} className={`relative p-4 rounded-xl border transition-all hover:shadow-md ${i === 0 ? 'border-blue-300 bg-gradient-to-br from-blue-50 to-white ring-1 ring-blue-100' : 'border-gray-100 bg-white'}`}>
                            <div className="flex justify-between items-start mb-2">
                                <div>
                                    <div className="font-medium text-gray-900">{row.name}</div>
                                    <div className="font-mono text-xs text-gray-400 mt-0.5">{row.code}</div>
                                </div>
                                {i === 0 && <span className="text-xl">👑</span>}
                            </div>
                            <div className="flex items-end justify-between">
                                <div className={`text-2xl font-bold tracking-tight ${row.momentum >= 0 ? 'text-red-500' : 'text-green-500'}`}>
                                    {row.momentum > 0 ? '+' : ''}{row.momentum}%
                                </div>
                            </div>
                            <div className="w-full bg-gray-100 h-1.5 rounded-full mt-3 overflow-hidden">
                                <div
                                    className={`h-full rounded-full ${i === 0 ? 'bg-blue-500' : 'bg-gray-300'}`}
                                    style={{ width: `${Math.max(0, Math.min(100, (row.momentum + 20) * 2))}%` }}
                                />
                            </div>
                        </div>
                    ))}
                </div>
            </div>
        </>
    )
}
