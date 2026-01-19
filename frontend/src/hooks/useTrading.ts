/**
 * 交易相关 Hooks
 */
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { api, useAuthStore } from '@/lib/store'

// ==================== 类型定义 ====================

export interface Position {
    symbol: string
    name: string
    shares: number
    avg_cost: number
    current_price: number
    value: number
    pnl: number
    pnl_pct: number
}

export interface AccountData {
    total_value: number
    cash: number
    positions_value: number
    total_pnl: number
    total_pnl_pct: number
    positions: Position[]
}

export interface TradeAction {
    action: 'buy' | 'sell' | 'hold'
    action_text: string
    code: string
    name: string
    shares: number
    amount?: number
    estimated_value?: number
    reason: string
}

export interface AdviceData {
    date: string
    risk_on: boolean
    total_value: number
    cash: number
    actions: TradeAction[]
    target_positions: any[]
    error?: string
    // 新增字段：用户干预检测
    user_intervention_detected?: boolean
    last_trade_time?: string | null
    deviation_pct?: number
    deviation_level?: 'low' | 'medium' | 'high'
    suggestion_mode?: 'auto' | 'manual_detected_ok' | 'manual_detected_wait' | 'manual_detected_review'
    suggestion_message?: string | null
}

// ==================== Hooks ====================

export function useAccount(enabled: boolean = true) {
    const { isLoggedIn } = useAuthStore()

    return useQuery<AccountData>({
        queryKey: ['account'],
        queryFn: () => api.get('/trading/account'),
        enabled: enabled && isLoggedIn(),
    })
}

export function useAdvice(enabled: boolean = true) {
    const { isLoggedIn } = useAuthStore()

    return useQuery<AdviceData>({
        queryKey: ['advice'],
        queryFn: () => api.get('/trading/advice'),
        enabled: enabled && isLoggedIn(),
    })
}

export function useRefreshAdvice() {
    const queryClient = useQueryClient()

    return useMutation({
        mutationFn: () => api.get('/trading/advice?force_refresh=true'),
        onSuccess: (data) => {
            queryClient.setQueryData(['advice'], data)
        },
    })
}

export function useTrade(options?: {
    onSuccess?: () => void
    onError?: (err: Error) => void
}) {
    const queryClient = useQueryClient()

    return useMutation({
        mutationFn: async ({ type, symbol, amount, shares }: {
            type: 'buy' | 'sell'
            symbol: string
            amount?: number
            shares?: number
        }) => {
            if (type === 'buy') {
                return api.post('/trading/buy', { symbol, amount })
            } else {
                return api.post('/trading/sell', { symbol, shares })
            }
        },
        onSuccess: () => {
            queryClient.invalidateQueries({ queryKey: ['account'] })
            queryClient.invalidateQueries({ queryKey: ['advice'] })
            options?.onSuccess?.()
        },
        onError: options?.onError,
    })
}

export function useBatchTrade(options?: {
    onSuccess?: (data: any) => void
    onError?: (err: Error) => void
}) {
    const queryClient = useQueryClient()

    return useMutation({
        mutationFn: (actions: TradeAction[]) =>
            api.post('/trading/batch', { actions }),
        onSuccess: (data) => {
            queryClient.invalidateQueries({ queryKey: ['account'] })
            queryClient.invalidateQueries({ queryKey: ['advice'] })
            options?.onSuccess?.(data)
        },
        onError: options?.onError,
    })
}

export function useUpdateData(options?: {
    onSuccess?: () => void
}) {
    const queryClient = useQueryClient()

    return useMutation({
        mutationFn: () => api.post('/data/update'),
        onSuccess: () => {
            options?.onSuccess?.()
            // 30秒后刷新所有数据
            setTimeout(() => queryClient.invalidateQueries(), 30000)
        },
    })
}

export interface NavHistoryItem {
    date: string
    value: number
}

export function useNavHistory(enabled: boolean = true) {
    const { isLoggedIn } = useAuthStore()

    return useQuery<NavHistoryItem[]>({
        queryKey: ['navHistory'],
        queryFn: () => api.get('/trading/history'),
        enabled: enabled && isLoggedIn(),
    })
}
