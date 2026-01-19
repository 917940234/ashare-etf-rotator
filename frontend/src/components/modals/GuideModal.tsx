'use client'

interface GuideModalProps {
    isOpen: boolean
    onClose: () => void
}

export function GuideModal({ isOpen, onClose }: GuideModalProps) {
    if (!isOpen) return null

    const handleStart = () => {
        localStorage.setItem('v5_guide_done', 'true')
        onClose()
    }

    return (
        <div className="dialog-overlay z-50">
            <div className="dialog-content max-w-lg text-center" onClick={e => e.stopPropagation()}>
                <div className="text-4xl mb-4">👋</div>
                <h2 className="text-2xl font-bold mb-2">欢迎来到股债轮动 v5.0</h2>
                <p className="text-gray-500 mb-6">您的智能量化投资助手已上线</p>

                <div className="text-left space-y-4 mb-8 bg-gray-50 p-4 rounded-xl">
                    <div className="flex items-start gap-3">
                        <span className="bg-blue-100 text-blue-600 w-6 h-6 rounded-full flex items-center justify-center flex-shrink-0 text-sm font-bold">1</span>
                        <div>
                            <h4 className="font-bold">市场温度计 🌡️</h4>
                            <p className="text-sm text-gray-500">仪表盘实时显示市场冷热，告诉您何时进攻、何时防守。</p>
                        </div>
                    </div>
                    <div className="flex items-start gap-3">
                        <span className="bg-blue-100 text-blue-600 w-6 h-6 rounded-full flex items-center justify-center flex-shrink-0 text-sm font-bold">2</span>
                        <div>
                            <h4 className="font-bold">智能策略解读 🧠</h4>
                            <p className="text-sm text-gray-500">系统会自动分析市场并生成自然语言报告，让您知其然更知其所以然。</p>
                        </div>
                    </div>
                    <div className="flex items-start gap-3">
                        <span className="bg-blue-100 text-blue-600 w-6 h-6 rounded-full flex items-center justify-center flex-shrink-0 text-sm font-bold">3</span>
                        <div>
                            <h4 className="font-bold">一键调仓 ⚡</h4>
                            <p className="text-sm text-gray-500">不再需要繁琐的手动操作，系统自动计算并执行最优调仓计划。</p>
                        </div>
                    </div>
                </div>

                <button
                    className="btn btn-primary w-full py-3 text-lg bg-gradient-to-r from-blue-600 to-indigo-600 border-none shadow-lg hover:shadow-xl transform hover:-translate-y-0.5 transition-all"
                    onClick={handleStart}
                >
                    开启智能投资之旅 🚀
                </button>
            </div>
        </div>
    )
}
