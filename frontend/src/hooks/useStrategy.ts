/**
 * 策略信号相关 Hooks
 */
import { useQuery } from '@tanstack/react-query'
import { api, useAuthStore } from '@/lib/store'

export interface BenchmarkInfo {
    name: string
    current: number
    ma: number
    raw_ratio: number
}

export interface RiskAsset {
    code: string
    name: string
    momentum: number
}

export interface Recommendation {
    code: string
    name: string
    weight: number
    type: 'risk' | 'defensive'
}

export interface SignalData {
    date: string
    risk_on: boolean
    benchmark: BenchmarkInfo
    risk_assets: RiskAsset[]
    recommendation: Recommendation[]
    strategy_text: string
    error?: string
}

export function useSignal(enabled: boolean = true) {
    const { isLoggedIn } = useAuthStore()

    return useQuery<SignalData>({
        queryKey: ['signal'],
        queryFn: () => api.get('/signal'),
        enabled: enabled && isLoggedIn(),
    })
}

export function usePrices(enabled: boolean = true) {
    const { isLoggedIn } = useAuthStore()

    return useQuery<Record<string, { name: string; price: number }>>({
        queryKey: ['prices'],
        queryFn: () => api.get('/trading/prices'),
        enabled: enabled && isLoggedIn(),
    })
}
