'use client'

import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { api } from '@/lib/store'
import { useAuthStore } from '@/lib/store'

interface Message {
    id: number
    user_id: number
    username: string
    avatar: string | null
    content: string
    likes: number
    dislikes: number
    user_reaction: 'like' | 'dislike' | null
    created_at: string
    replies: Message[]
}

interface MessagesResponse {
    messages: Message[]
    page: number
    page_size: number
    total: number
    total_pages: number
}

export function MessagePanel() {
    const { user } = useAuthStore()
    const queryClient = useQueryClient()
    const [content, setContent] = useState('')
    const [replyTo, setReplyTo] = useState<{ id: number; username: string } | null>(null)
    const [page, setPage] = useState(1)

    // 获取留言列表
    const { data, isLoading } = useQuery<MessagesResponse>({
        queryKey: ['messages', page],
        queryFn: () => api.get(`/messages?page=${page}`),
    })

    // 发布留言
    const postMutation = useMutation({
        mutationFn: (payload: { content: string; parent_id?: number }) =>
            api.post('/messages', payload),
        onMutate: async (newMessage) => {
            // 乐观更新：立即在本地添加新消息
            await queryClient.cancelQueries({ queryKey: ['messages', page] })
            const previousData = queryClient.getQueryData<MessagesResponse>(['messages', page])

            if (previousData && user && !newMessage.parent_id) {
                const optimisticMessage: Message = {
                    id: Date.now(), // 临时ID
                    user_id: user.id,
                    username: user.username,
                    avatar: user.avatar || null,
                    content: newMessage.content,
                    likes: 0,
                    dislikes: 0,
                    user_reaction: null,
                    created_at: new Date().toISOString(),
                    replies: []
                }
                queryClient.setQueryData<MessagesResponse>(['messages', page], {
                    ...previousData,
                    messages: [optimisticMessage, ...previousData.messages],
                    total: previousData.total + 1
                })
            }
            return { previousData }
        },
        onError: (_err, _newMessage, context) => {
            // 回滚
            if (context?.previousData) {
                queryClient.setQueryData(['messages', page], context.previousData)
            }
        },
        onSuccess: () => {
            setContent('')
            setReplyTo(null)
            // 重新获取以确保数据一致性
            queryClient.invalidateQueries({ queryKey: ['messages'] })
        },
    })

    // 点赞/踩
    const reactMutation = useMutation({
        mutationFn: ({ messageId, type }: { messageId: number; type: 'like' | 'dislike' }) =>
            api.post(`/messages/${messageId}/react`, { reaction_type: type }),
        onSuccess: () => {
            queryClient.invalidateQueries({ queryKey: ['messages'] })
        },
    })

    // 删除留言
    const deleteMutation = useMutation({
        mutationFn: (messageId: number) => api.delete(`/messages/${messageId}`),
        onSuccess: () => {
            queryClient.invalidateQueries({ queryKey: ['messages'] })
        },
    })

    const handleSubmit = () => {
        if (!content.trim()) return
        postMutation.mutate({
            content: content.trim(),
            parent_id: replyTo?.id,
        })
    }

    const formatTime = (isoString: string) => {
        const date = new Date(isoString)
        const now = new Date()
        const diff = now.getTime() - date.getTime()

        if (diff < 60000) return '刚刚'
        if (diff < 3600000) return `${Math.floor(diff / 60000)} 分钟前`
        if (diff < 86400000) return `${Math.floor(diff / 3600000)} 小时前`
        if (diff < 604800000) return `${Math.floor(diff / 86400000)} 天前`
        return date.toLocaleDateString('zh-CN')
    }

    const getDefaultAvatar = (username: string) => {
        return `https://api.dicebear.com/7.x/avataaars/svg?seed=${username}`
    }

    const MessageItem = ({ msg, isReply = false }: { msg: Message; isReply?: boolean }) => (
        <div className={`${isReply ? 'ml-12 mt-3' : ''}`}>
            <div className="flex gap-3">
                <img
                    src={msg.avatar || getDefaultAvatar(msg.username)}
                    alt={msg.username}
                    className={`rounded-full ${isReply ? 'w-8 h-8' : 'w-10 h-10'}`}
                />
                <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2 flex-wrap">
                        <span className="font-medium text-gray-900">{msg.username}</span>
                        <span className="text-xs text-gray-400">{formatTime(msg.created_at)}</span>
                    </div>
                    <p className="text-gray-700 mt-1 break-words">{msg.content}</p>

                    {/* 操作按钮 */}
                    <div className="flex items-center gap-4 mt-2">
                        <button
                            onClick={() => reactMutation.mutate({ messageId: msg.id, type: 'like' })}
                            className={`flex items-center gap-1 text-sm transition-colors ${msg.user_reaction === 'like'
                                ? 'text-blue-600'
                                : 'text-gray-400 hover:text-blue-600'
                                }`}
                        >
                            <svg className="w-4 h-4" fill={msg.user_reaction === 'like' ? 'currentColor' : 'none'} stroke="currentColor" viewBox="0 0 24 24">
                                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M14 10h4.764a2 2 0 011.789 2.894l-3.5 7A2 2 0 0115.263 21h-4.017c-.163 0-.326-.02-.485-.06L7 20m7-10V5a2 2 0 00-2-2h-.095c-.5 0-.905.405-.905.905 0 .714-.211 1.412-.608 2.006L7 11v9m7-10h-2M7 20H5a2 2 0 01-2-2v-6a2 2 0 012-2h2.5" />
                            </svg>
                            <span>{msg.likes || 0}</span>
                        </button>

                        <button
                            onClick={() => reactMutation.mutate({ messageId: msg.id, type: 'dislike' })}
                            className={`flex items-center gap-1 text-sm transition-colors ${msg.user_reaction === 'dislike'
                                ? 'text-red-600'
                                : 'text-gray-400 hover:text-red-600'
                                }`}
                        >
                            <svg className="w-4 h-4 rotate-180" fill={msg.user_reaction === 'dislike' ? 'currentColor' : 'none'} stroke="currentColor" viewBox="0 0 24 24">
                                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M14 10h4.764a2 2 0 011.789 2.894l-3.5 7A2 2 0 0115.263 21h-4.017c-.163 0-.326-.02-.485-.06L7 20m7-10V5a2 2 0 00-2-2h-.095c-.5 0-.905.405-.905.905 0 .714-.211 1.412-.608 2.006L7 11v9m7-10h-2M7 20H5a2 2 0 01-2-2v-6a2 2 0 012-2h2.5" />
                            </svg>
                            <span>{msg.dislikes || 0}</span>
                        </button>

                        {!isReply && (
                            <button
                                onClick={() => setReplyTo({ id: msg.id, username: msg.username })}
                                className="text-sm text-gray-400 hover:text-blue-600 transition-colors"
                            >
                                回复
                            </button>
                        )}

                        {(msg.user_id === user?.id || user?.is_admin) && (
                            <button
                                onClick={() => {
                                    if (confirm('确定要删除这条留言吗？')) {
                                        deleteMutation.mutate(msg.id)
                                    }
                                }}
                                className="text-sm text-gray-400 hover:text-red-600 transition-colors"
                            >
                                删除
                            </button>
                        )}
                    </div>
                </div>
            </div>

            {/* 回复列表 */}
            {msg.replies && msg.replies.length > 0 && (
                <div className="border-l-2 border-gray-100 pl-3 mt-3">
                    {msg.replies.map((reply) => (
                        <MessageItem key={reply.id} msg={reply} isReply />
                    ))}
                </div>
            )}
        </div>
    )

    return (
        <div className="space-y-4">
            {/* 发言框 */}
            <div className="card">
                <h3 className="text-lg font-semibold text-gray-900 mb-4">💬 留言墙</h3>

                {replyTo && (
                    <div className="flex items-center gap-2 mb-2 text-sm text-gray-500 bg-gray-50 px-3 py-2 rounded-lg">
                        <span>回复 @{replyTo.username}</span>
                        <button
                            onClick={() => setReplyTo(null)}
                            className="text-gray-400 hover:text-gray-600"
                        >
                            ✕
                        </button>
                    </div>
                )}

                <div className="flex gap-3">
                    <img
                        src={user?.avatar || getDefaultAvatar(user?.username || '')}
                        alt={user?.username}
                        className="w-10 h-10 rounded-full"
                    />
                    <div className="flex-1">
                        <textarea
                            value={content}
                            onChange={(e) => setContent(e.target.value)}
                            placeholder={replyTo ? `回复 @${replyTo.username}...` : '说点什么吧...'}
                            className="input resize-none h-20"
                            maxLength={500}
                        />
                        <div className="flex justify-between items-center mt-2">
                            <span className="text-xs text-gray-400">{content.length}/500</span>
                            <button
                                onClick={handleSubmit}
                                disabled={!content.trim() || postMutation.isPending}
                                className="btn btn-primary btn-sm"
                            >
                                {postMutation.isPending ? '发送中...' : replyTo ? '回复' : '发布'}
                            </button>
                        </div>
                    </div>
                </div>
            </div>

            {/* 留言列表 */}
            <div className="card">
                {isLoading ? (
                    <div className="text-center py-8 text-gray-400">加载中...</div>
                ) : data?.messages.length === 0 ? (
                    <div className="text-center py-8 text-gray-400">
                        还没有留言，来做第一个发言的人吧！
                    </div>
                ) : (
                    <div className="space-y-6">
                        {data?.messages.map((msg) => (
                            <MessageItem key={msg.id} msg={msg} />
                        ))}
                    </div>
                )}

                {/* 分页 */}
                {data && data.total_pages > 1 && (
                    <div className="flex justify-center gap-2 mt-6 pt-4 border-t">
                        <button
                            onClick={() => setPage(p => Math.max(1, p - 1))}
                            disabled={page === 1}
                            className="btn btn-secondary btn-sm"
                        >
                            上一页
                        </button>
                        <span className="text-sm text-gray-500 self-center">
                            {page} / {data.total_pages}
                        </span>
                        <button
                            onClick={() => setPage(p => Math.min(data.total_pages, p + 1))}
                            disabled={page === data.total_pages}
                            className="btn btn-secondary btn-sm"
                        >
                            下一页
                        </button>
                    </div>
                )}
            </div>
        </div>
    )
}
