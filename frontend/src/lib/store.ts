/**
 * 认证状态管理 - Zustand
 */
import { create } from 'zustand'
import { persist } from 'zustand/middleware'

interface User {
    id: number
    username: string
    is_admin: boolean
    avatar?: string
}

interface AuthState {
    token: string | null
    user: User | null
    setAuth: (token: string, user: User) => void
    setUser: (user: User) => void
    logout: () => void
    isLoggedIn: () => boolean
    isAdmin: () => boolean
}

export const useAuthStore = create<AuthState>()(
    persist(
        (set, get) => ({
            token: null,
            user: null,
            setAuth: (token, user) => set({ token, user }),
            setUser: (user) => set({ user }),
            logout: () => set({ token: null, user: null }),
            isLoggedIn: () => !!get().token,
            isAdmin: () => get().user?.is_admin ?? false,
        }),
        {
            name: 'auth-storage',
        }
    )
)

// API 封装
export const api = {
    baseUrl: '/api',

    async request(path: string, options: RequestInit = {}) {
        const { token } = useAuthStore.getState()
        const headers: Record<string, string> = {
            'Content-Type': 'application/json',
        }
        if (token) {
            headers['Authorization'] = `Bearer ${token}`
        }

        const res = await fetch(`${this.baseUrl}${path}`, {
            ...options,
            headers: { ...headers, ...(options.headers as Record<string, string>) },
        })

        if (res.status === 401) {
            useAuthStore.getState().logout()
            throw new Error('请先登录')
        }

        const data = await res.json().catch(() => ({}))

        if (!res.ok) {
            throw new Error(data.detail || '请求失败')
        }

        return data
    },

    get: (path: string) => api.request(path),

    post: (path: string, body?: any) =>
        api.request(path, { method: 'POST', body: body ? JSON.stringify(body) : undefined }),

    delete: (path: string) =>
        api.request(path, { method: 'DELETE' }),
}
