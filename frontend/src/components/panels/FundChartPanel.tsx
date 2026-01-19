'use client'

import { useState, useMemo } from 'react'
import { useQuery } from '@tanstack/react-query'
import dynamic from 'next/dynamic'
import { api } from '@/lib/store'

const ReactECharts = dynamic(() => import('echarts-for-react'), { ssr: false })

interface Fund {
    code: string
    name: string
    type: string
}

interface ChartData {
    code: string
    name: string
    period: string
    chart_type: string
    data_points: number
    dates?: string[]
    prices?: number[]
    data?: [string, number, number, number, number][]  // K线: [date, open, close, low, high]
}

const PERIODS = [
    { value: '1w', label: '1周' },
    { value: '1m', label: '1月' },
    { value: '1y', label: '1年' },
    { value: '3y', label: '3年' },
    { value: '5y', label: '5年' },
    { value: 'all', label: '全部' },
]

const CHART_TYPES = [
    { value: 'line', label: '📈 曲线图' },
    { value: 'kline', label: '📊 K线图' },
]

export function FundChartPanel() {
    const [selectedCode, setSelectedCode] = useState<string>('')
    const [period, setPeriod] = useState('1y')
    const [chartType, setChartType] = useState('line')

    // 获取基金列表
    const { data: fundsData } = useQuery<{ funds: Fund[] }>({
        queryKey: ['chart-funds'],
        queryFn: () => api.get('/chart'),
    })

    // 获取图表数据
    const { data: chartData, isLoading } = useQuery<ChartData>({
        queryKey: ['chart-data', selectedCode, period, chartType],
        queryFn: () => api.get(`/chart/${selectedCode}?period=${period}&chart_type=${chartType}`),
        enabled: !!selectedCode,
    })

    // 初始化默认选中第一个基金
    if (fundsData?.funds?.length && !selectedCode) {
        setSelectedCode(fundsData.funds[0].code)
    }

    // 生成 ECharts 配置
    const chartOption = useMemo(() => {
        if (!chartData) return null

        if (chartType === 'kline' && chartData.data) {
            // K线图配置
            const dates = chartData.data.map(d => d[0])
            const ohlc = chartData.data.map(d => [d[1], d[2], d[3], d[4]])  // [open, close, low, high]

            return {
                title: {
                    text: `${chartData.name} (${chartData.code})`,
                    left: 'center',
                    textStyle: { fontSize: 16, fontWeight: 'bold' }
                },
                tooltip: {
                    trigger: 'axis',
                    axisPointer: { type: 'cross' }
                },
                grid: { left: 60, right: 40, top: 60, bottom: 50 },
                xAxis: {
                    type: 'category',
                    data: dates,
                    axisLabel: { interval: Math.floor(dates.length / 8) }
                },
                yAxis: {
                    type: 'value',
                    scale: true,
                    splitLine: { lineStyle: { type: 'dashed' } }
                },
                series: [{
                    type: 'candlestick',
                    data: ohlc,
                    itemStyle: {
                        color: '#ef4444',      // 上涨红色
                        color0: '#22c55e',     // 下跌绿色
                        borderColor: '#ef4444',
                        borderColor0: '#22c55e'
                    }
                }]
            }
        } else if (chartData.dates && chartData.prices) {
            // 曲线图配置
            return {
                title: {
                    text: `${chartData.name} (${chartData.code})`,
                    left: 'center',
                    textStyle: { fontSize: 16, fontWeight: 'bold' }
                },
                tooltip: {
                    trigger: 'axis',
                    formatter: (params: any) => {
                        const data = params[0]
                        return `${data.axisValue}<br/>收盘价: ¥${data.value}`
                    }
                },
                grid: { left: 60, right: 40, top: 60, bottom: 50 },
                xAxis: {
                    type: 'category',
                    data: chartData.dates,
                    axisLabel: { interval: Math.floor(chartData.dates.length / 8) }
                },
                yAxis: {
                    type: 'value',
                    scale: true,
                    axisLabel: { formatter: (v: number) => `¥${v.toFixed(2)}` },
                    splitLine: { lineStyle: { type: 'dashed' } }
                },
                series: [{
                    type: 'line',
                    data: chartData.prices,
                    smooth: true,
                    lineStyle: { width: 2, color: '#3b82f6' },
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
                    itemStyle: { color: '#3b82f6' },
                    showSymbol: false
                }]
            }
        }
        return null
    }, [chartData, chartType])

    return (
        <div className="card">
            <div className="flex flex-wrap items-center justify-between gap-4 mb-4">
                <h2 className="text-lg font-bold">📊 基金行情</h2>

                <div className="flex flex-wrap items-center gap-3">
                    {/* 基金选择 */}
                    <select
                        value={selectedCode}
                        onChange={(e) => setSelectedCode(e.target.value)}
                        className="input w-48"
                    >
                        {fundsData?.funds?.map((fund) => (
                            <option key={fund.code} value={fund.code}>
                                {fund.name} ({fund.code})
                            </option>
                        ))}
                    </select>

                    {/* 图表类型 */}
                    <div className="flex gap-1 bg-gray-100 p-1 rounded-lg">
                        {CHART_TYPES.map((type) => (
                            <button
                                key={type.value}
                                onClick={() => setChartType(type.value)}
                                className={`px-3 py-1.5 text-sm rounded-md transition-colors ${chartType === type.value
                                        ? 'bg-white shadow text-blue-600 font-medium'
                                        : 'text-gray-600 hover:text-gray-900'
                                    }`}
                            >
                                {type.label}
                            </button>
                        ))}
                    </div>

                    {/* 时间周期 */}
                    <div className="flex gap-1 bg-gray-100 p-1 rounded-lg">
                        {PERIODS.map((p) => (
                            <button
                                key={p.value}
                                onClick={() => setPeriod(p.value)}
                                className={`px-3 py-1.5 text-sm rounded-md transition-colors ${period === p.value
                                        ? 'bg-white shadow text-blue-600 font-medium'
                                        : 'text-gray-600 hover:text-gray-900'
                                    }`}
                            >
                                {p.label}
                            </button>
                        ))}
                    </div>
                </div>
            </div>

            {/* 图表区域 */}
            <div className="min-h-[400px] flex items-center justify-center">
                {isLoading ? (
                    <div className="text-center text-gray-500">
                        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600 mx-auto mb-2"></div>
                        <p>加载中...</p>
                    </div>
                ) : chartOption ? (
                    <ReactECharts
                        option={chartOption}
                        style={{ height: 400, width: '100%' }}
                        notMerge={true}
                    />
                ) : (
                    <div className="text-center text-gray-400">
                        <p className="text-4xl mb-2">📊</p>
                        <p>请选择一个基金查看行情</p>
                    </div>
                )}
            </div>

            {chartData && (
                <p className="text-xs text-gray-400 text-center mt-2">
                    共 {chartData.data_points} 个数据点 | 数据来源: AKShare
                </p>
            )}
        </div>
    )
}
