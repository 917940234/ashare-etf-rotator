'use client'

import { useMemo } from 'react'
import dynamic from 'next/dynamic'
import { BacktestResult } from '@/hooks/useBacktest'

const ReactECharts = dynamic(() => import('echarts-for-react'), { ssr: false })

const METRIC_TIPS: Record<string, string> = {
    '累计收益': '从回测开始到结束的总收益率。正值表示盈利，负值表示亏损。',
    '年化收益': '将累计收益换算为每年平均收益。便于不同时间跨度的策略对比。',
    '最大回撤': '从最高点到最低点的最大跌幅。越小越好，代表风险控制能力。',
    '夏普比率': '风险调整后收益。大于1表示较好，大于2表示优秀。',
}

interface BacktestPanelProps {
    backtest: BacktestResult | undefined
    isLoading: boolean
    onRunBacktest: () => void
}

export function BacktestPanel({ backtest, isLoading, onRunBacktest }: BacktestPanelProps) {
    // 多曲线对比图表
    const multiLineChartOption = useMemo(() => {
        if (!backtest?.nav) return null
        const dates = Object.keys(backtest.nav).map(d => d.slice(0, 10))
        const strategyNav = Object.values(backtest.nav) as number[]
        const strategyNormed = strategyNav.map(v => (v / strategyNav[0] * 100))

        const series: any[] = [{
            name: '📈 策略',
            type: 'line',
            data: strategyNormed,
            smooth: true,
            lineStyle: { width: 3, color: '#3b82f6' },
            itemStyle: { color: '#3b82f6' }
        }]
        const legendData = ['📈 策略']

        const colors = ['#ef4444', '#10b981', '#f59e0b', '#8b5cf6']
        let colorIdx = 0

        if (backtest.benchmarks) {
            for (const [key, bench] of Object.entries(backtest.benchmarks)) {
                const benchNav = bench.nav
                if (benchNav) {
                    const vals = dates.map(d => benchNav[d] || null)
                    series.push({
                        name: bench.name,
                        type: 'line',
                        data: vals,
                        smooth: true,
                        lineStyle: { width: 2, color: colors[colorIdx % colors.length] },
                        itemStyle: { color: colors[colorIdx % colors.length] }
                    })
                    legendData.push(bench.name)
                    colorIdx++
                }
            }
        }

        return {
            tooltip: { trigger: 'axis' },
            legend: { data: legendData, top: 10 },
            grid: { left: 50, right: 30, top: 60, bottom: 30 },
            xAxis: { type: 'category', data: dates, axisLabel: { interval: Math.floor(dates.length / 8) } },
            yAxis: { type: 'value', scale: true, name: '归一化净值', axisLabel: { formatter: (v: number) => v.toFixed(0) } },
            series,
        }
    }, [backtest])

    if (!backtest) {
        return (
            <div className="card text-center py-16 text-gray-500 min-h-[400px] flex flex-col items-center justify-center">
                <div className="text-5xl mb-6">📊</div>
                <p className="text-lg mb-4">点击下方按钮开始回测分析</p>
                <p className="text-sm text-gray-400 mb-6">将自动从 2015 年起进行策略回测，并与大盘对比</p>
                <button
                    className="btn btn-primary px-6 py-2.5"
                    onClick={onRunBacktest}
                    disabled={isLoading}
                >
                    {isLoading ? (
                        <span className="flex items-center gap-2">
                            <svg className="animate-spin h-4 w-4" viewBox="0 0 24 24">
                                <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" fill="none" />
                                <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
                            </svg>
                            计算中...
                        </span>
                    ) : '📊 运行回测'}
                </button>
            </div>
        )
    }

    const metrics = [
        { label: '累计收益', value: `${backtest.total_return > 0 ? '+' : ''}${backtest.total_return}%`, color: backtest.total_return >= 0 ? 'text-green-600' : 'text-red-600' },
        { label: '年化收益', value: `${backtest.annual_return}%`, color: '' },
        { label: '最大回撤', value: `-${backtest.max_drawdown}%`, color: 'text-red-600' },
        { label: '夏普比率', value: String(backtest.sharpe), color: backtest.sharpe >= 1 ? 'text-green-600' : '' }
    ]

    return (
        <div className="card">
            <h2 className="text-lg font-semibold mb-4">📈 策略 vs 大盘对比（2015年至今）</h2>
            <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mb-4">
                {metrics.map((item) => (
                    <div key={item.label} className="text-center p-4 bg-gray-50 rounded-lg group relative cursor-help">
                        <div className={`text-2xl font-bold ${item.color}`}>{item.value}</div>
                        <div className="text-sm text-gray-500">{item.label}</div>
                        <div className="absolute bottom-full left-1/2 -translate-x-1/2 mb-2 px-3 py-2 bg-gray-800 text-white text-xs rounded-lg opacity-0 group-hover:opacity-100 transition-opacity whitespace-nowrap z-10">
                            {METRIC_TIPS[item.label]}
                        </div>
                    </div>
                ))}
            </div>
            {multiLineChartOption && <ReactECharts option={multiLineChartOption} style={{ height: 400 }} />}
            <p className="text-xs text-gray-400 mt-2 text-center">图表展示策略净值与主要 ETF 的归一化对比（初始值=100）</p>
        </div>
    )
}
