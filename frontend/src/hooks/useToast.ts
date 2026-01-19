/**
 * Toast 状态管理 Hook
 */
import { useState, useCallback, useEffect } from 'react'

export type ToastType = 'success' | 'error'

export interface ToastState {
    type: ToastType
    text: string
}

export function useToast() {
    const [toast, setToast] = useState<ToastState | null>(null)

    const showToast = useCallback((type: ToastType, text: string) => {
        setToast({ type, text })
    }, [])

    const hideToast = useCallback(() => {
        setToast(null)
    }, [])

    // 自动隐藏
    useEffect(() => {
        if (toast) {
            const timer = setTimeout(() => setToast(null), 3000)
            return () => clearTimeout(timer)
        }
    }, [toast])

    return { toast, showToast, hideToast }
}
