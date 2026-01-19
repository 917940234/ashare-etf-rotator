'use client'

import { ToastState } from '@/hooks/useToast'

interface ToastProps {
    toast: ToastState | null
}

export function Toast({ toast }: ToastProps) {
    if (!toast) return null

    return (
        <div className="fixed top-20 left-1/2 -translate-x-1/2 z-50 animate-fade-in">
            <div className={`px-6 py-3 rounded-lg shadow-lg ${toast.type === 'success' ? 'bg-green-500 text-white' : 'bg-red-500 text-white'}`}>
                {toast.text}
            </div>
        </div>
    )
}
