'use client'

import { useState, useRef } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { api, useAuthStore } from '@/lib/store'

interface DefaultAvatar {
    id: string
    url: string
}

interface ProfileModalProps {
    isOpen: boolean
    onClose: () => void
    user: any
    onSuccess: (message: string) => void
    onError: (message: string) => void
}

export function ProfileModal({ isOpen, onClose, user, onSuccess, onError }: ProfileModalProps) {
    const queryClient = useQueryClient()
    const { setUser } = useAuthStore()
    const fileInputRef = useRef<HTMLInputElement>(null)

    const [activeTab, setActiveTab] = useState<'avatar' | 'password'>('avatar')
    const [oldPassword, setOldPassword] = useState('')
    const [newPassword, setNewPassword] = useState('')
    const [confirmPassword, setConfirmPassword] = useState('')

    // 获取默认头像列表
    const { data: avatarsData } = useQuery<{ avatars: DefaultAvatar[] }>({
        queryKey: ['defaultAvatars'],
        queryFn: () => api.get('/avatar/defaults'),
        enabled: isOpen,
    })

    // 选择默认头像
    const selectAvatarMutation = useMutation({
        mutationFn: (avatarId: string) => api.post('/avatar/select', { avatar_id: avatarId }),
        onSuccess: (data: any) => {
            setUser({ ...user, avatar: data.avatar })
            onSuccess('头像更新成功')
            queryClient.invalidateQueries({ queryKey: ['messages'] })
        },
        onError: (err: any) => onError(err.message || '头像更新失败'),
    })

    // 上传自定义头像
    const uploadAvatarMutation = useMutation({
        mutationFn: (avatarData: string) => api.post('/avatar/upload', { avatar_data: avatarData }),
        onSuccess: (data: any) => {
            setUser({ ...user, avatar: data.avatar })
            onSuccess('头像上传成功')
            queryClient.invalidateQueries({ queryKey: ['messages'] })
        },
        onError: (err: any) => onError(err.message || '头像上传失败'),
    })

    // 修改密码
    const changePasswordMutation = useMutation({
        mutationFn: (data: { old_password: string; new_password: string }) =>
            api.post('/auth/change-password', data),
        onSuccess: () => {
            onSuccess('密码修改成功')
            setOldPassword('')
            setNewPassword('')
            setConfirmPassword('')
        },
        onError: (err: any) => onError(err.message || '密码修改失败'),
    })

    const handleFileSelect = (e: React.ChangeEvent<HTMLInputElement>) => {
        const file = e.target.files?.[0]
        if (!file) return

        if (!file.type.startsWith('image/')) {
            onError('请选择图片文件')
            return
        }

        if (file.size > 500 * 1024) {
            onError('图片大小不能超过 500KB')
            return
        }

        const reader = new FileReader()
        reader.onload = (event) => {
            const base64 = event.target?.result as string
            uploadAvatarMutation.mutate(base64)
        }
        reader.readAsDataURL(file)
    }

    const handlePasswordSubmit = () => {
        if (!oldPassword || !newPassword || !confirmPassword) {
            onError('请填写所有密码字段')
            return
        }
        if (newPassword !== confirmPassword) {
            onError('新密码与确认密码不一致')
            return
        }
        if (newPassword.length < 6) {
            onError('新密码至少6个字符')
            return
        }
        changePasswordMutation.mutate({ old_password: oldPassword, new_password: newPassword })
    }

    const getDefaultAvatar = (username: string) => {
        return `https://api.dicebear.com/7.x/avataaars/svg?seed=${username}`
    }

    if (!isOpen) return null

    return (
        <>
            <div className="dialog-overlay" onClick={onClose} />
            <div className="dialog-content max-w-xl">
                <div className="flex items-center justify-between mb-4">
                    <h2 className="text-lg font-semibold text-gray-900">账户设置</h2>
                    <button onClick={onClose} className="text-gray-400 hover:text-gray-600">
                        <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                        </svg>
                    </button>
                </div>

                {/* Tab 切换 */}
                <div className="flex gap-1 bg-gray-100 p-1 rounded-lg mb-4">
                    <button
                        onClick={() => setActiveTab('avatar')}
                        className={`flex-1 py-2 px-4 rounded-md text-sm font-medium transition-colors ${activeTab === 'avatar' ? 'bg-white shadow text-blue-600' : 'text-gray-600'
                            }`}
                    >
                        🖼️ 修改头像
                    </button>
                    <button
                        onClick={() => setActiveTab('password')}
                        className={`flex-1 py-2 px-4 rounded-md text-sm font-medium transition-colors ${activeTab === 'password' ? 'bg-white shadow text-blue-600' : 'text-gray-600'
                            }`}
                    >
                        🔒 修改密码
                    </button>
                </div>

                {/* 头像设置 */}
                {activeTab === 'avatar' && (
                    <div>
                        {/* 当前头像 */}
                        <div className="text-center mb-6">
                            <img
                                src={user?.avatar || getDefaultAvatar(user?.username || '')}
                                alt={user?.username}
                                className="w-20 h-20 rounded-full mx-auto border-4 border-white shadow-lg"
                            />
                            <p className="text-sm text-gray-500 mt-2">当前头像</p>
                        </div>

                        {/* 上传自定义头像 */}
                        <div className="mb-6">
                            <input
                                ref={fileInputRef}
                                type="file"
                                accept="image/*"
                                onChange={handleFileSelect}
                                className="hidden"
                            />
                            <button
                                onClick={() => fileInputRef.current?.click()}
                                disabled={uploadAvatarMutation.isPending}
                                className="btn btn-primary w-full"
                            >
                                {uploadAvatarMutation.isPending ? '上传中...' : '📤 上传自定义头像'}
                            </button>
                            <p className="text-xs text-gray-400 mt-1 text-center">支持 JPG、PNG 格式，最大 500KB</p>
                        </div>

                        {/* 默认头像选择 */}
                        <div>
                            <p className="text-sm font-medium text-gray-700 mb-3">或选择默认头像</p>
                            <div className="grid grid-cols-5 gap-3 max-h-60 overflow-y-auto">
                                {avatarsData?.avatars.map((avatar) => (
                                    <button
                                        key={avatar.id}
                                        onClick={() => selectAvatarMutation.mutate(avatar.id)}
                                        disabled={selectAvatarMutation.isPending}
                                        className="w-12 h-12 rounded-full overflow-hidden border-2 border-transparent hover:border-blue-500 transition-colors focus:outline-none focus:ring-2 focus:ring-blue-500"
                                    >
                                        <img src={avatar.url} alt={avatar.id} className="w-full h-full" />
                                    </button>
                                ))}
                            </div>
                        </div>
                    </div>
                )}

                {/* 密码设置 */}
                {activeTab === 'password' && (
                    <div className="space-y-4">
                        <div>
                            <label className="label">当前密码</label>
                            <input
                                type="password"
                                value={oldPassword}
                                onChange={(e) => setOldPassword(e.target.value)}
                                className="input mt-1"
                                placeholder="请输入当前密码"
                            />
                        </div>
                        <div>
                            <label className="label">新密码</label>
                            <input
                                type="password"
                                value={newPassword}
                                onChange={(e) => setNewPassword(e.target.value)}
                                className="input mt-1"
                                placeholder="请输入新密码（至少6位）"
                            />
                        </div>
                        <div>
                            <label className="label">确认新密码</label>
                            <input
                                type="password"
                                value={confirmPassword}
                                onChange={(e) => setConfirmPassword(e.target.value)}
                                className="input mt-1"
                                placeholder="请再次输入新密码"
                            />
                        </div>
                        <button
                            onClick={handlePasswordSubmit}
                            disabled={changePasswordMutation.isPending}
                            className="btn btn-primary w-full mt-4"
                        >
                            {changePasswordMutation.isPending ? '提交中...' : '确认修改'}
                        </button>
                    </div>
                )}
            </div>
        </>
    )
}
