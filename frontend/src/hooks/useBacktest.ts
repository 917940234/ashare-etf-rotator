/**
 * 回测相关 Hooks
 */
import { useMutation } from '@tanstack/react-query'
import { api } from '@/lib/store'

export interface BacktestParams {
    start_date?: string
    end_date?: string
    risk_weight?: number
    ma_period?: number
    momentum_months?: number
}

export interface BacktestResult {
    total_return: number
    annual_return: number
    max_drawdown: number
    sharpe: number
    nav: Record<string, number>
    benchmarks?: Record<string, {
        name: string
        nav: Record<string, number>
    }>
}

export function useBacktest(options?: {
    onSuccess?: () => void
    onError?: (err: Error) => void
}) {
    return useMutation<BacktestResult, Error, BacktestParams | void>({
        mutationFn: (params) =>
            api.post('/backtest', params ?? { start_date: '2015-01-01' }),
        onSuccess: options?.onSuccess,
        onError: options?.onError,
    })
}
